"""piping_symbol_recognition_dual_pipeline

Revision ID: 0019_piping_symbol_dual
Revises: 0018_visual_split_crop_lineage
Create Date: 2026-09-04 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0019_piping_symbol_dual'
down_revision: Union[str, None] = '0018_visual_split_crop_lineage'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'structured_symbols' in existing_tables:
        columns = [c['name'] for c in inspector.get_columns('structured_symbols')]

        # 1. source_render_mode
        if 'source_render_mode' not in columns:
            op.add_column(
                'structured_symbols',
                sa.Column('source_render_mode', sa.String(length=20), server_default='raster', nullable=False)
            )
            op.create_index(
                'ix_structured_symbols_source_render_mode',
                'structured_symbols',
                ['source_render_mode'],
                unique=False
            )

        # 2. layout_context
        if 'layout_context' not in columns:
            op.add_column(
                'structured_symbols',
                sa.Column('layout_context', sa.String(length=30), server_default='inside_table', nullable=False)
            )
            op.create_index(
                'ix_structured_symbols_layout_context',
                'structured_symbols',
                ['layout_context'],
                unique=False
            )

        # 3. context_association_mode
        if 'context_association_mode' not in columns:
            op.add_column(
                'structured_symbols',
                sa.Column('context_association_mode', sa.String(length=30), server_default='row_band', nullable=False)
            )
            op.create_index(
                'ix_structured_symbols_context_association_mode',
                'structured_symbols',
                ['context_association_mode'],
                unique=False
            )

        # 4. standard_reference
        if 'standard_reference' not in columns:
            op.add_column(
                'structured_symbols',
                sa.Column('standard_reference', sa.String(length=150), nullable=True)
            )

        # 5. canonical_symbol_family
        if 'canonical_symbol_family' not in columns:
            op.add_column(
                'structured_symbols',
                sa.Column('canonical_symbol_family', sa.String(length=50), server_default='valves', nullable=False)
            )
            op.create_index(
                'ix_structured_symbols_canonical_symbol_family',
                'structured_symbols',
                ['canonical_symbol_family'],
                unique=False
            )

        # 6. visual_variant_group_id
        if 'visual_variant_group_id' not in columns:
            op.add_column(
                'structured_symbols',
                sa.Column('visual_variant_group_id', sa.String(length=36), nullable=True)
            )
            op.create_index(
                'ix_structured_symbols_visual_variant_group_id',
                'structured_symbols',
                ['visual_variant_group_id'],
                unique=False
            )

        # 7. estimated_physical_size_mm
        if 'estimated_physical_size_mm' not in columns:
            op.add_column(
                'structured_symbols',
                sa.Column('estimated_physical_size_mm', sa.JSON(), server_default='{}', nullable=False)
            )

        # 8. reused_for_matching_count
        if 'reused_for_matching_count' not in columns:
            op.add_column(
                'structured_symbols',
                sa.Column('reused_for_matching_count', sa.Integer(), server_default='0', nullable=False)
            )

        # 9. false_positive_count
        if 'false_positive_count' not in columns:
            op.add_column(
                'structured_symbols',
                sa.Column('false_positive_count', sa.Integer(), server_default='0', nullable=False)
            )

        # 10. human_validation_notes
        if 'human_validation_notes' not in columns:
            op.add_column(
                'structured_symbols',
                sa.Column('human_validation_notes', sa.Text(), nullable=True)
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'structured_symbols' in existing_tables:
        columns = [c['name'] for c in inspector.get_columns('structured_symbols')]

        cols_to_drop = [
            ('human_validation_notes', None),
            ('false_positive_count', None),
            ('reused_for_matching_count', None),
            ('estimated_physical_size_mm', None),
            ('visual_variant_group_id', 'ix_structured_symbols_visual_variant_group_id'),
            ('canonical_symbol_family', 'ix_structured_symbols_canonical_symbol_family'),
            ('standard_reference', None),
            ('context_association_mode', 'ix_structured_symbols_context_association_mode'),
            ('layout_context', 'ix_structured_symbols_layout_context'),
            ('source_render_mode', 'ix_structured_symbols_source_render_mode')
        ]

        for col_name, idx_name in cols_to_drop:
            if col_name in columns:
                if idx_name:
                    try:
                        op.drop_index(idx_name, table_name='structured_symbols')
                    except Exception:
                        pass
                op.drop_column('structured_symbols', col_name)
