# Technical Decisions Log

This document records architectural, design, and implementation decisions made during the autonomous build of SealTrail.

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-31 | Docker not installed on host machine; provide complete Docker Compose configuration and verify code locally | Host execution environment lacks Docker daemon; architecture and compose files follow exact specification. |
| 2026-10-31 | Pydantic v2 + pydantic-settings for configuration management | Strict type-safety, fail-fast on missing secrets at application startup. |
| 2026-10-31 | Sync SQLAlchemy 2.0 with psycopg 3 | Mandated in AGENTS.md Section 2 for rock-solid transaction coupling with audit chain. |
| 2026-10-31 | Single global chain with advisory lock per transaction | Guarantees strictly serial contiguous audit entries without gaps or race conditions. |
| 2026-10-31 | Standalone verify.py shipped with standard library fallback for Ed25519 | Allows offline verification on any standard Python 3 workstation without pip dependencies. |
