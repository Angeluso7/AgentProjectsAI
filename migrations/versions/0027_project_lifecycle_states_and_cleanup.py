"""project_lifecycle_states_and_cleanup

Revision ID: 0027_project_lifecycle_states_and_cleanup
Revises: 0026_project_normalized_code_and_documents_sync
Create Date: 2026-09-22 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0027_project_lifecycle_states_and_cleanup'
down_revision: Union[str, None] = '0026_project_normalized_code_and_documents_sync'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'projects' in existing_tables:
        proj_cols = [col['name'] for col in inspector.get_columns('projects')]

        if 'cleanup_status' not in proj_cols:
            op.add_column('projects', sa.Column('cleanup_status', sa.String(30), nullable=True, server_default='none'))
        if 'cleanup_error' not in proj_cols:
            op.add_column('projects', sa.Column('cleanup_error', sa.Text(), nullable=True))
        if 'deletion_job_id' not in proj_cols:
            op.add_column('projects', sa.Column('deletion_job_id', sa.String(36), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'projects' in existing_tables:
        proj_cols = [col['name'] for col in inspector.get_columns('projects')]
        if 'deletion_job_id' in proj_cols:
            op.drop_column('projects', 'deletion_job_id')
        if 'cleanup_error' in proj_cols:
            op.drop_column('projects', 'cleanup_error')
        if 'cleanup_status' in proj_cols:
            op.drop_column('projects', 'cleanup_status')
