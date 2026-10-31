"""
Single source of truth for Role-Based Access Control (RBAC) permissions matrix.
Defines Permission enum, Role enum, and the exact matrix specified in AGENTS.md Section 6.8.
"""

import enum

from app.models.users import UserRole


class Permission(str, enum.Enum):
    MANAGE_USERS = "MANAGE_USERS"
    CREATE_CASE = "CREATE_CASE"
    MANAGE_CASE_MEMBERS = "MANAGE_CASE_MEMBERS"
    VIEW_CASE_METADATA = "VIEW_CASE_METADATA"
    REGISTER_EVIDENCE = "REGISTER_EVIDENCE"
    VERIFY_HASH = "VERIFY_HASH"
    DOWNLOAD_WORKING_COPY = "DOWNLOAD_WORKING_COPY"
    INITIATE_TRANSFER = "INITIATE_TRANSFER"
    ACKNOWLEDGE_RECEIPT = "ACKNOWLEDGE_RECEIPT"
    COLLABORATE = "COLLABORATE"
    DECIDE_APPROVALS = "DECIDE_APPROVALS"
    PLACE_LEGAL_HOLD = "PLACE_LEGAL_HOLD"
    REQUEST_EXPORT = "REQUEST_EXPORT"
    REQUEST_HOLD_RELEASE = "REQUEST_HOLD_RELEASE"
    REQUEST_DISPOSAL = "REQUEST_DISPOSAL"
    READ_AUDIT_LOG = "READ_AUDIT_LOG"
    VERIFY_CHAIN = "VERIFY_CHAIN"
    READ_ALERTS = "READ_ALERTS"
    ACKNOWLEDGE_ALERTS = "ACKNOWLEDGE_ALERTS"
    RESOLVE_ALERTS = "RESOLVE_ALERTS"


# Matrix mapping roles to their allowed permissions
# Note: Membership and dynamic attributes (lead only, current custodian, etc.)
# are checked at enforcement time in dependencies/services.
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.ADMIN: {
        Permission.MANAGE_USERS,
        Permission.READ_AUDIT_LOG,
        Permission.VERIFY_CHAIN,
    },
    UserRole.SUPERVISOR: {
        Permission.CREATE_CASE,
        Permission.MANAGE_CASE_MEMBERS,
        Permission.VIEW_CASE_METADATA,
        Permission.VERIFY_HASH,
        Permission.DOWNLOAD_WORKING_COPY,
        Permission.DECIDE_APPROVALS,
        Permission.PLACE_LEGAL_HOLD,
        Permission.REQUEST_EXPORT,
        Permission.REQUEST_HOLD_RELEASE,
        Permission.REQUEST_DISPOSAL,
        Permission.READ_AUDIT_LOG,
        Permission.VERIFY_CHAIN,
        Permission.READ_ALERTS,
        Permission.ACKNOWLEDGE_ALERTS,
        Permission.RESOLVE_ALERTS,
        Permission.COLLABORATE,
    },
    UserRole.INVESTIGATOR: {
        Permission.CREATE_CASE,
        Permission.MANAGE_CASE_MEMBERS,  # Lead only
        Permission.VIEW_CASE_METADATA,  # Member only
        Permission.REGISTER_EVIDENCE,  # Member only
        Permission.VERIFY_HASH,  # Member only
        Permission.DOWNLOAD_WORKING_COPY,  # Member only
        Permission.INITIATE_TRANSFER,  # Current custodian
        Permission.ACKNOWLEDGE_RECEIPT,  # Designated receiver
        Permission.COLLABORATE,  # Member only
        Permission.REQUEST_EXPORT,  # Member only
    },
    UserRole.CUSTODIAN: {
        Permission.VIEW_CASE_METADATA,  # Member only
        Permission.REGISTER_EVIDENCE,  # Member only
        Permission.VERIFY_HASH,  # Member only
        Permission.DOWNLOAD_WORKING_COPY,  # Member only
        Permission.INITIATE_TRANSFER,  # Current custodian
        Permission.ACKNOWLEDGE_RECEIPT,  # Designated receiver
        Permission.COLLABORATE,  # Member only
    },
    UserRole.AUDITOR: {
        Permission.VIEW_CASE_METADATA,  # Read all cases/evidence metadata
        Permission.VERIFY_HASH,  # Verify hashes
        Permission.READ_AUDIT_LOG,
        Permission.VERIFY_CHAIN,
        Permission.READ_ALERTS,
        Permission.ACKNOWLEDGE_ALERTS,
    },
}


def has_permission(role: UserRole, permission: Permission) -> bool:
    """Check if a role possesses the specified permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())
