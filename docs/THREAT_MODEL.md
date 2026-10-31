# SealTrail Threat Model & Security Architecture

This document provides a forensic threat analysis of SealTrail according to STRIDE and defense-in-depth principles.

---

## 1. Adversary Personas & Attack Capabilities

| Persona | Description | Capabilities |
|---------|-------------|--------------|
| **Curious Insider** | Valid organization user with low privileges (e.g., investigator or observer). | Has valid credentials; attempts to view unauthorized cases or manipulate records. |
| **Malicious Investigator** | Case-assigned investigator attempting to alter evidence, fabricate timelines, or tamper with logs. | Can upload evidence and initiate custody transfers for assigned cases. |
| **Malicious DBA** | Rogue PostgreSQL database administrator with full `SUPERUSER` privileges on the database host. | Direct read/write access to PostgreSQL tables, indexes, triggers, and sequences. |
| **Rogue Storage Administrator** | Rogue S3/MinIO administrator or compromised storage credentials. | Can replace, upload, or delete objects within the evidence storage bucket. |
| **External Attacker** | Remote unauthorized adversary on the network. | Unauthenticated; attempts credential brute-forcing, injection, or MITM. |
| **Compromised Signing Key** | Adversary who obtains the Ed25519 checkpoint private key. | Can generate valid cryptographic signatures over arbitrary checkpoint heads. |

---

## 2. Threat Coverage Matrix

### Legend
- **PREVENTED**: Cryptographic or architectural controls completely block the action from succeeding.
- **DETECTED**: The action cannot be prevented at the protocol layer, but is cryptographically and visibly detected immediately.
- **NOT COVERED**: Out-of-scope risks requiring physical or operational security controls outside the software application.

---

### Threat Analysis

| Threat / Scenario | Target System | Status | Defensive Mechanism |
|-------------------|---------------|--------|---------------------|
| **Unauthorized Case Access** | FastAPI API | **PREVENTED** | Case isolation checks (`deps.py`) reject non-members with 403 Forbidden. Attempt logged to audit. |
| **Self-Approval of Sensitive Actions** | Approval Engine | **PREVENTED** | Enforced at both application layer and PostgreSQL check constraint: `CHECK (decided_by IS NULL OR decided_by <> requested_by)`. |
| **Client-Side File Substitution During Intake** | Evidence Pipeline | **PREVENTED** | Dual hashing: client computes SHA-256 via `hash-wasm`; backend streams and computes SHA-256. Mismatches abort upload. |
| **Modifying Evidence Metadata in Database** | PostgreSQL DB | **PREVENTED** | `trg_prevent_evidence_update` database trigger raises an exception if any immutable column is modified. |
| **Altering or Deleting Audit Log Entries** | PostgreSQL DB | **PREVENTED** | `trg_audit_log_append_only` prevents all `UPDATE`, `DELETE`, and `TRUNCATE` operations on `audit_log`. |
| **Out-of-Order / Forked Audit Entries** | PostgreSQL DB | **PREVENTED** | `trg_audit_log_chain` verifies that `seq == last_seq + 1` and `prev_hash == last_entry_hash` before insertion. |
| **Direct DB Modification by Superuser (DBA)** | PostgreSQL DB | **DETECTED** | Alters entry hash without updating triggers. Next chain verification flags `CHAIN_BROKEN` at the exact sequence. |
| **Full Chain Rewrite by Superuser (DBA)** | PostgreSQL DB | **DETECTED** | DBA recomputes all row hashes from sequence $k$ to $N$. Checkpoint verification fails: `head_hash` does not match the Ed25519 signed checkpoint. |
| **Silent S3 Object Replacement by Storage Admin** | MinIO Storage | **DETECTED** | Storage object version ID changes. Periodic automated evidence sweep flags `OBJECT_REPLACED` and `HASH_MISMATCH`. |
| **Premature Evidence Disposal** | Storage / API | **PREVENTED** | Disposal requires dual authorization AND verification that `retention_until <= today` AND `legal_hold == False`. |
| **Deletion of Evidence by App Role** | MinIO Storage | **PREVENTED** | S3 IAM policy attached to `sealtrail-app` explicitly denies `s3:DeleteObject` and `s3:DeleteObjectVersion`. |
| **Custody Transfer SLA Abandonment** | Custody Engine | **DETECTED** | Scheduled background job flags transfers exceeding `ACK_SLA_MINUTES` without acknowledgement (`MISSING_ACK` alert). |
| **Brute-Force Credential Stuffing** | Auth Endpoint | **PREVENTED** | Account lockout after 5 consecutive failed attempts (`LOGIN_LOCKOUT_MINUTES`) + Argon2id rate-limiting. |
| **Replay Attacks on Custody Exports** | Verifier Script | **PREVENTED** | Export manifest contains ISO-8601 UTC timestamp, case ID, evidence ID, SHA-256 file digests, signed by Ed25519. |
| **Tampered Export ZIP Contents** | Verifier Script | **DETECTED** | `verify.py` recalculates SHA-256 for all payload files against `SHA256SUMS.txt` and validates the Ed25519 digital signature. |
| **Compromised Host Memory / Root Access** | Operating System | **NOT COVERED** | If an attacker gains full OS root access, they can manipulate running Python process memory or dump encryption keys. |
| **Compromised Offline Signing Key** | Checkpoints | **NOT COVERED** | If the Ed25519 private key is leaked, an attacker with DBA privileges can rewrite the chain and forge checkpoints. Production systems should anchor checkpoint heads to an external RFC 3161 Timestamp Authority or public ledger. |
| **Physical Theft of Storage Media** | Physical Infra | **NOT COVERED** | Relies on underlying OS-level or storage-level full disk encryption (LUKS / BitLocker). |
| **Legal Admissibility Contestation** | Legal / Court | **MITIGATED** | Compliant with Section 63 Bharatiya Sakshya Adhiniyam (BSA), 2023. Generates verifiable Schedule Part A/B draft certificate with automated custody logs. |

---

## 3. Security Design Principles

1. **Defense in Depth**: We do not rely solely on application code logic; PostgreSQL SQL triggers and MinIO IAM policies enforce immutability and append-only constraints at the infrastructure layer.
2. **Fail-Closed Default**: Any cryptographic hash mismatch or authorization ambiguity results in immediate operation abortion and critical anomaly alert creation.
3. **Audit Atomicity**: Every state change commits in the identical database transaction as its corresponding audit entry under `pg_advisory_xact_lock()`. No orphaned state changes can exist.
4. **Deterministic Canonicalization**: Audit entries are serialized to canonical JSON using sorted keys and standard separators to ensure bit-level stability across platforms and Python/PostgreSQL roundtrips.
