"""add_discipline_code_to_document_deliverables

Revision ID: 0035_add_discipline_code_to_document_deliverables
Revises: 0034_deactivate_legacy_architecture_rules
Create Date: 2026-10-09 20:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0035_add_discipline_code_to_document_deliverables'
down_revision: Union[str, None] = '0034_deactivate_legacy_architecture_rules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('document_deliverables')]
    if 'discipline_code' not in cols:
        op.add_column('document_deliverables', sa.Column('discipline_code', sa.String(length=50), nullable=True))
        op.create_index(op.f('ix_document_deliverables_discipline_code'), 'document_deliverables', ['discipline_code'], unique=False)


def downgrade() -> None:
    op.drop_index(
        op.f('ix_document_deliverables_discipline_code'),
        table_name='document_deliverables'
    )
    op.drop_column('document_deliverables', 'discipline_code')
