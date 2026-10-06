from __future__ import annotations

import unittest

from eolgae.pipelines.tofu_generator import generate_tofu
from eolgae.pipelines.validation import validate_canvas_for_plan


def _canvas(edges: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "aws_account": {"default_region": "ap-northeast-2"},
        "graph": {
            "nodes": [
                {
                    "id": "vpc1",
                    "type": "aws.ec2.vpc",
                    "properties": {"cidr": "10.0.0.0/16"},
                },
                {
                    "id": "subnet1",
                    "type": "aws.ec2.subnet",
                    "parent_group_id": "vpc1",
                    "properties": {
                        "cidr": "10.0.1.0/24",
                        "availability_zone": "ap-northeast-2a",
                    },
                },
                {
                    "id": "subnet2",
                    "type": "aws.ec2.subnet",
                    "parent_group_id": "vpc1",
                    "properties": {
                        "cidr": "10.0.2.0/24",
                        "availability_zone": "ap-northeast-2c",
                    },
                },
                {
                    "id": "sg1",
                    "type": "aws.ec2.security_group",
                    "display_name": "web-sg",
                    "parent_group_id": "vpc1",
                },
                {
                    "id": "alb1",
                    "type": "aws.ec2.alb",
                    "display_name": "web-alb",
                    "parent_group_id": "vpc1",
                },
            ],
            "edges": edges or [],
        },
    }


class GraphPipelineTests(unittest.TestCase):
    def test_security_group_association_is_optional_for_plan(self) -> None:
        self.assertEqual(validate_canvas_for_plan(_canvas()), [])

        hcl = generate_tofu(_canvas())
        self.assertIn("# security_groups = [...]", hcl)

    def test_explicit_security_group_association_generates_hcl_ref(self) -> None:
        canvas = _canvas(
            [
                {
                    "id": "edge1",
                    "source": "sg1",
                    "target": "alb1",
                    "type": "network",
                }
            ]
        )

        self.assertEqual(validate_canvas_for_plan(canvas), [])
        hcl = generate_tofu(canvas)
        self.assertIn("security_groups    = [aws_security_group.sg1.id]", hcl)

    def test_security_group_vpc_is_inferred_from_attached_resource(self) -> None:
        canvas = _canvas(
            [
                {
                    "id": "edge1",
                    "source": "sg1",
                    "target": "alb1",
                    "type": "reference",
                }
            ]
        )
        sg = canvas["graph"]["nodes"][3]  # type: ignore[index]
        sg["parent_group_id"] = None  # type: ignore[index]

        self.assertEqual(validate_canvas_for_plan(canvas), [])
        hcl = generate_tofu(canvas)
        self.assertIn("vpc_id = aws_vpc.vpc1.id", hcl)

    def test_subnet_cidr_must_be_inside_parent_vpc(self) -> None:
        canvas = _canvas()
        subnet = canvas["graph"]["nodes"][1]  # type: ignore[index]
        subnet["properties"]["cidr"] = "192.168.1.0/24"  # type: ignore[index]

        issues = validate_canvas_for_plan(canvas)

        self.assertTrue(
            any(issue["field"] == "placement.cidr" for issue in issues),
        )

    def test_route_table_edges_generate_route_and_associations(self) -> None:
        canvas = {
            "aws_account": {"default_region": "ap-northeast-2"},
            "graph": {
                "nodes": [
                    {
                        "id": "vpc1",
                        "type": "aws.ec2.vpc",
                        "properties": {"cidr": "10.0.0.0/16"},
                    },
                    {
                        "id": "subnet1",
                        "type": "aws.ec2.subnet",
                        "parent_group_id": "vpc1",
                        "properties": {
                            "cidr": "10.0.1.0/24",
                            "availability_zone": "ap-northeast-2a",
                            "type": "public",
                        },
                    },
                    {
                        "id": "subnet2",
                        "type": "aws.ec2.subnet",
                        "parent_group_id": "vpc1",
                        "properties": {
                            "cidr": "10.0.2.0/24",
                            "availability_zone": "ap-northeast-2c",
                            "type": "public",
                        },
                    },
                    {
                        "id": "igw1",
                        "type": "aws.ec2.internet_gateway",
                        "parent_group_id": "vpc1",
                    },
                    {
                        "id": "rt1",
                        "type": "aws.ec2.route_table",
                        "parent_group_id": "vpc1",
                        "properties": {
                            "routes": [{"cidr_block": "0.0.0.0/0"}],
                        },
                    },
                ],
                "edges": [
                    {
                        "id": "route1",
                        "source": "rt1",
                        "target": "igw1",
                        "type": "route",
                    },
                    {
                        "id": "assoc1",
                        "source": "rt1",
                        "target": "subnet1",
                        "type": "route",
                    },
                    {
                        "id": "assoc2",
                        "source": "rt1",
                        "target": "subnet2",
                        "type": "route",
                    },
                ],
            },
        }

        self.assertEqual(validate_canvas_for_plan(canvas), [])
        hcl = generate_tofu(canvas)

        self.assertIn('resource "aws_route_table" "rt1"', hcl)
        self.assertIn('gateway_id = aws_internet_gateway.igw1.id', hcl)
        self.assertIn(
            'resource "aws_route_table_association" "rt1_1"',
            hcl,
        )
        self.assertIn("subnet_id      = aws_subnet.subnet1.id", hcl)
        self.assertIn(
            'resource "aws_route_table_association" "rt1_2"',
            hcl,
        )
        self.assertIn("subnet_id      = aws_subnet.subnet2.id", hcl)

    def test_managed_aws_resources_include_system_tags_when_present(self) -> None:
        canvas = {
            "aws_account": {"default_region": "ap-northeast-2"},
            "system_tags": {
                "ManagedBy": "Eolgae",
                "EolgaeEnvironment": "dev",
                "EolgaeProjectGroup": "platform",
            },
            "graph": {
                "nodes": [
                    {
                        "id": "vpc1",
                        "type": "aws.ec2.vpc",
                        "properties": {"cidr": "10.0.0.0/16"},
                    },
                    {
                        "id": "subnet1",
                        "type": "aws.ec2.subnet",
                        "parent_group_id": "vpc1",
                        "properties": {
                            "cidr": "10.0.1.0/24",
                            "availability_zone": "ap-northeast-2a",
                        },
                    },
                    {
                        "id": "sg1",
                        "type": "aws.ec2.security_group",
                        "parent_group_id": "vpc1",
                    },
                    {
                        "id": "ec2",
                        "type": "aws.ec2.instance",
                        "parent_group_id": "subnet1",
                        "properties": {"ami_id": "ami-test"},
                    },
                    {
                        "id": "alb1",
                        "type": "aws.ec2.alb",
                        "parent_group_id": "vpc1",
                    },
                    {
                        "id": "asg1",
                        "type": "aws.ec2.asg",
                        "parent_group_id": "subnet1",
                    },
                    {
                        "id": "rds1",
                        "type": "aws.rds.db_instance",
                        "parent_group_id": "subnet1",
                    },
                    {
                        "id": "bucket1",
                        "type": "aws.s3.bucket",
                        "properties": {"bucket_name": "eolgae-test"},
                    },
                    {
                        "id": "role1",
                        "type": "aws.iam.role",
                    },
                    {
                        "id": "igw1",
                        "type": "aws.ec2.internet_gateway",
                        "parent_group_id": "vpc1",
                    },
                    {
                        "id": "nat1",
                        "type": "aws.ec2.nat_gateway",
                        "parent_group_id": "subnet1",
                    },
                    {
                        "id": "rt1",
                        "type": "aws.ec2.route_table",
                        "parent_group_id": "vpc1",
                    },
                ],
                "edges": [],
            },
        }

        hcl = generate_tofu(canvas)

        for resource_type, name in [
            ("aws_vpc", "vpc1"),
            ("aws_subnet", "subnet1"),
            ("aws_security_group", "sg1"),
            ("aws_instance", "ec2"),
            ("aws_lb", "alb1"),
            ("aws_db_instance", "rds1"),
            ("aws_db_subnet_group", "rds1"),
            ("aws_s3_bucket", "bucket1"),
            ("aws_iam_role", "role1"),
            ("aws_internet_gateway", "igw1"),
            ("aws_nat_gateway", "nat1"),
            ("aws_route_table", "rt1"),
        ]:
            resource_start = f'resource "{resource_type}" "{name}"'
            start = hcl.index(resource_start)
            end = hcl.find('\nresource "', start + len(resource_start))
            block = hcl[start:] if end == -1 else hcl[start:end]
            self.assertIn('EolgaeEnvironment = "dev"', block)
            self.assertIn('EolgaeProjectGroup = "platform"', block)

        self.assertIn('key                 = "EolgaeEnvironment"', hcl)
        self.assertIn('value               = "dev"', hcl)

    def test_system_tags_override_user_tags(self) -> None:
        canvas = {
            "aws_account": {"default_region": "ap-northeast-2"},
            "system_tags": {"ManagedBy": "Eolgae"},
            "graph": {
                "nodes": [
                    {
                        "id": "bucket1",
                        "type": "aws.s3.bucket",
                        "properties": {
                            "bucket_name": "eolgae-test",
                            "tags": {"ManagedBy": "user-value", "Owner": "platform"},
                        },
                    }
                ],
                "edges": [],
            },
        }

        hcl = generate_tofu(canvas)

        self.assertIn('ManagedBy = "Eolgae"', hcl)
        self.assertIn('Owner = "platform"', hcl)
        self.assertNotIn('ManagedBy = "user-value"', hcl)


if __name__ == "__main__":
    unittest.main()
