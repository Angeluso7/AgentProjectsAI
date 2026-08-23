"""initial schema for plan review ai hybrid

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-08-20 23:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Projects & Versions
    op.create_table(
        'projects',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, index=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('client_name', sa.String(150), nullable=True),
        sa.Column('discipline', sa.String(50), server_default='architecture', nullable=False),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'project_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_tag', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(30), server_default='draft', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(150), unique=True, index=True, nullable=False),
        sa.Column('full_name', sa.String(150), nullable=False),
        sa.Column('role', sa.String(30), server_default='reviewer', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False)
    )

    # 2. Knowledge Assets
    op.create_table(
        'knowledge_assets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('code', sa.String(100), unique=True, index=True, nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('asset_type', sa.String(50), nullable=False),
        sa.Column('discipline', sa.String(50), server_default='general', nullable=False),
        sa.Column('version', sa.String(30), server_default='1.0', nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('content_payload', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    # 3. Document Memory
    op.create_table(
        'documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_version_id', sa.String(36), sa.ForeignKey('project_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_hash_sha256', sa.String(64), unique=True, index=True, nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(100), server_default='application/pdf', nullable=False),
        sa.Column('is_vector_pdf', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('page_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('status', sa.String(30), server_default='uploaded', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata_info', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'document_sheets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sheet_number', sa.Integer(), nullable=False),
        sa.Column('sheet_code', sa.String(100), index=True, nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('scale', sa.String(50), nullable=True),
        sa.Column('revision', sa.String(20), nullable=True),
        sa.Column('date_str', sa.String(50), nullable=True),
        sa.Column('width_px', sa.Integer(), nullable=False),
        sa.Column('height_px', sa.Integer(), nullable=False),
        sa.Column('width_mm', sa.Float(), nullable=True),
        sa.Column('height_mm', sa.Float(), nullable=True),
        sa.Column('dpi', sa.Integer(), server_default='300', nullable=False),
        sa.Column('rotation_deg', sa.Integer(), server_default='0', nullable=False),
        sa.Column('raster_image_path', sa.String(500), nullable=True),
        sa.Column('thumbnail_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'sheet_regions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('region_type', sa.String(50), nullable=False),
        sa.Column('polygon_points', sa.JSON(), nullable=False),
        sa.Column('bbox', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'extracted_texts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('region_id', sa.String(36), sa.ForeignKey('sheet_regions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('clean_text', sa.Text(), nullable=True),
        sa.Column('bbox', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('font_name', sa.String(100), nullable=True),
        sa.Column('font_size', sa.Float(), nullable=True),
        sa.Column('angle', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('source', sa.String(30), server_default='vector', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'extracted_tables',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('table_type', sa.String(50), nullable=True),
        sa.Column('bbox', sa.JSON(), nullable=False),
        sa.Column('headers', sa.JSON(), nullable=True),
        sa.Column('rows', sa.JSON(), nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('confidence', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'detected_symbols',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol_class', sa.String(100), nullable=False),
        sa.Column('category', sa.String(50), server_default='architecture', nullable=False),
        sa.Column('bbox', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('detector_name', sa.String(50), server_default='yolo_v11', nullable=False),
        sa.Column('attributes', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'visual_evidences',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('bbox', sa.JSON(), nullable=False),
        sa.Column('image_path', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 4. Normative Memory
    op.create_table(
        'normative_documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, index=True, nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('authority', sa.String(150), nullable=True),
        sa.Column('country', sa.String(10), server_default='CL', nullable=False),
        sa.Column('discipline', sa.String(50), nullable=False),
        sa.Column('version_year', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('metadata_info', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'normative_clauses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('normative_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('clause_number', sa.String(50), index=True, nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('scope_keywords', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'normative_criteria',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('clause_id', sa.String(36), sa.ForeignKey('normative_clauses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('criterion_code', sa.String(100), unique=True, index=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_entity', sa.String(50), nullable=False),
        sa.Column('property_name', sa.String(50), nullable=False),
        sa.Column('operator', sa.String(20), nullable=False),
        sa.Column('threshold_value', sa.JSON(), nullable=False),
        sa.Column('severity', sa.String(20), server_default='high', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'normative_embeddings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('clause_id', sa.String(36), sa.ForeignKey('normative_clauses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('embedding_model', sa.String(100), server_default='sentence-transformers/all-MiniLM-L6-v2', nullable=False),
        sa.Column('vector_data', sa.JSON(), nullable=False),
        sa.Column('dimension', sa.Integer(), server_default='384', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 5. Template Memory
    op.create_table(
        'title_block_templates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(150), unique=True, index=True, nullable=False),
        sa.Column('client_or_standard', sa.String(100), nullable=True),
        sa.Column('discipline', sa.String(50), server_default='general', nullable=False),
        sa.Column('relative_position', sa.String(50), server_default='bottom_right', nullable=False),
        sa.Column('expected_bbox', sa.JSON(), nullable=False),
        sa.Column('field_anchors', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'symbol_libraries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(150), unique=True, index=True, nullable=False),
        sa.Column('discipline', sa.String(50), nullable=False),
        sa.Column('standard_name', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'symbol_templates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('library_id', sa.String(36), sa.ForeignKey('symbol_libraries.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol_class', sa.String(100), index=True, nullable=False),
        sa.Column('display_name', sa.String(150), nullable=False),
        sa.Column('aliases', sa.JSON(), nullable=True),
        sa.Column('image_template_path', sa.String(500), nullable=True),
        sa.Column('vector_svg_path', sa.String(500), nullable=True),
        sa.Column('feature_descriptors', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'table_schema_templates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('schema_code', sa.String(100), unique=True, index=True, nullable=False),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('discipline', sa.String(50), server_default='architecture', nullable=False),
        sa.Column('columns_spec', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'ontology_dictionaries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('domain', sa.String(50), index=True, nullable=False),
        sa.Column('canonical_term', sa.String(100), index=True, nullable=False),
        sa.Column('display_label', sa.String(150), nullable=False),
        sa.Column('synonyms', sa.JSON(), nullable=False),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    # 6. Decision Memory
    op.create_table(
        'review_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('run_name', sa.String(200), nullable=False),
        sa.Column('status', sa.String(30), server_default='pending', nullable=False),
        sa.Column('rules_applied_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('findings_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('execution_time_sec', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('summary_stats', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'rule_findings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('review_run_id', sa.String(36), sa.ForeignKey('review_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='CASCADE'), nullable=True),
        sa.Column('rule_code', sa.String(100), index=True, nullable=False),
        sa.Column('rule_name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), server_default='medium', nullable=False),
        sa.Column('confidence', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('status', sa.String(30), server_default='open', nullable=False),
        sa.Column('bbox', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'finding_evidences',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('finding_id', sa.String(36), sa.ForeignKey('rule_findings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('evidence_type', sa.String(50), nullable=False),
        sa.Column('reference_id', sa.String(36), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('crop_image_path', sa.String(500), nullable=True),
        sa.Column('metadata_info', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'human_feedbacks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('finding_id', sa.String(36), sa.ForeignKey('rule_findings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('corrected_bbox', sa.JSON(), nullable=True),
        sa.Column('corrected_class', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('sent_to_active_learning', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'decision_precedents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True),
        sa.Column('rule_code', sa.String(100), index=True, nullable=False),
        sa.Column('condition_signature', sa.JSON(), nullable=False),
        sa.Column('resolution', sa.String(50), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('approved_by', sa.String(150), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )


def downgrade() -> None:
    op.drop_table('decision_precedents')
    op.drop_table('human_feedbacks')
    op.drop_table('finding_evidences')
    op.drop_table('rule_findings')
    op.drop_table('review_runs')
    op.drop_table('ontology_dictionaries')
    op.drop_table('table_schema_templates')
    op.drop_table('symbol_templates')
    op.drop_table('symbol_libraries')
    op.drop_table('title_block_templates')
    op.drop_table('normative_embeddings')
    op.drop_table('normative_criteria')
    op.drop_table('normative_clauses')
    op.drop_table('normative_documents')
    op.drop_table('visual_evidences')
    op.drop_table('detected_symbols')
    op.drop_table('extracted_tables')
    op.drop_table('extracted_texts')
    op.drop_table('sheet_regions')
    op.drop_table('document_sheets')
    op.drop_table('documents')
    op.drop_table('knowledge_assets')
    op.drop_table('audit_logs')
    op.drop_table('users')
    op.drop_table('project_versions')
    op.drop_table('projects')
