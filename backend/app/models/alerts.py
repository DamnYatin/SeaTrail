"""
Security and anomaly alert tracking model.
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    ARRAY,
    BigInteger,
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


class AlertSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


def generate_uuid():
    return str(uuid.uuid4())


def utc_now():
    return datetime.now(timezone.utc)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    rule = Column(String(100), nullable=False, index=True)
    severity = Column(Enum(AlertSeverity), nullable=False)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=True, index=True)
    evidence_id = Column(String(36), ForeignKey("evidence_items.id"), nullable=True, index=True)
    details = Column(JSON, nullable=False)
    explanation = Column(Text, nullable=False)
    audit_seqs = Column(JSON, nullable=False, default=list)  # Stored as JSON list of integers for cross-db compatibility
    status = Column(Enum(AlertStatus), default=AlertStatus.OPEN, nullable=False)
    dedupe_key = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    acknowledged_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    resolution_note = Column(Text, nullable=True)

    case = relationship("Case")
    evidence = relationship("EvidenceItem")
