"""add_field_provenance_discipline_and_structured_models

Revision ID: 0016_structured_persistence_and_provenance
Revises: 0015_multimodal_assisted_review_and_enrichment
Create Date: 2026-08-24 12:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0016_structured_persistence_and_provenance'
down_revision: Union[str, None] = '0015_multimodal_assisted_review_and_enrichment'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Agregar columnas a extracted_items
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('extracted_items')]

    if 'discipline' not in existing_cols:
        op.add_column(
            'extracted_items',
            sa.Column('discipline', sa.String(length=50), server_default='general', nullable=False)
        )
        op.create_index(
            'ix_extracted_items_discipline',
            'extracted_items',
            ['discipline'],
            unique=False
        )

    if 'source_asset_id' not in existing_cols:
        op.add_column(
            'extracted_items',
            sa.Column('source_asset_id', sa.String(length=36), nullable=True)
        )
        op.create_index(
            'ix_extracted_items_source_asset_id',
            'extracted_items',
            ['source_asset_id'],
            unique=False
        )

    if 'field_provenance' not in existing_cols:
        op.add_column(
            'extracted_items',
            sa.Column('field_provenance', sa.JSON(), server_default='{}', nullable=False)
        )

    # 2. Crear tablas estructuradas hijas si no existen
    existing_tables = inspector.get_table_names()

    if 'structured_tables' not in existing_tables:
        op.create_table(
            'structured_tables',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('extracted_item_id', sa.String(length=36), sa.ForeignKey('extracted_items.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('table_code', sa.String(length=100), nullable=True),
            sa.Column('caption', sa.Text(), nullable=True),
            sa.Column('num_rows', sa.Integer(), server_default='0', nullable=False),
            sa.Column('num_cols', sa.Integer(), server_default='0', nullable=False),
            sa.Column('headers', sa.JSON(), nullable=False),
            sa.Column('rows_data', sa.JSON(), nullable=False),
            sa.Column('matrix_summary', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
        )
        op.create_index('ix_structured_tables_extracted_item_id', 'structured_tables', ['extracted_item_id'], unique=True)
        op.create_index('ix_structured_tables_table_code', 'structured_tables', ['table_code'], unique=False)

    if 'structured_symbols' not in existing_tables:
        op.create_table(
            'structured_symbols',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('extracted_item_id', sa.String(length=36), sa.ForeignKey('extracted_items.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('symbol_name', sa.String(length=255), nullable=False),
            sa.Column('standard_family', sa.String(length=100), nullable=True),
            sa.Column('discipline', sa.String(length=50), server_default='general', nullable=False),
            sa.Column('category', sa.String(length=100), nullable=True),
            sa.Column('svg_path', sa.Text(), nullable=True),
            sa.Column('crop_image_path', sa.String(length=500), nullable=True),
            sa.Column('confidence_score', sa.Float(), server_default='1.0', nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
        )
        op.create_index('ix_structured_symbols_extracted_item_id', 'structured_symbols', ['extracted_item_id'], unique=True)
        op.create_index('ix_structured_symbols_standard_family', 'structured_symbols', ['standard_family'], unique=False)
        op.create_index('ix_structured_symbols_discipline', 'structured_symbols', ['discipline'], unique=False)

    if 'structured_equipment' not in existing_tables:
        op.create_table(
            'structured_equipment',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('extracted_item_id', sa.String(length=36), sa.ForeignKey('extracted_items.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('tag_code', sa.String(length=100), nullable=False),
            sa.Column('equipment_type', sa.String(length=100), nullable=False),
            sa.Column('service_description', sa.Text(), nullable=True),
            sa.Column('manufacturer', sa.String(length=255), nullable=True),
            sa.Column('model_number', sa.String(length=100), nullable=True),
            sa.Column('rated_capacity', sa.String(length=100), nullable=True),
            sa.Column('operating_parameters', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
        )
        op.create_index('ix_structured_equipment_extracted_item_id', 'structured_equipment', ['extracted_item_id'], unique=True)
        op.create_index('ix_structured_equipment_tag_code', 'structured_equipment', ['tag_code'], unique=False)

    if 'structured_rules_premises' not in existing_tables:
        op.create_table(
            'structured_rules_premises',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('extracted_item_id', sa.String(length=36), sa.ForeignKey('extracted_items.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('rule_code', sa.String(length=100), nullable=False),
            sa.Column('statement', sa.Text(), nullable=False),
            sa.Column('rule_type', sa.String(length=50), server_default='mandatory_rule', nullable=False),
            sa.Column('discipline', sa.String(length=50), server_default='general', nullable=False),
            sa.Column('severity', sa.String(length=30), server_default='warning', nullable=False),
            sa.Column('evaluation_logic', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
        )
        op.create_index('ix_structured_rules_premises_extracted_item_id', 'structured_rules_premises', ['extracted_item_id'], unique=True)
        op.create_index('ix_structured_rules_premises_rule_code', 'structured_rules_premises', ['rule_code'], unique=False)


def downgrade() -> None:
    op.drop_table('structured_rules_premises')
    op.drop_table('structured_equipment')
    op.drop_table('structured_symbols')
    op.drop_table('structured_tables')

    op.drop_column('extracted_items', 'field_provenance')
    op.drop_index('ix_extracted_items_source_asset_id', table_name='extracted_items')
    op.drop_column('extracted_items', 'source_asset_id')
    op.drop_index('ix_extracted_items_discipline', table_name='extracted_items')
    op.drop_column('extracted_items', 'discipline')
