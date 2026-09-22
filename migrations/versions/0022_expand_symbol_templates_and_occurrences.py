"""expand_symbol_templates_and_occurrences

Revision ID: 0022_expand_symbol_templates
Revises: 0021_translations_table
Create Date: 2026-09-16 08:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0022_expand_symbol_templates'
down_revision: Union[str, None] = '0021_translations_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # 1. Expand symbol_templates table
    tmpl_columns = [col['name'] for col in inspector.get_columns('symbol_templates')]
    
    if 'normalized_mask_path' not in tmpl_columns:
        op.add_column('symbol_templates', sa.Column('normalized_mask_path', sa.String(500), nullable=True))
    if 'mask_hash' not in tmpl_columns:
        op.add_column('symbol_templates', sa.Column('mask_hash', sa.String(64), nullable=True))
    if 'hu_moments' not in tmpl_columns:
        op.add_column('symbol_templates', sa.Column('hu_moments', sa.JSON(), nullable=True))
    if 'contour_signature' not in tmpl_columns:
        op.add_column('symbol_templates', sa.Column('contour_signature', sa.JSON(), nullable=True))
    if 'canonical_width_mm' not in tmpl_columns:
        op.add_column('symbol_templates', sa.Column('canonical_width_mm', sa.Float(), nullable=True))
    if 'canonical_height_mm' not in tmpl_columns:
        op.add_column('symbol_templates', sa.Column('canonical_height_mm', sa.Float(), nullable=True))
    if 'aspect_ratio' not in tmpl_columns:
        op.add_column('symbol_templates', sa.Column('aspect_ratio', sa.Float(), nullable=True))
    if 'primitive_signature' not in tmpl_columns:
        op.add_column('symbol_templates', sa.Column('primitive_signature', sa.JSON(), nullable=True))
    if 'rotation_invariance_mode' not in tmpl_columns:
        op.add_column('symbol_templates', sa.Column('rotation_invariance_mode', sa.String(30), nullable=True, server_default='orthogonal_4_rotations'))
    if 'is_active_for_detection' not in tmpl_columns:
        op.add_column('symbol_templates', sa.Column('is_active_for_detection', sa.Boolean(), nullable=False, server_default='true'))
    if 'organization_id' not in tmpl_columns:
        op.add_column('symbol_templates', sa.Column('organization_id', sa.String(36), nullable=True))
    
    # Make library_id nullable in symbol_templates if not already
    op.alter_column('symbol_templates', 'library_id', existing_type=sa.String(36), nullable=True)
    
    # Indices on symbol_templates
    tmpl_indexes = [idx['name'] for idx in inspector.get_indexes('symbol_templates')]
    if 'ix_symbol_templates_is_active' not in tmpl_indexes:
        op.create_index('ix_symbol_templates_is_active', 'symbol_templates', ['is_active_for_detection'])
    if 'ix_symbol_templates_org_id' not in tmpl_indexes:
        op.create_index('ix_symbol_templates_org_id', 'symbol_templates', ['organization_id'])

    # 2. Expand detected_symbols table
    det_columns = [col['name'] for col in inspector.get_columns('detected_symbols')]
    
    if 'match_score_visual' not in det_columns:
        op.add_column('detected_symbols', sa.Column('match_score_visual', sa.Float(), nullable=True))
    if 'match_rotation_deg' not in det_columns:
        op.add_column('detected_symbols', sa.Column('match_rotation_deg', sa.Integer(), nullable=True))
    if 'match_method' not in det_columns:
        op.add_column('detected_symbols', sa.Column('match_method', sa.String(50), nullable=True))
    if 'match_evidence' not in det_columns:
        op.add_column('detected_symbols', sa.Column('match_evidence', sa.JSON(), nullable=True))
    if 'algorithm_version' not in det_columns:
        op.add_column('detected_symbols', sa.Column('algorithm_version', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_index('ix_symbol_templates_org_id', table_name='symbol_templates')
    op.drop_index('ix_symbol_templates_is_active', table_name='symbol_templates')
    
    op.drop_column('detected_symbols', 'algorithm_version')
    op.drop_column('detected_symbols', 'match_evidence')
    op.drop_column('detected_symbols', 'match_method')
    op.drop_column('detected_symbols', 'match_rotation_deg')
    op.drop_column('detected_symbols', 'match_score_visual')
    
    op.drop_column('symbol_templates', 'organization_id')
    op.drop_column('symbol_templates', 'is_active_for_detection')
    op.drop_column('symbol_templates', 'rotation_invariance_mode')
    op.drop_column('symbol_templates', 'primitive_signature')
    op.drop_column('symbol_templates', 'aspect_ratio')
    op.drop_column('symbol_templates', 'canonical_height_mm')
    op.drop_column('symbol_templates', 'canonical_width_mm')
    op.drop_column('symbol_templates', 'contour_signature')
    op.drop_column('symbol_templates', 'hu_moments')
    op.drop_column('symbol_templates', 'mask_hash')
    op.drop_column('symbol_templates', 'normalized_mask_path')
