# SealTrail — Build Specification

> Standing instructions for every agent working in this repository. Read this file completely before writing any code. Execute the stages in Section 12 in order. Do not ask the user questions; make the best decision, log it in `docs/DECISIONS.md`, and keep going.

---

## 0. Mission and working rules

**Product:** SealTrail — a secure case workspace where authorized investigators register digital evidence, transfer it between custodians, and keep a history that is **tamper-evident and defensible in court**. Tagline: *"Prove it hasn't changed."*

**Context:** 5-hour hackathon, problem statement "Digital Evidence Chain-of-Custody & Case Collaboration". The result is judged on technical implementation (including adherence to the mandated stack), tamper-evidence that is *demonstrably real*, workflow completeness, security thinking, UX, and the live demo. You are building the whole thing from scratch, to production-grade quality, unattended.

### 0.1 Non-negotiables

1. **Mandated stack must be implemented first and fully**: FastAPI, React, PostgreSQL, S3-compatible storage (MinIO), SHA-256, an append-only audit log, RBAC. Anything extra is allowed only on top of that. Not following the mandated stack costs 10 marks.
2. **Nothing is mocked.** Every endpoint hits the real database and real object storage. No hardcoded responses, no fake data in code paths, no `TODO`, no `pass` bodies, no `NotImplementedError`, no lorem ipsum. If a feature cannot be finished properly, **cut it entirely** and record it in `docs/KNOWN_LIMITATIONS.md` (see the cut line in Section 12). A half-built feature that pretends to work is worse than a missing one.
3. **Every claim must be provable by running code.** The tamper-evidence story is the product. Section 6 defines mechanisms and Section 11 defines the tests that prove them.
4. **Never log or commit secrets.** `.env` is git-ignored. Never log file contents, tokens, passwords, or full request bodies.
5. **Single source of truth for state changes:** every state change and the audit entry describing it are written in the **same database transaction**. There must be no code path that changes evidence state without an audit entry.

### 0.2 Anti-slop rules (apply to code, UI copy and docs)

- Every file, endpoint, table, column, component and dependency exists because a requirement or flow uses it. No dead code, no commented-out code, no unused dependencies, no unused exports.
- Typed everywhere. Python: type hints on every function, `ruff check` and `ruff format` clean. TypeScript: `"strict": true`, `tsc --noEmit` clean, ESLint clean.
- One error envelope for the entire API: `{"error": {"code": "SNAKE_CASE_CODE", "message": "human readable", "details": {}, "request_id": "..."}}`. Correct HTTP status codes (400/401/403/404/409/413/422/429). Never leak stack traces.
- UI copy is terse and operational (like a forensic tool, not a marketing page). No emojis anywhere. No decorative gradients, glassmorphism, or illustrations. Every data view has loading, empty and error states. Keyboard focus is visible; form fields have labels.
- Comments explain *why*, never *what*. No tutorial-style comments.
- Never report a stage as done without running it: run the tests, hit the endpoints, and (if you have a browser tool) open the page and compare it against `docs/reference/ui-reference.png`.
- Do not invent legal claims. Anything resembling a legal document is labeled as an auto-filled draft for the responsible person to review and sign.
- Pin versions: Docker images by explicit tag (never `latest`), Python and npm dependencies via lockfiles (`uv.lock` or pinned `requirements.txt`, `package-lock.json`).

### 0.3 Git policy

- `git init` at the start, branch `main`. Add `.gitignore` before the first commit (must ignore `.env`, `node_modules`, `__pycache__`, `.venv`, `dist`, `*.pyc`, `.pytest_cache`, `.ruff_cache`, local MinIO/Postgres volumes, `tmp/`).
- Commit after **every stage** in Section 12, only after that stage's acceptance checks pass. Use Conventional Commits with the exact message given per stage.
- Before each commit run `git status` and `git ls-files | grep -E '(^|/)\.env$'`; the second command must print nothing.
- Do not push anywhere. At the end, create the annotated tag `v1.0-hacknova`.

### 0.4 Operating mode

- Work autonomously. If something is ambiguous, choose the simplest option that satisfies the requirement and note it in `docs/DECISIONS.md` (one line: decision, reason).
- If you are stuck on a non-core feature for more than ~10 minutes, apply the cut line (Section 12) and move on.
- If you can run parallel agents: after Stage 2 is committed, one agent may take the frontend track (Stages 8–9) using `docs/openapi.json` while another continues the backend track (Stages 3–7). Otherwise run sequentially.
- Docker and Docker Compose are required. Run `docker compose version` first. If unavailable, say so at the top of your final report and explain what could not be verified.
- The user supplies `.env` at the repo root and the reference screenshot at `docs/reference/ui-reference.png`. If `.env` is missing, copy `.env.example` to `.env` and run `backend/scripts/gen_secrets.py` to fill every blank secret. The user also supplies `docs/PITCH.md`; never overwrite or delete it.

---

## 1. Requirements and where each lives

| # | Requirement from the problem statement | Implemented as |
|---|---|---|
| 1 | Register files and device extracts with source, collector, date, case metadata | Evidence intake flow (6.4), `evidence_items` table |
| 2 | Cryptographic hashes at ingestion, verified on every transfer | SHA-256 intake pipeline (6.4), re-verification on transfer, receipt, download, export (6.5) |
| 3 | Unique evidence IDs and controlled labels | Evidence number with check character, PDF labels with QR and tracked reprints (6.6) |
| 4 | Record each transfer, view, export, annotation, acknowledgement | Hash-chained audit log (6.1) + custody tables |
| 5 | Role-based approvals and dual authorization for sensitive actions | RBAC matrix (6.8), `approval_requests` with two-person rule (6.9) |
| 6 | Link evidence to people, events, notes, timelines without changing originals | Link tables and case timeline (5, 6.10); evidence row is immutable |
| 7 | Tamper-evident chronological custody reports | Signed JSON + PDF custody report (6.12) |
| 8 | Flag hash mismatches, missing acknowledgements, unusual access | Alerts engine with explainable rules (6.11) |
| 9 | Legal hold, retention rules, secure export packages | Retention/hold (6.13), signed export package with offline verifier (6.14) |

**Beyond the brief (differentiators, implement them well):** three-way integrity binding (storage object ↔ database row ↔ audit chain), Ed25519-signed checkpoints that defeat a full chain rewrite by a database administrator, an offline `verify.py` shipped inside every export, a scripted live tamper demo, and a draft Section 63 BSA certificate (India).

---

## 2. Technology stack

**Mandated by the problem statement (all seven are mandatory):**
FastAPI · React · PostgreSQL · S3-compatible storage (MinIO) · SHA-256 · append-only audit log · RBAC

**Backend additions:** Python 3.12, SQLAlchemy 2.0 (sync), psycopg 3, Alembic, Pydantic v2 + pydantic-settings, boto3, PyJWT, argon2-cffi, `cryptography` (Ed25519), reportlab, `qrcode[pil]`, pyzipper (AES-256 ZIP), APScheduler, slowapi (rate limiting), structlog, pytest, httpx, ruff. Run uvicorn with a **single worker** (the scheduler lives in-process).

**Frontend additions:** Vite, TypeScript (strict), React 18, React Router v6, MUI v5 (`@mui/material`, `@mui/icons-material`), TanStack Query v5, `openapi-typescript` + `openapi-fetch` (types generated from `docs/openapi.json`), `hash-wasm` (incremental SHA-256 in the browser), `date-fns`.

**Infrastructure:** Docker Compose, nginx (serves the built frontend, reverse-proxies `/api`), MinIO with bucket versioning.

---

## 3. Repository layout (create exactly this; additions need a line in `docs/DECISIONS.md`)

```
sealtrail/
├── AGENTS.md                         # this specification
├── README.md
├── docker-compose.yml
├── .env.example                      # same keys as .env, secrets blank
├── .gitignore
├── docs/
│   ├── ARCHITECTURE.md               # diagrams (Mermaid), data flow, trust boundaries
│   ├── THREAT_MODEL.md               # who we defend against, what we stop vs only detect vs do not cover
│   ├── DECISIONS.md
│   ├── KNOWN_LIMITATIONS.md          # honest list of what is not done or not covered
│   ├── DEMO_SCRIPT.md                # exact 5-minute click path + commands
│   ├── QA_CHECKLIST.md               # manual browser verification results
│   ├── FILE_MAP_ACTUAL.md            # generated at the end: real tree, one line per file
│   ├── PITCH.md                      # supplied by the user, never overwrite
│   ├── openapi.json                  # exported from the running backend
│   └── reference/ui-reference.png    # supplied by the user
├── infra/
│   ├── postgres/init/01-roles-and-extensions.sh
│   ├── minio/init.sh                 # buckets, versioning, service users, policies
│   └── nginx/nginx.conf
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/versions/             # raw-SQL aware migrations (triggers, grants)
│   ├── app/
│   │   ├── main.py                   # app factory, lifespan (scheduler), middleware, routers
│   │   ├── config.py                 # pydantic-settings, fails fast on missing values
│   │   ├── db.py                     # engines/sessions (app role), session helper
│   │   ├── logging.py                # structlog JSON, request id
│   │   ├── errors.py                 # exception types + handlers (error envelope)
│   │   ├── deps.py                   # auth, current user, permission + case-access dependencies
│   │   ├── security/
│   │   │   ├── passwords.py          # argon2 hash/verify, password policy
│   │   │   ├── tokens.py             # JWT access + refresh (httpOnly cookie)
│   │   │   └── permissions.py        # Role, Permission enums, the RBAC matrix (single source)
│   │   ├── models/                   # SQLAlchemy models split by domain
│   │   │   ├── users.py  cases.py  evidence.py  custody.py  approvals.py
│   │   │   ├── links.py  audit.py  alerts.py  exports.py
│   │   ├── schemas/                  # Pydantic request/response models by domain
│   │   ├── routers/
│   │   │   ├── auth.py  users.py  cases.py  evidence.py  custody.py  approvals.py
│   │   │   ├── links.py  audit.py  integrity.py  alerts.py  reports.py
│   │   │   ├── exports.py  retention.py  dashboard.py  health.py
│   │   ├── services/
│   │   │   ├── audit_chain.py        # canonicalization, append, verify
│   │   │   ├── checkpoints.py        # Ed25519 signed chain-head checkpoints
│   │   │   ├── hashing.py            # chunked SHA-256 helpers
│   │   │   ├── storage.py            # S3 client wrapper (put, get, head, versions)
│   │   │   ├── evidence_ids.py       # numbering + check character
│   │   │   ├── intake.py             # evidence registration pipeline
│   │   │   ├── integrity.py          # three-way evidence verification + sweep
│   │   │   ├── custody.py            # transfer state machine
│   │   │   ├── approvals.py          # dual-authorization engine
│   │   │   ├── anomaly.py            # alert rules
│   │   │   ├── labels.py             # PDF labels with QR
│   │   │   ├── custody_report.py     # JSON + PDF signed report
│   │   │   ├── export_package.py     # signed ZIP + verify.py
│   │   │   ├── bsa_certificate.py    # draft Section 63 certificate PDF
│   │   │   └── retention.py          # retention, legal hold, disposal
│   │   ├── jobs/scheduler.py         # APScheduler jobs
│   │   └── templates/verify_package.py   # shipped verbatim inside every export as verify.py
│   ├── scripts/
│   │   ├── gen_secrets.py            # fills blank secrets in .env, generates Ed25519 keypair
│   │   ├── seed.py                   # synthetic demo data through the real service layer
│   │   └── tamper_demo.py            # live attack simulation (db / audit / object)
│   └── tests/
└── frontend/
    ├── Dockerfile                    # build stage + nginx stage
    ├── package.json  vite.config.ts  tsconfig.json  eslint config
    └── src/
        ├── main.tsx  App.tsx  theme.ts
        ├── api/                      # generated types, client, query hooks
        ├── auth/                     # AuthProvider, route guards
        ├── layout/                   # Sidebar, AppShell, PageHeader
        ├── components/               # DataTable, ExpandableRow, ChipStatus, HashText, ConfirmDialog, ...
        ├── lib/                      # formatters, hashing worker wrapper, permissions helper
        └── pages/                    # one folder per page (Section 8)
```

---

## 4. Environment and infrastructure

### 4.1 `.env` keys (the user provides values; `.env.example` lists the same keys with blank secrets)

```
POSTGRES_DB, POSTGRES_SUPERUSER, POSTGRES_SUPERUSER_PASSWORD
DB_OWNER_USER, DB_OWNER_PASSWORD, DB_APP_USER, DB_APP_PASSWORD, DB_HOST, DB_PORT
DATABASE_URL_APP, DATABASE_URL_OWNER, DATABASE_URL_SUPERUSER_HOST
MINIO_ROOT_USER, MINIO_ROOT_PASSWORD
S3_ENDPOINT_URL, S3_ENDPOINT_URL_HOST, S3_REGION, S3_BUCKET_EVIDENCE, S3_BUCKET_EXPORTS
S3_APP_ACCESS_KEY, S3_APP_SECRET_KEY, S3_DISPOSER_ACCESS_KEY, S3_DISPOSER_SECRET_KEY
APP_ENV, APP_BASE_URL, CORS_ORIGINS, JWT_SECRET, JWT_ACCESS_MINUTES, JWT_REFRESH_DAYS
COOKIE_SECURE, MAX_UPLOAD_MB, LOGIN_MAX_FAILURES, LOGIN_LOCKOUT_MINUTES, PASSWORD_MIN_LENGTH
CHECKPOINT_SIGNING_KEY_B64, CHECKPOINT_PUBLIC_KEY_B64
CHECKPOINT_INTERVAL_MINUTES, CHAIN_VERIFY_INTERVAL_MINUTES
ACK_SLA_MINUTES, BUSINESS_TZ, BUSINESS_HOURS_START, BUSINESS_HOURS_END
BURST_VIEW_THRESHOLD, BURST_WINDOW_MINUTES, DENIED_ATTEMPTS_THRESHOLD, DENIED_WINDOW_MINUTES
APPROVAL_EXPIRY_HOURS, DEFAULT_RETENTION_DAYS
SEED_ON_START, SEED_PASSWORD, SEED_EMAIL_DOMAIN
```

`config.py` loads these with pydantic-settings and **refuses to start** if a required value is empty. No third-party API keys are needed anywhere in this project.

`backend/scripts/gen_secrets.py`: fills any blank secret in `.env` (random hex for passwords/JWT, Ed25519 keypair as base64 raw bytes for the two `CHECKPOINT_*` keys). With `--rotate` it regenerates all of them. It never prints secret values.

### 4.2 `docker-compose.yml`

Services (all on one private network, restart `unless-stopped`, healthchecks on each):

- `postgres` (postgres:16 pinned tag): runs `infra/postgres/init/01-roles-and-extensions.sh` on first start, which creates the owner role and the app role from env. Published only on `127.0.0.1:5432` (needed by the tamper demo).
- `minio` (pinned tag): API `127.0.0.1:9000`, console `127.0.0.1:9001`.
- `minio-init` (pinned `minio/mc` tag, runs once): creates both buckets, **enables versioning** on both, creates the two service users and attaches policies. App policy: `s3:PutObject`, `s3:GetObject`, `s3:GetObjectVersion`, `s3:ListBucket`, `s3:ListBucketVersions`, with `s3:DeleteObject` and `s3:DeleteObjectVersion` explicitly denied. Disposer policy: additionally allows `s3:DeleteObject` and `s3:DeleteObjectVersion` on the evidence bucket only.
- `backend`: runs `alembic upgrade head` (as owner), then `uvicorn app.main:app --workers 1`. Connects as the **app** role. Not published to the host except `127.0.0.1:8000` for Swagger.
- `frontend`: multi-stage build, nginx serves the build and proxies `/api/` to `backend:8000`. Published on `8080`.

`infra/nginx/nginx.conf`: `client_max_body_size 256m`, `proxy_request_buffering off` for upload routes, `proxy_read_timeout 300s`, gzip for static assets, SPA fallback to `index.html`, forward `X-Request-ID`/`X-Forwarded-For`, and security headers (`Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`).

One-command run for the user: `docker compose up --build -d` then `docker compose exec backend python scripts/seed.py`.

---

## 5. Data model

PostgreSQL 16. UUID primary keys with `gen_random_uuid()` (no extensions needed), `timestamptz` everywhere (UTC), emails stored lower-cased with a unique index on `lower(email)`. Alembic migrations written by hand (not autogenerated blindly), using `op.execute` for triggers and grants. All migrations run as the owner role.

| Table | Key columns and constraints |
|---|---|
| `users` | `id, email, full_name, role` (enum below), `password_hash, is_active, failed_login_count, locked_until, last_login_at, created_at` |
| `cases` | `id, case_number` (unique), `name, description, status` (OPEN/CLOSED), `classification` (RESTRICTED/CONFIDENTIAL/INTERNAL), `lead_user_id, evidence_counter int default 0, legal_hold bool, legal_hold_reason, retention_policy_id, opened_at, closed_at, created_by` |
| `case_members` | PK `(case_id, user_id)`, `case_role` (LEAD/MEMBER/OBSERVER), `added_by, added_at` |
| `retention_policies` | `id, name, retain_days, description` |
| `evidence_items` | `id, evidence_number` (unique), `case_id, parent_evidence_id` (nullable), `type` (FILE/DISK_IMAGE/MOBILE_EXTRACT/CLOUD_EXPORT/EMAIL/NETWORK_CAPTURE/OTHER), `item_name, description, source_description, collected_by_user_id, collected_at, acquisition_method, acquisition_tool, device_make, device_model, device_serial, original_filename, content_type, size_bytes, sha256 char(64), client_sha256 char(64) null, storage_bucket, storage_key, storage_version_id, intake_at, intake_by` — **immutable**; mutable: `current_custodian_id, current_location, status` (REGISTERED/IN_CUSTODY/TRANSFER_PENDING/DISPOSED), `integrity_state` (UNVERIFIED/OK/OBJECT_REPLACED/CORRUPT), `last_verified_at, legal_hold bool, retention_until date, label_print_count int, disposed_at` |
| `custody_transfers` | `id, evidence_id, from_user_id, to_user_id, to_location, reason, is_external bool, external_party, status` (PENDING_APPROVAL/PENDING_ACK/COMPLETED/REJECTED/CANCELLED/DISPUTED), `approval_request_id, hash_at_send, requested_at, ack_due_at, acknowledged_at, hash_at_receipt, receipt_verified bool` |
| `approval_requests` | `id, kind` (EXTERNAL_TRANSFER/EXPORT_PACKAGE/LEGAL_HOLD_RELEASE/DISPOSAL), `case_id, evidence_id null, requested_by, justification` (min 10 chars), `payload jsonb, status` (PENDING/APPROVED/REJECTED/CANCELLED/EXECUTED/EXPIRED), `decided_by, decided_at, decision_note, expires_at, executed_at`, **`CHECK (decided_by IS NULL OR decided_by <> requested_by)`** |
| `annotations` | `id, evidence_id, author_id, body, body_sha256, parent_annotation_id null, created_at` — **append-only** |
| `people` | `id, case_id, full_name, role_in_case` (SUSPECT/WITNESS/VICTIM/INVESTIGATOR/EXPERT/OTHER), `contact, notes, created_by` |
| `case_events` | `id, case_id, title, description, occurred_at, created_by` |
| `case_notes` | `id, case_id, evidence_id null, body, author_id, created_at` — **append-only** |
| `evidence_links` | `id, evidence_id, target_type` (PERSON/EVENT/NOTE/EVIDENCE), `target_id, relation, created_by, created_at, revoked_at null, revoked_by null`; unique on `(evidence_id, target_type, target_id, relation)`. Revoking only sets `revoked_*` and is audited. |
| `audit_log` | `seq bigint PK` (assigned by the chain, contiguous from 1), `ts timestamptz, actor_id null, actor_role null, action text, case_id null, evidence_id null, payload jsonb, ip null, prev_hash char(64), entry_hash char(64)` — **append-only** |
| `audit_checkpoints` | `id, seq_to, head_hash, signature_b64, public_key_id, created_at, created_by` — **append-only** |
| `integrity_state` | single-row table: `last_chain_check_at, chain_ok, head_seq, broken_seq null, broken_reason null` (mutable status, not evidence) |
| `integrity_runs` | `id, kind` (EVIDENCE_SWEEP), `started_by, started_at, finished_at, total, checked, failed, status` |
| `alerts` | `id, rule, severity` (LOW/MEDIUM/HIGH/CRITICAL), `case_id, evidence_id, details jsonb, explanation text, audit_seqs bigint[], status` (OPEN/ACKNOWLEDGED/RESOLVED), `dedupe_key` (unique), `created_at, acknowledged_by, resolved_by, resolution_note` |
| `exports` | `id, evidence_id, case_id, approval_request_id, requested_by, approved_by, encrypted bool, package_sha256, package_size, storage_key, created_at, download_count` |

`users.role` enum: `ADMIN, SUPERVISOR, INVESTIGATOR, CUSTODIAN, AUDITOR`.

### 5.1 Database-level enforcement (in migrations)

1. **Roles and grants.** The app role gets `SELECT, INSERT` only on `audit_log`, `audit_checkpoints`, `annotations`, `case_notes`. On other tables it gets only the verbs the app needs, granted explicitly per table (no default privileges, no `ALL`). It owns nothing and cannot alter schema or disable triggers.
2. **Append-only triggers** on those four tables: `BEFORE UPDATE OR DELETE` row trigger and `BEFORE TRUNCATE` statement trigger, each raising an exception.
3. **Chain trigger** on `audit_log`, `BEFORE INSERT`: the new row's `seq` must equal the last `seq + 1` (or `1` if empty, with `prev_hash` = 64 zeros), and `prev_hash` must equal the last row's `entry_hash`. This makes forking or gapping the chain impossible even through an application bug.
4. **Immutability trigger** on `evidence_items`: `BEFORE UPDATE` raises if any immutable column changes (everything not listed as mutable above).
5. **Foreign keys and checks** everywhere they apply, including the dual-authorization check on `approval_requests`.

---

## 6. Core mechanisms (specifications)

### 6.1 Hash-chained audit log (`services/audit_chain.py`)

- Single global chain. Genesis entry (`seq=1`, action `CHAIN_GENESIS`, `prev_hash` = 64 zeros) is created by the first migration/startup if the table is empty.
- **Canonical form** of an entry: JSON of `{"seq", "ts", "actor_id", "actor_role", "action", "case_id", "evidence_id", "payload", "ip"}` serialized with `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, UTF-8. `ts` is an ISO-8601 UTC string with microseconds and a `Z` suffix. **Payloads must not contain floats** (use ints and strings) so canonicalization is stable after a JSONB round-trip. UUIDs are lowercase hyphenated strings.
- `entry_hash = SHA256( bytes.fromhex(prev_hash) || canonical_bytes )`, hex-encoded.
- `append(session, actor, action, case_id, evidence_id, payload, ip)`: takes `pg_advisory_xact_lock(<constant>)`, reads the last row, computes the next `seq`, `prev_hash`, `entry_hash`, and inserts — **inside the caller's transaction**, so state change and audit entry commit or roll back together.
- Events that must be recorded even when the business transaction rolls back (`LOGIN_FAILED`, `ACCESS_DENIED`, `INTAKE_REJECTED`, `ACCOUNT_LOCKED`) are appended through `append_independent(...)`, which uses its own session/transaction.
- Only the seeder may pass a custom `ts`, and only with a non-decreasing value. A test must prove no API route can set `ts`.
- **Audit actions** (closed set, enum in code): `CHAIN_GENESIS, LOGIN_SUCCESS, LOGIN_FAILED, ACCOUNT_LOCKED, LOGOUT, USER_CREATED, USER_UPDATED, CASE_CREATED, CASE_MEMBER_ADDED, CASE_MEMBER_REMOVED, CASE_CLOSED, EVIDENCE_REGISTERED, INTAKE_HASH_VERIFIED, INTAKE_REJECTED, EVIDENCE_VIEWED, EVIDENCE_DOWNLOADED, EVIDENCE_LIST_EXPORTED, HASH_VERIFIED, HASH_MISMATCH, LABEL_PRINTED, EVIDENCE_ANNOTATED, PERSON_ADDED, EVENT_ADDED, NOTE_ADDED, EVIDENCE_LINKED, EVIDENCE_LINK_REVOKED, TRANSFER_REQUESTED, TRANSFER_ACKNOWLEDGED, TRANSFER_REJECTED, TRANSFER_CANCELLED, TRANSFER_DISPUTED, ACK_OVERDUE, APPROVAL_REQUESTED, APPROVAL_GRANTED, APPROVAL_REJECTED, APPROVAL_EXPIRED, APPROVAL_EXECUTED, LEGAL_HOLD_PLACED, LEGAL_HOLD_RELEASED, RETENTION_UPDATED, EVIDENCE_DISPOSED, CUSTODY_REPORT_GENERATED, EXPORT_PACKAGE_BUILT, EXPORT_PACKAGE_DOWNLOADED, BSA_CERTIFICATE_GENERATED, CHAIN_VERIFIED, CHAIN_BROKEN, CHECKPOINT_CREATED, ALERT_RAISED, ALERT_STATUS_CHANGED, ACCESS_DENIED`.
- Scheduled chain checks that pass do **not** write audit entries (they update `integrity_state`). A failure writes `CHAIN_BROKEN` and raises an alert. A user-triggered verification always writes `CHAIN_VERIFIED` or `CHAIN_BROKEN`.
- `verify_chain(session) -> ChainResult`: stream rows by `seq` in batches of 5000, recompute every hash, and check contiguity and linkage. Result: `{ok, checked, head_seq, head_hash, first_broken_seq, reason}` where `reason` is one of `ENTRY_HASH_MISMATCH` (row content altered), `PREV_LINK_MISMATCH`, `SEQ_GAP` (row deleted), `CHECKPOINT_HASH_MISMATCH`, `CHECKPOINT_SIGNATURE_INVALID`. It also verifies every checkpoint: signature valid, and `head_hash` equals the recomputed `entry_hash` at `seq_to`.

### 6.2 Signed checkpoints (`services/checkpoints.py`)

- Ed25519 key from env. Message signed: `sealtrail-checkpoint-v1|{seq_to}|{head_hash}|{created_at_iso}`. `public_key_id` = first 16 hex chars of SHA-256 of the raw public key.
- Created by the scheduler every `CHECKPOINT_INTERVAL_MINUTES`, on demand, and automatically when a custody report or export is produced.
- Purpose (document it in `THREAT_MODEL.md`): an attacker with full database superuser rights can recompute an entire consistent chain, but cannot forge a checkpoint signature without the key, which is never stored in the database. Be honest in the doc: an attacker who steals the signing key **and** rewrites the database defeats this; external anchoring (RFC 3161 timestamp authority or a public ledger) is the production mitigation and is listed as future work.

### 6.3 Storage (`services/storage.py`)

- boto3 client with `endpoint_url`, path-style addressing, the **app** service credentials. Bucket versioning is on.
- MinIO is **not** exposed to browsers and presigned URLs are never used: every byte served goes through the API so it can be verified first.
- Object key: `{case_number}/{evidence_number}/{sha256}`. The version ID returned by `put_object` is stored on the evidence row.
- Functions: `put_stream`, `get_stream(version_id=None)`, `head(version_id=None)` and `latest_version_id()`.

### 6.4 Evidence intake (`services/intake.py`) — `POST /api/v1/cases/{case_id}/evidence`

Multipart: JSON `metadata` field + `file` + optional `client_sha256`.

1. Authorization: role INVESTIGATOR or CUSTODIAN who is a non-observer member of the case; case must be OPEN.
2. Read the uploaded file (Starlette already spools it to disk) in 1 MiB chunks, computing SHA-256 and byte count. Enforce `MAX_UPLOAD_MB` (413).
3. If `client_sha256` is supplied and differs from the server hash → 422 `CLIENT_HASH_MISMATCH`, audit `INTAKE_REJECTED` via `append_independent`. (This means the chain of integrity starts on the collector's own machine.)
4. Allocate the evidence number atomically (6.6), upload to S3, store the returned version ID.
5. **Read back** the object from S3 (pinned version) and re-hash; it must equal the computed hash, else `INTAKE_REJECTED` and a 502 `STORAGE_VERIFICATION_FAILED`. Record the orphan key in the audit payload.
6. In one transaction: insert the evidence row (`status=IN_CUSTODY`, custodian = intake user, `retention_until` = intake date + case policy days, `integrity_state=OK`, `last_verified_at=now`) and append `EVIDENCE_REGISTERED` (payload includes `evidence_number, sha256, size_bytes, storage_key, version_id, client_sha256_present`) and `INTAKE_HASH_VERIFIED`.
7. Response: the evidence record plus `verification: {server_sha256, client_sha256, readback_sha256, match: true}`.

### 6.5 Three-way integrity verification (`services/integrity.py`)

`verify_evidence(evidence, actor, trigger)` checks and returns a structured result:

- **A. Pinned object hash:** stream the stored version from S3, compute SHA-256, compare with `evidence.sha256`.
- **B. Live object check:** `head` the latest version; if its version ID differs from the stored one, the object has been replaced out-of-band (`replaced=true`). Also hash the live object and report whether it matches. The original version remains recoverable because the bucket is versioned.
- **C. Audit binding:** load the evidence's `EVIDENCE_REGISTERED` audit entry and compare the `sha256` in its payload with `evidence.sha256` (detects someone editing the evidence row directly).

Outcome: `OK`, `OBJECT_REPLACED` (B failed, A ok), or `CORRUPT` (A or C failed). Update `integrity_state` and `last_verified_at`; append `HASH_VERIFIED` (result in payload) or `HASH_MISMATCH`; on any failure raise an alert (6.11). Verification is invoked: on transfer request, on acknowledgement, on every download, before building an export, on demand, and by the sweep. A download is **blocked** if verification fails (409 `INTEGRITY_CHECK_FAILED`) unless the actor is a SUPERVISOR and passes `?force=true` with a justification (audited).
The sweep (`POST /api/v1/integrity/evidence-sweep`) runs as a background task, records progress in `integrity_runs`, and the UI polls it.

### 6.6 Evidence IDs and labels

- **Case number:** `SL{yy}-{seq:04d}` from a Postgres sequence, e.g. `SL26-0007`.
- **Evidence number:** `{case_number}-E{n:04d}{c}` where `n` comes from `UPDATE cases SET evidence_counter = evidence_counter + 1 ... RETURNING` (atomic) and `c` is a check character from the Crockford base32 alphabet computed as `alphabet[(Σ ord(ch)·(i+1) for i,ch in enumerate(base_id)) % 32]`. Lookup by number (`GET /evidence/by-number/{number}`) validates the check character first and returns a clear error for mistyped IDs.
- **Label** (`services/labels.py`, reportlab): two formats, 90×50 mm and 50×25 mm. Contains: product name, evidence number (large, monospace), case number, type, intake date, first 16 hex chars of SHA-256, classification marking ("RESTRICTED — AUTHORIZED PERSONNEL ONLY" etc.), QR code encoding `{APP_BASE_URL}/e/{evidence_number}`. `label_print_count` is incremented on every print, every print is audited (`LABEL_PRINTED`), and reprints show `REPRINT {n}` on the label. That is what "controlled labels" means here.

### 6.7 Custody workflow (`services/custody.py`)

State machine: `PENDING_APPROVAL → PENDING_ACK → COMPLETED`, with `REJECTED`, `CANCELLED`, `DISPUTED` terminal states.

- **Request** (`POST /evidence/{id}/transfers`): only the current custodian or the case lead. Body: `to_user_id, to_location, reason, is_external, external_party`. Receiver must be an active INVESTIGATOR/CUSTODIAN and a case member (not required for external). Runs `verify_evidence`; on failure return 409 and raise an alert, no transfer is created. Internal transfer → `PENDING_ACK` immediately with `ack_due_at = now + ACK_SLA_MINUTES`. External transfer → creates an `EXTERNAL_TRANSFER` approval request, status `PENDING_APPROVAL`; when approved it moves to `PENDING_ACK`. Evidence `status=TRANSFER_PENDING`, custodian unchanged until acknowledged. Only one open transfer per evidence item (partial unique index).
- **Acknowledge** (`POST /transfers/{id}/acknowledge`): only the designated receiver. Re-verifies the hash at receipt, stores `hash_at_receipt`. OK → `COMPLETED`, custodian and location updated, evidence `IN_CUSTODY`. Mismatch → `DISPUTED`, alert, evidence flagged, and the custodian does **not** change.
- **Reject / cancel:** receiver may reject with a reason; sender may cancel before acknowledgement. Evidence returns to `IN_CUSTODY` with the sender.
- **Views and downloads:** `GET /evidence/{id}` writes `EVIDENCE_VIEWED` every time. `GET /evidence/{id}/download` (working copy) verifies, then streams from S3 through the API, and writes `EVIDENCE_DOWNLOADED`. AUDITOR cannot download.
- Case isolation: non-members (except SUPERVISOR and AUDITOR, who see all cases) get 403 and an `ACCESS_DENIED` audit entry.

### 6.8 RBAC (`security/permissions.py`, single source of truth)

Roles: ADMIN, SUPERVISOR, INVESTIGATOR, CUSTODIAN, AUDITOR. Every route declares its permission through one dependency; no ad-hoc role checks inside handlers. "Member" means a member of that case; SUPERVISOR and AUDITOR have implicit read access to all cases.

| Permission | ADMIN | SUPERVISOR | INVESTIGATOR | CUSTODIAN | AUDITOR |
|---|:-:|:-:|:-:|:-:|:-:|
| Manage users | yes | – | – | – | – |
| Create case | – | yes | yes | – | – |
| Manage case members | – | yes | lead only | – | – |
| View case and evidence metadata | – | yes (all) | member | member | yes (all) |
| Register evidence | – | – | member | member | – |
| Verify hash | – | yes | member | member | yes |
| Download working copy | – | member | member | member | – |
| Initiate transfer | – | – | current custodian | current custodian | – |
| Acknowledge receipt | – | – | designated receiver | designated receiver | – |
| Annotate, link, add people/events/notes | – | member | member | member | – |
| Decide approvals | – | yes (not own request) | – | – | – |
| Place legal hold | – | yes | – | – | – |
| Request export / hold release / disposal | – | yes | export only | – | – |
| Read audit log and verify chain | yes | yes | – | – | yes |
| Read / acknowledge alerts | – | yes | – | – | yes |
| Resolve alerts | – | yes | – | – | – |

ADMIN deliberately **cannot** read cases or evidence (separation of duties). One parametrized test must assert this entire matrix.

### 6.9 Dual authorization (`services/approvals.py`)

Sensitive actions: `EXTERNAL_TRANSFER, EXPORT_PACKAGE, LEGAL_HOLD_RELEASE, DISPOSAL`. The requester creates an `approval_request` with a justification; a **different** SUPERVISOR approves or rejects with a note. Enforced in three places: the service layer, the `CHECK` constraint in the database, and the UI (the approve button is disabled for your own requests with an explanatory tooltip). Requests expire after `APPROVAL_EXPIRY_HOURS` (scheduler marks `EXPIRED`). Executing an approved request writes `APPROVAL_EXECUTED` with both user IDs. The seed data must contain two supervisors so the demo works.

### 6.10 Collaboration and linking

Annotations (append-only, corrections are new annotations with `parent_annotation_id`), people, case events, case notes (append-only), and links connecting an evidence item to a person, event, note, or another evidence item. **Linking never touches `evidence_items`.** The case timeline (`GET /cases/{id}/timeline`) merges `case_events` with audit entries of that case (registrations, transfers, acknowledgements, annotations, approvals) in chronological order, each tagged by source.

### 6.11 Alerts (`services/anomaly.py`) — explainable rules only, no ML

Each alert has `rule`, `severity`, a human-readable `explanation` that states exactly what happened and which threshold was crossed, and `audit_seqs` pointing at the proving audit entries. `dedupe_key` prevents duplicates. Raising an alert writes `ALERT_RAISED`.

| Rule | Trigger | Severity |
|---|---|---|
| `HASH_MISMATCH` | any failed verification | CRITICAL |
| `OBJECT_REPLACED` | live object version differs from stored | HIGH |
| `CHAIN_BROKEN` | chain verification failure | CRITICAL |
| `CHECKPOINT_INVALID` | checkpoint signature or head hash invalid | CRITICAL |
| `MISSING_ACK` | transfer `PENDING_ACK` past `ack_due_at` | MEDIUM, HIGH after 2× SLA |
| `OFF_HOURS_ACCESS` | view/download outside `BUSINESS_HOURS_*` in `BUSINESS_TZ` | LOW |
| `BURST_ACCESS` | more than `BURST_VIEW_THRESHOLD` views/downloads by one user within `BURST_WINDOW_MINUTES` | MEDIUM |
| `REPEATED_DENIED` | `DENIED_ATTEMPTS_THRESHOLD` or more `ACCESS_DENIED` by one user within `DENIED_WINDOW_MINUTES` | HIGH |
| `LOGIN_LOCKOUT` | account locked after `LOGIN_MAX_FAILURES` failures | MEDIUM |

Synchronous rules (hash mismatch, denied attempts) run in the request path; periodic rules run in the scheduler every minute.

### 6.12 Custody report (`services/custody_report.py`)

`GET /evidence/{id}/custody-report?format=json|pdf`. Contents: evidence summary, chronological list of **every** audit entry for the evidence (seq, UTC time, actor name and role, action, readable detail, `prev_hash`, `entry_hash`), transfers, annotations, links, and an **integrity block** containing: result of the full-chain verification at generation time, the three-way verification result, the nearest signed checkpoint (created on demand so it covers the last included entry), and the highest `seq` covered. The JSON body is canonicalized, hashed with SHA-256 (`report_sha256`) and signed with Ed25519. The PDF prints the same data, the report hash, the signature fragment, and a QR to `/verify-report`. Generating a report writes `CUSTODY_REPORT_GENERATED`.
`POST /reports/verify` accepts a previously issued report JSON and returns: signature valid, report hash valid, and whether each included audit entry still matches the live chain.

### 6.13 Legal hold and retention (`services/retention.py`)

- Hold can be placed on a case or an evidence item by a SUPERVISOR with a reason. **Release needs dual authorization.** A hold blocks disposal everywhere and shows as a `LEGAL HOLD` chip.
- Retention policies (seed: Standard 5y, Extended 10y, Short 90d for demo). `retention_until` is set at intake. The retention page lists items due within 90 days and past due.
- **Disposal** (`DISPOSAL` approval): only if `retention_until` has passed **and** no hold (case or item). Execution deletes all versions of the object using the disposer credentials, sets `status=DISPOSED`, `disposed_at`, and writes `EVIDENCE_DISPOSED` with the SHA-256 retained forever as a tombstone. Metadata and audit trail are never deleted.

### 6.14 Export package (`services/export_package.py`)

Flow: `POST /evidence/{id}/exports` {justification, include_bsa_certificate, encrypt} → `EXPORT_PACKAGE` approval → after a different SUPERVISOR approves, the requester calls `POST /exports/{id}/build` (optional `passphrase` in the body, used for AES-256 ZIP via pyzipper and **never stored**). The build verifies the evidence first, assembles the package, uploads it to the exports bucket, records `package_sha256`, and writes `EXPORT_PACKAGE_BUILT`. `GET /exports/{id}/download` re-hashes the stored package, streams it, and writes `EXPORT_PACKAGE_DOWNLOADED`.

```
SEALTRAIL-EXPORT-<evidence_number>-<UTC timestamp>.zip
├── evidence/<original_filename>
├── manifest.json            # evidence metadata, SHA-256, size, approvals (requester, approver, justification),
│                            # audit entries with hashes, chain head, checkpoint + signature, public key id
├── manifest.sig             # Ed25519 signature over the canonical manifest, base64
├── custody_report.json
├── custody_report.pdf
├── BSA_s63_certificate_DRAFT.pdf   # optional, 6.15
├── SHA256SUMS.txt
├── PUBLIC_KEY.pem
├── verify.py                # standalone verifier (copy of templates/verify_package.py)
└── README.txt               # plain-language: what this is and how to verify it
```

`verify.py` (Python 3 standard library only for hashing and chain checks; signature check uses `cryptography` if installed and otherwise says clearly that the signature step was skipped): recomputes the SHA-256 of the evidence and every file in `SHA256SUMS.txt`, recomputes the hash chain over the included audit entries and checks each link, compares the manifest hash with the report hash, and verifies the Ed25519 signature. Output is a short PASS/FAIL list per check with a non-zero exit code on any failure. It must work with no network access.

### 6.15 Section 63 BSA certificate (draft, India) — `services/bsa_certificate.py`

Section 63(4)(c) of the Bharatiya Sakshya Adhiniyam, 2023 requires a certificate in the form prescribed in the Schedule: Part A is completed by the party (including the **hash value** of the electronic record) and Part B by an expert. Fetch the Schedule's text from an official source (India Code or the Gazette) and reproduce the prescribed headings and static text **verbatim**; auto-fill only the factual fields SealTrail knows (record description, device/source details, acquisition details, hash algorithm SHA-256 and hash value, date and time). Leave declarations and signature blocks blank. Footer on every page: "Auto-filled draft generated by SealTrail. To be reviewed, completed and signed by the responsible person (Part A) and the expert (Part B). Not legal advice." If you cannot retrieve the official text, **do not invent it**: skip this feature, say so in `KNOWN_LIMITATIONS.md`. Writes `BSA_CERTIFICATE_GENERATED`.

### 6.16 Authentication

argon2id password hashing, password policy (`PASSWORD_MIN_LENGTH`, at least one letter and one digit), JWT access token (HS256, `JWT_ACCESS_MINUTES`) returned in the response body and kept **in memory** by the frontend, and a rotating refresh token in an `httpOnly`, `SameSite=Lax`, `Secure` (when `COOKIE_SECURE=true`) cookie. Lockout after `LOGIN_MAX_FAILURES` consecutive failures for `LOGIN_LOCKOUT_MINUTES`. Login route rate-limited with slowapi (10/minute per IP). Generic "invalid credentials" message (no account enumeration). All auth events audited.

---

## 7. API surface (all under `/api/v1`, JSON, cursor or page based pagination)

```
Auth        POST /auth/login | /auth/refresh | /auth/logout        GET /auth/me
Users       GET /users   POST /users   PATCH /users/{id}                         (ADMIN)
Cases       GET /cases   POST /cases   GET /cases/{id}   POST /cases/{id}/close
            GET|POST /cases/{id}/members   DELETE /cases/{id}/members/{user_id}
            GET /cases/{id}/timeline
Evidence    GET /evidence  (server-side page, page_size, sort, order, filters, q)
            GET /evidence/export.csv   (metadata only, audited, role-limited)
            POST /cases/{id}/evidence   GET /evidence/{id}   GET /evidence/by-number/{number}
            POST /evidence/{id}/verify   GET /evidence/{id}/download
            POST /evidence/{id}/label?size=standard|small
            GET /evidence/{id}/custody   (audit trail for this item)
            GET|POST /evidence/{id}/annotations
            GET|POST /evidence/{id}/links   POST /evidence/{id}/links/{link_id}/revoke
            POST /evidence/{id}/legal-hold
Case data   GET|POST /cases/{id}/people | /cases/{id}/events | /cases/{id}/notes
Transfers   POST /evidence/{id}/transfers   GET /transfers?status=&mine=
            POST /transfers/{id}/acknowledge | /reject | /cancel
Approvals   GET /approvals?status=&mine=   POST /approvals/{id}/approve | /reject | /cancel
Audit       GET /audit  (filters: actor, action, case, evidence, from, to; paged by seq)
            POST /audit/verify   GET /audit/checkpoints   POST /audit/checkpoints
Integrity   POST /integrity/evidence-sweep   GET /integrity/runs/{id}
Alerts      GET /alerts   POST /alerts/{id}/acknowledge | /resolve
Reports     GET /evidence/{id}/custody-report   POST /reports/verify
Exports     POST /evidence/{id}/exports   POST /exports/{id}/build   GET /exports/{id}/download
Retention   GET|POST /retention/policies   GET /retention/due   POST /evidence/{id}/disposal
Dashboard   GET /dashboard/summary
Health      GET /healthz   GET /readyz  (db + storage + chain status)
```

Export `docs/openapi.json` from the running backend after Stage 2 and again after the last backend stage. The frontend generates its types from it (`npm run gen:api`).

---

## 8. Frontend specification

**Fidelity target:** the screenshot at `docs/reference/ui-reference.png` is the ground truth for look and layout. Reproduce its structure, density, spacing, typography and colors as closely as possible. **Do not copy the brand:** the screenshot shows another company's product. Use the SealTrail name and a simple original wordmark (a small hexagon/seal glyph in SVG plus "SEALTRAIL" and the tagline "Prove it hasn't changed"). Footer reads `© 2026 SealTrail`. Do not reuse the screenshot's names, emails, or lorem ipsum.

### 8.1 Design tokens (estimates; sample the real colors from the screenshot and adjust)

Dark theme is the default; a light theme exists behind the sun/moon switch (preference stored in `localStorage`, which is acceptable for a UI preference).

| Token | Dark | Light |
|---|---|---|
| App background | `#212121` | `#f4f5f7` |
| Sidebar background | `#1a1a1a` | `#ffffff` |
| Surface / table card | `#2a2a2a` | `#ffffff` |
| Table header row | `#2f2f2f` | `#eef0f3` |
| Expanded details panel | `#333333` | `#f7f8fa` |
| Border / divider | `#3b3b3b` | `#dfe3e8` |
| Primary (button, links) | `#3f7fe0` | `#1f63c9` |
| Case number green | `#5cb867` | `#2e7d32` |
| Needs-attention orange | `#f5a623` | `#b36b00` |
| Danger | `#ef5350` | `#c62828` |
| Text primary / secondary | `#e6e6e6` / `#a0a0a0` | `#1c2430` / `#5f6b7a` |

Typography: Roboto (self-hosted via `@fontsource/roboto`, no external font CDN), base 14 px, page title 24 px / 500, labels 12–13 px, hashes in a monospace stack. Dense rows (~34 px). Corner radius 2–4 px. No shadows except a subtle one on menus and dialogs.

### 8.2 Shell (match the screenshot)

- Fixed left sidebar, 232 px wide: brand block (≈85 px tall, bottom border), then collapsible nav groups each with an icon, label and chevron; children are indented, the active child has a full-width highlighted row. Group/children:
  - **Dashboard** → Overview
  - **Case Management** → Cases, Approvals
  - **Evidence Management** → Evidence Items, Transfers, Item Locations (custodian and location overview)
  - **People** → People Directory
  - **Audit & Reporting** → Audit Log, Integrity, Alerts, Reports
  - **Compliance** → Legal Holds, Retention & Disposal
  - **User Management** → Users (ADMIN only)
  - **Settings** → Profile
- Nav items a role cannot use are **hidden**, not disabled.
- Sidebar footer: the sun/moon theme switch, then the user block: name, email, and blue **Log Out** and **Profile** text links.
- Main area: 24 px padding; page title (24 px), muted subtitle (`Total N`), toolbar row, content card, footer line right-aligned (`© 2026 SealTrail`).

### 8.3 Evidence Items page (the page that must look like the screenshot)

- Toolbar: blue filled **+ Create Evidence** button; an outlined page-size dropdown (`25 / 50 / 100 / 500 Items ▾`); right-aligned icon buttons — download CSV (metadata, audited), clear filters, toggle column filters, refresh, column chooser — and an underlined **Search Evidence** field. **Every icon must work.**
- Table (server-side pagination, sorting and filtering): leading expand chevron; columns **Evidence Number** (blue link), **Case Number** (green link), **Case Name**, **Intake Date**, **Type**, **Brand**, **Item Name**, **Progress** (maps to status), **Current Location** (custodian name or location). Optional columns in the chooser: SHA-256 (short), Integrity, Collected By, Retention Until. Sortable headers show a sort arrow and a filter icon exactly as in the screenshot; filters open a small popover (text, select, or date range).
- Evidence number color: blue normally, **orange** when the item needs attention (pending acknowledgement, overdue, or an open alert), **red** when integrity is not OK. A small `LEGAL HOLD` chip appears next to held items.
- **Expanded row** = the *EVIDENCE DETAILS* panel, laid out as in the screenshot: header with **Print Label ▾** and **Actions ▾** as blue text links on the right; a two-column key/value grid; then a **DESCRIPTION** block. Fields: Evidence Number, Type, Item Name, Unique ID | S/N, Parent Evidence, Intake Date, Linked Contacts, Case, Brand, Model, Size, Progress, Source, Current Location, plus SHA-256 (full, monospace, copy button), Integrity (chip with last verified time), Collected By and date, Acquisition method and tool, Retention Until, Legal Hold. Beneath it, compact tabs: **Custody Trail** (chronological list from `/evidence/{id}/custody`), **Annotations**, **Links**, **Transfers**.
- Expanding a row calls `GET /evidence/{id}` (which audits `EVIDENCE_VIEWED`); cache the result per expansion so re-rendering does not re-log.
- **Print Label ▾:** Standard (90×50 mm), Small tag (50×25 mm) → opens the PDF.
- **Actions ▾** (items disabled with an explanatory tooltip when the role or state does not allow them): Verify hash, Transfer custody…, Acknowledge receipt, Download working copy, Add annotation…, Link to person / event / note…, Request export package…, Place legal hold…, Request hold release…, Custody report (PDF), Custody report (JSON), Request disposal….
- **Create Evidence** dialog, 3 steps: (1) case and type; (2) source and collector (collector defaults to the current user, collection date/time, source description, device make/model/serial, acquisition method/tool, parent evidence, description); (3) file — drag and drop, **client-side SHA-256 computed incrementally with hash-wasm with a progress bar**, then upload progress, then a result card showing the evidence number, server hash, matched client hash, read-back verification, and a **Print label** button.

### 8.4 Other pages

- **Login:** same dark style, centered card, no marketing copy.
- **Dashboard (Overview):** stat cards (open cases, evidence items, pending acknowledgements for me, open alerts), a **Chain status** card (green "Chain intact — N entries, head `abcd1234…`, verified 2 min ago" or red "Chain broken at #N: reason") with a Verify now button, my pending approvals, my pending acknowledgements, recent activity.
- **Cases:** table with the same style; case detail has tabs **Overview, Evidence, People, Events & Notes, Timeline, Members**. Timeline is a vertical chronological feed with source tags (Event, Registered, Transfer, Acknowledged, Annotation, Approval).
- **Approvals:** two tabs, *For my decision* and *My requests*. Each row shows kind, evidence, requester, justification, age. Approve/Reject open a dialog requiring a note. Approve is disabled on your own requests with a tooltip.
- **Transfers:** list with status filter; acknowledge and reject actions for the receiver; overdue rows highlighted orange.
- **Audit Log:** a status banner at the top (green intact / red broken), a **Verify chain** button with progress and a result panel naming the first broken entry and reason; table with seq, UTC time, actor, role, action chip, case, evidence number, short `prev_hash` and `entry_hash` (monospace, copyable). Clicking a row opens a side drawer with the full canonical JSON and the recomputed hash side-by-side. Checkpoints listed with signature status.
- **Integrity:** two actions — Verify audit chain, and **Verify all evidence** (sweep with live progress and a results table that links failures to the item).
- **Alerts:** table with severity chips, rule, explanation, linked evidence; Acknowledge and Resolve (with note).
- **Reports:** pick an evidence item → generate JSON/PDF custody report; a **Verify a report** card where you upload a previously issued JSON and get a clear pass/fail.
- **Legal Holds / Retention & Disposal:** holds list with place/release (release creates an approval); retention policies; items due or past due; disposal requests.
- **Users (ADMIN):** list, create, change role, deactivate.
- **Route `/e/:evidenceNumber`** (target of label QR codes): validates the check character, looks the item up, and opens it in the Evidence Items page (auth required).

### 8.5 Frontend engineering rules

TanStack Query for all server state; one `api` client wrapper that attaches the in-memory token, performs one silent refresh on 401, and surfaces `request_id` from the error envelope in a snackbar. Route guards by role. Mutations invalidate the right queries. No `any`. Components small and typed. Optimistic updates are not used for anything that writes to the audit log.

---

## 9. Seed data and demo scripts

All seeded data is **synthetic** and says so in the README. `backend/scripts/seed.py` goes through the real service layer (real hashing, real S3 uploads, real audit entries). It is safe to re-run: if any case already exists, it prints a message and exits without changing anything.

- **Users** (`@{SEED_EMAIL_DOMAIN}`, password `SEED_PASSWORD`): `admin`, `supervisor1`, `supervisor2`, `investigator1`, `investigator2`, `custodian1`, `auditor1` with realistic names.
- **Cases (3):** a UPI mule-account fraud case, an insider data-leak case at a textile exporter, a ransomware incident at a district hospital IT department — each with members, people, events and notes.
- **Evidence (~24 items)** with small real files generated programmatically (CSV bank-statement extracts, JSON chat exports, PNG screenshots via Pillow, a 2 MB random-bytes `.dd` standing in for a disk image, text logs). Seeded with simulated timestamps spread over the previous 14 days, using the real code paths.
- **States to include:** several clean custody trails with 2–5 events; one transfer waiting for acknowledgement; one **overdue** acknowledgement; one external transfer waiting for dual approval; one item under legal hold; one item past retention and eligible for disposal; one off-hours view; a few annotations; links between evidence, people and events.
- After seeding: run the alert rules once, create a checkpoint, and confirm `verify_chain` is clean. The script prints a summary table.

`backend/scripts/tamper_demo.py` — the live attack, host-side, using `DATABASE_URL_SUPERUSER_HOST` and `S3_ENDPOINT_URL_HOST` with root credentials (clearly labeled as a simulated malicious administrator):

- `python tamper_demo.py audit --seq N`: as superuser, set `session_replication_role = replica` (bypasses triggers) and edit that audit row's payload. Then verify in the UI/API: chain breaks at `N`.
- `python tamper_demo.py audit-rewrite --from-seq N`: recompute a *fully consistent* chain from `N` onward (the sophisticated attacker). Verification must still fail on the **checkpoint signature / head hash** — this is the demo's strongest moment.
- `python tamper_demo.py object --evidence EV-NUMBER`: overwrite the S3 object in place with altered bytes (creates a new version). Verification reports `OBJECT_REPLACED`, shows the original version is intact, and raises an alert.
- `python tamper_demo.py evidence-hash --evidence EV-NUMBER`: change `evidence_items.sha256` directly. Verification reports the mismatch with the audit binding and the object.
- `python tamper_demo.py restore`: undo the above (re-insert original audit payloads from a saved backup file, restore the original object version, restore the hash) so the demo can be repeated. The script saves the backup before each attack.

Each command prints exactly what it is doing and refuses to run unless `APP_ENV=development`.

---

## 10. Hardening checklist (Stage 10)

S3 service users with delete denied (disposal uses the disposer user only) · rate limit on login and on expensive endpoints (verify, sweep, export) · request size limits · filename sanitization (strip path components, control characters; store the original name as metadata only) · `Content-Disposition` set safely on downloads · CORS restricted to `CORS_ORIGINS` · structured JSON logs with request IDs and no sensitive fields · security headers via nginx · `/readyz` checks Postgres, S3 and chain state · graceful startup ordering via healthchecks · non-root users in Dockerfiles · no debug mode in compose.

---

## 11. Testing and verification (must exist and pass)

Backend (`pytest`, against a throwaway database and bucket prefix on the compose Postgres and MinIO, using the same migrations and roles as production):

1. Chain: append, verify, concurrency (50 parallel appends keep a strictly linear chain).
2. DB enforcement as the **app role**: `UPDATE`, `DELETE`, `TRUNCATE` on the four append-only tables all raise; an immutable evidence column update raises; a chain-forking insert raises.
3. Tamper detection: edit a payload; delete a middle row; reorder rows; recompute the whole chain after an edit (must be caught by the checkpoint signature); forged checkpoint signature.
4. Intake: correct hash; `CLIENT_HASH_MISMATCH` rejection and its audit entry; oversize upload; read-back verification failure path; evidence number check character (valid, mistyped).
5. Three-way verification: object replaced out of band, row hash edited, both reported correctly.
6. Custody: internal transfer, external transfer needing approval, acknowledgement OK, acknowledgement with mismatch → `DISPUTED`, reject, cancel, only one open transfer per item.
7. Dual authorization: same user cannot approve at service level **and** at database level (raw insert attempt); non-supervisor cannot approve; expiry.
8. RBAC: the full matrix in 6.8, parametrized; ADMIN cannot read evidence; non-member gets 403 with an `ACCESS_DENIED` audit entry.
9. Alerts: each rule in 6.11 fires once (dedupe) with a correct explanation.
10. Report: signature valid; altering any entry makes `POST /reports/verify` fail.
11. Export: build a package, run its `verify.py` as a subprocess → exit 0; modify a file inside → exit non-zero. Encrypted ZIP opens only with the passphrase.
12. Retention: disposal blocked by hold and by unexpired retention; allowed after both clear; metadata and audit survive.
13. No API route can set `ts` on an audit entry.

Frontend: `npm run typecheck`, `npm run lint`, `npm run build` all clean. A written manual pass in `docs/QA_CHECKLIST.md` covering every page in both themes, each toolbar icon, every Actions menu item, and the three tamper demos, with screenshots compared against the reference.

Final end-to-end drill (Stage 11): `docker compose down -v && docker compose up --build -d`, seed, run the test suite, execute `DEMO_SCRIPT.md` start to finish, and confirm every step works.

---

## 12. Stages (execute in order; commit after each)

Each stage ends with its acceptance checks green, then `git add -A && git commit -m "<message>"`.

| Stage | Scope | Acceptance | Commit message |
|---|---|---|---|
| **0 Bootstrap** | Repo skeleton (Section 3), `.gitignore`, `.env.example`, compose with postgres, minio, minio-init, nginx, backend and frontend skeletons, healthchecks, `config.py` fail-fast, `gen_secrets.py` | `docker compose up --build -d` is healthy; `/healthz` returns 200; MinIO buckets exist with versioning; app S3 user cannot delete | `chore: bootstrap repo, compose stack, env template` |
| **1 Schema and chain** | All tables, roles, grants, triggers (5.1); `audit_chain.py`; `checkpoints.py`; `integrity_state`; tests 1–3 | Tests 1–3 pass; app role cannot mutate append-only tables | `feat(audit): append-only hash-chained audit log with signed checkpoints` |
| **2 Auth, RBAC, cases** | Users, auth (6.16), permissions matrix, case CRUD, members, error envelope, request IDs, structured logs; export `docs/openapi.json` | Test 8 (matrix) passes; login lockout works; every route audited | `feat(auth): authentication, RBAC matrix, cases and members` |
| **3 Evidence intake** | Storage service, intake pipeline (6.4), numbering (6.6), three-way verify (6.5), labels, evidence list/detail/download | Tests 4–5 pass; upload a real file through the API; label PDF renders with QR | `feat(evidence): hashed intake, three-way verification, controlled labels` |
| **4 Custody and collaboration** | Transfers (6.7), approvals engine (6.9), annotations, people, events, notes, links, timeline | Tests 6–7 pass | `feat(custody): transfers, acknowledgements, dual authorization, case collaboration` |
| **5 Integrity engine** | Scheduler, anomaly rules (6.11), alerts API, chain verify endpoint, evidence sweep, checkpoints job | Test 9 passes; scheduled chain check updates `integrity_state` | `feat(integrity): anomaly detection, alerts, chain verification and sweep` |
| **6 Reports and exports** | Custody report JSON/PDF + verify (6.12), export package + `verify.py` (6.14), BSA draft certificate (6.15) | Tests 10–11 pass | `feat(reporting): signed custody reports and verifiable export packages` |
| **7 Retention** | Legal hold, retention policies, disposal (6.13); export `docs/openapi.json` again | Test 12 passes | `feat(compliance): legal hold, retention and approved disposal` |
| **8 Frontend foundation** | Theme (both modes), shell and sidebar, auth, API client with generated types, shared table components, **Evidence Items page** matching the reference | Page compared with `ui-reference.png` in the browser at 1600 px width and visually matches layout, spacing, columns, toolbar, expandable details | `feat(ui): app shell, theming and evidence items page` |
| **9a Frontend workflows** | Create Evidence dialog (client hashing), all Actions menu flows, labels, transfers, approvals pages | Golden path works in the browser: register → transfer → acknowledge | `feat(ui): evidence intake, custody actions, approvals` |
| **9b Frontend oversight** | Dashboard, cases and case detail with timeline, audit log with chain verify, integrity, alerts, reports (+ report verify), retention and holds, users, `/e/:number` route | Chain verify shows red after a tamper script and green after restore | `feat(ui): dashboard, audit log, integrity, alerts, reports, compliance` |
| **10 Seed and hardening** | `seed.py`, `tamper_demo.py`, hardening list (Section 10), tests 13 and any remaining | Seed runs clean on an empty stack; chain verifies; every tamper command is detected; `restore` returns to green | `feat(demo): synthetic seed data, tamper simulator, hardening` |
| **11 Docs and final QA** | README, ARCHITECTURE (Mermaid), THREAT_MODEL, DECISIONS, KNOWN_LIMITATIONS, DEMO_SCRIPT, QA_CHECKLIST, `FILE_MAP_ACTUAL.md`; clean-slate drill (Section 11) | All checks green from a fresh `down -v`; tag `v1.0-hacknova` | `docs: architecture, threat model, demo script, QA` |

### Cut line (only if running out of time; cut in this order, record each in `KNOWN_LIMITATIONS.md`)

1. Section 63 BSA draft certificate (6.15) and AES-256 encrypted ZIP option.
2. `POST /reports/verify` and its UI card.
3. S3 delete-denied service users (fall back to the root user with a recorded limitation).
4. Light theme polish (the dark theme is the priority).
5. Evidence sweep live progress (a simple spinner and result list is acceptable).

**Never cut:** Stages 0–5, the custody report, a basic signed export package with `verify.py`, the Evidence Items page, Create Evidence with client hashing, transfer + acknowledge, approvals, the audit log page with chain verification, and `tamper_demo.py`. These are what wins the demo.

---

## 13. Documentation requirements

- **README.md:** what it is (2 sentences), prerequisites, three-command run, the seeded login table, ports, how to run tests, how to run the tamper demo, a note that all data is synthetic.
- **ARCHITECTURE.md:** Mermaid diagrams for (a) containers and network, (b) intake sequence, (c) transfer state machine, (d) the three-way integrity binding and chain-plus-checkpoint structure. Short, accurate prose.
- **THREAT_MODEL.md:** table of adversaries (curious insider, malicious investigator, malicious DBA, storage admin, external attacker, stolen signing key) × what we **prevent**, what we **detect**, what we **do not cover**. Honest.
- **DEMO_SCRIPT.md:** the exact five-minute click path and the tamper commands in order, with expected outputs.
- **FILE_MAP_ACTUAL.md:** the real final tree, one line of purpose per file, so the pitch document can be reconciled.
- Do **not** write marketing claims. Everything in the docs must be true of the code as built.

## 14. Final report (your last message)

Report: what was built per stage, test results (counts passed), anything cut and why, anything you could not verify, the exact commands to start the stack and run the demo, and the list of commits. Then list the technology stack that was actually used and what each piece is used for (only items that are in the code).
