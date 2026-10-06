from __future__ import annotations

import unittest

from eolgae.pipelines.kubernetes_generator import generate_kubernetes_yaml


class KubernetesGeneratorTests(unittest.TestCase):
    def test_supported_kubernetes_nodes_generate_manifests(self) -> None:
        canvas = {
            "graph": {
                "nodes": [
                    {
                        "id": "ns1",
                        "type": "kubernetes.namespace",
                        "properties": {"name": "platform"},
                    },
                    {
                        "id": "web",
                        "type": "kubernetes.deployment",
                        "display_name": "web-api",
                        "properties": {
                            "namespace": "platform",
                            "replicas": 3,
                            "image": "ghcr.io/example/web:1.0",
                            "container_port": 8080,
                        },
                    },
                    {
                        "id": "svc",
                        "type": "kubernetes.service",
                        "display_name": "web-api",
                        "properties": {
                            "namespace": "platform",
                            "selector": "web-api",
                            "port": 80,
                            "target_port": 8080,
                        },
                    },
                    {
                        "id": "ing",
                        "type": "kubernetes.ingress",
                        "display_name": "web-api",
                        "properties": {
                            "namespace": "platform",
                            "host": "app.example.com",
                            "service_name": "web-api",
                            "service_port": 80,
                            "ingress_class_name": "nginx",
                        },
                    },
                    {
                        "id": "cm",
                        "type": "kubernetes.config_map",
                        "display_name": "web-config",
                        "properties": {
                            "namespace": "platform",
                            "data": "LOG_LEVEL=info\nFEATURE_FLAG=true",
                        },
                    },
                    {
                        "id": "secret",
                        "type": "kubernetes.secret_ref",
                        "properties": {"namespace": "platform", "name": "web-secret"},
                    },
                    {
                        "id": "pvc",
                        "type": "kubernetes.pvc",
                        "display_name": "web-data",
                        "properties": {
                            "namespace": "platform",
                            "storage": "20Gi",
                            "storage_class_name": "gp3",
                        },
                    },
                    {
                        "id": "hpa",
                        "type": "kubernetes.hpa",
                        "display_name": "web-api",
                        "properties": {
                            "namespace": "platform",
                            "target_deployment": "web-api",
                            "min_replicas": 2,
                            "max_replicas": 8,
                            "cpu_utilization": 65,
                        },
                    },
                ]
            }
        }

        yaml = generate_kubernetes_yaml(canvas)

        self.assertIn("kind: Namespace", yaml)
        self.assertIn("name: platform", yaml)
        self.assertIn("kind: Deployment", yaml)
        self.assertIn("replicas: 3", yaml)
        self.assertIn("image: ghcr.io/example/web:1.0", yaml)
        self.assertIn("containerPort: 8080", yaml)
        self.assertIn("kind: Service", yaml)
        self.assertIn("targetPort: 8080", yaml)
        self.assertIn("kind: Ingress", yaml)
        self.assertIn("host: app.example.com", yaml)
        self.assertIn("ingressClassName: nginx", yaml)
        self.assertIn("kind: ConfigMap", yaml)
        self.assertIn("LOG_LEVEL: info", yaml)
        self.assertIn("# Secret reference: web-secret", yaml)
        self.assertIn("kind: PersistentVolumeClaim", yaml)
        self.assertIn("storageClassName: gp3", yaml)
        self.assertIn("kind: HorizontalPodAutoscaler", yaml)
        self.assertIn("averageUtilization: 65", yaml)

    def test_secret_reference_does_not_render_secret_data(self) -> None:
        yaml = generate_kubernetes_yaml(
            {
                "graph": {
                    "nodes": [
                        {
                            "id": "secret",
                            "type": "kubernetes.secret_ref",
                            "properties": {
                                "namespace": "prod",
                                "name": "db-password",
                                "data": {"password": "plain-text"},
                            },
                        }
                    ]
                }
            }
        )

        self.assertIn("# Secret reference: db-password", yaml)
        self.assertNotIn("kind: Secret", yaml)
        self.assertNotIn("plain-text", yaml)
