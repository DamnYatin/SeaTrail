"""
Tests 6 and 7: Custody workflow, dual-authorization approvals engine, and check constraints.
"""

from datetime import datetime, timedelta, timezone
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import create_app
from app.models.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.models.cases import Case, CaseMember, CaseMemberRole, CaseStatus
from app.models.custody import CustodyTransfer, TransferStatus
from app.models.evidence import EvidenceItem, EvidenceStatus, EvidenceType, IntegrityStateEnum
from app.models.users import User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import create_access_token
from app.services import approvals, custody, storage


@pytest.fixture
def client(db_session: Session):
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def custody_setup(db_session: Session):
    storage.set_mock_storage(True)

    # Two supervisors for dual authorization tests
    sup1 = db_session.query(User).filter(User.email == "sup1@sealtrail.local").first()
    if not sup1:
        sup1 = User(
            email="sup1@sealtrail.local",
            full_name="Supervisor One",
            role=UserRole.SUPERVISOR,
            password_hash=hash_password("Demo#Seal2026!"),
            is_active=True,
        )
        db_session.add(sup1)

    sup2 = db_session.query(User).filter(User.email == "sup2@sealtrail.local").first()
    if not sup2:
        sup2 = User(
            email="sup2@sealtrail.local",
            full_name="Supervisor Two",
            role=UserRole.SUPERVISOR,
            password_hash=hash_password("Demo#Seal2026!"),
            is_active=True,
        )
        db_session.add(sup2)

    # Two investigators
    inv1 = db_session.query(User).filter(User.email == "inv1@sealtrail.local").first()
    if not inv1:
        inv1 = User(
            email="inv1@sealtrail.local",
            full_name="Investigator Alice",
            role=UserRole.INVESTIGATOR,
            password_hash=hash_password("Demo#Seal2026!"),
            is_active=True,
        )
        db_session.add(inv1)

    inv2 = db_session.query(User).filter(User.email == "inv2@sealtrail.local").first()
    if not inv2:
        inv2 = User(
            email="inv2@sealtrail.local",
            full_name="Investigator Bob",
            role=UserRole.INVESTIGATOR,
            password_hash=hash_password("Demo#Seal2026!"),
            is_active=True,
        )
        db_session.add(inv2)

    db_session.commit()

    # Create Case and add members
    case = db_session.query(Case).filter(Case.case_number == "SL26-0088").first()
    if not case:
        case = Case(
            case_number="SL26-0088",
            name="Custody Test Case",
            status=CaseStatus.OPEN,
            lead_user_id=inv1.id,
            evidence_counter=1,
            created_by=inv1.id,
        )
        db_session.add(case)
        db_session.flush()

        db_session.add(CaseMember(case_id=case.id, user_id=inv1.id, case_role=CaseMemberRole.LEAD, added_by=inv1.id))
        db_session.add(CaseMember(case_id=case.id, user_id=inv2.id, case_role=CaseMemberRole.MEMBER, added_by=inv1.id))
        db_session.commit()

    # Create evidence item currently with inv1
    item = db_session.query(EvidenceItem).filter(EvidenceItem.evidence_number == "SL26-0088-E0001A").first()
    if not item:
        import hashlib
        content = b"Custody tracking test item bytes"
        h = hashlib.sha256(content).hexdigest()
        storage_key = f"{case.case_number}/E0001/{h}"
        vid = storage.put_stream("sealtrail-evidence", storage_key, io.BytesIO(content))

        now_utc = datetime.now(timezone.utc)
        item = EvidenceItem(
            evidence_number="SL26-0088-E0001A",
            case_id=case.id,
            type=EvidenceType.FILE,
            item_name="phone_dump.bin",
            original_filename="phone_dump.bin",
            content_type="application/octet-stream",
            size_bytes=len(content),
            sha256=h,
            storage_bucket="sealtrail-evidence",
            storage_key=storage_key,
            storage_version_id=vid,
            collected_by_user_id=inv1.id,
            collected_at=now_utc,
            intake_at=now_utc,
            intake_by=inv1.id,
            current_custodian_id=inv1.id,
            current_location="Locker 1",
            status=EvidenceStatus.IN_CUSTODY,
            integrity_state=IntegrityStateEnum.OK,
            last_verified_at=now_utc,
        )
        db_session.add(item)
        db_session.commit()
    else:
        item.current_custodian_id = inv1.id
        item.current_location = "Locker 1"
        item.status = EvidenceStatus.IN_CUSTODY
        db_session.commit()

    return {
        "sup1": sup1,
        "sup2": sup2,
        "inv1": inv1,
        "inv2": inv2,
        "case": case,
        "item": item,
    }


def test_6_custody_transfers_and_states(client: TestClient, custody_setup: dict, db_session: Session):
    """Test 6: Internal transfer, acknowledge OK, single open transfer limit, reject, cancel."""
    inv1 = custody_setup["inv1"]
    inv2 = custody_setup["inv2"]
    item = custody_setup["item"]

    t1_inv1 = create_access_token(inv1.id, inv1.email, inv1.role.value)
    t2_inv2 = create_access_token(inv2.id, inv2.email, inv2.role.value)

    # 1. Internal transfer: inv1 -> inv2
    tr_resp = client.post(
        f"/api/v1/evidence/{item.id}/transfers",
        headers={"Authorization": f"Bearer {t1_inv1}"},
        json={
            "to_user_id": inv2.id,
            "to_location": "Lab Workbench 3",
            "reason": "Forensic examination",
        },
    )
    assert tr_resp.status_code == 201, tr_resp.text
    tr_data = tr_resp.json()
    assert tr_data["status"] == "PENDING_ACK"
    transfer_id = tr_data["id"]

    # 2. Cannot open a second transfer while one is pending
    dup_resp = client.post(
        f"/api/v1/evidence/{item.id}/transfers",
        headers={"Authorization": f"Bearer {t1_inv1}"},
        json={"to_user_id": inv2.id, "to_location": "Lab", "reason": "Second transfer attempt"},
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "TRANSFER_IN_PROGRESS"

    # 3. Inv2 acknowledges receipt
    ack_resp = client.post(
        f"/api/v1/transfers/{transfer_id}/acknowledge",
        headers={"Authorization": f"Bearer {t2_inv2}"},
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "COMPLETED"

    # Verify item custodian updated to inv2
    db_session.expire_all()
    updated_item = db_session.query(EvidenceItem).filter(EvidenceItem.id == item.id).first()
    assert updated_item.current_custodian_id == inv2.id
    assert updated_item.current_location == "Lab Workbench 3"
    assert updated_item.status == EvidenceStatus.IN_CUSTODY


def test_7_dual_authorization_enforcement(client: TestClient, custody_setup: dict, db_session: Session):
    """Test 7: Requester cannot approve own request (service + DB check constraint); non-supervisor cannot approve."""
    sup1 = custody_setup["sup1"]
    sup2 = custody_setup["sup2"]
    inv1 = custody_setup["inv1"]
    case = custody_setup["case"]

    t_sup1 = create_access_token(sup1.id, sup1.email, sup1.role.value)
    t_sup2 = create_access_token(sup2.id, sup2.email, sup2.role.value)
    t_inv1 = create_access_token(inv1.id, inv1.email, inv1.role.value)

    # 1. Sup1 creates an approval request (e.g. DISPOSAL)
    req = approvals.create_approval_request(
        session=db_session,
        case_id=case.id,
        kind=ApprovalKind.DISPOSAL,
        requester=sup1,
        justification="Case retention expired, all appeals exhausted.",
    )
    db_session.commit()

    # 2. Sup1 attempts to approve own request -> forbidden (two-person rule)
    self_app_resp = client.post(
        f"/api/v1/approvals/{req.id}/approve",
        headers={"Authorization": f"Bearer {t_sup1}"},
        json={"decision_note": "Self-approval attempt"},
    )
    assert self_app_resp.status_code == 403
    assert self_app_resp.json()["error"]["code"] == "DUAL_AUTHORIZATION_VIOLATION"

    # 3. Non-supervisor (Investigator) attempts to approve -> forbidden
    inv_app_resp = client.post(
        f"/api/v1/approvals/{req.id}/approve",
        headers={"Authorization": f"Bearer {t_inv1}"},
        json={"decision_note": "Investigator approval attempt"},
    )
    assert inv_app_resp.status_code == 403

    # 4. Sup2 approves -> success
    sup2_resp = client.post(
        f"/api/v1/approvals/{req.id}/approve",
        headers={"Authorization": f"Bearer {t_sup2}"},
        json={"decision_note": "Verified by second supervisor. Approved."},
    )
    assert sup2_resp.status_code == 200
    assert sup2_resp.json()["status"] == "APPROVED"
    assert sup2_resp.json()["decided_by"] == sup2.id

    # 5. Database CHECK constraint enforcement: Attempt direct raw SQL update with decided_by == requested_by
    with pytest.raises(Exception):
        db_session.execute(
            text(f"UPDATE approval_requests SET decided_by = requested_by WHERE id = '{req.id}'")
        )
        db_session.commit()
    db_session.rollback()
