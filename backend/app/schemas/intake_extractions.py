from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

# =========================================================
# SCHEMAS: ELEMENTOS EXTRAÍDOS (EXTRACTED ITEMS)
# =========================================================

class FieldProvenanceEntry(BaseModel):
    original_raw: Optional[str] = None
    ocr_extracted: Optional[str] = None
    suggested_value: Optional[str] = None
    suggestion_source: Optional[str] = None
    suggestion_confidence: float = 0.0
    accepted_value: Optional[str] = None
    accepted_from: Optional[str] = None # original_raw, ocr_extracted, suggested_value, manual_edited, hybrid_edited
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None

class FieldAcceptancePatchRequest(BaseModel):
    field_name: str = Field(..., description="title, description, function, code_or_number, etc.")
    accepted_value: str = Field(..., description="Valor aceptado para el campo")
    accepted_from: str = Field("suggested_value", description="suggested_value, ocr_extracted, manual_edited, original_raw")
    user_id: Optional[str] = "auditor"

class StructuredTableRead(BaseModel):
    id: str
    extracted_item_id: str
    table_code: Optional[str] = None
    caption: Optional[str] = None
    num_rows: int = 0
    num_cols: int = 0
    headers: List[str] = Field(default_factory=list)
    rows_data: List[Any] = Field(default_factory=list)
    matrix_summary: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class StructuredSymbolRead(BaseModel):
    id: str
    extracted_item_id: str
    symbol_name: str
    standard_family: Optional[str] = None
    discipline: str = "general"
    category: Optional[str] = None
    svg_path: Optional[str] = None
    crop_image_path: Optional[str] = None
    confidence_score: float = 1.0
    
    # Nuevos campos de Fase 1 Piping
    source_render_mode: str = "raster" # vector, raster, mixed
    layout_context: str = "inside_table" # inside_table, semi_structured_legend, free_layout, manual_crop
    context_association_mode: str = "row_band" # row_band, lateral_band, caption_band, manual_assignment
    standard_reference: Optional[str] = None
    canonical_symbol_family: str = "valves" # valves, instruments, pumps, fittings, line_types, other
    visual_variant_group_id: Optional[str] = None
    estimated_physical_size_mm: Dict[str, Any] = Field(default_factory=dict)
    reused_for_matching_count: int = 0
    false_positive_count: int = 0
    human_validation_notes: Optional[str] = None
    
    # Linaje estructural tabla-fila-columna
    source_table_id: Optional[str] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None
    cell_bbox: Optional[List[float]] = None
    row_bbox: Optional[List[float]] = None

    created_at: datetime

    class Config:
        from_attributes = True

class StructuredEquipmentRead(BaseModel):
    id: str
    extracted_item_id: str
    tag_code: str
    equipment_type: str
    service_description: Optional[str] = None
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    rated_capacity: Optional[str] = None
    operating_parameters: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True

class StructuredRulePremiseRead(BaseModel):
    id: str
    extracted_item_id: str
    rule_code: str
    statement: str
    rule_type: str = "mandatory_rule"
    discipline: str = "general"
    severity: str = "warning"
    evaluation_logic: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True

class ExtractionItemsSummaryStats(BaseModel):
    total_items: int = 0
    reviewed_count: int = 0
    pending_count: int = 0
    rejected_count: int = 0
    complete_count: int = 0
    partial_count: int = 0
    missing_data_count: int = 0
    web_suggested_count: int = 0
    by_item_type: Dict[str, int] = Field(default_factory=dict)
    by_completeness: Dict[str, int] = Field(default_factory=dict)
    by_review_status: Dict[str, int] = Field(default_factory=dict)

class ExtractedItemBase(BaseModel):
    item_type: str = Field(..., description="rule, article, chapter, table, image, figure, symbol, text_note, definition, procedure, restriction, requirement, other")
    candidate_type: Optional[str] = Field(None, description="premise_candidate, rule_candidate, symbol_candidate, table_matrix_candidate, equipment_image_candidate, diagram_candidate, example_candidate")
    title: str
    code_or_number: Optional[str] = None
    description: Optional[str] = None
    content_text: Optional[str] = None
    derived_text: Optional[str] = None
    ocr_text: Optional[str] = None
    caption_or_context: Optional[str] = None
    disclaimer_notes: Optional[str] = None
    translated_fields: Dict[str, Any] = Field(default_factory=dict)
    source_fields: Dict[str, Any] = Field(default_factory=dict)
    effective_fields: Dict[str, Any] = Field(default_factory=dict)
    source_language: str = "en"
    target_language: str = "es"
    translation_status: str = "not_required"
    presentation_language: str = "es"
    crop_image_path: Optional[str] = None
    bbox_normalized: List[float] = Field(default_factory=list)
    page_number: int = 1
    discipline: str = "general"
    source_asset_id: Optional[str] = None
    evidence_references: List[str] = Field(default_factory=list)
    technical_parameters: Dict[str, Any] = Field(default_factory=dict)
    target_destination: str = "rules_engine" # rules_engine, knowledge_base, both
    review_status: str = "draft" # draft, editado, por_confirmar, validada, eliminado, to_confirm, accepted, rejected
    
    # Deduplicación y Matching contra Motor de Reglas QA/QC
    duplicate_status: str = "no_match" # no_match, exact_match_existing_rule, likely_duplicate_existing_rule, related_existing_rule
    best_match_rule_id: Optional[str] = None
    best_match_rule_code: Optional[str] = None
    best_match_title: Optional[str] = None
    best_match_discipline: Optional[str] = None
    duplicate_reason: Optional[str] = None
    duplicate_confidence: float = 0.0
    blocked_from_acceptance: bool = False

    # Estado de Completitud y Enriquecimiento Asistido
    completeness_status: str = "missing_data" # complete, partial, missing_data, web_suggested
    enrichment_status: str = "not_enriched" # not_enriched, suggestion_found, manual_completed
    requires_validation: bool = True
    enriched_from_web: bool = False
    enrichment_method: Optional[str] = None
    match_confidence: float = 0.0
    suggested_title: Optional[str] = None
    suggested_description: Optional[str] = None
    suggested_function: Optional[str] = None
    suggested_source_url: Optional[str] = None
    suggested_source_label: Optional[str] = None

    # Separación Visual y Linaje de Derivación
    parent_item_id: Optional[str] = None
    is_derived: bool = False
    split_mode: Optional[str] = None

    field_provenance: Dict[str, Any] = Field(default_factory=dict)

    structured_matrix: Optional[Dict[str, Any]] = None
    validated_at: Optional[datetime] = None
    validated_by: Optional[str] = None

    source_origin: str = "document" # document, web
    source_reference: Optional[str] = None # URL, standard code, legal citation
    item_nature: str = "official_rule" # official_rule, proposed_rule, support_research, concept, reference
    governance_note: Optional[str] = None
    
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)

class ExtractedItemCreate(ExtractedItemBase):
    crop_image_base64: Optional[str] = None

class ExtractedItemUpdate(BaseModel):
    item_type: Optional[str] = None
    candidate_type: Optional[str] = None
    title: Optional[str] = None
    code_or_number: Optional[str] = None
    description: Optional[str] = None
    content_text: Optional[str] = None
    derived_text: Optional[str] = None
    ocr_text: Optional[str] = None
    caption_or_context: Optional[str] = None
    disclaimer_notes: Optional[str] = None
    crop_image_path: Optional[str] = None
    bbox_normalized: Optional[List[float]] = None
    page_number: Optional[int] = None
    discipline: Optional[str] = None
    source_asset_id: Optional[str] = None
    parent_item_id: Optional[str] = None
    is_derived: Optional[bool] = None
    split_mode: Optional[str] = None
    target_destination: Optional[str] = None
    review_status: Optional[str] = None
    
    duplicate_status: Optional[str] = None
    best_match_rule_id: Optional[str] = None
    best_match_rule_code: Optional[str] = None
    best_match_title: Optional[str] = None
    best_match_discipline: Optional[str] = None
    duplicate_reason: Optional[str] = None
    duplicate_confidence: Optional[float] = None
    blocked_from_acceptance: Optional[bool] = None

    completeness_status: Optional[str] = None
    enrichment_status: Optional[str] = None
    requires_validation: Optional[bool] = None
    enriched_from_web: Optional[bool] = None
    enrichment_method: Optional[str] = None
    match_confidence: Optional[float] = None
    suggested_title: Optional[str] = None
    suggested_description: Optional[str] = None
    suggested_function: Optional[str] = None
    suggested_source_url: Optional[str] = None
    suggested_source_label: Optional[str] = None

    field_provenance: Optional[Dict[str, Any]] = None
    structured_matrix: Optional[Dict[str, Any]] = None
    evidence_references: Optional[List[str]] = None
    technical_parameters: Optional[Dict[str, Any]] = None
    validated_at: Optional[datetime] = None
    validated_by: Optional[str] = None
    source_origin: Optional[str] = None
    source_reference: Optional[str] = None
    item_nature: Optional[str] = None
    governance_note: Optional[str] = None
    metadata_payload: Optional[Dict[str, Any]] = None

class ItemVisualSplitRequest(BaseModel):
    bbox: List[float] = Field(..., description="Coordenadas normalizadas [x0, y0, x1, y1] sobre la imagen de origen")
    title_hint: Optional[str] = None
    discipline: Optional[str] = None
    user_id: Optional[str] = None

class ItemCropRequest(BaseModel):
    bbox: List[float] = Field(..., description="Coordenadas normalizadas [x0, y0, x1, y1] sobre la imagen actual")
    user_id: Optional[str] = None

class ParagraphRuleCandidate(BaseModel):
    title: str
    summary: str
    rule_statement: str
    keywords: List[str] = Field(default_factory=list)
    discipline: str = "general"
    confidence: float = 0.90
    page_reference: Optional[str] = None
    review_status: str = "to_confirm"
    source_paragraph_text: Optional[str] = None

class ExtractParagraphRulesRequest(BaseModel):
    text_content: str = Field(..., description="Texto plano o extraído de documento/sección")
    discipline: str = "general"
    document_type: str = "norma"
    page_number: int = 1
    source_reference: Optional[str] = None

class ExtractParagraphRulesResponse(BaseModel):
    total_paragraphs_detected: int
    rules_candidates: List[ParagraphRuleCandidate] = Field(default_factory=list)

class ExtractedItemRead(ExtractedItemBase):
    id: str
    extraction_id: str
    structured_table: Optional[StructuredTableRead] = None
    structured_symbol: Optional[StructuredSymbolRead] = None
    structured_equipment: Optional[StructuredEquipmentRead] = None
    structured_rule_premise: Optional[StructuredRulePremiseRead] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TechnicalInterpretationCandidateRead(ExtractedItemRead):
    pass

class CandidateEnrichmentRequest(BaseModel):
    candidate_type: Optional[str] = None
    title: Optional[str] = None
    caption_or_context: Optional[str] = None
    ocr_text: Optional[str] = None
    discipline: str = "general"
    page_number: Optional[int] = 1
    document_title: Optional[str] = None
    force_web_search: bool = True
    presentation_language: str = "es"
    source_language: Optional[str] = None
    target_language: Optional[str] = "es"
    source_fields: Optional[Dict[str, Any]] = None
    translated_fields: Optional[Dict[str, Any]] = None
    effective_fields: Optional[Dict[str, Any]] = None

class CandidateEnrichmentResponse(BaseModel):
    item_id: Optional[str] = None
    enrichment_status: str # suggestion_found, manual_required, not_enriched
    completeness_status: str # complete, partial, missing_data, web_suggested
    match_confidence: float # 0.0 to 1.0
    suggested_title: Optional[str] = None
    suggested_description: Optional[str] = None
    suggested_function: Optional[str] = None
    suggested_source_label: Optional[str] = None
    suggested_source_url: Optional[str] = None
    enrichment_method: str
    requires_validation: bool = True
    enriched_from_web: bool = False
    technical_properties: Dict[str, Any] = Field(default_factory=dict)
    message: str
    presentation_language: str = "es"
    effective_fields: Dict[str, Any] = Field(default_factory=dict)

class ItemContextResponse(BaseModel):
    item_id: str
    extraction_id: str
    source_asset_id: Optional[str] = None
    source_title: str
    document_type: str
    discipline: str
    page_number: int
    total_pages: int
    bbox_normalized: List[float] = Field(default_factory=list)
    crop_image_path: Optional[str] = None
    page_image_url: Optional[str] = None
    file_url: Optional[str] = None
    page_text_preview: Optional[str] = None
    item_type: str
    candidate_type: Optional[str] = None
    title: str
    code_or_number: Optional[str] = None
    description: Optional[str] = None
    content_text: Optional[str] = None
    ocr_text: Optional[str] = None
    caption_or_context: Optional[str] = None
    technical_parameters: Dict[str, Any] = Field(default_factory=dict)
    source_fields: Dict[str, Any] = Field(default_factory=dict)
    translated_fields: Dict[str, Any] = Field(default_factory=dict)
    effective_fields: Dict[str, Any] = Field(default_factory=dict)
    source_language: str = "en"
    target_language: str = "es"
    translation_status: str = "not_required"
    presentation_language: str = "es"
    review_status: str
    completeness_status: str
    enrichment_status: str
    requires_validation: bool
    enriched_from_web: bool
    enrichment_method: Optional[str] = None
    match_confidence: float
    suggested_title: Optional[str] = None
    suggested_description: Optional[str] = None
    suggested_function: Optional[str] = None
    suggested_source_url: Optional[str] = None
    suggested_source_label: Optional[str] = None
    source_origin: Optional[str] = "document"
    source_reference: Optional[str] = None
    web_source_url: Optional[str] = None
    web_snapshot_url: Optional[str] = None
    dom_hint: Optional[str] = None
    duplicate_status: Optional[str] = None
    duplicate_reason: Optional[str] = None

class RegionOcrRequest(BaseModel):
    page_number: int
    bbox: List[float] = Field(..., description="[x0, y0, x1, y1] normalized coords")
    target_field: Optional[str] = Field("title", description="title, description, function, properties")

class RegionOcrResponse(BaseModel):
    page_number: int
    bbox: List[float]
    extracted_text: str
    target_field: str
    confidence: float = 0.95



# =========================================================
# SCHEMAS: SESIÓN DE EXTRACCIÓN (SOURCE EXTRACTIONS)
# =========================================================

class SourceExtractionBase(BaseModel):
    title: str
    document_type: str = "norma"
    authority: Optional[str] = None
    discipline: str = "general"
    extraction_mode: str = "ai_document" # ai_document, ai_web_research, without_ai, with_ai
    source_origin: str = "document" # document, web
    search_query: Optional[str] = None
    search_citations: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None
    source_url: Optional[str] = None

class TranslationConfig(BaseModel):
    enabled: bool = True
    source_language: str = "auto"
    target_language: str = Field(..., description="Idioma destino obligatorio si se configura translation (ej: 'es')")
    mode: str = "during_extraction"

class ProcessWithAiRequest(BaseModel):
    source_asset_id: Optional[str] = None
    project_id: Optional[str] = None
    title: str
    document_type: str = "norma" # norma, decreto, manual, reglamento, guia, ficha_tecnica, investigacion_web, otro
    authority: Optional[str] = None
    discipline: str = "general"
    text_content: Optional[str] = None
    file_path: Optional[str] = None
    extraction_mode: str = "ai_document" # ai_document, ai_web_research
    search_prompt: Optional[str] = None
    type_limits: Optional[Dict[str, int]] = None # {'rules': 4, 'tables': 2, 'images': 2, 'symbols': 2, 'equipment': 2}
    max_total: Optional[int] = 12
    translation: Optional[TranslationConfig] = None

class WebSource(BaseModel):
    url: str
    discovered_url: Optional[str] = None
    resolved_url: Optional[str] = None
    validated_content_url: Optional[str] = None
    canonical_url: Optional[str] = None
    final_url: Optional[str] = None
    content_subpage_url: Optional[str] = None
    title: str
    snippet: str
    domain: Optional[str] = None
    estimated_type: str = "Página Web"
    source_quality_tier: str = "secondary"
    quality_classification: Optional[str] = "general_web" # official_accessible, technical_specialized, official_partial, curated_backup, general_web
    verified: bool = False
    authority: Optional[str] = None
    detected_language: Optional[str] = "es"
    url_provenance: Optional[str] = "search_provider" # search_provider, internal_link, curated_backup
    provider_name: Optional[str] = None
    validation_status: Optional[str] = "validated" # validated, discarded
    discard_reason: Optional[str] = None
    match_bucket: Optional[str] = "MEDIUM_MATCH" # FULL_MATCH, HIGH_MATCH, MEDIUM_MATCH, LOW_MATCH, REJECTED
    coverage_score: Optional[float] = 0.0
    critical_coverage_pct: Optional[float] = 0.0
    total_coverage_pct: Optional[float] = 0.0
    matched_terms: Optional[List[str]] = None
    missing_critical_terms: Optional[List[str]] = None
    exact_phrase_matches: Optional[List[str]] = None
    subpage_selection_reason: Optional[str] = None
    relevance_score: Optional[int] = None
class WebSearchSourceRequest(BaseModel):
    search_prompt: str = Field(..., description="Prompt, tema o norma a investigar")
    discipline: str = "Arquitectura"
    document_type: str = "any_web_doc"
    authority: Optional[str] = None
    max_results: int = 10
    user_id: Optional[str] = None
    project_id: Optional[str] = None

class InspectManualUrlRequest(BaseModel):
    url: str = Field(..., description="URL pública a inspeccionar y validar")
    discipline: Optional[str] = "Arquitectura"
    document_type: Optional[str] = "norma"
    authority: Optional[str] = None
    search_prompt: Optional[str] = None
    max_internal_links: Optional[int] = 15
    user_id: Optional[str] = None
    project_id: Optional[str] = None

class ManualUrlInspectionResponse(BaseModel):
    submitted_url: str
    inspection_status: str # accessible, warning, invalid
    message: str
    main_source: Optional[WebSource] = None
    internal_links: List[WebSource] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    content_hash: Optional[str] = None

class ProcessManualUrlRequest(BaseModel):
    main_source: WebSource
    selected_sublinks: List[WebSource] = Field(default_factory=list)
    discipline: str = "Arquitectura"
    document_type: str = "norma"
    authority: Optional[str] = None
    project_id: Optional[str] = None
    search_prompt: Optional[str] = None
    type_limits: Optional[Dict[str, int]] = None
    max_total: Optional[int] = 15
    translate_to_spanish: bool = True
    translation: Optional[TranslationConfig] = None

class WebSearchHistoryRead(BaseModel):
    id: str
    organization_id: str
    project_id: Optional[str] = None
    user_id: Optional[str] = None
    search_prompt: str
    discipline: str
    document_type: str
    provider_used: str
    detected_language: str
    results_found: List[Dict[str, Any]] = Field(default_factory=list)
    discarded_sources: List[Dict[str, Any]] = Field(default_factory=list)
    selected_sources: List[Dict[str, Any]] = Field(default_factory=list)
    stage_applied: str
    extraction_status: str
    source_extraction_id: Optional[str] = None
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True

class AiWebResearchRequest(BaseModel):
    search_prompt: str = Field(..., description="Prompt, tema o norma a investigar (ej: 'Criterios de accesibilidad OGUC')")
    discipline: str = "Arquitectura"
    document_type: str = "any_web_doc" # any_web_doc, norma, decreto, manual, reglamento, guia, articulo_blog, ficha_fabricante, documento_academico, otro
    authority: Optional[str] = None
    project_id: Optional[str] = None
    search_history_id: Optional[str] = None
    focus_areas: Optional[List[str]] = None # ['evacuacion', 'ancho_puertas', 'resistencia_fuego']
    type_limits: Optional[Dict[str, int]] = None # {'rules': 4, 'tables': 2, 'images': 2, 'symbols': 2, 'equipment': 2}
    max_total: Optional[int] = 12
    selected_sources: List[WebSource] = Field(default_factory=list)
    translate_to_spanish: Optional[bool] = True
    translation: Optional[TranslationConfig] = None

class ManualExtractionCreateRequest(BaseModel):
    source_asset_id: Optional[str] = None
    project_id: Optional[str] = None
    title: str
    document_type: str = "norma"
    authority: Optional[str] = None
    discipline: str = "general"
    source_file_path: Optional[str] = None
    translation: Optional[TranslationConfig] = None

class SourceExtractionRead(SourceExtractionBase):
    id: str
    organization_id: str
    project_id: Optional[str] = None
    source_asset_id: Optional[str] = None
    status: str
    total_items: int
    source_file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SourceExtractionDetailRead(SourceExtractionRead):
    items: List[ExtractedItemRead] = Field(default_factory=list)

class ExtractionCommitRequest(BaseModel):
    approved_item_ids: Optional[List[str]] = None # If None, commits all with review_status == 'accepted' or 'to_confirm'
    target_rule_document_title: Optional[str] = None
    target_rule_document_description: Optional[str] = None

class ExtractionCommitResponse(BaseModel):
    extraction_id: str
    rule_document_id: str
    rules_incorporated_count: int
    knowledge_entries_created_count: int
    message: str


# =========================================================
# SCHEMAS: MOTOR DE REGLAS - DOCUMENTOS Y REGLAS
# =========================================================

class RuleDocumentItemRead(BaseModel):
    id: str
    rule_document_id: str
    extracted_item_id: Optional[str] = None
    item_type: str
    source_origin: str = "document"
    source_reference: Optional[str] = None
    item_nature: str = "official_rule"
    title: str
    code_or_number: Optional[str] = None
    description: Optional[str] = None
    content_text: Optional[str] = None
    ocr_text: Optional[str] = None
    crop_image_path: Optional[str] = None
    target_destination: str
    status: str
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True

class RuleDocumentItemUpdate(BaseModel):
    title: Optional[str] = None
    code_or_number: Optional[str] = None
    description: Optional[str] = None
    content_text: Optional[str] = None
    ocr_text: Optional[str] = None
    source_reference: Optional[str] = None
    item_nature: Optional[str] = None
    status: Optional[str] = None

class RuleDocumentRead(BaseModel):
    id: str
    organization_id: str
    project_id: Optional[str] = None
    source_extraction_id: Optional[str] = None
    source_asset_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    document_type: str
    source_origin: str
    authority: Optional[str] = None
    discipline: str
    version: str
    status: str
    items_count: int
    rules_count: int
    tables_count: int
    images_count: int
    symbols_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class RuleDocumentDetailRead(RuleDocumentRead):
    items: List[RuleDocumentItemRead] = Field(default_factory=list)

class RuleDocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    document_type: Optional[str] = None
    authority: Optional[str] = None
    discipline: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None

class ConfirmRuleDocumentContentRequest(BaseModel):
    confirmed_item_ids: Optional[List[str]] = None

class ConfirmRuleDocumentContentResponse(BaseModel):
    message: str
    document_id: str
    status: str
    confirmed_rules_count: int

class PromoteToBaselineResponse(BaseModel):
    message: str
    document_id: str
    promoted_count: int
    rule_codes: List[str]

class DocumentOcrRequest(BaseModel):
    source_asset_id: Optional[str] = None
    file_path: Optional[str] = None

class DocumentOcrResponse(BaseModel):
    total_pages: int
    full_text: str
    pages: List[Dict[str, Any]]


# =========================================================
# SCHEMAS: BASE DE CONOCIMIENTO DE APOYO / PATRONES VISUALES
# =========================================================

class SupportingKnowledgeItemRead(BaseModel):
    id: str
    organization_id: str
    project_id: Optional[str] = None
    source_asset_id: Optional[str] = None
    source_extraction_id: Optional[str] = None
    extracted_item_id: Optional[str] = None
    item_type: str
    title: str
    code_or_number: Optional[str] = None
    description: Optional[str] = None
    discipline: str = "general"
    page_number: int = 1
    bbox_normalized: List[float] = Field(default_factory=list)
    crop_image_path: Optional[str] = None
    ocr_text: Optional[str] = None
    structured_matrix: Dict[str, Any] = Field(default_factory=dict)
    status: str = "validada"
    validated_by: str = "system"
    validated_at: datetime
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =========================================================
# SCHEMAS: GENERACIÓN DE REGLAS CON IA DESDE OCR
# =========================================================

class GenerateRulesFromOcrRequest(BaseModel):
    ocr_text: str
    discipline: str = "general"
    document_title: Optional[str] = None
    page_number: Optional[int] = None

class GeneratedRuleItem(BaseModel):
    code: str
    title: str
    statement: str
    item_type: str = "rule"
    page_number: int = 1
    duplicate_status: str = "no_match"
    best_match_rule_id: Optional[str] = None
    best_match_rule_code: Optional[str] = None
    best_match_title: Optional[str] = None
    best_match_discipline: Optional[str] = None
    duplicate_reason: Optional[str] = None
    duplicate_confidence: float = 0.0
    blocked_from_acceptance: bool = False

class GenerateRulesFromOcrResponse(BaseModel):
    rules: List[GeneratedRuleItem]
