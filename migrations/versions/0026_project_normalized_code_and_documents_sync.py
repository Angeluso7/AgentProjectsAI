"""project_normalized_code_and_documents_sync

Revision ID: 0026_project_normalized_code_and_documents_sync
Revises: 0025_symbol_source_evidence_metadata
Create Date: 2026-09-22 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0026_project_normalized_code_and_documents_sync'
down_revision: Union[str, None] = '0025_symbol_source_evidence_metadata'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Sincronizar columnas faltantes en la tabla documents
    if 'documents' in existing_tables:
        doc_cols = [col['name'] for col in inspector.get_columns('documents')]

        if 'error_message' not in doc_cols:
            op.add_column('documents', sa.Column('error_message', sa.Text(), nullable=True))
        if 'metadata_info' not in doc_cols:
            op.add_column('documents', sa.Column('metadata_info', sa.JSON(), nullable=True, server_default='{}'))
        if 'processed_at' not in doc_cols:
            op.add_column('documents', sa.Column('processed_at', sa.DateTime(), nullable=True))
        if 'updated_at' not in doc_cols:
            op.add_column('documents', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))

    # 2. Agregar normalized_code a la tabla projects
    if 'projects' in existing_tables:
        proj_cols = [col['name'] for col in inspector.get_columns('projects')]

        if 'status' not in proj_cols:
            op.add_column('projects', sa.Column('status', sa.String(30), nullable=False, server_default='active'))

        if 'normalized_code' not in proj_cols:
            op.add_column('projects', sa.Column('normalized_code', sa.String(50), nullable=True))
            # Backfill existente con trim y uppercase
            op.execute("UPDATE projects SET normalized_code = UPPER(TRIM(code)) WHERE normalized_code IS NULL")
            # Hacer no nullable tras el backfill
            op.alter_column('projects', 'normalized_code', nullable=False)

        # Crear índice único parcial condicional:
        # Excluye registros soft-deleted (status == 'deleted') para permitir reutilización,
        # pero reserva el código para proyectos activos y archivados.
        proj_indexes = [idx['name'] for idx in inspector.get_indexes('projects')]
        if 'uq_projects_org_normalized_code' not in proj_indexes:
            op.create_index(
                'uq_projects_org_normalized_code',
                'projects',
                ['organization_id', 'normalized_code'],
                unique=True,
                postgresql_where=sa.text("status != 'deleted'")
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'projects' in existing_tables:
        proj_indexes = [idx['name'] for idx in inspector.get_indexes('projects')]
        if 'uq_projects_org_normalized_code' in proj_indexes:
            op.drop_index('uq_projects_org_normalized_code', table_name='projects')

        proj_cols = [col['name'] for col in inspector.get_columns('projects')]
        if 'normalized_code' in proj_cols:
            op.drop_column('projects', 'normalized_code')

    if 'documents' in existing_tables:
        doc_cols = [col['name'] for col in inspector.get_columns('documents')]
        if 'processed_at' in doc_cols:
            op.drop_column('documents', 'processed_at')
        if 'metadata_info' in doc_cols:
            op.drop_column('documents', 'metadata_info')
        if 'error_message' in doc_cols:
            op.drop_column('documents', 'error_message')
