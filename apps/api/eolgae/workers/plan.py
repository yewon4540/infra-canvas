"""Dramatiq actor for cross-account OpenTofu Plan jobs."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import dramatiq

from eolgae.db import SessionLocal
from eolgae.execution.policy import require_direct_execution
from eolgae.models.canvas import Canvas
from eolgae.models.deployment import AuditLog, CanvasVersion, Deployment
from eolgae.pipelines.graph_model import NODE_TF_RESOURCE, normalize_name
from eolgae.pipelines.apply import (
    apply_approved_plan,
    assume_role_environment,
    build_state_backend,
    ensure_state_backend_resources,
    generate_plan,
    serialize_plan_result,
)
from eolgae.pipelines.artifacts import deployment_artifact_prefix

logger = logging.getLogger(__name__)

LOCAL_PLAN_APPLY_READINESS_NOTE = (
    "State backend bootstrap 권한이 없어 local backend로 read-only Plan을 실행함. "
    "이 Plan은 미리보기 전용이며 Apply하려면 EnableApplyPermissions=true 권한으로 "
    "remote state backend와 Plan artifact를 생성해야 함."
)


def _finish_failed(deployment_id: UUID, message: str) -> None:
    with SessionLocal() as db:
        deployment = db.get(Deployment, deployment_id)
        if deployment is None:
            return
        _append_progress_event(
            deployment,
            step="deployment",
            label="Deployment 종료",
            status="failed",
            message=message,
        )
        deployment.status = "failed"
        deployment.error_message = message
        deployment.finished_at = datetime.now(timezone.utc)
        db.add(
            AuditLog(
                actor_id=None,
                action="deployment.complete",
                entity_type="deployment",
                entity_id=deployment.id,
                after={"status": "failed", "error_message": message},
            )
        )
        db.commit()


def _record_progress_event(
    deployment_id: UUID,
    *,
    step: str,
    label: str,
    status: str,
    message: str | None = None,
) -> None:
    with SessionLocal() as db:
        deployment = db.get(Deployment, deployment_id)
        if deployment is None:
            return
        _append_progress_event(
            deployment,
            step=step,
            label=label,
            status=status,
            message=message,
        )
        db.commit()


def _append_progress_event(
    deployment: Deployment,
    *,
    step: str,
    label: str,
    status: str,
    message: str | None = None,
) -> None:
    events = list(deployment.progress_events or [])
    event: dict[str, Any] = {
        "step": step,
        "label": label,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if message:
        event["message"] = message
    deployment.progress_events = [*events, event]


def _progress_callback(deployment_id: UUID):
    def callback(step: str, label: str, status: str, message: str | None) -> None:
        _record_progress_event(
            deployment_id,
            step=step,
            label=label,
            status=status,
            message=message,
        )

    return callback


@dramatiq.actor(queue_name="apply", max_retries=0, time_limit=600_000)
def run_plan(deployment_id: str) -> None:
    """Load the immutable snapshot, assume the user role, and run Plan."""
    deployment_uuid = UUID(deployment_id)
    try:
        with SessionLocal() as db:
            deployment = db.get(Deployment, deployment_uuid)
            if deployment is None:
                logger.error("plan deployment not found: %s", deployment_id)
                return
            if deployment.status != "queued":
                logger.info(
                    "plan deployment skipped: id=%s status=%s",
                    deployment_id,
                    deployment.status,
                )
                return

            require_direct_execution(db.get(Canvas, deployment.canvas_id))

            version = db.get(CanvasVersion, deployment.canvas_version_id)
            if version is None:
                raise RuntimeError("캔버스 버전 스냅샷을 찾을 수 없음")

            deployment.status = "planning"
            deployment.started_at = datetime.now(timezone.utc)
            _append_progress_event(
                deployment,
                step="worker",
                label="Plan worker 시작",
                status="running",
            )
            db.commit()

            aws_account = dict(deployment.aws_account_snapshot)
            canvas_data = {
                "graph": version.graph,
                "aws_account": aws_account,
            }
            canvas_id = str(deployment.canvas_id)

            is_destroy_plan = deployment.mode == "destroy"

            _record_progress_event(
                deployment_uuid,
                step="assume-role",
                label="AWS Role Assume",
                status="running",
            )
        process_env, assumed_arn = assume_role_environment(
            aws_account,
            session_name=f"eolgae-plan-{deployment_uuid}",
        )
        _record_progress_event(
            deployment_uuid,
            step="assume-role",
            label="AWS Role Assume",
            status="success",
            message=assumed_arn,
        )
        _record_progress_event(
            deployment_uuid,
            step="state-backend",
            label="State backend 준비",
            status="running",
        )
        result, apply_readiness_note = _generate_apply_ready_or_preview_plan(
            canvas_id=canvas_id,
            deployment_id=str(deployment_uuid),
            aws_account=aws_account,
            canvas_data=canvas_data,
            process_env=process_env,
            progress_callback=_progress_callback(deployment_uuid),
            destroy=is_destroy_plan,
        )
        _record_progress_event(
            deployment_uuid,
            step="worker",
            label="Plan worker",
            status="success",
        )
        _record_progress_event(
            deployment_uuid,
            step="deployment",
            label="Plan 완료",
            status="success" if result.ok else "failed",
            message=result.error,
        )
        serialized = serialize_plan_result(result)
        serialized["work_dir"] = ""
        serialized["plan_artifact"] = _artifact_summary(result.plan_artifact)
        serialized["apply_ready"] = bool(result.plan_artifact and result.state_backend)
        if apply_readiness_note:
            serialized["apply_readiness_note"] = apply_readiness_note

        with SessionLocal() as db:
            deployment = db.get(Deployment, deployment_uuid)
            if deployment is None:
                return
            deployment.plan_result = serialized
            deployment.plan_artifact = result.plan_artifact
            deployment.state_backend = result.state_backend
            deployment.assumed_arn = assumed_arn
            deployment.status = "success" if result.ok else "failed"
            deployment.error_message = result.error
            deployment.finished_at = datetime.now(timezone.utc)
            db.add(
                AuditLog(
                    actor_id=None,
                    action="deployment.complete",
                    entity_type="deployment",
                    entity_id=deployment.id,
                    after={
                        "status": deployment.status,
                        "assumed_arn": assumed_arn,
                    },
                )
            )
            db.commit()
    except Exception as exc:
        logger.exception("plan deployment failed: %s", deployment_id)
        _finish_failed(deployment_uuid, str(exc))


@dramatiq.actor(queue_name="apply", max_retries=0, time_limit=900_000)
def run_apply(deployment_id: str) -> None:
    """Apply a previously approved immutable Plan artifact."""
    deployment_uuid = UUID(deployment_id)
    try:
        with SessionLocal() as db:
            deployment = db.get(Deployment, deployment_uuid)
            if deployment is None:
                logger.error("apply deployment not found: %s", deployment_id)
                return
            if deployment.mode != "apply" or deployment.status != "queued":
                logger.info(
                    "apply deployment skipped: id=%s mode=%s status=%s",
                    deployment_id,
                    deployment.mode,
                    deployment.status,
                )
                return
            require_direct_execution(db.get(Canvas, deployment.canvas_id))

            if not deployment.source_plan_deployment_id:
                raise RuntimeError("Apply source Plan이 없음")

            source_plan = db.get(Deployment, deployment.source_plan_deployment_id)
            if source_plan is None:
                raise RuntimeError("승인된 Plan deployment를 찾을 수 없음")
            if source_plan.status != "approved":
                raise RuntimeError("승인된 Plan만 Apply할 수 있음")
            if not source_plan.plan_artifact or not source_plan.state_backend:
                raise RuntimeError("승인된 Plan artifact 또는 state backend가 없음")

            deployment.status = "applying"
            deployment.started_at = datetime.now(timezone.utc)
            _append_progress_event(
                deployment,
                step="worker",
                label="Apply worker 시작",
                status="running",
            )
            db.commit()

            aws_account = dict(deployment.aws_account_snapshot)
            plan_artifact = dict(source_plan.plan_artifact)
            state_backend = dict(source_plan.state_backend)

        _record_progress_event(
            deployment_uuid,
            step="assume-role",
            label="AWS Role Assume",
            status="running",
        )
        process_env, assumed_arn = assume_role_environment(
            aws_account,
            session_name=f"eolgae-apply-{deployment_uuid}",
        )
        _record_progress_event(
            deployment_uuid,
            step="assume-role",
            label="AWS Role Assume",
            status="success",
            message=assumed_arn,
        )
        result = apply_approved_plan(
            plan_artifact=plan_artifact,
            state_backend=state_backend,
            process_env=process_env,
            progress_callback=_progress_callback(deployment_uuid),
        )
        _record_progress_event(
            deployment_uuid,
            step="worker",
            label="Apply worker",
            status="success",
        )
        _record_progress_event(
            deployment_uuid,
            step="deployment",
            label="Apply 완료",
            status="success" if result.ok else "failed",
            message=result.error,
        )
        serialized = serialize_plan_result(result)
        serialized["work_dir"] = ""
        serialized["plan_artifact"] = _artifact_summary(plan_artifact)

        with SessionLocal() as db:
            deployment = db.get(Deployment, deployment_uuid)
            if deployment is None:
                return
            deployment.plan_result = serialized
            deployment.plan_artifact = plan_artifact
            deployment.state_backend = state_backend
            deployment.assumed_arn = assumed_arn
            deployment.status = "applied" if result.ok else "failed"
            deployment.error_message = result.error
            deployment.finished_at = datetime.now(timezone.utc)
            canvas = db.get(Canvas, deployment.canvas_id)
            if canvas is not None and result.ok:
                canvas.state = "applied"
                canvas.graph = _apply_resource_bindings_to_graph(
                    canvas.graph,
                    result.resource_bindings or [],
                )
            db.add(
                AuditLog(
                    actor_id=None,
                    action="deployment.complete",
                    entity_type="deployment",
                    entity_id=deployment.id,
                    after={
                        "status": deployment.status,
                        "assumed_arn": assumed_arn,
                        "source_plan_deployment_id": str(
                            deployment.source_plan_deployment_id
                        ),
                        "canvas_state": canvas.state if canvas is not None else None,
                        "resource_bindings": len(result.resource_bindings or []),
                    },
                )
            )
            db.commit()
    except Exception as exc:
        logger.exception("apply deployment failed: %s", deployment_id)
        _finish_failed(deployment_uuid, str(exc))


@dramatiq.actor(queue_name="apply", max_retries=0, time_limit=900_000)
def run_destroy(deployment_id: str) -> None:
    """Apply a previously approved destroy Plan artifact."""
    deployment_uuid = UUID(deployment_id)
    try:
        with SessionLocal() as db:
            deployment = db.get(Deployment, deployment_uuid)
            if deployment is None:
                logger.error("destroy deployment not found: %s", deployment_id)
                return
            if deployment.mode != "destroy" or deployment.status != "queued":
                logger.info(
                    "destroy deployment skipped: id=%s mode=%s status=%s",
                    deployment_id,
                    deployment.mode,
                    deployment.status,
                )
                return
            require_direct_execution(db.get(Canvas, deployment.canvas_id))

            if not deployment.source_plan_deployment_id:
                raise RuntimeError("Destroy source Plan이 없음")

            source_plan = db.get(Deployment, deployment.source_plan_deployment_id)
            if source_plan is None:
                raise RuntimeError("승인된 Destroy Plan deployment를 찾을 수 없음")
            if source_plan.mode != "destroy" or source_plan.status != "approved":
                raise RuntimeError("승인된 Destroy Plan만 실행할 수 있음")
            if not source_plan.plan_artifact or not source_plan.state_backend:
                raise RuntimeError("승인된 Destroy Plan artifact 또는 state backend가 없음")

            deployment.status = "destroying"
            deployment.started_at = datetime.now(timezone.utc)
            _append_progress_event(
                deployment,
                step="worker",
                label="Destroy worker 시작",
                status="running",
            )
            db.commit()

            aws_account = dict(deployment.aws_account_snapshot)
            plan_artifact = dict(source_plan.plan_artifact)
            state_backend = dict(source_plan.state_backend)

        _record_progress_event(
            deployment_uuid,
            step="assume-role",
            label="AWS Role Assume",
            status="running",
        )
        process_env, assumed_arn = assume_role_environment(
            aws_account,
            session_name=f"eolgae-destroy-{deployment_uuid}",
        )
        _record_progress_event(
            deployment_uuid,
            step="assume-role",
            label="AWS Role Assume",
            status="success",
            message=assumed_arn,
        )
        result = apply_approved_plan(
            plan_artifact=plan_artifact,
            state_backend=state_backend,
            process_env=process_env,
            progress_callback=_progress_callback(deployment_uuid),
        )
        _record_progress_event(
            deployment_uuid,
            step="worker",
            label="Destroy worker",
            status="success",
        )
        _record_progress_event(
            deployment_uuid,
            step="deployment",
            label="Destroy 완료",
            status="success" if result.ok else "failed",
            message=result.error,
        )
        serialized = serialize_plan_result(result)
        serialized["work_dir"] = ""
        serialized["plan_artifact"] = _artifact_summary(plan_artifact)

        with SessionLocal() as db:
            deployment = db.get(Deployment, deployment_uuid)
            if deployment is None:
                return
            deployment.plan_result = serialized
            deployment.plan_artifact = plan_artifact
            deployment.state_backend = state_backend
            deployment.assumed_arn = assumed_arn
            deployment.status = "destroyed" if result.ok else "failed"
            deployment.error_message = result.error
            deployment.finished_at = datetime.now(timezone.utc)
            canvas = db.get(Canvas, deployment.canvas_id)
            if canvas is not None and result.ok:
                canvas.state = "destroyed"
                canvas.graph = _clear_resource_bindings(canvas.graph)
            db.add(
                AuditLog(
                    actor_id=None,
                    action="deployment.complete",
                    entity_type="deployment",
                    entity_id=deployment.id,
                    after={
                        "status": deployment.status,
                        "assumed_arn": assumed_arn,
                        "source_plan_deployment_id": str(
                            deployment.source_plan_deployment_id
                        ),
                        "canvas_state": canvas.state if canvas is not None else None,
                    },
                )
            )
            db.commit()
    except Exception as exc:
        logger.exception("destroy deployment failed: %s", deployment_id)
        _finish_failed(deployment_uuid, str(exc))


def _artifact_summary(artifact: dict | None) -> dict | None:
    if not artifact:
        return None
    summary = {
        key: artifact.get(key)
        for key in ("format", "filename", "sha256", "size_bytes")
        if key in artifact
    }
    storage = artifact.get("storage")
    if isinstance(storage, dict):
        summary["storage"] = {
            key: storage.get(key)
            for key in ("backend", "retention_policy")
            if key in storage
        }
    return summary


def _apply_resource_bindings_to_graph(
    graph: dict[str, Any],
    bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attach OpenTofu state identifiers to matching canvas nodes."""
    binding_by_key = {
        (binding.get("resource_type"), binding.get("resource_name")): binding
        for binding in bindings
        if binding.get("resource_type") and binding.get("resource_name")
    }
    next_graph = dict(graph or {})
    next_nodes = []
    bound_at = datetime.now(timezone.utc).isoformat()
    for node in next_graph.get("nodes") or []:
        next_node = dict(node)
        node_type = next_node.get("type")
        node_id = next_node.get("id")
        resource_type = NODE_TF_RESOURCE.get(node_type)
        binding = binding_by_key.get((resource_type, normalize_name(str(node_id or ""))))
        if binding:
            next_node["aws_binding"] = {
                "provider": binding.get("provider", "aws"),
                "resource_address": binding.get("resource_address"),
                "resource_type": binding.get("resource_type"),
                "id": binding.get("id"),
                "arn": binding.get("arn"),
                "display_name": binding.get("display_name"),
                "status": "bound",
                "bound_at": bound_at,
            }
        next_nodes.append(next_node)
    next_graph["nodes"] = next_nodes
    return next_graph


def _clear_resource_bindings(graph: dict[str, Any]) -> dict[str, Any]:
    """Remove live AWS bindings after a successful destroy."""
    next_graph = dict(graph or {})
    next_nodes = []
    for node in next_graph.get("nodes") or []:
        next_node = dict(node)
        next_node.pop("aws_binding", None)
        next_nodes.append(next_node)
    next_graph["nodes"] = next_nodes
    return next_graph


def _generate_apply_ready_or_preview_plan(
    *,
    canvas_id: str,
    deployment_id: str,
    aws_account: dict,
    canvas_data: dict,
    process_env: dict[str, str],
    progress_callback,
    destroy: bool = False,
):
    """Run an Apply-ready remote-state Plan or fall back to read-only preview."""
    state_backend = build_state_backend(canvas_id, aws_account)
    try:
        ensure_state_backend_resources(state_backend, process_env=process_env)
        progress_callback(
            "state-backend",
            "State backend 준비",
            "success",
            state_backend.get("bucket"),
        )
    except Exception as exc:
        if not _is_backend_bootstrap_permission_error(exc):
            progress_callback(
                "state-backend",
                "State backend 준비",
                "failed",
                str(exc),
            )
            raise
        progress_callback(
            "state-backend",
            "State backend 준비",
            "warning",
            "권한 부족으로 read-only preview Plan으로 전환",
        )
        logger.warning(
            "state backend bootstrap denied; running local preview plan: canvas_id=%s",
            canvas_id,
        )
        return (
            generate_plan(
                canvas_data,
                process_env=process_env,
                state_backend=None,
                include_plan_artifact=False,
                destroy=destroy,
                progress_callback=progress_callback,
            ),
            LOCAL_PLAN_APPLY_READINESS_NOTE,
        )

    return (
        generate_plan(
            canvas_data,
            process_env=process_env,
            state_backend=state_backend,
            include_plan_artifact=True,
            destroy=destroy,
            progress_callback=progress_callback,
            artifact_context=deployment_artifact_prefix(
                canvas_id=canvas_id,
                deployment_id=deployment_id,
            ),
        ),
        None,
    )


def _is_backend_bootstrap_permission_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    error = response.get("Error", {}) if isinstance(response, dict) else {}
    code = str(error.get("Code") or "")
    message = str(error.get("Message") or exc)
    haystack = f"{code} {message}".lower()
    return any(
        marker in haystack
        for marker in (
            "accessdenied",
            "access denied",
            "not authorized",
            "unauthorized",
            "explicit deny",
            "is not authorized",
        )
    )
