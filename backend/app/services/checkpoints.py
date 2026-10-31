"""
Cryptographic checkpoints service using Ed25519 digital signatures.
Binds head sequence and hash into signed verifiable checkpoints.
"""

import base64
import hashlib
from datetime import UTC, datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.logging import logger
from app.models.audit import AuditCheckpoint, AuditLog


def get_signing_key() -> ed25519.Ed25519PrivateKey:
    raw_bytes = base64.b64decode(settings.CHECKPOINT_SIGNING_KEY_B64)
    return ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)


def get_public_key() -> ed25519.Ed25519PublicKey:
    raw_bytes = base64.b64decode(settings.CHECKPOINT_PUBLIC_KEY_B64)
    return ed25519.Ed25519PublicKey.from_public_bytes(raw_bytes)


def get_public_key_id() -> str:
    raw_bytes = base64.b64decode(settings.CHECKPOINT_PUBLIC_KEY_B64)
    return hashlib.sha256(raw_bytes).hexdigest()[:16]


def format_checkpoint_message(seq_to: int, head_hash: str, created_at_iso: str) -> bytes:
    msg = f"sealtrail-checkpoint-v1|{seq_to}|{head_hash}|{created_at_iso}"
    return msg.encode("utf-8")


def create_checkpoint(session: Session, created_by: str | None = None) -> AuditCheckpoint | None:
    """
    Produce an Ed25519 signed checkpoint over the current chain head.
    """
    last_entry = session.query(AuditLog).order_by(desc(AuditLog.seq)).first()
    if not last_entry:
        return None

    now_dt = datetime.now(UTC)
    created_at_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    msg_bytes = format_checkpoint_message(last_entry.seq, last_entry.entry_hash, created_at_iso)
    signing_key = get_signing_key()
    signature = signing_key.sign(msg_bytes)
    sig_b64 = base64.b64encode(signature).decode("ascii")

    cp = AuditCheckpoint(
        seq_to=last_entry.seq,
        head_hash=last_entry.entry_hash,
        signature_b64=sig_b64,
        public_key_id=get_public_key_id(),
        created_at=now_dt,
        created_by=created_by,
    )
    session.add(cp)
    session.flush()
    return cp


def verify_checkpoint(cp: AuditCheckpoint, expected_head_hash: str) -> bool:
    """
    Verify signature of an AuditCheckpoint.
    """
    if cp.head_hash != expected_head_hash:
        return False

    created_at_iso = cp.created_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    msg_bytes = format_checkpoint_message(cp.seq_to, cp.head_hash, created_at_iso)

    try:
        sig_bytes = base64.b64decode(cp.signature_b64)
        public_key = get_public_key()
        public_key.verify(sig_bytes, msg_bytes)
        return True
    except (InvalidSignature, ValueError, Exception) as e:
        logger.warning(
            "checkpoint_signature_verification_failed", checkpoint_id=cp.id, error=str(e)
        )
        return False
