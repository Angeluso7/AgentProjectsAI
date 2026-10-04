"""organizations_users_rbac_and_multitenancy

Revision ID: 0011_organizations_users_rbac_and_multitenancy
Revises: 0010_review_pipeline_runs_and_stages
Create Date: 2026-08-21 01:10:00.000000

"""
import uuid
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0011_organizations_users_rbac_and_multitenancy'
down_revision: Union[str, None] = '0010_review_pipeline_runs_and_stages'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_ORG_ID = "default-org-uuid"

def upgrade() -> None:
    # 1. Crear tabla organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('status', sa.String(30), server_default='active', nullable=False, index=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    # 2. Crear tabla organization_memberships
    op.create_table(
        'organization_memberships',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', sa.String(30), server_default='reviewer', nullable=False, index=True),
        sa.Column('status', sa.String(30), server_default='active', nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    # 3. Modificar users
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('display_name', sa.String(150), server_default='Usuario', nullable=False))
        batch_op.add_column(sa.Column('password_hash', sa.String(255), server_default='', nullable=False))
        batch_op.add_column(sa.Column('is_superuser', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # 4. Modificar projects
    with op.batch_alter_table('projects') as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True))
        batch_op.add_column(sa.Column('discipline_scope', sa.JSON(), nullable=True))

    # 5. Agregar organization_id a tablas tenant-scoped de Fase 2
    for table_name in [
        'source_assets',
        'documents',
        'processing_jobs',
        'review_pipeline_runs',
        'review_tasks',
        'decision_traces',
        'review_runs',
        'rule_findings',
        'audit_reports',
        'evidence_manifests',
        'audit_logs'
    ]:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True))

    # 6. Backfill de datos preexistentes a default-org
    op.execute(f"""
        INSERT INTO organizations (id, name, slug, status, settings, created_at, updated_at)
        VALUES ('{DEFAULT_ORG_ID}', 'Organización Principal', 'default-org', 'active', '{{}}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """)

    for table_name in [
        'projects',
        'source_assets',
        'documents',
        'processing_jobs',
        'review_pipeline_runs',
        'review_tasks',
        'decision_traces',
        'review_runs',
        'rule_findings',
        'audit_reports',
        'evidence_manifests',
        'audit_logs'
    ]:
        op.execute(f"UPDATE {table_name} SET organization_id = '{DEFAULT_ORG_ID}' WHERE organization_id IS NULL")

def downgrade() -> None:
    for table_name in [
        'audit_logs',
        'evidence_manifests',
        'audit_reports',
        'rule_findings',
        'review_runs',
        'decision_traces',
        'review_tasks',
        'review_pipeline_runs',
        'processing_jobs',
        'documents',
        'source_assets',
        'projects'
    ]:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column('organization_id')

    with op.batch_alter_table('projects') as batch_op:
        batch_op.drop_column('discipline_scope')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('is_superuser')
        batch_op.drop_column('password_hash')
        batch_op.drop_column('display_name')

    op.drop_table('organization_memberships')
    op.drop_table('organizations')
