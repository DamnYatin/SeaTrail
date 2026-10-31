"""
Custody reports router: signed JSON and PDF custody reports, and verification.
"""

import io
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_permission
from app.errors import AppError
from app.models.evidence import EvidenceItem
from app.models.users import User
from app.schemas.reports import ReportVerifyRequest, ReportVerifyResponse
from app.security.permissions import Permission
from app.services import custody_report

router = APIRouter(prefix="/api/v1", tags=["Reports"])


@router.get("/evidence/{evidence_id}/custody-report")
def get_custody_report(
    evidence_id: str,
    request: Request,
    format: str = Query("json", pattern="^(json|pdf)$"),
    current_user: User = Depends(require_permission(Permission.VIEW_CASE_METADATA)),
    session: Session = Depends(get_db),
):
    evidence = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not evidence:
        raise AppError(code="NOT_FOUND", message="Evidence item not found", status_code=status.HTTP_404_NOT_FOUND)

    ip = request.client.host if request.client else None
    report_dict = custody_report.generate_custody_report_data(
        session=session,
        evidence_id=evidence_id,
        actor=current_user,
        ip=ip,
    )

    if format == "pdf":
        pdf_bytes = custody_report.generate_custody_report_pdf(report_dict)
        filename = f"SEALTRAIL-REPORT-{evidence.evidence_number}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    return report_dict


@router.post("/reports/verify", response_model=ReportVerifyResponse)
def verify_report_endpoint(
    req: ReportVerifyRequest,
    session: Session = Depends(get_db),
):
    return custody_report.verify_custody_report(session, req.report)
