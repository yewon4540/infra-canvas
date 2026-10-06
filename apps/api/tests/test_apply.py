from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret")

from eolgae.pipelines.artifacts import LocalArtifactStore, S3ArtifactStore
from eolgae.pipelines import apply


class GeneratePlanTests(unittest.TestCase):
    def test_reports_missing_tofu(self) -> None:
        with patch.object(apply, "_tofu_available", return_value=False):
            result = apply.generate_plan({"graph": {"nodes": [], "edges": []}})

        self.assertFalse(result.ok)
        self.assertEqual(result.steps, [])
        self.assertIn("tofu CLI", result.error or "")

    def test_runs_init_and_plan_then_cleans_up(self) -> None:
        calls: list[tuple[str, list[str]]] = []
        events: list[tuple[str, str, str, str | None]] = []

        def fake_run(
            path: str,
            args: list[str],
            *,
            process_env: dict[str, str] | None = None,
        ) -> apply.StepResult:
            calls.append((path, args))
            return apply.StepResult(
                step="tofu " + " ".join(args),
                exit_code=0,
                stdout="plan ok" if args[0] == "plan" else "init ok",
                stderr="",
                duration_sec=0.01,
            )

        with (
            patch.object(apply, "_tofu_available", return_value=True),
            patch.object(apply, "_run_tofu", side_effect=fake_run),
        ):
            result = apply.generate_plan({"graph": {"nodes": [], "edges": []}})

        self.assertTrue(result.ok)
        self.assertEqual(result.plan_text, "plan ok")
        self.assertEqual(
            [args for _, args in calls],
            [
                ["init", "-backend=false", "-input=false"],
                ["plan", "-input=false", "-no-color", "-out=tfplan"],
            ],
        )
        self.assertTrue(all(not Path(path).exists() for path, _ in calls))

        with (
            patch.object(apply, "_tofu_available", return_value=True),
            patch.object(apply, "_run_tofu", side_effect=fake_run),
        ):
            apply.generate_plan(
                {"graph": {"nodes": [], "edges": []}},
                progress_callback=lambda step, label, status, message: events.append(
                    (step, label, status, message)
                ),
            )

        self.assertIn(("validate", "캔버스 검증", "running", None), events)
        self.assertIn(("tofu-init", "tofu init", "success", None), events)
        self.assertIn(("tofu-plan", "tofu plan", "success", None), events)

    def test_plan_can_store_backend_and_artifact(self) -> None:
        calls: list[list[str]] = []
        backend = apply.build_state_backend(
            "canvas-1",
            {
                "account_id": "123456789012",
                "default_region": "ap-northeast-2",
            },
        )

        def fake_run(
            path: str,
            args: list[str],
            *,
            process_env: dict[str, str] | None = None,
        ) -> apply.StepResult:
            calls.append(args)
            if args[0] == "plan":
                Path(path, "tfplan").write_bytes(b"approved-plan")
            return apply.StepResult(
                step="tofu " + " ".join(args),
                exit_code=0,
                stdout="plan ok",
                stderr="",
                duration_sec=0.01,
            )

        with (
            patch.object(apply, "_tofu_available", return_value=True),
            patch.object(apply, "_run_tofu", side_effect=fake_run),
        ):
            result = apply.generate_plan(
                {"graph": {"nodes": [], "edges": []}},
                state_backend=backend,
                include_plan_artifact=True,
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.state_backend, backend)
        self.assertEqual(result.plan_artifact["size_bytes"], len(b"approved-plan"))
        self.assertEqual(result.plan_artifact["filename"], "tfplan")
        self.assertIn(
            "-backend-config=bucket=eolgae-state-123456789012-ap-northeast-2",
            calls[0],
        )
        self.assertEqual(calls[1], ["plan", "-input=false", "-no-color", "-out=tfplan"])

    def test_plan_can_store_artifacts_in_local_store(self) -> None:
        calls: list[list[str]] = []

        def fake_run(
            path: str,
            args: list[str],
            *,
            process_env: dict[str, str] | None = None,
        ) -> apply.StepResult:
            calls.append(args)
            if args[0] == "plan":
                Path(path, "tfplan").write_bytes(b"stored-plan")
            return apply.StepResult(
                step="tofu " + " ".join(args),
                exit_code=0,
                stdout="plan ok",
                stderr="",
                duration_sec=0.01,
            )

        with tempfile.TemporaryDirectory() as artifact_root:
            store = LocalArtifactStore(root=artifact_root, retention_policy="keep")
            with (
                patch.object(apply, "_tofu_available", return_value=True),
                patch.object(apply, "_run_tofu", side_effect=fake_run),
            ):
                result = apply.generate_plan(
                    {"graph": {"nodes": [], "edges": []}},
                    include_plan_artifact=True,
                    artifact_store=store,
                    artifact_context={
                        "canvas_id": "canvas-1",
                        "deployment_id": "deployment-1",
                    },
                )

            self.assertTrue(result.ok)
            artifact = result.plan_artifact
            self.assertNotIn("tfplan_b64", artifact)
            self.assertNotIn("main_tf", artifact)
            self.assertEqual(artifact["storage"]["backend"], "local")
            self.assertEqual(
                store.get_bytes(artifact["storage"]["artifacts"]["tfplan"]),
                b"stored-plan",
            )
            self.assertIn(
                'provider "aws"',
                store.get_bytes(
                    artifact["storage"]["artifacts"]["main_tf"]
                ).decode("utf-8"),
            )

    def test_destroy_plan_uses_destroy_flag(self) -> None:
        calls: list[list[str]] = []

        def fake_run(
            path: str,
            args: list[str],
            *,
            process_env: dict[str, str] | None = None,
        ) -> apply.StepResult:
            calls.append(args)
            if args[0] == "plan":
                Path(path, "tfplan").write_bytes(b"destroy-plan")
            return apply.StepResult(
                step="tofu " + " ".join(args),
                exit_code=0,
                stdout="destroy plan ok",
                stderr="",
                duration_sec=0.01,
            )

        with (
            patch.object(apply, "_tofu_available", return_value=True),
            patch.object(apply, "_run_tofu", side_effect=fake_run),
        ):
            result = apply.generate_plan(
                {"graph": {"nodes": [], "edges": []}},
                include_plan_artifact=True,
                destroy=True,
            )

        self.assertTrue(result.ok)
        self.assertEqual(
            calls[1],
            ["plan", "-destroy", "-input=false", "-no-color", "-out=tfplan"],
        )

    def test_stops_after_init_failure(self) -> None:
        run = Mock(
            return_value=apply.StepResult(
                step="tofu init",
                exit_code=1,
                stdout="",
                stderr="provider download failed",
                duration_sec=0.01,
            )
        )

        with (
            patch.object(apply, "_tofu_available", return_value=True),
            patch.object(apply, "_run_tofu", run),
        ):
            result = apply.generate_plan({"graph": {"nodes": [], "edges": []}})

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "tofu init 실패")
        self.assertEqual(len(result.steps), 1)
        run.assert_called_once()

    def test_generated_main_tf_is_written_before_init(self) -> None:
        captured_tf = ""

        def fake_run(
            path: str,
            args: list[str],
            *,
            process_env: dict[str, str] | None = None,
        ) -> apply.StepResult:
            nonlocal captured_tf
            captured_tf = (Path(path) / "main.tf").read_text(encoding="utf-8")
            return apply.StepResult(
                step="tofu " + " ".join(args),
                exit_code=0,
                stdout="ok",
                stderr="",
                duration_sec=0.01,
            )

        with (
            patch.object(apply, "_tofu_available", return_value=True),
            patch.object(apply, "_run_tofu", side_effect=fake_run),
        ):
            result = apply.generate_plan({"graph": {"nodes": [], "edges": []}})

        self.assertTrue(result.ok)
        self.assertIn('provider "aws"', captured_tf)


class RunTofuTests(unittest.TestCase):
    def test_captures_process_result(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["tofu", "version"],
            returncode=0,
            stdout="OpenTofu v1.12.1\n",
            stderr="",
        )
        run = Mock(return_value=completed)

        with tempfile.TemporaryDirectory() as work_dir:
            with patch.object(apply.subprocess, "run", run):
                result = apply._run_tofu(work_dir, ["version"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "OpenTofu v1.12.1\n")
        args, kwargs = run.call_args
        self.assertEqual(args, (["tofu", "version"],))
        self.assertEqual(kwargs["cwd"], work_dir)
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])
        self.assertEqual(kwargs["timeout"], apply.TOFU_TIMEOUT_SEC)
        self.assertFalse(kwargs["check"])
        self.assertIn("PATH", kwargs["env"])

    def test_merges_cross_account_environment(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["tofu", "version"],
            returncode=0,
            stdout="ok",
            stderr="",
        )
        run = Mock(return_value=completed)
        assumed_env = {
            "AWS_ACCESS_KEY_ID": "temporary-key",
            "AWS_SECRET_ACCESS_KEY": "temporary-secret",
            "AWS_SESSION_TOKEN": "temporary-token",
        }

        with tempfile.TemporaryDirectory() as work_dir:
            with patch.object(apply.subprocess, "run", run):
                apply._run_tofu(
                    work_dir,
                    ["version"],
                    process_env=assumed_env,
                )

        env = run.call_args.kwargs["env"]
        self.assertEqual(env["AWS_ACCESS_KEY_ID"], "temporary-key")
        self.assertIn("PATH", env)


class ApplyApprovedPlanTests(unittest.TestCase):
    def test_applies_saved_plan_artifact(self) -> None:
        calls: list[list[str]] = []
        plan_bytes = b"approved-plan"
        artifact = {
            "filename": "tfplan",
            "sha256": (
                "f217982f42c6598eed7d95fde1e7020"
                "dea7c2e0d07165dc4a94dc7a26f9ba3f5"
            ),
            "size_bytes": len(plan_bytes),
            "tfplan_b64": "YXBwcm92ZWQtcGxhbg==",
            "main_tf": 'provider "aws" {}',
        }
        backend = {
            "type": "s3",
            "bucket": "eolgae-state-123456789012-ap-northeast-2",
            "key": "canvases/canvas-1/terraform.tfstate",
            "region": "ap-northeast-2",
            "dynamodb_table": "eolgae-tofu-locks",
            "encrypt": True,
        }

        def fake_run(
            path: str,
            args: list[str],
            *,
            process_env: dict[str, str] | None = None,
        ) -> apply.StepResult:
            calls.append(args)
            self.assertEqual(Path(path, "tfplan").read_bytes(), plan_bytes)
            stdout = "apply ok"
            if args[:2] == ["show", "-json"]:
                stdout = """
                {
                  "values": {
                    "root_module": {
                      "resources": [
                        {
                          "address": "aws_s3_bucket.node_s3",
                          "type": "aws_s3_bucket",
                          "name": "node_s3",
                          "values": {
                            "id": "test-bucket",
                            "arn": "arn:aws:s3:::test-bucket",
                            "bucket": "test-bucket"
                          }
                        },
                        {
                          "address": "aws_s3_bucket_public_access_block.node_s3_pab",
                          "type": "aws_s3_bucket_public_access_block",
                          "name": "node_s3_pab",
                          "values": {
                            "id": "test-bucket"
                          }
                        }
                      ]
                    }
                  }
                }
                """
            return apply.StepResult(
                step="tofu " + " ".join(args),
                exit_code=0,
                stdout=stdout,
                stderr="",
                duration_sec=0.01,
            )

        with (
            patch.object(apply, "_tofu_available", return_value=True),
            patch.object(apply, "_run_tofu", side_effect=fake_run),
        ):
            result = apply.apply_approved_plan(
                plan_artifact=artifact,
                state_backend=backend,
            )

        self.assertTrue(result.ok)
        self.assertEqual(calls[1], ["apply", "-input=false", "-no-color", "tfplan"])
        self.assertEqual(calls[2], ["show", "-json"])
        self.assertEqual(
            result.resource_bindings,
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
                    "display_name": "test-bucket",
                },
            ],
        )

    def test_applies_plan_artifact_from_local_store(self) -> None:
        calls: list[list[str]] = []
        backend = {
            "type": "s3",
            "bucket": "eolgae-state-123456789012-ap-northeast-2",
            "key": "canvases/canvas-1/terraform.tfstate",
            "region": "ap-northeast-2",
            "dynamodb_table": "eolgae-tofu-locks",
            "encrypt": True,
        }

        def fake_run(
            path: str,
            args: list[str],
            *,
            process_env: dict[str, str] | None = None,
        ) -> apply.StepResult:
            calls.append(args)
            self.assertEqual(Path(path, "tfplan").read_bytes(), b"stored-plan")
            return apply.StepResult(
                step="tofu " + " ".join(args),
                exit_code=0,
                stdout='{"values":{"root_module":{"resources":[]}}}'
                if args[:2] == ["show", "-json"]
                else "ok",
                stderr="",
                duration_sec=0.01,
            )

        with tempfile.TemporaryDirectory() as artifact_root:
            store = LocalArtifactStore(root=artifact_root, retention_policy="keep")
            Path(artifact_root, "tfplan").write_bytes(b"stored-plan")
            artifact = apply._read_plan_artifact(
                work_dir=artifact_root,
                tf_source='provider "aws" {}',
                plan_filename="tfplan",
                artifact_store=store,
                artifact_context={
                    "canvas_id": "canvas-1",
                    "deployment_id": "deployment-1",
                },
            )

            with (
                patch.object(apply, "_tofu_available", return_value=True),
                patch.object(apply, "_run_tofu", side_effect=fake_run),
            ):
                result = apply.apply_approved_plan(
                    plan_artifact=artifact,
                    state_backend=backend,
                    artifact_store=store,
                )

        self.assertTrue(result.ok)
        self.assertEqual(calls[1], ["apply", "-input=false", "-no-color", "tfplan"])

    def test_extract_resource_bindings_ignores_invalid_state_json(self) -> None:
        self.assertEqual(apply.extract_resource_bindings_from_state("not json"), [])


class ArtifactStoreTests(unittest.TestCase):
    def test_s3_store_writes_and_reads_artifact_bytes(self) -> None:
        client = Mock()
        stored: dict[tuple[str, str], bytes] = {}

        def put_object(**kwargs):
            stored[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]

        def get_object(**kwargs):
            return {
                "Body": BytesIO(stored[(kwargs["Bucket"], kwargs["Key"])]),
            }

        client.put_object.side_effect = put_object
        client.get_object.side_effect = get_object
        store = S3ArtifactStore(
            bucket="eolgae-artifacts",
            prefix="artifact-root",
            region="ap-northeast-2",
            endpoint_url="http://seaweedfs:8333",
            force_path_style=True,
            retention_policy="keep",
            client=client,
        )

        artifact = store.put_bytes(
            canvas_id="canvas-1",
            deployment_id="deployment-1",
            kind="tfplan",
            filename="tfplan",
            data=b"stored-plan",
        )

        self.assertEqual(
            artifact.storage_uri,
            "s3://eolgae-artifacts/artifact-root/canvases/canvas-1/deployments/deployment-1/tfplan",
        )
        self.assertEqual(store.get_bytes(artifact.to_metadata()), b"stored-plan")
        client.put_object.assert_called_once()
        put_kwargs = client.put_object.call_args.kwargs
        self.assertEqual(put_kwargs["Bucket"], "eolgae-artifacts")
        self.assertEqual(
            put_kwargs["Key"],
            "artifact-root/canvases/canvas-1/deployments/deployment-1/tfplan",
        )
        self.assertEqual(put_kwargs["Metadata"]["kind"], "tfplan")
        self.assertEqual(put_kwargs["Metadata"]["retention-policy"], "keep")

    def test_s3_store_rejects_checksum_mismatch(self) -> None:
        client = Mock()
        client.get_object.return_value = {"Body": BytesIO(b"changed")}
        store = S3ArtifactStore(
            bucket="eolgae-artifacts",
            prefix="artifact-root",
            region="ap-northeast-2",
            client=client,
        )

        metadata = {
            "storage_uri": "s3://eolgae-artifacts/artifact-root/tfplan",
            "sha256": "bad-sha",
        }
        with self.assertRaisesRegex(ValueError, "checksum"):
            store.get_bytes(metadata)


class AssumeRoleTests(unittest.TestCase):
    def test_creates_regional_sts_client(self) -> None:
        sts = Mock()
        sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "key",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
            }
        }
        boto3 = Mock()
        boto3.client.return_value = sts

        with patch.dict(sys.modules, {"boto3": boto3}):
            apply.assume_role_environment(
                {
                    "binding_status": "verified",
                    "role_arn": "arn:aws:iam::123456789012:role/Eolgae",
                    "external_id": "external",
                    "default_region": "ap-northeast-2",
                }
            )

        boto3.client.assert_called_once_with(
            "sts",
            region_name="ap-northeast-2",
        )

    def test_returns_temporary_process_environment(self) -> None:
        sts = Mock()
        sts.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "key",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
            },
            "AssumedRoleUser": {
                "Arn": "arn:aws:sts::123456789012:assumed-role/Eolgae/plan"
            },
        }

        env, arn = apply.assume_role_environment(
            {
                "binding_status": "verified",
                "role_arn": "arn:aws:iam::123456789012:role/Eolgae",
                "external_id": "external",
                "default_region": "ap-northeast-2",
            },
            sts_client=sts,
            session_name="test-plan",
        )

        self.assertEqual(env["AWS_ACCESS_KEY_ID"], "key")
        self.assertEqual(env["AWS_REGION"], "ap-northeast-2")
        self.assertEqual(
            arn,
            "arn:aws:sts::123456789012:assumed-role/Eolgae/plan",
        )
        sts.assume_role.assert_called_once_with(
            RoleArn="arn:aws:iam::123456789012:role/Eolgae",
            RoleSessionName="test-plan",
            ExternalId="external",
            DurationSeconds=3600,
        )

    def test_rejects_unverified_binding(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "verified"):
            apply.assume_role_environment(
                {
                    "binding_status": "role_saved",
                    "role_arn": "arn:aws:iam::123456789012:role/Eolgae",
                    "external_id": "external",
                },
                sts_client=Mock(),
            )


if __name__ == "__main__":
    unittest.main()
