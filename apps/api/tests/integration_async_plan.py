"""Seed a Plan job, enqueue it, and verify worker persistence."""
from __future__ import annotations

import time
import uuid

from sqlalchemy import select

from eolgae.db import SessionLocal
from eolgae.models.canvas import Canvas
from eolgae.models.deployment import AuditLog, CanvasVersion, Deployment
from eolgae.models.user import User
from eolgae.routers.deployments import create_plan_deployment


def main() -> None:
    with SessionLocal() as db:
        suffix = uuid.uuid4().hex[:12]
        user = User(
            username=f"async-plan-{suffix}",
            display_name="Async Plan Test",
            password_hash=None,
        )
        db.add(user)
        db.flush()
        canvas = Canvas(
            name="Async Plan Test",
            owner_id=user.id,
            graph={"nodes": [], "edges": [], "groups": []},
            aws_account={
                "account_id": "123456789012",
                "default_region": "ap-northeast-2",
                "external_id": "integration-external-id",
                "role_arn": (
                    "arn:aws:iam::123456789012:role/EolgaeDeployRole"
                ),
                "binding_status": "verified",
            },
        )
        db.add(canvas)
        db.commit()
        db.refresh(user)
        db.refresh(canvas)
        deployment = create_plan_deployment(canvas.id, user=user, db=db)
        deployment_id = deployment.id
        print(f"ENQUEUED={deployment_id}", flush=True)

    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        with SessionLocal() as db:
            deployment = db.get(Deployment, deployment_id)
            if deployment and deployment.status in {"success", "failed"}:
                break
        time.sleep(1)
    else:
        raise RuntimeError("deployment did not finish within 90 seconds")

    with SessionLocal() as db:
        deployment = db.get(Deployment, deployment_id)
        assert deployment is not None
        assert deployment.status == "success", deployment.error_message
        assert deployment.assumed_arn and "assumed-role" in deployment.assumed_arn
        assert deployment.plan_result and deployment.plan_result["ok"] is True
        assert "No changes" in (deployment.plan_result.get("plan_text") or "")

        version_count = len(
            db.scalars(
                select(CanvasVersion).where(
                    CanvasVersion.canvas_id == deployment.canvas_id
                )
            ).all()
        )
        audit_actions = db.scalars(
            select(AuditLog.action).where(
                AuditLog.entity_id == deployment.id
            )
        ).all()
        assert version_count == 1
        assert audit_actions.count("deployment.start") == 1
        assert audit_actions.count("deployment.complete") == 1
        print(
            "ASYNC_PLAN_OK "
            f"status={deployment.status} "
            f"version_count={version_count} "
            f"audits={','.join(audit_actions)}",
            flush=True,
        )


if __name__ == "__main__":
    main()
