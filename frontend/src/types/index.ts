export type Discipline =
  | 'Arquitectura'
  | 'Estructuras'
  | 'Mecánica'
  | 'Eléctrica'
  | 'Instrumentación'
  | 'Piping'
  | 'architecture'
  | 'electrical'
  | 'structural'
  | 'plumbing'
  | 'hvac'
  | 'fire_safety'
  | 'general'
  | string;
export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type FindingStatus = 'open' | 'under_review' | 'accepted' | 'rejected_false_positive' | 'resolved';

export type DeliverableType =
  | 'plano_general'
  | 'plano_detalles'
  | 'plano_estructural'
  | 'memoria_calculo'
  | 'especificaciones_tecnicas'
  | 'mecanica_suelos'
  | 'cuadro_cargas'
  | 'plan_seguridad'
  | 'otro_entregable';

export type EvidenceReadinessStatus =
  | 'uploaded'
  | 'classified'
  | 'validated'
  | 'eligible_as_evidence'
  | 'rejected';

export type AuditVerdict = 'cumple' | 'no_cumple' | 'no_verificable' | 'no_aplica';

export type UnverifiableReason =
  | 'minor_missing'
  | 'insufficient_evidence'
  | 'blocked_by_missing_doc'
  | 'formal_rfi_required';

export interface DeliverableRequirement {
  id: string;
  stage: string;
  discipline: string;
  deliverable_type: DeliverableType;
  title: string;
  description?: string;
  is_mandatory: boolean;
  blocked_rule_codes: string[];
}

export interface DocumentDeliverableItem {
  id: string;
  project_id: string;
  document_id: string;
  deliverable_type: DeliverableType;
  readiness_status: EvidenceReadinessStatus;
  validation_notes?: string;
  classified_by: string;
  validated_at?: string;
  document_filename?: string;
  document_title?: string;
  created_at: string;
  updated_at: string;
}

export interface BlockedRuleInfo {
  rule_code: string;
  rule_name: string;
  discipline: string;
  blocked_by_deliverable_title: string;
  blocked_by_deliverable_type: DeliverableType;
  reason: UnverifiableReason;
  detail: string;
}

export interface CompletenessEvaluationItem {
  id: string;
  project_id: string;
  stage: string;
  completeness_percentage: number;
  is_gate_passed: boolean;
  total_required_count: number;
  eligible_count: number;
  missing_mandatory_count: number;
  missing_optional_count: number;
  blocked_rules_count: number;
  deliverables_matrix: Array<{
    requirement: DeliverableRequirement;
    provided_documents: Array<{
      document_id: string;
      document_filename: string;
      document_title: string;
      deliverable_type: DeliverableType;
      readiness_status: EvidenceReadinessStatus;
      is_eligible: boolean;
    }>;
    is_fulfilled: boolean;
    status: 'eligible' | 'pending_validation' | 'missing_mandatory' | 'missing_optional';
  }>;
  missing_deliverables: Array<{
    requirement_id: string;
    title: string;
    deliverable_type: DeliverableType;
    is_mandatory: boolean;
    blocked_rule_codes: string[];
  }>;
  blocked_rules: BlockedRuleInfo[];
  blocked_rule_codes?: string[];
  evaluated_at: string;
}

export type ObservationType =
  | 'technical_observation' // OBS
  | 'information_request'    // RFI
  | 'document_blocker'      // BLK
  | 'minor_missing';        // MIN

export type ObservationStatus =
  | 'draft'
  | 'issued'
  | 'answered'
  | 'provisioned'
  | 'validated'
  | 'closed'
  | 'rejected'
  | 'superseded';

export interface ObservationResponseItem {
  id: string;
  observation_id: string;
  author: string;
  author_role: string;
  response_text: string;
  attached_document_id?: string;
  created_at: string;
}

export interface AuditObservationItem {
  id: string;
  organization_id: string;
  project_id: string;
  stage: string;
  code: string;
  item_type: ObservationType;
  title: string;
  description: string;
  recommendation?: string;
  discipline: string;
  severity: Severity;
  status: ObservationStatus;

  rule_finding_id?: string;
  rule_id?: string;
  rule_code?: string;
  document_id?: string;
  document_filename?: string;
  sheet_id?: string;
  sheet_title?: string;
  review_run_id?: string;

  required_deliverable_type?: string;
  provisioned_document_id?: string;
  provisioned_document_filename?: string;
  resolution_notes?: string;

  issued_by: string;
  assigned_to?: string;
  issued_at?: string;
  answered_at?: string;
  provisioned_at?: string;
  closed_at?: string;

  history_trace: Array<{
    from_status?: string;
    to_status: string;
    action: string;
    author: string;
    notes?: string;
    timestamp: string;
    is_resolved?: boolean;
    verdict_after?: string;
    provisioned_filename?: string;
    rule_code?: string;
  }>;
  responses: ObservationResponseItem[];

  created_at: string;
  updated_at: string;
}

export interface DeltaReevaluationResult {
  observation_id: string;
  code: string;
  status_before: ObservationStatus;
  status_after: ObservationStatus;
  verdict_after: string;
  is_resolved: boolean;
  affected_rules_evaluated: string[];
  affected_sheets_evaluated: string[];
  message: string;
  trace_entry: any;
}

export type GlobalStageVerdict =
  | 'aprobable'
  | 'aprobable_con_observaciones'
  | 'parcial_incompleta'
  | 'no_aprobable_bloqueada';

export interface ConsolidatedStageReportItem {
  id?: string;
  project_id: string;
  project_name: string;
  project_code: string;
  stage: string;
  revision_number: number;
  title: string;
  global_stage_verdict: GlobalStageVerdict;
  verdict_rationale: string;
  issued_by: string;
  issued_at?: string;

  completeness: {
    completeness_percentage: number;
    is_gate_passed: boolean;
    total_required_count: number;
    eligible_count: number;
    missing_mandatory_count: number;
    missing_optional_count: number;
    blocked_rules_count: number;
    deliverables_matrix: Array<{
      requirement_id: string;
      title: string;
      deliverable_type: string;
      is_mandatory: boolean;
      readiness_status: string;
      provided_files_count: number;
      is_fulfilled: boolean;
      blocked_rule_codes: string[];
    }>;
    missing_deliverables: Array<any>;
    blocked_rules: Array<any>;
  };

  audit_verdicts: {
    cumple_count: number;
    no_cumple_count: number;
    no_verificable_count: number;
    no_aplica_count: number;
    total_rules_evaluated: number;
    by_discipline: Record<string, Record<string, number>>;
    verdicts_list: Array<{
      rule_code: string;
      rule_name: string;
      category: string;
      discipline: string;
      verdict: 'cumple' | 'no_cumple' | 'no_verificable' | 'no_aplica';
      unverifiable_reason?: string;
      findings_count: number;
      sheet_code?: string;
      document_filename?: string;
    }>;
  };

  observations: {
    total_obs: number;
    open_obs: number;
    closed_obs: number;
    critical_obs: number;
    high_obs: number;
    medium_obs: number;
    low_obs: number;
    total_rfi: number;
    open_rfi: number;
    answered_rfi: number;
    closed_rfi: number;
    total_blk: number;
    active_blk: number;
    resolved_blk: number;
    total_min: number;
    items: Array<{
      id: string;
      code: string;
      item_type: ObservationType;
      title: string;
      discipline: string;
      severity: string;
      status: ObservationStatus;
      rule_code?: string;
      document_filename?: string;
      provisioned_filename?: string;
      responses_count: number;
    }>;
  };

  delta_evolution: {
    previous_snapshot_id?: string;
    previous_revision_number?: number;
    resolved_since_last_rev: Array<any>;
    new_since_last_rev: Array<any>;
    unblocked_rules_since_last_rev: Array<string>;
    status_changes: Array<{
      id: string;
      code: string;
      from: string;
      to: string;
      notes: string;
    }>;
    summary_narrative: string;
  };

  artifact_pdf_path?: string;
  artifact_json_path?: string;
  manifest_hash?: string;
  is_live_preview: boolean;
}

export interface ProjectStageReportSnapshotSummary {
  id: string;
  project_id: string;
  stage: string;
  revision_number: number;
  title: string;
  global_stage_verdict: GlobalStageVerdict;
  completeness_percentage: number;
  open_obs_count: number;
  open_rfi_count: number;
  active_blk_count: number;
  issued_by: string;
  created_at: string;
}

export type SourceType = 'analysis_document' | 'template_document' | 'symbol_reference' | 'normative_document' | 'web_normative_source';
export type SourceOrigin = 'local_upload' | 'web_scrape' | 'api_sync' | 'manual_entry';
export type ApprovalStatus = 'pending_review' | 'approved' | 'rejected' | 'not_required';
export type MemoryTarget = 'document_memory' | 'template_memory' | 'normative_memory';

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'retrying' | 'awaiting_review';
export type ReviewTaskStatus = 'open' | 'assigned' | 'in_review' | 'approved' | 'corrected' | 'rejected' | 'dismissed' | 'expired';

export interface ProcessingJobItem {
  id: string;
  job_type: string;
  target_type: string;
  target_id: string;
  project_id?: string;
  parent_job_id?: string;
  pipeline_name: string;
  pipeline_version: string;
  requested_by: string;
  status: JobStatus;
  priority: number;
  progress_percent: number;
  current_stage: string;
  input_payload?: Record<string, any>;
  result_summary?: Record<string, any>;
  error_code?: string;
  error_message?: string;
  retry_count: number;
  max_retries: number;
  queued_at: string;
  started_at?: string;
  completed_at?: string;
  failed_at?: string;
  cancelled_at?: string;
  created_at: string;
  updated_at: string;
  events?: JobEventItem[];
}

export interface JobEventItem {
  id: string;
  job_id: string;
  event_type: string;
  status_before?: string;
  status_after?: string;
  stage?: string;
  message?: string;
  details?: Record<string, any>;
  actor_type: string;
  actor_id?: string;
  created_at: string;
}

export interface ConfidencePolicyItem {
  id: string;
  name: string;
  applies_to: string;
  document_type?: string;
  discipline?: string;
  field_name?: string;
  risk_level: string;
  auto_accept_threshold: number;
  review_threshold: number;
  action_below_review_threshold: string;
  is_active: boolean;
  version: string;
  description?: string;
}

export interface ReviewDecisionItem {
  id: string;
  review_task_id: string;
  decision: string;
  original_value: Record<string, any>;
  corrected_value?: Record<string, any>;
  reviewer: string;
  reason_code?: string;
  notes?: string;
  created_at: string;
}

export interface ReviewTaskItem {
  id: string;
  project_id?: string;
  source_asset_id?: string;
  document_id?: string;
  sheet_id?: string;
  job_id?: string;
  task_type: string;
  priority: string;
  status: ReviewTaskStatus;
  reason_code: string;
  reason_message: string;
  confidence?: number;
  evidence_refs?: Record<string, any>;
  payload?: Record<string, any>;
  assigned_to?: string;
  created_at: string;
  due_at?: string;
  resolved_at?: string;
  decisions?: ReviewDecisionItem[];
}

export interface SourceAssetItem {
  id: string;
  organization_id?: string;
  project_id?: string;
  source_type: SourceType;
  source_origin: SourceOrigin;
  document_type?: string;
  discipline: Discipline;
  title: string;
  description?: string;
  file_path?: string;
  original_filename?: string;
  file_size_bytes?: number;
  source_url?: string;
  sha256?: string;
  mime_type: string;
  version: string;
  status: string;
  approval_status: ApprovalStatus;
  linked_memory_target: MemoryTarget;
  owner: string;
  approval_notes?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  metadata_payload?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface SourceDependenciesInfo {
  source_id: string;
  title: string;
  has_file: boolean;
  file_path?: string;
  original_filename?: string;
  file_size_bytes?: number;
  extractions_count: number;
  rule_documents_count: number;
  can_hard_delete: boolean;
  warnings: string[];
}

export interface SourceDeleteResult {
  source_id: string;
  deleted: boolean;
  mode: 'hard_delete' | 'soft_delete_archived';
  file_removed: boolean;
  message: string;
}

export interface ResearchSourceItem {
  id: string;
  title: string;
  url: string;
  domain: string;
  snippet?: string;
  retrieved_at: string;
  reliability_score: number;
}

export interface ResearchRuleItem {
  id: string;
  item_type: string;
  item_nature: ItemNatureType;
  title: string;
  code_or_number?: string;
  description?: string;
  content_text?: string;
  source_reference?: string;
  governance_note?: string;
  validation_status: string;
  created_at: string;
}

export interface ResearchResultItem {
  id: string;
  query_id: string;
  source_extraction_id?: string;
  title: string;
  executive_summary?: string;
  total_items_found: number;
  metadata_info?: Record<string, any>;
  sources: ResearchSourceItem[];
  items: ResearchRuleItem[];
  created_at: string;
}

export interface ResearchQueryItem {
  id: string;
  organization_id: string;
  project_id?: string;
  search_prompt: string;
  discipline: string;
  document_type: string;
  authority?: string;
  focus_areas: string[];
  status: string;
  created_at: string;
  updated_at: string;
  results_count: number;
  total_sources_count: number;
  total_items_count: number;
}

export interface ResearchQueryDetail {
  id: string;
  organization_id: string;
  project_id?: string;
  search_prompt: string;
  discipline: string;
  document_type: string;
  authority?: string;
  focus_areas: string[];
  status: string;
  metadata_payload?: Record<string, any>;
  results: ResearchResultItem[];
  created_at: string;
  updated_at: string;
}

export type ProjectStatus = 'active' | 'archived' | 'deleting' | 'deleted' | 'failed_cleanup';

export interface Project {
  id: string;
  organization_id?: string;
  code: string;
  name: string;
  description?: string;
  client_name?: string;
  discipline: Discipline;
  discipline_scope?: string[];
  stage?: string;
  project_type?: string;
  status?: ProjectStatus | string;
  cleanup_status?: string;
  cleanup_error?: string;
  deletion_job_id?: string;
  settings?: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  versions?: ProjectVersion[];
  documents_count?: number;
  sheets_count?: number;
  findings_count?: number;
}

export interface ProjectDeletionImpact {
  project_id: string;
  project_code: string;
  documents: number;
  stored_files: number;
  extractions: number;
  evaluation_runs: number;
  findings: number;
  reports: number;
  symbol_occurrences: number;
  can_hard_delete: boolean;
  blocking_reasons: string[];
}

export interface ProjectClearContentRequest {
  confirmation_code: string;
  reason?: string;
  acknowledge_data_loss?: boolean;
}

export interface ProjectDeleteConfirmedRequest {
  confirmation_code: string;
  mode?: 'hard_delete' | 'anonymize';
  reason?: string;
  acknowledge_data_loss?: boolean;
}

export interface ProjectLifecycleResult {
  success: boolean;
  message: string;
  project_id: string;
  status: string;
  files_deleted?: number;
  records_affected?: number;
  cleanup_status?: string;
  error?: string;
}

export interface ProjectVersion {
  id: string;
  project_id: string;
  version_tag: string;
  description?: string;
  status: string;
  created_at: string;
}

export interface ExtractedTextItem {
  id: string;
  sheet_id: string;
  region_id?: string;
  text: string;
  clean_text?: string;
  bbox: [number, number, number, number];
  bbox_normalized: [number, number, number, number];
  confidence: number;
  font_name?: string;
  font_size?: number;
  angle: number;
  source: string;
  created_at?: string;
}

export interface SheetRegionItem {
  id: string;
  sheet_id: string;
  region_type: string;
  polygon_points: [number, number][];
  bbox: [number, number, number, number];
  bbox_normalized: [number, number, number, number];
  confidence: number;
  detection_method: string;
  source_version: string;
  attributes?: Record<string, any>;
  created_at?: string;
}

export interface TitleBlockExtractionItem {
  id: string;
  sheet_id: string;
  template_id?: string;
  match_score: number;
  extraction_status: string;
  sheet_code?: string;
  sheet_title?: string;
  revision?: string;
  scale_text?: string;
  date_text?: string;
  project_name?: string;
  discipline?: string;
  drawn_by?: string;
  checked_by?: string;
  approved_by?: string;
  matched_anchors: string[];
  unmatched_required_fields: string[];
  raw_fields?: Record<string, any>;
  created_at?: string;
}

export interface ExtractedTableCellItem {
  id: string;
  table_id: string;
  row_index: number;
  column_index: number;
  row_span: number;
  col_span: number;
  text: string;
  normalized_text?: string;
  confidence: number;
  bbox: [number, number, number, number];
  bbox_normalized: [number, number, number, number];
  is_header: boolean;
  source_text_refs: string[];
  created_at: string;
}

export interface ExtractedTableItem {
  id: string;
  document_id: string;
  sheet_id?: string;
  region_id?: string;
  table_type: string;
  title?: string;
  bbox: [number, number, number, number];
  bbox_normalized: [number, number, number, number];
  row_count: number;
  column_count: number;
  confidence: number;
  extraction_status: string;
  source_engine: string;
  source_version: string;
  raw_structure: Record<string, any>;
  cells?: ExtractedTableCellItem[];
  created_at: string;
  updated_at: string;
}

export interface DetectedSymbolItem {
  id: string;
  document_id: string;
  sheet_id: string;
  region_id?: string;
  symbol_type: string;
  discipline: Discipline | string;
  bbox: [number, number, number, number];
  bbox_normalized: [number, number, number, number];
  polygon_points?: [number, number][];
  confidence: number;
  detection_status: string;
  source_engine: string;
  source_version: string;
  source_asset_template_id?: string;
  matched_library_entry_id?: string;
  attributes?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface SymbolSummaryItem {
  symbol_type: string;
  discipline: string;
  count: number;
  average_confidence: number;
}

export interface SheetSymbolsSummaryResponse {
  sheet_id: string;
  total_symbols: number;
  by_category: SymbolSummaryItem[];
}

export interface DocumentSheet {
  id: string;
  sheet_number: number;
  sheet_code?: string;
  title?: string;
  scale?: string;
  revision?: string;
  width_px: number;
  height_px: number;
  width_mm?: number;
  height_mm?: number;
  dpi: number;
  raster_image_path?: string;
  thumbnail_path?: string;
  texts_count?: number;
  title_block_extraction?: TitleBlockExtractionItem;
  tables?: ExtractedTableItem[];
  symbols?: DetectedSymbolItem[];
}

export interface ProjectDocumentView {
  id: string;
  project_id: string;
  organization_id: string;
  filename: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  document_type: 'pid' | 'legend' | 'specification' | 'unknown' | string;
  discipline: string;
  storage_status: 'stored' | 'failed' | 'pending_cleanup' | string;
  processing_status: 'uploaded' | 'queued' | 'processing' | 'processed' | 'failed' | 'cancelled' | string;
  processing_error_summary?: string | null;
  uploaded_at: string;
  uploaded_by?: string | null;
  page_count?: number | null;
  can_process: boolean;
  can_retry: boolean;
  can_open: boolean;
  sheets_count: number;
  sheets?: DocumentSheet[];
  context_metadata?: Record<string, any>;
}

export type UnifiedDocument = ProjectDocumentView;

export interface DocumentItem {
  id: string;
  document_id?: string;
  project_id: string;
  organization_id?: string;
  filename: string;
  original_filename?: string;
  file_hash_sha256?: string;
  sha256?: string;
  file_size_bytes?: number;
  size_bytes?: number;
  mime_type?: string;
  content_type?: string;
  page_count?: number;
  status: string;
  processing_status?: string;
  storage_status?: string;
  error_message?: string;
  processing_error_summary?: string | null;
  created_at?: string;
  uploaded_at?: string;
  upload_timestamp?: string;
  discipline?: string;
  document_type?: string;
  warnings?: string[];
  sheets?: DocumentSheet[];
  sheets_count?: number;
  can_process?: boolean;
  can_retry?: boolean;
  can_open?: boolean;
}

export interface BatchFileResultItem {
  filename: string;
  status: 'uploaded' | 'ready' | 'already_exists' | 'failed' | string;
  document_id?: string;
  file_size_bytes: number;
  mime_type?: string;
  page_count: number;
  sheets_count: number;
  error_message?: string;
}

export interface BatchUploadResponse {
  project_id: string;
  total_files: number;
  successful_count: number;
  duplicated_count: number;
  failed_count: number;
  documents: DocumentItem[];
  results: BatchFileResultItem[];
}


export interface DocumentImpact {
  document_id: string;
  filename: string;
  project_id: string;
  organization_id?: string;
  status: string;
  file_size_bytes: number;
  sheets_count: number;
  ocr_count: number;
  region_count: number;
  title_block_count: number;
  table_count: number;
  symbol_count: number;
  findings_count: number;
  severity_breakdown: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    info: number;
  };
  trace_count: number;
  review_task_count: number;
  raster_files_count: number;
  raw_file_exists: boolean;
}


export interface FindingResolutionItem {
  id: string;
  finding_id: string;
  resolution_type: string;
  resolved_by: string;
  notes?: string;
  corrected_value?: Record<string, any>;
  created_at: string;
}

export interface RuleFindingItem {
  id: string;
  document_id: string;
  sheet_id?: string;
  rule_id?: string;
  rule_code: string;
  rule_name: string;
  category: string;
  severity: Severity | string;
  status: FindingStatus | string;
  confidence: number;
  finding_type: string;
  title: string;
  description: string;
  recommendation?: string;
  evidence_refs: Record<string, any>;
  expected_value?: any;
  observed_value?: any;
  delta?: any;
  source_trace_ids?: string[];
  review_task_id?: string;
  bbox?: [number, number, number, number];
  resolutions?: FindingResolutionItem[];
  created_at: string;
  updated_at: string;
}

export interface RuleDefinitionItem {
  id: string;
  code: string;
  name: string;
  category: string;
  discipline: Discipline | string;
  severity_default: Severity | string;
  description: string;
  input_requirements?: Record<string, any>;
  rule_logic_type: string;
  is_active: boolean;
  version: string;
  created_at: string;
  updated_at: string;
}

export interface RuleEvaluationSummaryResponse {
  document_id?: string;
  sheet_id?: string;
  total_rules_evaluated: number;
  passed_count: number;
  failed_count: number;
  warning_count: number;
  insufficient_evidence_count: number;
  findings_generated: number;
  by_severity: Record<string, number>;
}

export interface ReviewRun {
  id: string;
  project_id: string;
  run_name: string;
  status: string;
  rules_applied_count: number;
  findings_count: number;
  execution_time_sec: number;
  summary_stats: Record<string, any>;
  created_at: string;
  findings?: RuleFindingItem[];
}

export interface MemoriesStats {
  document_memory: {
    documents_count: number;
    sheets_count: number;
  };
  normative_memory: {
    standards_count: number;
    clauses_count: number;
  };
  template_memory: {
    title_block_templates_count: number;
    symbol_libraries_count: number;
    ontologies_count: number;
  };
  decision_memory: {
    review_runs_count: number;
    findings_count: number;
    human_feedbacks_count: number;
  };
}

export interface EvidenceManifestItem {
  id: string;
  report_id: string;
  manifest_json: {
    manifest_version: string;
    report_id: string;
    report_type: string;
    timestamp_utc: string;
    engine_version: string;
    integrity_algorithm: string;
    files_count: number;
    files: Array<{
      path: string;
      sha256: string;
      size_bytes: number;
    }>;
  };
  sha256_bundle?: string;
  created_at: string;
}

export interface AuditReportItem {
  id: string;
  document_id: string;
  sheet_id?: string;
  report_type: string;
  report_scope: string;
  status: string;
  generated_by: string;
  source_rule_execution_ids: string[];
  source_finding_ids: string[];
  summary: {
    total_findings: number;
    by_severity: Record<string, number>;
    by_status: Record<string, number>;
    rules_evaluated_count: number;
  };
  artifact_pdf_path?: string;
  artifact_json_path?: string;
  artifact_bundle_path?: string;
  manifest_hash?: string;
  manifest?: EvidenceManifestItem;
  created_at: string;
  updated_at: string;
}

export interface PipelineStageRunItem {
  id: string;
  pipeline_run_id: string;
  stage_name: string;
  stage_order: number;
  status: string;
  job_id?: string;
  started_at?: string;
  completed_at?: string;
  result_summary: Record<string, any>;
  error_message?: string;
  created_at: string;
}

export interface ReviewPipelineRunItem {
  id: string;
  scope_type: string;
  scope_id: string;
  pipeline_version: string;
  requested_by: string;
  status: string;
  current_stage: string;
  progress_percent: number;
  summary: Record<string, any>;
  final_report_id?: string;
  started_at?: string;
  completed_at?: string;
  failed_at?: string;
  cancelled_at?: string;
  stages?: PipelineStageRunItem[];
  created_at: string;
  updated_at: string;
}

export type UserRole = 'admin' | 'audit_lead' | 'reviewer' | 'contributor' | 'viewer';

export interface UserProfile {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface UserMembership {
  membership_id: string;
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  role: UserRole;
  status: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
  user: UserProfile;
  active_organization_id: string;
  active_role: UserRole;
  memberships: UserMembership[];
}

export interface OrganizationItem {
  id: string;
  name: string;
  slug: string;
  status: string;
  settings: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EvaluationDatasetItem {
  id: string;
  organization_id?: string;
  name: string;
  description?: string;
  dataset_type: 'golden' | 'regression' | 'benchmark' | 'pilot';
  discipline: string;
  version: string;
  status: 'draft' | 'active' | 'frozen' | 'archived';
  source_policy: 'consented' | 'anonymized' | 'synthetic' | 'internal';
  snapshot_manifest_hash?: string;
  frozen_at?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  samples_count?: number;
}

export interface EvaluationSampleItem {
  id: string;
  dataset_id: string;
  source_asset_id?: string;
  document_id?: string;
  sheet_id?: string;
  sample_key: string;
  discipline: string;
  drawing_type: string;
  source_checksum: string;
  split: 'test' | 'holdout' | 'validation';
  annotation_status: 'pending' | 'in_progress' | 'reviewed' | 'approved' | 'rejected';
  approved_by?: string;
  approved_at?: string;
  metadata_json: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface AnnotationSetItem {
  id: string;
  sample_id: string;
  annotation_type: 'ocr' | 'layout' | 'title_block' | 'table' | 'symbol' | 'rule_finding';
  schema_version: string;
  status: 'draft' | 'submitted' | 'reviewed' | 'approved' | 'superseded';
  annotator_id?: string;
  reviewer_id?: string;
  source: string;
  payload: Record<string, any>;
  superseded_by_id?: string;
  created_at: string;
  reviewed_at?: string;
  approved_at?: string;
}

export interface EvaluationMetricItem {
  id: string;
  evaluation_run_id: string;
  category: 'perceptual' | 'decisional';
  component: string;
  metric_name: string;
  metric_value: number;
  metric_unit: string;
  scope: Record<string, any>;
  confidence_interval?: Record<string, any>;
  sample_count: number;
  created_at: string;
}

export interface EvaluationRunItem {
  id: string;
  dataset_id: string;
  dataset_version: string;
  pipeline_version: string;
  model_versions: Record<string, any>;
  rule_pack_version: string;
  split_evaluated: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  started_at?: string;
  completed_at?: string;
  config: Record<string, any>;
  summary: Record<string, any>;
  artifact_paths: Record<string, any>;
  created_by: string;
  created_at: string;
  metrics?: EvaluationMetricItem[];
}

export interface EngineDefinitionItem {
  id: string;
  category: string;
  provider: string;
  model_name: string;
  version: string;
  engine_type: 'local' | 'open_source' | 'api_cloud' | 'paid_saas';
  cost_tier: 'gratis' | 'pago' | 'mixto';
  status: 'active' | 'inactive' | 'experimental' | 'fallback';
  is_active: boolean;
  is_installed: boolean;
  required_credentials: string[];
  has_credentials: boolean;
  disciplines: string[];
  description: string;
  notes?: string;
  parameters: Record<string, any>;
  latency_ms?: number;
  last_tested?: string;
  last_error?: string | null;
}

export interface EnginesSummaryResponse {
  total_engines: number;
  free_engines: number;
  paid_engines: number;
  mixed_engines: number;
  categories: Record<string, {
    total_engines: number;
    active_engine_id?: string;
    active_engine_name: string;
    active_provider?: string;
    active_type?: string;
    active_cost?: string;
  }>;
}

export interface ManualAnnotation {
  id: string;
  organization_id: string;
  project_id: string;
  document_id: string;
  sheet_id: string;
  user_id?: string;
  bbox_normalized: [number, number, number, number];
  bbox_pixels?: [number, number, number, number];
  crop_image_path?: string;
  element_type: 'symbol' | 'table' | 'layout_region' | 'text_note' | 'title_block' | 'legend' | 'view_elevation_plan' | 'stamp_signature' | 'diagram_sketch' | 'other';
  name: string;
  description?: string;
  ocr_text?: string;
  discipline: string;
  category?: string;
  confidence: number;
  tags: string[];
  status: string;
  extra_metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface CropOcrResult {
  text: string;
  confidence: number;
  engine_used: string;
  line_count: number;
}

export interface KnowledgeLibraryEntry {
  id: string;
  organization_id: string;
  source_annotation_id?: string;
  entry_type: string;
  name: string;
  description?: string;
  discipline: string;
  crop_image_path?: string;
  canonical_text?: string;
  tags: string[];
  is_verified: boolean;
  created_by_user_id?: string;
  status: string;
  extra_metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface ActiveLearningPromotion {
  id: string;
  organization_id: string;
  knowledge_entry_id?: string;
  manual_annotation_id?: string;
  target_engine: string;
  dataset_split: string;
  crop_image_path?: string;
  label: string;
  ground_truth_text?: string;
  ground_truth_bbox?: number[];
  promoted_by_user_id?: string;
  status: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

// =========================================================
// INTAKE EXTRACTIONS & MOTOR DE REGLAS
// =========================================================

export type ExtractedItemType =
  | 'rule'
  | 'article'
  | 'chapter'
  | 'table'
  | 'image'
  | 'figure'
  | 'symbol'
  | 'simbolo'
  | 'foto'
  | 'imagen'
  | 'tabla'
  | 'figura'
  | 'sello'
  | 'firma'
  | 'leyenda'
  | 'vineta'
  | 'otro'
  | 'text_note'
  | 'definition'
  | 'procedure'
  | 'restriction'
  | 'requirement'
  | 'other';

export type ItemNatureType =
  | 'official_rule'
  | 'proposed_rule'
  | 'support_research'
  | 'concept'
  | 'reference';

export interface SourceDocumentPage {
  page_number: number;
  image_url: string;
  width_px: number;
  height_px: number;
  width_pt: number;
  height_pt: number;
  text_preview?: string;
}

export interface SourceDocumentPagesResponse {
  source_id: string;
  title: string;
  document_type: string;
  discipline: string;
  total_pages: number;
  file_exists: boolean;
  mime_type: string;
  pages: SourceDocumentPage[];
}

export interface PageCropResponse {
  source_id: string;
  page_number: number;
  bbox: number[];
  crop_image_url: string;
  crop_image_base64?: string;
  ocr_text?: string;
  width_px: number;
  height_px: number;
}

export interface RuleSummarizeResponse {
  rule_code: string;
  rule_statement: string;
  summary: string;
  discipline: string;
  item_nature: string;
  extracted_parameters: Record<string, any>;
}

export interface WebCitation {
  title: string;
  url: string;
  domain: string;
  snippet?: string;
  retrieved_at?: string;
}

export interface FieldProvenanceEntry {
  original_raw?: string;
  ocr_extracted?: string;
  suggested_value?: string;
  suggestion_source?: string;
  suggestion_confidence?: number;
  accepted_value?: string;
  accepted_from?: 'original_raw' | 'ocr_extracted' | 'suggested_value' | 'manual_edited' | 'hybrid_edited' | string;
  updated_by?: string;
  updated_at?: string;
}

export interface ExtractionItemsSummaryStats {
  total_items: number;
  reviewed_count: number;
  pending_count: number;
  rejected_count: number;
  complete_count: number;
  partial_count: number;
  missing_data_count: number;
  web_suggested_count: number;
  by_item_type: Record<string, number>;
  by_completeness: Record<string, number>;
  by_review_status: Record<string, number>;
}

export interface ExtractedItem {
  id: string;
  extraction_id: string;
  item_type: ExtractedItemType;
  candidate_type?: string;
  title: string;
  code_or_number?: string;
  description?: string;
  content_text?: string;
  derived_text?: string;
  ocr_text?: string;
  caption_or_context?: string;
  disclaimer_notes?: string;
  crop_image_path?: string;
  bbox_normalized: number[];
  page_number: number;
  discipline?: string;
  source_asset_id?: string;
  parent_item_id?: string;
  is_derived?: boolean;
  split_mode?: string;
  evidence_references?: string[];
  technical_parameters?: Record<string, any>;
  target_destination: 'rules_engine' | 'knowledge_base' | 'both';
  review_status: 'draft' | 'editado' | 'por_confirmar' | 'validada' | 'eliminado' | 'to_confirm' | 'accepted' | 'rejected';
  
  // Deduplicación contra Motor de Reglas QA/QC
  duplicate_status?: 'no_match' | 'exact_match_existing_rule' | 'likely_duplicate_existing_rule' | 'related_existing_rule' | string;
  best_match_rule_id?: string;
  best_match_rule_code?: string;
  best_match_title?: string;
  best_match_discipline?: string;
  duplicate_reason?: string;
  duplicate_confidence?: number;
  blocked_from_acceptance?: boolean;

  // Estado de Completitud y Enriquecimiento Asistido (Multimodal)
  completeness_status?: 'complete' | 'partial' | 'missing_data' | 'web_suggested' | string;
  enrichment_status?: 'not_enriched' | 'suggestion_found' | 'manual_completed' | string;
  requires_validation?: boolean;
  enriched_from_web?: boolean;
  enrichment_method?: string;
  match_confidence?: number;
  suggested_title?: string;
  suggested_description?: string;
  suggested_function?: string;
  suggested_source_url?: string;
  suggested_source_label?: string;

  // Trazabilidad y Linaje Granular por Campo (Field Provenance)
  field_provenance?: Record<string, FieldProvenanceEntry>;

  structured_matrix?: Record<string, any>;
  structured_table?: any;
  structured_symbol?: any;
  structured_equipment?: any;
  structured_rule_premise?: any;

  validated_at?: string;
  validated_by?: string;
  source_origin: 'document' | 'web';
  source_reference?: string;
  item_nature: ItemNatureType;
  governance_note?: string;
  metadata_payload?: Record<string, any>;
  source_fields?: Record<string, any>;
  translated_fields?: Record<string, any>;
  effective_fields?: Record<string, any>;
  source_language?: string;
  target_language?: string;
  translation_status?: string;
  presentation_language?: string;
  occurrences?: SymbolOccurrenceItem[];
  occurrences_count?: number;
  reading_orientation?: string;
  orientation?: string;
  orientation_confidence?: number;
  orientation_reason?: string;
  inner_drawing_bbox?: number[];
  requires_human_review?: boolean;
  content_class?: string;
  graphic_classification?: string;
  grid_source?: string;
  grid_confidence?: number;
  physical_grid_detected?: boolean;
  geometric_confidence?: number;
  cell_bbox?: number[];
  symbol_crop_bbox?: number[];
  boundary_evidence?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface ItemContextResponse {
  item_id: string;
  extraction_id: string;
  source_asset_id?: string;
  source_title: string;
  document_type: string;
  discipline: string;
  page_number: number;
  total_pages: number;
  bbox_normalized: number[];
  crop_image_path?: string;
  page_image_url?: string;
  file_url?: string;
  page_text_preview?: string;
  item_type: string;
  candidate_type?: string;
  title: string;
  code_or_number?: string;
  description?: string;
  content_text?: string;
  ocr_text?: string;
  caption_or_context?: string;
  technical_parameters: Record<string, any>;
  source_fields?: Record<string, any>;
  translated_fields?: Record<string, any>;
  effective_fields?: Record<string, any>;
  source_language?: string;
  target_language?: string;
  translation_status?: string;
  presentation_language?: string;
  review_status: string;
  completeness_status: string;
  enrichment_status: string;
  requires_validation: boolean;
  enriched_from_web: boolean;
  enrichment_method?: string;
  match_confidence: number;
  suggested_title?: string;
  suggested_description?: string;
  suggested_function?: string;
  suggested_source_url?: string;
  suggested_source_label?: string;
  source_origin?: string;
  source_reference?: string;
  web_source_url?: string;
  web_snapshot_url?: string;
  dom_hint?: string;
  duplicate_status?: string;
  duplicate_reason?: string;
}

export interface CandidateEnrichmentRequest {
  candidate_type?: string;
  title?: string;
  caption_or_context?: string;
  ocr_text?: string;
  discipline?: string;
  page_number?: number;
  document_title?: string;
  force_web_search?: boolean;
  presentation_language?: string;
  source_language?: string;
  target_language?: string;
  source_fields?: Record<string, any>;
  translated_fields?: Record<string, any>;
  effective_fields?: Record<string, any>;
}

export interface CandidateEnrichmentResponse {
  item_id?: string;
  enrichment_status: 'suggestion_found' | 'manual_required' | 'not_enriched' | string;
  completeness_status: 'complete' | 'partial' | 'missing_data' | 'web_suggested' | string;
  match_confidence: number;
  suggested_title?: string;
  suggested_description?: string;
  suggested_function?: string;
  suggested_source_label?: string;
  suggested_source_url?: string;
  enrichment_method: string;
  requires_validation: boolean;
  enriched_from_web: boolean;
  technical_properties: Record<string, any>;
  message: string;
  presentation_language?: string;
  effective_fields?: Record<string, any>;
}

export interface RegionOcrResponse {
  page_number: number;
  bbox: number[];
  extracted_text: string;
  target_field: string;
  confidence: number;
}

export interface SupportingKnowledgeItem {
  id: string;
  organization_id: string;
  project_id?: string;
  source_asset_id?: string;
  source_extraction_id?: string;
  extracted_item_id?: string;
  item_type: ExtractedItemType;
  title: string;
  code_or_number?: string;
  description?: string;
  discipline: string;
  page_number: number;
  bbox_normalized: number[];
  crop_image_path?: string;
  ocr_text?: string;
  structured_matrix?: Record<string, any>;
  status: string;
  validated_by: string;
  validated_at: string;
  metadata_payload?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface SourceExtraction {
  id: string;
  organization_id: string;
  project_id?: string;
  source_asset_id?: string;
  extraction_mode: 'ai_document' | 'ai_web_research' | 'without_ai' | 'with_ai';
  source_origin: 'document' | 'web';
  search_query?: string;
  search_citations?: WebCitation[];
  title: string;
  document_type: string;
  authority?: string;
  discipline: string;
  source_file_path?: string;
  source_url?: string;
  status: 'draft' | 'extracting' | 'extracted' | 'reviewed' | 'incorporated' | 'archived';
  summary?: string;
  total_items: number;
  metadata_info?: Record<string, any>;
  items?: ExtractedItem[];
  created_at: string;
  updated_at: string;
}

export interface RuleDocumentItem {
  id: string;
  rule_document_id: string;
  extracted_item_id?: string;
  item_type: string;
  title: string;
  code_or_number?: string;
  description?: string;
  content_text?: string;
  ocr_text?: string;
  crop_image_path?: string;
  target_destination: string;
  status: string;
  source_origin?: string;
  source_reference?: string;
  item_nature?: string;
  metadata_payload?: Record<string, any>;
  created_at: string;
}

export interface RuleDocument {
  id: string;
  organization_id: string;
  project_id?: string;
  source_extraction_id?: string;
  source_asset_id?: string;
  title: string;
  description?: string;
  document_type: string;
  source_origin: 'con_ia_documento' | 'con_ia_web' | 'sin_ia' | string;
  authority?: string;
  discipline: string;
  version: string;
  status: 'active' | 'draft' | 'confirmado' | 'promovido_baseline' | 'archived' | string;
  items_count: number;
  rules_count: number;
  tables_count: number;
  images_count: number;
  symbols_count?: number;
  metadata_info?: Record<string, any>;
  items?: RuleDocumentItem[];
  created_at: string;
  updated_at: string;
}

export interface DocumentOcrPage {
  page_number: number;
  text_content: string;
  confidence: number;
}

export interface DocumentOcrResult {
  total_pages: number;
  pages: DocumentOcrPage[];
  full_text: string;
}

export type KnowledgeDomain =
  | 'normative_knowledge'
  | 'rule_knowledge'
  | 'deliverable_knowledge'
  | 'guide_document_knowledge'
  | 'review_knowledge'
  | 'observation_rfi_knowledge'
  | 'project_knowledge'
  | 'feedback_learning_knowledge';

export type KnowledgeStatus =
  | 'draft'
  | 'extracted'
  | 'reviewed'
  | 'validated'
  | 'approved_for_reuse'
  | 'superseded'
  | 'archived'
  | 'rejected';

export interface KnowledgeChunkDTO {
  id: string;
  knowledge_item_id: string;
  chunk_index: number;
  chunk_title?: string;
  chunk_text: string;
  token_count: number;
  metadata_payload?: Record<string, any>;
  embedding_json?: number[];
  created_at: string;
}

export interface KnowledgeItemSummaryDTO {
  id: string;
  organization_id: string;
  project_id?: string;
  domain: KnowledgeDomain;
  item_type: string;
  title: string;
  summary?: string;
  discipline: string;
  stage?: string;
  status: KnowledgeStatus;
  is_active_for_reuse: boolean;
  confidence_score: number;
  version_number: number;
  parent_item_id?: string;
  author: string;
  origin_type: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface KnowledgeItemDetailDTO extends KnowledgeItemSummaryDTO {
  content_text: string;
  structured_payload: Record<string, any>;
  valid_from: string;
  valid_until?: string;
  source_asset_id?: string;
  document_id?: string;
  sheet_id?: string;
  rule_id?: string;
  observation_id?: string;
  review_run_id?: string;
  stage_snapshot_id?: string;
  visual_crop_url?: string;
  legend_reference?: string;
  provenance_trace: Array<{
    action: string;
    from_status?: string;
    to_status?: string;
    author: string;
    timestamp: string;
    notes?: string;
  }>;
  chunks: KnowledgeChunkDTO[];
}

export interface KnowledgeSyncResponseDTO {
  success: boolean;
  message: string;
  synced_counts: Record<string, number>;
  total_items_created: number;
  total_items_updated: number;
  synced_item_ids?: string[];
}

export interface KnowledgeSearchResultItemDTO {
  item_id: string;
  chunk_id?: string;
  title: string;
  domain: KnowledgeDomain;
  item_type: string;
  discipline: string;
  stage?: string;
  status: KnowledgeStatus;
  is_active_for_reuse: boolean;
  relevance_score: number;
  snippet: string;
  provenance: Record<string, any>;
  tags: string[];
}

export interface KnowledgeSearchResponseDTO {
  query: string;
  total_matches: number;
  results: KnowledgeSearchResultItemDTO[];
}

export interface KnowledgeStatsDTO {
  total_items: number;
  approved_for_reuse_count: number;
  draft_or_extracted_count: number;
  validated_count: number;
  rejected_or_superseded_count: number;
  global_items_count: number;
  project_scoped_items_count: number;
  items_by_domain: Record<string, number>;
  items_by_discipline: Record<string, number>;
  items_by_status: Record<string, number>;
}

export type AssistantTaskType =
  | 'normative_query'
  | 'rule_suggestion'
  | 'completeness_assistance'
  | 'document_classification'
  | 'review_support'
  | 'observation_rfi_draft'
  | 'finding_explanation'
  | 'stage_synthesis';

export interface AssistantExecutionRequestDTO {
  task_type: AssistantTaskType;
  prompt: string;
  project_id?: string;
  stage?: string;
  discipline?: string;
  context_data?: Record<string, any>;
  force_tier?: number;
  allow_escalation?: boolean;
}

export interface AssistantExecutionResponseDTO {
  interaction_id: string;
  task_type: AssistantTaskType;
  generated_response: string;
  structured_output?: Record<string, any>;
  confidence_score: number;
  tier_used: number;
  engine_model_used: string;
  was_escalated: boolean;
  escalation_reason?: string;
  cost_estimate_usd: number;
  retrieved_sources: KnowledgeSearchResultItemDTO[];
}

export interface AssistantFeedbackRequestDTO {
  status: 'accepted' | 'edited' | 'rejected';
  feedback_notes?: string;
  edited_payload?: Record<string, any>;
}

export interface AssistantInteractionItemDTO {
  id: string;
  organization_id: string;
  project_id?: string;
  task_type: AssistantTaskType;
  user_prompt: string;
  resolved_prompt?: string;
  stage?: string;
  discipline?: string;
  retrieved_knowledge_ids: string[];
  retrieved_chunks: Array<{
    item_id: string;
    chunk_id?: string;
    title: string;
    domain: string;
    snippet: string;
    relevance_score: number;
  }>;
  initial_tier: number;
  executed_tier: number;
  engine_model_used: string;
  was_escalated: boolean;
  escalation_reason?: string;
  generated_response: string;
  structured_output: Record<string, any>;
  confidence_score: number;
  cost_estimate_usd: number;
  feedback_status: 'pending' | 'accepted' | 'edited' | 'rejected';
  feedback_payload: Record<string, any>;
  user_id: string;
  created_at: string;
  updated_at: string;
}

export interface AssistantTaskCatalogItemDTO {
  task_type: AssistantTaskType;
  name: string;
  description: string;
  default_tier: number;
  default_engine: string;
  capabilities: string[];
  escalation_triggers: string[];
}

// ============================================================================
// PERFIL DE MADUREZ O SUFICIENCIA INFORMACIONAL (FASE MADUREZ)
// ============================================================================

export type MaturityLevel = 'insufficient' | 'basic' | 'intermediate' | 'advanced' | 'exhaustive';

export interface CriticalGapItemDTO {
  id: string;
  dimension: string;
  discipline: string;
  title: string;
  description: string;
  impact_rationale: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  blocked_rules_count: number;
  blocked_disciplines: string[];
  is_resolved: boolean;
}

export interface AcquisitionRouteItemDTO {
  id: string;
  gap_id: string;
  gap_title: string;
  suggested_source_type: string;
  suggested_repository: string;
  intake_method: string;
  suggested_responsible: string;
  target_discipline: string;
  unlock_impact: string;
  estimated_score_gain: number;
  status: 'pending' | 'in_progress' | 'completed';
}

export interface DimensionScoreDetailDTO {
  score: number;
  weight: number;
  weighted_score: number;
  title: string;
  details: string;
  sub_metrics?: Record<string, any>;
}

export interface DisciplineScoreDetailDTO {
  score: number;
  status: 'adequate' | 'partial' | 'insufficient';
  doc_count: number;
  rule_count: number;
  title: string;
}

export interface AcquiredKnowledgeSummaryDTO {
  available_documents_count: number;
  validated_evidence_count: number;
  approved_kb_items_count: number;
  closed_rfis_count: number;
  unblocked_rules_count: number;
  recently_acquired_items: Array<{
    id: string;
    title: string;
    domain: string;
    item_type: string;
    origin_type: string;
    approved_at: string;
  }>;
}

export interface AssistantUsageSummaryDTO {
  total_interactions: number;
  tasks_executed: string[];
  project_chunks_used_count: number;
  top_used_knowledge_items: Array<{
    item_id: string;
    use_count: number;
  }>;
  average_confidence: number;
  estimated_savings_usd: number;
}

export interface ReviewCapabilityAssessmentDTO {
  auditable_scope: string;
  partially_auditable_scope: string;
  blind_blocked_scope: string;
  can_issue_stage_verdict: boolean;
}

export interface DeltaSummaryDTO {
  previous_score?: number | null;
  score_delta: number;
  previous_level?: string | null;
  level_changed: boolean;
  newly_resolved_gaps_count: number;
  evaluation_date?: string | null;
}

export interface ProjectMaturityProfileDTO {
  id: string;
  organization_id: string;
  project_id: string;
  stage: string;
  overall_score: number;
  maturity_level: MaturityLevel;
  target_level: string;
  is_target_achieved: boolean;
  dimension_scores: Record<string, DimensionScoreDetailDTO>;
  discipline_scores: Record<string, DisciplineScoreDetailDTO>;
  critical_gaps: CriticalGapItemDTO[];
  acquisition_routes: AcquisitionRouteItemDTO[];
  acquired_knowledge_summary: AcquiredKnowledgeSummaryDTO;
  assistant_usage_summary: AssistantUsageSummaryDTO;
  review_capability_assessment: ReviewCapabilityAssessmentDTO;
  delta_summary: DeltaSummaryDTO;
  evaluated_by: string;
  created_at: string;
  updated_at: string;
}

// =========================================================
// ADQUISICIÓN DE INFORMACIÓN & POLÍTICA WEB-FIRST CON PERMISO
// =========================================================

export interface InformationAcquisitionRequestDTO {
  id: string;
  organization_id: string;
  project_id?: string | null;
  stage?: string | null;
  discipline: string;
  missing_topic: string;
  gap_description: string;
  detection_source: string;
  internal_rag_status: 'resolved' | 'insufficient' | 'not_found';
  internal_rag_score: number;
  internal_rag_matches_count: number;
  permission_status: 'pending_permission' | 'approved' | 'rejected' | 'not_required';
  permission_requested_at: string;
  permission_granted_by?: string | null;
  permission_granted_at?: string | null;
  rejection_reason?: string | null;
  action_type: 'web_search' | 'document_request' | 'internal_lookup';
  web_search_query?: string | null;
  web_search_executed: boolean;
  web_search_executed_at?: string | null;
  web_search_result_summary?: string | null;
  web_search_sources?: Array<{
    title: string;
    url: string;
    snippet: string;
    credibility_score: number;
  }>;
  iteration_count: number;
  max_iterations: number;
  search_sources_limit: number;
  relevance_score: number;
  confidence_score: number;
  coverage_score: number;
  overall_adequacy_score: number;
  adequacy_classification: 'sufficient' | 'partially_sufficient' | 'insufficient' | 'not_found' | 'not_applicable' | 'pending';
  termination_reason?: string | null;
  adequacy_status: 'pending_evaluation' | 'sufficient' | 'partially_sufficient' | 'insufficient_project_doc_needed' | 'rejected_by_user';
  requested_document_type?: string | null;
  requested_document_justification?: string | null;
  suggested_responsible?: string | null;
  escalation_details?: {
    missing_information_details?: string;
    why_web_internal_failed?: string;
    requested_document_type?: string;
    suggested_responsible?: string;
    audit_impact_justification?: string;
    unlocked_deliverables_and_rules?: string[];
    escalated_at?: string;
  };
  created_knowledge_item_id?: string | null;
  status: 'open' | 'in_progress' | 'resolved' | 'escalated' | 'closed';
  metadata_payload?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface DetectInformationGapResponseDTO {
  is_gap_detected: boolean;
  missing_topic: string;
  internal_rag_status: string;
  internal_rag_score: number;
  internal_rag_matches_count: number;
  acquisition_request_id?: string | null;
  recommended_action: string;
  message: string;
}

export interface WebSearchPermissionActionDTO {
  action: 'approve' | 'reject';
  query_override?: string;
  rejection_reason?: string;
  force_document_request?: boolean;
  max_iterations_override?: number;
  sources_limit_override?: number;
}

export interface ViewerKnowledgeCaptureDTO {
  project_id?: string;
  document_id?: string;
  sheet_id?: string;
  sheet_code?: string;
  page_number?: number;
  bbox_normalized?: number[];
  element_type: 'symbol' | 'table' | 'template' | 'detail' | 'photo' | 'schema' | 'vignette' | 'legend' | 'other';
  name: string;
  normalized_category?: string;
  aliases?: string[];
  description?: string;
  discipline: string;
  domain?: string;
  legend_text?: string;
  related_table_code?: string;
  related_rule_code?: string;
  crop_image_base64?: string;
  auto_approve?: boolean;
  deduplication_mode?: 'auto' | 'link_occurrence' | 'new_version' | 'create_new';
  target_existing_item_id?: string;
}

export interface VisualDeduplicationMatchDTO {
  item_id: string;
  title: string;
  normalized_category: string;
  discipline: string;
  similarity_score: number;
  visual_crop_url?: string | null;
  total_occurrences: number;
  status: string;
  is_active_for_reuse: boolean;
}

export interface VisualDeduplicationCheckResponseDTO {
  has_potential_duplicates: boolean;
  suggested_mode: 'create_new' | 'link_occurrence' | 'new_version';
  matches: VisualDeduplicationMatchDTO[];
  message: string;
}

export interface IngestionChannelItemDTO {
  channel_code: string;
  channel_name: string;
  description: string;
  total_items: number;
  approved_reusable_items: number;
  pending_validation_items: number;
  modalities_count: Record<string, number>;
  requires_human_approval: boolean;
  is_active: boolean;
}

export interface IngestionChannelSummaryResponseDTO {
  total_knowledge_items: number;
  total_active_for_reuse: number;
  channels: IngestionChannelItemDTO[];
}

// Backward compatibility type aliases
export type KnowledgeItemDTO = KnowledgeItemDetailDTO;
export type RuleDefinition = RuleDefinitionItem;
export type RuleFinding = RuleFindingItem;

// =========================================================
// EXECUTIVE DASHBOARD & AGENT GLOBAL HEALTH DTOs
// =========================================================

export interface EngineHealthItem {
  engine_id: string;
  name: string;
  category: 'vision' | 'ocr' | 'llm' | 'rules' | 'web' | 'mlops' | string;
  status: 'online' | 'degraded' | 'offline' | string;
  latency_ms: number;
  description: string;
}

export interface BackgroundJobsSummary {
  queued: number;
  running: number;
  completed: number;
  failed: number;
  total: number;
}

export interface AgentGlobalHealth {
  overall_status: 'healthy' | 'degraded' | 'critical' | string;
  engines: EngineHealthItem[];
  jobs_summary: BackgroundJobsSummary;
  average_confidence: number;
  knowledge_reuse_count: number;
  precedents_applied_count: number;
  duplicates_detected_count: number;
  system_uptime: string;
}

export interface ProjectExecutiveMetrics {
  project_id?: string;
  project_code?: string;
  project_name?: string;
  client_name?: string;
  discipline?: string;
  stage?: string;
  documents_total: number;
  documents_processed: number;
  sheets_total: number;
  sheets_rasterized: number;
  progress_percentage: number;
  active_rules_count: number;
  compliance_score: number;
  findings_total: number;
  findings_critical: number;
  findings_high: number;
  findings_medium: number;
  findings_low: number;
  findings_resolved: number;
  findings_open: number;
  pending_validations_count: number;
  information_coverage_score: number;
  maturity_stage?: string;
  last_review_run?: {
    id: string;
    run_name: string;
    status: string;
    rules_applied_count: number;
    findings_count: number;
    execution_time_sec: number;
    created_at?: string;
  } | null;
}

export interface AgentActivityLog {
  id: string;
  timestamp: string;
  activity_type: 'one_click_review' | 'extraction' | 'hitl_feedback' | 'web_search' | 'maintenance' | string;
  title: string;
  description: string;
  severity: 'info' | 'warning' | 'success' | 'error' | string;
  project_id?: string;
  user_name?: string;
}

export interface ExecutiveAlert {
  id: string;
  alert_type: string;
  title: string;
  message: string;
  severity: 'critical' | 'high' | 'medium' | 'info' | string;
  action_label: string;
  action_target_tab: string;
  created_at: string;
}

export interface ExecutiveDashboardSummary {
  timestamp: string;
  project_metrics: ProjectExecutiveMetrics;
  agent_health: AgentGlobalHealth;
  recent_activities: AgentActivityLog[];
  alerts_and_recommendations: ExecutiveAlert[];
  quick_shortcuts: Array<{
    id: string;
    title: string;
    description: string;
    target_tab: string;
    variant: 'primary' | 'secondary';
  }>;
}

// =========================================================
// LAS 4 MEMORIAS CONSOLE MANAGEMENT DTOs
// =========================================================

export interface MemoryOverviewDetail {
  memory_type: 'document_memory' | 'normative_memory' | 'template_memory' | 'decision_memory';
  name: string;
  status: 'active' | 'synchronizing' | 'degraded' | string;
  total_records: number;
  secondary_count: number;
  secondary_label: string;
  last_updated?: string;
  disciplines: string[];
  pending_reviews_count: number;
  consistency_score: number;
  index_status: 'indexed' | 'pending_reindex' | 'stale' | string;
  description: string;
}

export interface MemoriesOverviewResponse {
  timestamp: string;
  total_memories_count: number;
  total_combined_records: number;
  global_consistency_score: number;
  memories: MemoryOverviewDetail[];
}

export interface MemoryRecordItem {
  id: string;
  memory_type: 'document_memory' | 'normative_memory' | 'template_memory' | 'decision_memory';
  code_or_identifier: string;
  title: string;
  description?: string;
  discipline: string;
  category_or_nature: string;
  status: 'active' | 'to_confirm' | 'obsolete' | 'archived' | 'draft' | string;
  created_at: string;
  updated_at?: string;
  version_or_revision?: string;
  confidence_score?: number;
  metadata_payload: Record<string, any>;
  relationships_count?: number;
}

export interface MemoryRecordsListResponse {
  memory_type: string;
  total_count: number;
  page: number;
  page_size: number;
  records: MemoryRecordItem[];
}

export interface MemoryRecordCreateRequest {
  memory_type: string;
  code_or_identifier: string;
  title: string;
  description?: string;
  discipline?: string;
  category_or_nature?: string;
  status?: string;
  version_or_revision?: string;
  metadata_payload?: Record<string, any>;
}

export interface MemoryRecordUpdateRequest {
  title?: string;
  description?: string;
  discipline?: string;
  category_or_nature?: string;
  status?: string;
  version_or_revision?: string;
  metadata_payload?: Record<string, any>;
}

export interface MemoryConsistencyIssue {
  id: string;
  severity: 'critical' | 'warning' | 'info' | string;
  memory_source: string;
  issue_type: string;
  title: string;
  description: string;
  affected_record_id: string;
  suggested_action: string;
  can_auto_fix: boolean;
}

export interface MemoryConsistencyReport {
  generated_at: string;
  total_checks_run: number;
  issues_found_count: number;
  critical_issues_count: number;
  orphaned_elements_count: number;
  consistency_health: 'healthy' | 'attention_needed' | 'critical' | string;
  issues: MemoryConsistencyIssue[];
}

export interface MemoryMaintenanceResult {
  executed_at: string;
  action: string;
  status: 'success' | 'completed_with_warnings' | 'failed' | string;
  records_processed: number;
  records_repaired_or_cleaned: number;
  message: string;
  details: Record<string, any>;
}

export interface MemoriesExportResponse {
  exported_at: string;
  version: string;
  total_records: number;
  document_memory: any[];
  normative_memory: any[];
  template_memory: any[];
  decision_memory: any[];
}

// ============================================================================
// FASE 2: CURACIÓN HITL, DEDUPLICACIÓN MULTI-FACTOR Y CATÁLOGO CANÓNICO
// ============================================================================

export interface SymbolOccurrenceItem {
  occurrence_id?: string;
  page_number: number;
  sheet_id?: string;
  bbox_normalized: number[];
  cell_bbox?: number[];
  inner_drawing_bbox?: number[];
  source_document_id?: string;
  crop_image_path?: string;
  document_title?: string;
  row_index?: number;
  col_index?: number;
  source_reference?: string;
  reading_orientation?: string;
  orientation?: string;
  orientation_confidence?: number;
  orientation_reason?: string;
  title?: string;
  is_primary?: boolean;
}

export interface ExtractedTableCell {
  id?: string;
  table_id: string;
  row_index: number;
  column_index: number;
  text: string;
  normalized_text?: string;
  confidence: number;
  bbox?: number[];
  bbox_normalized?: number[];
  is_header: boolean;
  source_text_refs?: string[];
  cell_type: 'text_cell' | 'symbol_cell' | 'mixed_cell' | 'empty_cell' | string;
  symbol_id?: string;
  has_symbol: boolean;
  symbol_name?: string;
  crop_image_path?: string;
  inner_drawing_bbox?: number[];
}

export interface ExtractedTable {
  id: string;
  document_id: string;
  sheet_id: string;
  region_id?: string;
  table_type: string;
  title: string;
  bbox?: number[];
  bbox_normalized?: number[];
  row_count: number;
  column_count: number;
  has_symbols?: boolean;
  reading_orientation?: string;
  orientation?: string;
  orientation_confidence?: number;
  orientation_reason?: string;
  confidence: number;
  extraction_status: string;
  headers?: string[];
  cells: ExtractedTableCell[];
  raw_structure?: Record<string, any>;
  created_at: string;
}

export interface CandidateCurationDetail {
  id: string;
  extracted_item_id: string;
  symbol_name: string;
  standard_family: string;
  discipline: string;
  category?: string;
  crop_image_path?: string;
  confidence_score: number;
  source_render_mode: 'vector' | 'raster' | 'mixed' | string;
  layout_context: string;
  context_association_mode: string;
  standard_reference?: string;
  canonical_symbol_family: string;
  visual_variant_group_id?: string;
  estimated_physical_size_mm?: {
    width_mm?: number;
    height_mm?: number;
    [key: string]: any;
  };
  reused_for_matching_count: number;
  false_positive_count: number;
  human_validation_notes?: string;
  created_at: string;
  document_title?: string;
  document_id?: string;
  extraction_id?: string;
  page_number: number;
  ocr_associated_text?: string;
  review_status: 'pending' | 'accepted' | 'rejected' | 'flagged_false_positive' | string;
  possible_matching_template?: {
    template_id: string;
    display_name: string;
    symbol_class: string;
    similarity: number;
    library_name?: string;
  };
  // Linaje estructural tabla-fila-columna
  source_table_id?: string;
  row_index?: number;
  col_index?: number;
  cell_bbox?: number[];
  row_bbox?: number[];
  // Ocurrencias multipágina para navegación y foco en visor
  occurrences?: SymbolOccurrenceItem[];
}

export interface StructuredSymbolUpdateRequest {
  symbol_name?: string;
  canonical_symbol_family?: string;
  category?: string;
  standard_reference?: string;
  human_validation_notes?: string;
  visual_variant_group_id?: string;
  review_status?: string;
}

export interface BatchCurateSymbolsRequest {
  symbol_ids: string[];
  action: 'accept' | 'reject' | 'flag_false_positive' | 'update_family' | string;
  canonical_symbol_family?: string;
  standard_reference?: string;
  notes?: string;
  reviewer?: string;
}

export interface BatchCurateSymbolsResponse {
  updated_count: number;
  accepted_count: number;
  rejected_count: number;
  flagged_count: number;
  message: string;
}

export interface DeduplicateSymbolsRequest {
  extraction_id?: string;
  discipline?: string;
  canonical_symbol_family?: string;
  visual_threshold?: number;
  semantic_threshold?: number;
}

export interface VariantClusterItem {
  symbol_id: string;
  symbol_name: string;
  canonical_symbol_family: string;
  crop_image_path?: string;
  confidence_score: number;
  source_render_mode: string;
  visual_similarity: number;
  semantic_similarity: number;
  combined_score: number;
  is_canonical_representative: boolean;
}

export interface DeduplicationCluster {
  group_id: string;
  canonical_symbol_family: string;
  canonical_name: string;
  representative_id: string;
  members_count: number;
  members: VariantClusterItem[];
}

export interface DeduplicateSymbolsResponse {
  total_evaluated: number;
  clusters_count: number;
  duplicates_detected: number;
  clusters: DeduplicationCluster[];
}

export interface CanonicalTemplateItem {
  id: string;
  library_id: string;
  symbol_class: string;
  display_name: string;
  aliases: string[];
  image_template_path?: string;
  vector_svg_path?: string;
  approved_by?: string;
  approved_at?: string;
  source_structured_symbol_id?: string;
  visual_variant_group_id?: string;
  feature_descriptors?: Record<string, any>;
  created_at: string;
}

export interface CanonicalCatalogResponse {
  library_id: string;
  library_name: string;
  discipline: string;
  standard_name?: string;
  total_templates: number;
  family_counts: Record<string, number>;
  templates: CanonicalTemplateItem[];
}

export interface BatchPromoteToTemplateRequest {
  structured_symbol_ids: string[];
  library_name?: string;
  discipline?: string;
  reviewer?: string;
  user_notes?: string;
}

export interface BatchPromoteToTemplateResponse {
  promoted_count: number;
  library_id: string;
  library_name: string;
  promoted_templates: Array<{
    template_id: string;
    display_name: string;
    symbol_class: string;
    visual_variant_group_id?: string;
  }>;
  message: string;
}

// ==========================================
// One-Click Review Taxonomy & Orchestration
// ==========================================

export interface ReviewDisciplineItem {
  id: string;
  code: string;
  name: string;
  description?: string;
  order_index: number;
  is_active: boolean;
}

export interface ReviewTopicItem {
  id: string;
  discipline_id?: string;
  code: string;
  name: string;
  description?: string;
  is_transversal: boolean;
  enabled_mvp: boolean;
  order_index: number;
  is_active: boolean;
}

export interface ReviewPlanRequest {
  project_id: string;
  discipline_code: string;
  topic_code: string;
  document_ids?: string[];
  mode?: 'production' | 'sandbox';
}

export interface ReviewPlanResponse {
  project_id: string;
  project_code?: string;
  project_name?: string;
  discipline_code: string;
  discipline_name: string;
  topic_code: string;
  topic_name: string;
  execution_mode: 'production' | 'sandbox';
  can_execute: boolean;
  empty_reason?: string;
  applicable_rules: Array<{
    rule_id: string;
    code: string;
    name: string;
    category: string;
    discipline: string;
    severity_default: string;
    description: string;
    rule_scope: string;
    execution_phase: number;
    priority: number;
    requires_data: string[];
    applicable_document_types: string[];
    role: string;
    approval_status: string;
    source: string;
    rationale?: string;
    confidence: number;
  }>;
  unapproved_rules: Array<any>;
  included_documents: Array<{
    document_id: string;
    filename: string;
    file_hash_sha256?: string;
    inclusion_reason: string;
    document_role: string;
    status: string;
  }>;
  excluded_documents: Array<{
    document_id: string;
    filename: string;
    exclusion_reason: string;
  }>;
  missing_required_document_types: Array<{
    document_type: string;
    reason: string;
    recommended_action: string;
  }>;
  phases_blueprint: Array<{
    phase: number;
    phase_name: string;
    step_type: string;
    rule_count: number;
    rules: string[];
    description: string;
  }>;
  warnings: string[];
}

export interface ReviewRunCreatePayload {
  project_id: string;
  discipline_code: string;
  topic_code: string;
  document_ids: string[];
  mode: 'production' | 'sandbox';
  run_name?: string;
}

export interface ReviewRunStepDetail {
  phase: number;
  phase_name: string;
  step_type: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'skipped';
  input_summary: Record<string, any>;
  output_summary: Record<string, any>;
  error_summary?: string;
}

export interface RuleExecutionDetail {
  id: string;
  rule_code: string;
  rule_name: string;
  phase: number;
  status: string;
  confidence: number;
  not_evaluable_reason_code?: string;
  not_evaluable_reason_message?: string;
  missing_requirements: string[];
  recommended_action?: string;
  result_summary: Record<string, any>;
}

export interface ReviewFindingDetail {
  id: string;
  rule_code: string;
  rule_name: string;
  severity: string;
  status: string;
  title: string;
  description: string;
  recommendation?: string;
  bbox?: number[];
  evidence_refs?: Record<string, any>;
  navigation_context?: {
    document_id?: string;
    sheet_id?: string;
    bbox?: number[];
    crop_url?: string;
  };
}

export interface ReviewRunDetailResponse {
  id: string;
  project_id: string;
  run_name: string;
  discipline_code: string;
  discipline_name: string;
  topic_code: string;
  topic_name: string;
  execution_mode: 'production' | 'sandbox';
  status: string;
  requested_by: string;
  requested_at?: string;
  completed_at?: string;
  execution_time_sec: number;
  rule_count: number;
  document_count: number;
  findings_count: number;
  summary_stats: {
    passed?: number;
    failed?: number;
    warning?: number;
    not_evaluable?: number;
    critical?: number;
    high?: number;
    medium?: number;
  };
  documents: Array<{
    document_id: string;
    filename: string;
    inclusion_reason: string;
    document_role: string;
    status: string;
  }>;
  steps: ReviewRunStepDetail[];
  executions: RuleExecutionDetail[];
  findings: ReviewFindingDetail[];
  reports?: ReviewReportItem[];
  baseline_catalog_version?: string;
}

export interface ReviewReportItem {
  id: string;
  project_id: string;
  review_run_id: string;
  report_name: string;
  format: 'json' | 'xlsx' | 'pdf';
  artifact_path: string;
  sha256: string;
  status: string;
  file_size_bytes?: number;
  baseline_catalog_version?: string;
  stats_summary: Record<string, any>;
  created_at: string;
}



