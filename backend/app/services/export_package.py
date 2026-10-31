"""
Export package service: generates verifiable ZIP export packages containing
original evidence, signed manifest, custody report, Section 63 BSA certificate,
public key, SHA256SUMS.txt, and standalone offline verify.py script.
"""

import base64
import hashlib
import io
import json
import os
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyzipper
from cryptography.hazmat.primitives import serialization
from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.models.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.models.audit import AuditLog
from app.models.evidence import EvidenceItem
from app.models.exports import ExportPackage
from app.models.users import User
from app.services import (
    audit_chain,
    bsa_certificate,
    checkpoints,
    custody_report,
    integrity,
    storage,
)
from app.services.audit_chain import AuditAction, append


def _canonicalize(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def create_export_request(
    session: Session,
    evidence_id: str,
    requester: User,
    justification: str,
    include_bsa_certificate: bool = True,
    encrypt: bool = False,
    ip: str | None = None,
) -> ApprovalRequest:
    """
    Initiate an export request requiring dual-authorization approval.
    """
    evidence = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not evidence:
        raise AppError(code="NOT_FOUND", message="Evidence not found", status_code=404)

    expires_at = datetime.now(UTC) + timedelta(hours=settings.APPROVAL_EXPIRY_HOURS)
    req = ApprovalRequest(
        kind=ApprovalKind.EXPORT_PACKAGE,
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        requested_by=requester.id,
        justification=justification,
        payload={
            "include_bsa_certificate": include_bsa_certificate,
            "encrypt": encrypt,
        },
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
        payload={
            "approval_id": req.id,
            "kind": req.kind.value,
            "justification": justification,
        },
        ip=ip,
    )
    return req


def build_export_package(
    session: Session,
    approval_id: str,
    actor: User,
    passphrase: str | None = None,
    ip: str | None = None,
) -> ExportPackage:
    """
    Assemble the complete cryptographic export package after approval.
    """
    approval = session.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not approval:
        raise AppError(code="NOT_FOUND", message="Approval request not found", status_code=404)

    if approval.status != ApprovalStatus.APPROVED:
        raise AppError(
            code="NOT_APPROVED",
            message=f"Approval status is {approval.status.value}",
            status_code=409,
        )

    evidence = session.query(EvidenceItem).filter(EvidenceItem.id == approval.evidence_id).first()
    if not evidence:
        raise AppError(code="NOT_FOUND", message="Evidence item not found", status_code=404)

    # 1. Verify evidence integrity first
    integ_res = integrity.verify_evidence(
        session=session, evidence=evidence, actor=actor, trigger="EXPORT_BUILD", ip=ip
    )
    if not integ_res.match:
        raise AppError(
            code="INTEGRITY_COMPROMISED",
            message=f"Evidence verification failed: {integ_res.status.value}",
            status_code=409,
        )

    # 2. Retrieve original evidence file content
    stream, _ = storage.get_stream(
        bucket=evidence.storage_bucket,
        key=evidence.storage_key,
        version_id=evidence.storage_version_id,
    )
    evidence_bytes = stream.read()
    evidence_filename = evidence.original_filename or f"{evidence.evidence_number}.bin"

    # 3. Custody report JSON and PDF
    report_dict = custody_report.generate_custody_report_data(
        session=session,
        evidence_id=evidence.id,
        actor=actor,
        ip=ip,
    )
    report_json_bytes = _canonicalize(report_dict)
    report_pdf_bytes = custody_report.generate_custody_report_pdf(report_dict)

    # 4. Optional BSA Section 63 certificate PDF
    include_bsa = (approval.payload or {}).get("include_bsa_certificate", True)
    bsa_pdf_bytes = None
    if include_bsa:
        bsa_pdf_bytes = bsa_certificate.generate_bsa_certificate_pdf(
            session=session,
            evidence=evidence,
            actor=actor,
            ip=ip,
        )

    # 5. Fetch audit trail for manifest
    audit_entries = (
        session.query(AuditLog)
        .filter(AuditLog.evidence_id == evidence.id)
        .order_by(asc(AuditLog.seq))
        .all()
    )

    # Nearest checkpoint
    cp = checkpoints.create_checkpoint(session, created_by=actor.id)
    public_key = checkpoints.get_public_key()
    pub_pem_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    manifest_data = {
        "export_version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "evidence": {
            "evidence_number": evidence.evidence_number,
            "item_name": evidence.item_name,
            "original_filename": evidence_filename,
            "sha256": evidence.sha256,
            "size_bytes": evidence.size_bytes,
            "type": evidence.type.value if hasattr(evidence.type, "value") else str(evidence.type),
            "source_description": evidence.source_description,
        },
        "approvals": {
            "approval_id": approval.id,
            "requested_by": approval.requested_by,
            "decided_by": approval.decided_by,
            "justification": approval.justification,
        },
        "checkpoint": {
            "seq_to": cp.seq_to if cp else None,
            "head_hash": cp.head_hash if cp else None,
            "signature_b64": cp.signature_b64 if cp else None,
            "public_key_id": checkpoints.get_public_key_id(),
        },
        "audit_trail": [
            {
                "seq": e.seq,
                "ts": audit_chain.format_iso_utc(e.ts),
                "actor_id": e.actor_id,
                "actor_role": e.actor_role,
                "action": e.action,
                "case_id": e.case_id,
                "evidence_id": e.evidence_id,
                "payload": e.payload or {},
                "ip": e.ip,
                "prev_hash": e.prev_hash,
                "entry_hash": e.entry_hash,
            }
            for e in audit_entries
        ],
    }

    manifest_bytes = _canonicalize(manifest_data)
    signing_key = checkpoints.get_signing_key()
    manifest_sig = signing_key.sign(manifest_bytes)
    manifest_sig_bytes = base64.b64encode(manifest_sig)

    # 6. Read verify.py template
    template_path = Path(__file__).resolve().parent.parent / "templates" / "verify_package.py"
    if template_path.exists():
        with open(template_path, "rb") as f:
            verify_script_bytes = f.read()
    else:
        verify_script_bytes = b"# verify.py missing template\n"

    # 7. README.txt
    readme_text = (
        f"SEALTRAIL DIGITAL EVIDENCE EXPORT PACKAGE\n"
        f"Evidence Number: {evidence.evidence_number}\n"
        f"Generated UTC: {datetime.now(UTC).isoformat()}\n\n"
        f"INSTRUCTIONS FOR VERIFICATION:\n"
        f"This export package contains cryptographic proofs and audit trails.\n"
        f"To verify this package completely offline:\n"
        f"1. Extract this package to a directory.\n"
        f"2. Run: python3 verify.py\n\n"
        f"The verifier validates all file hashes against SHA256SUMS.txt,\n"
        f"re-checks the continuous hash chain of all audit entries in manifest.json,\n"
        f"and verifies the Ed25519 digital signature with PUBLIC_KEY.pem.\n"
    ).encode()

    # 8. Compute checksums for SHA256SUMS.txt
    files_to_pack: dict[str, bytes] = {
        f"evidence/{evidence_filename}": evidence_bytes,
        "manifest.json": manifest_bytes,
        "manifest.sig": manifest_sig_bytes,
        "custody_report.json": report_json_bytes,
        "custody_report.pdf": report_pdf_bytes,
        "PUBLIC_KEY.pem": pub_pem_bytes,
        "verify.py": verify_script_bytes,
        "README.txt": readme_text,
    }
    if bsa_pdf_bytes:
        files_to_pack["BSA_s63_certificate_DRAFT.pdf"] = bsa_pdf_bytes

    sha256_lines = []
    for file_name, file_data in files_to_pack.items():
        f_hash = hashlib.sha256(file_data).hexdigest()
        sha256_lines.append(f"{f_hash}  {file_name}")

    sums_bytes = ("\n".join(sha256_lines) + "\n").encode("utf-8")
    files_to_pack["SHA256SUMS.txt"] = sums_bytes

    # 9. Build ZIP archive
    zip_buf = io.BytesIO()
    encrypt = bool(passphrase) or (approval.payload or {}).get("encrypt", False)

    if encrypt and passphrase:
        with pyzipper.AESZipFile(
            zip_buf,
            "w",
            compression=pyzipper.ZIP_DEFLATED,
            encryption=pyzipper.WZ_AES,
        ) as zf:
            zf.setpassword(passphrase.encode("utf-8"))
            for path_in_zip, data in files_to_pack.items():
                zf.writestr(path_in_zip, data)
    else:
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path_in_zip, data in files_to_pack.items():
                zf.writestr(path_in_zip, data)

    zip_bytes = zip_buf.getvalue()
    package_sha256 = hashlib.sha256(zip_bytes).hexdigest()
    package_size = len(zip_bytes)

    # 10. Upload to S3/MinIO exports bucket
    timestamp_slug = datetime.now(UTC).strftime("%Y%m%d_%H%M%SZ")
    export_key = (
        f"exports/{evidence.evidence_number}/{evidence.evidence_number}_{timestamp_slug}.zip"
    )
    storage.put_stream(
        bucket=settings.S3_BUCKET_EXPORTS,
        key=export_key,
        stream=io.BytesIO(zip_bytes),
    )

    # 11. Create ExportPackage record and update approval
    export = ExportPackage(
        evidence_id=evidence.id,
        case_id=evidence.case_id,
        approval_request_id=approval.id,
        requested_by=approval.requested_by,
        approved_by=approval.decided_by,
        encrypted=encrypt,
        package_sha256=package_sha256,
        package_size=package_size,
        storage_key=export_key,
    )
    session.add(export)

    approval.status = ApprovalStatus.EXECUTED
    approval.executed_at = datetime.now(UTC)
    session.flush()

    # 12. Audit event
    append(
        session=session,
        actor=actor,
        action=AuditAction.EXPORT_PACKAGE_BUILT,
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        payload={
            "export_id": export.id,
            "package_sha256": package_sha256,
            "package_size": package_size,
            "encrypted": encrypt,
            "evidence_number": evidence.evidence_number,
        },
        ip=ip,
    )

    return export


def get_export_download(
    session: Session,
    export_id: str,
    actor: User,
    ip: str | None = None,
) -> tuple[io.BytesIO, str, str]:
    """
    Download export package, re-verifying hash and auditing event.
    Returns (stream, sha256, filename).
    """
    export = session.query(ExportPackage).filter(ExportPackage.id == export_id).first()
    if not export:
        raise AppError(code="NOT_FOUND", message="Export package not found", status_code=404)

    stream, _ = storage.get_stream(bucket=settings.S3_BUCKET_EXPORTS, key=export.storage_key)
    data = stream.read()

    # Re-verify hash
    actual_hash = hashlib.sha256(data).hexdigest()
    if actual_hash != export.package_sha256:
        raise AppError(
            code="HASH_MISMATCH", message="Stored export package hash mismatch", status_code=500
        )

    export.download_count += 1
    session.flush()

    append(
        session=session,
        actor=actor,
        action=AuditAction.EXPORT_PACKAGE_DOWNLOADED,
        case_id=export.case_id,
        evidence_id=export.evidence_id,
        payload={"export_id": export.id, "package_sha256": actual_hash},
        ip=ip,
    )

    filename = os.path.basename(export.storage_key)
    return io.BytesIO(data), actual_hash, filename
