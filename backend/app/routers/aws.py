from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.session import get_db
from app.models import Report, User
from app.schemas.aws import AWSConnectRequest, ScanStartRequest
from app.schemas.common import APIResponse
from app.services.account_service import connect_aws_account
from app.services.aws_queries import (
    generate_report,
    get_readiness,
    get_recommendations,
    list_history,
    list_resources,
)
from app.services.aws_scanner import start_scan
from app.services.pdf_report import build_report_pdf, upload_report_pdf

router = APIRouter(prefix="/aws", tags=["aws"])


@router.post("/connect", response_model=APIResponse[dict])
def connect_account(
    payload: AWSConnectRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = connect_aws_account(db, user, payload)
    return {"success": True, "message": "AWS account connected", "data": data}


@router.post("/scan", response_model=APIResponse[dict])
def scan_account(
    payload: ScanStartRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = start_scan(db, user, payload)
    message = "Scan completed" if data["status"] == "completed" else "Scan completed with warnings"
    return {"success": True, "message": message, "data": data}


@router.get("/resources", response_model=APIResponse[dict])
def resources(
    workspace_id: UUID,
    service: str | None = Query(default=None, max_length=64),
    region: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None, max_length=64),
    risk: str | None = Query(default=None, max_length=16),
    search: str | None = Query(default=None, max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = list_resources(db, user, workspace_id, service, region, status, risk, search, page, page_size)
    return {"success": True, "message": "Resource inventory", "data": data}


@router.get("/readiness", response_model=APIResponse[dict])
def readiness_score(
    workspace_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = get_readiness(db, user, workspace_id)
    return {"success": True, "message": "Disaster recovery readiness", "data": data}


@router.get("/recommendations", response_model=APIResponse[dict])
def recommendations(
    workspace_id: UUID,
    status: str | None = Query(default=None, max_length=24),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = get_recommendations(db, user, workspace_id, status, page, page_size)
    return {"success": True, "message": "Recommendations", "data": data}


@router.get("/report", response_model=APIResponse[dict])
def report(
    workspace_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = generate_report(db, user, workspace_id)
    pdf = build_report_pdf(data)
    stored = upload_report_pdf(pdf, str(workspace_id), data["id"])
    report_record = db.get(Report, UUID(data["id"]))
    if report_record:
        report_content = dict(report_record.content or {})
        report_content["pdf_s3_key"] = stored["key"]
        report_record.content = report_content
        db.commit()
    return {
        "success": True,
        "message": "PDF report generated and stored",
        "data": {
            "id": data["id"],
            "title": data["title"],
            "generated_at": data["generated_at"],
            "scan_id": data["scan_id"],
            "overall_score": data["overall_score"],
            "risk_indicator": data["risk_indicator"],
            "resources_count": len(data["resources"]),
            "recommendations_count": len(data["recommendations"]),
            **stored,
        },
    }


@router.get("/history", response_model=APIResponse[dict])
def history(
    workspace_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = list_history(db, user, workspace_id, page, page_size)
    return {"success": True, "message": "Scan history", "data": data}

