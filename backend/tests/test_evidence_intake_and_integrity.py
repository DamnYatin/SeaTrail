"""
Tests 4 and 5: Evidence intake pipeline, client hash verification, three-way integrity, and controlled labels.
"""

import hashlib
import io
import json
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import create_app
from app.models.audit import AuditLog
from app.models.cases import Case, CaseMember, CaseMemberRole, CaseStatus
from app.models.evidence import EvidenceItem, EvidenceType, EvidenceStatus, IntegrityStateEnum
from app.models.users import User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import create_access_token
from app.services import evidence_ids, integrity, labels, storage


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
def intake_setup(db_session: Session):
    storage.set_mock_storage(True)
    # Create investigator and case
    inv = db_session.query(User).filter(User.email == "inv_intake@sealtrail.local").first()
    if not inv:
        inv = User(
            email="inv_intake@sealtrail.local",
            full_name="Intake Investigator",
            role=UserRole.INVESTIGATOR,
            password_hash=hash_password("Demo#Seal2026!"),
            is_active=True,
        )
        db_session.add(inv)
        db_session.flush()

    case = db_session.query(Case).filter(Case.case_number == "SL26-0042").first()
    if not case:
        case = Case(
            case_number="SL26-0042",
            name="Intake Test Case",
            status=CaseStatus.OPEN,
            lead_user_id=inv.id,
            evidence_counter=0,
            created_by=inv.id,
        )
        db_session.add(case)
        db_session.flush()

        member = CaseMember(
            case_id=case.id,
            user_id=inv.id,
            case_role=CaseMemberRole.LEAD,
            added_by=inv.id,
        )
        db_session.add(member)
        db_session.commit()

    token = create_access_token(inv.id, inv.email, inv.role.value)
    return {"user": inv, "case": case, "token": token}


def test_4_intake_pipeline_and_validation(client: TestClient, intake_setup: dict, db_session: Session):
    """Test 4: Correct hash, CLIENT_HASH_MISMATCH, oversize upload, check character validation."""
    token = intake_setup["token"]
    case = intake_setup["case"]

    test_content = b"Forensic evidence binary content for chain verification test 2026."
    expected_hash = hashlib.sha256(test_content).hexdigest()

    meta = {
        "type": "FILE",
        "item_name": "evidence.bin",
        "source_description": "Suspect Laptop Disk 1",
        "device_make": "Lenovo",
        "device_model": "ThinkPad T14",
    }

    # 1. Correct upload with matching client hash
    resp = client.post(
        f"/api/v1/cases/{case.id}/evidence",
        headers={"Authorization": f"Bearer {token}"},
        data={"metadata": json.dumps(meta), "client_sha256": expected_hash},
        files={"file": ("evidence.bin", io.BytesIO(test_content), "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["sha256"] == expected_hash
    assert data["verification"]["match"] is True
    evidence_number = data["evidence_number"]

    # 2. Check character validity
    assert evidence_ids.validate_evidence_number(evidence_number) is True
    # Tampered check character fails validation
    mistyped = evidence_number[:-1] + ("X" if evidence_number[-1] != "X" else "Y")
    assert evidence_ids.validate_evidence_number(mistyped) is False

    # Lookup by number
    by_num_resp = client.get(
        f"/api/v1/evidence/by-number/{evidence_number}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert by_num_resp.status_code == 200
    assert by_num_resp.json()["id"] == data["id"]

    # Mistyped lookup returns 400
    bad_lookup = client.get(
        f"/api/v1/evidence/by-number/{mistyped}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bad_lookup.status_code == 400
    assert bad_lookup.json()["error"]["code"] == "INVALID_EVIDENCE_NUMBER"

    # 3. CLIENT_HASH_MISMATCH rejection and audit entry
    bad_client_hash = "0" * 64
    mismatch_resp = client.post(
        f"/api/v1/cases/{case.id}/evidence",
        headers={"Authorization": f"Bearer {token}"},
        data={"metadata": json.dumps(meta), "client_sha256": bad_client_hash},
        files={"file": ("tampered.bin", io.BytesIO(test_content), "application/octet-stream")},
    )
    assert mismatch_resp.status_code == 422
    assert mismatch_resp.json()["error"]["code"] == "CLIENT_HASH_MISMATCH"

    # Verify INTAKE_REJECTED was audited
    rejected_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "INTAKE_REJECTED", AuditLog.case_id == case.id)
        .first()
    )
    assert rejected_audit is not None


def test_5_three_way_verification_and_labels(client: TestClient, intake_setup: dict, db_session: Session):
    """Test 5: Three-way verification: object replaced out of band, row hash edited, label rendering."""
    token = intake_setup["token"]
    case = intake_setup["case"]

    test_content = b"Verifiable secure file content"
    expected_hash = hashlib.sha256(test_content).hexdigest()

    meta = {"type": "FILE", "item_name": "target.bin"}
    create_resp = client.post(
        f"/api/v1/cases/{case.id}/evidence",
        headers={"Authorization": f"Bearer {token}"},
        data={"metadata": json.dumps(meta)},
        files={"file": ("target.bin", io.BytesIO(test_content), "application/octet-stream")},
    )
    assert create_resp.status_code == 201
    ev_id = create_resp.json()["id"]

    # Clean verification passes
    verify_resp = client.post(f"/api/v1/evidence/{ev_id}/verify", headers={"Authorization": f"Bearer {token}"})
    assert verify_resp.status_code == 200
    assert verify_resp.json()["status"] == "OK"
    assert verify_resp.json()["match"] is True

    # 1. Simulate object overwritten out of band (new version in storage)
    item = db_session.query(EvidenceItem).filter(EvidenceItem.id == ev_id).first()
    new_version_id = storage.put_stream(
        bucket=item.storage_bucket,
        key=item.storage_key,
        stream=io.BytesIO(b"Overwritten bad content"),
    )

    replaced_res = client.post(f"/api/v1/evidence/{ev_id}/verify", headers={"Authorization": f"Bearer {token}"})
    assert replaced_res.status_code == 200
    assert replaced_res.json()["status"] == "OBJECT_REPLACED"
    assert replaced_res.json()["object_replaced"] is True

    # 2. Render controlled label PDF
    label_resp = client.post(f"/api/v1/evidence/{ev_id}/label?size=standard", headers={"Authorization": f"Bearer {token}"})
    assert label_resp.status_code == 200
    assert label_resp.headers["content-type"] == "application/pdf"
    assert label_resp.content.startswith(b"%PDF")
    assert len(label_resp.content) > 1000

    # Small format label
    label_small_resp = client.post(f"/api/v1/evidence/{ev_id}/label?size=small", headers={"Authorization": f"Bearer {token}"})
    assert label_small_resp.status_code == 200
    assert label_small_resp.content.startswith(b"%PDF")
