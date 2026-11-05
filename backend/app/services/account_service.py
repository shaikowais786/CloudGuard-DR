import re
from typing import Any
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import encrypt_credential
from app.models import AWSAccount, User, Workspace
from app.schemas.aws import AWSConnectRequest

REGION_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+-\d$")


def validate_region(region: str) -> str:
    normalized = region.strip().lower()
    if not REGION_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=422, detail="Invalid AWS region")
    session = boto3.Session(region_name=normalized)
    partition = session.get_partition_for_region(normalized)
    if normalized not in session.get_available_regions("ec2", partition_name=partition):
        raise HTTPException(status_code=422, detail="Invalid AWS region")
    return normalized


def get_owned_workspace(db: Session, user: User, workspace_id: UUID) -> Workspace:
    workspace = db.scalar(select(Workspace).where(
        Workspace.id == workspace_id, Workspace.owner_user_id == user.id,
    ))
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def connect_aws_account(db: Session, user: User, payload: AWSConnectRequest) -> dict[str, Any]:
    workspace = get_owned_workspace(db, user, payload.workspace_id)
    region = validate_region(payload.region)

    try:
        session = boto3.Session(
            aws_access_key_id=payload.access_key,
            aws_secret_access_key=payload.secret_key,
            region_name=region,
        )
        sts = session.client("sts", region_name=region, config=Config(
            connect_timeout=settings.aws_connect_timeout_seconds,
            read_timeout=settings.aws_read_timeout_seconds,
            retries={"max_attempts": 2, "mode": "standard"},
        ))
        identity = sts.get_caller_identity()
    except NoCredentialsError as exc:
        raise HTTPException(status_code=401, detail="AWS credentials were not accepted") from exc
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"InvalidClientTokenId", "SignatureDoesNotMatch", "ExpiredToken", "UnrecognizedClientException"}:
            raise HTTPException(status_code=401, detail="AWS credentials are invalid or expired") from exc
        if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
            raise HTTPException(status_code=403, detail="AWS denied the identity validation request") from exc
        raise HTTPException(status_code=502, detail="AWS could not validate the account connection") from exc
    except BotoCoreError as exc:
        raise HTTPException(status_code=502, detail="AWS connection failed; verify the region and network") from exc

    account = AWSAccount(
        workspace_id=workspace.id,
        account_name=payload.account_name.strip(),
        account_id=identity["Account"],
        user_arn=identity["Arn"],
        region=region,
        access_key_ciphertext=encrypt_credential(payload.access_key),
        secret_key_ciphertext=encrypt_credential(payload.secret_key),
        connection_status="connected",
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return {
        "account_id": account.account_id,
        "user_arn": account.user_arn,
        "connection_status": account.connection_status,
        "aws_account_id": str(account.id),
        "account_name": account.account_name,
        "region": account.region,
    }

