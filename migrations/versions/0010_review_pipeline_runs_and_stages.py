"""review_pipeline_runs and pipeline_stage_runs

Revision ID: 0010_review_pipeline_runs_and_stages
Revises: 0009_audit_reports_and_manifests
Create Date: 2026-08-21 00:54:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0010_review_pipeline_runs_and_stages'
down_revision: Union[str, None] = '0009_audit_reports_and_manifests'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Crear tabla review_pipeline_runs
    op.create_table(
        'review_pipeline_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scope_type', sa.String(30), server_default='document', nullable=False, index=True),
        sa.Column('scope_id', sa.String(36), nullable=False, index=True),
        sa.Column('pipeline_version', sa.String(30), server_default='v1.0', nullable=False),
        sa.Column('requested_by', sa.String(100), server_default='system_user', nullable=False),
        sa.Column('status', sa.String(30), server_default='queued', nullable=False, index=True),
        sa.Column('current_stage', sa.String(50), server_default='ingest', nullable=False),
        sa.Column('progress_percent', sa.Integer(), server_default='0', nullable=False),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.Column('final_report_id', sa.String(36), sa.ForeignKey('audit_reports.id', ondelete='SET NULL'), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    # 2. Crear tabla pipeline_stage_runs
    op.create_table(
        'pipeline_stage_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('pipeline_run_id', sa.String(36), sa.ForeignKey('review_pipeline_runs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('stage_name', sa.String(50), nullable=False),
        sa.Column('stage_order', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(30), server_default='pending', nullable=False),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('processing_jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('result_summary', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

def downgrade() -> None:
    op.drop_table('pipeline_stage_runs')
    op.drop_table('review_pipeline_runs')
