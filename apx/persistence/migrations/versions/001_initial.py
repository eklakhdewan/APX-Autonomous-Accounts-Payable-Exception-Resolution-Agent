"""Initial migration - create all tables

Revision ID: 001
Revises: 
Create Date: 2026-08-20

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create invoices table
    op.create_table(
        'invoices',
        sa.Column('invoice_id', sa.String(64), nullable=False),
        sa.Column('vendor_id', sa.String(64), nullable=False),
        sa.Column('invoice_number', sa.String(64), nullable=False),
        sa.Column('po_number', sa.String(64), nullable=True),
        sa.Column('invoice_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('subtotal', sa.DECIMAL(18, 2), nullable=False),
        sa.Column('tax', sa.DECIMAL(18, 2), nullable=False),
        sa.Column('total', sa.DECIMAL(18, 2), nullable=False),
        sa.Column('discount', sa.DECIMAL(18, 2), server_default='0', nullable=False),
        sa.Column('payload_json', sqlite.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('invoice_id'),
    )
    op.create_index('ix_invoices_vendor_date', 'invoices', ['vendor_id', 'invoice_date'])
    op.create_index('ix_invoices_po_number', 'invoices', ['po_number'])

    # Create ground_truth table
    op.create_table(
        'ground_truth',
        sa.Column('invoice_id', sa.String(64), nullable=False),
        sa.Column('expected_exceptions', sqlite.JSON(), server_default='[]', nullable=False),
        sa.Column('expected_decision', sa.String(64), nullable=True),
        sa.Column('injected_exceptions', sqlite.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.invoice_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('invoice_id'),
    )

    # Create cases table
    op.create_table(
        'cases',
        sa.Column('case_id', sa.String(36), nullable=False),
        sa.Column('invoice_id', sa.String(64), nullable=False),
        sa.Column('vendor_id', sa.String(64), nullable=False),
        sa.Column('status', sa.String(32), server_default='NEW', nullable=False),
        sa.Column('current_phase', sa.String(32), nullable=True),
        sa.Column('exception_codes', sqlite.JSON(), server_default='[]', nullable=False),
        sa.Column('validation_status', sa.String(32), nullable=True),
        sa.Column('evidence_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('valid_evidence_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('risk_level', sa.String(16), nullable=True),
        sa.Column('risk_score', sa.DECIMAL(4, 3), nullable=True),
        sa.Column('investigation_outcome', sa.String(32), nullable=True),
        sa.Column('investigation_findings', sa.Text(), nullable=True),
        sa.Column('investigation_budget_limit', sa.Integer(), nullable=True),
        sa.Column('investigation_budget_used', sa.Integer(), nullable=True),
        sa.Column('investigation_steps', sqlite.JSON(), server_default='[]', nullable=False),
        sa.Column('action_type', sa.String(32), nullable=True),
        sa.Column('action_status', sa.String(32), nullable=True),
        sa.Column('guardrail_decision', sa.String(32), nullable=True),
        sa.Column('guardrail_checks', sqlite.JSON(), server_default='[]', nullable=False),
        sa.Column('idempotency_key', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.invoice_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('case_id'),
        sa.UniqueConstraint('invoice_id', name='uq_cases_invoice_id'),
    )
    op.create_index('ix_cases_status_updated', 'cases', ['status', 'updated_at'])
    op.create_index('ix_cases_vendor_status', 'cases', ['vendor_id', 'status'])
    op.create_index('ix_cases_idempotency_key', 'cases', ['idempotency_key'], unique=True)

    # Create approvals table
    op.create_table(
        'approvals',
        sa.Column('approval_id', sa.String(36), nullable=False),
        sa.Column('case_id', sa.String(36), nullable=False),
        sa.Column('action_plan_id', sa.String(36), nullable=True),
        sa.Column('action_type', sa.String(32), nullable=False),
        sa.Column('risk_level', sa.String(16), nullable=False),
        sa.Column('status', sa.String(16), server_default='PENDING', nullable=False),
        sa.Column('required_approvers', sqlite.JSON(), server_default='[]', nullable=False),
        sa.Column('approvals_json', sqlite.JSON(), server_default='{}', nullable=False),
        sa.Column('requested_by', sa.String(64), server_default='system', nullable=False),
        sa.Column('requested_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('resolved_by', sa.String(64), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('approval_id'),
        sa.UniqueConstraint('case_id', name='uq_approvals_case_id'),
    )
    op.create_index('ix_approvals_status', 'approvals', ['status'])

    # Create actions table
    op.create_table(
        'actions',
        sa.Column('action_id', sa.String(36), nullable=False),
        sa.Column('case_id', sa.String(36), nullable=False),
        sa.Column('approval_id', sa.String(36), nullable=True),
        sa.Column('action_type', sa.String(32), nullable=False),
        sa.Column('target', sa.String(64), nullable=False),
        sa.Column('parameters_json', sqlite.JSON(), server_default='{}', nullable=False),
        sa.Column('risk_score', sa.DECIMAL(4, 3), nullable=True),
        sa.Column('guardrail_decision', sa.String(16), nullable=True),
        sa.Column('guardrail_checks', sqlite.JSON(), server_default='[]', nullable=False),
        sa.Column('status', sa.String(16), server_default='PENDING', nullable=False),
        sa.Column('idempotency_key', sa.String(64), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('result_json', sqlite.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['approval_id'], ['approvals.approval_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('action_id'),
        sa.UniqueConstraint('case_id', name='uq_actions_case_id'),
    )
    op.create_index('ix_actions_status', 'actions', ['status'])
    op.create_index('ix_actions_type_status', 'actions', ['action_type', 'status'])
    op.create_index('ix_actions_idempotency_key', 'actions', ['idempotency_key'], unique=True)

    # Create audit_events table
    op.create_table(
        'audit_events',
        sa.Column('event_id', sa.String(36), nullable=False),
        sa.Column('case_id', sa.String(36), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('phase', sa.String(16), nullable=True),
        sa.Column('component', sa.String(64), nullable=True),
        sa.Column('payload_json', sqlite.JSON(), nullable=False),
        sa.Column('metadata_json', sqlite.JSON(), server_default='{}', nullable=False),
        sa.Column('request_id', sa.String(64), nullable=True),
        sa.Column('correlation_id', sa.String(64), nullable=True),
        sa.Column('user_id', sa.String(64), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('event_id'),
    )
    op.create_index('ix_audit_case_created', 'audit_events', ['case_id', 'created_at'])
    op.create_index('ix_audit_type_created', 'audit_events', ['event_type', 'created_at'])
    op.create_index('ix_audit_request_correlation', 'audit_events', ['request_id', 'correlation_id'])


def downgrade() -> None:
    op.drop_index('ix_audit_request_correlation', table_name='audit_events')
    op.drop_index('ix_audit_type_created', table_name='audit_events')
    op.drop_index('ix_audit_case_created', table_name='audit_events')
    op.drop_table('audit_events')

    op.drop_index('ix_actions_idempotency_key', table_name='actions')
    op.drop_index('ix_actions_type_status', table_name='actions')
    op.drop_index('ix_actions_status', table_name='actions')
    op.drop_table('actions')

    op.drop_index('ix_approvals_status', table_name='approvals')
    op.drop_table('approvals')

    op.drop_index('ix_cases_idempotency_key', table_name='cases')
    op.drop_index('ix_cases_vendor_status', table_name='cases')
    op.drop_index('ix_cases_status_updated', table_name='cases')
    op.drop_table('cases')

    op.drop_table('ground_truth')

    op.drop_index('ix_invoices_po_number', table_name='invoices')
    op.drop_index('ix_invoices_vendor_date', table_name='invoices')
    op.drop_table('invoices')