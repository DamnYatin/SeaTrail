"""
Collaboration routes: Annotations, People Directory, Case Events, Notes, and Evidence Links.
"""

import hashlib
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_case_with_access, get_current_user
from app.errors import AppError
from app.models.evidence import EvidenceItem
from app.models.links import Annotation, CaseEvent, CaseNote, EvidenceLink, LinkTargetType, Person
from app.models.users import User
from app.schemas.collaboration import (
    AnnotationCreate,
    AnnotationResponse,
    CaseEventCreate,
    CaseEventResponse,
    CaseNoteCreate,
    CaseNoteResponse,
    EvidenceLinkCreate,
    EvidenceLinkResponse,
    PersonCreate,
    PersonResponse,
)
from app.services.audit_chain import AuditAction, append

router = APIRouter(tags=["Case Collaboration & Linking"])


# ---- Annotations ----
@router.get("/api/v1/evidence/{evidence_id}/annotations", response_model=List[AnnotationResponse])
def get_annotations(
    evidence_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[AnnotationResponse]:
    """List append-only annotations for an evidence item."""
    ev = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not ev:
        raise AppError(code="EVIDENCE_NOT_FOUND", message="Evidence not found", status_code=404)
    get_case_with_access(ev.case_id, user, session, request=request)

    notes = session.query(Annotation).filter(Annotation.evidence_id == evidence_id).order_by(Annotation.created_at.asc()).all()
    results = []
    for a in notes:
        u = session.query(User).filter(User.id == a.author_id).first()
        resp = AnnotationResponse.model_validate(a)
        if u:
            resp.author_name = u.full_name
        results.append(resp)
    return results


@router.post("/api/v1/evidence/{evidence_id}/annotations", response_model=AnnotationResponse, status_code=status.HTTP_201_CREATED)
def create_annotation(
    evidence_id: str,
    req: AnnotationCreate,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnnotationResponse:
    """Create an append-only annotation on evidence."""
    ev = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not ev:
        raise AppError(code="EVIDENCE_NOT_FOUND", message="Evidence not found", status_code=404)
    get_case_with_access(ev.case_id, user, session, request=request, allow_observer=False)

    body_clean = req.body.strip()
    body_hash = hashlib.sha256(body_clean.encode("utf-8")).hexdigest()

    ann = Annotation(
        evidence_id=evidence_id,
        author_id=user.id,
        body=body_clean,
        body_sha256=body_hash,
        parent_annotation_id=req.parent_annotation_id,
    )
    session.add(ann)
    session.flush()

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=user,
        action=AuditAction.EVIDENCE_ANNOTATED,
        case_id=ev.case_id,
        evidence_id=ev.id,
        payload={"annotation_id": ann.id, "body_sha256": body_hash},
        ip=ip,
    )

    resp = AnnotationResponse.model_validate(ann)
    resp.author_name = user.full_name
    return resp


# ---- People ----
@router.get("/api/v1/cases/{case_id}/people", response_model=List[PersonResponse])
def get_people(
    case_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[PersonResponse]:
    """List persons linked to a case."""
    get_case_with_access(case_id, user, session, request=request)
    return session.query(Person).filter(Person.case_id == case_id).all()


@router.post("/api/v1/cases/{case_id}/people", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
def add_person(
    case_id: str,
    req: PersonCreate,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PersonResponse:
    """Add a person of interest to a case."""
    get_case_with_access(case_id, user, session, request=request, allow_observer=False)

    p = Person(
        case_id=case_id,
        full_name=req.full_name.strip(),
        role_in_case=req.role_in_case,
        contact=req.contact.strip() if req.contact else None,
        notes=req.notes.strip() if req.notes else None,
        created_by=user.id,
    )
    session.add(p)
    session.flush()

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=user,
        action=AuditAction.PERSON_ADDED,
        case_id=case_id,
        payload={"person_id": p.id, "full_name": p.full_name, "role": p.role_in_case.value},
        ip=ip,
    )
    return p


# ---- Case Events ----
@router.get("/api/v1/cases/{case_id}/events", response_model=List[CaseEventResponse])
def get_case_events(
    case_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[CaseEventResponse]:
    """List timeline incident events for a case."""
    get_case_with_access(case_id, user, session, request=request)
    return session.query(CaseEvent).filter(CaseEvent.case_id == case_id).order_by(CaseEvent.occurred_at.asc()).all()


@router.post("/api/v1/cases/{case_id}/events", response_model=CaseEventResponse, status_code=status.HTTP_201_CREATED)
def add_case_event(
    case_id: str,
    req: CaseEventCreate,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseEventResponse:
    """Record an incident timeline event."""
    get_case_with_access(case_id, user, session, request=request, allow_observer=False)

    ev = CaseEvent(
        case_id=case_id,
        title=req.title.strip(),
        description=req.description.strip() if req.description else None,
        occurred_at=req.occurred_at,
        created_by=user.id,
    )
    session.add(ev)
    session.flush()

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=user,
        action=AuditAction.EVENT_ADDED,
        case_id=case_id,
        payload={"event_id": ev.id, "title": ev.title, "occurred_at": ev.occurred_at.isoformat()},
        ip=ip,
    )
    return ev


# ---- Case Notes ----
@router.get("/api/v1/cases/{case_id}/notes", response_model=List[CaseNoteResponse])
def get_case_notes(
    case_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[CaseNoteResponse]:
    """List append-only investigation notes."""
    get_case_with_access(case_id, user, session, request=request)
    notes = session.query(CaseNote).filter(CaseNote.case_id == case_id).order_by(CaseNote.created_at.asc()).all()
    results = []
    for n in notes:
        u = session.query(User).filter(User.id == n.author_id).first()
        resp = CaseNoteResponse.model_validate(n)
        if u:
            resp.author_name = u.full_name
        results.append(resp)
    return results


@router.post("/api/v1/cases/{case_id}/notes", response_model=CaseNoteResponse, status_code=status.HTTP_201_CREATED)
def add_case_note(
    case_id: str,
    req: CaseNoteCreate,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseNoteResponse:
    """Add an append-only case investigation note."""
    get_case_with_access(case_id, user, session, request=request, allow_observer=False)

    note = CaseNote(
        case_id=case_id,
        evidence_id=req.evidence_id,
        body=req.body.strip(),
        author_id=user.id,
    )
    session.add(note)
    session.flush()

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=user,
        action=AuditAction.NOTE_ADDED,
        case_id=case_id,
        evidence_id=req.evidence_id,
        payload={"note_id": note.id},
        ip=ip,
    )

    resp = CaseNoteResponse.model_validate(note)
    resp.author_name = user.full_name
    return resp


# ---- Evidence Links ----
@router.get("/api/v1/evidence/{evidence_id}/links", response_model=List[EvidenceLinkResponse])
def get_evidence_links(
    evidence_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[EvidenceLinkResponse]:
    """List links connecting evidence to people, events, notes, or other evidence."""
    ev = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not ev:
        raise AppError(code="EVIDENCE_NOT_FOUND", message="Evidence not found", status_code=404)
    get_case_with_access(ev.case_id, user, session, request=request)

    links = session.query(EvidenceLink).filter(EvidenceLink.evidence_id == evidence_id).all()
    results = []
    for lnk in links:
        target_name = None
        if lnk.target_type == LinkTargetType.PERSON:
            p = session.query(Person).filter(Person.id == lnk.target_id).first()
            if p:
                target_name = p.full_name
        elif lnk.target_type == LinkTargetType.EVENT:
            evt = session.query(CaseEvent).filter(CaseEvent.id == lnk.target_id).first()
            if evt:
                target_name = evt.title
        elif lnk.target_type == LinkTargetType.EVIDENCE:
            other = session.query(EvidenceItem).filter(EvidenceItem.id == lnk.target_id).first()
            if other:
                target_name = f"{other.evidence_number} ({other.item_name})"

        resp = EvidenceLinkResponse.model_validate(lnk)
        resp.target_name = target_name
        results.append(resp)
    return results


@router.post("/api/v1/evidence/{evidence_id}/links", response_model=EvidenceLinkResponse, status_code=status.HTTP_201_CREATED)
def create_evidence_link(
    evidence_id: str,
    req: EvidenceLinkCreate,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvidenceLinkResponse:
    """Link evidence to a person, event, note, or other evidence without touching evidence_items."""
    ev = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not ev:
        raise AppError(code="EVIDENCE_NOT_FOUND", message="Evidence not found", status_code=404)
    get_case_with_access(ev.case_id, user, session, request=request, allow_observer=False)

    existing = (
        session.query(EvidenceLink)
        .filter(
            EvidenceLink.evidence_id == evidence_id,
            EvidenceLink.target_type == req.target_type,
            EvidenceLink.target_id == req.target_id,
            EvidenceLink.relation == req.relation.strip(),
        )
        .first()
    )
    if existing:
        raise AppError(code="LINK_EXISTS", message="Link already exists", status_code=409)

    lnk = EvidenceLink(
        evidence_id=evidence_id,
        target_type=req.target_type,
        target_id=req.target_id,
        relation=req.relation.strip(),
        created_by=user.id,
    )
    session.add(lnk)
    session.flush()

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=user,
        action=AuditAction.EVIDENCE_LINKED,
        case_id=ev.case_id,
        evidence_id=ev.id,
        payload={"link_id": lnk.id, "target_type": lnk.target_type.value, "target_id": lnk.target_id, "relation": lnk.relation},
        ip=ip,
    )
    return EvidenceLinkResponse.model_validate(lnk)


@router.post("/api/v1/evidence/{evidence_id}/links/{link_id}/revoke")
def revoke_evidence_link(
    evidence_id: str,
    link_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Revoke a link without deleting it (soft revocation, audited)."""
    ev = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not ev:
        raise AppError(code="EVIDENCE_NOT_FOUND", message="Evidence not found", status_code=404)
    get_case_with_access(ev.case_id, user, session, request=request, allow_observer=False)

    lnk = session.query(EvidenceLink).filter(EvidenceLink.id == link_id, EvidenceLink.evidence_id == evidence_id).first()
    if not lnk:
        raise AppError(code="LINK_NOT_FOUND", message="Link not found", status_code=404)

    lnk.revoked_at = datetime.now(timezone.utc)
    lnk.revoked_by = user.id

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=user,
        action=AuditAction.EVIDENCE_LINK_REVOKED,
        case_id=ev.case_id,
        evidence_id=ev.id,
        payload={"link_id": lnk.id},
        ip=ip,
    )
    return {"status": "ok", "message": "Link revoked"}
