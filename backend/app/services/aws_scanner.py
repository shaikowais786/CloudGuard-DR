from datetime import datetime, timezone
from typing import Any
from uuid import UUID
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decrypt_credential
from app.models import AWSAccount, Recommendation, Scan, ScanHistory, ScanResource, User
from app.schemas.aws import ScanStartRequest
from app.services.account_service import get_owned_workspace, validate_region
from app.services.aws import (
    AvailabilityZonesService,
    CloudWatchService,
    EC2Service,
    EBSService,
    IAMService,
    LambdaService,
    RDSService,
    RegionsService,
    S3Service,
    SecurityGroupsService,
    VPCService,
)
from app.services.recommendations import analyze_resources
from app.services.scoring import readiness

COLLECTORS = (
    EC2Service,
    RDSService,
    S3Service,
    IAMService,
    CloudWatchService,
    SecurityGroupsService,
    VPCService,
    LambdaService,
    EBSService,
    AvailabilityZonesService,
    RegionsService,
)


def _previous_score(db: Session, workspace_id: UUID) -> int | None:
    previous = db.scalar(select(Scan.overall_score).where(
        Scan.workspace_id == workspace_id, Scan.status.in_(["completed", "partial"]),
    ).order_by(Scan.completed_at.desc()).limit(1))
    return previous


def start_scan(db: Session, user: User, payload: ScanStartRequest) -> dict[str, Any]:
    workspace = get_owned_workspace(db, user, payload.workspace_id)
    account_query = select(AWSAccount).where(
        AWSAccount.workspace_id == workspace.id, AWSAccount.connection_status == "connected",
    )
    if payload.account_id:
        account_query = account_query.where(AWSAccount.id == payload.account_id)
    accounts = list(db.scalars(account_query.order_by(AWSAccount.connected_at.desc())).all())
    if not accounts:
        raise HTTPException(status_code=404, detail="No connected AWS accounts were found for this workspace")
    accounts_with_regions = [(account, validate_region(payload.region or account.region)) for account in accounts]

    before_score = _previous_score(db, workspace.id)
    scan = Scan(workspace_id=workspace.id, aws_account_id=accounts_with_regions[0][0].id if len(accounts) == 1 else None, status="running")
    db.add(scan)
    db.commit()

    collected: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    for account, region in accounts_with_regions:
        try:
            access_key = decrypt_credential(account.access_key_ciphertext)
            secret_key = decrypt_credential(account.secret_key_ciphertext)
        except RuntimeError as exc:
            scan.status = "failed"
            scan.completed_at = datetime.now(timezone.utc)
            db.commit()
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        for collector_type in COLLECTORS:
            collector = collector_type(session, region)
            try:
                rows = collector.scan()
                for row in rows:
                    row["aws_account_id"] = account.id
                collected.extend(rows)
            except ClientError as exc:
                error = exc.response.get("Error", {})
                code = str(error.get("Code", "AWSServiceError"))
                warnings.append({"service": collector.service_name, "code": code,
                                 "message": "AWS permissions or service availability prevented this collector from completing."})
            except (BotoCoreError, ValueError, KeyError, TypeError) as exc:
                # Exception text may contain request details; only expose the exception class.
                warnings.append({"service": collector.service_name, "code": type(exc).__name__,
                                 "message": "AWS service could not be reached for this collector."})

    if not collected:
        scan.status = "failed"
        scan.completed_at = datetime.now(timezone.utc)
        db.commit()
        if warnings and all("AccessDenied" in item["code"] or "Unauthorized" in item["code"] for item in warnings):
            status = 403
        elif warnings and all(any(token in item["code"] for token in ("InvalidClientTokenId", "SignatureDoesNotMatch", "ExpiredToken", "RequestExpired")) for item in warnings):
            status = 401
        elif warnings and all(any(token in item["code"] for token in ("InvalidRegion", "InvalidEndpoint", "EndpointConnectionError")) for item in warnings):
            status = 422
        else:
            status = 502
        raise HTTPException(status_code=status, detail="The scan did not return any AWS resources; check account permissions and region")

    result = readiness(collected)
    recommendations = analyze_resources(collected, {item["service"] for item in warnings})
    scan.status = "partial" if warnings else "completed"
    scan.overall_score = result["overall_score"]
    scan.resource_count = len(collected)
    scan.finding_count = sum(1 for row in collected if row["risk"] in {"High", "Medium"})
    scan.completed_at = datetime.now(timezone.utc)
    scan.trend = result["overall_score"] - before_score if before_score is not None else 0

    for row in collected:
        metadata = row.get("metadata", {})
        db.add(ScanResource(
            scan_id=scan.id,
            aws_account_id=row.get("aws_account_id"),
            resource_id=row["resource_id"],
            name=row["name"],
            resource_type=row["resource_type"],
            service=row["service"],
            region=row["region"],
            status=row["status"],
            health=row["health"],
            risk=row["risk"],
            last_updated=row["last_updated"],
            details=row["details"],
            metadata_json=metadata,
        ))
    for recommendation in recommendations:
        db.add(Recommendation(scan_id=scan.id, **recommendation))
    db.add(ScanHistory(
        scan_id=scan.id,
        workspace_id=workspace.id,
        scan_time=scan.completed_at,
        score=scan.overall_score,
        resources_scanned=scan.resource_count,
        findings=scan.finding_count,
        trend=scan.trend or 0,
    ))
    db.commit()
    db.refresh(scan)
    return {
        "scan_id": str(scan.id),
        "status": scan.status,
        "scan_time": scan.completed_at,
        "resources_scanned": scan.resource_count,
        "findings": scan.finding_count,
        "overall_score": scan.overall_score,
        "trend": scan.trend,
        "readiness": result,
        "recommendations_generated": len(recommendations),
        "warnings": warnings,
    }

