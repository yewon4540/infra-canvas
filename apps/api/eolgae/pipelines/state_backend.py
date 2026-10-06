"""OpenTofu remote state backend bootstrap helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def build_state_backend(canvas_id: str, aws_account: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic S3 backend metadata for a canvas."""
    region = aws_account.get("default_region") or "ap-northeast-2"
    account_id = aws_account.get("account_id") or _account_id_from_role(
        aws_account.get("role_arn") or ""
    )
    if not account_id:
        raise RuntimeError("state backend 생성을 위해 AWS account_id가 필요")
    return {
        "type": "s3",
        "bucket": f"eolgae-state-{account_id}-{region}".lower(),
        "key": f"canvases/{canvas_id}/terraform.tfstate",
        "region": region,
        "dynamodb_table": "eolgae-tofu-locks",
        "encrypt": True,
    }


def ensure_state_backend_resources(
    backend: dict[str, Any],
    *,
    process_env: dict[str, str],
) -> None:
    """Create the S3 bucket and DynamoDB lock table if they are missing."""
    if backend.get("type") != "s3":
        raise RuntimeError("지원하지 않는 state backend")

    import boto3
    from botocore.exceptions import ClientError

    region = backend["region"]
    session = boto3.session.Session(
        aws_access_key_id=process_env.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=process_env.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=process_env.get("AWS_SESSION_TOKEN"),
        region_name=region,
    )
    s3 = session.client("s3", region_name=region)
    dynamodb = session.client("dynamodb", region_name=region)

    bucket = backend["bucket"]
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        create_args: dict[str, Any] = {"Bucket": bucket}
        if region != "us-east-1":
            create_args["CreateBucketConfiguration"] = {
                "LocationConstraint": region,
            }
        s3.create_bucket(**create_args)
        s3.put_bucket_versioning(
            Bucket=bucket,
            VersioningConfiguration={"Status": "Enabled"},
        )
        s3.put_bucket_encryption(
            Bucket=bucket,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256",
                        },
                    }
                ],
            },
        )

    table = backend["dynamodb_table"]
    try:
        dynamodb.describe_table(TableName=table)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code != "ResourceNotFoundException":
            raise
        dynamodb.create_table(
            TableName=table,
            AttributeDefinitions=[{"AttributeName": "LockID", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "LockID", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        waiter = dynamodb.get_waiter("table_exists")
        waiter.wait(TableName=table)


def write_backend_tf(work_dir: str) -> None:
    Path(work_dir, "backend.tf").write_text(
        'terraform {\n  backend "s3" {}\n}\n',
        encoding="utf-8",
    )


def backend_config_args(backend: dict[str, Any]) -> list[str]:
    return [
        f"-backend-config=bucket={backend['bucket']}",
        f"-backend-config=key={backend['key']}",
        f"-backend-config=region={backend['region']}",
        f"-backend-config=dynamodb_table={backend['dynamodb_table']}",
        f"-backend-config=encrypt={str(backend.get('encrypt', True)).lower()}",
    ]


def _account_id_from_role(role_arn: str) -> str:
    parts = role_arn.split(":")
    if len(parts) >= 5 and parts[2] == "iam":
        return parts[4]
    return ""
