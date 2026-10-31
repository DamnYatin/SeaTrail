"""
Evidence identification and Crockford base32 check character verification.
"""

import re
from typing import Tuple

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def compute_check_char(base_id: str) -> str:
    """Compute Crockford base32 check character for a base ID."""
    total = sum(ord(ch) * (i + 1) for i, ch in enumerate(base_id))
    return CROCKFORD_ALPHABET[total % 32]


def format_evidence_number(case_number: str, counter: int) -> str:
    """Format full evidence number: {case_number}-E{n:04d}{check_char}."""
    base_id = f"{case_number}-E{counter:04d}"
    check = compute_check_char(base_id)
    return f"{base_id}{check}"


def validate_evidence_number(evidence_number: str) -> bool:
    """Validate check character on an evidence number."""
    cleaned = evidence_number.strip().upper()
    # Expect format like SL26-0001-E0001C
    pattern = r"^[A-Z0-9]+-\d+-E\d{4}[0-9A-HJKMNP-Z]$"
    if not re.match(pattern, cleaned):
        return False

    base_id = cleaned[:-1]
    expected_check = compute_check_char(base_id)
    actual_check = cleaned[-1]
    return expected_check == actual_check
