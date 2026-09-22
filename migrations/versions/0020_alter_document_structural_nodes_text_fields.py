"""alter_document_structural_nodes_text_fields

Revision ID: 0020_structural_nodes_text
Revises: 0019_piping_symbol_dual
Create Date: 2026-09-11 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0020_structural_nodes_text'
down_revision: Union[str, None] = '0019_piping_symbol_dual'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'document_structural_nodes' in existing_tables:
        columns = {c['name']: c for c in inspector.get_columns('document_structural_nodes')}

        # 1. hierarchy_path: cambiar de VARCHAR(255) a TEXT para permitir rutas jerárquicas sin truncamiento
        if 'hierarchy_path' in columns:
            op.alter_column(
                'document_structural_nodes',
                'hierarchy_path',
                type_=sa.Text(),
                existing_type=sa.String(length=255),
                nullable=True
            )

        # 2. content_text: asegurar tipo TEXT
        if 'content_text' in columns:
            op.alter_column(
                'document_structural_nodes',
                'content_text',
                type_=sa.Text(),
                existing_type=columns['content_text'].get('type', sa.Text()),
                nullable=False
            )
    else:
        # Crear tabla si no existe
        op.create_table(
            'document_structural_nodes',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='SET NULL'), nullable=True),
            sa.Column('node_type', sa.String(30), nullable=False),
            sa.Column('hierarchy_path', sa.Text(), nullable=True),
            sa.Column('level', sa.Integer(), server_default='0', nullable=False),
            sa.Column('title', sa.String(255), nullable=True),
            sa.Column('content_text', sa.Text(), nullable=False),
            sa.Column('structured_payload', sa.JSON(), nullable=False),
            sa.Column('page_number', sa.Integer(), nullable=True),
            sa.Column('bbox_normalized', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False)
        )
        op.create_index(
            'ix_document_structural_nodes_document_id',
            'document_structural_nodes',
            ['document_id']
        )
        op.create_index(
            'ix_document_structural_nodes_sheet_id',
            'document_structural_nodes',
            ['sheet_id']
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'document_structural_nodes' in existing_tables:
        columns = {c['name']: c for c in inspector.get_columns('document_structural_nodes')}
        if 'hierarchy_path' in columns:
            op.alter_column(
                'document_structural_nodes',
                'hierarchy_path',
                type_=sa.String(length=255),
                existing_type=sa.Text(),
                nullable=True
            )
