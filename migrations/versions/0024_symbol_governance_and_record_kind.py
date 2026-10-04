"""symbol_governance_and_record_kind

Revision ID: 0024_symbol_governance
Revises: 0023_piping_canonical_catalog
Create Date: 2026-09-22 02:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0024_symbol_governance'
down_revision: Union[str, None] = '0023_piping_canonical_catalog'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'detected_symbols' in existing_tables:
        det_columns = [col['name'] for col in inspector.get_columns('detected_symbols')]
        if 'record_kind' not in det_columns:
            op.add_column('detected_symbols', sa.Column('record_kind', sa.String(30), nullable=False, server_default='candidate'))
        if 'environment' not in det_columns:
            op.add_column('detected_symbols', sa.Column('environment', sa.String(30), nullable=False, server_default='production'))

        det_indexes = [idx['name'] for idx in inspector.get_indexes('detected_symbols')]
        if 'ix_detected_symbols_record_kind' not in det_indexes:
            op.create_index('ix_detected_symbols_record_kind', 'detected_symbols', ['record_kind'])
        if 'ix_detected_symbols_environment' not in det_indexes:
            op.create_index('ix_detected_symbols_environment', 'detected_symbols', ['environment'])

    if 'extracted_table_cells' in existing_tables:
        cell_columns = [col['name'] for col in inspector.get_columns('extracted_table_cells')]
        if 'cell_type' not in cell_columns:
            op.add_column('extracted_table_cells', sa.Column('cell_type', sa.String(30), nullable=False, server_default='text_cell'))
        if 'symbol_id' not in cell_columns:
            op.add_column('extracted_table_cells', sa.Column('symbol_id', sa.String(36), nullable=True))
        if 'has_symbol' not in cell_columns:
            op.add_column('extracted_table_cells', sa.Column('has_symbol', sa.Boolean(), nullable=False, server_default=sa.false()))
        cell_indexes = [idx['name'] for idx in inspector.get_indexes('extracted_table_cells')]
        if 'ix_extracted_table_cells_cell_type' not in cell_indexes:
            op.create_index('ix_extracted_table_cells_cell_type', 'extracted_table_cells', ['cell_type'])
        if 'ix_extracted_table_cells_symbol_id' not in cell_indexes:
            op.create_index('ix_extracted_table_cells_symbol_id', 'extracted_table_cells', ['symbol_id'])

    if 'knowledge_items' in existing_tables:
        ki_columns = [col['name'] for col in inspector.get_columns('knowledge_items')]
        if 'ingestion_channel' not in ki_columns:
            op.add_column('knowledge_items', sa.Column('ingestion_channel', sa.String(64), nullable=True, server_default='manual_entry'))
        ki_indexes = [idx['name'] for idx in inspector.get_indexes('knowledge_items')]
        if 'ix_knowledge_items_ingestion_channel' not in ki_indexes:
            op.create_index('ix_knowledge_items_ingestion_channel', 'knowledge_items', ['ingestion_channel'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'knowledge_items' in existing_tables:
        ki_indexes = {idx['name'] for idx in inspector.get_indexes('knowledge_items')}
        if 'ix_knowledge_items_ingestion_channel' in ki_indexes:
            op.drop_index('ix_knowledge_items_ingestion_channel', table_name='knowledge_items')
        ki_columns = [col['name'] for col in inspector.get_columns('knowledge_items')]
        if 'ingestion_channel' in ki_columns:
            op.drop_column('knowledge_items', 'ingestion_channel')

    if 'extracted_table_cells' in existing_tables:
        cell_indexes = {idx['name'] for idx in inspector.get_indexes('extracted_table_cells')}
        if 'ix_extracted_table_cells_symbol_id' in cell_indexes:
            op.drop_index('ix_extracted_table_cells_symbol_id', table_name='extracted_table_cells')
        if 'ix_extracted_table_cells_cell_type' in cell_indexes:
            op.drop_index('ix_extracted_table_cells_cell_type', table_name='extracted_table_cells')
        cell_columns = [col['name'] for col in inspector.get_columns('extracted_table_cells')]
        if 'has_symbol' in cell_columns:
            op.drop_column('extracted_table_cells', 'has_symbol')
        if 'symbol_id' in cell_columns:
            op.drop_column('extracted_table_cells', 'symbol_id')
        if 'cell_type' in cell_columns:
            op.drop_column('extracted_table_cells', 'cell_type')

    if 'detected_symbols' in existing_tables:
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('detected_symbols')}
        if 'ix_detected_symbols_environment' in existing_indexes:
            op.drop_index('ix_detected_symbols_environment', table_name='detected_symbols')
        if 'ix_detected_symbols_record_kind' in existing_indexes:
            op.drop_index('ix_detected_symbols_record_kind', table_name='detected_symbols')

        det_columns = [col['name'] for col in inspector.get_columns('detected_symbols')]
        if 'environment' in det_columns:
            op.drop_column('detected_symbols', 'environment')
        if 'record_kind' in det_columns:
            op.drop_column('detected_symbols', 'record_kind')
