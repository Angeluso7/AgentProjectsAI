import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.db.session import Base


class SymbolTemplateVersion(Base):
    """
    Representa una variante gráfica/técnica aprobada de una identidad simbólica canónica.
    Permite versionar la representación visual, rasgos geométricos y descriptores
    sin alterar el código canónico del símbolo.
    """
    __tablename__ = "symbol_template_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol_template_id = Column(String(36), ForeignKey("symbol_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    approval_status = Column(String(30), default="approved", nullable=False, index=True) # draft, pending_review, approved, rejected, retired
    source_kind = Column(String(50), default="normative_document", nullable=False) # normative_document, project_legend, approved_manual_capture
    
    canonical_crop_path = Column(String(500), nullable=True)
    canonical_crop_hash = Column(String(64), nullable=True)
    normalized_representation = Column(JSON, default=dict) # Metadatos de rasterización normalizada
    
    # Políticas de invarianza y orientación
    # rotation_invariant, rotation_equivalent_180, orientation_sensitive, mirror_allowed, mirror_forbidden
    orientation_policy = Column(String(50), default="rotation_equivalent_180", nullable=False)
    scale_policy = Column(String(50), default="isotropic_bounded", nullable=False)
    
    # Firmas y descriptores explicables
    geometric_signature = Column(JSON, default=dict) # Conteo y métricas de primitivas
    perceptual_signature = Column(JSON, default=dict) # Hu moments, radial profile, dHash
    matcher_thresholds = Column(JSON, default=dict) # Umbrales específicos de la versión
    
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    template = relationship("SymbolTemplate", back_populates="versions")
    geometric_features = relationship("SymbolGeometricFeature", back_populates="template_version", cascade="all, delete-orphan")
    source_evidence = relationship("SymbolSourceEvidence", back_populates="template_version", uselist=False, cascade="all, delete-orphan")


class SymbolGeometricFeature(Base):
    """
    Representa una primitiva geométrica explicable, normalizada y medible de un símbolo.
    Reemplaza booleanos simplistas por parámetros dimensionales, relativos y grupos de relación.
    """
    __tablename__ = "symbol_geometric_features"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol_template_version_id = Column(String(36), ForeignKey("symbol_template_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Tipo de primitiva: line_segment, arc, circle, ellipse, rectangle, polygon, triangle, diagonal, arrowhead, connection_port, junction, filled_region, symmetry_axis
    feature_type = Column(String(50), nullable=False, index=True)
    feature_count = Column(Integer, default=1, nullable=False)
    feature_parameters = Column(JSON, default=dict, nullable=False) # Coordenadas normalizadas, radio, vértices
    normalized_bbox = Column(JSON, default=list, nullable=False) # [x0, y0, x1, y1] relativo al crop
    relative_position = Column(String(50), nullable=True) # top, center, left, right, bottom
    orientation_degrees = Column(Float, nullable=True) # Orientación de la primitiva
    confidence = Column(Float, default=1.0, nullable=False)
    relationship_group = Column(String(50), nullable=True) # valve_body, actuator, port
    extractor_version = Column(String(30), default="v1.0", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    template_version = relationship("SymbolTemplateVersion", back_populates="geometric_features")


class SymbolFeatureRelation(Base):
    """
    Relación espacial y topológica entre dos rasgos geométricos del mismo símbolo.
    Garantiza que la estructura interna (ej. vástago conectado a vértice de triángulos)
    sea verificable de manera determinista.
    """
    __tablename__ = "symbol_feature_relations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_feature_id = Column(String(36), ForeignKey("symbol_geometric_features.id", ondelete="CASCADE"), nullable=False, index=True)
    target_feature_id = Column(String(36), ForeignKey("symbol_geometric_features.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # contains, intersects, touches, crosses, connected_to, aligned_with, concentric_with, symmetric_to, adjacent_to
    relation_type = Column(String(50), nullable=False, index=True)
    confidence = Column(Float, default=1.0, nullable=False)
    relation_parameters = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SymbolSourceEvidence(Base):
    """
    Trazabilidad inmutable de la versión de plantilla hacia el documento, lámina, celda y recorte original.
    Permite auditar el origen normativo o documental de cada símbolo.
    """
    __tablename__ = "symbol_source_evidences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol_template_version_id = Column(String(36), ForeignKey("symbol_template_versions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    source_document_id = Column(String(36), nullable=True, index=True)
    source_document_hash = Column(String(64), nullable=True)
    # synthetic, redacted_real, real_authorized
    evidence_kind = Column(String(30), default="synthetic", nullable=False, index=True)
    page_number = Column(Integer, default=1, nullable=False)
    sheet_id = Column(String(36), nullable=True)
    table_id = Column(String(36), nullable=True)
    cell_id = Column(String(36), nullable=True)
    
    bbox_normalized = Column(JSON, default=list, nullable=False) # [x0, y0, x1, y1] en página
    cell_bbox = Column(JSON, nullable=True)
    inner_drawing_bbox = Column(JSON, nullable=True)
    symbol_crop_bbox = Column(JSON, nullable=True)
    crop_image_path = Column(String(500), nullable=True)
    crop_image_hash = Column(String(64), nullable=True)
    source_excerpt = Column(Text, nullable=True)
    grid_source = Column(String(30), nullable=True)
    geometric_confidence = Column(Float, default=1.0, nullable=False)
    
    source_standard_or_project = Column(String(150), nullable=True)
    source_revision = Column(String(50), nullable=True)
    source_date = Column(String(50), nullable=True)
    extraction_run_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    template_version = relationship("SymbolTemplateVersion", back_populates="source_evidence")


class SymbolReviewDecision(Base):
    """
    Registro formal de curación humana (HITL) para candidatos, versiones de plantilla u ocurrencias.
    Conserva la justificación técnica y snapshot de estado para reproducibilidad total.
    """
    __tablename__ = "symbol_review_decisions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # candidate, template_version, occurrence
    subject_type = Column(String(30), nullable=False, index=True)
    subject_id = Column(String(36), nullable=False, index=True)
    
    # approve, reject, mark_unknown, link_template, create_template, retire_template, override_match
    decision = Column(String(50), nullable=False, index=True)
    reviewer_id = Column(String(100), nullable=False)
    rationale = Column(Text, nullable=True)
    evidence_snapshot = Column(JSON, default=dict)
    previous_state = Column(JSON, default=dict)
    new_state = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SymbolUnknownResearchCase(Base):
    """
    Registro de investigación técnica para símbolos con geometría real válida
    que no coinciden con ninguna plantilla canónica activa en el catálogo.
    """
    __tablename__ = "symbol_unknown_research_cases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol_occurrence_id = Column(String(36), ForeignKey("detected_symbols.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # unknown, queued_for_research, sources_found, proposed_identity, human_validated, research_exhausted, unresolved
    status = Column(String(40), default="unknown", nullable=False, index=True)
    search_query = Column(String(255), nullable=True)
    source_urls = Column(JSON, default=list)
    proposed_name = Column(String(200), nullable=True)
    proposed_standard_reference = Column(String(150), nullable=True)
    research_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    occurrence = relationship("DetectedSymbol")
