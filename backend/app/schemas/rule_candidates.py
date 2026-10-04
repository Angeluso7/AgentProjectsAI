from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class RuleApplicabilityItemResponse(BaseModel):
    """Representación canónica de una relación de aplicabilidad de regla."""
    discipline: str
    topic: str
    approval_status: str
    role: str = "primary"


class PromoteRuleCandidateRequest(BaseModel):
    """Contrato de payload para la promoción de regla candidata a Baseline QA/QC."""
    decision: Literal["approve", "reject"] = Field(
        default="approve",
        description="Decisión de revisión HITL: 'approve' para promover o 'reject' para descartar."
    )
    action: Optional[Literal["promote_and_activate", "promote_for_review"]] = Field(
        default=None,
        description="Acción específica: 'promote_and_activate' (admin/audit_lead) o 'promote_for_review' (auditor)."
    )
    reviewer_rationale: str = Field(
        ...,
        min_length=3,
        description="Justificación técnica obligatoria del revisor."
    )
    rule_code: str = Field(
        ...,
        description="Código identificador único de la regla (ej: PIP-SYM-001)."
    )
    title: str = Field(
        ...,
        min_length=2,
        description="Título o nombre técnico de la regla."
    )
    severity: str = Field(
        default="medium",
        description="Nivel de severidad por defecto (critical, high, major, medium, low, info)."
    )
    discipline_ids: List[str] = Field(
        ...,
        min_items=1,
        description="Lista de códigos o UUIDs de especialidades técnicas aplicables (ej: ['PIPING'])."
    )
    topic_ids: List[str] = Field(
        ...,
        min_items=1,
        description="Lista de códigos o UUIDs de puntos de revisión aplicables (ej: ['PID_SYMBOLS'])."
    )
    execution_phase: int = Field(
        default=6,
        ge=1,
        le=9,
        description="Fase de ejecución topológica del motor de reglas (1 a 9)."
    )
    enabled: bool = Field(
        default=True,
        description="Si la regla debe quedar habilitada para evaluación."
    )


class PromoteRuleCandidateResponse(BaseModel):
    """Respuesta estructurada tras la promoción de una regla candidata."""
    candidate_id: str
    candidate_status: str = Field(
        ...,
        description="Estado del candidato: 'promoted', 'promoted_draft', 'rejected', 'superseded'."
    )
    rule_definition_id: Optional[str] = Field(
        default=None,
        description="UUID de la RuleDefinition creada o vinculada."
    )
    rule_code: Optional[str] = Field(
        default=None,
        description="Código normalizado de la regla en el catálogo."
    )
    rule_definition_status: Optional[str] = Field(
        default=None,
        description="Estado de la definición de regla ('approved', 'proposed', 'draft', 'rejected')."
    )
    baseline_status: Optional[str] = Field(
        default=None,
        description="Estado en el baseline ('active', 'pending_approval', 'inactive')."
    )
    applicabilities: List[RuleApplicabilityItemResponse] = Field(
        default_factory=list,
        description="Listado de relaciones de aplicabilidad canónicas registradas."
    )
    already_promoted: bool = Field(
        default=False,
        description="Indica si la regla ya había sido promovida con anterioridad (idempotente)."
    )
    message: Optional[str] = None
