"""
Schemas for Annotations, People, Case Events, Case Notes, and Evidence Links.
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.links import LinkTargetType, PersonRole


class AnnotationCreate(BaseModel):
    body: str
    parent_annotation_id: str | None = None


class AnnotationResponse(BaseModel):
    id: str
    evidence_id: str
    author_id: str
    author_name: str | None = None
    body: str
    body_sha256: str
    parent_annotation_id: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class PersonCreate(BaseModel):
    full_name: str
    role_in_case: PersonRole = PersonRole.OTHER
    contact: str | None = None
    notes: str | None = None


class PersonResponse(BaseModel):
    id: str
    case_id: str
    full_name: str
    role_in_case: PersonRole
    contact: str | None = None
    notes: str | None = None
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class CaseEventCreate(BaseModel):
    title: str
    description: str | None = None
    occurred_at: datetime


class CaseEventResponse(BaseModel):
    id: str
    case_id: str
    title: str
    description: str | None = None
    occurred_at: datetime
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class CaseNoteCreate(BaseModel):
    body: str
    evidence_id: str | None = None


class CaseNoteResponse(BaseModel):
    id: str
    case_id: str
    evidence_id: str | None = None
    body: str
    author_id: str
    author_name: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class EvidenceLinkCreate(BaseModel):
    target_type: LinkTargetType
    target_id: str
    relation: str


class EvidenceLinkResponse(BaseModel):
    id: str
    evidence_id: str
    target_type: LinkTargetType
    target_id: str
    relation: str
    target_name: str | None = None
    created_by: str
    created_at: datetime
    revoked_at: datetime | None = None
    revoked_by: str | None = None

    class Config:
        from_attributes = True
