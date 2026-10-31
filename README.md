# SealTrail — Digital Evidence Chain-of-Custody & Case Workspace

> *"Prove it hasn't changed."*

SealTrail is an enterprise-grade digital evidence management system designed for law enforcement, digital forensics incident response (DFIR) units, and regulatory compliance teams. It guarantees that digital evidence registered during an investigation remains provably untampered from crime scene ingestion to courtroom presentation.

Built for HACKNOVA 2026 (Problem Statement 04: *Digital Evidence Chain-of-Custody & Case Collaboration*).

---

## Key Capabilities

- **Three-Way Cryptographic Integrity Binding**: Synchronizes the raw storage object version in S3/MinIO, the immutable database record, and a contiguous hash-chained audit trail.
- **Append-Only Hash-Chained Audit Trail**: Database-enforced triggers prevent any update, delete, truncation, or out-of-order sequence insertion. Every state change and its audit record commit atomically in the same transaction.
- **Ed25519-Signed Chain Checkpoints**: Periodic cryptographic signatures over chain heads thwart even a full database administrator rewrite.
- **Dual-Authorization Controls (Two-Person Rule)**: Reversible and irreversible actions (external custody transfers, legal hold releases, evidence disposal, and export packages) require explicit two-party approval enforced at both application and database check levels.
- **Explainable Anomaly Alerts**: Deterministic rule engines detect hash mismatches, silent object replacements, out-of-sequence chain modifications, SLA-breaching custody acknowledgements, burst extractions, off-hours access, and brute-force attempts.
- **Courtroom-Defensible Exports**: Self-verifying ZIP packages containing raw evidence, chain certificates, SHA256SUMS, Ed25519 signatures, and an offline zero-dependency `verify.py` script.
- **Statutory Section 63 BSA Certificate**: Generates official Schedule Part A/B electronic evidence certificates compliant with India's Bharatiya Sakshya Adhiniyam, 2023.

---

## Mandated Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend API** | FastAPI 0.111 (Python 3.12/3.11) | RESTful API with strict Pydantic v2 schemas and single error envelope |
| **Frontend SPA** | React 18, TypeScript (Strict), Vite | Forensic analyst UI with dark/light theme, incremental client-side hashing |
| **Relational Database** | PostgreSQL 16 | Relational data model with SQL triggers, foreign keys, and role isolation |
| **Object Storage** | MinIO / S3-compatible | Versioned object storage with IAM policies denying delete operations to app role |
| **Hashing Engine** | SHA-256 (`hashlib`, `hash-wasm`) | End-to-end streaming evidence digest calculation in browser and server |
| **Audit Ledger** | Custom Hash-Chained Log | Append-only ledger linking entries via `SHA-256(prev_hash || canonical_entry)` |
| **Access Control** | Role-Based Access Control (RBAC) | Strict permission matrix across Admin, Supervisor, Investigator, Custodian, Auditor |

**Key Additions:** SQLAlchemy 2.0 (sync), psycopg 3, Alembic, Ed25519 (`cryptography`), ReportLab, PyZipper (AES-256 encrypted ZIPs), APScheduler, SlowAPI, Structlog, MUI v5, TanStack Query v5.

---

## Quickstart

### Prerequisites
- Docker & Docker Compose (v2.20+)
- Web browser (Chrome, Firefox, Edge, Safari)

### 1. Launch the Stack
```bash
docker compose up --build -d
```
This spins up:
- `postgres` on port `5432` with automated database schema migrations and triggers
- `minio` on port `9000` (API) and `9001` (Console) with bucket versioning
- `backend` on port `8000` (FastAPI + in-process integrity scheduler)
- `frontend` on port `8080` (Nginx serving built React app and reverse-proxying `/api/`)

### 2. Populate Synthetic Forensic Seed Data
```bash
docker compose exec backend python scripts/seed.py
```
This runs synthetic cases, evidence items across disk images, mobile extractions, network PCAPs, active custody transfers, overdue SLA alerts, and dual-authorization approval queues through the real service layer.

### 3. Access the Application
Open **`http://localhost:8080`** in your browser.

---

## Default Synthetic User Accounts

All seeded accounts use the password configured in `SEED_PASSWORD` (default: `SealTrail2026!Secure`):

| Email | Role | Access Scope |
|-------|------|--------------|
| `admin@sealtrail.local` | `ADMIN` | User lifecycle management, global audit log view, system configuration |
| `supervisor.patil@sealtrail.local` | `SUPERVISOR` | All cases oversight, dual-authorization approvals, legal holds, export grants |
| `investigator.sharma@sealtrail.local` | `INVESTIGATOR` | Assigned cases, evidence intake, internal custody transfers, notes & links |
| `investigator.rao@sealtrail.local` | `INVESTIGATOR` | Secondary case investigator, evidence intake and custody handling |
| `custodian.singh@sealtrail.local` | `CUSTODIAN` | Evidence locker control, physical custody intake and transfer receipts |
| `auditor.deshmukh@sealtrail.local` | `AUDITOR` | Read-only global compliance access, integrity sweeps, audit verification |

---

## Live Tamper Simulation & Attack Scenarios

SealTrail includes a dedicated attack simulation script (`backend/scripts/tamper_demo.py`) that demonstrates both attack vectors and automated detection in real time.

```bash
# 1. Simulate a malicious DBA modifying an audit entry directly in PostgreSQL
docker compose exec backend python scripts/tamper_demo.py audit

# 2. Verify detection via backend or UI (Triggers HASH_MISMATCH / CHAIN_BROKEN)
docker compose exec backend python -c "from app.db import get_db_session; from app.services.audit_chain import verify_chain; print(verify_chain(next(get_db_session())))"

# 3. Restore the modified record
docker compose exec backend python scripts/tamper_demo.py restore

# 4. Simulate a compromised storage administrator replacing an S3 file in MinIO
docker compose exec backend python scripts/tamper_demo.py object

# 5. Run an automated evidence integrity sweep
# In the Web UI: Go to Integrity -> Trigger Evidence Sweep -> Alert raised: OBJECT_REPLACED

# 6. Simulate an attacker rewriting PostgreSQL and recomputing the entire hash chain
docker compose exec backend python scripts/tamper_demo.py audit-rewrite
# Detection: The head hash now disagrees with the signed Ed25519 checkpoint!
```

---

## Testing & Verification

Run the comprehensive automated test suite (18 integration & security test suites):
```bash
# Backend pytest suite
docker compose exec backend pytest -v

# Frontend TypeScript and lint checks
cd frontend
npm run typecheck
npm run lint
npm run build
```

---

## License & Disclaimer
SealTrail was created as an educational prototype for HACKNOVA 2026. Electronic certificates generated under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023 are draft templates requiring review and execution by authorized forensic practitioners.
