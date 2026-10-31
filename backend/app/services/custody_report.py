"""
Custody report service: signed JSON and ReportLab PDF custody report generation and offline verification.
"""

import base64
import hashlib
import io
import json
from datetime import UTC, datetime
from typing import Any

import qrcode
from cryptography.exceptions import InvalidSignature
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.cases import Case
from app.models.custody import CustodyTransfer
from app.models.evidence import EvidenceItem
from app.models.links import Annotation, EvidenceLink
from app.models.users import User
from app.schemas.reports import ReportVerifyResponse
from app.services import audit_chain, checkpoints, integrity
from app.services.audit_chain import AuditAction, append


def _canonicalize_json(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def generate_custody_report_data(
    session: Session,
    evidence_id: str,
    actor: User | None = None,
    ip: str | None = None,
) -> dict[str, Any]:
    """
    Generate cryptographically signed custody report JSON for an evidence item.
    """
    evidence = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not evidence:
        raise ValueError("Evidence item not found")

    case = session.query(Case).filter(Case.id == evidence.case_id).first()
    collector = (
        session.query(User).filter(User.id == evidence.collected_by_user_id).first()
        if evidence.collected_by_user_id
        else None
    )
    custodian = (
        session.query(User).filter(User.id == evidence.current_custodian_id).first()
        if evidence.current_custodian_id
        else None
    )

    # Audit trail for this item
    entries = (
        session.query(AuditLog)
        .filter(AuditLog.evidence_id == evidence.id)
        .order_by(asc(AuditLog.seq))
        .all()
    )

    # Transfers
    transfers = (
        session.query(CustodyTransfer)
        .filter(CustodyTransfer.evidence_id == evidence.id)
        .order_by(asc(CustodyTransfer.requested_at))
        .all()
    )

    # Annotations
    annotations = (
        session.query(Annotation)
        .filter(Annotation.evidence_id == evidence.id)
        .order_by(asc(Annotation.created_at))
        .all()
    )

    # Links
    links = (
        session.query(EvidenceLink)
        .filter(EvidenceLink.evidence_id == evidence.id, EvidenceLink.revoked_at is None)
        .all()
    )

    # Perform three-way verification
    integ_res = integrity.verify_evidence(
        session=session,
        evidence=evidence,
        actor=actor,
        trigger="CUSTODY_REPORT_GENERATION",
        ip=ip,
    )

    # Full chain check
    chain_res = audit_chain.verify_chain(session)

    # Create signed checkpoint on demand covering this entry
    cp = checkpoints.create_checkpoint(session, created_by=actor.id if actor else None)

    report_payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "evidence": {
            "id": evidence.id,
            "evidence_number": evidence.evidence_number,
            "item_name": evidence.item_name,
            "case_id": evidence.case_id,
            "case_number": case.case_number if case else None,
            "sha256": evidence.sha256,
            "size_bytes": evidence.size_bytes,
            "type": evidence.type.value if hasattr(evidence.type, "value") else str(evidence.type),
            "source_description": evidence.source_description,
            "collected_by": collector.full_name if collector else None,
            "collected_at": evidence.collected_at.isoformat() if evidence.collected_at else None,
            "current_custodian": custodian.full_name if custodian else None,
            "current_location": evidence.current_location,
            "status": evidence.status.value
            if hasattr(evidence.status, "value")
            else str(evidence.status),
            "legal_hold": evidence.legal_hold,
        },
        "transfers": [
            {
                "id": t.id,
                "from_user_id": t.from_user_id,
                "to_user_id": t.to_user_id,
                "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                "requested_at": t.requested_at.isoformat() if t.requested_at else None,
                "acknowledged_at": t.acknowledged_at.isoformat() if t.acknowledged_at else None,
                "receipt_verified": t.receipt_verified,
            }
            for t in transfers
        ],
        "annotations": [
            {
                "id": a.id,
                "author_id": a.author_id,
                "body": a.body,
                "body_sha256": a.body_sha256,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in annotations
        ],
        "links": [
            {
                "id": link.id,
                "target_type": link.target_type.value
                if hasattr(link.target_type, "value")
                else str(link.target_type),
                "target_id": link.target_id,
                "relation": link.relation,
            }
            for link in links
        ],
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
            for e in entries
        ],
        "integrity_block": {
            "chain_verified": chain_res.ok,
            "chain_head_seq": chain_res.head_seq,
            "chain_head_hash": chain_res.head_hash,
            "three_way_verified": integ_res.match,
            "three_way_status": integ_res.status.value,
            "nearest_checkpoint": {
                "id": cp.id,
                "seq_to": cp.seq_to,
                "head_hash": cp.head_hash,
                "signature_b64": cp.signature_b64,
                "public_key_id": cp.public_key_id,
            }
            if cp
            else None,
        },
    }

    # Canonicalize and sign
    canonical_bytes = _canonicalize_json(report_payload)
    report_sha256 = hashlib.sha256(canonical_bytes).hexdigest()

    signing_key = checkpoints.get_signing_key()
    signature = signing_key.sign(canonical_bytes)
    sig_b64 = base64.b64encode(signature).decode("ascii")

    full_report = {
        "report_data": report_payload,
        "report_sha256": report_sha256,
        "signature_b64": sig_b64,
        "public_key_id": checkpoints.get_public_key_id(),
    }

    # Record audit entry
    append(
        session=session,
        actor=actor,
        action=AuditAction.CUSTODY_REPORT_GENERATED,
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        payload={
            "report_sha256": report_sha256,
            "highest_seq_covered": entries[-1].seq if entries else 0,
            "entries_count": len(entries),
        },
        ip=ip,
    )

    return full_report


def generate_custody_report_pdf(report_dict: dict[str, Any]) -> bytes:
    """
    Render PDF custody report with ReportLab.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
    )
    section_title = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1e293b"),
    )
    mono_style = ParagraphStyle(
        "MonoText",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#334155"),
    )

    story = []

    report_data = report_dict.get("report_data", {})
    ev = report_data.get("evidence", {})
    integrity_block = report_data.get("integrity_block", {})
    report_sha = report_dict.get("report_sha256", "")
    sig_b64 = report_dict.get("signature_b64", "")

    # Header with title and QR Code
    qr_img = qrcode.make(f"https://sealtrail.local/verify-report?hash={report_sha}")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    header_table = Table(
        [
            [
                Paragraph("<b>SEALTRAIL DIGITAL EVIDENCE CUSTODY REPORT</b>", title_style),
                Image(qr_buf, width=64, height=64),
            ],
            [
                Paragraph(
                    f"Evidence ID: <b>{ev.get('evidence_number', 'N/A')}</b> &nbsp;|&nbsp; Case: <b>{ev.get('case_number', 'N/A')}</b> &nbsp;|&nbsp; Generated: {report_data.get('generated_at', '')}",
                    subtitle_style,
                ),
                "",
            ],
        ],
        colWidths=[450, 90],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("SPAN", (0, 1), (0, 1)),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ]
        )
    )
    story.append(header_table)
    story.append(
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=10)
    )

    # Evidence Summary
    story.append(Paragraph("1. EVIDENCE RECORD SUMMARY", section_title))
    summary_data = [
        [
            Paragraph("<b>Item Name:</b>", body_style),
            Paragraph(str(ev.get("item_name")), body_style),
            Paragraph("<b>Type:</b>", body_style),
            Paragraph(str(ev.get("type")), body_style),
        ],
        [
            Paragraph("<b>SHA-256:</b>", body_style),
            Paragraph(f"<font name='Courier' size=7>{ev.get('sha256')}</font>", body_style),
            Paragraph("<b>Size:</b>", body_style),
            Paragraph(f"{ev.get('size_bytes', 0):,} bytes", body_style),
        ],
        [
            Paragraph("<b>Collector:</b>", body_style),
            Paragraph(str(ev.get("collected_by")), body_style),
            Paragraph("<b>Collected At:</b>", body_style),
            Paragraph(str(ev.get("collected_at")), body_style),
        ],
        [
            Paragraph("<b>Current Custodian:</b>", body_style),
            Paragraph(str(ev.get("current_custodian")), body_style),
            Paragraph("<b>Location:</b>", body_style),
            Paragraph(str(ev.get("current_location")), body_style),
        ],
        [
            Paragraph("<b>Status:</b>", body_style),
            Paragraph(str(ev.get("status")), body_style),
            Paragraph("<b>Legal Hold:</b>", body_style),
            Paragraph("YES" if ev.get("legal_hold") else "NO", body_style),
        ],
    ]
    st = Table(summary_data, colWidths=[100, 200, 90, 150])
    st.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(st)
    story.append(Spacer(1, 10))

    # Cryptographic Integrity Status
    story.append(Paragraph("2. CRYPTOGRAPHIC INTEGRITY VERIFICATION", section_title))
    cp_info = integrity_block.get("nearest_checkpoint", {}) or {}
    integ_data = [
        [
            Paragraph("<b>Three-Way Binding:</b>", body_style),
            Paragraph(
                "<font color='green'><b>PASS (OK)</b></font>"
                if integrity_block.get("three_way_verified")
                else "<font color='red'><b>FAIL</b></font>",
                body_style,
            ),
            Paragraph("<b>Audit Chain Status:</b>", body_style),
            Paragraph(
                "<font color='green'><b>PASS (VALID)</b></font>"
                if integrity_block.get("chain_verified")
                else "<font color='red'><b>BROKEN</b></font>",
                body_style,
            ),
        ],
        [
            Paragraph("<b>Chain Head Seq:</b>", body_style),
            Paragraph(str(integrity_block.get("chain_head_seq")), body_style),
            Paragraph("<b>Nearest Checkpoint:</b>", body_style),
            Paragraph(
                f"Seq #{cp_info.get('seq_to', 'N/A')} (Key ID: {cp_info.get('public_key_id', 'N/A')})",
                body_style,
            ),
        ],
        [
            Paragraph("<b>Report SHA-256:</b>", body_style),
            Paragraph(f"<font name='Courier' size=7>{report_sha}</font>", body_style),
            Paragraph("<b>Ed25519 Signature:</b>", body_style),
            Paragraph(
                f"<font name='Courier' size=7>{sig_b64[:24]}...{sig_b64[-12:]}</font>", body_style
            ),
        ],
    ]
    it = Table(integ_data, colWidths=[110, 180, 110, 140])
    it.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(it)
    story.append(Spacer(1, 10))

    # Chronological Audit Trail
    story.append(Paragraph("3. COMPLETE CHRONOLOGICAL AUDIT TRAIL", section_title))
    audit_entries = report_data.get("audit_trail", [])
    table_rows = [
        [
            Paragraph("<b>Seq</b>", body_style),
            Paragraph("<b>Timestamp (UTC)</b>", body_style),
            Paragraph("<b>Action</b>", body_style),
            Paragraph("<b>Actor</b>", body_style),
            Paragraph("<b>Entry Hash</b>", body_style),
        ]
    ]
    for row in audit_entries:
        table_rows.append(
            [
                Paragraph(str(row.get("seq")), mono_style),
                Paragraph(str(row.get("ts"))[:19].replace("T", " "), mono_style),
                Paragraph(str(row.get("action")), mono_style),
                Paragraph(f"{row.get('actor_role') or ''}", mono_style),
                Paragraph(f"{row.get('entry_hash', '')[:16]}...", mono_style),
            ]
        )

    at = Table(table_rows, colWidths=[35, 110, 155, 90, 150])
    at.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(at)
    story.append(Spacer(1, 15))

    # Mandatory Legal Notice Footer
    notice = (
        "<b>LEGAL NOTICE:</b> Auto-filled draft generated by SealTrail. To be reviewed, "
        "completed and signed by authorized personnel. Not legal advice. "
        "Cryptographically verifiable against live audit log via /verify-report."
    )
    story.append(Paragraph(notice, subtitle_style))

    doc.build(story)
    return buf.getvalue()


def verify_custody_report(session: Session, report_dict: dict[str, Any]) -> ReportVerifyResponse:
    """
    Verify report signature, report hash, and audit trail consistency against the live chain.
    """
    details: dict[str, Any] = {}

    report_data = report_dict.get("report_data")
    report_sha256 = report_dict.get("report_sha256")
    sig_b64 = report_dict.get("signature_b64")

    if not report_data or not report_sha256 or not sig_b64:
        return ReportVerifyResponse(
            valid=False,
            signature_valid=False,
            report_hash_valid=False,
            audit_entries_match=False,
            details={"error": "Missing report_data, report_sha256, or signature_b64"},
        )

    # 1. Verify Report Hash
    canonical_bytes = _canonicalize_json(report_data)
    computed_hash = hashlib.sha256(canonical_bytes).hexdigest()
    report_hash_valid = computed_hash == report_sha256
    details["report_hash_match"] = report_hash_valid

    # 2. Verify Ed25519 signature
    signature_valid = False
    try:
        pub_key = checkpoints.get_public_key()
        sig_bytes = base64.b64decode(sig_b64)
        pub_key.verify(sig_bytes, canonical_bytes)
        signature_valid = True
    except InvalidSignature:
        signature_valid = False
        details["signature_error"] = "Invalid digital signature"
    except Exception as e:
        signature_valid = False
        details["signature_error"] = str(e)

    # 3. Verify each audit entry matches the live chain
    audit_trail = report_data.get("audit_trail", [])
    audit_entries_match = True
    mismatched_seqs = []

    for entry in audit_trail:
        seq = entry.get("seq")
        live_entry = session.query(AuditLog).filter(AuditLog.seq == seq).first()
        if not live_entry:
            audit_entries_match = False
            mismatched_seqs.append({"seq": seq, "reason": "ENTRY_NOT_IN_LIVE_CHAIN"})
            continue

        if (
            live_entry.entry_hash != entry.get("entry_hash")
            or live_entry.prev_hash != entry.get("prev_hash")
            or live_entry.action != entry.get("action")
        ):
            audit_entries_match = False
            mismatched_seqs.append(
                {
                    "seq": seq,
                    "reason": "HASH_OR_ACTION_MISMATCH",
                    "live_entry_hash": live_entry.entry_hash,
                    "report_entry_hash": entry.get("entry_hash"),
                }
            )

    if mismatched_seqs:
        details["mismatched_entries"] = mismatched_seqs

    overall_valid = report_hash_valid and signature_valid and audit_entries_match
    return ReportVerifyResponse(
        valid=overall_valid,
        signature_valid=signature_valid,
        report_hash_valid=report_hash_valid,
        audit_entries_match=audit_entries_match,
        details=details,
    )
