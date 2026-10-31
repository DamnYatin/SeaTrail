"""
Argon2id password hashing and validation against system security policy.
"""

import re

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import settings

_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash."""
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def validate_password_complexity(password: str) -> bool:
    """
    Validate password meets minimum length and complexity:
    at least PASSWORD_MIN_LENGTH, at least one letter and one digit.
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return False
    has_letter = bool(re.search(r"[A-Za-z]", password))
    has_digit = bool(re.search(r"\d", password))
    return has_letter and has_digit
