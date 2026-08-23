"""add layout columns and title_block_extractions table

Revision ID: 0003_layout_and_title_block_extractions
Revises: 0002_add_bbox_normalized
Create Date: 2026-08-20 23:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003_layout_and_title_block_extractions'
down_revision: Union[str, None] = '0002_add_bbox_normalized'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Columnas adicionales para sheet_regions
    op.add_column('sheet_regions', sa.Column('bbox_normalized', sa.JSON(), nullable=True))
    op.add_column('sheet_regions', sa.Column('detection_method', sa.String(50), server_default='hybrid_heuristic', nullable=False))
    op.add_column('sheet_regions', sa.Column('source_version', sa.String(30), server_default='v1.0', nullable=False))
    op.add_column('sheet_regions', sa.Column('attributes', sa.JSON(), nullable=True))

    # 2. Tabla title_block_extractions
    op.create_table(
        'title_block_extractions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('template_id', sa.String(36), sa.ForeignKey('title_block_templates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('match_score', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('extraction_status', sa.String(30), server_default='extracted', nullable=False),
        sa.Column('sheet_code', sa.String(100), nullable=True),
        sa.Column('sheet_title', sa.String(255), nullable=True),
        sa.Column('revision', sa.String(50), nullable=True),
        sa.Column('scale_text', sa.String(50), nullable=True),
        sa.Column('date_text', sa.String(50), nullable=True),
        sa.Column('project_name', sa.String(255), nullable=True),
        sa.Column('discipline', sa.String(50), nullable=True),
        sa.Column('drawn_by', sa.String(100), nullable=True),
        sa.Column('checked_by', sa.String(100), nullable=True),
        sa.Column('approved_by', sa.String(100), nullable=True),
        sa.Column('matched_anchors', sa.JSON(), nullable=True),
        sa.Column('unmatched_required_fields', sa.JSON(), nullable=True),
        sa.Column('raw_fields', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

def downgrade() -> None:
    op.drop_table('title_block_extractions')
    op.drop_column('sheet_regions', 'attributes')
    op.drop_column('sheet_regions', 'source_version')
    op.drop_column('sheet_regions', 'detection_method')
    op.drop_column('sheet_regions', 'bbox_normalized')
