from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class RuleInput:
    """Contenedor unificado de evidencias y extracciones provistas a las reglas."""
    document_id: str
    sheet_id: Optional[str] = None
    document: Optional[Any] = None
    sheet: Optional[Any] = None
    title_block: Optional[Any] = None
    tables: List[Any] = field(default_factory=list)
    cells_by_table: Dict[str, List[Any]] = field(default_factory=dict)
    symbols: List[Any] = field(default_factory=list)
    texts: List[Any] = field(default_factory=list)
    regions: List[Any] = field(default_factory=list)
    normative_criteria: List[Any] = field(default_factory=list)

@dataclass
class RuleResult:
    """Resultado estructurado, determinístico y trazable de la evaluación de una regla."""
    rule_code: str
    rule_name: str
    status: str # passed, failed, warning, not_applicable, insufficient_evidence
    severity: str # critical, high, medium, low, info
    title: str
    description: str
    recommendation: Optional[str] = None
    evidence_refs: Dict[str, Any] = field(default_factory=dict)
    expected_value: Optional[Any] = None
    observed_value: Optional[Any] = None
    delta: Optional[Any] = None
    confidence: float = 1.0
    requires_human_review: bool = False
    review_reason: Optional[str] = None
    review_task_type: Optional[str] = None
    verdict: str = "cumple" # cumple, no_cumple, no_verificable, no_aplica
    unverifiable_reason: Optional[str] = None # minor_missing, insufficient_evidence, blocked_by_missing_doc, formal_rfi_required
    blocked_by_deliverable: Optional[str] = None

    # Not Evaluable Estructurado (Auditoría QA/QC)
    not_evaluable_reason_code: Optional[str] = None
    not_evaluable_reason_message: Optional[str] = None
    missing_requirements: List[str] = field(default_factory=list)
    recommended_action: Optional[str] = None
    findings_list: List[Dict[str, Any]] = field(default_factory=list)
