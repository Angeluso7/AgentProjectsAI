"""add source_assets table for intake and governance

Revision ID: 0004_source_assets_intake
Revises: 0003_layout_and_title_block_extractions
Create Date: 2026-08-21 00:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004_source_assets_intake'
down_revision: Union[str, None] = '0003_layout_and_title_block_extractions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'source_assets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('source_type', sa.String(50), nullable=False, index=True),
        sa.Column('source_origin', sa.String(50), server_default='local_upload', nullable=False),
        sa.Column('document_type', sa.String(50), nullable=True),
        sa.Column('discipline', sa.String(50), server_default='general', nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('sha256', sa.String(64), nullable=True, index=True),
        sa.Column('mime_type', sa.String(100), server_default='application/pdf', nullable=False),
        sa.Column('version', sa.String(50), server_default='1.0', nullable=False),
        sa.Column('status', sa.String(30), server_default='registered', nullable=False),
        sa.Column('approval_status', sa.String(30), server_default='pending_review', nullable=False, index=True),
        sa.Column('linked_memory_target', sa.String(50), nullable=False, index=True),
        sa.Column('owner', sa.String(100), server_default='system', nullable=False),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.String(100), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('metadata_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

def downgrade() -> None:
    op.drop_table('source_assets')
