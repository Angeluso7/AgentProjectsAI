from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.knowledge_base import KnowledgeSearchResultItem

class AssistantTaskTypeEnum(str, Enum):
    normative_query = "normative_query"
    rule_suggestion = "rule_suggestion"
    completeness_assistance = "completeness_assistance"
    document_classification = "document_classification"
    review_support = "review_support"
    observation_rfi_draft = "observation_rfi_draft"
    finding_explanation = "finding_explanation"
    stage_synthesis = "stage_synthesis"
    symbol_clarification = "symbol_clarification"

class AssistantExecutionRequest(BaseModel):
    task_type: AssistantTaskTypeEnum = Field(..., description="Tipo canónico de tarea asistida")
    prompt: str = Field(..., min_length=2, description="Consulta, requerimiento o instrucción para el asistente")
    project_id: Optional[str] = Field(None, description="ID del proyecto activo (opcional)")
    stage: Optional[str] = Field(None, description="Etapa del proyecto (e.g. 'Ingeniería Básica')")
    discipline: Optional[str] = Field(None, description="Disciplina involucrada (e.g. 'architecture', 'structural')")
    context_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadatos o entidad objetivo (hallazgo, entregable, etc.)")
    force_tier: Optional[int] = Field(None, description="Forzar tier de motor (1=Gratis/Local, 2=Intermedio, 3=Premium)")
    allow_escalation: bool = Field(True, description="Permite escalamiento automático si hay criticidad o baja confianza")

class AssistantExecutionResponse(BaseModel):
    interaction_id: str
    task_type: str
    generated_response: str
    structured_output: Optional[Dict[str, Any]] = None
    confidence_score: float
    tier_used: int
    engine_model_used: str
    was_escalated: bool
    escalation_reason: Optional[str] = None
    cost_estimate_usd: float
    retrieved_sources: List[KnowledgeSearchResultItem] = []

class AssistantFeedbackRequest(BaseModel):
    status: str = Field(..., description="accepted, edited, rejected")
    feedback_notes: Optional[str] = Field(None, description="Observaciones o correcciones del auditor")
    edited_payload: Optional[Dict[str, Any]] = Field(None, description="Versión editada/corregida del resultado")

class AssistantInteractionRead(BaseModel):
    id: str
    organization_id: str
    project_id: Optional[str] = None
    task_type: str
    user_prompt: str
    resolved_prompt: Optional[str] = None
    stage: Optional[str] = None
    discipline: Optional[str] = None
    retrieved_knowledge_ids: List[str] = []
    retrieved_chunks: List[Dict[str, Any]] = []
    initial_tier: int
    executed_tier: int
    engine_model_used: str
    was_escalated: bool
    escalation_reason: Optional[str] = None
    generated_response: str
    structured_output: Dict[str, Any] = {}
    confidence_score: float
    cost_estimate_usd: float
    feedback_status: str
    feedback_payload: Dict[str, Any] = {}
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AssistantTaskCatalogItem(BaseModel):
    task_type: str
    name: str
    description: str
    default_tier: int
    default_engine: str
    capabilities: List[str]
    escalation_triggers: List[str]
