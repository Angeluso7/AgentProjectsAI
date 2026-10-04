"""piping_canonical_catalog_and_occurrences

Revision ID: 0023_piping_canonical_catalog
Revises: 0022_expand_symbol_templates
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0023_piping_canonical_catalog'
down_revision: Union[str, None] = '0022_expand_symbol_templates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Extender symbol_templates con campos de catálogo canónico
    if 'symbol_templates' in existing_tables:
        tmpl_columns = [col['name'] for col in inspector.get_columns('symbol_templates')]
        if 'canonical_code' not in tmpl_columns:
            op.add_column('symbol_templates', sa.Column('canonical_code', sa.String(100), nullable=True))
        if 'canonical_name' not in tmpl_columns:
            op.add_column('symbol_templates', sa.Column('canonical_name', sa.String(150), nullable=True))
        if 'category' not in tmpl_columns:
            op.add_column('symbol_templates', sa.Column('category', sa.String(100), nullable=True))
        if 'subcategory' not in tmpl_columns:
            op.add_column('symbol_templates', sa.Column('subcategory', sa.String(100), nullable=True))
        if 'discipline' not in tmpl_columns:
            op.add_column('symbol_templates', sa.Column('discipline', sa.String(50), nullable=False, server_default='piping'))
        if 'technical_function' not in tmpl_columns:
            op.add_column('symbol_templates', sa.Column('technical_function', sa.Text(), nullable=True))
        if 'standard_reference' not in tmpl_columns:
            op.add_column('symbol_templates', sa.Column('standard_reference', sa.String(150), nullable=True))
        if 'status' not in tmpl_columns:
            op.add_column('symbol_templates', sa.Column('status', sa.String(30), nullable=False, server_default='active'))
        if 'current_version_id' not in tmpl_columns:
            op.add_column('symbol_templates', sa.Column('current_version_id', sa.String(36), nullable=True))
        if 'created_by' not in tmpl_columns:
            op.add_column('symbol_templates', sa.Column('created_by', sa.String(100), nullable=True))
        if 'updated_at' not in tmpl_columns:
            op.add_column('symbol_templates', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))

        tmpl_indexes = [idx['name'] for idx in inspector.get_indexes('symbol_templates')]
        if 'ix_symbol_templates_canonical_code' not in tmpl_indexes:
            op.create_index('ix_symbol_templates_canonical_code', 'symbol_templates', ['canonical_code'], unique=False)
        if 'ix_symbol_templates_category' not in tmpl_indexes:
            op.create_index('ix_symbol_templates_category', 'symbol_templates', ['category'], unique=False)
        if 'ix_symbol_templates_subcategory' not in tmpl_indexes:
            op.create_index('ix_symbol_templates_subcategory', 'symbol_templates', ['subcategory'], unique=False)
        if 'ix_symbol_templates_discipline' not in tmpl_indexes:
            op.create_index('ix_symbol_templates_discipline', 'symbol_templates', ['discipline'], unique=False)
        if 'ix_symbol_templates_status' not in tmpl_indexes:
            op.create_index('ix_symbol_templates_status', 'symbol_templates', ['status'], unique=False)

    # 2. Crear tabla symbol_template_versions
    if 'symbol_template_versions' not in existing_tables:
        op.create_table(
            'symbol_template_versions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('symbol_template_id', sa.String(36), sa.ForeignKey('symbol_templates.id', ondelete='CASCADE'), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('approval_status', sa.String(30), nullable=False, server_default='approved'),
            sa.Column('source_kind', sa.String(50), nullable=False, server_default='normative_document'),
            sa.Column('canonical_crop_path', sa.String(500), nullable=True),
            sa.Column('canonical_crop_hash', sa.String(64), nullable=True),
            sa.Column('normalized_representation', sa.JSON(), nullable=True),
            sa.Column('orientation_policy', sa.String(50), nullable=False, server_default='rotation_equivalent_180'),
            sa.Column('scale_policy', sa.String(50), nullable=False, server_default='isotropic_bounded'),
            sa.Column('geometric_signature', sa.JSON(), nullable=True),
            sa.Column('perceptual_signature', sa.JSON(), nullable=True),
            sa.Column('matcher_thresholds', sa.JSON(), nullable=True),
            sa.Column('approved_by', sa.String(100), nullable=True),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        op.create_index('ix_symbol_tmpl_versions_tmpl_id', 'symbol_template_versions', ['symbol_template_id'])
        op.create_index('ix_symbol_tmpl_versions_status', 'symbol_template_versions', ['approval_status'])

    # 3. Crear tabla symbol_geometric_features
    if 'symbol_geometric_features' not in existing_tables:
        op.create_table(
            'symbol_geometric_features',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('symbol_template_version_id', sa.String(36), sa.ForeignKey('symbol_template_versions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('feature_type', sa.String(50), nullable=False),
            sa.Column('feature_count', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('feature_parameters', sa.JSON(), nullable=False),
            sa.Column('normalized_bbox', sa.JSON(), nullable=False),
            sa.Column('relative_position', sa.String(50), nullable=True),
            sa.Column('orientation_degrees', sa.Float(), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('relationship_group', sa.String(50), nullable=True),
            sa.Column('extractor_version', sa.String(30), nullable=False, server_default='v1.0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        op.create_index('ix_symbol_geom_features_version_id', 'symbol_geometric_features', ['symbol_template_version_id'])
        op.create_index('ix_symbol_geom_features_type', 'symbol_geometric_features', ['feature_type'])

    # 4. Crear tabla symbol_feature_relations
    if 'symbol_feature_relations' not in existing_tables:
        op.create_table(
            'symbol_feature_relations',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('source_feature_id', sa.String(36), sa.ForeignKey('symbol_geometric_features.id', ondelete='CASCADE'), nullable=False),
            sa.Column('target_feature_id', sa.String(36), sa.ForeignKey('symbol_geometric_features.id', ondelete='CASCADE'), nullable=False),
            sa.Column('relation_type', sa.String(50), nullable=False),
            sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('relation_parameters', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        op.create_index('ix_symbol_feat_rel_src', 'symbol_feature_relations', ['source_feature_id'])
        op.create_index('ix_symbol_feat_rel_tgt', 'symbol_feature_relations', ['target_feature_id'])
        op.create_index('ix_symbol_feat_rel_type', 'symbol_feature_relations', ['relation_type'])

    # 5. Crear tabla symbol_source_evidences
    if 'symbol_source_evidences' not in existing_tables:
        op.create_table(
            'symbol_source_evidences',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('symbol_template_version_id', sa.String(36), sa.ForeignKey('symbol_template_versions.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('source_document_id', sa.String(36), nullable=True),
            sa.Column('source_document_hash', sa.String(64), nullable=True),
            sa.Column('evidence_kind', sa.String(30), nullable=False, server_default='synthetic'),
            sa.Column('page_number', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('sheet_id', sa.String(36), nullable=True),
            sa.Column('table_id', sa.String(36), nullable=True),
            sa.Column('cell_id', sa.String(36), nullable=True),
            sa.Column('bbox_normalized', sa.JSON(), nullable=False),
            sa.Column('cell_bbox', sa.JSON(), nullable=True),
            sa.Column('inner_drawing_bbox', sa.JSON(), nullable=True),
            sa.Column('symbol_crop_bbox', sa.JSON(), nullable=True),
            sa.Column('crop_image_path', sa.String(500), nullable=True),
            sa.Column('crop_image_hash', sa.String(64), nullable=True),
            sa.Column('source_excerpt', sa.Text(), nullable=True),
            sa.Column('grid_source', sa.String(30), nullable=True),
            sa.Column('geometric_confidence', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('source_standard_or_project', sa.String(150), nullable=True),
            sa.Column('source_revision', sa.String(50), nullable=True),
            sa.Column('source_date', sa.String(50), nullable=True),
            sa.Column('extraction_run_id', sa.String(36), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        op.create_index('ix_symbol_source_ev_ver_id', 'symbol_source_evidences', ['symbol_template_version_id'], unique=True)
        op.create_index('ix_symbol_source_ev_doc_id', 'symbol_source_evidences', ['source_document_id'])
        op.create_index('ix_symbol_source_ev_kind', 'symbol_source_evidences', ['evidence_kind'])

    # 6. Crear tabla symbol_review_decisions
    if 'symbol_review_decisions' not in existing_tables:
        op.create_table(
            'symbol_review_decisions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('subject_type', sa.String(30), nullable=False),
            sa.Column('subject_id', sa.String(36), nullable=False),
            sa.Column('decision', sa.String(50), nullable=False),
            sa.Column('reviewer_id', sa.String(100), nullable=False),
            sa.Column('rationale', sa.Text(), nullable=True),
            sa.Column('evidence_snapshot', sa.JSON(), nullable=True),
            sa.Column('previous_state', sa.JSON(), nullable=True),
            sa.Column('new_state', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        op.create_index('ix_symbol_rev_dec_subj_type', 'symbol_review_decisions', ['subject_type'])
        op.create_index('ix_symbol_rev_dec_subj_id', 'symbol_review_decisions', ['subject_id'])
        op.create_index('ix_symbol_rev_dec_decision', 'symbol_review_decisions', ['decision'])

    # 7. Extender detected_symbols con campos de SymbolOccurrence de proyecto
    if 'detected_symbols' in existing_tables:
        det_columns = [col['name'] for col in inspector.get_columns('detected_symbols')]
        if 'project_id' not in det_columns:
            op.add_column('detected_symbols', sa.Column('project_id', sa.String(36), nullable=True))
        if 'project_document_id' not in det_columns:
            op.add_column('detected_symbols', sa.Column('project_document_id', sa.String(36), nullable=True))
        if 'table_id' not in det_columns:
            op.add_column('detected_symbols', sa.Column('table_id', sa.String(36), nullable=True))
        if 'cell_id' not in det_columns:
            op.add_column('detected_symbols', sa.Column('cell_id', sa.String(36), nullable=True))
        if 'cell_bbox' not in det_columns:
            op.add_column('detected_symbols', sa.Column('cell_bbox', sa.JSON(), nullable=True))
        if 'inner_drawing_bbox' not in det_columns:
            op.add_column('detected_symbols', sa.Column('inner_drawing_bbox', sa.JSON(), nullable=True))
        if 'symbol_crop_bbox' not in det_columns:
            op.add_column('detected_symbols', sa.Column('symbol_crop_bbox', sa.JSON(), nullable=True))
        if 'crop_image_path' not in det_columns:
            op.add_column('detected_symbols', sa.Column('crop_image_path', sa.String(500), nullable=True))
        if 'crop_image_hash' not in det_columns:
            op.add_column('detected_symbols', sa.Column('crop_image_hash', sa.String(64), nullable=True))
        if 'classification' not in det_columns:
            op.add_column('detected_symbols', sa.Column('classification', sa.String(40), nullable=False, server_default='symbol'))
        if 'geometric_evidence' not in det_columns:
            op.add_column('detected_symbols', sa.Column('geometric_evidence', sa.Boolean(), nullable=False, server_default='true'))
        if 'geometric_confidence' not in det_columns:
            op.add_column('detected_symbols', sa.Column('geometric_confidence', sa.Float(), nullable=False, server_default='1.0'))
        if 'matching_status' not in det_columns:
            op.add_column('detected_symbols', sa.Column('matching_status', sa.String(30), nullable=False, server_default='unmatched'))
        if 'matched_template_id' not in det_columns:
            op.add_column('detected_symbols', sa.Column('matched_template_id', sa.String(36), sa.ForeignKey('symbol_templates.id', ondelete='SET NULL'), nullable=True))
        if 'matched_template_version_id' not in det_columns:
            op.add_column('detected_symbols', sa.Column('matched_template_version_id', sa.String(36), sa.ForeignKey('symbol_template_versions.id', ondelete='SET NULL'), nullable=True))
        if 'match_score' not in det_columns:
            op.add_column('detected_symbols', sa.Column('match_score', sa.Float(), nullable=True))
        if 'geometry_score' not in det_columns:
            op.add_column('detected_symbols', sa.Column('geometry_score', sa.Float(), nullable=True))
        if 'topology_score' not in det_columns:
            op.add_column('detected_symbols', sa.Column('topology_score', sa.Float(), nullable=True))
        if 'visual_score' not in det_columns:
            op.add_column('detected_symbols', sa.Column('visual_score', sa.Float(), nullable=True))
        if 'context_score' not in det_columns:
            op.add_column('detected_symbols', sa.Column('context_score', sa.Float(), nullable=True))
        if 'detected_tag_or_code' not in det_columns:
            op.add_column('detected_symbols', sa.Column('detected_tag_or_code', sa.String(100), nullable=True))
        if 'context_text' not in det_columns:
            op.add_column('detected_symbols', sa.Column('context_text', sa.Text(), nullable=True))
        if 'review_status' not in det_columns:
            op.add_column('detected_symbols', sa.Column('review_status', sa.String(30), nullable=False, server_default='unreviewed'))
        if 'detection_run_id' not in det_columns:
            op.add_column('detected_symbols', sa.Column('detection_run_id', sa.String(36), nullable=True))

        det_indexes = [idx['name'] for idx in inspector.get_indexes('detected_symbols')]
        if 'ix_detected_symbols_project_id' not in det_indexes:
            op.create_index('ix_detected_symbols_project_id', 'detected_symbols', ['project_id'])
        if 'ix_detected_symbols_classification' not in det_indexes:
            op.create_index('ix_detected_symbols_classification', 'detected_symbols', ['classification'])
        if 'ix_detected_symbols_matching_status' not in det_indexes:
            op.create_index('ix_detected_symbols_matching_status', 'detected_symbols', ['matching_status'])
        if 'ix_detected_symbols_matched_tmpl_id' not in det_indexes:
            op.create_index('ix_detected_symbols_matched_tmpl_id', 'detected_symbols', ['matched_template_id'])
        if 'ix_detected_symbols_review_status' not in det_indexes:
            op.create_index('ix_detected_symbols_review_status', 'detected_symbols', ['review_status'])

    # 8. Crear tabla symbol_unknown_research_cases
    if 'symbol_unknown_research_cases' not in existing_tables:
        op.create_table(
            'symbol_unknown_research_cases',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('symbol_occurrence_id', sa.String(36), sa.ForeignKey('detected_symbols.id', ondelete='CASCADE'), nullable=False),
            sa.Column('status', sa.String(40), nullable=False, server_default='unknown'),
            sa.Column('search_query', sa.String(255), nullable=True),
            sa.Column('source_urls', sa.JSON(), nullable=True),
            sa.Column('proposed_name', sa.String(200), nullable=True),
            sa.Column('proposed_standard_reference', sa.String(150), nullable=True),
            sa.Column('research_notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        op.create_index('ix_sym_unk_res_case_occ_id', 'symbol_unknown_research_cases', ['symbol_occurrence_id'])
        op.create_index('ix_sym_unk_res_case_status', 'symbol_unknown_research_cases', ['status'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 8. Eliminar symbol_unknown_research_cases
    if 'symbol_unknown_research_cases' in existing_tables:
        op.drop_table('symbol_unknown_research_cases')

    # 7. Eliminar columnas e índices agregados a detected_symbols
    if 'detected_symbols' in existing_tables:
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('detected_symbols')}
        for idx_name in [
            'ix_detected_symbols_review_status',
            'ix_detected_symbols_matched_tmpl_id',
            'ix_detected_symbols_matching_status',
            'ix_detected_symbols_classification',
            'ix_detected_symbols_project_id'
        ]:
            if idx_name in existing_indexes:
                op.drop_index(idx_name, table_name='detected_symbols')

        existing_cols = {col['name'] for col in inspector.get_columns('detected_symbols')}
        for col in [
            'detection_run_id', 'review_status', 'context_text', 'detected_tag_or_code',
            'context_score', 'visual_score', 'topology_score', 'geometry_score', 'match_score',
            'matched_template_version_id', 'matched_template_id', 'matching_status',
            'geometric_confidence', 'geometric_evidence', 'classification', 'crop_image_hash',
            'crop_image_path', 'symbol_crop_bbox', 'inner_drawing_bbox', 'cell_bbox',
            'cell_id', 'table_id', 'project_document_id', 'project_id'
        ]:
            if col in existing_cols:
                op.drop_column('detected_symbols', col)

    # 6. Eliminar symbol_review_decisions
    if 'symbol_review_decisions' in existing_tables:
        op.drop_table('symbol_review_decisions')

    # 5. Eliminar symbol_source_evidences
    if 'symbol_source_evidences' in existing_tables:
        op.drop_table('symbol_source_evidences')

    # 4. Eliminar symbol_feature_relations
    if 'symbol_feature_relations' in existing_tables:
        op.drop_table('symbol_feature_relations')

    # 3. Eliminar symbol_geometric_features
    if 'symbol_geometric_features' in existing_tables:
        op.drop_table('symbol_geometric_features')

    # 2. Eliminar symbol_template_versions
    if 'symbol_template_versions' in existing_tables:
        op.drop_table('symbol_template_versions')

    # 1. Eliminar columnas e índices de symbol_templates
    if 'symbol_templates' in existing_tables:
        tmpl_indexes = {idx['name'] for idx in inspector.get_indexes('symbol_templates')}
        for idx_name in [
            'ix_symbol_templates_status',
            'ix_symbol_templates_discipline',
            'ix_symbol_templates_subcategory',
            'ix_symbol_templates_category',
            'ix_symbol_templates_canonical_code'
        ]:
            if idx_name in tmpl_indexes:
                op.drop_index(idx_name, table_name='symbol_templates')

        tmpl_cols = {col['name'] for col in inspector.get_columns('symbol_templates')}
        for col in [
            'updated_at', 'created_by', 'current_version_id', 'status', 'standard_reference',
            'technical_function', 'discipline', 'subcategory', 'category', 'canonical_name', 'canonical_code'
        ]:
            if col in tmpl_cols:
                op.drop_column('symbol_templates', col)
