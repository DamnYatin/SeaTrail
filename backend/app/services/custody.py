"""
Chain-of-custody transfer lifecycle and verification state machine.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.models.approvals import ApprovalKind
from app.models.cases import CaseMember
from app.models.custody import CustodyTransfer, TransferStatus
from app.models.evidence import EvidenceItem, EvidenceStatus
from app.models.users import User, UserRole
from app.services import approvals, integrity
from app.services.audit_chain import AuditAction, append


def initiate_transfer(
    session: Session,
    evidence: EvidenceItem,
    sender: User,
    to_user_id: str | None,
    to_location: str,
    reason: str,
    is_external: bool = False,
    external_party: str | None = None,
    ip: str | None = None,
) -> CustodyTransfer:
    """Initiate custody transfer following pre-verification and role validation."""
    # Caller must be custodian or lead
    is_custodian = evidence.current_custodian_id == sender.id
    case_member = (
        session.query(CaseMember)
        .filter(CaseMember.case_id == evidence.case_id, CaseMember.user_id == sender.id)
        .first()
    )
    is_lead = (case_member and case_member.case_role.value == "LEAD") or (
        sender.role == UserRole.SUPERVISOR
    )

    if not is_custodian and not is_lead:
        raise AppError(
            code="FORBIDDEN",
            message="Only current custodian or Case Lead can transfer evidence",
            status_code=403,
        )

    if evidence.status == EvidenceStatus.TRANSFER_PENDING:
        raise AppError(
            code="TRANSFER_IN_PROGRESS",
            message="Evidence already has a transfer in progress",
            status_code=409,
        )

    # Pre-verification check
    ver = integrity.verify_evidence(
        session, evidence, actor=sender, trigger="TRANSFER_PRECHECK", ip=ip
    )
    if not ver.match:
        raise AppError(
            code="INTEGRITY_CHECK_FAILED",
            message=f"Transfer blocked: evidence failed cryptographic verification ({ver.status.value})",
            status_code=409,
        )

    now = datetime.now(UTC)
    ack_due_at = now + timedelta(minutes=settings.ACK_SLA_MINUTES)

    status_initial = TransferStatus.PENDING_ACK
    approval_req_id = None

    if is_external:
        if not external_party:
            raise AppError(
                code="MISSING_PARAM",
                message="External party name required for external transfer",
                status_code=400,
            )
        status_initial = TransferStatus.PENDING_APPROVAL
        ack_due_at = None

        app_req = approvals.create_approval_request(
            session=session,
            case_id=evidence.case_id,
            kind=ApprovalKind.EXTERNAL_TRANSFER,
            requester=sender,
            justification=f"External transfer to {external_party}: {reason}",
            evidence_id=evidence.id,
            payload={"external_party": external_party, "to_location": to_location},
            ip=ip,
        )
        approval_req_id = app_req.id
    else:
        if not to_user_id:
            raise AppError(
                code="MISSING_PARAM",
                message="Designated receiver required for internal transfer",
                status_code=400,
            )
        # Verify receiver is member of case
        rec_member = (
            session.query(CaseMember)
            .filter(CaseMember.case_id == evidence.case_id, CaseMember.user_id == to_user_id)
            .first()
        )
        if not rec_member:
            raise AppError(
                code="RECEIVER_NOT_MEMBER",
                message="Recipient must be an active member of this case",
                status_code=400,
            )

    transfer = CustodyTransfer(
        evidence_id=evidence.id,
        from_user_id=sender.id,
        to_user_id=to_user_id,
        to_location=to_location.strip(),
        reason=reason.strip(),
        is_external=is_external,
        external_party=external_party.strip() if external_party else None,
        status=status_initial,
        approval_request_id=approval_req_id,
        hash_at_send=evidence.sha256,
        requested_at=now,
        ack_due_at=ack_due_at,
    )
    session.add(transfer)
    evidence.status = EvidenceStatus.TRANSFER_PENDING

    append(
        session=session,
        actor=sender,
        action=AuditAction.TRANSFER_REQUESTED,
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        payload={
            "transfer_id": transfer.id,
            "to_user_id": to_user_id,
            "to_location": to_location,
            "is_external": is_external,
            "hash_at_send": transfer.hash_at_send,
        },
        ip=ip,
    )
    return transfer


def acknowledge_transfer(
    session: Session,
    transfer_id: str,
    receiver: User,
    ip: str | None = None,
) -> CustodyTransfer:
    """Acknowledge receipt and complete custody transfer with re-verification."""
    transfer = session.query(CustodyTransfer).filter(CustodyTransfer.id == transfer_id).first()
    if not transfer:
        raise AppError(
            code="TRANSFER_NOT_FOUND", message="Transfer record not found", status_code=404
        )

    if transfer.status != TransferStatus.PENDING_ACK:
        raise AppError(
            code="INVALID_STATE",
            message=f"Transfer cannot be acknowledged in status {transfer.status.value}",
            status_code=400,
        )

    if transfer.to_user_id != receiver.id:
        raise AppError(
            code="FORBIDDEN",
            message="Only the designated receiver can acknowledge receipt",
            status_code=403,
        )

    evidence = session.query(EvidenceItem).filter(EvidenceItem.id == transfer.evidence_id).first()
    ver = integrity.verify_evidence(
        session, evidence, actor=receiver, trigger="RECEIPT_ACKNOWLEDGEMENT", ip=ip
    )

    now = datetime.now(UTC)
    transfer.acknowledged_at = now
    transfer.hash_at_receipt = ver.pinned_object_hash or evidence.sha256
    transfer.receipt_verified = ver.match

    if ver.match:
        transfer.status = TransferStatus.COMPLETED
        evidence.current_custodian_id = receiver.id
        evidence.current_location = transfer.to_location
        evidence.status = EvidenceStatus.IN_CUSTODY

        append(
            session=session,
            actor=receiver,
            action=AuditAction.TRANSFER_ACKNOWLEDGED,
            case_id=evidence.case_id,
            evidence_id=evidence.id,
            payload={
                "transfer_id": transfer.id,
                "new_custodian_id": receiver.id,
                "location": transfer.to_location,
                "hash_at_receipt": transfer.hash_at_receipt,
            },
            ip=ip,
        )
    else:
        transfer.status = TransferStatus.DISPUTED
        # Custodian does not change on dispute
        evidence.status = EvidenceStatus.IN_CUSTODY

        append(
            session=session,
            actor=receiver,
            action=AuditAction.TRANSFER_DISPUTED,
            case_id=evidence.case_id,
            evidence_id=evidence.id,
            payload={
                "transfer_id": transfer.id,
                "hash_at_send": transfer.hash_at_send,
                "hash_at_receipt": transfer.hash_at_receipt,
            },
            ip=ip,
        )

    return transfer


def reject_transfer(
    session: Session,
    transfer_id: str,
    receiver: User,
    reason: str,
    ip: str | None = None,
) -> CustodyTransfer:
    """Reject custody transfer request."""
    transfer = session.query(CustodyTransfer).filter(CustodyTransfer.id == transfer_id).first()
    if not transfer:
        raise AppError(
            code="TRANSFER_NOT_FOUND", message="Transfer record not found", status_code=404
        )

    if transfer.status not in (TransferStatus.PENDING_ACK, TransferStatus.PENDING_APPROVAL):
        raise AppError(
            code="INVALID_STATE", message="Transfer is not in a rejectable state", status_code=400
        )

    if (
        transfer.to_user_id
        and transfer.to_user_id != receiver.id
        and receiver.role != UserRole.SUPERVISOR
    ):
        raise AppError(
            code="FORBIDDEN",
            message="Only designated receiver or supervisor can reject transfer",
            status_code=403,
        )

    transfer.status = TransferStatus.REJECTED
    evidence = session.query(EvidenceItem).filter(EvidenceItem.id == transfer.evidence_id).first()
    evidence.status = EvidenceStatus.IN_CUSTODY

    append(
        session=session,
        actor=receiver,
        action=AuditAction.TRANSFER_REJECTED,
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        payload={"transfer_id": transfer.id, "reason": reason},
        ip=ip,
    )
    return transfer


def cancel_transfer(
    session: Session,
    transfer_id: str,
    sender: User,
    ip: str | None = None,
) -> CustodyTransfer:
    """Cancel custody transfer request by sender before acknowledgement."""
    transfer = session.query(CustodyTransfer).filter(CustodyTransfer.id == transfer_id).first()
    if not transfer:
        raise AppError(
            code="TRANSFER_NOT_FOUND", message="Transfer record not found", status_code=404
        )

    if transfer.status not in (TransferStatus.PENDING_ACK, TransferStatus.PENDING_APPROVAL):
        raise AppError(
            code="INVALID_STATE", message="Transfer cannot be cancelled", status_code=400
        )

    if transfer.from_user_id != sender.id and sender.role != UserRole.SUPERVISOR:
        raise AppError(
            code="FORBIDDEN",
            message="Only sender or supervisor can cancel transfer",
            status_code=403,
        )

    transfer.status = TransferStatus.CANCELLED
    evidence = session.query(EvidenceItem).filter(EvidenceItem.id == transfer.evidence_id).first()
    evidence.status = EvidenceStatus.IN_CUSTODY

    append(
        session=session,
        actor=sender,
        action=AuditAction.TRANSFER_CANCELLED,
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        payload={"transfer_id": transfer.id},
        ip=ip,
    )
    return transfer
