from __future__ import annotations

from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import boto3
from boto3.s3.transfer import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from app.core.config import settings


NAVY = colors.HexColor("#172033")
BLUE = colors.HexColor("#536DFE")
PALE_BLUE = colors.HexColor("#EEF1FF")
PALE = colors.HexColor("#F4F6FA")
INK = colors.HexColor("#283247")
MUTED = colors.HexColor("#687386")
GREEN = colors.HexColor("#19845B")
AMBER = colors.HexColor("#A65A0A")
RED = colors.HexColor("#B42332")


def _paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(value if value is not None else "-")), style)


def _footer(canvas: Any, document: Any) -> None:
    canvas.saveState()
    width, _ = letter
    canvas.setStrokeColor(colors.HexColor("#E3E7EF"))
    canvas.line(0.65 * inch, 0.5 * inch, width - 0.65 * inch, 0.5 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.65 * inch, 0.32 * inch, "CloudGuard DR | Confidential")
    canvas.drawRightString(width - 0.65 * inch, 0.32 * inch, f"Page {document.page}")
    canvas.restoreState()


def build_report_pdf(report: dict[str, Any]) -> BytesIO:
    """Render a report payload into an in-memory, multi-page PDF."""
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.72 * inch,
        title=str(report.get("title") or "Disaster Recovery Assessment"),
        author="CloudGuard DR",
    )

    base = getSampleStyleSheet()
    title = ParagraphStyle("CGTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=23,
                           leading=28, alignment=TA_LEFT, textColor=NAVY, spaceAfter=7)
    subtitle = ParagraphStyle("CGSubtitle", parent=base["Normal"], fontSize=9, leading=13,
                              textColor=MUTED, spaceAfter=16)
    section = ParagraphStyle("CGSection", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13,
                             leading=17, textColor=NAVY, spaceBefore=15, spaceAfter=7, keepWithNext=True)
    body = ParagraphStyle("CGBody", parent=base["BodyText"], fontSize=8.5, leading=12, textColor=INK)
    small = ParagraphStyle("CGSmall", parent=body, fontSize=7.5, leading=10)
    table_header = ParagraphStyle("CGTableHeader", parent=small, fontName="Helvetica-Bold", textColor=colors.white)
    centered = ParagraphStyle("CGCentered", parent=body, alignment=TA_CENTER)

    resources = report.get("resources") or []
    recommendations = report.get("recommendations") or []
    score = int(report.get("overall_score") or 0)
    risk = str(report.get("risk_indicator") or "Unknown")
    risks = {level: sum(1 for resource in resources if resource.get("risk") == level)
             for level in ("Low", "Medium", "High")}
    by_service: dict[str, list[dict[str, Any]]] = {}
    for resource in resources:
        by_service.setdefault(str(resource.get("service") or "Other"), []).append(resource)

    story = [
        Paragraph("Disaster Recovery Assessment", title),
        Paragraph(
            f"Generated {escape(str(report.get('generated_at') or ''))}"
            f" &nbsp;&nbsp;|&nbsp;&nbsp; Scan {escape(str(report.get('scan_id') or ''))}",
            subtitle,
        ),
    ]

    score_tone = GREEN if score >= 85 else AMBER if score >= 65 else RED
    score_block = Table([
        [Paragraph("OVERALL DR READINESS", ParagraphStyle("CGLabel", parent=small, textColor=MUTED,
                                                            fontName="Helvetica-Bold")),
         Paragraph("RISK INDICATOR", ParagraphStyle("CGLabel2", parent=small, textColor=MUTED,
                                                       fontName="Helvetica-Bold"))],
        [Paragraph(f'<font color="{score_tone.hexval()}"><b>{score}</b></font> <font size="11">/ 100</font>',
                   ParagraphStyle("CGScore", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=26,
                                  leading=31, textColor=NAVY)),
         Paragraph(f'<font color="{score_tone.hexval()}"><b>{escape(risk)}</b></font>',
                   ParagraphStyle("CGRisk", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=17,
                                  leading=22, textColor=NAVY))],
    ], colWidths=[3.35 * inch, 3.35 * inch])
    score_block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#DCE2FF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 13),
        ("RIGHTPADDING", (0, 0), (-1, -1), 13),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LINEBEFORE", (1, 0), (1, -1), 0.6, colors.HexColor("#DCE2FF")),
    ]))
    story.extend([score_block, Paragraph("Resource Summary", section)])

    summary_rows = [[_paragraph("AWS SERVICE", table_header), _paragraph("RESOURCES", table_header),
                     _paragraph("HEALTHY", table_header), _paragraph("HIGH RISK", table_header)]]
    for service, entries in sorted(by_service.items()):
        summary_rows.append([
            _paragraph(service, body),
            _paragraph(len(entries), centered),
            _paragraph(sum(1 for item in entries if int(item.get("health") or 0) >= 85), centered),
            _paragraph(sum(1 for item in entries if item.get("risk") == "High"), centered),
        ])
    summary_rows.append([_paragraph("Total", body), _paragraph(len(resources), centered),
                         _paragraph(sum(1 for item in resources if int(item.get("health") or 0) >= 85), centered),
                         _paragraph(risks["High"], centered)])
    summary = LongTable(summary_rows, colWidths=[3.25 * inch, 1.05 * inch, 1.1 * inch, 1.3 * inch], repeatRows=1)
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), PALE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, NAVY),
        ("LINEBELOW", (0, 1), (-1, -2), 0.35, colors.HexColor("#E3E7EF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([summary, Paragraph("Risk Analysis", section)])

    risk_rows = [[_paragraph("RISK", table_header), _paragraph("RESOURCES", table_header), _paragraph("SHARE", table_header)]]
    total = len(resources)
    for level in ("High", "Medium", "Low"):
        risk_rows.append([_paragraph(level, body), _paragraph(risks[level], centered),
                          _paragraph(f"{(risks[level] / total * 100):.1f}%" if total else "0%", centered)])
    risk_table = Table(risk_rows, colWidths=[3.25 * inch, 1.05 * inch, 1.3 * inch])
    risk_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, colors.HexColor("#E3E7EF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TEXTCOLOR", (0, 1), (0, 1), RED), ("TEXTCOLOR", (0, 2), (0, 2), AMBER),
        ("TEXTCOLOR", (0, 3), (0, 3), GREEN),
    ]))
    story.append(risk_table)

    story.append(Paragraph("Priority Recommendations", section))
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    recommendations = sorted(recommendations, key=lambda item: (priority_order.get(item.get("priority"), 3),
                                                                  str(item.get("title") or "")))
    if recommendations:
        recommendation_rows = [[_paragraph("PRIORITY", table_header), _paragraph("RECOMMENDATION", table_header),
                                _paragraph("SERVICE", table_header), _paragraph("IMPACT", table_header)]]
        for item in recommendations:
            recommendation_rows.append([
                _paragraph(item.get("priority", "-"), body),
                _paragraph(item.get("title", "-"), body),
                _paragraph(item.get("affected_service", "-"), body),
                _paragraph(f"+{item.get('estimated_score_improvement', 0)} pts", centered),
            ])
        rec_table = LongTable(recommendation_rows, colWidths=[0.85 * inch, 3.85 * inch, 1.15 * inch, 0.95 * inch], repeatRows=1)
        rec_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 1), (-1, -1), 0.35, colors.HexColor("#E3E7EF")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(rec_table)
        for index, item in enumerate(recommendations, 1):
            story.append(Spacer(1, 3))
            story.append(_paragraph(f"{index}. {item.get('title', '-')} - {item.get('description', '')}", small))
    else:
        story.append(Paragraph("No recommendations were generated for this scan.", body))

    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    output.seek(0)
    return output


def upload_report_pdf(pdf: BytesIO, workspace_id: str, report_id: str) -> dict[str, Any]:
    bucket = settings.aws_report_bucket_name.strip()
    if not bucket:
        raise HTTPException(status_code=503, detail="PDF report storage is not configured")

    filename = f"cloudguard-disaster-recovery-{report_id}.pdf"
    key = f"workspaces/{workspace_id}/reports/{report_id}.pdf"
    disposition = f'attachment; filename="{filename}"'
    client = boto3.client("s3", region_name=settings.aws_region)
    pdf.seek(0)
    try:
        client.upload_fileobj(
            pdf,
            bucket,
            key,
            ExtraArgs={
                "ContentType": "application/pdf",
                "ContentDisposition": disposition,
                "ServerSideEncryption": "AES256",
                "Metadata": {"workspace-id": workspace_id, "report-id": report_id},
            },
        )
        download_url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentType": "application/pdf",
                "ResponseContentDisposition": disposition,
            },
            ExpiresIn=settings.aws_report_presign_expires_seconds,
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=502,
            detail="S3 rejected the report upload; verify the EC2 report-bucket permissions.",
        ) from exc
    except (BotoCoreError, S3UploadFailedError) as exc:
        raise HTTPException(status_code=502, detail="The PDF report could not be stored in S3.") from exc

    return {
        "bucket": bucket,
        "key": key,
        "filename": filename,
        "download_url": download_url,
        "expires_in": settings.aws_report_presign_expires_seconds,
    }
