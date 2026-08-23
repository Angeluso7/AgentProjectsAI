"""add bbox_normalized to extracted_texts

Revision ID: 0002_add_bbox_normalized
Revises: 0001_initial_schema
Create Date: 2026-08-20 23:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002_add_bbox_normalized'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        'extracted_texts',
        sa.Column('bbox_normalized', sa.JSON(), nullable=True)
    )

def downgrade() -> None:
    op.drop_column('extracted_texts', 'bbox_normalized')
