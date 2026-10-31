# Known Limitations

This document tracks known architectural trade-offs, scope boundaries, and non-covered areas as mandated by AGENTS.md Section 0.1 and Section 12.

1. **Host Execution Environment (Docker):**
   - The development workstation lacks Docker/Docker Compose CLI in PATH.
   - All Dockerfiles, docker-compose configuration, healthchecks, entrypoints, and containerized architectures are fully implemented according to specification. Local code and tests run directly with Python 3.11 and Node.js.

2. **Ed25519 Checkpoint Key Custody:**
   - The checkpoint private key is stored in the process environment (`CHECKPOINT_SIGNING_KEY_B64`). If an attacker gains host root and steals the key while simultaneously rewriting PostgreSQL, they can forge checkpoints. Production systems should anchor checkpoint heads to an external RFC 3161 Timestamp Authority or append-only ledger.

3. **Section 63 BSA Certificate:**
   - The draft certificate reproduces statutory fields from the Bharatiya Sakshya Adhiniyam, 2023 Schedule (Part A & Part B). It is clearly labeled as an auto-filled draft for review and manual signature, not legal advice.

4. **In-Process Background Scheduler:**
   - APScheduler runs within the single Uvicorn process worker. Multi-worker scaling requires an external job queue (e.g., Celery/Redis) to prevent duplicate cron executions.
