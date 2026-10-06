from __future__ import annotations

import os
import sys
import types
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret")

db_module = types.ModuleType("eolgae.db")
db_module.get_db = Mock()
db_module.SessionLocal = Mock()
sys.modules.setdefault("eolgae.db", db_module)

auth_dependencies = types.ModuleType("eolgae.auth.dependencies")
auth_dependencies.get_current_user = Mock()
sys.modules.setdefault("eolgae.auth.dependencies", auth_dependencies)

dramatiq = types.ModuleType("dramatiq")


def _actor(**_kwargs):
    def decorate(fn):
        fn.send = Mock()
        return fn

    return decorate


dramatiq.actor = _actor
dramatiq.set_broker = Mock()
dramatiq_brokers = types.ModuleType("dramatiq.brokers")
dramatiq_redis = types.ModuleType("dramatiq.brokers.redis")
dramatiq_redis.RedisBroker = Mock()
sys.modules.setdefault("dramatiq", dramatiq)
sys.modules.setdefault("dramatiq.brokers", dramatiq_brokers)
sys.modules.setdefault("dramatiq.brokers.redis", dramatiq_redis)

from eolgae.routers import deployments
from eolgae.workers import plan as plan_worker


class ApplyDeploymentRouteTests(unittest.TestCase):
    def test_deployment_summary_counts_user_deployments(self) -> None:
        db = Mock()
        db.scalars.return_value.all.return_value = [
            SimpleNamespace(status="success"),
            SimpleNamespace(status="failed"),
            SimpleNamespace(status="planning"),
            SimpleNamespace(status="applied"),
            SimpleNamespace(status="destroyed"),
        ]

        summary = deployments.deployment_summary(
            user=SimpleNamespace(id=uuid4()),
            db=db,
        )

        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["approval_pending"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["active"], 1)
        self.assertEqual(summary["applied"], 1)
        self.assertEqual(summary["destroyed"], 1)

    def test_canvas_deployment_history_returns_canvas_runs(self) -> None:
        canvas_id = uuid4()
        user_id = uuid4()
        plan_id = uuid4()
        apply_id = uuid4()
        created_at = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        db = Mock()
        db.get.return_value = SimpleNamespace(
            id=canvas_id,
            owner_id=user_id,
            deleted_at=None,
        )
        db.scalars.return_value.all.return_value = [
            SimpleNamespace(
                id=apply_id,
                canvas_id=canvas_id,
                mode="apply",
                status="applied",
                created_at=created_at,
                finished_at=created_at,
                error_message=None,
                source_plan_deployment_id=plan_id,
            ),
            SimpleNamespace(
                id=plan_id,
                canvas_id=canvas_id,
                mode="plan",
                status="success",
                created_at=created_at,
                finished_at=None,
                error_message=None,
                source_plan_deployment_id=None,
            ),
        ]

        history = deployments.canvas_deployment_history(
            canvas_id=canvas_id,
            limit=10,
            user=SimpleNamespace(id=user_id),
            db=db,
        )

        self.assertEqual(history["canvas_id"], str(canvas_id))
        self.assertEqual(history["total_returned"], 2)
        self.assertEqual(history["items"][0]["mode"], "apply")
        self.assertEqual(history["items"][1]["requires_approval"], True)

    def test_resource_bindings_are_attached_to_matching_canvas_nodes(self) -> None:
        graph = {
            "nodes": [
                {
                    "id": "node-s3",
                    "type": "aws.s3.bucket",
                    "display_name": "bucket",
                    "position": {"x": 0, "y": 0},
                    "properties": {},
                    "metadata": {},
                },
                {
                    "id": "node-ec2",
                    "type": "aws.ec2.instance",
                    "display_name": "app",
                    "position": {"x": 100, "y": 0},
                    "properties": {},
                    "metadata": {},
                },
            ],
            "edges": [],
            "groups": [],
        }
        updated = plan_worker._apply_resource_bindings_to_graph(
            graph,
            [
                {
                    "provider": "aws",
                    "resource_address": "aws_s3_bucket.node_s3",
                    "resource_type": "aws_s3_bucket",
                    "resource_name": "node_s3",
                    "id": "test-bucket",
                    "arn": "arn:aws:s3:::test-bucket",
                    "display_name": "test-bucket",
                },
                {
                    "provider": "aws",
                    "resource_address": "aws_s3_bucket_public_access_block.node_s3_pab",
                    "resource_type": "aws_s3_bucket_public_access_block",
                    "resource_name": "node_s3_pab",
                    "id": "test-bucket",
                },
            ],
        )

        s3 = updated["nodes"][0]
        ec2 = updated["nodes"][1]
        self.assertEqual(s3["aws_binding"]["id"], "test-bucket")
        self.assertEqual(s3["aws_binding"]["arn"], "arn:aws:s3:::test-bucket")
        self.assertEqual(s3["aws_binding"]["status"], "bound")
        self.assertNotIn("aws_binding", ec2)

    def test_destroy_clears_resource_bindings_from_canvas_nodes(self) -> None:
        graph = {
            "nodes": [
                {
                    "id": "node-s3",
                    "type": "aws.s3.bucket",
                    "aws_binding": {"id": "test-bucket"},
                }
            ],
            "edges": [],
            "groups": [],
        }

        updated = plan_worker._clear_resource_bindings(graph)

        self.assertNotIn("aws_binding", updated["nodes"][0])

    def test_repeat_apply_for_same_source_plan_is_rejected(self) -> None:
        canvas_id = uuid4()
        user_id = uuid4()
        source_plan_id = uuid4()
        existing_apply_id = uuid4()
        canvas_version_id = uuid4()
        canvas = SimpleNamespace(id=canvas_id, owner_id=user_id, deleted_at=None)
        user = SimpleNamespace(id=user_id)
        source_plan = SimpleNamespace(
            id=source_plan_id,
            canvas_id=canvas_id,
            canvas_version_id=canvas_version_id,
            mode="plan",
            status="approved",
            plan_artifact={"filename": "tfplan"},
            state_backend={"type": "s3"},
        )
        db = Mock()
        db.get.return_value = canvas
        db.scalar.side_effect = [source_plan, existing_apply_id]

        with self.assertRaises(HTTPException) as ctx:
            deployments.create_apply_deployment(
                canvas_id=canvas_id,
                deployment_id=source_plan_id,
                user=user,
                db=db,
            )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, deployments.REPEAT_APPLY_DETAIL)
        db.add.assert_not_called()

    def test_first_apply_for_source_plan_is_created(self) -> None:
        canvas_id = uuid4()
        user_id = uuid4()
        source_plan_id = uuid4()
        canvas_version_id = uuid4()
        canvas = SimpleNamespace(id=canvas_id, owner_id=user_id, deleted_at=None)
        user = SimpleNamespace(id=user_id)
        source_plan = SimpleNamespace(
            id=source_plan_id,
            canvas_id=canvas_id,
            canvas_version_id=canvas_version_id,
            mode="plan",
            status="approved",
            aws_account_snapshot={"binding_status": "verified"},
            plan_artifact={"filename": "tfplan"},
            state_backend={"type": "s3"},
            approved_by=user_id,
            approved_at=None,
        )
        db = Mock()
        db.get.return_value = canvas
        db.scalar.side_effect = [source_plan, None, None]
        apply_id = uuid4()
        db.flush.side_effect = lambda: setattr(db.add.call_args.args[0], "id", apply_id)
        db.refresh.side_effect = lambda deployment: None

        with patch.object(deployments.run_apply, "send") as send:
            created = deployments.create_apply_deployment(
                canvas_id=canvas_id,
                deployment_id=source_plan_id,
                user=user,
                db=db,
            )

        self.assertEqual(created.mode, "apply")
        self.assertEqual(created.source_plan_deployment_id, source_plan_id)
        self.assertEqual(created.progress_events[0]["step"], "queue")
        self.assertEqual(created.progress_events[0]["label"], "Apply 큐 등록")
        send.assert_called_once_with(str(apply_id))

    def test_repeat_destroy_for_same_source_plan_is_rejected(self) -> None:
        canvas_id = uuid4()
        user_id = uuid4()
        source_plan_id = uuid4()
        existing_destroy_id = uuid4()
        canvas_version_id = uuid4()
        canvas = SimpleNamespace(id=canvas_id, owner_id=user_id, deleted_at=None)
        user = SimpleNamespace(id=user_id)
        source_plan = SimpleNamespace(
            id=source_plan_id,
            canvas_id=canvas_id,
            canvas_version_id=canvas_version_id,
            mode="destroy",
            status="approved",
            plan_artifact={"filename": "tfplan"},
            state_backend={"type": "s3"},
        )
        db = Mock()
        db.get.return_value = canvas
        db.scalar.side_effect = [source_plan, existing_destroy_id]

        with self.assertRaises(HTTPException) as ctx:
            deployments.create_destroy_deployment(
                canvas_id=canvas_id,
                deployment_id=source_plan_id,
                user=user,
                db=db,
            )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, deployments.REPEAT_DESTROY_DETAIL)
        db.add.assert_not_called()

    def test_first_destroy_for_source_plan_is_created(self) -> None:
        canvas_id = uuid4()
        user_id = uuid4()
        source_plan_id = uuid4()
        canvas_version_id = uuid4()
        canvas = SimpleNamespace(id=canvas_id, owner_id=user_id, deleted_at=None)
        user = SimpleNamespace(id=user_id)
        source_plan = SimpleNamespace(
            id=source_plan_id,
            canvas_id=canvas_id,
            canvas_version_id=canvas_version_id,
            mode="destroy",
            status="approved",
            aws_account_snapshot={"binding_status": "verified"},
            plan_artifact={"filename": "tfplan"},
            state_backend={"type": "s3"},
            approved_by=user_id,
            approved_at=None,
        )
        db = Mock()
        db.get.return_value = canvas
        db.scalar.side_effect = [source_plan, None, None]
        destroy_id = uuid4()
        db.flush.side_effect = lambda: setattr(db.add.call_args.args[0], "id", destroy_id)
        db.refresh.side_effect = lambda deployment: None

        with patch.object(deployments.run_destroy, "send") as send:
            created = deployments.create_destroy_deployment(
                canvas_id=canvas_id,
                deployment_id=source_plan_id,
                user=user,
                db=db,
            )

        self.assertEqual(created.mode, "destroy")
        self.assertEqual(created.source_plan_deployment_id, source_plan_id)
        self.assertEqual(created.progress_events[0]["step"], "queue")
        self.assertEqual(created.progress_events[0]["label"], "Destroy 큐 등록")
        send.assert_called_once_with(str(destroy_id))


if __name__ == "__main__":
    unittest.main()
