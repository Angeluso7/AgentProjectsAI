"""add_piping_line_segments

Revision ID: 0036_add_piping_line_segments
Revises: 0035_add_discipline_code_to_document_deliverables
Create Date: 2026-10-11 00:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0036_add_piping_line_segments'
down_revision: Union[str, None] = '0035_add_discipline_code_to_document_deliverables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table('piping_line_segments'):
        op.create_table(
            'piping_line_segments',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('sheet_id', sa.String(length=36), sa.ForeignKey('document_sheets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('polyline_points', sa.JSON(), nullable=False),
            sa.Column('bbox_normalized', sa.JSON(), nullable=False),
            sa.Column('line_style', sa.String(length=30), nullable=False, server_default='solid'),
            sa.Column('length_mm', sa.Float(), nullable=False),
            sa.Column('stroke_width_pt', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('connected_symbol_ids', sa.JSON(), nullable=False),
            sa.Column('is_main_process_line', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('attributes', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False)
        )
        op.create_index(
            op.f('ix_piping_line_segments_sheet_id'),
            'piping_line_segments',
            ['sheet_id'],
            unique=False
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if inspector.has_table('piping_line_segments'):
        op.drop_index(
            op.f('ix_piping_line_segments_sheet_id'),
            table_name='piping_line_segments'
        )
        op.drop_table('piping_line_segments')
