# SealTrail QA Verification Checklist

This document records the end-to-end acceptance criteria and manual browser verification steps for the completed SealTrail system.

---

## 1. Visual Verification & Layout Parity

| Component / Flow | Criteria | Status | Notes |
|------------------|----------|--------|-------|
| **Theme System** | Dark theme (#1e1e1e surface, #2d2d2d panels) and Light theme toggle without visual regressions. | **PASS** | Matches `docs/reference/ui-reference.png` aesthetic. |
| **Sidebar Navigation** | Fixed 232px width, active item highlight, collapsed state on smaller screens, role badges. | **PASS** | Routes to Dashboard, Evidence Items, Cases, Transfers, Approvals, Audit Log, Integrity, Alerts, Reports, Retention, Users. |
| **Evidence Table** | Sticky header, pagination, search input, column chooser, status chips, hash clipping. | **PASS** | Supports dynamic column visibility, sorting, search filter. |
| **Row Expansion** | Expanding evidence row splits into Metadata pane, Cryptographic Integrity pane, and subtabs. | **PASS** | Subtabs: Custody History, Links, Annotations, Audit Trail. |

---

## 2. Evidence Registration & Integrity Workflows

| Test Scenario | Action Taken | Expected Outcome | Result |
|---------------|--------------|------------------|--------|
| **Client-Side Hashing** | Select large file in "+ Register Evidence" dialog. | Incremental hashing progress bar displays `hash-wasm` calculation before network transmission. | **PASS** |
| **Intake Validation** | Submit file with modified client digest. | Server aborts intake with `400 HASH_MISMATCH`; no record created. | **PASS** |
| **Check Character ID** | Register new evidence item. | Generated ID has valid Crockford Base32 check character (e.g., `CASE-2026-001-EV-0001-K`). | **PASS** |
| **Controlled PDF Label** | Click Actions -> Print Label. | Generates printable PDF label with QR code pointing to `/e/:evidenceNumber`. Increments `label_print_count` in audit. | **PASS** |
| **Direct QR Resolution** | Navigate to `/e/{evidence_number}`. | Validates check character; redirects directly to item view. | **PASS** |

---

## 3. Chain-of-Custody & Dual Authorization

| Test Scenario | Action Taken | Expected Outcome | Result |
|---------------|--------------|------------------|--------|
| **Internal Custody Transfer** | Transfer item from Investigator 1 to Investigator 2. | Status transitions to `TRANSFER_PENDING`. Recipient receives acknowledgement prompt. | **PASS** |
| **Receipt Acknowledgement** | Custodian acknowledges pending transfer with correct hash. | Status transitions to `IN_CUSTODY`; `current_custodian_id` updates atomically with audit entry. | **PASS** |
| **External Transfer Flow** | Initiate external transfer to CFSL laboratory. | Requires dual-authorization approval request; status becomes `PENDING_APPROVAL`. | **PASS** |
| **Two-Person Rule** | Requester attempts to approve their own external transfer or disposal request. | Request rejected with 403 Forbidden: `Requester cannot approve their own request`. | **PASS** |
| **Supervisor Approval** | Unrelated supervisor approves request. | Request marked `APPROVED`; transfer or disposal proceeds to execution. | **PASS** |

---

## 4. Courtroom Reports, Legal Hold & Exports

| Test Scenario | Action Taken | Expected Outcome | Result |
|---------------|--------------|------------------|--------|
| **Signed Custody Report** | Request custody report via Actions -> Custody Report (JSON/PDF). | Report generated with Ed25519 digital signature, QR code, and statutory declaration. | **PASS** |
| **Report Verification** | Submit downloaded report to `POST /api/v1/reports/verify`. | Returns `valid: true`, `signature_valid: true`, and verifies all audit sequences. | **PASS** |
| **Section 63 BSA Certificate** | Export package with Section 63 BSA certificate. | Generates ReportLab PDF conforming to Schedule Part A & B of the Bharatiya Sakshya Adhiniyam, 2023. | **PASS** |
| **Offline Export Verifier** | Unzip export package and run `python verify.py`. | Verifies payload SHA-256 against `SHA256SUMS.txt` and validates the Ed25519 signature offline. | **PASS** |
| **Legal Hold Placement** | Place legal hold on evidence or case. | Prevents disposal even if retention policy has expired. | **PASS** |
| **Approved Disposal** | Complete disposal for expired item with no legal hold via dual authorization. | Deletes all S3 object versions; sets `status=DISPOSED`; retains immutable SHA-256 tombstone and audit records. | **PASS** |

---

## 5. Security Anomaly Detection & Tamper Simulation

| Attack / Anomaly | Script Command | Detection Mechanism | Result |
|------------------|----------------|---------------------|--------|
| **Database Audit Tampering** | `python scripts/tamper_demo.py audit` | `verify_chain` detects `CHAIN_BROKEN` at sequence; raises `HIGH` alert. | **PASS** |
| **Audit Chain Full Rewrite** | `python scripts/tamper_demo.py audit-rewrite` | Head hash mismatch against Ed25519 checkpoint; raises `CRITICAL` alert. | **PASS** |
| **S3 Object Replacement** | `python scripts/tamper_demo.py object` | Evidence sweep detects version mismatch; flags `OBJECT_REPLACED`. | **PASS** |
| **Evidence Hash Corruption** | `python scripts/tamper_demo.py evidence-hash` | Evidence sweep detects SHA-256 mismatch; flags `HASH_MISMATCH`. | **PASS** |
| **SLA Missing Ack** | Background scheduler job | Detects transfers where `now > ack_due_at`; raises `MEDIUM` alert. | **PASS** |
| **Clean State Restoration** | `python scripts/tamper_demo.py restore` | Reverts modified database rows; `verify_chain` returns `ok: true`. | **PASS** |
