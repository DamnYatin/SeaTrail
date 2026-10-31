"""
Evidence items data model.
Distinguishes between immutable intake attributes and mutable lifecycle states.
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db import Base


class EvidenceType(str, enum.Enum):
    FILE = "FILE"
    DISK_IMAGE = "DISK_IMAGE"
    MOBILE_EXTRACT = "MOBILE_EXTRACT"
    CLOUD_EXPORT = "CLOUD_EXPORT"
    EMAIL = "EMAIL"
    NETWORK_CAPTURE = "NETWORK_CAPTURE"
    OTHER = "OTHER"


class EvidenceStatus(str, enum.Enum):
    REGISTERED = "REGISTERED"
    IN_CUSTODY = "IN_CUSTODY"
    TRANSFER_PENDING = "TRANSFER_PENDING"
    DISPOSED = "DISPOSED"


class IntegrityStateEnum(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    OK = "OK"
    OBJECT_REPLACED = "OBJECT_REPLACED"
    CORRUPT = "CORRUPT"


def generate_uuid():
    return str(uuid.uuid4())


def utc_now():
    return datetime.now(timezone.utc)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    # Primary key and identifiers
    id = Column(String(36), primary_key=True, default=generate_uuid)
    evidence_number = Column(String(50), unique=True, nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    parent_evidence_id = Column(String(36), ForeignKey("evidence_items.id"), nullable=True)

    # Immutable intake metadata
    type = Column(Enum(EvidenceType), nullable=False)
    item_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_description = Column(Text, nullable=True)
    collected_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    collected_at = Column(DateTime(timezone=True), nullable=False)
    acquisition_method = Column(String(255), nullable=True)
    acquisition_tool = Column(String(255), nullable=True)
    device_make = Column(String(100), nullable=True)
    device_model = Column(String(100), nullable=True)
    device_serial = Column(String(100), nullable=True)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    client_sha256 = Column(String(64), nullable=True)
    storage_bucket = Column(String(100), nullable=False)
    storage_key = Column(String(500), nullable=False)
    storage_version_id = Column(String(255), nullable=True)
    intake_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    intake_by = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Mutable lifecycle states
    current_custodian_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    current_location = Column(String(255), nullable=False)
    status = Column(Enum(EvidenceStatus), default=EvidenceStatus.IN_CUSTODY, nullable=False)
    integrity_state = Column(
        Enum(IntegrityStateEnum), default=IntegrityStateEnum.OK, nullable=False
    )
    last_verified_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    legal_hold = Column(Boolean, default=False, nullable=False)
    retention_until = Column(Date, nullable=True)
    label_print_count = Column(Integer, default=0, nullable=False)
    disposed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    case = relationship("Case")
    custodian = relationship("User", foreign_keys=[current_custodian_id])
    collector = relationship("User", foreign_keys=[collected_by_user_id])
