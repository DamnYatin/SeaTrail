"""
Custody transfer tracking model.
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db import Base


class TransferStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    PENDING_ACK = "PENDING_ACK"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    DISPUTED = "DISPUTED"


def generate_uuid():
    return str(uuid.uuid4())


def utc_now():
    return datetime.now(timezone.utc)


class CustodyTransfer(Base):
    __tablename__ = "custody_transfers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    evidence_id = Column(String(36), ForeignKey("evidence_items.id"), nullable=False, index=True)
    from_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    to_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    to_location = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    is_external = Column(Boolean, default=False, nullable=False)
    external_party = Column(String(255), nullable=True)
    status = Column(Enum(TransferStatus), default=TransferStatus.PENDING_ACK, nullable=False)
    approval_request_id = Column(String(36), ForeignKey("approval_requests.id"), nullable=True)
    hash_at_send = Column(String(64), nullable=False)
    requested_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    ack_due_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    hash_at_receipt = Column(String(64), nullable=True)
    receipt_verified = Column(Boolean, nullable=True)

    evidence = relationship("EvidenceItem")
    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user = relationship("User", foreign_keys=[to_user_id])
