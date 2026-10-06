from __future__ import annotations

import unittest

from eolgae.pipelines.feedback import build_rule_based_feedback, parse_feedback


def _node(
    node_id: str,
    node_type: str,
    *,
    parent: str | None = None,
    props: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "id": node_id,
        "type": node_type,
        "parent_group_id": parent,
        "properties": props or {},
    }


def _edge(
    edge_id: str,
    source: str,
    target: str,
    edge_type: str,
) -> dict[str, object]:
    return {"id": edge_id, "source": source, "target": target, "type": edge_type}


def good_structure_canvas() -> dict[str, object]:
    return {
        "nodes": [
            _node("vpc", "aws.ec2.vpc", props={"cidr": "10.0.0.0/16"}),
            _node(
                "subnet-a",
                "aws.ec2.subnet",
                parent="vpc",
                props={"cidr": "10.0.1.0/24", "availability_zone": "ap-northeast-2a"},
            ),
            _node(
                "subnet-c",
                "aws.ec2.subnet",
                parent="vpc",
                props={"cidr": "10.0.2.0/24", "availability_zone": "ap-northeast-2c"},
            ),
            _node("alb-sg", "aws.ec2.security_group", parent="vpc"),
            _node("app-sg", "aws.ec2.security_group", parent="vpc"),
            _node("db-sg", "aws.ec2.security_group", parent="vpc"),
            _node("alb", "aws.ec2.alb", parent="vpc", props={"listener_port": 443}),
            _node("asg", "aws.ec2.asg", parent="subnet-a", props={"desired_capacity": 2}),
            _node("app-role", "aws.iam.role"),
            _node("db", "aws.rds.db_instance", parent="subnet-c", props={"multi_az": True}),
            _node("assets", "aws.s3.bucket", props={"public_access_block": True, "versioning": True}),
        ],
        "edges": [
            _edge("e-alb-sg", "alb-sg", "alb", "reference"),
            _edge("e-app-sg", "app-sg", "asg", "reference"),
            _edge("e-db-sg", "db-sg", "db", "reference"),
            _edge("e-alb-app", "alb", "asg", "network"),
            _edge("e-app-db", "asg", "db", "network"),
            _edge("e-app-role", "asg", "app-role", "reference"),
            _edge("e-app-s3", "asg", "assets", "data_flow"),
        ],
    }


def dangerous_structure_canvas() -> dict[str, object]:
    return {
        "nodes": [
            _node("vpc", "aws.ec2.vpc"),
            _node("subnet-a", "aws.ec2.subnet", parent="vpc", props={"availability_zone": "ap-northeast-2a"}),
            _node("alb", "aws.ec2.alb", parent="subnet-a", props={"listener_port": 80}),
            _node("web", "aws.ec2.instance", parent="subnet-a"),
            _node(
                "db",
                "aws.rds.db_instance",
                parent="subnet-a",
                props={"multi_az": False, "publicly_accessible": True},
            ),
            _node("dump", "aws.s3.bucket", props={"public_access_block": False, "versioning": False}),
        ],
        "edges": [
            _edge("e-alb-web", "alb", "web", "network"),
            _edge("e-web-db", "web", "db", "network"),
            _edge("e-s3-db", "dump", "db", "network"),
        ],
    }


def ambiguous_real_world_canvas() -> dict[str, object]:
    return {
        "nodes": [
            _node("vpc", "aws.ec2.vpc"),
            _node("subnet-a", "aws.ec2.subnet", parent="vpc", props={"availability_zone": "ap-northeast-2a"}),
            _node("subnet-c", "aws.ec2.subnet", parent="vpc", props={"availability_zone": "ap-northeast-2c"}),
            _node("alb-sg", "aws.ec2.security_group", parent="vpc"),
            _node("alb", "aws.ec2.alb", parent="vpc", props={"listener_port": 80}),
            _node("web", "aws.ec2.instance", parent="subnet-a"),
            _node("db", "aws.rds.db_instance", parent="subnet-c", props={"multi_az": False}),
            _node("assets", "aws.s3.bucket", props={"public_access_block": True, "versioning": False}),
        ],
        "edges": [
            _edge("e-alb-sg", "alb-sg", "alb", "reference"),
            _edge("e-alb-web", "alb", "web", "network"),
            _edge("e-web-db", "web", "db", "network"),
            _edge("e-web-s3", "web", "assets", "data_flow"),
        ],
    }


class FeedbackPipelineTests(unittest.TestCase):
    def test_good_structure_has_no_critical_or_high_rule_findings(self) -> None:
        severities = {item.severity for item in build_rule_based_feedback(good_structure_canvas())}

        self.assertNotIn("critical", severities)
        self.assertNotIn("high", severities)

    def test_dangerous_structure_gets_deep_security_ha_and_edge_findings(self) -> None:
        items = build_rule_based_feedback(dangerous_structure_canvas())

        self.assertTrue(any(item.severity == "critical" and item.target_node_id == "dump" for item in items))
        self.assertTrue(any(item.severity == "critical" and item.target_node_id == "db" for item in items))
        self.assertTrue(any(item.severity == "high" and item.category == "ha" for item in items))
        self.assertTrue(any(item.target_edge_id == "e-web-db" for item in items))
        self.assertFalse(any(item.severity == "medium" for item in items))
        self.assertFalse(any(item.severity == "low" for item in items))

    def test_ambiguous_alb_ec2_rds_s3_structure_gets_actionable_findings(self) -> None:
        items = build_rule_based_feedback(ambiguous_real_world_canvas())
        pairs = {(item.category, item.severity) for item in items}

        self.assertIn(("security", "high"), pairs)
        self.assertIn(("ha", "high"), pairs)
        self.assertTrue(any(item.target_node_id == "web" for item in items))
        self.assertTrue(
            any(
                item.target_edge_id == "e-web-s3"
                and item.category == "security"
                and item.severity == "high"
                for item in items
            )
        )

    def test_parse_preserves_all_severities_and_node_edge_annotations(self) -> None:
        raw = """
        {
          "items": [
            {
              "category": "security",
              "severity": "critical",
              "title": "critical item",
              "description": "critical description",
              "target_node_id": "db",
              "target_edge_id": null,
              "recommendation": "fix db"
            },
            {
              "category": "ha",
              "severity": "high",
              "title": "high item",
              "description": "high description",
              "target_node_id": null,
              "target_edge_id": "e-web-db",
              "recommendation": "fix edge"
            },
            {
              "category": "operations",
              "severity": "medium",
              "title": "medium item",
              "description": "medium description",
              "target_node_id": "web",
              "target_edge_id": null,
              "recommendation": "fix ops"
            },
            {
              "category": "cost",
              "severity": "low",
              "title": "low item",
              "description": "low description",
              "target_node_id": null,
              "target_edge_id": null,
              "recommendation": "fix cost"
            }
          ],
          "summary": "summary"
        }
        """

        response = parse_feedback({"nodes": [], "edges": []}, raw)
        severities = {item.severity for item in response.items}

        self.assertEqual({"critical", "high", "medium", "low"}, severities)
        self.assertTrue(any(item.target_node_id == "db" for item in response.items))
        self.assertTrue(any(item.target_edge_id == "e-web-db" for item in response.items))


if __name__ == "__main__":
    unittest.main()
