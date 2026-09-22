"""rule_candidate_deduplication_and_motor_qaqc

Revision ID: 0014_rule_candidate_deduplication_and_motor_qaqc
Revises: 0013_multimodal_candidates_and_structural_chunks
Create Date: 2026-08-24 03:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0014_rule_candidate_deduplication_and_motor_qaqc'
down_revision: Union[str, None] = '0013_multimodal_candidates_and_structural_chunks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # Campos de Deduplicación y Bloqueo contra Motor de Reglas QA/QC
    # =========================================================================
    
    # 1. duplicate_status (no_match, exact_match_existing_rule, likely_duplicate_existing_rule, related_existing_rule)
    op.add_column(
        'extracted_items',
        sa.Column('duplicate_status', sa.String(length=50), server_default='no_match', nullable=False)
    )
    op.create_index(
        'ix_extracted_items_duplicate_status',
        'extracted_items',
        ['duplicate_status'],
        unique=False
    )

    # 2. best_match_rule_id
    op.add_column(
        'extracted_items',
        sa.Column('best_match_rule_id', sa.String(length=36), nullable=True)
    )

    # 3. best_match_rule_code
    op.add_column(
        'extracted_items',
        sa.Column('best_match_rule_code', sa.String(length=100), nullable=True)
    )

    # 4. best_match_title
    op.add_column(
        'extracted_items',
        sa.Column('best_match_title', sa.String(length=255), nullable=True)
    )

    # 5. best_match_discipline
    op.add_column(
        'extracted_items',
        sa.Column('best_match_discipline', sa.String(length=50), nullable=True)
    )

    # 6. duplicate_reason
    op.add_column(
        'extracted_items',
        sa.Column('duplicate_reason', sa.Text(), nullable=True)
    )

    # 7. duplicate_confidence
    op.add_column(
        'extracted_items',
        sa.Column('duplicate_confidence', sa.Float(), server_default='0.0', nullable=True)
    )

    # 8. blocked_from_acceptance
    op.add_column(
        'extracted_items',
        sa.Column('blocked_from_acceptance', sa.Boolean(), server_default='false', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('extracted_items', 'blocked_from_acceptance')
    op.drop_column('extracted_items', 'duplicate_confidence')
    op.drop_column('extracted_items', 'duplicate_reason')
    op.drop_column('extracted_items', 'best_match_discipline')
    op.drop_column('extracted_items', 'best_match_title')
    op.drop_column('extracted_items', 'best_match_rule_code')
    op.drop_column('extracted_items', 'best_match_rule_id')
    op.drop_index('ix_extracted_items_duplicate_status', table_name='extracted_items')
    op.drop_column('extracted_items', 'duplicate_status')
