"""
Pytest fixtures and database test harness.
Provides in-memory SQLite engine with full SQL triggers mirroring PostgreSQL enforcement.
"""

import os
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.db import Base
import app.models  # load all models


@pytest.fixture(scope="session")
def test_engine():
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable SQLite foreign keys
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    # Create SQLite triggers mirroring PostgreSQL triggers
    from app.db import set_engine
    set_engine(engine)
    with engine.begin() as conn:
        # Append-only triggers on audit_log, audit_checkpoints, annotations, case_notes
        for table in ["audit_log", "audit_checkpoints", "annotations", "case_notes"]:
            conn.execute(text(f"""
                CREATE TRIGGER trg_{table}_no_update
                BEFORE UPDATE ON {table}
                BEGIN
                    SELECT RAISE(ABORT, 'APPEND_ONLY_VIOLATION: Table is append-only');
                END;
            """))
            conn.execute(text(f"""
                CREATE TRIGGER trg_{table}_no_delete
                BEFORE DELETE ON {table}
                BEGIN
                    SELECT RAISE(ABORT, 'APPEND_ONLY_VIOLATION: Table is append-only');
                END;
            """))

        # Chain continuity trigger on audit_log
        conn.execute(text("""
            CREATE TRIGGER trg_audit_chain_enforce
            BEFORE INSERT ON audit_log
            BEGIN
                SELECT
                    CASE
                        WHEN (SELECT COUNT(*) FROM audit_log) = 0 THEN
                            CASE
                                WHEN NEW.seq != 1 OR NEW.prev_hash != '0000000000000000000000000000000000000000000000000000000000000000' THEN
                                    RAISE(ABORT, 'CHAIN_VIOLATION: Genesis entry must have seq=1 and prev_hash=64 zeros')
                            END
                        ELSE
                            CASE
                                WHEN NEW.seq != (SELECT seq + 1 FROM audit_log ORDER BY seq DESC LIMIT 1) THEN
                                    RAISE(ABORT, 'CHAIN_VIOLATION: seq must equal last_seq + 1')
                                WHEN NEW.prev_hash != (SELECT entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1) THEN
                                    RAISE(ABORT, 'CHAIN_VIOLATION: prev_hash must equal last entry_hash')
                            END
                    END;
            END;
        """))

        # Immutability trigger on evidence_items
        conn.execute(text("""
            CREATE TRIGGER trg_evidence_immutability
            BEFORE UPDATE ON evidence_items
            BEGIN
                SELECT
                    CASE
                        WHEN OLD.id != NEW.id OR
                             OLD.evidence_number != NEW.evidence_number OR
                             OLD.case_id != NEW.case_id OR
                             OLD.type != NEW.type OR
                             OLD.sha256 != NEW.sha256 OR
                             OLD.size_bytes != NEW.size_bytes OR
                             OLD.original_filename != NEW.original_filename OR
                             OLD.storage_key != NEW.storage_key THEN
                            RAISE(ABORT, 'IMMUTABILITY_VIOLATION: Cannot modify immutable evidence fields')
                    END;
            END;
        """))

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
