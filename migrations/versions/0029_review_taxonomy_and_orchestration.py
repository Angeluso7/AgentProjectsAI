"""review_taxonomy_and_orchestration

Revision ID: 0029_review_taxonomy_and_orchestration
Revises: 0028_document_hash_per_project
Create Date: 2026-09-23 01:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0029_review_taxonomy_and_orchestration'
down_revision: Union[str, None] = '0028_document_hash_per_project'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. review_disciplines
    if 'review_disciplines' not in existing_tables:
        op.create_table(
            'review_disciplines',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('code', sa.String(50), nullable=False, unique=True),
            sa.Column('name', sa.String(150), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        )
        op.create_index('ix_review_disciplines_code', 'review_disciplines', ['code'])

    # 2. review_topics
    if 'review_topics' not in existing_tables:
        op.create_table(
            'review_topics',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('discipline_id', sa.String(36), sa.ForeignKey('review_disciplines.id', ondelete='SET NULL'), nullable=True),
            sa.Column('code', sa.String(100), nullable=False, unique=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_transversal', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('enabled_mvp', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        )
        op.create_index('ix_review_topics_code', 'review_topics', ['code'])
        op.create_index('ix_review_topics_discipline_id', 'review_topics', ['discipline_id'])

    # 3. rule_applicabilities
    if 'rule_applicabilities' not in existing_tables:
        op.create_table(
            'rule_applicabilities',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('rule_id', sa.String(36), sa.ForeignKey('rule_definitions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('discipline_id', sa.String(36), sa.ForeignKey('review_disciplines.id', ondelete='CASCADE'), nullable=False),
            sa.Column('topic_id', sa.String(36), sa.ForeignKey('review_topics.id', ondelete='CASCADE'), nullable=False),
            sa.Column('role', sa.String(30), nullable=False, server_default='primary'),
            sa.Column('source', sa.String(30), nullable=False, server_default='human'),
            sa.Column('approval_status', sa.String(30), nullable=False, server_default='draft'),
            sa.Column('reviewer', sa.String(100), nullable=True),
            sa.Column('rationale', sa.Text(), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('rule_id', 'discipline_id', 'topic_id', name='uq_rule_discipline_topic')
        )
        op.create_index('ix_rule_applicabilities_rule_id', 'rule_applicabilities', ['rule_id'])
        op.create_index('ix_rule_applicabilities_discipline_id', 'rule_applicabilities', ['discipline_id'])
        op.create_index('ix_rule_applicabilities_topic_id', 'rule_applicabilities', ['topic_id'])

    # 4. rule_execution_dependencies
    if 'rule_execution_dependencies' not in existing_tables:
        op.create_table(
            'rule_execution_dependencies',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('rule_id', sa.String(36), sa.ForeignKey('rule_definitions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('depends_on_rule_id', sa.String(36), sa.ForeignKey('rule_definitions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('dependency_type', sa.String(50), nullable=False, server_default='requires_success'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('rule_id', 'depends_on_rule_id', name='uq_rule_dependency')
        )
        op.create_index('ix_rule_execution_dependencies_rule_id', 'rule_execution_dependencies', ['rule_id'])
        op.create_index('ix_rule_execution_dependencies_depends_on_rule_id', 'rule_execution_dependencies', ['depends_on_rule_id'])

    # 5. Alter rule_definitions
    if 'rule_definitions' in existing_tables:
        rule_def_cols = {col['name'] for col in inspector.get_columns('rule_definitions')}
        if 'rule_scope' not in rule_def_cols:
            op.add_column('rule_definitions', sa.Column('rule_scope', sa.String(50), nullable=False, server_default='specialty'))
        if 'execution_phase' not in rule_def_cols:
            op.add_column('rule_definitions', sa.Column('execution_phase', sa.Integer(), nullable=False, server_default='5'))
        if 'priority' not in rule_def_cols:
            op.add_column('rule_definitions', sa.Column('priority', sa.Integer(), nullable=False, server_default='100'))
        if 'enabled' not in rule_def_cols:
            op.add_column('rule_definitions', sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'))
        if 'source_status' not in rule_def_cols:
            op.add_column('rule_definitions', sa.Column('source_status', sa.String(30), nullable=False, server_default='approved'))
        if 'requires_data' not in rule_def_cols:
            op.add_column('rule_definitions', sa.Column('requires_data', sa.JSON(), nullable=False, server_default='[]'))
        if 'suggested_by_ai' not in rule_def_cols:
            op.add_column('rule_definitions', sa.Column('suggested_by_ai', sa.Boolean(), nullable=False, server_default='false'))
        if 'classification_confidence' not in rule_def_cols:
            op.add_column('rule_definitions', sa.Column('classification_confidence', sa.Float(), nullable=False, server_default='1.0'))
        if 'classification_rationale' not in rule_def_cols:
            op.add_column('rule_definitions', sa.Column('classification_rationale', sa.Text(), nullable=True))
        if 'applicable_document_types' not in rule_def_cols:
            op.add_column('rule_definitions', sa.Column('applicable_document_types', sa.JSON(), nullable=False, server_default='[]'))

    # 6. Alter review_runs
    if 'review_runs' in existing_tables:
        rr_cols = {col['name'] for col in inspector.get_columns('review_runs')}
        if 'discipline_id' not in rr_cols:
            op.add_column('review_runs', sa.Column('discipline_id', sa.String(36), sa.ForeignKey('review_disciplines.id', ondelete='SET NULL'), nullable=True))
            op.create_index('ix_review_runs_discipline_id', 'review_runs', ['discipline_id'])
        if 'topic_id' not in rr_cols:
            op.add_column('review_runs', sa.Column('topic_id', sa.String(36), sa.ForeignKey('review_topics.id', ondelete='SET NULL'), nullable=True))
            op.create_index('ix_review_runs_topic_id', 'review_runs', ['topic_id'])
        if 'execution_mode' not in rr_cols:
            op.add_column('review_runs', sa.Column('execution_mode', sa.String(30), nullable=False, server_default='production'))
        if 'requested_by' not in rr_cols:
            op.add_column('review_runs', sa.Column('requested_by', sa.String(100), nullable=False, server_default='user'))
        if 'requested_at' not in rr_cols:
            op.add_column('review_runs', sa.Column('requested_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
        if 'rule_count' not in rr_cols:
            op.add_column('review_runs', sa.Column('rule_count', sa.Integer(), nullable=False, server_default='0'))
        if 'document_count' not in rr_cols:
            op.add_column('review_runs', sa.Column('document_count', sa.Integer(), nullable=False, server_default='0'))
        if 'summary' not in rr_cols:
            op.add_column('review_runs', sa.Column('summary', sa.JSON(), nullable=False, server_default='{}'))

    # 7. review_run_documents
    if 'review_run_documents' not in existing_tables:
        op.create_table(
            'review_run_documents',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('review_run_id', sa.String(36), sa.ForeignKey('review_runs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('inclusion_reason', sa.String(100), nullable=False, server_default='user_selected'),
            sa.Column('document_role', sa.String(50), nullable=False, server_default='primary'),
            sa.Column('status', sa.String(30), nullable=False, server_default='included'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('review_run_id', 'document_id', name='uq_review_run_document')
        )
        op.create_index('ix_review_run_documents_review_run_id', 'review_run_documents', ['review_run_id'])
        op.create_index('ix_review_run_documents_document_id', 'review_run_documents', ['document_id'])

    # 8. review_run_steps
    if 'review_run_steps' not in existing_tables:
        op.create_table(
            'review_run_steps',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('review_run_id', sa.String(36), sa.ForeignKey('review_runs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('phase', sa.Integer(), nullable=False),
            sa.Column('phase_name', sa.String(100), nullable=False),
            sa.Column('step_type', sa.String(50), nullable=False),
            sa.Column('status', sa.String(30), nullable=False, server_default='queued'),
            sa.Column('input_summary', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('output_summary', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('error_summary', sa.Text(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        )
        op.create_index('ix_review_run_steps_review_run_id', 'review_run_steps', ['review_run_id'])

    # 9. Alter rule_executions
    if 'rule_executions' in existing_tables:
        re_cols = {col['name'] for col in inspector.get_columns('rule_executions')}
        if 'review_run_id' not in re_cols:
            op.add_column('rule_executions', sa.Column('review_run_id', sa.String(36), sa.ForeignKey('review_runs.id', ondelete='CASCADE'), nullable=True))
            op.create_index('ix_rule_executions_review_run_id', 'rule_executions', ['review_run_id'])
        if 'phase' not in re_cols:
            op.add_column('rule_executions', sa.Column('phase', sa.Integer(), nullable=False, server_default='5'))
        if 'evidence' not in re_cols:
            op.add_column('rule_executions', sa.Column('evidence', sa.JSON(), nullable=False, server_default='{}'))
        if 'not_evaluable_reason_code' not in re_cols:
            op.add_column('rule_executions', sa.Column('not_evaluable_reason_code', sa.String(50), nullable=True))
        if 'not_evaluable_reason_message' not in re_cols:
            op.add_column('rule_executions', sa.Column('not_evaluable_reason_message', sa.Text(), nullable=True))
        if 'missing_requirements' not in re_cols:
            op.add_column('rule_executions', sa.Column('missing_requirements', sa.JSON(), nullable=False, server_default='[]'))
        if 'recommended_action' not in re_cols:
            op.add_column('rule_executions', sa.Column('recommended_action', sa.Text(), nullable=True))
        if 'started_at' not in re_cols:
            op.add_column('rule_executions', sa.Column('started_at', sa.DateTime(), nullable=True))
        if 'completed_at' not in re_cols:
            op.add_column('rule_executions', sa.Column('completed_at', sa.DateTime(), nullable=True))

    # 10. Alter rule_findings
    if 'rule_findings' in existing_tables:
        rf_cols = {col['name'] for col in inspector.get_columns('rule_findings')}
        if 'rule_execution_id' not in rf_cols:
            op.add_column('rule_findings', sa.Column('rule_execution_id', sa.String(36), sa.ForeignKey('rule_executions.id', ondelete='SET NULL'), nullable=True))
            op.create_index('ix_rule_findings_rule_execution_id', 'rule_findings', ['rule_execution_id'])
        if 'navigation_context' not in rf_cols:
            op.add_column('rule_findings', sa.Column('navigation_context', sa.JSON(), nullable=False, server_default='{}'))

    # 11. review_reports
    if 'review_reports' not in existing_tables:
        op.create_table(
            'review_reports',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('review_run_id', sa.String(36), sa.ForeignKey('review_runs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('discipline_id', sa.String(36), sa.ForeignKey('review_disciplines.id', ondelete='SET NULL'), nullable=True),
            sa.Column('topic_id', sa.String(36), sa.ForeignKey('review_topics.id', ondelete='SET NULL'), nullable=True),
            sa.Column('report_name', sa.String(255), nullable=False),
            sa.Column('format', sa.String(20), nullable=False),
            sa.Column('artifact_path', sa.String(500), nullable=False),
            sa.Column('sha256', sa.String(64), nullable=False),
            sa.Column('status', sa.String(30), nullable=False, server_default='ready'),
            sa.Column('documents_snapshot', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('baseline_catalog_version', sa.String(50), nullable=True),
            sa.Column('stats_summary', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        )
        op.create_index('ix_review_reports_project_id', 'review_reports', ['project_id'])
        op.create_index('ix_review_reports_review_run_id', 'review_reports', ['review_run_id'])
        op.create_index('ix_review_reports_organization_id', 'review_reports', ['organization_id'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'review_reports' in existing_tables:
        op.drop_table('review_reports')

    if 'rule_findings' in existing_tables:
        rf_cols = {col['name'] for col in inspector.get_columns('rule_findings')}
        if 'navigation_context' in rf_cols:
            op.drop_column('rule_findings', 'navigation_context')
        if 'rule_execution_id' in rf_cols:
            op.drop_column('rule_findings', 'rule_execution_id')

    if 'rule_executions' in existing_tables:
        re_cols = {col['name'] for col in inspector.get_columns('rule_executions')}
        for col_name in ['completed_at', 'started_at', 'recommended_action', 'missing_requirements',
                         'not_evaluable_reason_message', 'not_evaluable_reason_code', 'evidence', 'phase', 'review_run_id']:
            if col_name in re_cols:
                op.drop_column('rule_executions', col_name)

    if 'review_run_steps' in existing_tables:
        op.drop_table('review_run_steps')

    if 'review_run_documents' in existing_tables:
        op.drop_table('review_run_documents')

    if 'review_runs' in existing_tables:
        rr_cols = {col['name'] for col in inspector.get_columns('review_runs')}
        for col_name in ['summary', 'document_count', 'rule_count', 'requested_at', 'requested_by',
                         'execution_mode', 'topic_id', 'discipline_id']:
            if col_name in rr_cols:
                op.drop_column('review_runs', col_name)

    if 'rule_definitions' in existing_tables:
        rd_cols = {col['name'] for col in inspector.get_columns('rule_definitions')}
        for col_name in ['applicable_document_types', 'classification_rationale', 'classification_confidence',
                         'suggested_by_ai', 'requires_data', 'source_status', 'enabled', 'priority',
                         'execution_phase', 'rule_scope']:
            if col_name in rd_cols:
                op.drop_column('rule_definitions', col_name)

    if 'rule_execution_dependencies' in existing_tables:
        op.drop_table('rule_execution_dependencies')

    if 'rule_applicabilities' in existing_tables:
        op.drop_table('rule_applicabilities')

    if 'review_topics' in existing_tables:
        op.drop_table('review_topics')

    if 'review_disciplines' in existing_tables:
        op.drop_table('review_disciplines')
