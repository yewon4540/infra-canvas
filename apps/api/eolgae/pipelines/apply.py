"""OpenTofu Plan/Apply execution for asynchronous deployment workers.

비동기 경로는 Dramatiq worker가 verified cross-account Role을 AssumeRole한 뒤
temporary credentials를 `generate_plan`의 process environment로 전달한다.
Plan은 사용자 AWS 계정의 S3 backend를 사용하고, 승인 후 Apply가 같은 plan
artifact를 재사용할 수 있도록 binary tfplan을 DB metadata에 보존한다.

실행 경계와 데이터 흐름: `docs/ARCHITECTURE.md`
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from eolgae.pipelines.artifacts import ArtifactStore, get_artifact_store
from eolgae.pipelines.state_backend import (
    backend_config_args,
    build_state_backend,
    ensure_state_backend_resources,
    write_backend_tf,
)
from eolgae.pipelines.tofu_generator import generate_tofu
from eolgae.pipelines.validation import validate_canvas_for_plan

logger = logging.getLogger(__name__)

# tofu CLI 호출 타임아웃 — 큰 캔버스 대비
TOFU_TIMEOUT_SEC = 120
ProgressCallback = Callable[[str, str, str, str | None], None]


@dataclass
class StepResult:
    """tofu 명령 1건 결과."""

    step: str
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float


@dataclass
class PlanResult:
    """`generate_plan` 의 전체 결과."""

    ok: bool
    error: str | None
    steps: list[StepResult]
    work_dir: str  # 디버깅용. 실 사용 시엔 cleanup 됨
    plan_text: str | None  # tofu plan stdout (사용자 표시용)
    validation_issues: list[dict[str, Any]] | None = None
    plan_artifact: dict[str, Any] | None = None
    state_backend: dict[str, Any] | None = None
    resource_bindings: list[dict[str, Any]] | None = None


def generate_plan(
    canvas_data: dict[str, Any],
    *,
    process_env: dict[str, str] | None = None,
    state_backend: dict[str, Any] | None = None,
    include_plan_artifact: bool = False,
    destroy: bool = False,
    progress_callback: ProgressCallback | None = None,
    artifact_store: ArtifactStore | None = None,
    artifact_context: dict[str, str] | None = None,
) -> PlanResult:
    """캔버스 → .tf → `tofu init` + `tofu plan` 실행.

    Args:
        canvas_data: `{aws_account: ..., graph: {nodes, edges, groups}}` 형태.
            `routers/canvas.py` 의 generate-tofu endpoint 와 동일 입력.

    Returns:
        `PlanResult`. ok=False 시 error 필드에 사유, steps 에 부분 실행 결과.

    한계:
    - process_env 미지정 시 호스트 default AWS credentials 로 호출
    - local state — 다회 호출 시 state 누적 안 됨 (매번 새 work_dir)
    - apply 미실행
    """
    if not _tofu_available():
        return PlanResult(
            ok=False,
            error=(
                "tofu CLI 가 시스템에 없습니다. "
                "OpenTofu 설치 후 다시 시도: https://opentofu.org/docs/intro/install/"
            ),
            steps=[],
            work_dir="",
            plan_text=None,
        )

    _emit_progress(progress_callback, "validate", "캔버스 검증", "running")
    validation_issues = validate_canvas_for_plan(canvas_data)
    if validation_issues:
        _emit_progress(
            progress_callback,
            "validate",
            "캔버스 검증",
            "failed",
            "Plan 전 수정이 필요한 항목이 있음",
        )
        issue_lines = [
            f"{issue.get('display_name')}: {issue.get('message')}"
            for issue in validation_issues
        ]
        return PlanResult(
            ok=False,
            error="Plan 전 필수 입력 확인 필요",
            steps=[
                StepResult(
                    step="canvas validation",
                    exit_code=1,
                    stdout="",
                    stderr="\n".join(issue_lines),
                    duration_sec=0,
                )
            ],
            work_dir="",
            plan_text="\n".join(
                f"- {issue.get('display_name')}: {issue.get('suggested_action') or issue.get('message')}"
                for issue in validation_issues
            ),
            validation_issues=validation_issues,
        )
    _emit_progress(progress_callback, "validate", "캔버스 검증", "success")

    _emit_progress(progress_callback, "generate-hcl", "OpenTofu HCL 생성", "running")
    tf_source = generate_tofu(canvas_data)
    _emit_progress(progress_callback, "generate-hcl", "OpenTofu HCL 생성", "success")

    work_dir = tempfile.mkdtemp(prefix="eolgae-plan-")
    logger.info("apply.plan: work_dir=%s", work_dir)
    steps: list[StepResult] = []

    try:
        main_tf = Path(work_dir) / "main.tf"
        main_tf.write_text(tf_source, encoding="utf-8")
        if state_backend:
            write_backend_tf(work_dir)

        init_args = ["init", "-input=false"]
        if state_backend:
            init_args.extend(backend_config_args(state_backend))
        else:
            init_args.insert(1, "-backend=false")
        _emit_progress(progress_callback, "tofu-init", "tofu init", "running")
        init = _run_tofu(work_dir, init_args, process_env=process_env)
        steps.append(init)
        if init.exit_code != 0:
            _emit_progress(
                progress_callback,
                "tofu-init",
                "tofu init",
                "failed",
                "provider/backend 초기화 실패",
            )
            return PlanResult(
                ok=False,
                error="tofu init 실패",
                steps=steps,
                work_dir=work_dir,
                plan_text=None,
            )
        _emit_progress(progress_callback, "tofu-init", "tofu init", "success")

        _emit_progress(progress_callback, "tofu-plan", "tofu plan", "running")
        plan_args = ["plan", "-input=false", "-no-color", "-out=tfplan"]
        if destroy:
            plan_args.insert(1, "-destroy")
        plan = _run_tofu(
            work_dir,
            plan_args,
            process_env=process_env,
        )
        steps.append(plan)
        if plan.exit_code != 0:
            _emit_progress(
                progress_callback,
                "tofu-plan",
                "tofu plan",
                "failed",
                "OpenTofu Plan 실패",
            )
            return PlanResult(
                ok=False,
                error="tofu plan 실패",
                steps=steps,
                work_dir=work_dir,
                plan_text=plan.stdout,
            )
        _emit_progress(progress_callback, "tofu-plan", "tofu plan", "success")

        plan_artifact = None
        if include_plan_artifact:
            _emit_progress(
                progress_callback,
                "plan-artifact",
                "Plan artifact 저장",
                "running",
            )
            plan_artifact = _read_plan_artifact(
                work_dir=work_dir,
                tf_source=tf_source,
                plan_filename="tfplan",
                artifact_store=artifact_store,
                artifact_context=artifact_context,
            )
            _emit_progress(
                progress_callback,
                "plan-artifact",
                "Plan artifact 저장",
                "success",
                f"{plan_artifact['size_bytes']} bytes",
            )

        return PlanResult(
            ok=True,
            error=None,
            steps=steps,
            work_dir=work_dir,
            plan_text=plan.stdout,
            plan_artifact=plan_artifact,
            state_backend=state_backend,
        )
    finally:
        # PoC: 작업 끝나면 work_dir 즉시 cleanup. state 보존 안 함
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except OSError:
            logger.exception("apply.plan: work_dir cleanup 실패 %s", work_dir)


def apply_approved_plan(
    *,
    plan_artifact: dict[str, Any],
    state_backend: dict[str, Any],
    process_env: dict[str, str] | None = None,
    progress_callback: ProgressCallback | None = None,
    artifact_store: ArtifactStore | None = None,
) -> PlanResult:
    """Run `tofu apply` using a previously approved plan artifact."""
    if not _tofu_available():
        return PlanResult(
            ok=False,
            error=(
                "tofu CLI 가 시스템에 없습니다. "
                "OpenTofu 설치 후 다시 시도: https://opentofu.org/docs/intro/install/"
            ),
            steps=[],
            work_dir="",
            plan_text=None,
            state_backend=state_backend,
        )

    _emit_progress(progress_callback, "verify-artifact", "Plan artifact 검증", "running")
    try:
        tf_source, plan_bytes = _load_plan_artifact_payload(
            plan_artifact,
            artifact_store=artifact_store,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        _emit_progress(
            progress_callback,
            "verify-artifact",
            "Plan artifact 검증",
            "failed",
            str(e),
        )
        return PlanResult(
            ok=False,
            error=f"승인된 Plan artifact 로드 실패: {e}",
            steps=[],
            work_dir="",
            plan_text=None,
            plan_artifact=plan_artifact,
            state_backend=state_backend,
        )
    expected_sha = plan_artifact.get("sha256")
    plan_filename = plan_artifact.get("filename") or "tfplan"
    if not tf_source or not plan_bytes or not expected_sha:
        _emit_progress(
            progress_callback,
            "verify-artifact",
            "Plan artifact 검증",
            "failed",
            "artifact metadata 불완전",
        )
        return PlanResult(
            ok=False,
            error="승인된 Plan artifact가 불완전함",
            steps=[],
            work_dir="",
            plan_text=None,
            plan_artifact=plan_artifact,
            state_backend=state_backend,
        )

    work_dir = tempfile.mkdtemp(prefix="eolgae-apply-")
    steps: list[StepResult] = []
    try:
        Path(work_dir, "main.tf").write_text(tf_source, encoding="utf-8")
        write_backend_tf(work_dir)
        actual_sha = hashlib.sha256(plan_bytes).hexdigest()
        if actual_sha != expected_sha:
            _emit_progress(
                progress_callback,
                "verify-artifact",
                "Plan artifact 검증",
                "failed",
                "checksum 불일치",
            )
            return PlanResult(
                ok=False,
                error="승인된 Plan artifact checksum 불일치",
                steps=[],
                work_dir=work_dir,
                plan_text=None,
                plan_artifact=plan_artifact,
                state_backend=state_backend,
            )
        Path(work_dir, plan_filename).write_bytes(plan_bytes)
        _emit_progress(progress_callback, "verify-artifact", "Plan artifact 검증", "success")

        _emit_progress(progress_callback, "tofu-init", "tofu init", "running")
        init = _run_tofu(
            work_dir,
            ["init", "-input=false", *backend_config_args(state_backend)],
            process_env=process_env,
        )
        steps.append(init)
        if init.exit_code != 0:
            _emit_progress(
                progress_callback,
                "tofu-init",
                "tofu init",
                "failed",
                "remote state backend 초기화 실패",
            )
            return PlanResult(
                ok=False,
                error="tofu init 실패",
                steps=steps,
                work_dir=work_dir,
                plan_text=None,
                plan_artifact=plan_artifact,
                state_backend=state_backend,
            )
        _emit_progress(progress_callback, "tofu-init", "tofu init", "success")

        _emit_progress(progress_callback, "tofu-apply", "tofu apply", "running")
        apply = _run_tofu(
            work_dir,
            ["apply", "-input=false", "-no-color", plan_filename],
            process_env=process_env,
        )
        steps.append(apply)
        _emit_progress(
            progress_callback,
            "tofu-apply",
            "tofu apply",
            "success" if apply.exit_code == 0 else "failed",
            None if apply.exit_code == 0 else "OpenTofu Apply 실패",
        )
        resource_bindings = None
        if apply.exit_code == 0:
            _emit_progress(
                progress_callback,
                "resource-binding",
                "Resource binding 추출",
                "running",
            )
            show = _run_tofu(
                work_dir,
                ["show", "-json"],
                process_env=process_env,
            )
            steps.append(show)
            if show.exit_code == 0:
                resource_bindings = extract_resource_bindings_from_state(show.stdout)
                _emit_progress(
                    progress_callback,
                    "resource-binding",
                    "Resource binding 추출",
                    "success",
                    f"{len(resource_bindings)} resources",
                )
            else:
                _emit_progress(
                    progress_callback,
                    "resource-binding",
                    "Resource binding 추출",
                    "warning",
                    "OpenTofu state 조회 실패",
                )
        return PlanResult(
            ok=apply.exit_code == 0,
            error=None if apply.exit_code == 0 else "tofu apply 실패",
            steps=steps,
            work_dir=work_dir,
            plan_text=apply.stdout,
            plan_artifact=plan_artifact,
            state_backend=state_backend,
            resource_bindings=resource_bindings,
        )
    finally:
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except OSError:
            logger.exception("apply.run: work_dir cleanup 실패 %s", work_dir)



def _tofu_available() -> bool:
    return shutil.which("tofu") is not None


def _emit_progress(
    callback: ProgressCallback | None,
    step: str,
    label: str,
    status: str,
    message: str | None = None,
) -> None:
    if callback is not None:
        callback(step, label, status, message)


def _read_plan_artifact(
    *,
    work_dir: str,
    tf_source: str,
    plan_filename: str,
    artifact_store: ArtifactStore | None = None,
    artifact_context: dict[str, str] | None = None,
) -> dict[str, Any]:
    plan_bytes = Path(work_dir, plan_filename).read_bytes()
    artifact: dict[str, Any] = {
        "format": "opentofu-plan-v1",
        "filename": plan_filename,
        "sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "size_bytes": len(plan_bytes),
    }
    if artifact_context:
        store = artifact_store or get_artifact_store()
        main_tf = store.put_bytes(
            **artifact_context,
            kind="main_tf",
            filename="main.tf",
            data=tf_source.encode("utf-8"),
            content_type="text/plain; charset=utf-8",
        )
        tfplan = store.put_bytes(
            **artifact_context,
            kind="tfplan",
            filename=plan_filename,
            data=plan_bytes,
            content_type="application/octet-stream",
        )
        artifact["storage"] = {
            "backend": tfplan.backend,
            "retention_policy": tfplan.retention_policy,
            "artifacts": {
                "main_tf": main_tf.to_metadata(),
                "tfplan": tfplan.to_metadata(),
            },
        }
    else:
        artifact["tfplan_b64"] = base64.b64encode(plan_bytes).decode("ascii")
        artifact["main_tf"] = tf_source
    return artifact


def _load_plan_artifact_payload(
    plan_artifact: dict[str, Any],
    *,
    artifact_store: ArtifactStore | None = None,
) -> tuple[str | None, bytes | None]:
    storage = plan_artifact.get("storage")
    if isinstance(storage, dict):
        artifacts = storage.get("artifacts")
        if not isinstance(artifacts, dict):
            raise ValueError("artifact storage metadata 불완전")
        main_tf_meta = artifacts.get("main_tf")
        tfplan_meta = artifacts.get("tfplan")
        if not isinstance(main_tf_meta, dict) or not isinstance(tfplan_meta, dict):
            raise ValueError("artifact storage metadata 불완전")
        store = artifact_store or get_artifact_store()
        tf_source = store.get_bytes(main_tf_meta).decode("utf-8")
        plan_bytes = store.get_bytes(tfplan_meta)
        return tf_source, plan_bytes

    plan_b64 = plan_artifact.get("tfplan_b64")
    tf_source = plan_artifact.get("main_tf")
    if not isinstance(plan_b64, str):
        return tf_source, None
    return tf_source, base64.b64decode(plan_b64)



def assume_role_environment(
    aws_account: dict[str, Any],
    *,
    sts_client: Any | None = None,
    session_name: str = "eolgae-plan",
) -> tuple[dict[str, str], str]:
    """Assume the verified canvas role and return an in-memory process env."""
    role_arn = aws_account.get("role_arn")
    external_id = aws_account.get("external_id")
    region = aws_account.get("default_region") or "ap-northeast-2"
    if aws_account.get("binding_status") != "verified":
        raise RuntimeError("AWS 계정 연결이 verified 상태가 아님")
    if not role_arn or not external_id:
        raise RuntimeError("Role ARN 과 External ID 가 필요")

    if sts_client is None:
        import boto3

        sts_client = boto3.client("sts", region_name=region)

    assumed = sts_client.assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name[:64],
        ExternalId=external_id,
        DurationSeconds=3600,
    )
    credentials = assumed["Credentials"]
    assumed_arn = assumed.get("AssumedRoleUser", {}).get("Arn") or role_arn
    return (
        {
            "AWS_ACCESS_KEY_ID": credentials["AccessKeyId"],
            "AWS_SECRET_ACCESS_KEY": credentials["SecretAccessKey"],
            "AWS_SESSION_TOKEN": credentials["SessionToken"],
            "AWS_REGION": region,
            "AWS_DEFAULT_REGION": region,
        },
        assumed_arn,
    )


def _run_tofu(
    work_dir: str,
    args: list[str],
    *,
    process_env: dict[str, str] | None = None,
) -> StepResult:
    """`tofu <args>` 호출. capture stdout/stderr."""
    t0 = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603 — args 는 코드 내부 통제
            ["tofu", *args],
            cwd=work_dir,
            capture_output=True,
            text=True,
            env={**os.environ, **(process_env or {})},
            timeout=TOFU_TIMEOUT_SEC,
            check=False,
        )
        duration = time.monotonic() - t0
        return StepResult(
            step=" ".join(["tofu", *args]),
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_sec=round(duration, 2),
        )
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - t0
        return StepResult(
            step=" ".join(["tofu", *args]),
            exit_code=-1,
            stdout="",
            stderr=f"timeout after {TOFU_TIMEOUT_SEC}s",
            duration_sec=round(duration, 2),
        )
    except OSError as e:
        duration = time.monotonic() - t0
        return StepResult(
            step=" ".join(["tofu", *args]),
            exit_code=-1,
            stdout="",
            stderr=f"OS error: {e}",
            duration_sec=round(duration, 2),
        )


def extract_resource_bindings_from_state(state_json: str) -> list[dict[str, Any]]:
    """Extract minimal resource identifiers from `tofu show -json` state output.

    The full OpenTofu state can contain sensitive values. This keeps only
    provider/resource address, type/name, id, arn, and a display name candidate.
    """
    try:
        parsed = json.loads(state_json)
    except json.JSONDecodeError:
        return []

    values = parsed.get("values") if isinstance(parsed, dict) else None
    root = values.get("root_module") if isinstance(values, dict) else None
    if not isinstance(root, dict):
        return []

    bindings: list[dict[str, Any]] = []
    for resource in _iter_state_resources(root):
        address = resource.get("address")
        resource_type = resource.get("type")
        resource_name = resource.get("name")
        values = resource.get("values")
        if not address or not resource_type or not resource_name or not isinstance(values, dict):
            continue
        resource_id = values.get("id")
        if not resource_id:
            continue
        binding: dict[str, Any] = {
            "provider": "aws",
            "resource_address": address,
            "resource_type": resource_type,
            "resource_name": resource_name,
            "id": resource_id,
        }
        arn = values.get("arn")
        if arn:
            binding["arn"] = arn
        display_name = (
            values.get("bucket")
            or values.get("name")
            or values.get("arn")
            or resource_id
        )
        if display_name:
            binding["display_name"] = display_name
        bindings.append(binding)
    return bindings


def _iter_state_resources(module: dict[str, Any]):
    resources = module.get("resources") or []
    for resource in resources:
        if isinstance(resource, dict):
            yield resource
    for child in module.get("child_modules") or []:
        if isinstance(child, dict):
            yield from _iter_state_resources(child)


def serialize_plan_result(result: PlanResult) -> dict[str, Any]:
    """`PlanResult` 를 JSON-friendly dict 로. router 응답용."""
    return asdict(result)
