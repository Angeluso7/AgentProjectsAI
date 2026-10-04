"""add_visual_split_crop_and_lineage_fields_to_extracted_items

Revision ID: 0018_visual_split_crop_lineage
Revises: 0017_web_search_history_audit
Create Date: 2026-08-25 13:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0018_visual_split_crop_lineage'
down_revision: Union[str, None] = '0017_web_search_history_audit'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('extracted_items')]

    # 1. parent_item_id
    if 'parent_item_id' not in columns:
        op.add_column(
            'extracted_items',
            sa.Column('parent_item_id', sa.String(length=36), nullable=True)
        )
        op.create_index(
            'ix_extracted_items_parent_item_id',
            'extracted_items',
            ['parent_item_id'],
            unique=False
        )

    # 2. is_derived
    if 'is_derived' not in columns:
        op.add_column(
            'extracted_items',
            sa.Column('is_derived', sa.Boolean(), server_default='false', nullable=False)
        )
        op.create_index(
            'ix_extracted_items_is_derived',
            'extracted_items',
            ['is_derived'],
            unique=False
        )

    # 3. split_mode
    if 'split_mode' not in columns:
        op.add_column(
            'extracted_items',
            sa.Column('split_mode', sa.String(length=50), nullable=True)
        )
        op.create_index(
            'ix_extracted_items_split_mode',
            'extracted_items',
            ['split_mode'],
            unique=False
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('extracted_items')]

    if 'split_mode' in columns:
        op.drop_index('ix_extracted_items_split_mode', table_name='extracted_items')
        op.drop_column('extracted_items', 'split_mode')

    if 'is_derived' in columns:
        op.drop_index('ix_extracted_items_is_derived', table_name='extracted_items')
        op.drop_column('extracted_items', 'is_derived')

    if 'parent_item_id' in columns:
        op.drop_index('ix_extracted_items_parent_item_id', table_name='extracted_items')
        op.drop_column('extracted_items', 'parent_item_id')
