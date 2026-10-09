"""add_project_id_to_decision_traces

Revision ID: 0033_add_project_id_to_decision_traces
Revises: 0032_consolidate_schema_gaps
Create Date: 2026-10-09 00:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0033_add_project_id_to_decision_traces'
down_revision: Union[str, None] = '0032_consolidate_schema_gaps'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('decision_traces')]
    if 'project_id' not in cols:
        op.add_column('decision_traces', sa.Column('project_id', sa.String(length=36), nullable=True))
        op.create_index('ix_decision_traces_project_id', 'decision_traces', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_decision_traces_project_id', table_name='decision_traces')
    op.drop_column('decision_traces', 'project_id')
