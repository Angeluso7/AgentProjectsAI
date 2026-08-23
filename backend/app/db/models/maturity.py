import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.db.session import Base

class ProjectMaturityProfile(Base):
    """
    Perfil de Madurez o Suficiencia Informacional por Proyecto y Etapa.
    Evalúa la completitud documental, cobertura normativa, calibración de reglas,
    resolución de observaciones/RFIs, base de conocimiento validada y uso por el asistente.
    """
    __tablename__ = "project_maturity_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    stage = Column(String(50), nullable=False, index=True) # e.g. "Ingeniería Básica", "Ingeniería de Detalle"
    
    # Score y Nivel Cualitativo
    overall_score = Column(Float, default=0.0, nullable=False) # 0.0 a 100.0
    maturity_level = Column(String(30), default="insufficient", nullable=False, index=True)
    # insufficient (<35), basic (35-59), intermediate (60-79), advanced (80-94), exhaustive (>=95)
    
    target_level = Column(String(30), default="advanced", nullable=False)
    is_target_achieved = Column(Boolean, default=False, nullable=False)
    
    # Desglose Explicable por Dimensiones y Disciplinas
    dimension_scores = Column(JSON, default=dict, nullable=False)
    # {
    #   "documental_plans": {"score": 75.0, "weight": 0.25, "weighted_score": 18.75, "details": "..."},
    #   "normative_rules": {"score": 60.0, "weight": 0.20, "weighted_score": 12.00, "details": "..."},
    #   "extractions_metadata": {"score": 70.0, "weight": 0.20, "weighted_score": 14.00, "details": "..."},
    #   "resolution_rfis": {"score": 80.0, "weight": 0.15, "weighted_score": 12.00, "details": "..."},
    #   "knowledge_rag": {"score": 50.0, "weight": 0.20, "weighted_score": 10.00, "details": "..."}
    # }
    
    discipline_scores = Column(JSON, default=dict, nullable=False)
    # {
    #   "architecture": {"score": 85.0, "status": "adequate", "doc_count": 5, "rule_count": 8},
    #   "structures": {"score": 40.0, "status": "insufficient", "doc_count": 1, "rule_count": 3},
    #   "mep": {"score": 60.0, "status": "partial", "doc_count": 2, "rule_count": 4}
    # }
    
    # Brechas Críticas y Accionables
    critical_gaps = Column(JSON, default=list, nullable=False)
    # [
    #   {
    #     "id": "gap-01",
    #     "dimension": "documental_plans",
    #     "discipline": "structures",
    #     "title": "Falta Memoria de Cálculo Sísmico",
    #     "description": "El proyecto no cuenta con memoria de cálculo estructural requerida para la etapa.",
    #     "impact_rationale": "Impide la verificación de esfuerzos en muros y fundaciones.",
    #     "priority": "critical",
    #     "blocked_rules_count": 4,
    #     "blocked_disciplines": ["structures"],
    #     "is_resolved": false
    #   }
    # ]
    
    # Ruta Sugerida de Adquisición de Información
    acquisition_routes = Column(JSON, default=list, nullable=False)
    # [
    #   {
    #     "id": "route-01",
    #     "gap_id": "gap-01",
    #     "gap_title": "Memoria de Cálculo Sísmico",
    #     "suggested_source_type": "calculation_memory",
    #     "suggested_repository": "Repositorio de Ingeniería Estructural",
    #     "intake_method": "Intake Documental (PDF/Excel)",
    #     "suggested_responsible": "Ingeniero Calculista / Proyectista Estructural",
    #     "target_discipline": "structures",
    #     "unlock_impact": "Desbloquea 4 reglas de diseño sísmico y permite emitir veredicto estructural.",
    #     "estimated_score_gain": 12.5,
    #     "status": "pending"
    #   }
    # ]
    
    # Resumen de Información Adquirida y Validada
    acquired_knowledge_summary = Column(JSON, default=dict, nullable=False)
    # {
    #   "available_documents_count": 8,
    #   "validated_evidence_count": 7,
    #   "approved_kb_items_count": 4,
    #   "closed_rfis_count": 2,
    #   "recently_acquired_items": [
    #     {"title": "OGUC Art. 4.1.7", "origin_type": "normative_intake", "approved_at": "2026-08-23T00:00:00Z"}
    #   ]
    # }
    
    # Resumen de Uso del Asistente RAG en el Proyecto
    assistant_usage_summary = Column(JSON, default=dict, nullable=False)
    # {
    #   "total_interactions": 6,
    #   "project_chunks_used_count": 14,
    #   "top_used_knowledge_items": [{"id": "...", "title": "...", "use_count": 3}],
    #   "average_confidence": 0.92,
    #   "estimated_savings_usd": 0.045
    # }
    
    # Diagnóstico de Capacidad de Revisión del Sistema
    review_capability_assessment = Column(JSON, default=dict, nullable=False)
    # {
    #   "auditable_scope": "Revisión arquitectónica y accesibilidad universal completas.",
    #   "partially_auditable_scope": "Instalaciones sanitarias básicas.",
    #   "blind_blocked_scope": "Verificación estructural bloqueada por falta de memoria."
    # }
    
    # Evolución Temporal (Delta con evaluación previa)
    delta_summary = Column(JSON, default=dict, nullable=False)
    # {
    #   "previous_score": 42.0,
    #   "score_delta": 18.0,
    #   "previous_level": "basic",
    #   "level_changed": true,
    #   "newly_resolved_gaps_count": 2,
    #   "evaluation_date": "2026-08-23T01:40:00Z"
    # }
    
    evaluated_by = Column(String(100), default="system_maturity_engine", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    organization = relationship("Organization")
    project = relationship("Project")
