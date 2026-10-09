"""deactivate_legacy_architecture_rules

Revision ID: 0034_deactivate_legacy_architecture_rules
Revises: 0033_add_project_id_to_decision_traces
Create Date: 2026-10-09 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0034_deactivate_legacy_architecture_rules'
down_revision: Union[str, None] = '0033_add_project_id_to_decision_traces'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # Desactivar de forma permanente y segura las 6 reglas demo/legacy sin borrar historial
    conn.execute(
        sa.text(
            """
            UPDATE rule_definitions
            SET enabled = false, is_active = false
            WHERE code IN (
                'RULE_DOOR_COUNT_MATCH_V1',
                'RULE_WINDOW_COUNT_MATCH_V1',
                'RULE_TITLE_BLOCK_REQUIRED_FIELDS_V1',
                'RULE_TITLE_BLOCK_SCALE_VALID_V1',
                'RULE_REQUIRED_TABLES_BY_DOCUMENT_TYPE_V1',
                'RULE_NORMATIVE_MIN_WIDTH_DOOR_V1'
            )
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE rule_definitions
            SET enabled = true, is_active = true
            WHERE code IN (
                'RULE_DOOR_COUNT_MATCH_V1',
                'RULE_WINDOW_COUNT_MATCH_V1',
                'RULE_TITLE_BLOCK_REQUIRED_FIELDS_V1',
                'RULE_TITLE_BLOCK_SCALE_VALID_V1',
                'RULE_REQUIRED_TABLES_BY_DOCUMENT_TYPE_V1',
                'RULE_NORMATIVE_MIN_WIDTH_DOOR_V1'
            )
            """
        )
    )
