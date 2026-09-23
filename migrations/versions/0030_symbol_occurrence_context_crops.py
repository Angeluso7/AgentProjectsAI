"""symbol_occurrence_context_crops_and_inventory_groups

Revision ID: 0030_symbol_inventory_groups
Revises: 0029_review_taxonomy_and_orchestration
Create Date: 2026-09-23 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0030_symbol_inventory_groups'
down_revision: Union[str, None] = '0029_review_taxonomy_and_orchestration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Crear tabla symbol_inventory_groups si no existe
    if 'symbol_inventory_groups' not in existing_tables:
        op.create_table(
            'symbol_inventory_groups',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('review_run_id', sa.String(36), sa.ForeignKey('review_runs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('grouping_key', sa.String(150), nullable=False),
            sa.Column('grouping_method', sa.String(50), nullable=False, server_default='template_match'),
            sa.Column('grouping_confidence', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('grouping_version', sa.String(30), nullable=False, server_default='v1.0'),
            sa.Column('display_code', sa.String(50), nullable=False),
            sa.Column('unknown_group_id', sa.String(36), nullable=True),
            sa.Column('representative_occurrence_id', sa.String(36), nullable=True),
            sa.Column('representative_selection_reason', sa.String(255), nullable=True),
            sa.Column('matched_template_id', sa.String(36), sa.ForeignKey('symbol_templates.id', ondelete='SET NULL'), nullable=True),
            sa.Column('matched_template_version_id', sa.String(36), sa.ForeignKey('symbol_template_versions.id', ondelete='SET NULL'), nullable=True),
            sa.Column('canonical_name', sa.String(150), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('technical_function', sa.Text(), nullable=True),
            sa.Column('standard_reference', sa.String(150), nullable=True),
            sa.Column('catalog_status', sa.String(40), nullable=False, server_default='unknown_symbol'),
            sa.Column('confidence_summary', sa.JSON(), nullable=True),
            sa.Column('total_occurrences', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('occurrences_by_document', sa.JSON(), nullable=True),
            sa.Column('occurrences_by_sheet', sa.JSON(), nullable=True),
            sa.Column('requires_human_review', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('explanation', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('review_run_id', 'grouping_key', name='uq_run_grouping_key')
        )
        op.create_index('ix_symbol_inventory_groups_run_id', 'symbol_inventory_groups', ['review_run_id'])
        op.create_index('ix_symbol_inventory_groups_status', 'symbol_inventory_groups', ['catalog_status'])
        op.create_index('ix_symbol_inventory_groups_display_code', 'symbol_inventory_groups', ['display_code'])
        op.create_index('ix_symbol_inventory_groups_tmpl_id', 'symbol_inventory_groups', ['matched_template_id'])
        op.create_index('ix_symbol_inventory_groups_tmpl_ver_id', 'symbol_inventory_groups', ['matched_template_version_id'])

    # 2. Extender detected_symbols con campos de context crop e inventario
    if 'detected_symbols' in existing_tables:
        det_cols = {col['name'] for col in inspector.get_columns('detected_symbols')}
        if 'inventory_group_id' not in det_cols:
            op.add_column('detected_symbols', sa.Column('inventory_group_id', sa.String(36), sa.ForeignKey('symbol_inventory_groups.id', ondelete='SET NULL'), nullable=True))
            op.create_index('ix_detected_symbols_inv_group_id', 'detected_symbols', ['inventory_group_id'])
        if 'occurrence_context_crop_bbox' not in det_cols:
            op.add_column('detected_symbols', sa.Column('occurrence_context_crop_bbox', sa.JSON(), nullable=True))
        if 'occurrence_context_crop_path' not in det_cols:
            op.add_column('detected_symbols', sa.Column('occurrence_context_crop_path', sa.String(500), nullable=True))
        if 'occurrence_context_crop_hash' not in det_cols:
            op.add_column('detected_symbols', sa.Column('occurrence_context_crop_hash', sa.String(64), nullable=True))
        if 'context_margin_mm' not in det_cols:
            op.add_column('detected_symbols', sa.Column('context_margin_mm', sa.Float(), nullable=False, server_default='15.0'))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'detected_symbols' in existing_tables:
        det_cols = {col['name'] for col in inspector.get_columns('detected_symbols')}
        if 'context_margin_mm' in det_cols:
            op.drop_column('detected_symbols', 'context_margin_mm')
        if 'occurrence_context_crop_hash' in det_cols:
            op.drop_column('detected_symbols', 'occurrence_context_crop_hash')
        if 'occurrence_context_crop_path' in det_cols:
            op.drop_column('detected_symbols', 'occurrence_context_crop_path')
        if 'occurrence_context_crop_bbox' in det_cols:
            op.drop_column('detected_symbols', 'occurrence_context_crop_bbox')
        if 'inventory_group_id' in det_cols:
            op.drop_index('ix_detected_symbols_inv_group_id', table_name='detected_symbols')
            op.drop_column('detected_symbols', 'inventory_group_id')

    if 'symbol_inventory_groups' in existing_tables:
        op.drop_table('symbol_inventory_groups')
