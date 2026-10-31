# SealTrail Architecture & Trust Model

## 1. System Overview

SealTrail ensures the non-repudiation, tamper-evidence, and courtroom defensibility of digital evidence using a layered defense-in-depth model across the application, database, and storage subsystems.

---

## 2. Infrastructure & Container Topology

```mermaid
flowchart TD
    Browser["Analyst Workstation (Browser)"]
    
    subgraph Host ["Docker Host Environment"]
        Nginx["nginx :8080 (Reverse Proxy & Static SPA)"]
        Backend["backend :8000 (FastAPI + APScheduler)"]
        Postgres[("PostgreSQL 16 :5432 (App & Owner Roles)")]
        MinIO[("MinIO S3 :9000/:9001 (Versioned Storage)")]
    end

    Browser -->|HTTP/HTTPS :8080| Nginx
    Nginx -->|/api/*| Backend
    Nginx -->|Static Assets| Nginx
    Backend -->|SQL (app_user)| Postgres
    Backend -->|boto3 S3 API| MinIO
```

### Trust Boundaries & Network Isolation
- **Perimeter (Public)**: Nginx reverse-proxy on port `8080` terminates requests, enforces Content-Security-Policy, strips server headers, and serves the pre-compiled Vite SPA bundle.
- **Internal Network**: Communication between FastAPI, PostgreSQL, and MinIO occurs within an isolated Docker bridge network.
- **Database Roles**: The FastAPI application connects using the least-privilege `app_user` role. DDL modifications and schema migrations run strictly as `owner_user` during container boot.
- **Storage Policies**: MinIO IAM policies explicitly deny `s3:DeleteObject` and `s3:DeleteObjectVersion` to the `sealtrail-app` credential. Disposal operations utilize a separate single-purpose privileged credential.

---

## 3. Evidence Ingestion Pipeline

```mermaid
sequenceDiagram
    autonumber
    actor Analyst as Investigator / Custodian
    participant Web as React SPA (Client)
    participant API as FastAPI Backend
    participant Storage as MinIO S3
    participant DB as PostgreSQL 16
    
    Analyst->>Web: Select file + enter forensic metadata
    Note over Web: Incremental SHA-256 via hash-wasm
    Web->>API: POST /api/v1/evidence (multipart + client_sha256)
    API->>Storage: Stream file chunk-by-chunk to S3 bucket
    Note over API: Streaming SHA-256 calculation
    API-->>Storage: Complete upload & retrieve version_id
    API->>API: Verify server_sha256 == client_sha256
    rect rgb(240, 245, 255)
        Note over API,DB: Single Atomic Transaction
        API->>DB: INSERT INTO evidence_items (immutable metadata + hash + version_id)
        API->>DB: INSERT INTO audit_log (seq = N+1, action = EVIDENCE_REGISTERED)
    end
    API-->>Web: 201 Created (Evidence ID + check character number)
    Web-->>Analyst: Display evidence item & printable QR label
```

---

## 4. Custody Transfer State Machine

Evidence custody transitions are enforced by a strict state machine that guarantees accountability:

```mermaid
stateDiagram-v2
    [*] --> IN_CUSTODY : Intake Complete
    IN_CUSTODY --> TRANSFER_PENDING : Initiate Internal Transfer
    IN_CUSTODY --> PENDING_APPROVAL : Initiate External Transfer
    
    PENDING_APPROVAL --> TRANSFER_PENDING : Approved (Dual-Auth Supervisor)
    PENDING_APPROVAL --> IN_CUSTODY : Rejected / Cancelled
    
    TRANSFER_PENDING --> IN_CUSTODY : Acknowledge Receipt (Hash Verified)
    TRANSFER_PENDING --> DISPUTED : Acknowledge Failed (Hash Mismatch)
    TRANSFER_PENDING --> IN_CUSTODY : Cancelled by Sender
    
    IN_CUSTODY --> DISPOSED : Approved Disposal (Retention Expired & No Hold)
    DISPOSED --> [*]
```

### State Transition Rules
1. **Initiation**: When a custodian initiates a transfer, `hash_at_send` is recorded from the live object and status transitions to `TRANSFER_PENDING`.
2. **Two-Person Rule for External Transfers**: Transfers to third-party entities require prior approval from a supervisor who is not the requester (`decided_by <> requested_by`).
3. **Receipt Acknowledgement**: The receiving custodian confirms receipt by submitting `hash_at_receipt`. The system matches this against `hash_at_send`. If identical, custody changes; if differing, an immediate `CRITICAL` alert is dispatched.
4. **SLA Deadlines**: Transfers have an `ack_due_at` SLA timestamp. An automated background task flags any transfer exceeding its SLA without acknowledgement.

---

## 5. Three-Way Cryptographic Integrity Binding

To prevent silent evidence tampering or decoupling of audit records, SealTrail enforces a three-way cryptographic binding:

```mermaid
graph TD
    subgraph Storage ["Object Storage (MinIO)"]
        OBJ["Object: cases/{case_id}/{evidence_id}
Version: v1.0 (Locked)
Content SHA-256: e3b0c4429..."]
    end

    subgraph Database ["PostgreSQL Relational Record"]
        ROW["evidence_items Row:
- id: 550e8400...
- sha256: e3b0c4429...
- storage_key: cases/...
- storage_version_id: v1.0
(Protected by DB immutability trigger)"]
    end

    subgraph Chain ["Append-Only Audit Ledger"]
        LOG1["Audit Log Seq 42:
Action: EVIDENCE_REGISTERED
Payload: sha256: e3b0c4429..., version: v1.0
prev_hash: a1b2...
entry_hash: c3d4..."]
        LOG2["Audit Log Seq 85:
Action: CUSTODY_TRANSFERRED
Payload: hash_at_send: e3b0c4429...
prev_hash: c3d4...
entry_hash: e5f6..."]
        LOG1 --> LOG2
    end

    OBJ <== "Live Content Match" ==> ROW
    ROW <== "Metadata Integrity" ==> LOG1
```

### Continuous Verification
- **Automated Evidence Sweep**: Background workers read the live S3 object stream, recompute the SHA-256 digest, verify that the active version matches `storage_version_id`, and compare against `evidence_items.sha256`.
- **Three Failure States**:
  - `OK`: Storage content hash matches the database record.
  - `OBJECT_REPLACED`: The S3 key exists and matches the hash, but its version ID changed.
  - `CORRUPT / HASH_MISMATCH`: The content of the S3 object has changed.

---

## 6. Hash Chain & Ed25519 Checkpoint Structure

```mermaid
flowchart LR
    subgraph HashChain ["PostgreSQL Append-Only Audit Chain"]
        E1["Entry 1 (Genesis)
seq: 1
prev_hash: 000...000
entry_hash: H1"] --> E2["Entry 2
seq: 2
prev_hash: H1
entry_hash: H2"] --> E3["Entry 3
seq: 3
prev_hash: H2
entry_hash: H3"] --> E4["Entry N
seq: N
prev_hash: H(N-1)
entry_hash: HN"]
    end

    subgraph CheckpointRecord ["Cryptographic Checkpoint"]
        CP["audit_checkpoints Table
seq_to: N
head_hash: HN
signature_b64: Ed25519_Sign(private_key, 'N:HN')
public_key_id: ed25519-2026-v1"]
    end

    E4 -.->|"Seals Head"| CP
```

### Defense Against Malicious Database Administrators
1. If a rogue administrator updates an audit entry directly in PostgreSQL, the hash chain breaks (`prev_hash != calculated_hash` for subsequent rows).
2. If the rogue administrator recomputes all hashes down the entire chain to forge consistency, the newly calculated head hash will fail verification against the historical **Ed25519-signed checkpoints** published outside the transaction table.
