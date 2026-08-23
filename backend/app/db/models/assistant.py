import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class AssistantInteraction(Base):
    """
    Registro inmutable y trazable de cada interacción asistida por IA.
    Registra el tipo de tarea, contexto de proyecto, RAG recuperado,
    motor y tier ejecutado, si hubo escalamiento, resultado y feedback HITL.
    """
    __tablename__ = "assistant_interactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Tipo de tarea asistida
    task_type = Column(String(50), nullable=False, index=True)
    # e.g. normative_query, rule_suggestion, completeness_assistance, document_classification,
    # review_support, observation_rfi_draft, finding_explanation, stage_synthesis

    user_prompt = Column(Text, nullable=False)
    resolved_prompt = Column(Text, nullable=True) # Prompt final enriquecido con RAG
    
    stage = Column(String(50), nullable=True, index=True) # e.g. "Ingeniería Básica"
    discipline = Column(String(50), nullable=True, index=True) # e.g. "architecture", "structural"
    
    # Trazabilidad RAG exacta
    retrieved_knowledge_ids = Column(JSON, default=list, nullable=False) # ["uuid1", "uuid2"]
    retrieved_chunks = Column(JSON, default=list, nullable=False) # [{"chunk_id": "...", "title": "...", "snippet": "...", "domain": "..."}]
    
    # Routing de Motores & Tiers
    initial_tier = Column(Integer, default=1, nullable=False) # 1=Local/Gratis, 2=Intermedio, 3=Premium
    executed_tier = Column(Integer, default=1, nullable=False)
    engine_model_used = Column(String(100), nullable=False) # e.g. "fastapi_rule_reasoner", "google_gemini_flash", "openai_gpt4o"
    
    # Escalamiento dinámico
    was_escalated = Column(Boolean, default=False, nullable=False)
    escalation_reason = Column(String(255), nullable=True) # e.g. "critical_severity", "low_confidence", "ambiguous_context"
    
    # Resultado generado
    generated_response = Column(Text, nullable=False)
    structured_output = Column(JSON, default=dict, nullable=False) # Objeto JSON estructurado según la tarea
    confidence_score = Column(Float, default=1.0, nullable=False)
    cost_estimate_usd = Column(Float, default=0.0, nullable=False)
    
    # Ciclo de feedback y trazabilidad HITL (Human-In-The-Loop)
    feedback_status = Column(String(30), default="pending", nullable=False, index=True)
    # pending, accepted, edited, rejected
    feedback_payload = Column(JSON, default=dict, nullable=False) # {"user_notes": "...", "edited_content": "..."}
    
    user_id = Column(String(100), default="system", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    organization = relationship("Organization")
    project = relationship("Project")
