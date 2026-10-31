"""
Export package router: export requests, builds, and downloads.
"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_permission
from app.errors import AppError
from app.models.approvals import ApprovalRequest
from app.models.exports import ExportPackage
from app.models.users import User
from app.schemas.approvals import ApprovalResponse
from app.schemas.exports import ExportBuildRequest, ExportCreateRequest, ExportResponse
from app.security.permissions import Permission
from app.services import export_package

router = APIRouter(prefix="/api/v1", tags=["Exports"])


@router.post("/evidence/{evidence_id}/exports", response_model=ApprovalResponse)
def create_export_request_endpoint(
    evidence_id: str,
    req_body: ExportCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission(Permission.REQUEST_EXPORT)),
    session: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    approval = export_package.create_export_request(
        session=session,
        evidence_id=evidence_id,
        requester=current_user,
        justification=req_body.justification,
        include_bsa_certificate=req_body.include_bsa_certificate,
        encrypt=req_body.encrypt,
        ip=ip,
    )
    return approval


@router.post("/exports/{approval_id}/build", response_model=ExportResponse)
def build_export_endpoint(
    approval_id: str,
    req_body: ExportBuildRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    export = export_package.build_export_package(
        session=session,
        approval_id=approval_id,
        actor=current_user,
        passphrase=req_body.passphrase,
        ip=ip,
    )
    return export


@router.get("/exports/{export_id}/download")
def download_export_endpoint(
    export_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    stream, pkg_hash, filename = export_package.get_export_download(
        session=session,
        export_id=export_id,
        actor=current_user,
        ip=ip,
    )
    return StreamingResponse(
        stream,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-SHA256": pkg_hash,
        },
    )
