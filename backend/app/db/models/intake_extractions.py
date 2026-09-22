import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class SourceExtraction(Base):
    """Sesión de extracción estructurada de conocimiento (CON IA: Documento o Web, o SIN IA)."""
    __tablename__ = "source_extractions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    source_asset_id = Column(String(36), ForeignKey("source_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    
    extraction_mode = Column(String(30), default="ai_document", nullable=False) 
    # ai_document (Opción 1 con IA), ai_web_research (Opción 2 con IA), without_ai (Manual sin IA), with_ai (legacy alias)
    
    source_origin = Column(String(50), default="document", nullable=False, index=True) # document, web
    search_query = Column(Text, nullable=True) # Prompt o tema de búsqueda web
    search_citations = Column(JSON, default=list) # Fuentes web, URLs o referencias consultadas
    
    title = Column(String(255), nullable=False)
    document_type = Column(String(50), default="norma", nullable=False) # norma, decreto, manual, reglamento, guia, ficha_tecnica, investigacion_web, otro
    authority = Column(String(150), nullable=True) # e.g. MINVU, SEC, NFPA, INN, SEREMI, Web Research
    discipline = Column(String(50), default="general", nullable=False, index=True)
    source_file_path = Column(String(500), nullable=True)
    source_url = Column(String(500), nullable=True)
    
    status = Column(String(30), default="draft", nullable=False) # draft, extracting, extracted, reviewed, incorporated, archived
    summary = Column(Text, nullable=True)
    total_items = Column(Integer, default=0, nullable=False)
    
    metadata_info = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    items = relationship("ExtractedItem", back_populates="extraction", cascade="all, delete-orphan")


class ExtractedItem(Base):
    """Elemento individual extraído y clasificado (regla, artículo, tabla, imagen, definición, nota)."""
    __tablename__ = "extracted_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    extraction_id = Column(String(36), ForeignKey("source_extractions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    item_type = Column(String(50), nullable=False, index=True)
    # rule, article, chapter, table, image, figure, symbol, text_note, definition, procedure, restriction, requirement, other
    
    candidate_type = Column(String(50), nullable=True, index=True)
    # premise_candidate, rule_candidate, symbol_candidate, table_matrix_candidate, equipment_image_candidate, diagram_candidate, example_candidate
    
    source_origin = Column(String(50), default="document", nullable=False, index=True) # document, web
    source_reference = Column(String(500), nullable=True) # URL o cita normativa / bibliográfica
    item_nature = Column(String(50), default="official_rule", nullable=False) 
    # official_rule (norma oficial), proposed_rule (regla propuesta), support_research (apoyo de investigación), concept, reference
    governance_note = Column(Text, nullable=True) # Nota de gobernanza (e.g. "Investigado vía Web: Requiere validación reforzada")
    
    title = Column(String(255), nullable=False)
    code_or_number = Column(String(100), nullable=True, index=True) # e.g. "Art. 4.1.7", "Capítulo 2", "Tabla 3.1", "REF-WEB-01"
    description = Column(Text, nullable=True)
    content_text = Column(Text, nullable=True)
    derived_text = Column(Text, nullable=True) # Resumen o formulación técnica derivada por IA
    ocr_text = Column(Text, nullable=True)
    caption_or_context = Column(Text, nullable=True) # Caption, texto circundante o contexto de foto/diagrama
    disclaimer_notes = Column(Text, nullable=True) # e.g. "Sin inferencia de conectividad topológica"
    
    crop_image_path = Column(String(500), nullable=True)
    bbox_normalized = Column(JSON, default=list) # [x0, y0, x1, y1]
    page_number = Column(Integer, default=1, nullable=False, index=True)
    discipline = Column(String(50), default="general", nullable=False, index=True)
    source_asset_id = Column(String(36), nullable=True, index=True)
    
    # Separación Visual y Linaje de Derivación
    parent_item_id = Column(String(36), nullable=True, index=True) # ID del elemento padre si fue separado visualmente
    is_derived = Column(Boolean, default=False, nullable=False, index=True)
    split_mode = Column(String(50), nullable=True, index=True) # visual_split, manual_split, crop_current_item
    
    evidence_references = Column(JSON, default=list) # Enlaces a DocumentStructuralNode, ExtractedText o regiones
    technical_parameters = Column(JSON, default=dict) # Parámetros técnicos específicos (line_count, ratings, etc.)
    
    target_destination = Column(String(30), default="rules_engine", nullable=False) # rules_engine, knowledge_base, both
    review_status = Column(String(30), default="draft", nullable=False, index=True) # draft, editado, por_confirmar, validada, eliminado, to_confirm, accepted, rejected
    
    # Deduplicación y Matching contra Motor de Reglas QA/QC
    duplicate_status = Column(String(50), default="no_match", nullable=False, index=True)
    # no_match, exact_match_existing_rule, likely_duplicate_existing_rule, related_existing_rule
    best_match_rule_id = Column(String(100), nullable=True)
    best_match_rule_code = Column(String(100), nullable=True)
    best_match_title = Column(String(255), nullable=True)
    best_match_discipline = Column(String(50), nullable=True)
    duplicate_reason = Column(Text, nullable=True)
    duplicate_confidence = Column(Float, default=0.0, nullable=False)
    blocked_from_acceptance = Column(Boolean, default=False, nullable=False, index=True)

    # Estado de Completitud y Enriquecimiento Asistido (Multimodal)
    completeness_status = Column(String(50), default="missing_data", nullable=False, index=True)
    # complete, partial, missing_data, web_suggested
    enrichment_status = Column(String(50), default="not_enriched", nullable=False, index=True)
    # not_enriched, suggestion_found, manual_completed
    requires_validation = Column(Boolean, default=True, nullable=False, index=True)
    enriched_from_web = Column(Boolean, default=False, nullable=False)
    enrichment_method = Column(String(100), nullable=True)
    # web_reference_lookup, technical_ontology_match, ocr_region_extraction, manual_input, hybrid_research
    match_confidence = Column(Float, default=0.0, nullable=False)
    suggested_title = Column(String(255), nullable=True)
    suggested_description = Column(Text, nullable=True)
    suggested_function = Column(Text, nullable=True)
    suggested_source_url = Column(String(500), nullable=True)
    suggested_source_label = Column(String(255), nullable=True)

    # Trazabilidad y Linaje Granular por Campo (Field Provenance)
    field_provenance = Column(JSON, default=dict)

    structured_matrix = Column(JSON, default=dict) # Para tablas o matrices estructuradas
    validated_at = Column(DateTime, nullable=True)
    validated_by = Column(String(100), nullable=True)
    
    metadata_payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    extraction = relationship("SourceExtraction", back_populates="items")
    structured_table = relationship("StructuredTable", back_populates="extracted_item", uselist=False, cascade="all, delete-orphan")
    structured_symbol = relationship("StructuredSymbol", back_populates="extracted_item", uselist=False, cascade="all, delete-orphan")
    structured_equipment = relationship("StructuredEquipment", back_populates="extracted_item", uselist=False, cascade="all, delete-orphan")
    structured_rule_premise = relationship("StructuredRulePremise", back_populates="extracted_item", uselist=False, cascade="all, delete-orphan")

    @property
    def translated_fields(self) -> Dict[str, Any]:
        return (self.metadata_payload or {}).get("translated_fields", {})

    @property
    def source_fields(self) -> Dict[str, Any]:
        tech = self.technical_parameters or {}
        return {
            "title": self.title,
            "description": self.description,
            "content_text": self.content_text,
            "ocr_text": self.ocr_text,
            "caption_or_context": self.caption_or_context,
            "technical_function": tech.get("function") or tech.get("function_or_role")
        }

    @property
    def source_language(self) -> str:
        return (self.metadata_payload or {}).get("source_language") or "en"

    @property
    def target_language(self) -> str:
        return (self.metadata_payload or {}).get("target_language") or "es"

    @property
    def translation_status(self) -> str:
        return (self.metadata_payload or {}).get("translation_status") or "not_required"

    @property
    def presentation_language(self) -> str:
        return (self.metadata_payload or {}).get("presentation_language") or self.target_language

    @property
    def effective_fields(self) -> Dict[str, Any]:
        src = dict(self.source_fields)
        trans = dict(self.translated_fields or {})
        status = self.translation_status

        if status == "completed":
            for k, v in trans.items():
                if v is not None and str(v).strip():
                    src[k] = v
        return src


class RuleDocument(Base):
    """Documento normativo o fuente técnica incorporada al Motor de Reglas QA/QC."""
    __tablename__ = "rule_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    source_extraction_id = Column(String(36), ForeignKey("source_extractions.id", ondelete="SET NULL"), nullable=True)
    source_asset_id = Column(String(36), ForeignKey("source_assets.id", ondelete="SET NULL"), nullable=True)
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    document_type = Column(String(50), default="norma", nullable=False) # norma, decreto, manual, reglamento, guia, ficha_tecnica, investigacion_web, otro
    source_origin = Column(String(50), default="con_ia", nullable=False) # con_ia_documento, con_ia_web, sin_ia, manual, importado
    authority = Column(String(150), nullable=True) # MINVU, SEC, Web Research, etc.
    discipline = Column(String(50), default="general", nullable=False, index=True)
    version = Column(String(50), default="1.0", nullable=False)
    
    status = Column(String(30), default="active", nullable=False, index=True) # active, draft, archived
    
    items_count = Column(Integer, default=0, nullable=False)
    rules_count = Column(Integer, default=0, nullable=False)
    tables_count = Column(Integer, default=0, nullable=False)
    images_count = Column(Integer, default=0, nullable=False)
    symbols_count = Column(Integer, default=0, nullable=False)
    
    metadata_info = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    items = relationship("RuleDocumentItem", back_populates="document", cascade="all, delete-orphan")


class RuleDocumentItem(Base):
    """Elemento específico de regla o referencia dentro de un documento del Motor de Reglas."""
    __tablename__ = "rule_document_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_document_id = Column(String(36), ForeignKey("rule_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    extracted_item_id = Column(String(36), nullable=True)
    
    item_type = Column(String(50), nullable=False, index=True)
    source_origin = Column(String(50), default="document", nullable=False) # document, web
    source_reference = Column(String(500), nullable=True)
    item_nature = Column(String(50), default="official_rule", nullable=False)
    
    title = Column(String(255), nullable=False)
    code_or_number = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    content_text = Column(Text, nullable=True)
    ocr_text = Column(Text, nullable=True)
    crop_image_path = Column(String(500), nullable=True)
    
    target_destination = Column(String(30), default="rules_engine", nullable=False)
    status = Column(String(30), default="active", nullable=False) # active, disabled
    
    metadata_payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    document = relationship("RuleDocument", back_populates="items")


class SupportingKnowledgeItem(Base):
    """Elemento visual de apoyo técnico y patrones reutilizables (símbolos, sellos, firmas, figuras, tablas)."""
    __tablename__ = "supporting_knowledge_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    source_asset_id = Column(String(36), ForeignKey("source_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    source_extraction_id = Column(String(36), ForeignKey("source_extractions.id", ondelete="SET NULL"), nullable=True)
    extracted_item_id = Column(String(36), nullable=True)
    
    item_type = Column(String(50), nullable=False, index=True) # simbolo, foto, imagen, tabla, figura, sello, firma, leyenda, vineta, otro
    title = Column(String(255), nullable=False)
    code_or_number = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    discipline = Column(String(50), default="general", nullable=False, index=True)
    
    page_number = Column(Integer, default=1, nullable=False)
    bbox_normalized = Column(JSON, default=list) # [x0, y0, x1, y1]
    crop_image_path = Column(String(500), nullable=True)
    ocr_text = Column(Text, nullable=True)
    structured_matrix = Column(JSON, default=dict) # Para tablas estructuradas (filas, columnas, celdas)
    
    status = Column(String(30), default="validada", nullable=False) # draft, editado, por_confirmar, validada, archivado
    validated_by = Column(String(100), default="system", nullable=False)
    validated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    metadata_payload = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# =========================================================
# MODELOS DE PERSISTENCIA ESTRUCTURADA INCREMENTAL Y TIPADA
# =========================================================

class StructuredTable(Base):
    """Persistencia estructurada tipada de tablas y matrices extraídas."""
    __tablename__ = "structured_tables"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    extracted_item_id = Column(String(36), ForeignKey("extracted_items.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    table_code = Column(String(100), nullable=True, index=True)
    caption = Column(Text, nullable=True)
    num_rows = Column(Integer, default=0, nullable=False)
    num_cols = Column(Integer, default=0, nullable=False)
    headers = Column(JSON, default=list, nullable=False)
    rows_data = Column(JSON, default=list, nullable=False)
    matrix_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    extracted_item = relationship("ExtractedItem", back_populates="structured_table")


class StructuredSymbol(Base):
    """Persistencia estructurada tipada de símbolos, bloques CAD y elementos de leyenda."""
    __tablename__ = "structured_symbols"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    extracted_item_id = Column(String(36), ForeignKey("extracted_items.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    symbol_name = Column(String(200), nullable=False, index=True)
    standard_family = Column(String(100), nullable=True, index=True) # ISA-5.1, DIN, NCh, NFPA, etc.
    discipline = Column(String(50), default="general", nullable=False, index=True)
    category = Column(String(100), nullable=True, index=True)
    svg_path = Column(Text, nullable=True)
    crop_image_path = Column(String(500), nullable=True)
    confidence_score = Column(Float, default=1.0, nullable=False)
    
    # Nuevos campos de estrategia dual, contexto y gobernanza (Fase 1 Piping)
    source_render_mode = Column(String(20), default="raster", nullable=False, index=True) # vector, raster, mixed
    layout_context = Column(String(30), default="inside_table", nullable=False, index=True) # inside_table, semi_structured_legend, free_layout, manual_crop
    context_association_mode = Column(String(30), default="row_band", nullable=False, index=True) # row_band, lateral_band, caption_band, manual_assignment
    standard_reference = Column(String(150), nullable=True) # ej. "Norma ISA S5.1 / ASME B16.34"
    canonical_symbol_family = Column(String(50), default="valves", nullable=False, index=True) # valves, instruments, pumps, fittings, line_types, other
    visual_variant_group_id = Column(String(36), nullable=True, index=True)
    estimated_physical_size_mm = Column(JSON, default=dict, nullable=False) # {"width_mm": 7.2, "height_mm": 6.8, "aspect_ratio": 1.05, "stroke_density": 0.18}
    reused_for_matching_count = Column(Integer, default=0, nullable=False)
    false_positive_count = Column(Integer, default=0, nullable=False)
    human_validation_notes = Column(Text, nullable=True)

    # Linaje estructural tabla-fila-columna
    source_table_id = Column(String(36), nullable=True, index=True)
    row_index = Column(Integer, nullable=True)
    col_index = Column(Integer, nullable=True)
    cell_bbox = Column(JSON, nullable=True) # [x0, y0, x1, y1] normalizado
    row_bbox = Column(JSON, nullable=True)  # [x0, y0, x1, y1] normalizado de la franja/fila

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    extracted_item = relationship("ExtractedItem", back_populates="structured_symbol")


class StructuredEquipment(Base):
    """Persistencia estructurada tipada de equipos, instrumentos y componentes físicos."""
    __tablename__ = "structured_equipment"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    extracted_item_id = Column(String(36), ForeignKey("extracted_items.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    tag_code = Column(String(100), nullable=False, index=True)
    equipment_type = Column(String(100), nullable=False, index=True)
    service_description = Column(Text, nullable=True)
    manufacturer = Column(String(150), nullable=True)
    model_number = Column(String(150), nullable=True)
    rated_capacity = Column(String(100), nullable=True)
    operating_parameters = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    extracted_item = relationship("ExtractedItem", back_populates="structured_equipment")


class StructuredRulePremise(Base):
    """Persistencia estructurada tipada de premisas técnicas, reglas normativas y afirmaciones de auditoría."""
    __tablename__ = "structured_rules_premises"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    extracted_item_id = Column(String(36), ForeignKey("extracted_items.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    rule_code = Column(String(100), nullable=False, index=True)
    statement = Column(Text, nullable=False)
    rule_type = Column(String(50), default="mandatory_rule", nullable=False, index=True)
    discipline = Column(String(50), default="general", nullable=False, index=True)
    severity = Column(String(30), default="warning", nullable=False, index=True)
    evaluation_logic = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    extracted_item = relationship("ExtractedItem", back_populates="structured_rule_premise")


class WebSearchHistory(Base):
    """Registro persistente de auditoría y trazabilidad para búsquedas web e ingesta documental."""
    __tablename__ = "web_search_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(String(100), nullable=True, index=True)

    search_prompt = Column(Text, nullable=False)
    discipline = Column(String(50), default="general", nullable=False, index=True)
    document_type = Column(String(50), default="any_web_doc", nullable=False)
    provider_used = Column(String(50), default="duckduckgo", nullable=False)
    detected_language = Column(String(20), default="es", nullable=False)

    results_found = Column(JSON, default=list, nullable=False)
    discarded_sources = Column(JSON, default=list, nullable=False)
    selected_sources = Column(JSON, default=list, nullable=False)
    
    stage_applied = Column(String(50), default="stage_1_strict", nullable=False)
    extraction_status = Column(String(30), default="searched", nullable=False, index=True) # searched, extracted, failed, discarded
    source_extraction_id = Column(String(36), ForeignKey("source_extractions.id", ondelete="SET NULL"), nullable=True, index=True)
    
    metadata_payload = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

