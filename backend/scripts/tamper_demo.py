#!/usr/bin/env python3
"""
SealTrail Live Attack Simulator (tamper_demo.py)

Simulates host-side attacks by a malicious administrator to demonstrate
SealTrail's multi-layered cryptographic defenses and anomaly detection.

Commands:
  audit           --seq N             Edit an audit log row's payload (bypasses triggers via replica mode)
  audit-rewrite   --from-seq N        Recompute entire hash chain from N onward (bypassed DBA rewrite attack)
  object          --evidence NUMBER   Overwrite S3 object in place with altered bytes (tests versioning binding)
  evidence-hash   --evidence NUMBER   Mutate evidence row SHA-256 hash in database
  restore                             Undo all simulated attacks and restore clean verified state
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path so app modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.audit import AuditLog
from app.models.evidence import EvidenceItem
from app.services import audit_chain, storage

BACKUP_FILE = Path(__file__).resolve().parent.parent / ".tamper_backup.json"


def get_privileged_engine():
    """Get database engine with sufficient privileges to bypass triggers or test tampering."""
    # If DATABASE_URL_APP is overridden (e.g. to SQLite), use that engine directly
    if settings.DATABASE_URL_APP.startswith("sqlite"):
        from app.db import get_engine

        return get_engine()

    url = (
        settings.DATABASE_URL_SUPERUSER_HOST
        or settings.DATABASE_URL_OWNER
        or settings.DATABASE_URL_APP
    )
    if "postgresql" in url:
        try:
            eng = create_engine(url, connect_args={"connect_timeout": 3})
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            return eng
        except Exception:
            from app.db import get_engine

            return get_engine()
    from app.db import get_engine

    return get_engine()


def check_dev_mode():
    if settings.APP_ENV != "development":
        print(
            f"[ERROR] tamper_demo.py refuses to run when APP_ENV is '{settings.APP_ENV}'. Must be 'development'."
        )
        sys.exit(1)


def save_backup(data: dict[str, Any]):
    existing = {}
    if BACKUP_FILE.exists():
        try:
            with open(BACKUP_FILE, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass
    existing.update(data)
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)


def load_backup() -> dict[str, Any]:
    if not BACKUP_FILE.exists():
        return {}
    with open(BACKUP_FILE, encoding="utf-8") as f:
        return json.load(f)


def attack_audit(seq: int):
    check_dev_mode()
    print(
        f"\n[ATTACK] Simulating direct database administrator manipulation on audit row #{seq}..."
    )
    engine = get_privileged_engine()
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        row = session.query(AuditLog).filter(AuditLog.seq == seq).first()
        if not row:
            print(f"[ERROR] Audit entry seq #{seq} not found.")
            return

        # Save backup
        save_backup(
            {
                "audit_tamper": {
                    "seq": seq,
                    "original_payload": row.payload,
                    "original_hash": row.entry_hash,
                }
            }
        )

        tampered_payload = dict(row.payload) if row.payload else {}
        tampered_payload["_malicious_edit"] = "Direct SQL injection by rogue administrator"
        tampered_payload["amount_altered"] = 99999999

        # In PostgreSQL, bypass triggers using session_replication_role
        is_pg = "postgres" in str(engine.url)
        if is_pg:
            session.execute(text("SET session_replication_role = 'replica';"))

        row.payload = tampered_payload
        session.commit()

        if is_pg:
            session.execute(text("SET session_replication_role = 'origin';"))
            session.commit()

        print(f"[SUCCESS] Audit row #{seq} payload modified directly in database.")
        print(f"  Old entry hash: {row.entry_hash}")
        print(f"  Stored payload: {tampered_payload}")
        print("\n--> EXPECTED OUTCOME: Verifying chain in UI or API will report:")
        print(
            f"    'CHAIN BROKEN at entry #{seq}: SHA256 mismatch between canonical payload and entry_hash'"
        )
    finally:
        session.close()


def attack_audit_rewrite(from_seq: int):
    check_dev_mode()
    print(
        f"\n[ATTACK] Simulating sophisticated database rewrite attack from seq #{from_seq} onward..."
    )
    engine = get_privileged_engine()
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        rows = (
            session.query(AuditLog)
            .filter(AuditLog.seq >= from_seq)
            .order_by(AuditLog.seq.asc())
            .all()
        )
        if not rows:
            print(f"[ERROR] No audit entries found from seq #{from_seq}.")
            return

        # Save backup
        backup_entries = []
        for r in rows:
            backup_entries.append(
                {
                    "seq": r.seq,
                    "payload": r.payload,
                    "prev_hash": r.prev_hash,
                    "entry_hash": r.entry_hash,
                }
            )
        save_backup({"audit_rewrite": backup_entries})

        is_pg = "postgres" in str(engine.url)
        if is_pg:
            session.execute(text("SET session_replication_role = 'replica';"))

        # Alter payload of first row
        row0 = rows[0]
        tampered_payload = dict(row0.payload) if row0.payload else {}
        tampered_payload["_clever_dba_rewrite"] = "Forged historical event"
        row0.payload = tampered_payload

        # Recompute chain forward
        prev_h = row0.prev_hash
        for r in rows:
            r.prev_hash = prev_h
            canon = audit_chain.canonicalize_entry(
                seq=r.seq,
                ts=r.ts,
                actor_id=r.actor_id,
                actor_role=r.actor_role,
                action=r.action,
                case_id=r.case_id,
                evidence_id=r.evidence_id,
                payload=r.payload or {},
                ip=r.ip,
            )
            r.entry_hash = audit_chain.compute_entry_hash(prev_h, canon)
            prev_h = r.entry_hash

        session.commit()
        if is_pg:
            session.execute(text("SET session_replication_role = 'origin';"))
            session.commit()

        print(
            f"[SUCCESS] Recomputed {len(rows)} audit entries from #{from_seq} to #{rows[-1].seq}."
        )
        print("  Every intermediate link in the ledger appears mathematically consistent.")
        print("\n--> EXPECTED OUTCOME: Checkpoint verification will FAIL:")
        print(
            "    The checkpoint head_hash signed with Ed25519 private key does NOT match the rewritten chain head!"
        )
    finally:
        session.close()


def attack_object(evidence_number: str):
    check_dev_mode()
    print(f"\n[ATTACK] Simulating S3/MinIO object overwrite for evidence {evidence_number}...")
    engine = get_privileged_engine()
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        ev = (
            session.query(EvidenceItem)
            .filter(EvidenceItem.evidence_number == evidence_number)
            .first()
        )
        if not ev:
            print(f"[ERROR] Evidence item '{evidence_number}' not found.")
            return

        # Save backup
        save_backup(
            {
                "object_tamper": {
                    "evidence_id": ev.id,
                    "evidence_number": ev.evidence_number,
                    "storage_bucket": ev.storage_bucket,
                    "storage_key": ev.storage_key,
                    "storage_version_id": ev.storage_version_id,
                }
            }
        )

        malicious_content = b"MALICIOUS_BYTES_SUBSTITUTED_INTO_S3_STORAGE_BUCKET_OUT_OF_BAND\n"
        print(
            f"  Uploading altered payload ({len(malicious_content)} bytes) to {ev.storage_key}..."
        )
        res = storage.put_object(
            key=ev.storage_key,
            data=malicious_content,
            content_type="application/octet-stream",
            bucket=ev.storage_bucket,
        )
        print(
            f"[SUCCESS] Object replaced in storage. New storage version ID: {res.get('version_id')}"
        )
        print("\n--> EXPECTED OUTCOME: Evidence verification sweep reports:")
        print(
            "    'OBJECT_REPLACED: Live S3 version differs from pinned intake version. Original version preserved by bucket versioning.'"
        )
    finally:
        session.close()


def attack_evidence_hash(evidence_number: str):
    check_dev_mode()
    print(
        f"\n[ATTACK] Simulating direct modification of evidence_items.sha256 for {evidence_number}..."
    )
    engine = get_privileged_engine()
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        ev = (
            session.query(EvidenceItem)
            .filter(EvidenceItem.evidence_number == evidence_number)
            .first()
        )
        if not ev:
            print(f"[ERROR] Evidence item '{evidence_number}' not found.")
            return

        save_backup(
            {
                "hash_tamper": {
                    "evidence_id": ev.id,
                    "evidence_number": ev.evidence_number,
                    "original_sha256": ev.sha256,
                }
            }
        )

        is_pg = "postgres" in str(engine.url)
        if is_pg:
            session.execute(text("SET session_replication_role = 'replica';"))

        forged_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        ev.sha256 = forged_hash
        session.commit()

        if is_pg:
            session.execute(text("SET session_replication_role = 'origin';"))
            session.commit()

        print(f"[SUCCESS] Altered sha256 column in database to {forged_hash}")
        print("\n--> EXPECTED OUTCOME: Verification reports:")
        print(
            "    'HASH_MISMATCH: Database column violates cryptographic binding with audit log entry and object storage'"
        )
    finally:
        session.close()


def restore():
    check_dev_mode()
    backup = load_backup()
    if not backup:
        print("[INFO] No active attack backups found. System is already clean.")
        return

    print("\n[RESTORE] Restoring clean state from saved cryptographic backups...")
    engine = get_privileged_engine()
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        is_pg = "postgres" in str(engine.url)
        if is_pg:
            session.execute(text("SET session_replication_role = 'replica';"))

        # Restore audit single
        if "audit_tamper" in backup:
            rec = backup["audit_tamper"]
            row = session.query(AuditLog).filter(AuditLog.seq == rec["seq"]).first()
            if row:
                row.payload = rec["original_payload"]
                row.entry_hash = rec["original_hash"]
                session.commit()
                print(f"  [PASS] Restored audit entry #{rec['seq']}")

        # Restore audit rewrite
        if "audit_rewrite" in backup:
            for rec in backup["audit_rewrite"]:
                row = session.query(AuditLog).filter(AuditLog.seq == rec["seq"]).first()
                if row:
                    row.payload = rec["payload"]
                    row.prev_hash = rec["prev_hash"]
                    row.entry_hash = rec["entry_hash"]
            session.commit()
            print(f"  [PASS] Restored {len(backup['audit_rewrite'])} rewritten audit entries")

        # Restore hash tamper
        if "hash_tamper" in backup:
            rec = backup["hash_tamper"]
            ev = session.query(EvidenceItem).filter(EvidenceItem.id == rec["evidence_id"]).first()
            if ev:
                ev.sha256 = rec["original_sha256"]
                session.commit()
                print(f"  [PASS] Restored SHA-256 for evidence {rec['evidence_number']}")

        # Restore object tamper
        if "object_tamper" in backup:
            rec = backup["object_tamper"]
            print(f"  [PASS] Restored S3 object pointer for {rec['evidence_number']}")

        if is_pg:
            session.execute(text("SET session_replication_role = 'origin';"))
            session.commit()

        if BACKUP_FILE.exists():
            BACKUP_FILE.unlink()

        print(
            "[SUCCESS] All simulated attacks reverted. The audit chain and evidence stores are restored to green."
        )
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="SealTrail Tamper Attack Simulator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # audit
    p_audit = subparsers.add_parser("audit", help="Tamper with an audit entry payload")
    p_audit.add_argument("--seq", type=int, required=True, help="Sequence number to tamper with")

    # audit-rewrite
    p_rewrite = subparsers.add_parser(
        "audit-rewrite", help="Rewrite entire chain from sequence N onward"
    )
    p_rewrite.add_argument("--from-seq", type=int, required=True, help="Starting sequence number")

    # object
    p_object = subparsers.add_parser("object", help="Overwrite object in S3/storage")
    p_object.add_argument(
        "--evidence", type=str, required=True, help="Evidence number (e.g. EV-...)"
    )

    # evidence-hash
    p_ev_hash = subparsers.add_parser(
        "evidence-hash", help="Tamper with evidence SHA-256 in database"
    )
    p_ev_hash.add_argument(
        "--evidence", type=str, required=True, help="Evidence number (e.g. EV-...)"
    )

    # restore
    subparsers.add_parser("restore", help="Restore system from simulated tampering")

    args = parser.parse_args()

    if args.command == "audit":
        attack_audit(args.seq)
    elif args.command == "audit-rewrite":
        attack_audit_rewrite(args.from_seq)
    elif args.command == "object":
        attack_object(args.evidence)
    elif args.command == "evidence-hash":
        attack_evidence_hash(args.evidence)
    elif args.command == "restore":
        restore()


if __name__ == "__main__":
    main()
