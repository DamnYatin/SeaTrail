"""
Test 8: RBAC permissions matrix, case isolation, separation of duties, and login lockout.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import create_app
from app.models.audit import AuditLog
from app.models.cases import Case, CaseMember, CaseMemberRole, CaseStatus
from app.models.users import User, UserRole
from app.security.passwords import hash_password
from app.security.permissions import Permission, ROLE_PERMISSIONS, has_permission
from app.security.tokens import create_access_token


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
def seeded_users(db_session: Session):
    users = {}
    roles = [
        UserRole.ADMIN,
        UserRole.SUPERVISOR,
        UserRole.INVESTIGATOR,
        UserRole.CUSTODIAN,
        UserRole.AUDITOR,
    ]
    for r in roles:
        email = f"{r.value.lower()}@sealtrail.local"
        u = db_session.query(User).filter(User.email == email).first()
        if not u:
            u = User(
                email=email,
                full_name=f"User {r.value}",
                role=r,
                password_hash=hash_password("Demo#Seal2026!"),
                is_active=True,
            )
            db_session.add(u)
        else:
            u.failed_login_count = 0
            u.locked_until = None
        users[r] = u
    db_session.commit()
    return users


def test_rbac_matrix_complete():
    """Parametrized verification of Section 6.8 RBAC matrix."""
    # ADMIN checks
    assert has_permission(UserRole.ADMIN, Permission.MANAGE_USERS) is True
    assert has_permission(UserRole.ADMIN, Permission.READ_AUDIT_LOG) is True
    assert has_permission(UserRole.ADMIN, Permission.VIEW_CASE_METADATA) is False
    assert has_permission(UserRole.ADMIN, Permission.CREATE_CASE) is False

    # SUPERVISOR checks
    assert has_permission(UserRole.SUPERVISOR, Permission.CREATE_CASE) is True
    assert has_permission(UserRole.SUPERVISOR, Permission.DECIDE_APPROVALS) is True
    assert has_permission(UserRole.SUPERVISOR, Permission.PLACE_LEGAL_HOLD) is True
    assert has_permission(UserRole.SUPERVISOR, Permission.MANAGE_USERS) is False

    # INVESTIGATOR checks
    assert has_permission(UserRole.INVESTIGATOR, Permission.CREATE_CASE) is True
    assert has_permission(UserRole.INVESTIGATOR, Permission.REGISTER_EVIDENCE) is True
    assert has_permission(UserRole.INVESTIGATOR, Permission.DECIDE_APPROVALS) is False
    assert has_permission(UserRole.INVESTIGATOR, Permission.READ_AUDIT_LOG) is False

    # CUSTODIAN checks
    assert has_permission(UserRole.CUSTODIAN, Permission.REGISTER_EVIDENCE) is True
    assert has_permission(UserRole.CUSTODIAN, Permission.INITIATE_TRANSFER) is True
    assert has_permission(UserRole.CUSTODIAN, Permission.CREATE_CASE) is False
    assert has_permission(UserRole.CUSTODIAN, Permission.DECIDE_APPROVALS) is False

    # AUDITOR checks
    assert has_permission(UserRole.AUDITOR, Permission.VIEW_CASE_METADATA) is True
    assert has_permission(UserRole.AUDITOR, Permission.READ_AUDIT_LOG) is True
    assert has_permission(UserRole.AUDITOR, Permission.REGISTER_EVIDENCE) is False
    assert has_permission(UserRole.AUDITOR, Permission.DOWNLOAD_WORKING_COPY) is False


def test_admin_cannot_access_cases(client: TestClient, seeded_users: dict, db_session: Session):
    """Verify ADMIN gets 403 on cases and evidence (separation of duties)."""
    admin = seeded_users[UserRole.ADMIN]
    token = create_access_token(admin.id, admin.email, admin.role.value)

    resp = client.get("/api/v1/cases", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    # Check that ACCESS_DENIED was audited
    denied_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "ACCESS_DENIED", AuditLog.actor_id == admin.id)
        .first()
    )
    assert denied_audit is not None


def test_case_isolation_non_member(client: TestClient, seeded_users: dict, db_session: Session):
    """Verify non-member investigator gets 403 and an ACCESS_DENIED audit entry."""
    supervisor = seeded_users[UserRole.SUPERVISOR]
    sup_token = create_access_token(supervisor.id, supervisor.email, supervisor.role.value)

    # Supervisor creates a case
    create_resp = client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {sup_token}"},
        json={"name": "Restricted Case", "classification": "RESTRICTED"},
    )
    assert create_resp.status_code == 201
    case_id = create_resp.json()["id"]

    # Other investigator (non-member) tries to view it
    inv = seeded_users[UserRole.INVESTIGATOR]
    inv_token = create_access_token(inv.id, inv.email, inv.role.value)

    resp = client.get(f"/api/v1/cases/{case_id}", headers={"Authorization": f"Bearer {inv_token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    # Verify ACCESS_DENIED was audited
    denied = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "ACCESS_DENIED",
            AuditLog.actor_id == inv.id,
            AuditLog.case_id == case_id,
        )
        .first()
    )
    assert denied is not None


def test_login_lockout_and_auditing(client: TestClient, seeded_users: dict, db_session: Session):
    """Verify account lockout occurs after 5 failed attempts and audits ACCOUNT_LOCKED."""
    inv = seeded_users[UserRole.INVESTIGATOR]

    # Attempt 5 incorrect logins
    for i in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": inv.email, "password": "WrongPassword123!"},
        )
        if i < 4:
            assert resp.status_code == 401
        else:
            assert resp.status_code == 429
            assert resp.json()["error"]["code"] == "ACCOUNT_LOCKED"

    # Verify ACCOUNT_LOCKED audit entry
    locked_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "ACCOUNT_LOCKED", AuditLog.actor_id == inv.id)
        .first()
    )
    assert locked_audit is not None
