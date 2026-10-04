"""document_hash_per_project

Revision ID: 0028_document_hash_per_project
Revises: 0027_project_lifecycle_states_and_cleanup
Create Date: 2026-09-23 00:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0028_document_hash_per_project'
down_revision: Union[str, None] = '0027_project_lifecycle_states_and_cleanup'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'documents' in existing_tables:
        indexes = inspector.get_indexes('documents')
        index_names = {idx['name'] for idx in indexes}

        # 1. Eliminar índice único global si existe
        if 'ix_documents_file_hash_sha256' in index_names:
            op.drop_index('ix_documents_file_hash_sha256', table_name='documents')

        # 2. Recrear índice técnico no único sobre file_hash_sha256
        op.create_index('ix_documents_file_hash_sha256', 'documents', ['file_hash_sha256'], unique=False)

        # 3. Crear índice único compuesto por (project_id, file_hash_sha256)
        if 'uq_documents_project_file_hash' not in index_names:
            op.create_index('uq_documents_project_file_hash', 'documents', ['project_id', 'file_hash_sha256'], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'documents' in existing_tables:
        indexes = inspector.get_indexes('documents')
        index_names = {idx['name'] for idx in indexes}

        if 'uq_documents_project_file_hash' in index_names:
            op.drop_index('uq_documents_project_file_hash', table_name='documents')

        if 'ix_documents_file_hash_sha256' in index_names:
            op.drop_index('ix_documents_file_hash_sha256', table_name='documents')

        # Restaurar índice único global original
        op.create_index('ix_documents_file_hash_sha256', 'documents', ['file_hash_sha256'], unique=True)
