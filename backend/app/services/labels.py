"""
Controlled evidence label PDF generator using ReportLab and QRCode.
Produces compliant physical labels (90x50mm and 50x25mm) with verifiable QR codes.
"""

import io

import qrcode
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.config import settings
from app.models.evidence import EvidenceItem


def generate_qr_image(data: str) -> io.BytesIO:
    """Generate high-contrast QR code image."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def render_label_pdf(evidence: EvidenceItem, is_small: bool = False, reprint_num: int = 0) -> bytes:
    """
    Render controlled label PDF:
    - 90x50 mm (Standard) or 50x25 mm (Small).
    - Monospace evidence number, QR code, intake date, SHA-256 prefix.
    - Reprints clearly watermarked REPRINT {n}.
    """
    width = 50 * mm if is_small else 90 * mm
    height = 25 * mm if is_small else 50 * mm

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=(width, height))

    qr_url = f"{settings.APP_BASE_URL}/e/{evidence.evidence_number}"
    qr_buf = generate_qr_image(qr_url)
    from reportlab.lib.utils import ImageReader

    qr_reader = ImageReader(qr_buf)

    if not is_small:
        # Standard format 90x50 mm
        # Header border & Product name
        p.setFont("Helvetica-Bold", 8)
        p.drawString(4 * mm, 44 * mm, "SEALTRAIL FORENSIC CUSTODY LABEL")

        if reprint_num > 1:
            p.setFillColorRGB(0.8, 0, 0)
            p.setFont("Helvetica-Bold", 8)
            p.drawRightString(86 * mm, 44 * mm, f"REPRINT #{reprint_num}")
            p.setFillColorRGB(0, 0, 0)

        # Draw QR Code on the right
        p.drawImage(qr_reader, 64 * mm, 16 * mm, width=22 * mm, height=22 * mm)

        # Monospace Evidence Number
        p.setFont("Courier-Bold", 11)
        p.drawString(4 * mm, 37 * mm, evidence.evidence_number)

        # Key metadata fields
        p.setFont("Helvetica", 7)
        case_no = evidence.case.case_number if evidence.case else "N/A"
        p.drawString(4 * mm, 31 * mm, f"CASE: {case_no}")
        p.drawString(4 * mm, 26 * mm, f"TYPE: {evidence.type.value}")
        p.drawString(
            4 * mm, 21 * mm, f"INTAKE: {evidence.intake_at.strftime('%Y-%m-%d %H:%M UTC')}"
        )
        p.drawString(4 * mm, 16 * mm, f"NAME: {evidence.item_name[:25]}")

        # Monospace SHA-256 prefix
        p.setFont("Courier", 7)
        sha_prefix = f"SHA: {evidence.sha256[:24]}..."
        p.drawString(4 * mm, 10 * mm, sha_prefix)

        # Classification footer
        p.setFont("Helvetica-Bold", 6)
        p.drawString(4 * mm, 5 * mm, "RESTRICTED — AUTHORIZED PERSONNEL ONLY")

    else:
        # Small format 50x25 mm
        # QR Code on the right
        p.drawImage(qr_reader, 34 * mm, 4 * mm, width=14 * mm, height=14 * mm)

        p.setFont("Courier-Bold", 7.5)
        p.drawString(2 * mm, 20 * mm, evidence.evidence_number)

        p.setFont("Helvetica", 5.5)
        case_no = evidence.case.case_number if evidence.case else "N/A"
        p.drawString(2 * mm, 15 * mm, f"CASE: {case_no}")
        p.drawString(2 * mm, 11 * mm, f"DATE: {evidence.intake_at.strftime('%Y-%m-%d')}")

        p.setFont("Courier", 5)
        p.drawString(2 * mm, 7 * mm, f"SHA:{evidence.sha256[:16]}")

        if reprint_num > 1:
            p.setFont("Helvetica-Bold", 5)
            p.drawString(2 * mm, 3 * mm, f"REPRINT #{reprint_num}")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer.getvalue()
