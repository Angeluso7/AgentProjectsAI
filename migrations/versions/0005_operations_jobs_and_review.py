"""operations, jobs, policies, review queue and decision traces

Revision ID: 0005_operations_jobs_and_review
Revises: 0004_source_assets_intake
Create Date: 2026-08-21 00:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0005_operations_jobs_and_review'
down_revision: Union[str, None] = '0004_source_assets_intake'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. processing_jobs
    op.create_table(
        'processing_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('job_type', sa.String(50), nullable=False, index=True),
        sa.Column('target_type', sa.String(50), nullable=False, index=True),
        sa.Column('target_id', sa.String(36), nullable=False, index=True),
        sa.Column('project_id', sa.String(36), nullable=True, index=True),
        sa.Column('parent_job_id', sa.String(36), nullable=True, index=True),
        sa.Column('pipeline_name', sa.String(100), server_default='standard_pipeline', nullable=False),
        sa.Column('pipeline_version', sa.String(30), server_default='v1.0', nullable=False),
        sa.Column('requested_by', sa.String(100), server_default='system', nullable=False),
        sa.Column('status', sa.String(30), server_default='queued', nullable=False, index=True),
        sa.Column('priority', sa.Integer(), server_default='5', nullable=False),
        sa.Column('progress_percent', sa.Integer(), server_default='0', nullable=False),
        sa.Column('current_stage', sa.String(100), server_default='init', nullable=False),
        sa.Column('input_payload', sa.JSON(), nullable=True),
        sa.Column('result_summary', sa.JSON(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False),
        sa.Column('queued_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    # 2. job_events
    op.create_table(
        'job_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('processing_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False, index=True),
        sa.Column('status_before', sa.String(30), nullable=True),
        sa.Column('status_after', sa.String(30), nullable=True),
        sa.Column('stage', sa.String(100), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('actor_type', sa.String(30), server_default='system', nullable=False),
        sa.Column('actor_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 3. confidence_policies
    op.create_table(
        'confidence_policies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('applies_to', sa.String(50), nullable=False, index=True),
        sa.Column('document_type', sa.String(50), nullable=True),
        sa.Column('discipline', sa.String(50), nullable=True),
        sa.Column('field_name', sa.String(50), nullable=True),
        sa.Column('risk_level', sa.String(20), server_default='medium', nullable=False),
        sa.Column('auto_accept_threshold', sa.Float(), nullable=False),
        sa.Column('review_threshold', sa.Float(), nullable=False),
        sa.Column('action_below_review_threshold', sa.String(30), server_default='exception_required', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('version', sa.String(20), server_default='1.0', nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    # 4. review_tasks
    op.create_table(
        'review_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), nullable=True, index=True),
        sa.Column('source_asset_id', sa.String(36), nullable=True, index=True),
        sa.Column('document_id', sa.String(36), nullable=True, index=True),
        sa.Column('sheet_id', sa.String(36), nullable=True, index=True),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('processing_jobs.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('task_type', sa.String(50), nullable=False, index=True),
        sa.Column('priority', sa.String(20), server_default='medium', nullable=False),
        sa.Column('status', sa.String(30), server_default='open', nullable=False, index=True),
        sa.Column('reason_code', sa.String(50), nullable=False),
        sa.Column('reason_message', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('evidence_refs', sa.JSON(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('assigned_to', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('due_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True)
    )

    # 5. review_decisions
    op.create_table(
        'review_decisions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('review_task_id', sa.String(36), sa.ForeignKey('review_tasks.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('decision', sa.String(30), nullable=False),
        sa.Column('original_value', sa.JSON(), nullable=False),
        sa.Column('corrected_value', sa.JSON(), nullable=True),
        sa.Column('reviewer', sa.String(100), server_default='auditor_qa', nullable=False),
        sa.Column('reason_code', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 6. decision_traces
    op.create_table(
        'decision_traces',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('trace_type', sa.String(50), nullable=False, index=True),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=False, index=True),
        sa.Column('source_asset_id', sa.String(36), nullable=True),
        sa.Column('document_id', sa.String(36), nullable=True),
        sa.Column('sheet_id', sa.String(36), nullable=True),
        sa.Column('job_id', sa.String(36), nullable=True),
        sa.Column('evidence_refs', sa.JSON(), nullable=True),
        sa.Column('engine_name', sa.String(50), nullable=False),
        sa.Column('engine_version', sa.String(30), nullable=False),
        sa.Column('template_id', sa.String(36), nullable=True),
        sa.Column('template_version', sa.String(30), nullable=True),
        sa.Column('policy_id', sa.String(36), nullable=True),
        sa.Column('policy_version', sa.String(30), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('decision_status', sa.String(30), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

def downgrade() -> None:
    op.drop_table('decision_traces')
    op.drop_table('review_decisions')
    op.drop_table('review_tasks')
    op.drop_table('confidence_policies')
    op.drop_table('job_events')
    op.drop_table('processing_jobs')
