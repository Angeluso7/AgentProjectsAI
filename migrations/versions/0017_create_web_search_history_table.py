"""create_web_search_history_table

Revision ID: 0017_web_search_history_audit
Revises: 0016_structured_persistence_and_provenance
Create Date: 2026-08-25 11:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0017_web_search_history_audit'
down_revision: Union[str, None] = '0016_structured_persistence_and_provenance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'web_search_history' not in tables:
        op.create_table(
            'web_search_history',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('organization_id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=True),
            sa.Column('user_id', sa.String(length=100), nullable=True),
            sa.Column('search_prompt', sa.Text(), nullable=False),
            sa.Column('discipline', sa.String(length=50), server_default='general', nullable=False),
            sa.Column('document_type', sa.String(length=50), server_default='any_web_doc', nullable=False),
            sa.Column('provider_used', sa.String(length=50), server_default='duckduckgo', nullable=False),
            sa.Column('detected_language', sa.String(length=20), server_default='es', nullable=False),
            sa.Column('results_found', sa.JSON(), nullable=False),
            sa.Column('discarded_sources', sa.JSON(), nullable=False),
            sa.Column('selected_sources', sa.JSON(), nullable=False),
            sa.Column('stage_applied', sa.String(length=50), server_default='stage_1_strict', nullable=False),
            sa.Column('extraction_status', sa.String(length=30), server_default='searched', nullable=False),
            sa.Column('source_extraction_id', sa.String(length=36), nullable=True),
            sa.Column('metadata_payload', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['source_extraction_id'], ['source_extractions.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_web_search_history_organization_id', 'web_search_history', ['organization_id'], unique=False)
        op.create_index('ix_web_search_history_project_id', 'web_search_history', ['project_id'], unique=False)
        op.create_index('ix_web_search_history_user_id', 'web_search_history', ['user_id'], unique=False)
        op.create_index('ix_web_search_history_discipline', 'web_search_history', ['discipline'], unique=False)
        op.create_index('ix_web_search_history_extraction_status', 'web_search_history', ['extraction_status'], unique=False)
        op.create_index('ix_web_search_history_source_extraction_id', 'web_search_history', ['source_extraction_id'], unique=False)
        op.create_index('ix_web_search_history_created_at', 'web_search_history', ['created_at'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'web_search_history' in tables:
        op.drop_index('ix_web_search_history_created_at', table_name='web_search_history')
        op.drop_index('ix_web_search_history_source_extraction_id', table_name='web_search_history')
        op.drop_index('ix_web_search_history_extraction_status', table_name='web_search_history')
        op.drop_index('ix_web_search_history_discipline', table_name='web_search_history')
        op.drop_index('ix_web_search_history_user_id', table_name='web_search_history')
        op.drop_index('ix_web_search_history_project_id', table_name='web_search_history')
        op.drop_index('ix_web_search_history_organization_id', table_name='web_search_history')
        op.drop_table('web_search_history')
