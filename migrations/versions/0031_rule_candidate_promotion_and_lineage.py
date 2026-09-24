"""rule_candidate_promotion_and_lineage

Revision ID: 0031_rule_candidate_promotion
Revises: 0030_symbol_inventory_groups
Create Date: 2026-09-23 21:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0031_rule_candidate_promotion'
down_revision: Union[str, None] = '0030_symbol_inventory_groups'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Extender rule_definitions con linaje fuente explícito
    if 'rule_definitions' in existing_tables:
        rd_cols = {col['name'] for col in inspector.get_columns('rule_definitions')}
        if 'source_candidate_id' not in rd_cols:
            op.add_column('rule_definitions', sa.Column('source_candidate_id', sa.String(36), nullable=True))
            op.create_index('ix_rule_definitions_source_cand_id', 'rule_definitions', ['source_candidate_id'])
        if 'source_document_id' not in rd_cols:
            op.add_column('rule_definitions', sa.Column('source_document_id', sa.String(36), nullable=True))
            op.create_index('ix_rule_definitions_source_doc_id', 'rule_definitions', ['source_document_id'])
        if 'source_page' not in rd_cols:
            op.add_column('rule_definitions', sa.Column('source_page', sa.Integer(), nullable=True))
        if 'source_bbox' not in rd_cols:
            op.add_column('rule_definitions', sa.Column('source_bbox', sa.JSON(), nullable=True))
        if 'source_excerpt' not in rd_cols:
            op.add_column('rule_definitions', sa.Column('source_excerpt', sa.Text(), nullable=True))
        if 'source_hash' not in rd_cols:
            op.add_column('rule_definitions', sa.Column('source_hash', sa.String(64), nullable=True))

    # 2. Extender rule_document_items con estado de promoción y tracking
    if 'rule_document_items' in existing_tables:
        rdi_cols = {col['name'] for col in inspector.get_columns('rule_document_items')}
        if 'promoted_rule_definition_id' not in rdi_cols:
            op.add_column('rule_document_items', sa.Column('promoted_rule_definition_id', sa.String(36), sa.ForeignKey('rule_definitions.id', ondelete='SET NULL'), nullable=True))
            op.create_index('ix_rule_doc_items_promoted_rd_id', 'rule_document_items', ['promoted_rule_definition_id'])
        if 'promoted_at' not in rdi_cols:
            op.add_column('rule_document_items', sa.Column('promoted_at', sa.DateTime(), nullable=True))
        if 'promoted_by' not in rdi_cols:
            op.add_column('rule_document_items', sa.Column('promoted_by', sa.String(100), nullable=True))
        if 'promotion_status' not in rdi_cols:
            op.add_column('rule_document_items', sa.Column('promotion_status', sa.String(30), nullable=False, server_default='pending'))
            op.create_index('ix_rule_doc_items_promotion_status', 'rule_document_items', ['promotion_status'])
        if 'promotion_error' not in rdi_cols:
            op.add_column('rule_document_items', sa.Column('promotion_error', sa.Text(), nullable=True))

    # 3. Crear tabla rule_review_decisions para auditoría inmutable HITL
    if 'rule_review_decisions' not in existing_tables:
        op.create_table(
            'rule_review_decisions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('candidate_id', sa.String(36), nullable=False),
            sa.Column('rule_definition_id', sa.String(36), sa.ForeignKey('rule_definitions.id', ondelete='SET NULL'), nullable=True),
            sa.Column('decision', sa.String(30), nullable=False),
            sa.Column('reviewer_id', sa.String(100), nullable=False),
            sa.Column('reviewer_role', sa.String(50), nullable=False, server_default='auditor'),
            sa.Column('reviewer_rationale', sa.Text(), nullable=True),
            sa.Column('rule_code', sa.String(100), nullable=True),
            sa.Column('payload_snapshot', sa.JSON(), nullable=True),
            sa.Column('previous_state', sa.JSON(), nullable=True),
            sa.Column('new_state', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        op.create_index('ix_rule_rev_dec_candidate_id', 'rule_review_decisions', ['candidate_id'])
        op.create_index('ix_rule_rev_dec_rule_def_id', 'rule_review_decisions', ['rule_definition_id'])
        op.create_index('ix_rule_rev_dec_rule_code', 'rule_review_decisions', ['rule_code'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Dropear tabla rule_review_decisions
    if 'rule_review_decisions' in existing_tables:
        op.drop_table('rule_review_decisions')

    # 2. Dropear columnas de rule_document_items
    if 'rule_document_items' in existing_tables:
        rdi_cols = {col['name'] for col in inspector.get_columns('rule_document_items')}
        if 'promotion_error' in rdi_cols:
            op.drop_column('rule_document_items', 'promotion_error')
        if 'promotion_status' in rdi_cols:
            op.drop_index('ix_rule_doc_items_promotion_status', table_name='rule_document_items')
            op.drop_column('rule_document_items', 'promotion_status')
        if 'promoted_by' in rdi_cols:
            op.drop_column('rule_document_items', 'promoted_by')
        if 'promoted_at' in rdi_cols:
            op.drop_column('rule_document_items', 'promoted_at')
        if 'promoted_rule_definition_id' in rdi_cols:
            op.drop_index('ix_rule_doc_items_promoted_rd_id', table_name='rule_document_items')
            op.drop_column('rule_document_items', 'promoted_rule_definition_id')

    # 3. Dropear columnas de rule_definitions
    if 'rule_definitions' in existing_tables:
        rd_cols = {col['name'] for col in inspector.get_columns('rule_definitions')}
        if 'source_hash' in rd_cols:
            op.drop_column('rule_definitions', 'source_hash')
        if 'source_excerpt' in rd_cols:
            op.drop_column('rule_definitions', 'source_excerpt')
        if 'source_bbox' in rd_cols:
            op.drop_column('rule_definitions', 'source_bbox')
        if 'source_page' in rd_cols:
            op.drop_column('rule_definitions', 'source_page')
        if 'source_document_id' in rd_cols:
            op.drop_index('ix_rule_definitions_source_doc_id', table_name='rule_definitions')
            op.drop_column('rule_definitions', 'source_document_id')
        if 'source_candidate_id' in rd_cols:
            op.drop_index('ix_rule_definitions_source_cand_id', table_name='rule_definitions')
            op.drop_column('rule_definitions', 'source_candidate_id')
