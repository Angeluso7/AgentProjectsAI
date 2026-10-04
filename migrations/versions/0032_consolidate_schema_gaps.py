"""consolidate_schema_gaps

Revision ID: 0032_consolidate_schema_gaps
Revises: 0031_rule_candidate_promotion
Create Date: 2026-10-04 20:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0032_consolidate_schema_gaps'
down_revision: Union[str, None] = '0031_rule_candidate_promotion'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # =========================================================================
    # 1. Crear tablas del modelo no cubiertas en migraciones históricas
    # =========================================================================

    if 'information_acquisition_requests' not in existing_tables:
        op.create_table(
            'information_acquisition_requests',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True, index=True),
            sa.Column('stage', sa.String(50), nullable=True, index=True),
            sa.Column('discipline', sa.String(50), server_default='general', nullable=False, index=True),
            sa.Column('missing_topic', sa.String(255), nullable=False),
            sa.Column('gap_description', sa.Text(), nullable=False),
            sa.Column('detection_source', sa.String(50), server_default='assistant_evaluator', nullable=False),
            sa.Column('internal_rag_status', sa.String(30), server_default='insufficient', nullable=False),
            sa.Column('internal_rag_score', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('internal_rag_matches_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('permission_status', sa.String(30), server_default='pending_permission', nullable=False, index=True),
            sa.Column('permission_requested_at', sa.DateTime(), nullable=False),
            sa.Column('permission_granted_by', sa.String(100), nullable=True),
            sa.Column('permission_granted_at', sa.DateTime(), nullable=True),
            sa.Column('rejection_reason', sa.Text(), nullable=True),
            sa.Column('action_type', sa.String(50), server_default='web_search', nullable=False),
            sa.Column('web_search_query', sa.String(500), nullable=True),
            sa.Column('web_search_executed', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('web_search_executed_at', sa.DateTime(), nullable=True),
            sa.Column('web_search_result_summary', sa.Text(), nullable=True),
            sa.Column('web_search_sources', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('iteration_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('max_iterations', sa.Integer(), server_default='3', nullable=False),
            sa.Column('search_sources_limit', sa.Integer(), server_default='5', nullable=False),
            sa.Column('adequacy_status', sa.String(50), server_default='pending_evaluation', nullable=False),
            sa.Column('adequacy_classification', sa.String(64), server_default='pending', nullable=False),
            sa.Column('relevance_score', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('confidence_score', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('coverage_score', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('overall_adequacy_score', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('termination_reason', sa.String(64), nullable=True),
            sa.Column('requested_document_type', sa.String(100), nullable=True),
            sa.Column('requested_document_justification', sa.Text(), nullable=True),
            sa.Column('suggested_responsible', sa.String(100), nullable=True),
            sa.Column('escalation_details', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('created_knowledge_item_id', sa.String(36), sa.ForeignKey('knowledge_items.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('status', sa.String(30), server_default='open', nullable=False, index=True),
            sa.Column('metadata_payload', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('information_acquisition_requests')

    if 'assistant_interactions' not in existing_tables:
        op.create_table(
            'assistant_interactions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True, index=True),
            sa.Column('task_type', sa.String(50), nullable=False, index=True),
            sa.Column('user_prompt', sa.Text(), nullable=False),
            sa.Column('resolved_prompt', sa.Text(), nullable=True),
            sa.Column('stage', sa.String(50), nullable=True, index=True),
            sa.Column('discipline', sa.String(50), nullable=True, index=True),
            sa.Column('retrieved_knowledge_ids', sa.JSON(), server_default='[]', nullable=False),
            sa.Column('retrieved_chunks', sa.JSON(), server_default='[]', nullable=False),
            sa.Column('initial_tier', sa.Integer(), server_default='1', nullable=False),
            sa.Column('executed_tier', sa.Integer(), server_default='1', nullable=False),
            sa.Column('engine_model_used', sa.String(100), nullable=False),
            sa.Column('was_escalated', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('escalation_reason', sa.String(255), nullable=True),
            sa.Column('generated_response', sa.Text(), nullable=False),
            sa.Column('structured_output', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('confidence_score', sa.Float(), server_default='1.0', nullable=False),
            sa.Column('cost_estimate_usd', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('feedback_status', sa.String(30), server_default='pending', nullable=False, index=True),
            sa.Column('feedback_payload', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('user_id', sa.String(100), server_default='system', nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('assistant_interactions')

    if 'audit_observations' not in existing_tables:
        op.create_table(
            'audit_observations',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('stage', sa.String(50), nullable=False, index=True),
            sa.Column('code', sa.String(50), nullable=False, index=True),
            sa.Column('item_type', sa.String(50), nullable=False, index=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('recommendation', sa.Text(), nullable=True),
            sa.Column('discipline', sa.String(50), server_default='general', nullable=False, index=True),
            sa.Column('severity', sa.String(20), server_default='medium', nullable=False, index=True),
            sa.Column('status', sa.String(30), server_default='draft', nullable=False, index=True),
            sa.Column('rule_finding_id', sa.String(36), sa.ForeignKey('rule_findings.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('rule_id', sa.String(36), sa.ForeignKey('rule_definitions.id', ondelete='SET NULL'), nullable=True),
            sa.Column('rule_code', sa.String(100), nullable=True, index=True),
            sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('review_run_id', sa.String(36), sa.ForeignKey('review_runs.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('required_deliverable_type', sa.String(50), nullable=True),
            sa.Column('provisioned_document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
            sa.Column('resolution_notes', sa.Text(), nullable=True),
            sa.Column('issued_by', sa.String(100), server_default='system', nullable=False),
            sa.Column('assigned_to', sa.String(100), nullable=True),
            sa.Column('issued_at', sa.DateTime(), nullable=True),
            sa.Column('answered_at', sa.DateTime(), nullable=True),
            sa.Column('provisioned_at', sa.DateTime(), nullable=True),
            sa.Column('closed_at', sa.DateTime(), nullable=True),
            sa.Column('history_trace', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('audit_observations')

    if 'observation_responses' not in existing_tables:
        op.create_table(
            'observation_responses',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('observation_id', sa.String(36), sa.ForeignKey('audit_observations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('author', sa.String(100), nullable=False),
            sa.Column('author_role', sa.String(50), server_default='contractor', nullable=False),
            sa.Column('response_text', sa.Text(), nullable=False),
            sa.Column('attached_document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('observation_responses')

    if 'project_deliverable_requirements' not in existing_tables:
        op.create_table(
            'project_deliverable_requirements',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True, index=True),
            sa.Column('stage', sa.String(50), nullable=False, index=True),
            sa.Column('discipline', sa.String(50), server_default='general', nullable=False, index=True),
            sa.Column('deliverable_type', sa.String(50), nullable=False, index=True),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_mandatory', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('blocked_rule_codes', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('project_deliverable_requirements')

    if 'document_deliverables' not in existing_tables:
        op.create_table(
            'document_deliverables',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
            sa.Column('deliverable_type', sa.String(50), server_default='plano_general', nullable=False, index=True),
            sa.Column('readiness_status', sa.String(50), server_default='uploaded', nullable=False, index=True),
            sa.Column('validation_notes', sa.Text(), nullable=True),
            sa.Column('classified_by', sa.String(100), server_default='system', nullable=False),
            sa.Column('validated_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('document_deliverables')

    if 'project_completeness_evaluations' not in existing_tables:
        op.create_table(
            'project_completeness_evaluations',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('stage', sa.String(50), nullable=False),
            sa.Column('completeness_percentage', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('is_gate_passed', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('total_required_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('eligible_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('missing_mandatory_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('missing_optional_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('blocked_rules_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('deliverables_matrix', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('missing_deliverables', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('blocked_rules', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('evaluated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('project_completeness_evaluations')

    if 'project_maturity_profiles' not in existing_tables:
        op.create_table(
            'project_maturity_profiles',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('stage', sa.String(50), nullable=False, index=True),
            sa.Column('overall_score', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('maturity_level', sa.String(30), server_default='insufficient', nullable=False, index=True),
            sa.Column('target_level', sa.String(30), server_default='advanced', nullable=False),
            sa.Column('is_target_achieved', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('dimension_scores', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('discipline_scores', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('critical_gaps', sa.JSON(), server_default='[]', nullable=False),
            sa.Column('acquisition_routes', sa.JSON(), server_default='[]', nullable=False),
            sa.Column('acquired_knowledge_summary', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('assistant_usage_summary', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('review_capability_assessment', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('delta_summary', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('evaluated_by', sa.String(100), server_default='system_maturity_engine', nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('project_maturity_profiles')

    if 'project_stage_report_snapshots' not in existing_tables:
        op.create_table(
            'project_stage_report_snapshots',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True, index=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('stage', sa.String(50), nullable=False, index=True),
            sa.Column('revision_number', sa.Integer(), server_default='1', nullable=False, index=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('global_stage_verdict', sa.String(50), nullable=False, index=True),
            sa.Column('verdict_rationale', sa.Text(), nullable=False),
            sa.Column('completeness_summary', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('audit_verdicts_summary', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('observations_summary', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('delta_evolution_summary', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('artifact_pdf_path', sa.String(500), nullable=True),
            sa.Column('artifact_json_path', sa.String(500), nullable=True),
            sa.Column('manifest_hash', sa.String(64), nullable=True),
            sa.Column('issued_by', sa.String(100), server_default='auditor_lead', nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('project_stage_report_snapshots')

    if 'research_queries' not in existing_tables:
        op.create_table(
            'research_queries',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('search_prompt', sa.Text(), nullable=False),
            sa.Column('discipline', sa.String(50), server_default='Arquitectura', nullable=False, index=True),
            sa.Column('document_type', sa.String(50), server_default='norma', nullable=False),
            sa.Column('authority', sa.String(150), nullable=True),
            sa.Column('focus_areas', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('status', sa.String(30), server_default='completed', nullable=False),
            sa.Column('metadata_payload', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('research_queries')

    if 'research_results' not in existing_tables:
        op.create_table(
            'research_results',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('query_id', sa.String(36), sa.ForeignKey('research_queries.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('source_extraction_id', sa.String(36), sa.ForeignKey('source_extractions.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('executive_summary', sa.Text(), nullable=True),
            sa.Column('total_items_found', sa.Integer(), server_default='0', nullable=False),
            sa.Column('raw_payload', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('metadata_info', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('research_results')

    if 'research_sources' not in existing_tables:
        op.create_table(
            'research_sources',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('result_id', sa.String(36), sa.ForeignKey('research_results.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('url', sa.String(500), nullable=False),
            sa.Column('domain', sa.String(150), nullable=False),
            sa.Column('snippet', sa.Text(), nullable=True),
            sa.Column('retrieved_at', sa.DateTime(), nullable=False),
            sa.Column('reliability_score', sa.Float(), server_default='0.9', nullable=False)
        )
        existing_tables.add('research_sources')

    if 'research_items' not in existing_tables:
        op.create_table(
            'research_items',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('result_id', sa.String(36), sa.ForeignKey('research_results.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('item_type', sa.String(50), nullable=False),
            sa.Column('item_nature', sa.String(50), server_default='proposed_rule', nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('code_or_number', sa.String(100), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('content_text', sa.Text(), nullable=True),
            sa.Column('source_reference', sa.String(500), nullable=True),
            sa.Column('governance_note', sa.Text(), nullable=True),
            sa.Column('validation_status', sa.String(30), server_default='pending_review', nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('research_items')

    if 'supporting_knowledge_items' not in existing_tables:
        op.create_table(
            'supporting_knowledge_items',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('source_asset_id', sa.String(36), sa.ForeignKey('source_assets.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('source_extraction_id', sa.String(36), sa.ForeignKey('source_extractions.id', ondelete='SET NULL'), nullable=True),
            sa.Column('extracted_item_id', sa.String(36), nullable=True),
            sa.Column('item_type', sa.String(50), nullable=False, index=True),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('code_or_number', sa.String(100), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('discipline', sa.String(50), server_default='general', nullable=False, index=True),
            sa.Column('page_number', sa.Integer(), server_default='1', nullable=False),
            sa.Column('bbox_normalized', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('crop_image_path', sa.String(500), nullable=True),
            sa.Column('ocr_text', sa.Text(), nullable=True),
            sa.Column('structured_matrix', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('status', sa.String(30), server_default='validada', nullable=False),
            sa.Column('validated_by', sa.String(100), server_default='system', nullable=False),
            sa.Column('validated_at', sa.DateTime(), nullable=False),
            sa.Column('metadata_payload', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('supporting_knowledge_items')

    if 'manual_annotations' not in existing_tables:
        op.create_table(
            'manual_annotations',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('sheet_id', sa.String(36), sa.ForeignKey('document_sheets.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('bbox_normalized', sa.JSON(), nullable=False),
            sa.Column('bbox_pixels', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('crop_image_path', sa.String(500), nullable=True),
            sa.Column('element_type', sa.String(50), nullable=False, index=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('ocr_text', sa.Text(), nullable=True),
            sa.Column('discipline', sa.String(50), server_default='general', nullable=False),
            sa.Column('category', sa.String(100), nullable=True),
            sa.Column('confidence', sa.Float(), server_default='1.0', nullable=True),
            sa.Column('tags', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('status', sa.String(40), server_default='confirmed', nullable=False, index=True),
            sa.Column('extra_metadata', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('manual_annotations')

    if 'knowledge_library_entries' not in existing_tables:
        op.create_table(
            'knowledge_library_entries',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('source_annotation_id', sa.String(36), sa.ForeignKey('manual_annotations.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('entry_type', sa.String(50), nullable=False, index=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('discipline', sa.String(50), server_default='general', nullable=False),
            sa.Column('crop_image_path', sa.String(500), nullable=True),
            sa.Column('canonical_text', sa.Text(), nullable=True),
            sa.Column('tags', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('is_verified', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('created_by_user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('status', sa.String(30), server_default='active', nullable=False, index=True),
            sa.Column('extra_metadata', sa.JSON(), server_default='{}', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('knowledge_library_entries')

    if 'active_learning_promotions' not in existing_tables:
        op.create_table(
            'active_learning_promotions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('knowledge_entry_id', sa.String(36), sa.ForeignKey('knowledge_library_entries.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('manual_annotation_id', sa.String(36), sa.ForeignKey('manual_annotations.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('target_engine', sa.String(50), nullable=False, index=True),
            sa.Column('dataset_split', sa.String(30), server_default='few_shot_pool', nullable=False),
            sa.Column('crop_image_path', sa.String(500), nullable=True),
            sa.Column('label', sa.String(100), nullable=False),
            sa.Column('ground_truth_text', sa.Text(), nullable=True),
            sa.Column('ground_truth_bbox', sa.JSON(), server_default='[]', nullable=True),
            sa.Column('promoted_by_user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('status', sa.String(30), server_default='staged', nullable=False, index=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('active_learning_promotions')

    if 'password_reset_tokens' not in existing_tables:
        op.create_table(
            'password_reset_tokens',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('token_hash', sa.String(64), unique=True, nullable=False, index=True),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('used_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('password_reset_tokens')

    if 'email_change_requests' not in existing_tables:
        op.create_table(
            'email_change_requests',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('new_email', sa.String(150), nullable=False, index=True),
            sa.Column('token_hash', sa.String(64), unique=True, nullable=False, index=True),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('used_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False)
        )
        existing_tables.add('email_change_requests')

    # =========================================================================
    # 2. Consolidar columnas e índices de main.py no cubiertas previamente
    # =========================================================================

    # A. knowledge_items
    if 'knowledge_items' in existing_tables:
        ki_cols = {c['name'] for c in inspector.get_columns('knowledge_items')}
        if 'ingestion_channel' not in ki_cols:
            op.add_column('knowledge_items', sa.Column('ingestion_channel', sa.String(64), server_default='manual_entry', nullable=False))
        if 'modality' not in ki_cols:
            op.add_column('knowledge_items', sa.Column('modality', sa.String(64), server_default='text', nullable=False))
        if 'visual_crop_url' not in ki_cols:
            op.add_column('knowledge_items', sa.Column('visual_crop_url', sa.String(512), nullable=True))
        if 'legend_reference' not in ki_cols:
            op.add_column('knowledge_items', sa.Column('legend_reference', sa.String(512), nullable=True))

    # B. structured_symbols (source_table_id, row/col coordinates y bboxes)
    if 'structured_symbols' in existing_tables:
        ss_cols = {c['name'] for c in inspector.get_columns('structured_symbols')}
        if 'source_table_id' not in ss_cols:
            op.add_column('structured_symbols', sa.Column('source_table_id', sa.String(36), nullable=True))
        if 'row_index' not in ss_cols:
            op.add_column('structured_symbols', sa.Column('row_index', sa.Integer(), nullable=True))
        if 'col_index' not in ss_cols:
            op.add_column('structured_symbols', sa.Column('col_index', sa.Integer(), nullable=True))
        if 'cell_bbox' not in ss_cols:
            op.add_column('structured_symbols', sa.Column('cell_bbox', sa.JSON(), nullable=True))
        if 'row_bbox' not in ss_cols:
            op.add_column('structured_symbols', sa.Column('row_bbox', sa.JSON(), nullable=True))

        ss_indexes = {idx['name'] for idx in inspector.get_indexes('structured_symbols')}
        if 'ix_structured_symbols_source_table_id' not in ss_indexes:
            op.create_index('ix_structured_symbols_source_table_id', 'structured_symbols', ['source_table_id'], unique=False)

    # C. rule_documents (symbols_count)
    if 'rule_documents' in existing_tables:
        rd_cols = {c['name'] for c in inspector.get_columns('rule_documents')}
        if 'symbols_count' not in rd_cols:
            op.add_column('rule_documents', sa.Column('symbols_count', sa.Integer(), server_default='0', nullable=False))

    # D. confidence_policies (task_type, exception_threshold, action_on_below_review)
    if 'confidence_policies' in existing_tables:
        cp_cols = {c['name'] for c in inspector.get_columns('confidence_policies')}
        if 'task_type' not in cp_cols:
            op.add_column('confidence_policies', sa.Column('task_type', sa.String(50), nullable=True))
        if 'exception_threshold' not in cp_cols:
            op.add_column('confidence_policies', sa.Column('exception_threshold', sa.Float(), server_default='0.40', nullable=False))
        if 'action_on_below_review' not in cp_cols:
            op.add_column('confidence_policies', sa.Column('action_on_below_review', sa.String(50), server_default='send_to_review_queue', nullable=False))
        if 'policy_name' in cp_cols:
            op.execute("UPDATE confidence_policies SET name = policy_name WHERE name IS NULL")
            op.drop_column('confidence_policies', 'policy_name')

    # E. job_events (actor_type, actor_id)
    if 'job_events' in existing_tables:
        je_cols = {c['name'] for c in inspector.get_columns('job_events')}
        if 'actor_type' not in je_cols:
            op.add_column('job_events', sa.Column('actor_type', sa.String(50), server_default='system', nullable=False))
        if 'actor_id' not in je_cols:
            op.add_column('job_events', sa.Column('actor_id', sa.String(100), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'structured_symbols' in existing_tables:
        ss_indexes = {idx['name'] for idx in inspector.get_indexes('structured_symbols')}
        if 'ix_structured_symbols_source_table_id' in ss_indexes:
            op.drop_index('ix_structured_symbols_source_table_id', table_name='structured_symbols')
        ss_cols = {c['name'] for c in inspector.get_columns('structured_symbols')}
        for col in ['row_bbox', 'cell_bbox', 'col_index', 'row_index', 'source_table_id']:
            if col in ss_cols:
                op.drop_column('structured_symbols', col)

    if 'confidence_policies' in existing_tables:
        cp_cols = {c['name'] for c in inspector.get_columns('confidence_policies')}
        for col in ['action_on_below_review', 'exception_threshold', 'task_type']:
            if col in cp_cols:
                op.drop_column('confidence_policies', col)

    if 'rule_documents' in existing_tables:
        rd_cols = {c['name'] for c in inspector.get_columns('rule_documents')}
        if 'symbols_count' in rd_cols:
            op.drop_column('rule_documents', 'symbols_count')

    if 'knowledge_items' in existing_tables:
        ki_cols = {c['name'] for c in inspector.get_columns('knowledge_items')}
        for col in ['legend_reference', 'visual_crop_url', 'modality']:
            if col in ki_cols:
                op.drop_column('knowledge_items', col)

    for tbl in [
        'email_change_requests', 'password_reset_tokens', 'active_learning_promotions',
        'knowledge_library_entries', 'manual_annotations', 'supporting_knowledge_items',
        'research_items', 'research_sources', 'research_results', 'research_queries',
        'project_stage_report_snapshots', 'project_maturity_profiles',
        'project_completeness_evaluations', 'document_deliverables',
        'project_deliverable_requirements', 'observation_responses',
        'audit_observations', 'assistant_interactions',
        'information_acquisition_requests'
    ]:
        if tbl in existing_tables:
            op.drop_table(tbl)
