"""golden_datasets_and_evaluations

Revision ID: 0012_golden_datasets_and_evaluations
Revises: 0011_organizations_users_rbac_and_multitenancy
Create Date: 2026-08-21 01:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0012_golden_datasets_and_evaluations'
down_revision: Union[str, None] = '0011_organizations_users_rbac_and_multitenancy'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Tabla evaluation_datasets
    op.create_table(
        'evaluation_datasets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('dataset_type', sa.String(50), server_default='golden', nullable=False),
        sa.Column('discipline', sa.String(50), server_default='architecture', nullable=False),
        sa.Column('version', sa.String(30), server_default='1.0', nullable=False),
        sa.Column('status', sa.String(30), server_default='draft', nullable=False),
        sa.Column('source_policy', sa.String(50), server_default='consented', nullable=False),
        sa.Column('snapshot_manifest_hash', sa.String(64), nullable=True),
        sa.Column('frozen_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(100), server_default='system_evaluator', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    # 2. Tabla evaluation_samples
    op.create_table(
        'evaluation_samples',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('dataset_id', sa.String(36), sa.ForeignKey('evaluation_datasets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('source_asset_id', sa.String(36), sa.ForeignKey('source_assets.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('sample_key', sa.String(150), nullable=False),
        sa.Column('discipline', sa.String(50), server_default='architecture', nullable=False),
        sa.Column('drawing_type', sa.String(100), server_default='floor_plan', nullable=False),
        sa.Column('source_checksum', sa.String(64), nullable=False),
        sa.Column('split', sa.String(30), server_default='test', nullable=False),
        sa.Column('annotation_status', sa.String(30), server_default='pending', nullable=False),
        sa.Column('approved_by', sa.String(100), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    # 3. Tabla annotation_sets
    op.create_table(
        'annotation_sets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sample_id', sa.String(36), sa.ForeignKey('evaluation_samples.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('annotation_type', sa.String(50), nullable=False),
        sa.Column('schema_version', sa.String(30), server_default='v1.0', nullable=False),
        sa.Column('status', sa.String(30), server_default='draft', nullable=False),
        sa.Column('annotator_id', sa.String(100), nullable=True),
        sa.Column('reviewer_id', sa.String(100), nullable=True),
        sa.Column('source', sa.String(50), server_default='human', nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('superseded_by_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True)
    )

    # 4. Tabla evaluation_runs
    op.create_table(
        'evaluation_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('dataset_id', sa.String(36), sa.ForeignKey('evaluation_datasets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('dataset_version', sa.String(30), server_default='1.0', nullable=False),
        sa.Column('pipeline_version', sa.String(50), server_default='v1.0', nullable=False),
        sa.Column('git_commit_hash', sa.String(40), nullable=True),
        sa.Column('model_versions', sa.JSON(), nullable=True),
        sa.Column('rule_pack_version', sa.String(50), server_default='v1.0-oguc', nullable=False),
        sa.Column('ocr_raster_config', sa.JSON(), nullable=True),
        sa.Column('inference_thresholds', sa.JSON(), nullable=True),
        sa.Column('prompts_and_rules_config', sa.JSON(), nullable=True),
        sa.Column('split_evaluated', sa.String(30), server_default='test', nullable=False),
        sa.Column('status', sa.String(30), server_default='queued', nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.Column('artifact_paths', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(100), server_default='system_evaluator', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 5. Tabla evaluation_metrics
    op.create_table(
        'evaluation_metrics',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('evaluation_run_id', sa.String(36), sa.ForeignKey('evaluation_runs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('category', sa.String(30), server_default='perceptual', nullable=False),
        sa.Column('component', sa.String(50), nullable=False),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('metric_unit', sa.String(30), server_default='ratio', nullable=False),
        sa.Column('scope', sa.JSON(), nullable=True),
        sa.Column('confidence_interval', sa.JSON(), nullable=True),
        sa.Column('sample_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

def downgrade() -> None:
    op.drop_table('evaluation_metrics')
    op.drop_table('evaluation_runs')
    op.drop_table('annotation_sets')
    op.drop_table('evaluation_samples')
    op.drop_table('evaluation_datasets')
