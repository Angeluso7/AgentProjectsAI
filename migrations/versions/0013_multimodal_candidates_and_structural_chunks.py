"""multimodal_candidates_and_structural_chunks

Revision ID: 0013_multimodal_candidates_and_structural_chunks
Revises: 0012_golden_datasets_and_evaluations
Create Date: 2026-08-23 22:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0013_multimodal_candidates_and_structural_chunks'
down_revision: Union[str, None] = '0012_golden_datasets_and_evaluations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # Ensure baseline intake & knowledge tables exist before extending them
    if 'source_extractions' not in existing_tables:
        op.create_table(
            'source_extractions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('source_asset_id', sa.String(36), sa.ForeignKey('source_assets.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('extraction_mode', sa.String(30), server_default='ai_document', nullable=False),
            sa.Column('source_origin', sa.String(50), server_default='document', nullable=False, index=True),
            sa.Column('search_query', sa.Text(), nullable=True),
            sa.Column('search_citations', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('document_type', sa.String(50), server_default='norma', nullable=False),
            sa.Column('authority', sa.String(150), nullable=True),
            sa.Column('discipline', sa.String(50), server_default='general', nullable=False, index=True),
            sa.Column('source_file_path', sa.String(500), nullable=True),
            sa.Column('source_url', sa.String(500), nullable=True),
            sa.Column('status', sa.String(30), server_default='draft', nullable=False),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('total_items', sa.Integer(), server_default='0', nullable=False),
            sa.Column('metadata_info', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('source_extractions')

    if 'extracted_items' not in existing_tables:
        op.create_table(
            'extracted_items',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('extraction_id', sa.String(36), sa.ForeignKey('source_extractions.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('item_type', sa.String(50), nullable=False, index=True),
            sa.Column('source_origin', sa.String(50), server_default='document', nullable=False, index=True),
            sa.Column('source_reference', sa.String(500), nullable=True),
            sa.Column('item_nature', sa.String(50), server_default='official_rule', nullable=False),
            sa.Column('governance_note', sa.Text(), nullable=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('code_or_number', sa.String(100), nullable=True, index=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('content_text', sa.Text(), nullable=True),
            sa.Column('ocr_text', sa.Text(), nullable=True),
            sa.Column('crop_image_path', sa.String(500), nullable=True),
            sa.Column('bbox_normalized', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('page_number', sa.Integer(), server_default='1', nullable=False, index=True),
            sa.Column('discipline', sa.String(50), server_default='general', nullable=False, index=True),
            sa.Column('source_asset_id', sa.String(36), nullable=True, index=True),
            sa.Column('target_destination', sa.String(30), server_default='rules_engine', nullable=False),
            sa.Column('review_status', sa.String(30), server_default='draft', nullable=False, index=True),
            sa.Column('structured_matrix', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('validated_at', sa.DateTime(), nullable=True),
            sa.Column('validated_by', sa.String(100), nullable=True),
            sa.Column('metadata_payload', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('extracted_items')

    if 'rule_documents' not in existing_tables:
        op.create_table(
            'rule_documents',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('source_extraction_id', sa.String(36), sa.ForeignKey('source_extractions.id', ondelete='SET NULL'), nullable=True),
            sa.Column('source_asset_id', sa.String(36), sa.ForeignKey('source_assets.id', ondelete='SET NULL'), nullable=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('document_type', sa.String(50), server_default='norma', nullable=False),
            sa.Column('source_origin', sa.String(50), server_default='con_ia', nullable=False),
            sa.Column('authority', sa.String(150), nullable=True),
            sa.Column('discipline', sa.String(50), server_default='general', nullable=False, index=True),
            sa.Column('version', sa.String(50), server_default='1.0', nullable=False),
            sa.Column('status', sa.String(30), server_default='active', nullable=False, index=True),
            sa.Column('items_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('rules_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('tables_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('images_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('symbols_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('metadata_info', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('rule_documents')

    if 'rule_document_items' not in existing_tables:
        op.create_table(
            'rule_document_items',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('rule_document_id', sa.String(36), sa.ForeignKey('rule_documents.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('extracted_item_id', sa.String(36), nullable=True),
            sa.Column('item_type', sa.String(50), nullable=False, index=True),
            sa.Column('source_origin', sa.String(50), server_default='document', nullable=False),
            sa.Column('source_reference', sa.String(500), nullable=True),
            sa.Column('item_nature', sa.String(50), server_default='official_rule', nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('code_or_number', sa.String(100), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('content_text', sa.Text(), nullable=True),
            sa.Column('ocr_text', sa.Text(), nullable=True),
            sa.Column('crop_image_path', sa.String(500), nullable=True),
            sa.Column('target_destination', sa.String(30), server_default='rules_engine', nullable=False),
            sa.Column('status', sa.String(30), server_default='active', nullable=False),
            sa.Column('metadata_payload', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('rule_document_items')

    if 'knowledge_items' not in existing_tables:
        op.create_table(
            'knowledge_items',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True, index=True),
            sa.Column('domain', sa.String(50), nullable=False, index=True),
            sa.Column('item_type', sa.String(50), nullable=False, index=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('content_text', sa.Text(), nullable=False),
            sa.Column('structured_payload', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('discipline', sa.String(50), server_default='general', nullable=False, index=True),
            sa.Column('stage', sa.String(50), nullable=True, index=True),
            sa.Column('status', sa.String(30), server_default='draft', nullable=False, index=True),
            sa.Column('is_active_for_reuse', sa.Boolean(), server_default='false', nullable=False, index=True),
            sa.Column('confidence_score', sa.Float(), server_default='1.0', nullable=False),
            sa.Column('version_number', sa.Integer(), server_default='1', nullable=False),
            sa.Column('parent_item_id', sa.String(36), sa.ForeignKey('knowledge_items.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('superseded_by_id', sa.String(36), sa.ForeignKey('knowledge_items.id', ondelete='SET NULL'), nullable=True),
            sa.Column('valid_from', sa.DateTime(), nullable=False),
            sa.Column('valid_until', sa.DateTime(), nullable=True),
            sa.Column('source_asset_id', sa.String(36), sa.ForeignKey('source_assets.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='SET NULL'), nullable=True),
            sa.Column('rule_id', sa.String(36), sa.ForeignKey('rule_definitions.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('observation_id', sa.String(36), nullable=True, index=True),
            sa.Column('review_run_id', sa.String(36), sa.ForeignKey('review_runs.id', ondelete='SET NULL'), nullable=True),
            sa.Column('stage_snapshot_id', sa.String(36), nullable=True),
            sa.Column('author', sa.String(100), server_default='system', nullable=False),
            sa.Column('origin_type', sa.String(50), server_default='manual_entry', nullable=False),
            sa.Column('provenance_trace', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('tags', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('knowledge_items')

    if 'knowledge_chunks' not in existing_tables:
        op.create_table(
            'knowledge_chunks',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('knowledge_item_id', sa.String(36), sa.ForeignKey('knowledge_items.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('chunk_index', sa.Integer(), server_default='0', nullable=False),
            sa.Column('chunk_title', sa.String(200), nullable=True),
            sa.Column('chunk_text', sa.Text(), nullable=False),
            sa.Column('token_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('metadata_payload', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('embedding_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('knowledge_chunks')

    ei_cols = {col['name'] for col in inspector.get_columns('extracted_items')} if 'extracted_items' in existing_tables else set()
    kc_cols = {col['name'] for col in inspector.get_columns('knowledge_chunks')} if 'knowledge_chunks' in existing_tables else set()

    # =========================================================================
    # 1. Campos multimodales en extracted_items
    # =========================================================================
    # candidate_type (premise_candidate, rule_candidate, symbol_candidate, etc.)
    if 'candidate_type' not in ei_cols:
        op.add_column(
            'extracted_items',
            sa.Column('candidate_type', sa.String(length=50), nullable=True)
        )
    op.create_index(
        'ix_extracted_items_candidate_type',
        'extracted_items',
        ['candidate_type'],
        unique=False
    )

    # derived_text (formulación técnica o síntesis IA)
    op.add_column(
        'extracted_items',
        sa.Column('derived_text', sa.Text(), nullable=True)
    )

    # caption_or_context (contexto circundante, pie de figura, etc.)
    op.add_column(
        'extracted_items',
        sa.Column('caption_or_context', sa.Text(), nullable=True)
    )

    # disclaimer_notes (aviso de conectividad no topológica, etc.)
    op.add_column(
        'extracted_items',
        sa.Column('disclaimer_notes', sa.Text(), nullable=True)
    )

    # evidence_references (lista de IDs de nodos estructurales o cajas delimitadoras)
    op.add_column(
        'extracted_items',
        sa.Column('evidence_references', sa.JSON(), server_default='[]', nullable=True)
    )

    # technical_parameters (diccionario de parámetros específicos extraídos)
    op.add_column(
        'extracted_items',
        sa.Column('technical_parameters', sa.JSON(), server_default='{}', nullable=True)
    )

    # =========================================================================
    # 2. Campos de chunking estructural en knowledge_chunks
    # =========================================================================
    # chunk_type (section_chunk, table_chunk, technical_note, dxf_block_summary, general)
    op.add_column(
        'knowledge_chunks',
        sa.Column('chunk_type', sa.String(length=50), server_default='general', nullable=False)
    )
    op.create_index(
        'ix_knowledge_chunks_chunk_type',
        'knowledge_chunks',
        ['chunk_type'],
        unique=False
    )

    # hierarchy_path (ej. "/Line_Schedule/Area_100/Row_1")
    op.add_column(
        'knowledge_chunks',
        sa.Column('hierarchy_path', sa.String(length=255), nullable=True)
    )

    # structured_data (pares clave/valor, matrices, etc.)
    op.add_column(
        'knowledge_chunks',
        sa.Column('structured_data', sa.JSON(), server_default='{}', nullable=False)
    )


def downgrade() -> None:
    # =========================================================================
    # 2. Reversión en knowledge_chunks
    # =========================================================================
    op.drop_column('knowledge_chunks', 'structured_data')
    op.drop_column('knowledge_chunks', 'hierarchy_path')
    op.drop_index('ix_knowledge_chunks_chunk_type', table_name='knowledge_chunks')
    op.drop_column('knowledge_chunks', 'chunk_type')

    # =========================================================================
    # 1. Reversión en extracted_items
    # =========================================================================
    op.drop_column('extracted_items', 'technical_parameters')
    op.drop_column('extracted_items', 'evidence_references')
    op.drop_column('extracted_items', 'disclaimer_notes')
    op.drop_column('extracted_items', 'caption_or_context')
    op.drop_column('extracted_items', 'derived_text')
    op.drop_index('ix_extracted_items_candidate_type', table_name='extracted_items')
    op.drop_column('extracted_items', 'candidate_type')
