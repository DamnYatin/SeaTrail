# SealTrail Actual Codebase File Map

Generated at the completion of Stage 11. This map lists all repository files (excluding `.git/`, `.venv/`, `node_modules/`, `dist/`, and cache directories) with a one-line description of their purpose.

## Root Configuration & Specifications
- `AGENTS.md`: Full build specification, rules, mandated stack, data model, stages, and acceptance criteria.
- `README.md`: Project summary, architecture, prerequisites, quickstart, synthetic login accounts, and testing guide.
- `docker-compose.yml`: Multi-container topology for PostgreSQL 16, MinIO, FastAPI backend, and Nginx frontend.
- `.env.example`: Template of required environment variables and secrets (unpopulated).
- `.gitignore`: Git exclusion rules for secrets, local volumes, virtualenvs, dependencies, and build artifacts.

## Documentation (`docs/`)
- `docs/ARCHITECTURE.md`: System topology, container network, data flows, state machines, and trust boundary diagrams.
- `docs/DECISIONS.md`: Architectural decision records log detailing rationale and technical choices.
- `docs/DEMO_SCRIPT.md`: Step-by-step 5-minute live demonstration script for hackathon presentation and evaluation.
- `docs/KNOWN_LIMITATIONS.md`: Explicit documentation of system boundaries, non-covered threats, and trade-offs.
- `docs/PITCH.md`: Business value proposition, legal context (Section 63 BSA 2023), and product positioning.
- `docs/PROGRESS.md`: Stage verification status, test pass counts, and active build state.
- `docs/QA_CHECKLIST.md`: Comprehensive manual browser verification matrix across all UI pages and workflows.
- `docs/THREAT_MODEL.md`: Adversary personas, attack vectors, defensive mechanisms, and PREVENTED/DETECTED matrix.
- `docs/openapi.json`: OpenAPI 3.1 specification exported from the running FastAPI backend.
- `docs/FILE_MAP_ACTUAL.md`: This file; comprehensive file map with one-line descriptions.
- `docs/reference/ui-reference.png`: Ground-truth dark-theme forensic reference screenshot.

## Infrastructure Configuration (`infra/`)
- `infra/postgres/init/01-roles-and-extensions.sh`: Postgres init script provisioning least-privilege `app_user` and `owner_user` roles.
- `infra/minio/init.sh`: MinIO bucket provisioning script configuring bucket versioning and IAM access policies.
- `infra/nginx/nginx.conf`: Nginx reverse-proxy configuration enforcing security headers, proxy timeouts, and SPA routing.

## Backend Application (`backend/`)
- `backend/Dockerfile`: Multi-stage Docker container build for the FastAPI backend.
- `backend/entrypoint.sh`: Container entrypoint running migrations, generating secret fallbacks, and starting Uvicorn.
- `backend/pyproject.toml`: Python project configuration, dependencies, and Ruff linter/formatter rules.
- `backend/requirements.txt`: Pinned Python dependencies.
- `backend/alembic.ini`: Database migration configuration for Alembic.
- `backend/alembic/env.py`: Alembic migration environment executing DDL and triggers as `owner_user`.
- `backend/alembic/versions/0001_initial_schema_and_triggers.py`: Raw-SQL migration establishing tables, triggers, and append-only rules.

### Backend Application Code (`backend/app/`)
- `backend/app/main.py`: FastAPI application factory, lifespan event handler (scheduler startup), middleware, and routers.
- `backend/app/config.py`: Pydantic-settings configuration loader with fail-fast validation for secrets and environment variables.
- `backend/app/db.py`: SQLAlchemy database engines, scoped session factories, and connection helpers.
- `backend/app/deps.py`: FastAPI dependency injectors for authentication, user extraction, RBAC authorization, and case access.
- `backend/app/errors.py`: Standardized API exception classes and centralized JSON error envelope handler.
- `backend/app/logging.py`: Structured JSON logger with request ID tracing and secret redaction.

### Security Subsystem (`backend/app/security/`)
- `backend/app/security/passwords.py`: Argon2id password hashing, verification, and complexity policy validation.
- `backend/app/security/permissions.py`: Single-source-of-truth RBAC matrix defining Roles and granular Permissions.
- `backend/app/security/tokens.py`: JWT access token and refresh token generation, decoding, and cookie handling.

### Database Models (`backend/app/models/`)
- `backend/app/models/alerts.py`: SQLAlchemy models for anomaly alerts, severity enums, and resolution status.
- `backend/app/models/approvals.py`: SQLAlchemy models for two-person dual-authorization requests and decision constraints.
- `backend/app/models/audit.py`: SQLAlchemy models for append-only audit ledger entries and Ed25519 checkpoints.
- `backend/app/models/cases.py`: SQLAlchemy models for forensic cases, classifications, and case membership.
- `backend/app/models/custody.py`: SQLAlchemy models for custody transfer state machines and acknowledgements.
- `backend/app/models/evidence.py`: SQLAlchemy models for immutable evidence items, hashing, and storage locations.
- `backend/app/models/exports.py`: SQLAlchemy models for court-defensible export packages and download counters.
- `backend/app/models/integrity.py`: SQLAlchemy models for singleton integrity state and evidence verification sweep runs.
- `backend/app/models/links.py`: SQLAlchemy models for annotations, persons, case events, notes, and entity links.
- `backend/app/models/users.py`: SQLAlchemy models for user accounts, lockout tracking, and roles.

### API Schemas (`backend/app/schemas/`)
- `backend/app/schemas/alerts.py`: Pydantic request/response schemas for anomaly alerts and resolutions.
- `backend/app/schemas/approvals.py`: Pydantic request/response schemas for approval workflows and decisions.
- `backend/app/schemas/audit.py`: Pydantic schemas for audit trail queries, canonical forms, and verification results.
- `backend/app/schemas/auth.py`: Pydantic schemas for login, tokens, password change, and session state.
- `backend/app/schemas/cases.py`: Pydantic schemas for case creation, member management, and updates.
- `backend/app/schemas/collaboration.py`: Pydantic schemas for annotations, people, case events, notes, and links.
- `backend/app/schemas/custody.py`: Pydantic schemas for custody transfer initiation and receipt acknowledgement.
- `backend/app/schemas/evidence.py`: Pydantic schemas for evidence intake, verification info, and metadata.
- `backend/app/schemas/exports.py`: Pydantic schemas for export package requests and download metadata.
- `backend/app/schemas/reports.py`: Pydantic schemas for signed custody report requests and verification.
- `backend/app/schemas/retention.py`: Pydantic schemas for retention policies, legal holds, and disposal requests.
- `backend/app/schemas/users.py`: Pydantic schemas for user administration, profile updates, and role assignment.

### API Routers (`backend/app/routers/`)
- `backend/app/routers/alerts.py`: REST endpoints for listing, filtering, acknowledging, and resolving security alerts.
- `backend/app/routers/approvals.py`: REST endpoints for managing the dual-authorization approval queue.
- `backend/app/routers/audit.py`: REST endpoints for viewing the audit log, inspecting JSON, and running chain verification.
- `backend/app/routers/auth.py`: REST endpoints for user authentication, token refresh, and profile inspection.
- `backend/app/routers/cases.py`: REST endpoints for case creation, metadata updates, member assignment, and timelines.
- `backend/app/routers/custody.py`: REST endpoints for initiating custody transfers and acknowledging receipt.
- `backend/app/routers/evidence.py`: REST endpoints for streaming evidence intake, downloads, verification, and label printing.
- `backend/app/routers/exports.py`: REST endpoints for generating court-defensible export packages.
- `backend/app/routers/health.py`: REST healthcheck endpoint reporting database, storage, and scheduler readiness.
- `backend/app/routers/integrity.py`: REST endpoints for triggering and inspecting background evidence sweeps.
- `backend/app/routers/links.py`: REST endpoints for adding annotations, people, events, notes, and entity links.
- `backend/app/routers/reports.py`: REST endpoints for generating signed custody reports and verifying report authenticity.
- `backend/app/routers/retention.py`: REST endpoints for retention policy management, legal holds, and disposal.
- `backend/app/routers/users.py`: REST endpoints for administrative user CRUD and account unlocking.

### Core Services (`backend/app/services/`)
- `backend/app/services/anomaly.py`: Deterministic rules engine detecting hash mismatches, burst access, and SLA violations.
- `backend/app/services/approvals.py`: Dual-authorization engine enforcing two-person rules and expiration logic.
- `backend/app/services/audit_chain.py`: Canonical JSON serialization, advisory locking, chain verification, and append operations.
- `backend/app/services/bsa_certificate.py`: Statutory Section 63 BSA (Schedule Part A/B) ReportLab PDF certificate generator.
- `backend/app/services/checkpoints.py`: Ed25519 digital signature signing and verification over audit chain heads.
- `backend/app/services/custody.py`: Custody transfer state machine managing handoffs and hash re-verification.
- `backend/app/services/custody_report.py`: Cryptographically signed JSON and PDF custody report generator.
- `backend/app/services/evidence_ids.py`: Case-scoped evidence numbering with Crockford Base32 check characters.
- `backend/app/services/export_package.py`: Defensible ZIP packaging engine with AES-256 encryption and embedded verifier.
- `backend/app/services/hashing.py`: Chunked SHA-256 stream calculation helpers.
- `backend/app/services/intake.py`: Dual-hash intake pipeline streaming raw bytes to S3 and pinning to the audit ledger.
- `backend/app/services/integrity.py`: Three-way integrity binding verification and background batch sweep engine.
- `backend/app/services/labels.py`: Printable ReportLab PDF label generator with QR code and tracking metadata.
- `backend/app/services/retention.py`: Retention policy evaluation, legal hold enforcement, and approved S3 object disposal.
- `backend/app/services/storage.py`: Boto3 S3 client wrapper handling versioned put, get, head, and delete operations.

### Background Jobs & Templates (`backend/app/jobs/`, `backend/app/templates/`)
- `backend/app/jobs/scheduler.py`: In-process APScheduler background service for periodic checkpoints and SLA sweeps.
- `backend/app/templates/verify_package.py`: Standalone offline verification script packaged into every export ZIP as `verify.py`.

### Scripts (`backend/scripts/`)
- `backend/scripts/gen_secrets.py`: Generates cryptographic secrets, passwords, and Ed25519 keypairs in `.env`.
- `backend/scripts/seed.py`: Populates realistic forensic cases, evidence, custody transfers, and audit logs via the service layer.
- `backend/scripts/tamper_demo.py`: Multi-vector attack simulation script (`audit`, `audit-rewrite`, `object`, `evidence-hash`, `restore`).

### Automated Test Suite (`backend/tests/`)
- `backend/tests/conftest.py`: Pytest test fixtures providing isolated SQLite/Postgres test sessions and API test clients.
- `backend/tests/test_audit_chain_and_enforcement.py`: Tests 1–3, 13: audit append, database triggers, checkpoint signing, API timestamp immutability.
- `backend/tests/test_rbac_matrix.py`: Test 8: RBAC permissions matrix, case isolation, and login lockout.
- `backend/tests/test_evidence_intake_and_integrity.py`: Tests 4–5: streaming hashed intake, three-way verification, PDF labels.
- `backend/tests/test_custody_and_approvals.py`: Tests 6–7: custody transfer state machine, SLA ack, dual authorization two-person rule.
- `backend/tests/test_integrity_engine_and_alerts.py`: Test 9: explainable anomaly alerts, evidence sweep, chain verification.
- `backend/tests/test_reports_and_exports.py`: Tests 10–11: signed custody reports, Section 63 BSA certificate, export package offline verifier.
- `backend/tests/test_retention.py`: Test 12: retention policies, legal hold blocking, approved S3 object disposal with audit preservation.

## Frontend Single-Page Application (`frontend/`)
- `frontend/package.json`: NPM package manifest, scripts, and dependencies (MUI v5, React 18, TanStack Query v5, Vite).
- `frontend/vite.config.ts`: Vite bundler configuration with proxy rules routing `/api/` to the FastAPI backend.
- `frontend/tsconfig.json`: TypeScript compiler configuration in strict mode.
- `frontend/.eslintrc.cjs`: ESLint static analysis rules.
- `frontend/Dockerfile`: Multi-stage Docker build packaging the compiled React SPA into Nginx.
- `frontend/index.html`: HTML entrypoint with viewport metadata and web fonts.

### Frontend Application Code (`frontend/src/`)
- `frontend/src/main.tsx`: React application entrypoint mounting root providers.
- `frontend/src/App.tsx`: Top-level application component configuring theme, QueryClient, and React Router routes.
- `frontend/src/theme.ts`: Custom MUI v5 forensic theme definitions supporting dark (#1e1e1e) and light modes.
- `frontend/src/api/client.ts`: Typed API client wrapper built with `openapi-fetch` and authentication interceptors.
- `frontend/src/api/schema.d.ts`: Generated TypeScript types reflecting backend schemas from `docs/openapi.json`.
- `frontend/src/auth/AuthContext.tsx`: Authentication provider managing user login state, JWT tokens, and user roles.
- `frontend/src/auth/ProtectedRoute.tsx`: Route guard enforcing authentication and role-based route permissions.

### UI Layout & Shared Components (`frontend/src/layout/`, `frontend/src/components/`)
- `frontend/src/layout/AppShell.tsx`: Primary application layout providing topbar, theme switcher, and navigation drawer.
- `frontend/src/layout/Sidebar.tsx`: Fixed 232px forensic navigation sidebar with badge counters and role indicators.
- `frontend/src/components/AcknowledgeTransferDialog.tsx`: Dialog modal for acknowledging receipt of evidence with hash verification.
- `frontend/src/components/AddAnnotationDialog.tsx`: Dialog modal for appending immutable forensic annotations to evidence.
- `frontend/src/components/BrandGlyph.tsx`: Vector SVG logo glyph representing the SealTrail tamper-evident shield.
- `frontend/src/components/CreateEvidenceDialog.tsx`: Multi-step evidence intake modal with client-side SHA-256 progress via `hash-wasm`.
- `frontend/src/components/CreateLinkDialog.tsx`: Dialog modal for creating defensible relationships between evidence and entities.
- `frontend/src/components/ExportPackageDialog.tsx`: Dialog modal for requesting verifiable courtroom export packages.
- `frontend/src/components/HashText.tsx`: Cryptographic hash display component with monospace font and copy-to-clipboard button.
- `frontend/src/components/LegalHoldDialog.tsx`: Dialog modal for applying legal holds or requesting dual-authorization release.
- `frontend/src/components/StatusChip.tsx`: Styled color-coded status chip indicating evidence integrity and transfer states.
- `frontend/src/components/TransferCustodyDialog.tsx`: Dialog modal for initiating internal transfers or external dual-auth transfers.

### Client Libraries (`frontend/src/lib/`)
- `frontend/src/lib/hashing.ts`: Incremental chunked SHA-256 calculation worker wrapper utilizing `hash-wasm`.

### Application Pages (`frontend/src/pages/`)
- `frontend/src/pages/AlertsPage.tsx`: Security anomaly alerts management page with acknowledge and resolution notes.
- `frontend/src/pages/ApprovalsPage.tsx`: Two-person rule dual-authorization approval queue for supervisors.
- `frontend/src/pages/AuditLogPage.tsx`: Append-only audit log browser with canonical JSON drawer and Ed25519 checkpoints.
- `frontend/src/pages/CasesPage.tsx`: Case management view with case details and merged chronological incident timeline.
- `frontend/src/pages/DashboardPage.tsx`: High-level operational dashboard with chain status card, metrics, and active alerts.
- `frontend/src/pages/EvidenceLookupPage.tsx`: Direct QR code resolution route (`/e/:evidenceNumber`) validating check characters.
- `frontend/src/pages/EvidencePage.tsx`: Primary Evidence Items table matching reference design with expandable detail rows.
- `frontend/src/pages/IntegrityPage.tsx`: Integrity sweep controls, chain verification triggering, and sweep history.
- `frontend/src/pages/LoginPage.tsx`: Secure analyst login form with lockout detection and credentials handling.
- `frontend/src/pages/PlaceholderPage.tsx`: Fallback route page for non-implemented secondary views.
- `frontend/src/pages/ReportsPage.tsx`: Custody reports generator and offline report verification card.
- `frontend/src/pages/RetentionPage.tsx`: Retention policies, upcoming retention expirations, and approved disposal queue.
- `frontend/src/pages/TransfersPage.tsx`: Chain-of-custody transfers list with SLA tracking and direct receipt acknowledgement.
- `frontend/src/pages/UsersPage.tsx`: Administrative user management page for creating users and unlocking locked accounts.
