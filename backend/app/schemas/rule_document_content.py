from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class RuleDocumentContentItem(BaseModel):
    id: str
    item_type: str  # rule_candidate, rule, symbol_candidate, symbol, table, figure
    status: str  # pending, validated, promoted, rejected, active, por_confirmar, etc.
    title: str
    content: Optional[str] = None
    code_or_number: Optional[str] = None
    source_page: Optional[int] = None
    source_bbox: Optional[List[float]] = None
    confidence: Optional[float] = None
    promotion_status: str = "pending"  # pending, promoted, rejected
    promoted_rule_definition_id: Optional[str] = None
    can_promote: bool = False
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class RuleDocumentContentSummary(BaseModel):
    total_items: int = 0
    rule_candidates: int = 0
    symbol_candidates: int = 0
    validated_rules: int = 0
    pending_rules: int = 0
    rejected_rules: int = 0
    promoted_rules: int = 0


class RuleDocumentContentResponse(BaseModel):
    document_id: str
    organization_id: str
    title: str
    discipline: str
    status: str
    content_status: str = "extracted"  # not_extracted, extracting, extracted, failed, legacy_needs_reprocess
    summary: RuleDocumentContentSummary
    items: List[RuleDocumentContentItem] = Field(default_factory=list)
    can_reprocess: bool = True
    explanation_code: Optional[str] = None  # CONTENT_NOT_EXTRACTED, CONTENT_EXTRACTION_FAILED, NO_RULE_CANDIDATES_FOUND
    error: Optional[str] = None


class AffectedBaselineRule(BaseModel):
    id: str
    rule_code: str
    title: str
    code: Optional[str] = None
    name: Optional[str] = None
    discipline: Optional[str] = None
    enabled: bool = True
    source_status: Optional[str] = None


class DeletionImpactResponse(BaseModel):
    document_id: str
    title: str
    total_items_count: int = 0
    total_items: int = 0
    rule_candidates_count: int = 0
    symbol_candidates_count: int = 0
    promoted_rules_count: int = 0
    active_baseline_rules_count: int = 0
    affected_rules: List[AffectedBaselineRule] = Field(default_factory=list)
    can_delete: bool = True
    recommended_policy: str = "keep_baseline_source_removed"


class DeleteDocumentRequest(BaseModel):
    policy: Literal["keep_baseline_source_removed", "retire_rules", "cancel"] = "keep_baseline_source_removed"


class ReprocessDocumentContentResponse(BaseModel):
    document_id: str
    status: str
    extracted_items_count: int
    rule_candidates_count: int
    symbol_candidates_count: int
    message: str
