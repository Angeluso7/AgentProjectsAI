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
    # =========================================================================
    # 1. Campos multimodales en extracted_items
    # =========================================================================
    # candidate_type (premise_candidate, rule_candidate, symbol_candidate, etc.)
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
