"""
Retention policies, legal holds, and approved evidence disposal router.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_permission
from app.errors import AppError
from app.models.cases import Case
from app.models.evidence import EvidenceItem
from app.models.users import User
from app.schemas.approvals import ApprovalResponse
from app.schemas.cases import CaseResponse
from app.schemas.retention import (
    DisposalRequest,
    LegalHoldReleaseRequest,
    LegalHoldRequest,
    RetentionDueItemResponse,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
)
from app.security.permissions import Permission
from app.services import retention

router = APIRouter(prefix="/api/v1", tags=["Retention & Compliance"])


@router.get("/retention/policies", response_model=List[RetentionPolicyResponse])
def get_retention_policies(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return retention.list_retention_policies(session)


@router.post("/retention/policies", response_model=RetentionPolicyResponse)
def create_retention_policy_endpoint(
    req: RetentionPolicyCreate,
    current_user: User = Depends(require_permission(Permission.PLACE_LEGAL_HOLD)),
    session: Session = Depends(get_db),
):
    return retention.create_retention_policy(
        session=session,
        name=req.name,
        retain_days=req.retain_days,
        description=req.description,
    )


@router.get("/retention/due", response_model=List[RetentionDueItemResponse])
def get_retention_due_items(
    days: int = Query(90, ge=1, le=365),
    current_user: User = Depends(require_permission(Permission.VIEW_CASE_METADATA)),
    session: Session = Depends(get_db),
):
    return retention.list_retention_due(session=session, days_threshold=days)


@router.post("/evidence/{evidence_id}/legal-hold")
def place_evidence_legal_hold(
    evidence_id: str,
    req_body: LegalHoldRequest,
    request: Request,
    current_user: User = Depends(require_permission(Permission.PLACE_LEGAL_HOLD)),
    session: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    ev = retention.place_legal_hold_evidence(
        session=session,
        evidence_id=evidence_id,
        actor=current_user,
        reason=req_body.reason,
        ip=ip,
    )
    return {"message": "Legal hold placed", "evidence_id": ev.id, "legal_hold": ev.legal_hold}


@router.post("/cases/{case_id}/legal-hold")
def place_case_legal_hold(
    case_id: str,
    req_body: LegalHoldRequest,
    request: Request,
    current_user: User = Depends(require_permission(Permission.PLACE_LEGAL_HOLD)),
    session: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    case = retention.place_legal_hold_case(
        session=session,
        case_id=case_id,
        actor=current_user,
        reason=req_body.reason,
        ip=ip,
    )
    return {"message": "Legal hold placed on case", "case_id": case.id, "legal_hold": case.legal_hold}


@router.post("/legal-hold/release-request", response_model=ApprovalResponse)
def request_legal_hold_release_endpoint(
    target_type: str = Query(..., pattern="^(EVIDENCE|CASE)$"),
    target_id: str = Query(...),
    req_body: LegalHoldReleaseRequest = ...,
    request: Request = None,
    current_user: User = Depends(require_permission(Permission.REQUEST_HOLD_RELEASE)),
    session: Session = Depends(get_db),
):
    ip = request.client.host if request and request.client else None
    return retention.request_legal_hold_release(
        session=session,
        target_type=target_type,
        target_id=target_id,
        requester=current_user,
        justification=req_body.justification,
        ip=ip,
    )


@router.post("/evidence/{evidence_id}/disposal", response_model=ApprovalResponse)
def request_evidence_disposal_endpoint(
    evidence_id: str,
    req_body: DisposalRequest,
    request: Request,
    current_user: User = Depends(require_permission(Permission.REQUEST_DISPOSAL)),
    session: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    return retention.request_disposal(
        session=session,
        evidence_id=evidence_id,
        requester=current_user,
        justification=req_body.justification,
        ip=ip,
    )


@router.post("/retention/disposal/{approval_id}/execute")
def execute_evidence_disposal_endpoint(
    approval_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    ev = retention.execute_disposal(
        session=session,
        approval_id=approval_id,
        actor=current_user,
        ip=ip,
    )
    return {
        "message": "Evidence disposed permanently",
        "evidence_id": ev.id,
        "evidence_number": ev.evidence_number,
        "sha256_tombstone": ev.sha256,
        "status": ev.status.value,
        "disposed_at": ev.disposed_at,
    }
