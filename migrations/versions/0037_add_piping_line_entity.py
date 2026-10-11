"""add_piping_line_entity

Revision ID: 0037_add_piping_line_entity
Revises: 0036_add_piping_line_segments
Create Date: 2026-10-11 01:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0037_add_piping_line_entity'
down_revision: Union[str, None] = '0036_add_piping_line_segments'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Crear tabla piping_lines si no existe
    if not inspector.has_table('piping_lines'):
        op.create_table(
            'piping_lines',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('project_id', sa.String(length=36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('line_number', sa.String(length=100), nullable=True),
            sa.Column('nominal_size', sa.String(length=50), nullable=True),
            sa.Column('service_fluid', sa.String(length=50), nullable=True),
            sa.Column('spec_class', sa.String(length=50), nullable=True),
            sa.Column('insulation', sa.String(length=50), nullable=True),
            sa.Column('design_pressure', sa.Float(), nullable=True),
            sa.Column('design_temperature', sa.Float(), nullable=True),
            sa.Column('from_equipment_tag', sa.String(length=100), nullable=True),
            sa.Column('to_equipment_tag', sa.String(length=100), nullable=True),
            sa.Column('flow_direction', sa.String(length=30), nullable=False, server_default='unconfirmed'),
            sa.Column('source', sa.String(length=50), nullable=False, server_default='auto_vector_extraction'),
            sa.Column('confidence_status', sa.String(length=30), nullable=False, server_default='auto_low_needs_review'),
            sa.Column('attributes', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        op.create_index(op.f('ix_piping_lines_project_id'), 'piping_lines', ['project_id'], unique=False)
        op.create_index(op.f('ix_piping_lines_line_number'), 'piping_lines', ['line_number'], unique=False)

    # 2. Agregar columna piping_line_id en piping_line_segments si no existe
    if inspector.has_table('piping_line_segments'):
        cols = [c['name'] for c in inspector.get_columns('piping_line_segments')]
        if 'piping_line_id' not in cols:
            op.add_column(
                'piping_line_segments',
                sa.Column('piping_line_id', sa.String(length=36), sa.ForeignKey('piping_lines.id', ondelete='SET NULL'), nullable=True)
            )
            op.create_index(
                op.f('ix_piping_line_segments_piping_line_id'),
                'piping_line_segments',
                ['piping_line_id'],
                unique=False
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Eliminar piping_line_id de piping_line_segments si existe
    if inspector.has_table('piping_line_segments'):
        cols = [c['name'] for c in inspector.get_columns('piping_line_segments')]
        if 'piping_line_id' in cols:
            op.drop_index(op.f('ix_piping_line_segments_piping_line_id'), table_name='piping_line_segments')
            op.drop_column('piping_line_segments', 'piping_line_id')

    # 2. Eliminar tabla piping_lines si existe
    if inspector.has_table('piping_lines'):
        op.drop_index(op.f('ix_piping_lines_line_number'), table_name='piping_lines')
        op.drop_index(op.f('ix_piping_lines_project_id'), table_name='piping_lines')
        op.drop_table('piping_lines')
