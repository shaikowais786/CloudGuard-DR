"""Run the live, read-only AWS inventory collectors using credentials from .env."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.services.aws import EC2Service, IAMService, RDSService, S3Service


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE entries without printing or overriding shell values."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    load_env_file(Path(__file__).resolve().parent / ".env")
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    session_token = os.getenv("AWS_SESSION_TOKEN")
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

    if not access_key or not secret_key:
        print("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in backend/.env or the environment.", file=sys.stderr)
        return 2

    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
        region_name=region,
    )
    try:
        identity = session.client("sts").get_caller_identity()
        output = {
            "identity": {"account": identity.get("Account"), "arn": identity.get("Arn")},
            "region": region,
            "collectors": {
                "EC2": EC2Service(session, region).scan(),
                "S3": S3Service(session, region).scan(),
                "IAM": IAMService(session, region).scan(),
                "RDS": RDSService(session, region).scan(),
            },
        }
        print(json.dumps(output, indent=2, default=str))
        return 0
    except (BotoCoreError, ClientError) as exc:
        print(f"AWS scanner failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
