"""
Test 9: Integrity engine, anomaly rules, deduplication, scheduled chain check, and alerts API.
"""

import hashlib
import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.jobs.scheduler import run_scheduled_chain_check
from app.main import create_app
from app.models.alerts import AlertSeverity, AlertStatus
from app.models.cases import Case, CaseClassification, CaseMember, CaseMemberRole, CaseStatus
from app.models.custody import CustodyTransfer, TransferStatus
from app.models.evidence import EvidenceItem, EvidenceType, IntegrityStateEnum
from app.models.integrity import IntegrityState
from app.models.users import User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import create_access_token
from app.services import anomaly, audit_chain, storage


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    test_app = create_app()
    test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_app) as test_client:
        yield test_client
    test_app.dependency_overrides.clear()


@pytest.fixture
def integrity_setup(db_session: Session):
    uid = uuid.uuid4().hex[:6]
    sup = User(
        email=f"sup_integrity_{uid}@example.com",
        full_name="Supervisor Integ",
        role=UserRole.SUPERVISOR,
        password_hash=hash_password("Password123!"),
    )
    inv = User(
        email=f"inv_integrity_{uid}@example.com",
        full_name="Investigator Integ",
        role=UserRole.INVESTIGATOR,
        password_hash=hash_password("Password123!"),
    )
    aud = User(
        email=f"aud_integrity_{uid}@example.com",
        full_name="Auditor Integ",
        role=UserRole.AUDITOR,
        password_hash=hash_password("Password123!"),
    )
    db_session.add_all([sup, inv, aud])
    db_session.flush()

    case = Case(
        case_number=f"CASE-INTEG-{uid}",
        name="Integrity Verification Case",
        status=CaseStatus.OPEN,
        classification=CaseClassification.INTERNAL,
        lead_user_id=inv.id,
        created_by=sup.id,
    )
    db_session.add(case)
    db_session.flush()

    db_session.add_all(
        [
            CaseMember(
                case_id=case.id, user_id=sup.id, case_role=CaseMemberRole.MEMBER, added_by=sup.id
            ),
            CaseMember(
                case_id=case.id, user_id=inv.id, case_role=CaseMemberRole.LEAD, added_by=sup.id
            ),
        ]
    )
    db_session.flush()

    storage.set_mock_storage(True)
    content = b"Integrity test payload data"
    content_hash = hashlib.sha256(content).hexdigest()
    key = f"cases/{uid}/sample.bin"
    ver_id = storage.put_stream("evidence", key, io.BytesIO(content))

    item = EvidenceItem(
        evidence_number=f"SEAL-INTEG-{uid}-A",
        case_id=case.id,
        type=EvidenceType.FILE,
        item_name="IntegTestFile",
        description="Integrity test file",
        collected_by_user_id=inv.id,
        collected_at=datetime.now(UTC),
        original_filename="sample.bin",
        content_type="application/octet-stream",
        size_bytes=len(content),
        sha256=content_hash,
        storage_bucket="evidence",
        storage_key=key,
        storage_version_id=ver_id,
        intake_by=inv.id,
        current_custodian_id=inv.id,
        current_location="Lab Secure Cabinet",
        integrity_state=IntegrityStateEnum.OK,
    )
    db_session.add(item)
    db_session.flush()

    audit_chain.ensure_genesis_entry(db_session)

    return {"sup": sup, "inv": inv, "aud": aud, "case": case, "item": item}


def test_anomaly_rules_and_deduplication(db_session: Session, integrity_setup):
    sup = integrity_setup["sup"]
    inv = integrity_setup["inv"]
    item = integrity_setup["item"]

    # 1. HASH_MISMATCH
    alt1 = anomaly.create_or_dedupe_alert(
        session=db_session,
        rule="HASH_MISMATCH",
        severity=AlertSeverity.CRITICAL,
        explanation=f"Evidence {item.evidence_number} hash verification mismatch",
        details={"expected": item.sha256, "actual": "b" * 64},
        audit_seqs=[1],
        dedupe_key=f"HASH_MISMATCH:{item.id}:CRITICAL",
        evidence_id=item.id,
    )
    assert alt1 is not None
    assert alt1.severity == AlertSeverity.CRITICAL
    assert "hash verification mismatch" in alt1.explanation

    # Dedupe check
    alt1_dup = anomaly.create_or_dedupe_alert(
        session=db_session,
        rule="HASH_MISMATCH",
        severity=AlertSeverity.CRITICAL,
        explanation="Another attempt",
        details={},
        audit_seqs=[1],
        dedupe_key=f"HASH_MISMATCH:{item.id}:CRITICAL",
        evidence_id=item.id,
    )
    assert alt1_dup.id == alt1.id

    # 2. OBJECT_REPLACED
    alt2 = anomaly.create_or_dedupe_alert(
        session=db_session,
        rule="OBJECT_REPLACED",
        severity=AlertSeverity.HIGH,
        explanation=f"Evidence {item.evidence_number} object replaced out-of-band",
        details={"stored_version": "v1", "live_version": "v2"},
        audit_seqs=[1],
        dedupe_key=f"OBJECT_REPLACED:{item.id}:HIGH",
        evidence_id=item.id,
    )
    assert alt2 is not None
    assert alt2.severity == AlertSeverity.HIGH

    # 3. MISSING_ACK
    now = datetime.now(UTC)
    tr = CustodyTransfer(
        evidence_id=item.id,
        from_user_id=inv.id,
        to_user_id=sup.id,
        to_location="Vault A",
        reason="Testing SLA",
        status=TransferStatus.PENDING_ACK,
        ack_due_at=now - timedelta(minutes=settings.ACK_SLA_MINUTES + 10),
        requested_at=now - timedelta(hours=1),
        hash_at_send=item.sha256,
    )
    db_session.add(tr)
    db_session.flush()

    missing_alerts = anomaly.check_missing_acknowledgements(db_session)
    assert len(missing_alerts) >= 1
    assert any(a.rule == "MISSING_ACK" for a in missing_alerts)

    # 4. BURST_ACCESS
    for _ in range(settings.BURST_VIEW_THRESHOLD + 1):
        audit_chain.append(
            session=db_session,
            actor=inv,
            action=audit_chain.AuditAction.EVIDENCE_VIEWED,
            evidence_id=item.id,
            payload={},
        )
    burst_alerts = anomaly.check_burst_access(db_session)
    assert len(burst_alerts) >= 1
    assert any(a.rule == "BURST_ACCESS" for a in burst_alerts)

    # 5. REPEATED_DENIED
    for _ in range(settings.DENIED_ATTEMPTS_THRESHOLD + 1):
        audit_chain.append(
            session=db_session,
            actor=inv,
            action=audit_chain.AuditAction.ACCESS_DENIED,
            payload={"reason": "UNAUTHORIZED"},
        )
    denied_alerts = anomaly.check_repeated_denied(db_session)
    assert len(denied_alerts) >= 1
    assert any(a.rule == "REPEATED_DENIED" for a in denied_alerts)

    # 6. OFF_HOURS_ACCESS
    off_hours_alert = anomaly.check_off_hours_access(
        session=db_session,
        actor_id=inv.id,
        action_name="EVIDENCE_VIEWED",
        audit_seq=1,
        ts=datetime(2026, 1, 1, 2, 0, 0, tzinfo=UTC),  # 2 AM UTC = off hours
    )
    assert off_hours_alert is not None
    assert off_hours_alert.rule == "OFF_HOURS_ACCESS"


def test_scheduled_chain_check_and_integrity_state(db_session: Session, integrity_setup):
    # Verify initial scheduled check
    run_scheduled_chain_check()
    state = db_session.query(IntegrityState).filter(IntegrityState.id == 1).first()
    assert state is not None
    assert state.chain_ok is True
    assert state.head_seq >= 1


def test_alerts_and_audit_api(client: TestClient, db_session: Session, integrity_setup):
    sup = integrity_setup["sup"]
    inv = integrity_setup["inv"]
    sup_token = create_access_token(sup.id, sup.email, sup.role.value)
    inv_token = create_access_token(inv.id, inv.email, inv.role.value)

    # Raise a test alert
    alert = anomaly.create_or_dedupe_alert(
        session=db_session,
        rule="HASH_MISMATCH",
        severity=AlertSeverity.CRITICAL,
        explanation="API Test Alert",
        details={"test": True},
        audit_seqs=[1],
        dedupe_key="TEST:ALERT:1",
    )
    db_session.commit()

    # GET /alerts (Supervisor can read, Investigator cannot)
    resp = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {inv_token}"})
    assert resp.status_code == 403

    resp = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {sup_token}"})
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) >= 1

    # POST /alerts/{id}/acknowledge
    resp = client.post(
        f"/api/v1/alerts/{alert.id}/acknowledge", headers={"Authorization": f"Bearer {sup_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == AlertStatus.ACKNOWLEDGED.value

    # POST /alerts/{id}/resolve
    resp = client.post(
        f"/api/v1/alerts/{alert.id}/resolve",
        headers={"Authorization": f"Bearer {sup_token}"},
        json={"resolution_note": "False positive verified during test"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == AlertStatus.RESOLVED.value
    assert resp.json()["resolution_note"] == "False positive verified during test"

    # POST /audit/verify
    resp = client.post("/api/v1/audit/verify", headers={"Authorization": f"Bearer {sup_token}"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["checked"] >= 1

    # POST /integrity/evidence-sweep
    resp = client.post(
        "/api/v1/integrity/evidence-sweep", headers={"Authorization": f"Bearer {sup_token}"}
    )
    assert resp.status_code == 200
    sweep = resp.json()
    assert sweep["status"] == "COMPLETED"
    assert sweep["total"] >= 1
