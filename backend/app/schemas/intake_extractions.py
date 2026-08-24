from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

# =========================================================
# SCHEMAS: ELEMENTOS EXTRAÍDOS (EXTRACTED ITEMS)
# =========================================================

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
    crop_image_path: Optional[str] = None
    bbox_normalized: List[float] = Field(default_factory=list)
    page_number: int = 1
    evidence_references: List[str] = Field(default_factory=list)
    technical_parameters: Dict[str, Any] = Field(default_factory=dict)
    target_destination: str = "rules_engine" # rules_engine, knowledge_base, both
    review_status: str = "draft" # draft, editado, por_confirmar, validada, eliminado, to_confirm, accepted, rejected
    
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
    target_destination: Optional[str] = None
    review_status: Optional[str] = None
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

class ExtractedItemRead(ExtractedItemBase):
    id: str
    extraction_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TechnicalInterpretationCandidateRead(ExtractedItemRead):
    pass


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

class AiWebResearchRequest(BaseModel):
    search_prompt: str = Field(..., description="Prompt, tema o norma a investigar (ej: 'Criterios de accesibilidad OGUC')")
    discipline: str = "Arquitectura"
    document_type: str = "norma" # norma, decreto, manual, reglamento, guia, otro
    authority: Optional[str] = "MINVU / Web Research"
    project_id: Optional[str] = None
    focus_areas: Optional[List[str]] = None # ['evacuacion', 'ancho_puertas', 'resistencia_fuego']

class ManualExtractionCreateRequest(BaseModel):
    source_asset_id: Optional[str] = None
    project_id: Optional[str] = None
    title: str
    document_type: str = "norma"
    authority: Optional[str] = None
    discipline: str = "general"
    source_file_path: Optional[str] = None

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

class GenerateRulesFromOcrResponse(BaseModel):
    rules: List[GeneratedRuleItem]
