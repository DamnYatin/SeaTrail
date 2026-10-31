"""
Export package records model.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.db import Base


def generate_uuid():
    return str(uuid.uuid4())


def utc_now():
    return datetime.now(UTC)


class ExportPackage(Base):
    __tablename__ = "exports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    evidence_id = Column(String(36), ForeignKey("evidence_items.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    approval_request_id = Column(String(36), ForeignKey("approval_requests.id"), nullable=True)
    requested_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    encrypted = Column(Boolean, default=False, nullable=False)
    package_sha256 = Column(String(64), nullable=False)
    package_size = Column(BigInteger, nullable=False)
    storage_key = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    download_count = Column(Integer, default=0, nullable=False)

    evidence = relationship("EvidenceItem")
    case = relationship("Case")
    requester = relationship("User", foreign_keys=[requested_by])
    approver = relationship("User", foreign_keys=[approved_by])
