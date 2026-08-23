from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class KnowledgeDomainEnum(str, Enum):
    normative_knowledge = "normative_knowledge"
    rule_knowledge = "rule_knowledge"
    deliverable_knowledge = "deliverable_knowledge"
    guide_document_knowledge = "guide_document_knowledge"
    review_knowledge = "review_knowledge"
    observation_rfi_knowledge = "observation_rfi_knowledge"
    project_knowledge = "project_knowledge"
    feedback_learning_knowledge = "feedback_learning_knowledge"
    symbol_knowledge = "symbol_knowledge"
    template_knowledge = "template_knowledge"
    lesson_knowledge = "lesson_knowledge"
    guide_knowledge = "guide_knowledge"
    web_research_knowledge = "web_research_knowledge"

class KnowledgeStatusEnum(str, Enum):
    draft = "draft"
    extracted = "extracted"
    reviewed = "reviewed"
    validated = "validated"
    approved_for_reuse = "approved_for_reuse"
    superseded = "superseded"
    archived = "archived"
    rejected = "rejected"

class KnowledgeChunkRead(BaseModel):
    id: str
    knowledge_item_id: str
    chunk_index: int
    chunk_title: Optional[str] = None
    chunk_text: str
    token_count: int = 0
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)
    embedding_json: Optional[List[float]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class KnowledgeItemCreate(BaseModel):
    project_id: Optional[str] = None
    domain: KnowledgeDomainEnum
    item_type: str
    title: str
    summary: Optional[str] = None
    content_text: str
    structured_payload: Dict[str, Any] = Field(default_factory=dict)
    discipline: str = "general"
    stage: Optional[str] = None
    status: KnowledgeStatusEnum = KnowledgeStatusEnum.draft
    confidence_score: float = 1.0
    source_asset_id: Optional[str] = None
    document_id: Optional[str] = None
    sheet_id: Optional[str] = None
    rule_id: Optional[str] = None
    observation_id: Optional[str] = None
    review_run_id: Optional[str] = None
    stage_snapshot_id: Optional[str] = None
    origin_type: str = "manual_entry"
    ingestion_channel: str = "manual_entry"
    modality: str = "text"
    visual_crop_url: Optional[str] = None
    legend_reference: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

class KnowledgeItemUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    content_text: Optional[str] = None
    structured_payload: Optional[Dict[str, Any]] = None
    discipline: Optional[str] = None
    stage: Optional[str] = None
    confidence_score: Optional[float] = None
    modality: Optional[str] = None
    visual_crop_url: Optional[str] = None
    legend_reference: Optional[str] = None
    tags: Optional[List[str]] = None

class KnowledgeItemTransitionRequest(BaseModel):
    target_status: KnowledgeStatusEnum
    notes: Optional[str] = None
    reviewer: Optional[str] = None

class KnowledgeItemVersionRequest(BaseModel):
    new_title: Optional[str] = None
    new_content_text: str
    new_summary: Optional[str] = None
    new_structured_payload: Optional[Dict[str, Any]] = None
    change_notes: str
    author: Optional[str] = None

class KnowledgeItemSummaryRead(BaseModel):
    id: str
    organization_id: str
    project_id: Optional[str] = None
    domain: str
    item_type: str
    title: str
    summary: Optional[str] = None
    discipline: str
    stage: Optional[str] = None
    status: str
    is_active_for_reuse: bool
    confidence_score: float
    version_number: int
    parent_item_id: Optional[str] = None
    author: str
    origin_type: str
    ingestion_channel: str = "manual_entry"
    modality: str = "text"
    visual_crop_url: Optional[str] = None
    legend_reference: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class KnowledgeItemRead(KnowledgeItemSummaryRead):
    content_text: str
    structured_payload: Dict[str, Any] = Field(default_factory=dict)
    valid_from: datetime
    valid_until: Optional[datetime] = None
    source_asset_id: Optional[str] = None
    document_id: Optional[str] = None
    sheet_id: Optional[str] = None
    rule_id: Optional[str] = None
    observation_id: Optional[str] = None
    review_run_id: Optional[str] = None
    stage_snapshot_id: Optional[str] = None
    provenance_trace: List[Dict[str, Any]] = Field(default_factory=list)
    chunks: List[KnowledgeChunkRead] = Field(default_factory=list)

    class Config:
        from_attributes = True

class KnowledgeSyncRequest(BaseModel):
    project_id: Optional[str] = None
    auto_approve: bool = False
    source_module: Optional[str] = "all" # all, sources, rules, completeness, observations, snapshots

class KnowledgeSyncResponse(BaseModel):
    success: bool
    message: str
    synced_counts: Dict[str, int]
    total_items_created: int
    total_items_updated: int
    synced_item_ids: List[str] = Field(default_factory=list)

class KnowledgeSearchQuery(BaseModel):
    query: str
    project_id: Optional[str] = None
    domain: Optional[str] = None
    discipline: Optional[str] = None
    stage: Optional[str] = None
    active_only: bool = True # Solo approved_for_reuse o validated
    top_k: int = 5

class KnowledgeSearchResultItem(BaseModel):
    item_id: str
    chunk_id: Optional[str] = None
    title: str
    domain: str
    item_type: str
    discipline: str
    stage: Optional[str] = None
    status: str
    is_active_for_reuse: bool
    relevance_score: float
    snippet: str
    provenance: Dict[str, Any]
    tags: List[str]

class KnowledgeSearchResponse(BaseModel):
    query: str
    total_matches: int
    results: List[KnowledgeSearchResultItem]

class KnowledgeBaseStatsRead(BaseModel):
    total_items: int
    approved_for_reuse_count: int
    draft_or_extracted_count: int
    validated_count: int
    rejected_or_superseded_count: int
    global_items_count: int
    project_scoped_items_count: int
    items_by_domain: Dict[str, int]
    items_by_discipline: Dict[str, int]
    items_by_status: Dict[str, int]
