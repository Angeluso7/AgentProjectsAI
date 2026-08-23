"""detected_symbols schema update for visual detection and template memory

Revision ID: 0007_detected_symbols_and_libraries
Revises: 0006_extracted_tables_and_cells
Create Date: 2026-08-21 00:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0007_detected_symbols_and_libraries'
down_revision: Union[str, None] = '0006_extracted_tables_and_cells'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Ajuste de detected_symbols con batch_alter_table para compatibilidad SQLite/PostgreSQL
    with op.batch_alter_table('detected_symbols') as batch_op:
        batch_op.add_column(sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=True))
        batch_op.add_column(sa.Column('symbol_type', sa.String(100), server_default='unknown_symbol_candidate', nullable=False))
        batch_op.add_column(sa.Column('discipline', sa.String(50), server_default='architecture', nullable=False))
        batch_op.add_column(sa.Column('bbox_normalized', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('polygon_points', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('detection_status', sa.String(30), server_default='detected', nullable=False))
        batch_op.add_column(sa.Column('source_engine', sa.String(50), server_default='yolo_sahi_hybrid', nullable=False))
        batch_op.add_column(sa.Column('source_version', sa.String(30), server_default='v1.0', nullable=False))
        batch_op.add_column(sa.Column('source_asset_template_id', sa.String(36), nullable=True))
        batch_op.add_column(sa.Column('matched_library_entry_id', sa.String(36), sa.ForeignKey('symbol_templates.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table('detected_symbols') as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('matched_library_entry_id')
        batch_op.drop_column('source_asset_template_id')
        batch_op.drop_column('source_version')
        batch_op.drop_column('source_engine')
        batch_op.drop_column('detection_status')
        batch_op.drop_column('polygon_points')
        batch_op.drop_column('bbox_normalized')
        batch_op.drop_column('discipline')
        batch_op.drop_column('symbol_type')
        batch_op.drop_column('document_id')
