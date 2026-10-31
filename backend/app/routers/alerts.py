"""
Alerts router: view and manage explainable security alerts.
"""

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_permission
from app.errors import AppError
from app.models.alerts import Alert, AlertSeverity, AlertStatus
from app.models.cases import Case
from app.models.evidence import EvidenceItem
from app.models.users import User
from app.schemas.alerts import AlertResolveRequest, AlertResponse
from app.security.permissions import Permission
from app.services.audit_chain import AuditAction, append

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


def _to_alert_response(session: Session, alert: Alert) -> AlertResponse:
    case_num = None
    if alert.case_id:
        c = session.query(Case.case_number).filter(Case.id == alert.case_id).first()
        if c:
            case_num = c[0]

    ev_num = None
    if alert.evidence_id:
        e = (
            session.query(EvidenceItem.evidence_number)
            .filter(EvidenceItem.id == alert.evidence_id)
            .first()
        )
        if e:
            ev_num = e[0]

    return AlertResponse(
        id=alert.id,
        rule=alert.rule,
        severity=alert.severity,
        case_id=alert.case_id,
        case_number=case_num,
        evidence_id=alert.evidence_id,
        evidence_number=ev_num,
        details=alert.details or {},
        explanation=alert.explanation,
        audit_seqs=alert.audit_seqs or [],
        status=alert.status,
        dedupe_key=alert.dedupe_key,
        created_at=alert.created_at,
        acknowledged_by=alert.acknowledged_by,
        resolved_by=alert.resolved_by,
        resolution_note=alert.resolution_note,
    )


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    status_filter: AlertStatus | None = Query(None, alias="status"),
    severity: AlertSeverity | None = Query(None),
    case_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_permission(Permission.READ_ALERTS)),
    session: Session = Depends(get_db),
):
    query = session.query(Alert)
    if status_filter:
        query = query.filter(Alert.status == status_filter)
    if severity:
        query = query.filter(Alert.severity == severity)
    if case_id:
        query = query.filter(Alert.case_id == case_id)

    offset = (page - 1) * page_size
    alerts = query.order_by(desc(Alert.created_at)).offset(offset).limit(page_size).all()

    return [_to_alert_response(session, a) for a in alerts]


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: str,
    request: Request,
    current_user: User = Depends(require_permission(Permission.ACKNOWLEDGE_ALERTS)),
    session: Session = Depends(get_db),
):
    alert = session.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise AppError(
            code="NOT_FOUND", message="Alert not found", status_code=status.HTTP_404_NOT_FOUND
        )

    if alert.status == AlertStatus.RESOLVED:
        raise AppError(
            code="INVALID_STATE",
            message="Resolved alert cannot be acknowledged",
            status_code=status.HTTP_409_CONFLICT,
        )

    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_by = current_user.id
    session.flush()

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=current_user,
        action=AuditAction.ALERT_STATUS_CHANGED,
        case_id=alert.case_id,
        evidence_id=alert.evidence_id,
        payload={
            "alert_id": alert.id,
            "old_status": AlertStatus.OPEN.value,
            "new_status": AlertStatus.ACKNOWLEDGED.value,
            "rule": alert.rule,
        },
        ip=ip,
    )

    return _to_alert_response(session, alert)


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: str,
    req_body: AlertResolveRequest,
    request: Request,
    current_user: User = Depends(require_permission(Permission.RESOLVE_ALERTS)),
    session: Session = Depends(get_db),
):
    if not req_body.resolution_note or len(req_body.resolution_note.strip()) < 3:
        raise AppError(
            code="INVALID_INPUT",
            message="Resolution note must be at least 3 characters",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    alert = session.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise AppError(
            code="NOT_FOUND", message="Alert not found", status_code=status.HTTP_404_NOT_FOUND
        )

    old_status = alert.status.value
    alert.status = AlertStatus.RESOLVED
    alert.resolved_by = current_user.id
    alert.resolution_note = req_body.resolution_note.strip()
    session.flush()

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=current_user,
        action=AuditAction.ALERT_STATUS_CHANGED,
        case_id=alert.case_id,
        evidence_id=alert.evidence_id,
        payload={
            "alert_id": alert.id,
            "old_status": old_status,
            "new_status": AlertStatus.RESOLVED.value,
            "resolution_note": alert.resolution_note,
            "rule": alert.rule,
        },
        ip=ip,
    )

    return _to_alert_response(session, alert)
