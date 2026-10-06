"""Kubernetes manifest generator for canvas graph resources."""
from __future__ import annotations

import re
from typing import Any


SUPPORTED_KUBERNETES_TYPES = {
    "kubernetes.namespace",
    "kubernetes.deployment",
    "kubernetes.service",
    "kubernetes.ingress",
    "kubernetes.config_map",
    "kubernetes.secret_ref",
    "kubernetes.pvc",
    "kubernetes.hpa",
}


def validate_kubernetes_canvas(canvas_data: dict[str, Any]) -> dict[str, Any]:
    """Validate Kubernetes canvas resources before cluster-side dry-run.

    This is intentionally local and read-only. Real Kubernetes server dry-run can
    be layered on top once kubeconfig/credential handling is explicit.
    """
    graph = canvas_data.get("graph") or {}
    nodes = [node for node in graph.get("nodes") or [] if isinstance(node, dict)]
    kube_nodes = [
        node
        for node in nodes
        if str(node.get("type") or "") in SUPPORTED_KUBERNETES_TYPES
    ]
    issues: list[dict[str, Any]] = []
    if not kube_nodes:
        issues.append(
            {
                "severity": "error",
                "code": "no_kubernetes_resources",
                "message": "Kubernetes 리소스가 없습니다.",
                "node_id": None,
            }
        )

    resources: dict[tuple[str, str, str], dict[str, Any]] = {}
    deployments: set[tuple[str, str]] = set()
    services: set[tuple[str, str]] = set()
    namespaces: set[str] = set()

    for node in kube_nodes:
        node_type = str(node.get("type") or "")
        props = _props(node)
        kind = _kind_for_type(node_type)
        name = _resource_name(node)
        namespace = name if kind == "Namespace" else _k8s_name(props.get("namespace") or "default")
        key = (kind, namespace, name)
        if key in resources:
            issues.append(
                {
                    "severity": "error",
                    "code": "duplicate_resource",
                    "message": f"{kind} {namespace}/{name} 리소스가 중복됩니다.",
                    "node_id": node.get("id"),
                }
            )
        resources[key] = node
        if kind == "Namespace":
            namespaces.add(name)
        if kind == "Deployment":
            deployments.add((namespace, name))
            if not str(props.get("image") or "").strip():
                issues.append(
                    {
                        "severity": "warning",
                        "code": "deployment_default_image",
                        "message": "Deployment image가 비어 있어 기본 nginx:1.27로 생성됩니다.",
                        "node_id": node.get("id"),
                    }
                )
        if kind == "Service":
            services.add((namespace, name))

    for node in kube_nodes:
        node_type = str(node.get("type") or "")
        props = _props(node)
        name = _resource_name(node)
        namespace = _k8s_name(props.get("namespace") or "default")
        if namespaces and namespace not in namespaces and node_type != "kubernetes.namespace":
            issues.append(
                {
                    "severity": "warning",
                    "code": "namespace_not_declared",
                    "message": f"Namespace {namespace} 리소스가 캔버스에 선언되어 있지 않습니다.",
                    "node_id": node.get("id"),
                }
            )
        if node_type == "kubernetes.service":
            selector = _k8s_name(props.get("selector") or name)
            if (namespace, selector) not in deployments:
                issues.append(
                    {
                        "severity": "warning",
                        "code": "service_selector_unmatched",
                        "message": f"Service selector app={selector} 와 일치하는 Deployment가 없습니다.",
                        "node_id": node.get("id"),
                    }
                )
        if node_type == "kubernetes.ingress":
            service_name = _k8s_name(props.get("service_name") or name)
            if (namespace, service_name) not in services:
                issues.append(
                    {
                        "severity": "error",
                        "code": "ingress_service_missing",
                        "message": f"Ingress 대상 Service {namespace}/{service_name} 를 찾을 수 없습니다.",
                        "node_id": node.get("id"),
                    }
                )
        if node_type == "kubernetes.hpa":
            target = _k8s_name(props.get("target_deployment") or name)
            if (namespace, target) not in deployments:
                issues.append(
                    {
                        "severity": "error",
                        "code": "hpa_target_missing",
                        "message": f"HPA 대상 Deployment {namespace}/{target} 를 찾을 수 없습니다.",
                        "node_id": node.get("id"),
                    }
                )

    yaml_string = generate_kubernetes_yaml(canvas_data)
    if kube_nodes and not yaml_string.strip():
        issues.append(
            {
                "severity": "error",
                "code": "manifest_empty",
                "message": "Kubernetes YAML이 생성되지 않았습니다.",
                "node_id": None,
            }
        )
    has_errors = any(issue["severity"] == "error" for issue in issues)
    return {
        "ok": not has_errors,
        "mode": "server_validation",
        "issues": issues,
        "summary": {
            "resources": len(kube_nodes),
            "errors": sum(1 for issue in issues if issue["severity"] == "error"),
            "warnings": sum(1 for issue in issues if issue["severity"] == "warning"),
        },
        "yaml": yaml_string,
    }


def generate_kubernetes_yaml(canvas_data: dict[str, Any]) -> str:
    """Render supported Kubernetes canvas nodes as multi-document YAML."""
    graph = canvas_data.get("graph") or {}
    nodes = graph.get("nodes") or []
    documents: list[str] = []

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type") or "")
        if node_type not in SUPPORTED_KUBERNETES_TYPES:
            continue
        rendered = _render_node(node_type, node)
        if rendered:
            documents.append(rendered)

    if not documents:
        return ""
    return "\n---\n".join(documents) + "\n"


def _render_node(node_type: str, node: dict[str, Any]) -> str:
    props = _props(node)
    name = _resource_name(node)
    namespace = _k8s_name(props.get("namespace") or "default")

    if node_type == "kubernetes.namespace":
        name = _k8s_name(props.get("name") or node.get("display_name") or node.get("id") or "namespace")
        return _yaml(
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {"name": name},
            }
        )

    if node_type == "kubernetes.deployment":
        replicas = _int(props.get("replicas"), 2)
        image = str(props.get("image") or "nginx:1.27")
        port = _int(props.get("container_port"), 80)
        labels = _labels(name, props.get("labels"))
        return _yaml(
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": name, "namespace": namespace, "labels": labels},
                "spec": {
                    "replicas": replicas,
                    "selector": {"matchLabels": {"app": labels["app"]}},
                    "template": {
                        "metadata": {"labels": labels},
                        "spec": {
                            "containers": [
                                {
                                    "name": name,
                                    "image": image,
                                    "ports": [{"containerPort": port}],
                                }
                            ]
                        },
                    },
                },
            }
        )

    if node_type == "kubernetes.service":
        service_type = str(props.get("service_type") or "ClusterIP")
        port = _int(props.get("port"), 80)
        target_port = _int(props.get("target_port"), port)
        selector = _k8s_name(props.get("selector") or name)
        return _yaml(
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": name, "namespace": namespace},
                "spec": {
                    "type": service_type,
                    "selector": {"app": selector},
                    "ports": [{"port": port, "targetPort": target_port}],
                },
            }
        )

    if node_type == "kubernetes.ingress":
        service_name = _k8s_name(props.get("service_name") or name)
        service_port = _int(props.get("service_port"), 80)
        host = str(props.get("host") or f"{name}.local")
        path = str(props.get("path") or "/")
        spec: dict[str, Any] = {
            "rules": [
                {
                    "host": host,
                    "http": {
                        "paths": [
                            {
                                "path": path,
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": service_name,
                                        "port": {"number": service_port},
                                    }
                                },
                            }
                        ]
                    },
                }
            ]
        }
        ingress_class_name = str(props.get("ingress_class_name") or "")
        if ingress_class_name:
            spec["ingressClassName"] = ingress_class_name
        return _yaml(
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {"name": name, "namespace": namespace},
                "spec": spec,
            }
        )

    if node_type == "kubernetes.config_map":
        return _yaml(
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": name, "namespace": namespace},
                "data": _data_map(props.get("data")),
            }
        )

    if node_type == "kubernetes.secret_ref":
        secret_name = _k8s_name(props.get("name") or node.get("display_name") or node.get("id") or "secret")
        return "\n".join(
            [
                f"# Secret reference: {secret_name}",
                f"# Existing Kubernetes Secret expected in namespace {namespace}.",
                "# Eolgae intentionally does not render Secret data.",
            ]
        )

    if node_type == "kubernetes.pvc":
        pvc_spec: dict[str, Any] = {
            "accessModes": [str(props.get("access_mode") or "ReadWriteOnce")],
            "resources": {"requests": {"storage": str(props.get("storage") or "10Gi")}},
        }
        storage_class_name = str(props.get("storage_class_name") or "")
        if storage_class_name:
            pvc_spec["storageClassName"] = storage_class_name
        return _yaml(
            {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {"name": name, "namespace": namespace},
                "spec": pvc_spec,
            }
        )

    if node_type == "kubernetes.hpa":
        target = _k8s_name(props.get("target_deployment") or name)
        return _yaml(
            {
                "apiVersion": "autoscaling/v2",
                "kind": "HorizontalPodAutoscaler",
                "metadata": {"name": name, "namespace": namespace},
                "spec": {
                    "scaleTargetRef": {
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "name": target,
                    },
                    "minReplicas": _int(props.get("min_replicas"), 1),
                    "maxReplicas": _int(props.get("max_replicas"), 5),
                    "metrics": [
                        {
                            "type": "Resource",
                            "resource": {
                                "name": "cpu",
                                "target": {
                                    "type": "Utilization",
                                    "averageUtilization": _int(props.get("cpu_utilization"), 70),
                                },
                            },
                        }
                    ],
                },
            }
        )

    return ""


def _kind_for_type(node_type: str) -> str:
    return {
        "kubernetes.namespace": "Namespace",
        "kubernetes.deployment": "Deployment",
        "kubernetes.service": "Service",
        "kubernetes.ingress": "Ingress",
        "kubernetes.config_map": "ConfigMap",
        "kubernetes.secret_ref": "SecretRef",
        "kubernetes.pvc": "PersistentVolumeClaim",
        "kubernetes.hpa": "HorizontalPodAutoscaler",
    }.get(node_type, "Resource")


def _props(node: dict[str, Any]) -> dict[str, Any]:
    props = node.get("properties")
    return props if isinstance(props, dict) else {}


def _resource_name(node: dict[str, Any]) -> str:
    props = _props(node)
    return _k8s_name(props.get("name") or node.get("display_name") or node.get("id") or "resource")


def _k8s_name(value: object) -> str:
    raw = str(value or "resource").strip().lower()
    raw = re.sub(r"[^a-z0-9-]+", "-", raw)
    raw = re.sub(r"-+", "-", raw).strip("-")
    if not raw:
        raw = "resource"
    if not re.match(r"^[a-z0-9]", raw):
        raw = f"resource-{raw}"
    return raw[:63].rstrip("-") or "resource"


def _labels(name: str, value: object) -> dict[str, str]:
    labels = {"app": name}
    if isinstance(value, dict):
        for key, item in value.items():
            if key:
                labels[str(key)] = str(item)
    return labels


def _data_map(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items() if key}
    if not isinstance(value, str):
        return {}
    data: dict[str, str] = {}
    for line in value.splitlines():
        if not line.strip() or "=" not in line:
            continue
        key, item = line.split("=", 1)
        key = key.strip()
        if key:
            data[key] = item.strip()
    return data


def _int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _yaml(value: Any, indent: int = 0) -> str:
    lines = _yaml_lines(value, indent)
    return "\n".join(lines)


def _yaml_lines(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_yaml_lines(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                if not item:
                    lines.append(f"{prefix}- {{}}")
                    continue
                first_key = next(iter(item))
                first_value = item[first_key]
                rest = {key: val for key, val in item.items() if key != first_key}
                if isinstance(first_value, (dict, list)):
                    lines.append(f"{prefix}- {first_key}:")
                    lines.extend(_yaml_lines(first_value, indent + 4))
                else:
                    lines.append(f"{prefix}- {first_key}: {_scalar(first_value)}")
                if rest:
                    lines.extend(_yaml_lines(rest, indent + 2))
            else:
                lines.append(f"{prefix}- {_scalar(item)}")
        return lines
    return [f"{prefix}{_scalar(value)}"]


def _scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    if re.match(r"^[A-Za-z0-9_.:/@-]+$", text):
        return text
    return '"' + text.replace('"', '\\"') + '"'
