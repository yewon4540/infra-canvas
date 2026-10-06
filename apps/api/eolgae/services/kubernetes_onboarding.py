"""Kubernetes target onboarding helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass


_K8S_NAME_RE = re.compile(r"[^a-z0-9.-]+")


@dataclass(frozen=True)
class KubernetesReadOnlyManifest:
    namespace: str
    service_account_name: str
    cluster_role_name: str
    cluster_role_binding_name: str
    manifest: str
    apply_command: str
    token_command: str
    ca_command: str
    endpoint_command: str


def kubernetes_name(value: str | None, fallback: str) -> str:
    """Return a conservative Kubernetes metadata.name value."""
    candidate = _K8S_NAME_RE.sub("-", (value or fallback).strip().lower())
    candidate = candidate.strip(".-")
    return candidate or fallback


def build_read_only_manifest(
    *,
    namespace: str = "eolgae-system",
    service_account_name: str = "eolgae-reader",
    cluster_role_name: str = "eolgae-readonly",
    cluster_role_binding_name: str = "eolgae-reader",
) -> KubernetesReadOnlyManifest:
    namespace = kubernetes_name(namespace, "eolgae-system")
    service_account_name = kubernetes_name(service_account_name, "eolgae-reader")
    cluster_role_name = kubernetes_name(cluster_role_name, "eolgae-readonly")
    cluster_role_binding_name = kubernetes_name(
        cluster_role_binding_name,
        "eolgae-reader",
    )
    manifest = f"""apiVersion: v1
kind: Namespace
metadata:
  name: {namespace}
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {service_account_name}
  namespace: {namespace}
  labels:
    app.kubernetes.io/managed-by: eolgae
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: {cluster_role_name}
rules:
  - apiGroups: [""]
    resources:
      - namespaces
      - nodes
      - pods
      - services
      - endpoints
      - configmaps
      - persistentvolumeclaims
      - events
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources:
      - deployments
      - replicasets
      - statefulsets
      - daemonsets
    verbs: ["get", "list", "watch"]
  - apiGroups: ["networking.k8s.io"]
    resources:
      - ingresses
      - networkpolicies
    verbs: ["get", "list", "watch"]
  - apiGroups: ["autoscaling"]
    resources:
      - horizontalpodautoscalers
    verbs: ["get", "list", "watch"]
  - apiGroups: ["batch"]
    resources:
      - jobs
      - cronjobs
    verbs: ["get", "list", "watch"]
  - apiGroups: ["argoproj.io"]
    resources:
      - applications
      - applicationsets
    verbs: ["get", "list", "watch"]
  - apiGroups:
      - helm.toolkit.fluxcd.io
      - kustomize.toolkit.fluxcd.io
      - source.toolkit.fluxcd.io
    resources: ["*"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: {cluster_role_binding_name}
  labels:
    app.kubernetes.io/managed-by: eolgae
subjects:
  - kind: ServiceAccount
    name: {service_account_name}
    namespace: {namespace}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: {cluster_role_name}
"""
    return KubernetesReadOnlyManifest(
        namespace=namespace,
        service_account_name=service_account_name,
        cluster_role_name=cluster_role_name,
        cluster_role_binding_name=cluster_role_binding_name,
        manifest=manifest,
        apply_command="kubectl apply -f eolgae-readonly-rbac.yaml",
        token_command=(
            f"kubectl -n {namespace} create token {service_account_name} "
            "--duration=24h"
        ),
        ca_command=(
            "kubectl config view --raw --minify "
            "-o jsonpath='{.clusters[0].cluster.certificate-authority-data}'"
        ),
        endpoint_command=(
            "kubectl config view --raw --minify "
            "-o jsonpath='{.clusters[0].cluster.server}'"
        ),
    )
