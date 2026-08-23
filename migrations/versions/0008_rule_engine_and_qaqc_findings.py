"""rule_definitions, rule_executions, finding_resolutions and findings update

Revision ID: 0008_rule_engine_and_qaqc_findings
Revises: 0007_detected_symbols_and_libraries
Create Date: 2026-08-21 00:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0008_rule_engine_and_qaqc_findings'
down_revision: Union[str, None] = '0007_detected_symbols_and_libraries'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Crear tabla rule_definitions
    op.create_table(
        'rule_definitions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('code', sa.String(100), unique=True, index=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(50), index=True, nullable=False),
        sa.Column('discipline', sa.String(50), server_default='general', nullable=False),
        sa.Column('severity_default', sa.String(20), server_default='medium', nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('input_requirements', sa.JSON(), nullable=True),
        sa.Column('rule_logic_type', sa.String(50), server_default='count_reconciliation', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('version', sa.String(30), server_default='1.0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    # 2. Crear tabla rule_executions
    op.create_table(
        'rule_executions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('processing_jobs.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('rule_id', sa.String(36), sa.ForeignKey('rule_definitions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('rule_version', sa.String(30), server_default='1.0', nullable=False),
        sa.Column('execution_status', sa.String(30), nullable=False),
        sa.Column('input_snapshot', sa.JSON(), nullable=True),
        sa.Column('result_summary', sa.JSON(), nullable=True),
        sa.Column('confidence', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 3. Actualizar rule_findings
    with op.batch_alter_table('rule_findings') as batch_op:
        batch_op.alter_column('review_run_id', existing_type=sa.String(36), nullable=True)
        batch_op.add_column(sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=True))
        batch_op.add_column(sa.Column('rule_id', sa.String(36), sa.ForeignKey('rule_definitions.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('finding_type', sa.String(50), server_default='reconciliation_mismatch', nullable=False))
        batch_op.add_column(sa.Column('evidence_refs', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('expected_value', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('observed_value', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('delta', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('source_trace_ids', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('review_task_id', sa.String(36), sa.ForeignKey('review_tasks.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # 4. Crear finding_resolutions
    op.create_table(
        'finding_resolutions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('finding_id', sa.String(36), sa.ForeignKey('rule_findings.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('resolution_type', sa.String(50), nullable=False),
        sa.Column('resolved_by', sa.String(100), server_default='auditor_qa', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('corrected_value', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

def downgrade() -> None:
    op.drop_table('finding_resolutions')
    with op.batch_alter_table('rule_findings') as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('review_task_id')
        batch_op.drop_column('source_trace_ids')
        batch_op.drop_column('delta')
        batch_op.drop_column('observed_value')
        batch_op.drop_column('expected_value')
        batch_op.drop_column('evidence_refs')
        batch_op.drop_column('finding_type')
        batch_op.drop_column('rule_id')
        batch_op.drop_column('document_id')
    op.drop_table('rule_executions')
    op.drop_table('rule_definitions')
