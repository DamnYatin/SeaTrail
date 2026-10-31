"""
Retention and compliance service:
- Legal holds on cases and evidence items (dual authorization for release)
- Configurable retention policies (Standard 5y, Extended 10y, Short 90d)
- Approved evidence disposal with permanent SHA-256 tombstone preserving audit trail
"""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.logging import logger
from app.models.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.models.cases import Case, RetentionPolicy
from app.models.evidence import EvidenceItem, EvidenceStatus
from app.models.users import User
from app.services import storage
from app.services.audit_chain import AuditAction, append


DEFAULT_POLICIES = [
    {"name": "Standard (5 Years)", "retain_days": 1825, "description": "Standard evidence retention policy"},
    {"name": "Extended (10 Years)", "retain_days": 3650, "description": "Extended statutory felony retention"},
    {"name": "Short (90 Days)", "retain_days": 90, "description": "Short evaluation and temporary media retention"},
]


def ensure_default_policies(session: Session) -> List[RetentionPolicy]:
    """Ensure baseline retention policies are seeded."""
    policies = session.query(RetentionPolicy).all()
    if not policies:
        created = []
        for p in DEFAULT_POLICIES:
            rp = RetentionPolicy(name=p["name"], retain_days=p["retain_days"], description=p["description"])
            session.add(rp)
            created.append(rp)
        session.flush()
        return created
    return policies


def list_retention_policies(session: Session) -> List[RetentionPolicy]:
    ensure_default_policies(session)
    return session.query(RetentionPolicy).order_by(asc(RetentionPolicy.retain_days)).all()


def create_retention_policy(session: Session, name: str, retain_days: int, description: Optional[str] = None) -> RetentionPolicy:
    existing = session.query(RetentionPolicy).filter(RetentionPolicy.name == name).first()
    if existing:
        raise AppError(code="DUPLICATE_POLICY", message=f"Policy '{name}' already exists", status_code=409)

    policy = RetentionPolicy(name=name, retain_days=retain_days, description=description)
    session.add(policy)
    session.flush()
    return policy


def place_legal_hold_evidence(
    session: Session,
    evidence_id: str,
    actor: User,
    reason: str,
    ip: Optional[str] = None,
) -> EvidenceItem:
    """Place a legal hold directly on an evidence item."""
    evidence = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not evidence:
        raise AppError(code="NOT_FOUND", message="Evidence not found", status_code=404)

    evidence.legal_hold = True
    session.flush()

    append(
        session=session,
        actor=actor,
        action=AuditAction.LEGAL_HOLD_PLACED,
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        payload={"reason": reason, "target_type": "EVIDENCE", "evidence_number": evidence.evidence_number},
        ip=ip,
    )
    return evidence


def place_legal_hold_case(
    session: Session,
    case_id: str,
    actor: User,
    reason: str,
    ip: Optional[str] = None,
) -> Case:
    """Place a legal hold across an entire case and all its evidence items."""
    case = session.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise AppError(code="NOT_FOUND", message="Case not found", status_code=404)

    case.legal_hold = True
    case.legal_hold_reason = reason

    # Cascade hold flag to evidence items
    items = session.query(EvidenceItem).filter(EvidenceItem.case_id == case.id).all()
    for it in items:
        it.legal_hold = True

    session.flush()

    append(
        session=session,
        actor=actor,
        action=AuditAction.LEGAL_HOLD_PLACED,
        case_id=case.id,
        payload={"reason": reason, "target_type": "CASE", "case_number": case.case_number},
        ip=ip,
    )
    return case


def request_legal_hold_release(
    session: Session,
    target_type: str,
    target_id: str,
    requester: User,
    justification: str,
    ip: Optional[str] = None,
) -> ApprovalRequest:
    """
    Request release of a legal hold requiring dual authorization.
    target_type: 'EVIDENCE' or 'CASE'
    """
    case_id = None
    evidence_id = None

    if target_type == "EVIDENCE":
        evidence = session.query(EvidenceItem).filter(EvidenceItem.id == target_id).first()
        if not evidence:
            raise AppError(code="NOT_FOUND", message="Evidence not found", status_code=404)
        case_id = evidence.case_id
        evidence_id = evidence.id
    elif target_type == "CASE":
        case = session.query(Case).filter(Case.id == target_id).first()
        if not case:
            raise AppError(code="NOT_FOUND", message="Case not found", status_code=404)
        case_id = case.id
    else:
        raise AppError(code="INVALID_TARGET", message="Target must be 'EVIDENCE' or 'CASE'", status_code=422)

    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.APPROVAL_EXPIRY_HOURS)
    req = ApprovalRequest(
        kind=ApprovalKind.LEGAL_HOLD_RELEASE,
        case_id=case_id,
        evidence_id=evidence_id,
        requested_by=requester.id,
        justification=justification,
        payload={"target_type": target_type, "target_id": target_id},
        status=ApprovalStatus.PENDING,
        expires_at=expires_at,
    )
    session.add(req)
    session.flush()

    append(
        session=session,
        actor=requester,
        action=AuditAction.APPROVAL_REQUESTED,
        case_id=case_id,
        evidence_id=evidence_id,
        payload={"approval_id": req.id, "kind": req.kind.value, "target_type": target_type},
        ip=ip,
    )
    return req


def execute_legal_hold_release(
    session: Session,
    approval_id: str,
    actor: User,
    ip: Optional[str] = None,
) -> None:
    """
    Release legal hold upon dual-authorization approval.
    """
    approval = session.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not approval:
        raise AppError(code="NOT_FOUND", message="Approval request not found", status_code=404)

    if approval.status != ApprovalStatus.APPROVED:
        raise AppError(code="NOT_APPROVED", message=f"Approval status is {approval.status.value}", status_code=409)

    target_type = approval.payload.get("target_type")
    target_id = approval.payload.get("target_id")

    if target_type == "EVIDENCE":
        evidence = session.query(EvidenceItem).filter(EvidenceItem.id == target_id).first()
        if evidence:
            evidence.legal_hold = False
    elif target_type == "CASE":
        case = session.query(Case).filter(Case.id == target_id).first()
        if case:
            case.legal_hold = False
            case.legal_hold_reason = None
            for it in session.query(EvidenceItem).filter(EvidenceItem.case_id == case.id).all():
                it.legal_hold = False

    approval.status = ApprovalStatus.EXECUTED
    approval.executed_at = datetime.now(timezone.utc)
    session.flush()

    append(
        session=session,
        actor=actor,
        action=AuditAction.LEGAL_HOLD_RELEASED,
        case_id=approval.case_id,
        evidence_id=approval.evidence_id,
        payload={"approval_id": approval.id, "target_type": target_type, "target_id": target_id},
        ip=ip,
    )


def list_retention_due(session: Session, days_threshold: int = 90) -> List[dict]:
    """
    List items due for retention expiration or past due.
    """
    cutoff = date.today() + timedelta(days=days_threshold)
    items = (
        session.query(EvidenceItem)
        .filter(
            EvidenceItem.status != EvidenceStatus.DISPOSED,
            EvidenceItem.retention_until != None,
            EvidenceItem.retention_until <= cutoff,
        )
        .all()
    )

    results = []
    for it in items:
        case = session.query(Case).filter(Case.id == it.case_id).first()
        case_hold = bool(case and case.legal_hold)
        has_hold = it.legal_hold or case_hold

        days_remaining = (it.retention_until - date.today()).days if it.retention_until else 0
        results.append({
            "evidence_id": it.id,
            "evidence_number": it.evidence_number,
            "item_name": it.item_name,
            "case_id": it.case_id,
            "case_number": case.case_number if case else None,
            "retention_until": it.retention_until,
            "days_remaining": days_remaining,
            "legal_hold": has_hold,
            "status": it.status.value if hasattr(it.status, "value") else str(it.status),
        })

    return results


def request_disposal(
    session: Session,
    evidence_id: str,
    requester: User,
    justification: str,
    ip: Optional[str] = None,
) -> ApprovalRequest:
    """
    Initiate disposal request. Blocked if legal hold exists or retention date not reached.
    """
    evidence = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not evidence:
        raise AppError(code="NOT_FOUND", message="Evidence not found", status_code=404)

    case = session.query(Case).filter(Case.id == evidence.case_id).first()

    # Hold check
    if evidence.legal_hold or (case and case.legal_hold):
        raise AppError(
            code="DISPOSAL_BLOCKED_BY_HOLD",
            message="Evidence is protected by an active Legal Hold; disposal is prohibited.",
            status_code=409,
        )

    # Retention date check
    if evidence.retention_until and evidence.retention_until > date.today():
        raise AppError(
            code="RETENTION_NOT_EXPIRED",
            message=f"Retention period has not expired (due {evidence.retention_until}); disposal is prohibited.",
            status_code=409,
        )

    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.APPROVAL_EXPIRY_HOURS)
    req = ApprovalRequest(
        kind=ApprovalKind.DISPOSAL,
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        requested_by=requester.id,
        justification=justification,
        payload={"evidence_number": evidence.evidence_number, "sha256": evidence.sha256},
        status=ApprovalStatus.PENDING,
        expires_at=expires_at,
    )
    session.add(req)
    session.flush()

    append(
        session=session,
        actor=requester,
        action=AuditAction.APPROVAL_REQUESTED,
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        payload={"approval_id": req.id, "kind": req.kind.value, "justification": justification},
        ip=ip,
    )
    return req


def execute_disposal(
    session: Session,
    approval_id: str,
    actor: User,
    ip: Optional[str] = None,
) -> EvidenceItem:
    """
    Execute disposal after dual-authorization approval.
    Permanently deletes all object versions from storage using disposer credentials.
    Sets status=DISPOSED with permanent sha256 tombstone.
    Metadata and complete audit history survive forever.
    """
    approval = session.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not approval:
        raise AppError(code="NOT_FOUND", message="Approval request not found", status_code=404)

    if approval.status != ApprovalStatus.APPROVED:
        raise AppError(code="NOT_APPROVED", message=f"Approval status is {approval.status.value}", status_code=409)

    evidence = session.query(EvidenceItem).filter(EvidenceItem.id == approval.evidence_id).first()
    if not evidence:
        raise AppError(code="NOT_FOUND", message="Evidence item not found", status_code=404)

    case = session.query(Case).filter(Case.id == evidence.case_id).first()
    if evidence.legal_hold or (case and case.legal_hold):
        raise AppError(code="DISPOSAL_BLOCKED_BY_HOLD", message="Disposal blocked by legal hold", status_code=409)

    # 1. Permanently delete all object versions from S3/MinIO
    storage.delete_all_versions(bucket=evidence.storage_bucket, key=evidence.storage_key)

    # 2. Update status and disposed_at
    now = datetime.now(timezone.utc)
    evidence.status = EvidenceStatus.DISPOSED
    evidence.disposed_at = now

    approval.status = ApprovalStatus.EXECUTED
    approval.executed_at = now
    session.flush()

    # 3. Permanent tombstone audit entry
    append(
        session=session,
        actor=actor,
        action=AuditAction.EVIDENCE_DISPOSED,
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        payload={
            "approval_id": approval.id,
            "evidence_number": evidence.evidence_number,
            "sha256": evidence.sha256,
            "disposed_at": now.isoformat(),
            "reason": approval.justification,
        },
        ip=ip,
    )

    return evidence
