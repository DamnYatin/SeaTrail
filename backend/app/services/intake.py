"""
Evidence intake pipeline service.
Performs streaming SHA-256 calculation, client hash validation, atomic ID allocation,
storage upload with immediate read-back verification, and atomic audit logging.
"""

import io
from datetime import UTC, datetime, timedelta
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.models.cases import Case, CaseStatus, RetentionPolicy
from app.models.evidence import EvidenceItem, EvidenceStatus, EvidenceType, IntegrityStateEnum
from app.models.users import User
from app.services import hashing, storage
from app.services.audit_chain import AuditAction, append, append_independent
from app.services.evidence_ids import format_evidence_number


def register_evidence(
    session: Session,
    case: Case,
    user: User,
    file_stream: BinaryIO,
    original_filename: str,
    content_type: str,
    metadata: dict,
    client_sha256: str | None = None,
    ip: str | None = None,
) -> tuple[EvidenceItem, dict]:
    """
    Execute full evidence intake pipeline.
    """
    if case.status != CaseStatus.OPEN:
        raise AppError(
            code="CASE_CLOSED", message="Cannot intake evidence into a closed case", status_code=400
        )

    # 1. Read file stream in 1 MiB chunks, compute SHA-256 and size
    hasher = hashing.hashlib.sha256()
    buffer = io.BytesIO()
    total_bytes = 0
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024

    while True:
        chunk = file_stream.read(1024 * 1024)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise AppError(
                code="PAYLOAD_TOO_LARGE",
                message=f"Upload exceeds maximum allowable limit of {settings.MAX_UPLOAD_MB} MB",
                status_code=413,
            )
        hasher.update(chunk)
        buffer.write(chunk)

    server_sha256 = hasher.hexdigest()
    buffer.seek(0)

    # 2. Validate client-supplied hash if present
    if client_sha256:
        client_clean = client_sha256.strip().lower()
        if client_clean != server_sha256:
            append_independent(
                actor=user,
                action=AuditAction.INTAKE_REJECTED,
                case_id=case.id,
                payload={
                    "reason": "CLIENT_HASH_MISMATCH",
                    "client_sha256": client_clean,
                    "server_sha256": server_sha256,
                    "filename": original_filename,
                },
                ip=ip,
            )
            raise AppError(
                code="CLIENT_HASH_MISMATCH",
                message=f"Client calculated hash ({client_clean}) does not match server intake hash ({server_sha256})",
                status_code=422,
                details={"client_sha256": client_clean, "server_sha256": server_sha256},
            )

    # 3. Atomically allocate evidence counter and number
    case.evidence_counter += 1
    session.flush()
    evidence_number = format_evidence_number(case.case_number, case.evidence_counter)

    # 4. Upload object to S3
    storage_bucket = settings.S3_BUCKET_EVIDENCE
    storage_key = f"{case.case_number}/{evidence_number}/{server_sha256}"

    version_id = storage.put_stream(
        bucket=storage_bucket,
        key=storage_key,
        stream=buffer,
        content_type=content_type,
    )

    # 5. Read back from S3 (pinned version) and re-verify hash
    try:
        readback_stream, _ = storage.get_stream(
            bucket=storage_bucket,
            key=storage_key,
            version_id=version_id,
        )
        readback_sha256 = hashing.hash_stream(readback_stream)
    except Exception as e:
        append_independent(
            actor=user,
            action=AuditAction.INTAKE_REJECTED,
            case_id=case.id,
            payload={
                "reason": "STORAGE_READBACK_FAILED",
                "error": str(e),
                "storage_key": storage_key,
            },
            ip=ip,
        )
        raise AppError(
            code="STORAGE_VERIFICATION_FAILED",
            message="Failed to read back evidence from storage",
            status_code=502,
        )

    if readback_sha256 != server_sha256:
        append_independent(
            actor=user,
            action=AuditAction.INTAKE_REJECTED,
            case_id=case.id,
            payload={
                "reason": "STORAGE_HASH_MISMATCH",
                "server_sha256": server_sha256,
                "readback_sha256": readback_sha256,
                "orphan_key": storage_key,
            },
            ip=ip,
        )
        raise AppError(
            code="STORAGE_VERIFICATION_FAILED",
            message="Read-back hash verification failed",
            status_code=502,
        )

    # 6. Calculate retention date
    retention_days = settings.DEFAULT_RETENTION_DAYS
    if case.retention_policy_id:
        policy = (
            session.query(RetentionPolicy)
            .filter(RetentionPolicy.id == case.retention_policy_id)
            .first()
        )
        if policy:
            retention_days = policy.retain_days

    now = datetime.now(UTC)
    retention_until = (now + timedelta(days=retention_days)).date()

    collected_at = metadata.get("collected_at")
    if isinstance(collected_at, str):
        collected_at = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
    elif not collected_at:
        collected_at = now

    # 7. Insert evidence record
    item = EvidenceItem(
        evidence_number=evidence_number,
        case_id=case.id,
        parent_evidence_id=metadata.get("parent_evidence_id"),
        type=EvidenceType(metadata.get("type", "FILE")),
        item_name=metadata.get("item_name", original_filename),
        description=metadata.get("description"),
        source_description=metadata.get("source_description"),
        collected_by_user_id=metadata.get("collected_by_user_id") or user.id,
        collected_at=collected_at,
        acquisition_method=metadata.get("acquisition_method"),
        acquisition_tool=metadata.get("acquisition_tool"),
        device_make=metadata.get("device_make"),
        device_model=metadata.get("device_model"),
        device_serial=metadata.get("device_serial"),
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=total_bytes,
        sha256=server_sha256,
        client_sha256=client_sha256.strip().lower() if client_sha256 else None,
        storage_bucket=storage_bucket,
        storage_key=storage_key,
        storage_version_id=version_id,
        intake_at=now,
        intake_by=user.id,
        current_custodian_id=user.id,
        current_location=metadata.get("current_location", "Digital Evidence Repository"),
        status=EvidenceStatus.IN_CUSTODY,
        integrity_state=IntegrityStateEnum.OK,
        last_verified_at=now,
        legal_hold=False,
        retention_until=retention_until,
        label_print_count=0,
    )
    session.add(item)
    session.flush()

    # Append audit entries
    append(
        session=session,
        actor=user,
        action=AuditAction.EVIDENCE_REGISTERED,
        case_id=case.id,
        evidence_id=item.id,
        payload={
            "evidence_number": item.evidence_number,
            "sha256": item.sha256,
            "size_bytes": item.size_bytes,
            "storage_key": item.storage_key,
            "version_id": item.storage_version_id,
            "client_sha256_present": bool(client_sha256),
        },
        ip=ip,
    )

    append(
        session=session,
        actor=user,
        action=AuditAction.INTAKE_HASH_VERIFIED,
        case_id=case.id,
        evidence_id=item.id,
        payload={
            "sha256": item.sha256,
            "readback_match": True,
        },
        ip=ip,
    )

    verification = {
        "server_sha256": server_sha256,
        "client_sha256": client_sha256,
        "readback_sha256": readback_sha256,
        "match": True,
    }

    return item, verification
