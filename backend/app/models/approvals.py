"""
Dual-authorization approval request model with check constraint enforcing separate decider.
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db import Base


class ApprovalKind(str, enum.Enum):
    EXTERNAL_TRANSFER = "EXTERNAL_TRANSFER"
    EXPORT_PACKAGE = "EXPORT_PACKAGE"
    LEGAL_HOLD_RELEASE = "LEGAL_HOLD_RELEASE"
    DISPOSAL = "DISPOSAL"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"


def generate_uuid():
    return str(uuid.uuid4())


def utc_now():
    return datetime.now(timezone.utc)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        CheckConstraint(
            "decided_by IS NULL OR decided_by <> requested_by",
            name="check_separate_approver",
        ),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    kind = Column(Enum(ApprovalKind), nullable=False)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    evidence_id = Column(String(36), ForeignKey("evidence_items.id"), nullable=True, index=True)
    requested_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    justification = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False)
    decided_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_note = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    case = relationship("Case")
    evidence = relationship("EvidenceItem")
    requester = relationship("User", foreign_keys=[requested_by])
    decider = relationship("User", foreign_keys=[decided_by])
