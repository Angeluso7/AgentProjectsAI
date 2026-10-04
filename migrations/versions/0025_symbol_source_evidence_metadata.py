"""symbol_source_evidence_metadata

Revision ID: 0025_symbol_source_evidence_metadata
Revises: 0024_symbol_governance
Create Date: 2026-09-22 09:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0025_symbol_source_evidence_metadata'
down_revision: Union[str, None] = '0024_symbol_governance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'symbol_source_evidences' in existing_tables:
        existing_cols = [col['name'] for col in inspector.get_columns('symbol_source_evidences')]
        
        if 'source_authority' not in existing_cols:
            op.add_column('symbol_source_evidences', sa.Column('source_authority', sa.String(150), nullable=True))
        if 'discipline' not in existing_cols:
            op.add_column('symbol_source_evidences', sa.Column('discipline', sa.String(50), nullable=True))
        if 'sheet_name' not in existing_cols:
            op.add_column('symbol_source_evidences', sa.Column('sheet_name', sa.String(150), nullable=True))
        if 'sheet_code' not in existing_cols:
            op.add_column('symbol_source_evidences', sa.Column('sheet_code', sa.String(50), nullable=True))
        if 'extractor_version' not in existing_cols:
            op.add_column('symbol_source_evidences', sa.Column('extractor_version', sa.String(50), nullable=True))
        if 'evidence_metadata' not in existing_cols:
            op.add_column('symbol_source_evidences', sa.Column('evidence_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'symbol_source_evidences' in existing_tables:
        existing_cols = [col['name'] for col in inspector.get_columns('symbol_source_evidences')]
        
        if 'evidence_metadata' in existing_cols:
            op.drop_column('symbol_source_evidences', 'evidence_metadata')
        if 'extractor_version' in existing_cols:
            op.drop_column('symbol_source_evidences', 'extractor_version')
        if 'sheet_code' in existing_cols:
            op.drop_column('symbol_source_evidences', 'sheet_code')
        if 'sheet_name' in existing_cols:
            op.drop_column('symbol_source_evidences', 'sheet_name')
        if 'discipline' in existing_cols:
            op.drop_column('symbol_source_evidences', 'discipline')
        if 'source_authority' in existing_cols:
            op.drop_column('symbol_source_evidences', 'source_authority')
