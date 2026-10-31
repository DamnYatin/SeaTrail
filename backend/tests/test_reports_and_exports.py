"""
Tests 10 and 11: Cryptographically signed custody reports, report verification,
statutory Section 63 BSA certificate, and export package with standalone offline verify.py.
"""

import copy
import hashlib
import io
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime

import pytest
import pyzipper
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import create_app
from app.models.cases import Case, CaseClassification, CaseMember, CaseMemberRole, CaseStatus
from app.models.evidence import EvidenceItem, EvidenceType, IntegrityStateEnum
from app.models.users import User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import create_access_token
from app.services import audit_chain, bsa_certificate, storage


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
def reports_setup(db_session: Session):
    storage.set_mock_storage(True)
    uid = uuid.uuid4().hex[:6]

    sup1 = User(
        email=f"sup1_{uid}@example.com",
        full_name="Supervisor One",
        role=UserRole.SUPERVISOR,
        password_hash=hash_password("Password123!"),
    )
    sup2 = User(
        email=f"sup2_{uid}@example.com",
        full_name="Supervisor Two",
        role=UserRole.SUPERVISOR,
        password_hash=hash_password("Password123!"),
    )
    inv = User(
        email=f"inv_rep_{uid}@example.com",
        full_name="Investigator Rep",
        role=UserRole.INVESTIGATOR,
        password_hash=hash_password("Password123!"),
    )
    db_session.add_all([sup1, sup2, inv])
    db_session.flush()

    case = Case(
        case_number=f"CASE-REP-{uid}",
        name="Reports Test Case",
        status=CaseStatus.OPEN,
        classification=CaseClassification.INTERNAL,
        lead_user_id=inv.id,
        created_by=sup1.id,
    )
    db_session.add(case)
    db_session.flush()

    db_session.add_all(
        [
            CaseMember(
                case_id=case.id, user_id=sup1.id, case_role=CaseMemberRole.MEMBER, added_by=sup1.id
            ),
            CaseMember(
                case_id=case.id, user_id=sup2.id, case_role=CaseMemberRole.MEMBER, added_by=sup1.id
            ),
            CaseMember(
                case_id=case.id, user_id=inv.id, case_role=CaseMemberRole.LEAD, added_by=sup1.id
            ),
        ]
    )
    db_session.flush()

    content = b"Evidence test payload for reports and exports"
    content_hash = hashlib.sha256(content).hexdigest()
    key = f"cases/{uid}/payload.bin"
    ver_id = storage.put_stream("evidence", key, io.BytesIO(content))

    item = EvidenceItem(
        evidence_number=f"SEAL-REP-{uid}-A",
        case_id=case.id,
        type=EvidenceType.FILE,
        item_name="ReportEvidenceFile",
        description="Test evidence for custody reports",
        collected_by_user_id=inv.id,
        collected_at=datetime.now(UTC),
        original_filename="payload.bin",
        content_type="application/octet-stream",
        size_bytes=len(content),
        sha256=content_hash,
        storage_bucket="evidence",
        storage_key=key,
        storage_version_id=ver_id,
        intake_by=inv.id,
        current_custodian_id=inv.id,
        current_location="Secure Room 1",
        integrity_state=IntegrityStateEnum.OK,
    )
    db_session.add(item)
    db_session.flush()

    audit_chain.ensure_genesis_entry(db_session)
    audit_chain.append(
        session=db_session,
        actor=inv,
        action=audit_chain.AuditAction.EVIDENCE_REGISTERED,
        case_id=case.id,
        evidence_id=item.id,
        payload={"sha256": content_hash, "item_name": item.item_name},
    )

    return {"sup1": sup1, "sup2": sup2, "inv": inv, "case": case, "item": item, "content": content}


def test_10_custody_report_and_verification(client: TestClient, db_session: Session, reports_setup):
    """
    Test 10: Custody report generation, signature validation, tamper detection via POST /reports/verify,
    and statutory Section 63 BSA certificate generation.
    """
    sup1 = reports_setup["sup1"]
    item = reports_setup["item"]
    token = create_access_token(sup1.id, sup1.email, sup1.role.value)

    # 1. GET JSON report
    resp = client.get(
        f"/api/v1/evidence/{item.id}/custody-report?format=json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    report_json = resp.json()

    assert "report_data" in report_json
    assert "report_sha256" in report_json
    assert "signature_b64" in report_json
    assert report_json["report_data"]["evidence"]["sha256"] == item.sha256

    # 2. POST /reports/verify with untampered report -> valid
    verify_resp = client.post("/api/v1/reports/verify", json={"report": report_json})
    assert verify_resp.status_code == 200
    v_data = verify_resp.json()
    assert v_data["valid"] is True
    assert v_data["signature_valid"] is True
    assert v_data["report_hash_valid"] is True
    assert v_data["audit_entries_match"] is True

    # 3. Tamper with an audit entry in the report
    tampered_report = copy.deepcopy(report_json)
    if tampered_report["report_data"]["audit_trail"]:
        tampered_report["report_data"]["audit_trail"][0]["action"] = "UNAUTHORIZED_TAMPER"

    verify_tampered = client.post("/api/v1/reports/verify", json={"report": tampered_report})
    assert verify_tampered.status_code == 200
    assert verify_tampered.json()["valid"] is False

    # 4. GET PDF report
    resp_pdf = client.get(
        f"/api/v1/evidence/{item.id}/custody-report?format=pdf",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert resp_pdf.content.startswith(b"%PDF")

    # 5. Section 63 BSA Certificate PDF
    bsa_pdf = bsa_certificate.generate_bsa_certificate_pdf(
        session=db_session, evidence=item, actor=sup1
    )
    assert bsa_pdf.startswith(b"%PDF")
    assert len(bsa_pdf) > 1000


def test_11_export_package_and_offline_verifier(
    client: TestClient, db_session: Session, reports_setup
):
    """
    Test 11: Export package build, embedded verify.py execution via subprocess -> exit 0,
    tampered file inside -> verify.py exits non-zero, and encrypted ZIP protection.
    """
    sup1 = reports_setup["sup1"]
    sup2 = reports_setup["sup2"]
    item = reports_setup["item"]
    sup1_token = create_access_token(sup1.id, sup1.email, sup1.role.value)
    sup2_token = create_access_token(sup2.id, sup2.email, sup2.role.value)

    # 1. Request export (Supervisor 1)
    req_resp = client.post(
        f"/api/v1/evidence/{item.id}/exports",
        headers={"Authorization": f"Bearer {sup1_token}"},
        json={
            "justification": "Required for statutory forensic submission to court",
            "include_bsa_certificate": True,
            "encrypt": False,
        },
    )
    assert req_resp.status_code == 200
    approval_id = req_resp.json()["id"]

    # 2. Dual Authorization: Supervisor 2 approves
    appr_resp = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers={"Authorization": f"Bearer {sup2_token}"},
        json={"decision_note": "Approved for forensic submission"},
    )
    assert appr_resp.status_code == 200

    # 3. Build export package
    build_resp = client.post(
        f"/api/v1/exports/{approval_id}/build",
        headers={"Authorization": f"Bearer {sup1_token}"},
        json={},
    )
    assert build_resp.status_code == 200
    export_info = build_resp.json()
    export_id = export_info["id"]

    # 4. Download export package
    dl_resp = client.get(
        f"/api/v1/exports/{export_id}/download", headers={"Authorization": f"Bearer {sup1_token}"}
    )
    assert dl_resp.status_code == 200
    zip_bytes = dl_resp.content

    # 5. Extract ZIP to temporary directory and run verify.py
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = f"{tmpdir}/export.zip"
        with open(zip_path, "wb") as f:
            f.write(zip_bytes)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)

        # Run verify.py inside tmpdir
        result = subprocess.run(
            [sys.executable, f"{tmpdir}/verify.py"],
            capture_output=True,
            text=True,
            cwd=tmpdir,
        )
        assert (
            result.returncode == 0
        ), f"Verifier failed with output: {result.stdout}\n{result.stderr}"
        assert "ALL VERIFICATIONS PASSED" in result.stdout

        # 6. Tamper with a file inside package and confirm verify.py fails
        with open(f"{tmpdir}/manifest.json", "a") as f:
            f.write(" ")

        tamper_result = subprocess.run(
            [sys.executable, f"{tmpdir}/verify.py"],
            capture_output=True,
            text=True,
            cwd=tmpdir,
        )
        assert tamper_result.returncode != 0

    # 7. Test encrypted export package with pyzipper
    passphrase = "SecretExportPass123!"
    req2_resp = client.post(
        f"/api/v1/evidence/{item.id}/exports",
        headers={"Authorization": f"Bearer {sup1_token}"},
        json={
            "justification": "Second export requiring AES-256 encryption",
            "include_bsa_certificate": True,
            "encrypt": True,
        },
    )
    approval2_id = req2_resp.json()["id"]

    client.post(
        f"/api/v1/approvals/{approval2_id}/approve",
        headers={"Authorization": f"Bearer {sup2_token}"},
        json={"decision_note": "Approved encrypted export"},
    )

    build2_resp = client.post(
        f"/api/v1/exports/{approval2_id}/build",
        headers={"Authorization": f"Bearer {sup1_token}"},
        json={"passphrase": passphrase},
    )
    assert build2_resp.status_code == 200

    enc_dl_resp = client.get(
        f"/api/v1/exports/{build2_resp.json()['id']}/download",
        headers={"Authorization": f"Bearer {sup1_token}"},
    )
    assert enc_dl_resp.status_code == 200

    # Confirm pyzipper opens it only with passphrase
    enc_buf = io.BytesIO(enc_dl_resp.content)
    with pyzipper.AESZipFile(enc_buf) as zf:
        # Without password, reading fails
        with pytest.raises(Exception):
            zf.read("README.txt")

        # With correct password, reading succeeds
        zf.setpassword(passphrase.encode("utf-8"))
        readme = zf.read("README.txt")
        assert b"SEALTRAIL DIGITAL EVIDENCE EXPORT PACKAGE" in readme
