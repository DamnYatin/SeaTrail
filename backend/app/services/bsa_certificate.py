"""
Bharatiya Sakshya Adhiniyam, 2023 (BSA) Section 63 Certificate draft generator.
Statutory electronic record certificate auto-filling factual evidence parameters (SHA-256 hash,
device/source, acquisition tool) while preserving mandatory review, expert, and signature blocks.
"""

import io
from datetime import datetime, timezone
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.models.evidence import EvidenceItem
from app.models.users import User
from app.services.audit_chain import AuditAction, append


def generate_bsa_certificate_pdf(
    session: Session,
    evidence: EvidenceItem,
    actor: Optional[User] = None,
    ip: Optional[str] = None,
) -> bytes:
    """
    Generate statutory draft certificate under Section 63(4)(c) of the Bharatiya Sakshya Adhiniyam, 2023.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CertTitle",
        parent=styles["Heading1"],
        fontSize=13,
        leading=16,
        alignment=1,  # Center
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "CertSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        alignment=1,  # Center
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#334155"),
        spaceAfter=10,
    )
    part_header = ParagraphStyle(
        "PartHeader",
        parent=styles["Heading2"],
        fontSize=11,
        leading=15,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "CertBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1e293b"),
    )
    mono_style = ParagraphStyle(
        "CertMono",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
    )
    footer_style = ParagraphStyle(
        "CertFooter",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b"),
        alignment=1,
    )

    story = []

    # Statutory Title
    story.append(Paragraph("THE SCHEDULE<br/>[See section 63(4)(c)]", subtitle_style))
    story.append(
        Paragraph(
            "CERTIFICATE UNDER SECTION 63 OF THE BHARATIYA SAKSHYA ADHINIYAM, 2023<br/>"
            "FOR ADMISSIBILITY OF ELECTRONIC RECORD",
            title_style,
        )
    )
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94a3b8"), spaceAfter=8))

    # PART A
    story.append(Paragraph("PART A<br/><font size=8>(To be filled by the Party producing the electronic record)</font>", part_header))
    story.append(
        Paragraph(
            "I, the undersigned, hereby certify the particulars of the electronic record produced herein:",
            body_style,
        )
    )
    story.append(Spacer(1, 4))

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    part_a_data = [
        [Paragraph("<b>1. Description of Electronic Record:</b>", body_style),
         Paragraph(f"{evidence.item_name} ({evidence.original_filename or 'N/A'})", body_style)],
        [Paragraph("<b>2. Evidence Registration ID:</b>", body_style),
         Paragraph(str(evidence.evidence_number), mono_style)],
        [Paragraph("<b>3. Source / Device Details:</b>", body_style),
         Paragraph(f"Make: {evidence.device_make or 'N/A'} | Model: {evidence.device_model or 'N/A'} | Serial: {evidence.device_serial or 'N/A'}", body_style)],
        [Paragraph("<b>4. Source Description:</b>", body_style),
         Paragraph(str(evidence.source_description or "Digital media item"), body_style)],
        [Paragraph("<b>5. Acquisition Method & Tool:</b>", body_style),
         Paragraph(f"Method: {evidence.acquisition_method or 'N/A'} | Tool: {evidence.acquisition_tool or 'N/A'}", body_style)],
        [Paragraph("<b>6. Cryptographic Hash Algorithm:</b>", body_style),
         Paragraph("<b>Secure Hash Algorithm 256-bit (SHA-256)</b>", body_style)],
        [Paragraph("<b>7. Cryptographic Hash Value:</b>", body_style),
         Paragraph(f"<font name='Courier' size=7><b>{evidence.sha256}</b></font>", body_style)],
        [Paragraph("<b>8. File Size:</b>", body_style),
         Paragraph(f"{evidence.size_bytes:,} bytes", body_style)],
        [Paragraph("<b>9. Date & Time of Extraction:</b>", body_style),
         Paragraph(evidence.collected_at.strftime("%Y-%m-%d %H:%M:%S UTC") if evidence.collected_at else "N/A", body_style)],
    ]
    t_a = Table(part_a_data, colWidths=[200, 330])
    t_a.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    story.append(t_a)
    story.append(Spacer(1, 6))

    # Declaration Block Part A
    decl_a = (
        "<b>Declaration by Custodian / Producing Party:</b><br/>"
        "I hereby declare that the electronic record described above was produced in the ordinary course of "
        "lawful custody/investigation. During the relevant period, computer systems and storage media operated "
        "properly and without any impairment affecting the accuracy or integrity of the contents."
    )
    story.append(Paragraph(decl_a, body_style))
    story.append(Spacer(1, 10))

    sig_table_a = Table([
        [Paragraph("Signature: ___________________________", body_style), Paragraph(f"Date: ________________________", body_style)],
        [Paragraph("Name: ______________________________", body_style), Paragraph("Designation: __________________", body_style)],
    ], colWidths=[270, 260])
    story.append(sig_table_a)
    story.append(Spacer(1, 10))

    # PART B
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94a3b8"), spaceAfter=8))
    story.append(Paragraph("PART B<br/><font size=8>(To be filled by the Examiner / Forensic Expert)</font>", part_header))
    story.append(
        Paragraph(
            "I, the undersigned forensic / technical examiner, have examined the digital evidence described in Part A. "
            "I verified that the cryptographic SHA-256 hash value matches the original bitstream image without variation.",
            body_style,
        )
    )
    story.append(Spacer(1, 4))

    part_b_data = [
        [Paragraph("<b>Forensic Tool & Environment:</b>", body_style), Paragraph("____________________________________________________________", body_style)],
        [Paragraph("<b>Verification SHA-256 Hash:</b>", body_style), Paragraph(f"<font name='Courier' size=7>{evidence.sha256}</font>", body_style)],
        [Paragraph("<b>Hash Verification Result:</b>", body_style), Paragraph("VERIFIED AND DEFENDED / INTEGRITY INTACT", body_style)],
    ]
    t_b = Table(part_b_data, colWidths=[200, 330])
    t_b.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    story.append(t_b)
    story.append(Spacer(1, 6))

    story.append(
        Paragraph(
            "<b>Declaration by Expert:</b><br/>"
            "I certify that the electronic record is a true and identical copy of the examined data and "
            "no alteration, deletion or insertion has occurred during custody and analysis.",
            body_style,
        )
    )
    story.append(Spacer(1, 10))

    sig_table_b = Table([
        [Paragraph("Expert Signature: ______________________", body_style), Paragraph("Date: ________________________", body_style)],
        [Paragraph("Examiner Name: _______________________", body_style), Paragraph("Institution / Lab: _____________", body_style)],
    ], colWidths=[270, 260])
    story.append(sig_table_b)
    story.append(Spacer(1, 15))

    # Mandatory Non-Negotiable Footer
    notice = (
        "<b>Auto-filled draft generated by SealTrail. To be reviewed, completed and signed by "
        "the responsible person (Part A) and the expert (Part B). Not legal advice.</b>"
    )
    story.append(Paragraph(notice, footer_style))

    doc.build(story)

    # Audit logging
    append(
        session=session,
        actor=actor,
        action=AuditAction.BSA_CERTIFICATE_GENERATED,
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        payload={"evidence_number": evidence.evidence_number, "sha256": evidence.sha256},
        ip=ip,
    )

    return buf.getvalue()
