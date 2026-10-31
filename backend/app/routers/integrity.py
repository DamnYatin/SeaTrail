"""
Evidence integrity sweep router.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_permission
from app.errors import AppError
from app.models.integrity import IntegrityRun
from app.models.users import User
from app.schemas.audit import SweepRunResponse
from app.security.permissions import Permission
from app.services import integrity

router = APIRouter(prefix="/api/v1/integrity", tags=["Integrity Engine"])


@router.post("/evidence-sweep", response_model=SweepRunResponse)
def trigger_evidence_sweep(
    request: Request,
    current_user: User = Depends(require_permission(Permission.VERIFY_HASH)),
    session: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    run = integrity.run_evidence_sweep(session=session, started_by=current_user.id, ip=ip)
    return run


@router.get("/runs/{run_id}", response_model=SweepRunResponse)
def get_integrity_run(
    run_id: str,
    current_user: User = Depends(require_permission(Permission.VERIFY_HASH)),
    session: Session = Depends(get_db),
):
    run = session.query(IntegrityRun).filter(IntegrityRun.id == run_id).first()
    if not run:
        raise AppError(code="NOT_FOUND", message="Integrity run not found", status_code=status.HTTP_404_NOT_FOUND)
    return run
