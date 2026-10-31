# Build Progress

| Metric | Status |
|--------|--------|
| Last verified stage | **Stage 5 Integrity engine** |
| Current stage in progress | **Stage 6 Reports and exports** |
| Passed tests | 14 backend tests (Tests 1, 2, 3, 4, 5, 6, 7, 8, 9) |
| Known issues | Docker Compose CLI absent on Windows workstation; codebase designed with container-parity and verified with in-process test fixtures. |

## Completed Stages
- [x] **Stage 0 Bootstrap** (`e832363`): Repo layout, `.gitignore`, `.env.example`, Docker Compose, Postgres init, MinIO init, Nginx conf, backend and frontend skeletons, fail-fast configuration.
- [x] **Stage 1 Schema and chain** (`b813411`): Complete PostgreSQL data model, append-only triggers, chain insertion trigger, immutability trigger, `audit_chain.py`, `checkpoints.py` with Ed25519 signing, Tests 1–3 passing.
- [x] **Stage 2 Auth, RBAC, cases** (`82715b4`): Argon2id password hashing, lockout, JWT access & httpOnly refresh cookie, RBAC permissions matrix, case CRUD and members, Test 8 passing, `docs/openapi.json` exported.
- [x] **Stage 3 Evidence intake** (`9b015b6`): Storage service (S3/MinIO), streaming SHA-256 intake, Crockford base32 check character numbering, three-way verification (pinned, live, audit), controlled PDF labels with QR, Tests 4–5 passing.
- [x] **Stage 4 Custody and collaboration** (`bcf7e93`): Custody transfer state machine (internal, external), receipt acknowledgement re-verification, dual-authorization approvals engine, annotations, people, events, notes, links, timeline, Tests 6–7 passing.
- [x] **Stage 5 Integrity engine**: Anomaly detection rules engine (HASH_MISMATCH, OBJECT_REPLACED, CHAIN_BROKEN, CHECKPOINT_INVALID, MISSING_ACK, OFF_HOURS_ACCESS, BURST_ACCESS, REPEATED_DENIED) with deduplication and audit linking, in-process APScheduler background jobs, alerts REST API, chain verification endpoint with `integrity_state` caching, evidence verification sweep service and API, Test 9 passing.

## Next Stages
- [ ] **Stage 6 Reports and exports** (Custody report JSON/PDF + verify, export package with offline `verify.py`, draft Section 63 BSA certificate)
- [ ] **Stage 7 Retention** (Legal hold, retention policies, approved disposal)
- [ ] **Stage 8 Frontend foundation** (MUI theme, AppShell, Sidebar, Evidence Items table matching reference)
- [ ] **Stage 9a Frontend workflows** (Create Evidence dialog, actions menu, transfers, approvals)
- [ ] **Stage 9b Frontend oversight** (Dashboard, timeline, audit log, integrity, alerts, reports)
- [ ] **Stage 10 Seed and hardening** (Seed data, live tamper demo script, security hardening)
- [ ] **Stage 11 Docs and final QA** (Architecture, threat model, demo script, QA checklist, final tag)
