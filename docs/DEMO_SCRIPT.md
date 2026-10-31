# SealTrail Live 5-Minute Demonstration Script

This script provides an exact step-by-step path to demonstrate the key differentiators and technical capabilities of SealTrail to judges in 5 minutes.

---

## Preparation (Pre-Demo)

Ensure the stack is running and seeded:
```bash
docker compose up --build -d
docker compose exec backend python scripts/seed.py
```
Open **`http://localhost:8080`** in your browser.

---

## Minute 1: The Problem & The Defense-Grade Interface

1. **Login**:
   - Go to `http://localhost:8080/login`.
   - Log in as **Supervisor**:
     - Email: `supervisor.patil@sealtrail.local`
     - Password: `SealTrail2026!Secure`
2. **Dashboard Overview**:
   - Point out the **Chain Status Card**: Shows green "Audit Chain Valid", Sequence count, and the active Ed25519-signed checkpoint head hash.
   - Point out the **Anomaly Alerts Counter**: Live alerts flagged by deterministic explainable rules (e.g., overdue SLA transfer).
3. **Evidence Items Page**:
   - Navigate to **Evidence Items** from the sidebar.
   - Show the operational dark theme interface matching forensic workstation standards.
   - Highlight the controlled evidence IDs with check characters (e.g., `CASE-2026-001-EV-0001-K`).
   - Click the expand arrow on any item (e.g., `iphone_14_logical_dump.tar.gz`).
   - Show the **Three-Way Integrity Block**: Live SHA-256 digest, storage version ID, intake timestamp, and the four sub-tabs (*Custody History, Defensible Links, Annotations, Audit Trail*).

---

## Minute 2: Hashed Intake & Client-Side Verification

1. **Click "+ Register Evidence"**:
   - Select Case: `Operation Dark Ledger (CASE-2026-001)`
   - Item Name: `Forensic Image - USB Drive`
   - Evidence Type: `DISK_IMAGE`
   - Source: `Seized from suspect residence study desk`
   - Acquisition Method: `Hardware write-blocked bitstream dd`
   - Acquisition Tool: `Tableau T8u USB Forensic Bridge`
2. **Select Any Test File** (e.g., a `.bin` or `.pdf` file):
   - Notice the **Incremental Client-Side Hash Calculation**: The blue progress bar fills in real time via `hash-wasm` before upload.
   - Point out: *"The client calculates the SHA-256 digest locally. The server streams the upload into MinIO and independently recomputes the SHA-256. If they do not match bit-for-bit, the registration aborts."*
3. **Click "Submit & Register"**:
   - Item is registered, assigned a Crockford check-character number, and immediately pinned to the audit chain.

---

## Minute 3: Custody Transfers & Dual-Authorization Enforcement

1. **Initiate an External Transfer**:
   - On the newly registered evidence item, click **Actions (...) -> Transfer Custody**.
   - Check **External Transfer (Dual Authorization Required)**.
   - External Recipient Organization: `Central Forensic Science Laboratory (CFSL)`
   - Reason: `Statutory secondary forensic verification for court trial`.
   - Click **Submit Transfer**. Notice the status becomes `PENDING_APPROVAL`.
2. **Demonstrate the Two-Person Rule (Dual Authorization)**:
   - Go to **Approvals** in the sidebar.
   - Notice the approval request submitted by `supervisor.patil@sealtrail.local`.
   - Click **Approve**.
   - **Notice the error**: *"Requester cannot approve their own request (Two-Person Rule Enforced)"*.
   - Log out and log in as another supervisor or admin:
     - Email: `investigator.sharma@sealtrail.local` (or login as second supervisor if created).
   - Alternatively, approve via a non-conflicted supervisor account to show success.

---

## Minute 4: Courtroom-Defensible Export & Offline Verification

1. **Request an Evidence Export**:
   - On any evidence item in `Operation Dark Ledger`, click **Actions (...) -> Export Package**.
   - Justification: `Official evidentiary submission to the High Court of Judicature`.
   - Check **Include Section 63 BSA Certificate**.
   - Click **Generate Export Package**.
2. **Inspect the Export ZIP**:
   - Download the generated ZIP package (`SEALTRAIL-EXPORT-*.zip`).
   - Extract it on your computer.
   - Show the package contents:
     - `evidence.bin` (original bitstream payload)
     - `SHA256SUMS.txt` (manifest of file digests)
     - `manifest.json` (canonical case and custody metadata)
     - `manifest.sig` (Ed25519 digital signature from SealTrail)
     - `PUBLIC_KEY.pem` (public verification key)
     - `Section_63_BSA_Certificate.pdf` (statutory electronic evidence certificate under India's BSA 2023)
     - `verify.py` (zero-dependency standalone offline verification script)
3. **Run the Offline Verifier**:
   ```bash
   python verify.py
   ```
   - Show the console output:
     - `[PASS] evidence.bin SHA-256 matches manifest`
     - `[PASS] SHA256SUMS.txt hashes match`
     - `[PASS] Ed25519 digital signature verified valid`
   - Emphasize to judges: *"Even if SealTrail's servers were destroyed tomorrow, this evidence package can be independently verified on any courtroom laptop without Internet access."*

---

## Minute 5: Live Tamper Simulation & Attack Detection

Open your terminal beside the browser:

1. **Simulate a Malicious DBA Tampering with the Audit Log**:
   ```bash
   docker compose exec backend python scripts/tamper_demo.py audit
   ```
   - Output: `[ATTACK] Modified payload in audit log sequence 2 directly in PostgreSQL.`
2. **Detect the Tampering in the UI**:
   - In the browser, navigate to **Audit Log** or **Dashboard**.
   - Click **Verify Chain Now**.
   - **Result**: The UI flashes Red: `[TAMPER DETECTED] Hash chain broken at sequence 2! Expected hash differs from calculated hash.`
   - An anomaly alert is automatically raised in the **Alerts** queue.
3. **Simulate a DBA Rewriting the Entire Chain**:
   ```bash
   docker compose exec backend python scripts/tamper_demo.py audit-rewrite
   ```
   - Explain to judges: *"The DBA recomputed all row hashes to make the chain look unbroken. But watch what happens:"*
   - Click **Verify Chain Now**.
   - **Result**: `[CHECKPOINT FAILED] Head hash does not match signed Ed25519 checkpoint!`
4. **Restore Clean State**:
   ```bash
   docker compose exec backend python scripts/tamper_demo.py restore
   ```
   - Re-verify: Chain is immediately green and valid again.
5. **Conclude with Tagline**: *"SealTrail: Prove it hasn't changed."*
