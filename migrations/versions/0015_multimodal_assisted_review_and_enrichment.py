"""multimodal_assisted_review_and_enrichment

Revision ID: 0015_multimodal_assisted_review_and_enrichment
Revises: 0014_rule_candidate_deduplication_and_motor_qaqc
Create Date: 2026-08-24 10:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0015_multimodal_assisted_review_and_enrichment'
down_revision: Union[str, None] = '0014_rule_candidate_deduplication_and_motor_qaqc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. completeness_status
    op.add_column(
        'extracted_items',
        sa.Column('completeness_status', sa.String(length=50), server_default='missing_data', nullable=False)
    )
    op.create_index(
        'ix_extracted_items_completeness_status',
        'extracted_items',
        ['completeness_status'],
        unique=False
    )

    # 2. enrichment_status
    op.add_column(
        'extracted_items',
        sa.Column('enrichment_status', sa.String(length=50), server_default='not_enriched', nullable=False)
    )
    op.create_index(
        'ix_extracted_items_enrichment_status',
        'extracted_items',
        ['enrichment_status'],
        unique=False
    )

    # 3. requires_validation
    op.add_column(
        'extracted_items',
        sa.Column('requires_validation', sa.Boolean(), server_default='true', nullable=False)
    )
    op.create_index(
        'ix_extracted_items_requires_validation',
        'extracted_items',
        ['requires_validation'],
        unique=False
    )

    # 4. enriched_from_web
    op.add_column(
        'extracted_items',
        sa.Column('enriched_from_web', sa.Boolean(), server_default='false', nullable=False)
    )

    # 5. enrichment_method
    op.add_column(
        'extracted_items',
        sa.Column('enrichment_method', sa.String(length=100), nullable=True)
    )

    # 6. match_confidence
    op.add_column(
        'extracted_items',
        sa.Column('match_confidence', sa.Float(), server_default='0.0', nullable=True)
    )

    # 7. suggested_title
    op.add_column(
        'extracted_items',
        sa.Column('suggested_title', sa.String(length=255), nullable=True)
    )

    # 8. suggested_description
    op.add_column(
        'extracted_items',
        sa.Column('suggested_description', sa.Text(), nullable=True)
    )

    # 9. suggested_function
    op.add_column(
        'extracted_items',
        sa.Column('suggested_function', sa.Text(), nullable=True)
    )

    # 10. suggested_source_url
    op.add_column(
        'extracted_items',
        sa.Column('suggested_source_url', sa.String(length=500), nullable=True)
    )

    # 11. suggested_source_label
    op.add_column(
        'extracted_items',
        sa.Column('suggested_source_label', sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('extracted_items', 'suggested_source_label')
    op.drop_column('extracted_items', 'suggested_source_url')
    op.drop_column('extracted_items', 'suggested_function')
    op.drop_column('extracted_items', 'suggested_description')
    op.drop_column('extracted_items', 'suggested_title')
    op.drop_column('extracted_items', 'match_confidence')
    op.drop_column('extracted_items', 'enrichment_method')
    op.drop_column('extracted_items', 'enriched_from_web')
    op.drop_index('ix_extracted_items_requires_validation', table_name='extracted_items')
    op.drop_column('extracted_items', 'requires_validation')
    op.drop_index('ix_extracted_items_enrichment_status', table_name='extracted_items')
    op.drop_column('extracted_items', 'enrichment_status')
    op.drop_index('ix_extracted_items_completeness_status', table_name='extracted_items')
    op.drop_column('extracted_items', 'completeness_status')
