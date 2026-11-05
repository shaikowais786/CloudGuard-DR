from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Recommendation, Report, Scan, ScanHistory, ScanResource, User
from app.services.account_service import get_owned_workspace
from app.services.scoring import readiness


def latest_scan(db: Session, workspace_id: UUID) -> Scan:
    scan = db.scalar(select(Scan).where(
        Scan.workspace_id == workspace_id, Scan.status.in_(["completed", "partial"]),
    ).order_by(Scan.completed_at.desc()).limit(1))
    if scan is None:
        raise HTTPException(status_code=404, detail="No completed scan was found for this workspace")
    return scan


def resource_dict(row: ScanResource) -> dict:
    return {
        "id": row.resource_id,
        "resource_id": row.resource_id,
        "name": row.name,
        "type": row.resource_type,
        "resource_type": row.resource_type,
        "service": row.service,
        "region": row.region,
        "health": row.health,
        "risk": row.risk,
        "status": row.status,
        "updated": row.last_updated.isoformat(),
        "last_updated": row.last_updated.isoformat(),
        "details": row.details,
        "metadata": row.metadata_json,
    }


def list_resources(
    db: Session, user: User, workspace_id: UUID, service: str | None, region: str | None,
    status: str | None, risk: str | None, search: str | None, page: int, page_size: int,
) -> dict:
    workspace = get_owned_workspace(db, user, workspace_id)
    scan = latest_scan(db, workspace.id)
    conditions = [ScanResource.scan_id == scan.id]
    for column, value in ((ScanResource.service, service), (ScanResource.region, region),
                          (ScanResource.status, status), (ScanResource.risk, risk)):
        if value:
            conditions.append(column.ilike(value.strip()))
    if search:
        term = f"%{search.strip()}%"
        conditions.append(or_(ScanResource.name.ilike(term), ScanResource.resource_id.ilike(term),
                              ScanResource.resource_type.ilike(term), ScanResource.service.ilike(term)))
    total = db.scalar(select(func.count(ScanResource.id)).where(*conditions)) or 0
    rows = list(db.scalars(select(ScanResource).where(*conditions)
                           .order_by(ScanResource.service, ScanResource.name)
                           .offset((page - 1) * page_size).limit(page_size)).all())
    return {"scan_id": str(scan.id), "total": total, "page": page, "page_size": page_size,
            "items": [resource_dict(row) for row in rows]}


def get_readiness(db: Session, user: User, workspace_id: UUID) -> dict:
    workspace = get_owned_workspace(db, user, workspace_id)
    scan = latest_scan(db, workspace.id)
    rows = list(db.scalars(select(ScanResource).where(ScanResource.scan_id == scan.id)).all())
    result = readiness([{
        "service": row.service, "resource_type": row.resource_type, "status": row.status,
        "metadata": row.metadata_json,
    } for row in rows])
    return {"scan_id": str(scan.id), **result}


def get_recommendations(
    db: Session, user: User, workspace_id: UUID, status: str | None, page: int, page_size: int,
) -> dict:
    workspace = get_owned_workspace(db, user, workspace_id)
    scan = latest_scan(db, workspace.id)
    conditions = [Recommendation.scan_id == scan.id]
    if status:
        conditions.append(Recommendation.status.ilike(status.strip()))
    total = db.scalar(select(func.count(Recommendation.id)).where(*conditions)) or 0
    rows = list(db.scalars(select(Recommendation).where(*conditions)
                           .order_by(Recommendation.priority, Recommendation.created_at.desc())
                           .offset((page - 1) * page_size).limit(page_size)).all())
    items = [{
        "id": str(row.id), "key": row.recommendation_key, "title": row.title,
        "priority": row.priority, "affected_service": row.affected_service,
        "estimated_score_improvement": row.estimated_score_improvement,
        "description": row.description, "status": row.status, "resource_ids": row.resource_ids,
        "created_at": row.created_at.isoformat(),
    } for row in rows]
    return {"scan_id": str(scan.id), "total": total, "page": page, "page_size": page_size, "items": items}


def generate_report(db: Session, user: User, workspace_id: UUID) -> dict:
    workspace = get_owned_workspace(db, user, workspace_id)
    scan = latest_scan(db, workspace.id)
    resource_rows = list(db.scalars(select(ScanResource).where(ScanResource.scan_id == scan.id)
                                    .order_by(ScanResource.service, ScanResource.name)).all())
    recommendation_rows = list(db.scalars(select(Recommendation).where(Recommendation.scan_id == scan.id)
                                          .order_by(Recommendation.priority)).all())
    inventory = [resource_dict(row) for row in resource_rows]
    score = readiness([{
        "service": row.service, "resource_type": row.resource_type, "status": row.status,
        "metadata": row.metadata_json,
    } for row in resource_rows])
    findings = [item for item in inventory if item["risk"] in {"High", "Medium"}]
    recommendation_data = [{
        "id": str(row.id), "title": row.title, "priority": row.priority,
        "affected_service": row.affected_service, "estimated_score_improvement": row.estimated_score_improvement,
        "description": row.description, "status": row.status,
    } for row in recommendation_rows]
    content = {
        "scan_id": str(scan.id), "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_score": score["overall_score"], "risk_indicator": score["risk_indicator"],
        "pillars": score["pillars"], "resources": inventory, "risks": findings,
        "recommendations": recommendation_data,
    }
    report = Report(scan_id=scan.id, title="Disaster Recovery Assessment", content=content)
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": str(report.id), "title": report.title, "generated_at": report.generated_at.isoformat(), **content}


def list_history(db: Session, user: User, workspace_id: UUID, page: int, page_size: int) -> dict:
    workspace = get_owned_workspace(db, user, workspace_id)
    total = db.scalar(select(func.count(ScanHistory.id)).where(ScanHistory.workspace_id == workspace.id)) or 0
    rows = list(db.scalars(select(ScanHistory).where(ScanHistory.workspace_id == workspace.id)
                           .order_by(ScanHistory.scan_time.desc())
                           .offset((page - 1) * page_size).limit(page_size)).all())
    items = [{
        "scan_id": str(row.scan_id), "scan_time": row.scan_time.isoformat(), "score": row.score,
        "resources_scanned": row.resources_scanned, "findings": row.findings, "trend": row.trend,
    } for row in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}

