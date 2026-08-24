import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean, ForeignKey
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
    page_number = Column(Integer, default=1, nullable=False)
    evidence_references = Column(JSON, default=list) # Enlaces a DocumentStructuralNode, ExtractedText o regiones
    technical_parameters = Column(JSON, default=dict) # Parámetros técnicos específicos (line_count, ratings, etc.)
    
    target_destination = Column(String(30), default="rules_engine", nullable=False) # rules_engine, knowledge_base, both
    review_status = Column(String(30), default="draft", nullable=False, index=True) # draft, editado, por_confirmar, validada, eliminado, to_confirm, accepted, rejected
    
    structured_matrix = Column(JSON, default=dict) # Para tablas o matrices estructuradas
    validated_at = Column(DateTime, nullable=True)
    validated_by = Column(String(100), nullable=True)
    
    metadata_payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    extraction = relationship("SourceExtraction", back_populates="items")


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
