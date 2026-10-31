"""
Evidence management routes: intake, search/list, detail, download, verify, and label printing.
"""

import csv
import io
import json
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_case_with_access, get_current_user, require_permission
from app.errors import AppError
from app.models.audit import AuditLog
from app.models.cases import Case, CaseMember
from app.models.evidence import EvidenceItem, EvidenceStatus, EvidenceType, IntegrityStateEnum
from app.models.users import User, UserRole
from app.schemas.evidence import (
    EvidenceCreateMetadata,
    EvidenceListResponse,
    EvidenceResponse,
    EvidenceVerifyResponse,
)
from app.security.permissions import Permission, has_permission
from app.services import intake, integrity, labels, storage
from app.services.audit_chain import AuditAction, append, append_independent
from app.services.evidence_ids import validate_evidence_number

router = APIRouter(tags=["Evidence"])


def serialize_evidence(session: Session, item: EvidenceItem) -> EvidenceResponse:
    """Helper to attach case and user names to evidence item response."""
    case = session.query(Case).filter(Case.id == item.case_id).first()
    custodian = session.query(User).filter(User.id == item.current_custodian_id).first()
    collector = session.query(User).filter(User.id == item.collected_by_user_id).first()

    resp = EvidenceResponse.model_validate(item)
    if case:
        resp.case_number = case.case_number
        resp.case_name = case.name
    if custodian:
        resp.current_custodian_name = custodian.full_name
    if collector:
        resp.collected_by_name = collector.full_name
    return resp


@router.get("/api/v1/evidence", response_model=EvidenceListResponse)
def list_evidence(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=500),
    sort_by: str = Query("intake_at"),
    order: str = Query("desc"),
    case_id: Optional[str] = None,
    type: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = None,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvidenceListResponse:
    """Search and filter evidence items with server-side pagination."""
    if user.role == UserRole.ADMIN:
        raise AppError(code="FORBIDDEN", message="Administrators cannot view evidence", status_code=403)

    query = session.query(EvidenceItem)

    # Enforce case membership access control
    if user.role not in (UserRole.SUPERVISOR, UserRole.AUDITOR):
        user_case_ids = session.query(CaseMember.case_id).filter(CaseMember.user_id == user.id).subquery()
        query = query.filter(EvidenceItem.case_id.in_(select(user_case_ids)))

    if case_id:
        query = query.filter(EvidenceItem.case_id == case_id)
    if type:
        query = query.filter(EvidenceItem.type == type)
    if status_filter:
        query = query.filter(EvidenceItem.status == status_filter)
    if q:
        search = f"%{q.strip()}%"
        query = query.filter(
            or_(
                EvidenceItem.evidence_number.ilike(search),
                EvidenceItem.item_name.ilike(search),
                EvidenceItem.original_filename.ilike(search),
                EvidenceItem.sha256.ilike(search),
            )
        )

    total = query.count()

    sort_col = getattr(EvidenceItem, sort_by, EvidenceItem.intake_at)
    if order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    items = query.offset((page - 1) * page_size).limit(page_size).all()
    serialized = [serialize_evidence(session, item) for item in items]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return EvidenceListResponse(
        items=serialized,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/api/v1/evidence/export.csv")
def export_evidence_csv(
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Export evidence metadata CSV (audited, working copy)."""
    if user.role == UserRole.ADMIN:
        raise AppError(code="FORBIDDEN", message="Administrators cannot export evidence metadata", status_code=403)

    query = session.query(EvidenceItem)
    if user.role not in (UserRole.SUPERVISOR, UserRole.AUDITOR):
        user_case_ids = session.query(CaseMember.case_id).filter(CaseMember.user_id == user.id).subquery()
        query = query.filter(EvidenceItem.case_id.in_(select(user_case_ids)))

    items = query.order_by(EvidenceItem.intake_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Evidence Number", "Case Number", "Item Name", "Type", "Status",
        "SHA-256", "Size (Bytes)", "Current Custodian", "Location",
        "Intake Date (UTC)", "Legal Hold"
    ])

    for it in items:
        case = session.query(Case).filter(Case.id == it.case_id).first()
        cust = session.query(User).filter(User.id == it.current_custodian_id).first()
        writer.writerow([
            it.evidence_number,
            case.case_number if case else "",
            it.item_name,
            it.type.value,
            it.status.value,
            it.sha256,
            it.size_bytes,
            cust.full_name if cust else "",
            it.current_location,
            it.intake_at.strftime("%Y-%m-%d %H:%M:%S"),
            it.legal_hold,
        ])

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=user,
        action=AuditAction.EVIDENCE_LIST_EXPORTED,
        payload={"exported_count": len(items)},
        ip=ip,
    )

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sealtrail-evidence-export.csv"'},
    )


@router.post("/api/v1/cases/{case_id}/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
def intake_evidence(
    case_id: str,
    request: Request,
    metadata: str = Form(...),
    file: UploadFile = File(...),
    client_sha256: Optional[str] = Form(None),
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvidenceResponse:
    """Intake digital evidence with streaming SHA-256 and read-back verification."""
    case = get_case_with_access(case_id, user, session, request=request, allow_observer=False)

    if user.role not in (UserRole.INVESTIGATOR, UserRole.CUSTODIAN, UserRole.SUPERVISOR):
        raise AppError(code="FORBIDDEN", message="Role not authorized to intake evidence", status_code=403)

    try:
        meta_dict = json.loads(metadata)
    except json.JSONDecodeError:
        raise AppError(code="INVALID_METADATA", message="Metadata field must be valid JSON", status_code=400)

    ip = request.client.host if request.client else None
    item, verification = intake.register_evidence(
        session=session,
        case=case,
        user=user,
        file_stream=file.file,
        original_filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        metadata=meta_dict,
        client_sha256=client_sha256,
        ip=ip,
    )

    resp = serialize_evidence(session, item)
    resp.verification = verification
    return resp


@router.get("/api/v1/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(
    evidence_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvidenceResponse:
    """Get evidence details and audit EVIDENCE_VIEWED."""
    item = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not item:
        raise AppError(code="EVIDENCE_NOT_FOUND", message=f"Evidence {evidence_id} not found", status_code=404)

    get_case_with_access(item.case_id, user, session, request=request)

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=user,
        action=AuditAction.EVIDENCE_VIEWED,
        case_id=item.case_id,
        evidence_id=item.id,
        payload={"evidence_number": item.evidence_number},
        ip=ip,
    )

    return serialize_evidence(session, item)


@router.get("/api/v1/evidence/by-number/{evidence_number}", response_model=EvidenceResponse)
def get_evidence_by_number(
    evidence_number: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvidenceResponse:
    """Validate check character and resolve evidence item by number."""
    clean_number = evidence_number.strip().upper()
    if not validate_evidence_number(clean_number):
        raise AppError(
            code="INVALID_EVIDENCE_NUMBER",
            message=f"Evidence number '{clean_number}' has invalid format or check character",
            status_code=400,
        )

    item = session.query(EvidenceItem).filter(EvidenceItem.evidence_number == clean_number).first()
    if not item:
        raise AppError(code="EVIDENCE_NOT_FOUND", message=f"Evidence {clean_number} not found", status_code=404)

    get_case_with_access(item.case_id, user, session, request=request)

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=user,
        action=AuditAction.EVIDENCE_VIEWED,
        case_id=item.case_id,
        evidence_id=item.id,
        payload={"evidence_number": item.evidence_number, "lookup": "BY_NUMBER"},
        ip=ip,
    )

    return serialize_evidence(session, item)


@router.post("/api/v1/evidence/{evidence_id}/verify", response_model=EvidenceVerifyResponse)
def trigger_verify_evidence(
    evidence_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.VERIFY_HASH)),
) -> EvidenceVerifyResponse:
    """Trigger three-way cryptographic verification on an evidence item."""
    item = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not item:
        raise AppError(code="EVIDENCE_NOT_FOUND", message="Evidence not found", status_code=404)

    get_case_with_access(item.case_id, user, session, request=request)

    ip = request.client.host if request.client else None
    res = integrity.verify_evidence(session, item, actor=user, trigger="MANUAL_API", ip=ip)
    return EvidenceVerifyResponse(
        status=res.status,
        match=res.match,
        pinned_object_hash=res.pinned_object_hash,
        live_object_hash=res.live_object_hash,
        object_replaced=res.object_replaced,
        audit_hash_match=res.audit_hash_match,
        details=res.details,
    )


@router.get("/api/v1/evidence/{evidence_id}/download")
def download_evidence(
    evidence_id: str,
    request: Request,
    force: bool = Query(False),
    force_reason: Optional[str] = Query(None),
    session: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.DOWNLOAD_WORKING_COPY)),
):
    """
    Download evidence file.
    Verifies cryptographic hash first. Blocks on failure unless SUPERVISOR force=true.
    AUDITOR is forbidden from downloading working copies.
    """
    if user.role == UserRole.AUDITOR:
        raise AppError(code="FORBIDDEN", message="Auditors cannot download working copies", status_code=403)

    item = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not item:
        raise AppError(code="EVIDENCE_NOT_FOUND", message="Evidence not found", status_code=404)

    get_case_with_access(item.case_id, user, session, request=request)

    ip = request.client.host if request.client else None
    ver = integrity.verify_evidence(session, item, actor=user, trigger="DOWNLOAD_PRECHECK", ip=ip)

    if not ver.match:
        if force and user.role == UserRole.SUPERVISOR:
            append(
                session=session,
                actor=user,
                action=AuditAction.EVIDENCE_DOWNLOADED,
                case_id=item.case_id,
                evidence_id=item.id,
                payload={"forced": True, "justification": force_reason, "verdict": ver.status.value},
                ip=ip,
            )
        else:
            raise AppError(
                code="INTEGRITY_CHECK_FAILED",
                message=f"Download blocked: evidence failed cryptographic verification ({ver.status.value})",
                status_code=409,
                details=ver.details,
            )

    stream, ctype = storage.get_stream(item.storage_bucket, item.storage_key, item.storage_version_id)

    append(
        session=session,
        actor=user,
        action=AuditAction.EVIDENCE_DOWNLOADED,
        case_id=item.case_id,
        evidence_id=item.id,
        payload={"size_bytes": item.size_bytes, "sha256": item.sha256},
        ip=ip,
    )

    clean_filename = item.original_filename.replace('"', "")
    return StreamingResponse(
        stream,
        media_type=ctype,
        headers={"Content-Disposition": f'attachment; filename="{clean_filename}"'},
    )


@router.post("/api/v1/evidence/{evidence_id}/label")
def print_label(
    evidence_id: str,
    request: Request,
    size: str = Query("standard", pattern="^(standard|small)$"),
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate controlled PDF label with QR code, track reprint counter, and audit."""
    item = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not item:
        raise AppError(code="EVIDENCE_NOT_FOUND", message="Evidence not found", status_code=404)

    get_case_with_access(item.case_id, user, session, request=request)

    item.label_print_count += 1
    pdf_bytes = labels.render_label_pdf(item, is_small=(size == "small"), reprint_num=item.label_print_count)

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=user,
        action=AuditAction.LABEL_PRINTED,
        case_id=item.case_id,
        evidence_id=item.id,
        payload={"size": size, "print_count": item.label_print_count},
        ip=ip,
    )

    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/api/v1/evidence/{evidence_id}/custody")
def get_evidence_custody(
    evidence_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve full chronological custody and audit events for this specific item."""
    item = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not item:
        raise AppError(code="EVIDENCE_NOT_FOUND", message="Evidence not found", status_code=404)

    get_case_with_access(item.case_id, user, session, request=request)

    entries = (
        session.query(AuditLog)
        .filter(AuditLog.evidence_id == evidence_id)
        .order_by(AuditLog.seq.asc())
        .all()
    )

    results = []
    for e in entries:
        actor = session.query(User).filter(User.id == e.actor_id).first() if e.actor_id else None
        results.append({
            "seq": e.seq,
            "ts": e.ts.isoformat(),
            "action": e.action,
            "actor_id": e.actor_id,
            "actor_name": actor.full_name if actor else "System",
            "actor_role": e.actor_role,
            "payload": e.payload,
            "prev_hash": e.prev_hash,
            "entry_hash": e.entry_hash,
        })
    return results
