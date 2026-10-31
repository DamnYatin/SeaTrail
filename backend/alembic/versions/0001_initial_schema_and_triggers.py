"""Initial schema, audit chain triggers, immutability triggers and app role grants

Revision ID: 0001_initial
Revises: 
Create Date: 2026-10-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create Tables
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('failed_login_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    op.create_table(
        'retention_policies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('retain_days', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
    )

    op.create_table(
        'cases',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('case_number', sa.String(30), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), server_default='OPEN', nullable=False),
        sa.Column('classification', sa.String(50), server_default='CONFIDENTIAL', nullable=False),
        sa.Column('lead_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('evidence_counter', sa.Integer(), server_default='0', nullable=False),
        sa.Column('legal_hold', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('legal_hold_reason', sa.Text(), nullable=True),
        sa.Column('retention_policy_id', sa.String(36), sa.ForeignKey('retention_policies.id'), nullable=True),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
    )
    op.create_index('ix_cases_case_number', 'cases', ['case_number'])

    op.create_table(
        'case_members',
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('case_role', sa.String(50), server_default='MEMBER', nullable=False),
        sa.Column('added_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'evidence_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('evidence_number', sa.String(50), unique=True, nullable=False),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id'), nullable=False),
        sa.Column('parent_evidence_id', sa.String(36), sa.ForeignKey('evidence_items.id'), nullable=True),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('item_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_description', sa.Text(), nullable=True),
        sa.Column('collected_by_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acquisition_method', sa.String(255), nullable=True),
        sa.Column('acquisition_tool', sa.String(255), nullable=True),
        sa.Column('device_make', sa.String(100), nullable=True),
        sa.Column('device_model', sa.String(100), nullable=True),
        sa.Column('device_serial', sa.String(100), nullable=True),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('client_sha256', sa.String(64), nullable=True),
        sa.Column('storage_bucket', sa.String(100), nullable=False),
        sa.Column('storage_key', sa.String(500), nullable=False),
        sa.Column('storage_version_id', sa.String(255), nullable=True),
        sa.Column('intake_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('intake_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('current_custodian_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('current_location', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), server_default='IN_CUSTODY', nullable=False),
        sa.Column('integrity_state', sa.String(50), server_default='OK', nullable=False),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('legal_hold', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('retention_until', sa.Date(), nullable=True),
        sa.Column('label_print_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('disposed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_evidence_items_case_id', 'evidence_items', ['case_id'])
    op.create_index('ix_evidence_items_number', 'evidence_items', ['evidence_number'])
    op.create_index('ix_evidence_items_sha256', 'evidence_items', ['sha256'])

    op.create_table(
        'approval_requests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('kind', sa.String(50), nullable=False),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id'), nullable=False),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('evidence_items.id'), nullable=True),
        sa.Column('requested_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(50), server_default='PENDING', nullable=False),
        sa.Column('decided_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_note', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('decided_by IS NULL OR decided_by <> requested_by', name='check_separate_approver'),
    )

    op.create_table(
        'custody_transfers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('evidence_items.id'), nullable=False),
        sa.Column('from_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('to_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('to_location', sa.String(255), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('is_external', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('external_party', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), server_default='PENDING_ACK', nullable=False),
        sa.Column('approval_request_id', sa.String(36), sa.ForeignKey('approval_requests.id'), nullable=True),
        sa.Column('hash_at_send', sa.String(64), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ack_due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hash_at_receipt', sa.String(64), nullable=True),
        sa.Column('receipt_verified', sa.Boolean(), nullable=True),
    )
    op.create_index('ix_custody_transfers_evidence_id', 'custody_transfers', ['evidence_id'])

    op.create_table(
        'annotations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('evidence_items.id'), nullable=False),
        sa.Column('author_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('body_sha256', sa.String(64), nullable=False),
        sa.Column('parent_annotation_id', sa.String(36), sa.ForeignKey('annotations.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'people',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id'), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role_in_case', sa.String(50), server_default='OTHER', nullable=False),
        sa.Column('contact', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'case_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'case_notes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id'), nullable=False),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('evidence_items.id'), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('author_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'evidence_links',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('evidence_items.id'), nullable=False),
        sa.Column('target_type', sa.String(50), nullable=False),
        sa.Column('target_id', sa.String(36), nullable=False),
        sa.Column('relation', sa.String(100), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.UniqueConstraint('evidence_id', 'target_type', 'target_id', 'relation', name='uq_evidence_link'),
    )

    op.create_table(
        'audit_log',
        sa.Column('seq', sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actor_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('actor_role', sa.String(50), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id'), nullable=True),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('evidence_items.id'), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('ip', sa.String(45), nullable=True),
        sa.Column('prev_hash', sa.String(64), nullable=False),
        sa.Column('entry_hash', sa.String(64), nullable=False),
    )
    op.create_index('ix_audit_log_entry_hash', 'audit_log', ['entry_hash'])
    op.create_index('ix_audit_log_ts', 'audit_log', ['ts'])
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])

    op.create_table(
        'audit_checkpoints',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('seq_to', sa.BigInteger(), nullable=False),
        sa.Column('head_hash', sa.String(64), nullable=False),
        sa.Column('signature_b64', sa.Text(), nullable=False),
        sa.Column('public_key_id', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
    )

    op.create_table(
        'integrity_state',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('last_chain_check_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('chain_ok', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('head_seq', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('broken_seq', sa.BigInteger(), nullable=True),
        sa.Column('broken_reason', sa.String(255), nullable=True),
    )

    op.create_table(
        'integrity_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('kind', sa.String(50), nullable=False),
        sa.Column('started_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total', sa.Integer(), server_default='0', nullable=False),
        sa.Column('checked', sa.Integer(), server_default='0', nullable=False),
        sa.Column('failed', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(50), server_default='PENDING', nullable=False),
    )

    op.create_table(
        'alerts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('rule', sa.String(100), nullable=False),
        sa.Column('severity', sa.String(50), nullable=False),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id'), nullable=True),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('evidence_items.id'), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('audit_seqs', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(50), server_default='OPEN', nullable=False),
        sa.Column('dedupe_key', sa.String(255), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('resolved_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
    )

    op.create_table(
        'exports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('evidence_items.id'), nullable=False),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('cases.id'), nullable=False),
        sa.Column('approval_request_id', sa.String(36), sa.ForeignKey('approval_requests.id'), nullable=True),
        sa.Column('requested_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('approved_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('encrypted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('package_sha256', sa.String(64), nullable=False),
        sa.Column('package_size', sa.BigInteger(), nullable=False),
        sa.Column('storage_key', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('download_count', sa.Integer(), server_default='0', nullable=False),
    )

    # 2. PostgreSQL Triggers and Grants (executed conditionally when running under PostgreSQL)
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # Append-only trigger function
        op.execute("""
            CREATE OR REPLACE FUNCTION sealtrail_prevent_mutation()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'APPEND_ONLY_VIOLATION: Table % is append-only', TG_TABLE_NAME;
            END;
            $$ LANGUAGE plpgsql;
        """)

        # Append-only triggers on audit_log, audit_checkpoints, annotations, case_notes
        for table in ['audit_log', 'audit_checkpoints', 'annotations', 'case_notes']:
            op.execute(f"""
                CREATE TRIGGER trg_{table}_append_only
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION sealtrail_prevent_mutation();

                CREATE TRIGGER trg_{table}_no_truncate
                BEFORE TRUNCATE ON {table}
                FOR EACH STATEMENT EXECUTE FUNCTION sealtrail_prevent_mutation();
            """)

        # Audit log chain integrity trigger (enforce seq + 1 and prev_hash)
        op.execute("""
            CREATE OR REPLACE FUNCTION sealtrail_enforce_audit_chain()
            RETURNS TRIGGER AS $$
            DECLARE
                last_row RECORD;
            BEGIN
                SELECT seq, entry_hash INTO last_row FROM audit_log ORDER BY seq DESC LIMIT 1;
                IF last_row IS NULL THEN
                    IF NEW.seq <> 1 OR NEW.prev_hash <> repeat('0', 64) THEN
                        RAISE EXCEPTION 'CHAIN_VIOLATION: Genesis entry must have seq=1 and prev_hash=64 zeros';
                    END IF;
                ELSE
                    IF NEW.seq <> last_row.seq + 1 THEN
                        RAISE EXCEPTION 'CHAIN_VIOLATION: seq must equal last_seq + 1 (got %, expected %)', NEW.seq, last_row.seq + 1;
                    END IF;
                    IF NEW.prev_hash <> last_row.entry_hash THEN
                        RAISE EXCEPTION 'CHAIN_VIOLATION: prev_hash must equal last entry_hash';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER trg_audit_chain_enforce
            BEFORE INSERT ON audit_log
            FOR EACH ROW EXECUTE FUNCTION sealtrail_enforce_audit_chain();
        """)

        # Immutability trigger on evidence_items
        op.execute("""
            CREATE OR REPLACE FUNCTION sealtrail_enforce_evidence_immutability()
            RETURNS TRIGGER AS $$
            BEGIN
                IF OLD.id <> NEW.id OR
                   OLD.evidence_number <> NEW.evidence_number OR
                   OLD.case_id <> NEW.case_id OR
                   (OLD.parent_evidence_id IS DISTINCT FROM NEW.parent_evidence_id) OR
                   OLD.type <> NEW.type OR
                   OLD.item_name <> NEW.item_name OR
                   OLD.description IS DISTINCT FROM NEW.description OR
                   OLD.source_description IS DISTINCT FROM NEW.source_description OR
                   OLD.collected_by_user_id <> NEW.collected_by_user_id OR
                   OLD.collected_at <> NEW.collected_at OR
                   OLD.acquisition_method IS DISTINCT FROM NEW.acquisition_method OR
                   OLD.acquisition_tool IS DISTINCT FROM NEW.acquisition_tool OR
                   OLD.device_make IS DISTINCT FROM NEW.device_make OR
                   OLD.device_model IS DISTINCT FROM NEW.device_model OR
                   OLD.device_serial IS DISTINCT FROM NEW.device_serial OR
                   OLD.original_filename <> NEW.original_filename OR
                   OLD.content_type <> NEW.content_type OR
                   OLD.size_bytes <> NEW.size_bytes OR
                   OLD.sha256 <> NEW.sha256 OR
                   OLD.storage_bucket <> NEW.storage_bucket OR
                   OLD.storage_key <> NEW.storage_key OR
                   OLD.storage_version_id IS DISTINCT FROM NEW.storage_version_id OR
                   OLD.intake_at <> NEW.intake_at OR
                   OLD.intake_by <> NEW.intake_by THEN
                    RAISE EXCEPTION 'IMMUTABILITY_VIOLATION: Cannot modify immutable evidence fields';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER trg_evidence_immutability
            BEFORE UPDATE ON evidence_items
            FOR EACH ROW EXECUTE FUNCTION sealtrail_enforce_evidence_immutability();
        """)

        # Grants for DB_APP_USER if user exists
        op.execute("""
            DO $$
            DECLARE
                app_user text := current_setting('app.db_app_user', true);
            BEGIN
                IF app_user IS NULL OR app_user = '' THEN
                    app_user := 'sealtrail_app';
                END IF;

                IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = app_user) THEN
                    EXECUTE format('GRANT SELECT, INSERT ON audit_log, audit_checkpoints, annotations, case_notes TO %I', app_user);
                    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON users, cases, case_members, retention_policies, evidence_items, custody_transfers, approval_requests, people, case_events, evidence_links, integrity_state, integrity_runs, alerts, exports TO %I', app_user);
                    EXECUTE format('GRANT SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO %I', app_user);
                END IF;
            END
            $$;
        """)


def downgrade() -> None:
    pass
