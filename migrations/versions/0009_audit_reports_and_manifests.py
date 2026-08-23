"""audit_reports and evidence_manifests

Revision ID: 0009_audit_reports_and_manifests
Revises: 0008_rule_engine_and_qaqc_findings
Create Date: 2026-08-21 00:46:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0009_audit_reports_and_manifests'
down_revision: Union[str, None] = '0008_rule_engine_and_qaqc_findings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Crear tabla audit_reports
    op.create_table(
        'audit_reports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('report_type', sa.String(50), server_default='technical_audit_qaqc', nullable=False),
        sa.Column('report_scope', sa.String(30), server_default='sheet', nullable=False),
        sa.Column('status', sa.String(30), server_default='completed', nullable=False),
        sa.Column('generated_by', sa.String(100), server_default='system_audit_engine', nullable=False),
        sa.Column('source_rule_execution_ids', sa.JSON(), nullable=True),
        sa.Column('source_finding_ids', sa.JSON(), nullable=True),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.Column('artifact_pdf_path', sa.String(500), nullable=True),
        sa.Column('artifact_json_path', sa.String(500), nullable=True),
        sa.Column('artifact_bundle_path', sa.String(500), nullable=True),
        sa.Column('manifest_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    # 2. Crear tabla evidence_manifests
    op.create_table(
        'evidence_manifests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('report_id', sa.String(36), sa.ForeignKey('audit_reports.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
        sa.Column('manifest_json', sa.JSON(), nullable=False),
        sa.Column('sha256_bundle', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

def downgrade() -> None:
    op.drop_table('evidence_manifests')
    op.drop_table('audit_reports')
