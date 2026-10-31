"""
Test 12: Retention policies, legal holds, dual authorization hold release,
and disposal enforcement with permanent tombstone.
"""

from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import create_app
from app.models.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.models.cases import Case, CaseClassification, CaseMember, CaseMemberRole, CaseStatus
from app.models.evidence import EvidenceItem, EvidenceStatus, EvidenceType, IntegrityStateEnum
from app.models.users import User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import create_access_token
from app.services import audit_chain, retention, storage


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
def retention_setup(db_session: Session):
    storage.set_mock_storage(True)
    uid = uuid.uuid4().hex[:6]

    sup1 = User(
        email=f"sup1_ret_{uid}@example.com",
        full_name="Supervisor One",
        role=UserRole.SUPERVISOR,
        password_hash=hash_password("Password123!"),
    )
    sup2 = User(
        email=f"sup2_ret_{uid}@example.com",
        full_name="Supervisor Two",
        role=UserRole.SUPERVISOR,
        password_hash=hash_password("Password123!"),
    )
    db_session.add_all([sup1, sup2])
    db_session.flush()

    case = Case(
        case_number=f"CASE-RET-{uid}",
        name="Retention Test Case",
        status=CaseStatus.OPEN,
        classification=CaseClassification.INTERNAL,
        lead_user_id=sup1.id,
        created_by=sup1.id,
    )
    db_session.add(case)
    db_session.flush()

    db_session.add_all([
        CaseMember(case_id=case.id, user_id=sup1.id, case_role=CaseMemberRole.LEAD, added_by=sup1.id),
        CaseMember(case_id=case.id, user_id=sup2.id, case_role=CaseMemberRole.MEMBER, added_by=sup1.id),
    ])
    db_session.flush()

    content = b"Binary evidence data to be tested for retention and disposal"
    content_hash = hashlib.sha256(content).hexdigest()
    key = f"cases/{uid}/dispose_test.bin"
    ver_id = storage.put_stream("evidence", key, io.BytesIO(content))

    item = EvidenceItem(
        evidence_number=f"SEAL-RET-{uid}-A",
        case_id=case.id,
        type=EvidenceType.FILE,
        item_name="RetentionTestFile",
        description="Evidence item for retention and disposal tests",
        collected_by_user_id=sup1.id,
        collected_at=datetime.now(timezone.utc),
        original_filename="dispose_test.bin",
        content_type="application/octet-stream",
        size_bytes=len(content),
        sha256=content_hash,
        storage_bucket="evidence",
        storage_key=key,
        storage_version_id=ver_id,
        intake_by=sup1.id,
        current_custodian_id=sup1.id,
        current_location="Secure Room 2",
        integrity_state=IntegrityStateEnum.OK,
        legal_hold=False,
        retention_until=date.today() + timedelta(days=365),  # Unexpired by default
    )
    db_session.add(item)
    db_session.flush()

    audit_chain.ensure_genesis_entry(db_session)
    audit_chain.append(
        session=db_session,
        actor=sup1,
        action=audit_chain.AuditAction.EVIDENCE_REGISTERED,
        case_id=case.id,
        evidence_id=item.id,
        payload={"sha256": content_hash, "item_name": item.item_name},
    )

    return {"sup1": sup1, "sup2": sup2, "case": case, "item": item, "content": content}


def test_12_retention_legal_hold_and_disposal(client: TestClient, db_session: Session, retention_setup):
    """
    Test 12:
    - Retention policies listing and custom policy creation
    - Disposal blocked by unexpired retention
    - Legal hold placement on evidence
    - Disposal blocked by legal hold
    - Legal hold release via dual authorization
    - Disposal allowed once retention expired and hold cleared
    - Object deleted from storage, status=DISPOSED, sha256 tombstone intact, audit preserved
    """
    sup1 = retention_setup["sup1"]
    sup2 = retention_setup["sup2"]
    case = retention_setup["case"]
    item = retention_setup["item"]
    sup1_token = create_access_token(sup1.id, sup1.email, sup1.role.value)
    sup2_token = create_access_token(sup2.id, sup2.email, sup2.role.value)

    # 1. Retention policies API
    resp_pol = client.get("/api/v1/retention/policies", headers={"Authorization": f"Bearer {sup1_token}"})
    assert resp_pol.status_code == 200
    policies = resp_pol.json()
    assert len(policies) >= 3

    new_pol = client.post(
        "/api/v1/retention/policies",
        headers={"Authorization": f"Bearer {sup1_token}"},
        json={"name": f"Custom Policy {uuid.uuid4().hex[:4]}", "retain_days": 180, "description": "Custom 6 months"},
    )
    assert new_pol.status_code == 200

    # 2. Attempt disposal while retention is unexpired (retention_until is +365 days) -> 409
    disp_unexp = client.post(
        f"/api/v1/evidence/{item.id}/disposal",
        headers={"Authorization": f"Bearer {sup1_token}"},
        json={"justification": "Trying to dispose unexpired evidence"},
    )
    assert disp_unexp.status_code == 409
    assert disp_unexp.json()["error"]["code"] == "RETENTION_NOT_EXPIRED"

    # 3. Fast-forward retention date so it has expired
    item.retention_until = date.today() - timedelta(days=10)
    db_session.flush()

    # 4. Place Legal Hold on evidence -> verify disposal blocked by hold
    hold_resp = client.post(
        f"/api/v1/evidence/{item.id}/legal-hold",
        headers={"Authorization": f"Bearer {sup1_token}"},
        json={"reason": "Pending grand jury subpoena investigation"},
    )
    assert hold_resp.status_code == 200
    assert hold_resp.json()["legal_hold"] is True

    disp_hold = client.post(
        f"/api/v1/evidence/{item.id}/disposal",
        headers={"Authorization": f"Bearer {sup1_token}"},
        json={"justification": "Trying to dispose evidence on legal hold"},
    )
    assert disp_hold.status_code == 409
    assert disp_hold.json()["error"]["code"] == "DISPOSAL_BLOCKED_BY_HOLD"

    # 5. Request Legal Hold Release (Dual Authorization)
    rel_req = client.post(
        f"/api/v1/legal-hold/release-request?target_type=EVIDENCE&target_id={item.id}",
        headers={"Authorization": f"Bearer {sup1_token}"},
        json={"justification": "Grand jury proceedings concluded without indictment"},
    )
    assert rel_req.status_code == 200
    approval_id = rel_req.json()["id"]

    # Requester cannot approve their own release request
    self_appr = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers={"Authorization": f"Bearer {sup1_token}"},
        json={"decision_note": "Self approval attempt"},
    )
    assert self_appr.status_code == 403
    assert self_appr.json()["error"]["code"] == "DUAL_AUTHORIZATION_VIOLATION"

    # Supervisor 2 approves release
    sup2_appr = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers={"Authorization": f"Bearer {sup2_token}"},
        json={"decision_note": "Approved release of legal hold"},
    )
    assert sup2_appr.status_code == 200

    # Execute release
    retention.execute_legal_hold_release(session=db_session, approval_id=approval_id, actor=sup2)
    assert item.legal_hold is False

    # 6. Now both retention has expired AND hold is cleared -> disposal request succeeds
    disp_req = client.post(
        f"/api/v1/evidence/{item.id}/disposal",
        headers={"Authorization": f"Bearer {sup1_token}"},
        json={"justification": "Retention statutory window passed, case closed and holds released"},
    )
    assert disp_req.status_code == 200
    disp_appr_id = disp_req.json()["id"]

    # Supervisor 2 approves disposal
    disp_appr = client.post(
        f"/api/v1/approvals/{disp_appr_id}/approve",
        headers={"Authorization": f"Bearer {sup2_token}"},
        json={"decision_note": "Approved permanent disposal"},
    )
    assert disp_appr.status_code == 200

    # 7. Execute disposal
    disp_exec = client.post(
        f"/api/v1/retention/disposal/{disp_appr_id}/execute",
        headers={"Authorization": f"Bearer {sup1_token}"},
    )
    assert disp_exec.status_code == 200
    exec_data = disp_exec.json()
    assert exec_data["status"] == EvidenceStatus.DISPOSED.value
    assert exec_data["sha256_tombstone"] == item.sha256

    # 8. Verify metadata survives, storage object is deleted
    assert item.status == EvidenceStatus.DISPOSED
    assert item.disposed_at is not None
    assert item.sha256 is not None  # Permanent tombstone

    # Storage object is gone
    with pytest.raises(Exception):
        storage.get_stream("evidence", item.storage_key)

    # Audit history survives
    audit_entries = db_session.query(audit_chain.AuditLog).filter(audit_chain.AuditLog.evidence_id == item.id).all()
    actions = [a.action for a in audit_entries]
    assert "EVIDENCE_REGISTERED" in actions
    assert "LEGAL_HOLD_PLACED" in actions
    assert "EVIDENCE_DISPOSED" in actions
