"""create_translations_table

Revision ID: 0021_translations_table
Revises: 0020_structural_nodes_text
Create Date: 2026-09-15 19:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0021_translations_table'
down_revision: Union[str, None] = '0020_structural_nodes_text'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'translations' not in existing_tables:
        op.create_table(
            'translations',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('source_entity_type', sa.String(50), nullable=False),
            sa.Column('source_entity_id', sa.String(36), nullable=False),
            sa.Column('source_language', sa.String(10), nullable=False),
            sa.Column('source_language_confidence', sa.Float(), nullable=True),
            sa.Column('target_language', sa.String(10), nullable=False),
            sa.Column('source_text_hash', sa.String(64), nullable=False),
            sa.Column('translated_title', sa.Text(), nullable=True),
            sa.Column('translated_content', sa.Text(), nullable=True),
            sa.Column('translated_summary', sa.Text(), nullable=True),
            sa.Column('translated_fields', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column('provider', sa.String(50), nullable=False, server_default='gemini'),
            sa.Column('model', sa.String(50), nullable=False, server_default='gemini-1.5-pro'),
            sa.Column('prompt_version', sa.String(20), nullable=False, server_default='v1.0'),
            sa.Column('translation_status', sa.String(20), nullable=False, server_default='completed'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('source_entity_type', 'source_entity_id', 'target_language', 'source_text_hash', name='uq_translations_entity_target_hash')
        )
        op.create_index('ix_translations_organization_id', 'translations', ['organization_id'])
        op.create_index('ix_translations_source_entity_type', 'translations', ['source_entity_type'])
        op.create_index('ix_translations_source_entity_id', 'translations', ['source_entity_id'])
        op.create_index('ix_translations_target_language', 'translations', ['target_language'])
        op.create_index('ix_translations_source_text_hash', 'translations', ['source_text_hash'])
        op.create_index('ix_translations_translation_status', 'translations', ['translation_status'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'translations' in existing_tables:
        op.drop_index('ix_translations_translation_status', table_name='translations')
        op.drop_index('ix_translations_source_text_hash', table_name='translations')
        op.drop_index('ix_translations_target_language', table_name='translations')
        op.drop_index('ix_translations_source_entity_id', table_name='translations')
        op.drop_index('ix_translations_source_entity_type', table_name='translations')
        op.drop_index('ix_translations_organization_id', table_name='translations')
        op.drop_table('translations')
