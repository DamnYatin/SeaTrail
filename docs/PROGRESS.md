# Build Progress

| Metric | Status |
|--------|--------|
| Last verified stage | **Stage 10 Tamper simulator & hardening** |
| Current stage in progress | **Stage 11 Docs and final QA** |
| Passed tests | 18 backend tests passing + Frontend tsc, eslint, build passing |
| Known issues | Docker Compose CLI absent on Windows workstation; codebase designed with container-parity and verified with in-process test fixtures. |

## Completed Stages
- [x] **Stage 0 Bootstrap** (`e832363`): Repo layout, `.gitignore`, `.env.example`, Docker Compose, Postgres init, MinIO init, Nginx conf, backend and frontend skeletons, fail-fast configuration.
- [x] **Stage 1 Schema and chain** (`b813411`): Complete PostgreSQL data model, append-only triggers, chain insertion trigger, immutability trigger, `audit_chain.py`, `checkpoints.py` with Ed25519 signing, Tests 1–3 passing.
- [x] **Stage 2 Auth, RBAC, cases** (`82715b4`): Argon2id password hashing, lockout, JWT access & httpOnly refresh cookie, RBAC permissions matrix, case CRUD and members, Test 8 passing, `docs/openapi.json` exported.
- [x] **Stage 3 Evidence intake** (`9b015b6`): Storage service (S3/MinIO), streaming SHA-256 intake, Crockford base32 check character numbering, three-way verification (pinned, live, audit), controlled PDF labels with QR, Tests 4–5 passing.
- [x] **Stage 4 Custody and collaboration** (`bcf7e93`): Custody transfer state machine (internal, external), receipt acknowledgement re-verification, dual-authorization approvals engine, annotations, people, events, notes, links, timeline, Tests 6–7 passing.
- [x] **Stage 5 Integrity engine** (`f041d3b`): Anomaly detection rules engine (HASH_MISMATCH, OBJECT_REPLACED, CHAIN_BROKEN, CHECKPOINT_INVALID, MISSING_ACK, OFF_HOURS_ACCESS, BURST_ACCESS, REPEATED_DENIED) with deduplication and audit linking, in-process APScheduler background jobs, alerts REST API, chain verification endpoint with `integrity_state` caching, evidence verification sweep service and API, Test 9 passing.
- [x] **Stage 6 Reports and exports** (`12e56c0`): Cryptographically signed custody reports (JSON + ReportLab PDF with QR verification code and legal notice), offline report verification endpoint (`POST /reports/verify`), statutory Section 63 BSA draft certificate PDF, verifiable export package generation (`SEALTRAIL-EXPORT-*.zip`) with embedded offline verifier (`verify.py`), SHA256SUMS.txt, Ed25519 manifest signature, optional AES-256 ZIP encryption via pyzipper, Tests 10 and 11 passing.
- [x] **Stage 7 Retention** (`79ca4dd`): Legal hold placement on evidence and cases, dual-authorization hold release, retention policies (Standard 5y, Extended 10y, Short 90d), retention due listing, approved disposal with complete S3 object version deletion, status DISPOSED with permanent SHA-256 tombstone preserving complete audit trail, Test 12 passing, `docs/openapi.json` re-exported.
- [x] **Synthetic Seed Data** (`557628b`): Realistic synthetic dataset generated through service layer (7 users, 3 cases, 24 evidence items across formats, active transfers, overdue SLA alert, dual-authorization approvals, legal holds, annotations, entity links, signed checkpoint). `verify_chain` verified clean.
- [x] **Stage 8 Frontend foundation** (`e9de7c7`): MUI dark (#1e1e1e / #2d2d2d) and light themes, 232px sidebar navigation, responsive AppShell, full Evidence Items table matching reference design with pagination, search, column chooser, expandable row with metadata split, cryptographic SHA-256 integrity block, tabbed subpanels, status chips and hash text. Strict TypeScript, ESLint and production build passing.
- [x] **Stage 9a Frontend workflows** (`8774c2b`): Create Evidence dialog with chunked client-side hashing via hash-wasm (real-time progress bar), all Action menu flows (Transfer Custody, Acknowledge Receipt, Add Annotation, Create Defensible Link, Legal Hold placement/release request, Export Package request, PDF/JSON reports), Transfers Page with overdue SLA tracking and direct receipt acknowledgement, Approvals Page with dual-authorization two-person rule enforcement (self-approval blocked).
- [x] **Stage 9b Frontend oversight** (`feat(ui): dashboard, audit log, integrity, alerts, reports, compliance`): Dashboard with live chain status card and verification trigger, Cases management with merged chronological incident timeline, Audit log with side drawer canonical JSON inspection and Ed25519 checkpoints table, Integrity sweep and audit chain verify UI, Alerts page with acknowledge and resolution notes, Reports page with independent report verification card, Retention & disposal tracking, Users admin view, and QR code `/e/:evidenceNumber` check character resolution route.

- [x] **Stage 10 Tamper simulator & hardening** (`feat(demo): synthetic seed data, tamper simulator, hardening`): `backend/scripts/tamper_demo.py` multi-vector attack simulator implementing `audit`, `audit-rewrite`, `object`, `evidence-hash`, and `restore`. Test 13 ensuring immutability of audit timestamps across all API routes. Formatted and linted backend and frontend.

## Next Stages
- [ ] **Stage 11 Docs and final QA** (Architecture, threat model, demo script, QA checklist, final tag)
