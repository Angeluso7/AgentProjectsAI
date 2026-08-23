"""extracted_tables and extracted_table_cells schema update

Revision ID: 0006_extracted_tables_and_cells
Revises: 0005_operations_jobs_and_review
Create Date: 2026-08-21 00:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0006_extracted_tables_and_cells'
down_revision: Union[str, None] = '0005_operations_jobs_and_review'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Ajuste/recreación de extracted_tables
    # Si la tabla ya existía en 0001 con esquema simple, agregamos las columnas nuevas
    with op.batch_alter_table('extracted_tables') as batch_op:
        batch_op.add_column(sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=True))
        batch_op.add_column(sa.Column('region_id', sa.String(36), sa.ForeignKey('sheet_regions.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('title', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('bbox_normalized', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('row_count', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('column_count', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('extraction_status', sa.String(30), server_default='extracted', nullable=False))
        batch_op.add_column(sa.Column('source_engine', sa.String(50), server_default='spatial_grid_reconstruction', nullable=False))
        batch_op.add_column(sa.Column('source_version', sa.String(30), server_default='v1.0', nullable=False))
        batch_op.add_column(sa.Column('raw_structure', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # 2. Crear extracted_table_cells
    op.create_table(
        'extracted_table_cells',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('table_id', sa.String(36), sa.ForeignKey('extracted_tables.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('row_index', sa.Integer(), nullable=False),
        sa.Column('column_index', sa.Integer(), nullable=False),
        sa.Column('row_span', sa.Integer(), server_default='1', nullable=False),
        sa.Column('col_span', sa.Integer(), server_default='1', nullable=False),
        sa.Column('text', sa.Text(), server_default='', nullable=False),
        sa.Column('normalized_text', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('bbox', sa.JSON(), nullable=False),
        sa.Column('bbox_normalized', sa.JSON(), nullable=False),
        sa.Column('is_header', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('source_text_refs', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )

def downgrade() -> None:
    op.drop_table('extracted_table_cells')
    with op.batch_alter_table('extracted_tables') as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('raw_structure')
        batch_op.drop_column('source_version')
        batch_op.drop_column('source_engine')
        batch_op.drop_column('extraction_status')
        batch_op.drop_column('column_count')
        batch_op.drop_column('row_count')
        batch_op.drop_column('bbox_normalized')
        batch_op.drop_column('title')
        batch_op.drop_column('region_id')
        batch_op.drop_column('document_id')
