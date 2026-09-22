from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class MemoryOverviewDetail(BaseModel):
    memory_type: str  # document_memory, normative_memory, template_memory, decision_memory
    name: str
    status: str       # active, synchronizing, degraded
    total_records: int
    secondary_count: int = 0
    secondary_label: str = ""
    last_updated: Optional[datetime] = None
    disciplines: List[str] = Field(default_factory=list)
    pending_reviews_count: int = 0
    consistency_score: float = 1.0  # 0.0 - 1.0
    index_status: str = "indexed"   # indexed, pending_reindex, stale
    description: str


class MemoriesOverviewResponse(BaseModel):
    timestamp: datetime
    total_memories_count: int = 4
    total_combined_records: int
    global_consistency_score: float
    memories: List[MemoryOverviewDetail]


class MemoryRecordItem(BaseModel):
    id: str
    memory_type: str
    code_or_identifier: str
    title: str
    description: Optional[str] = None
    discipline: str = "general"
    category_or_nature: str = "general"
    status: str = "active"  # active, to_confirm, obsolete, archived, draft
    created_at: datetime
    updated_at: Optional[datetime] = None
    version_or_revision: Optional[str] = None
    confidence_score: Optional[float] = None
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)
    relationships_count: int = 0


class MemoryRecordsListResponse(BaseModel):
    memory_type: str
    total_count: int
    page: int
    page_size: int
    records: List[MemoryRecordItem]


class MemoryRecordCreateRequest(BaseModel):
    memory_type: str
    code_or_identifier: str
    title: str
    description: Optional[str] = None
    discipline: str = "general"
    category_or_nature: str = "general"
    status: str = "active"
    version_or_revision: Optional[str] = "1.0"
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)


class MemoryRecordUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    discipline: Optional[str] = None
    category_or_nature: Optional[str] = None
    status: Optional[str] = None
    version_or_revision: Optional[str] = None
    metadata_payload: Optional[Dict[str, Any]] = None


class MemoryConsistencyIssue(BaseModel):
    id: str
    severity: str  # critical, warning, info
    memory_source: str
    issue_type: str  # orphaned_sheet, rule_without_standard, orphan_decision, duplicate_alias, unindexed_vectors
    title: str
    description: str
    affected_record_id: str
    suggested_action: str
    can_auto_fix: bool = True


class MemoryConsistencyReport(BaseModel):
    generated_at: datetime
    total_checks_run: int
    issues_found_count: int
    critical_issues_count: int
    orphaned_elements_count: int
    consistency_health: str  # healthy, attention_needed, critical
    issues: List[MemoryConsistencyIssue] = Field(default_factory=list)


class MemoryMaintenanceRequest(BaseModel):
    action: str  # full_maintenance, reindex_vectors, cleanup_orphans, sync_ontologies, vacuum_history
    memory_type: Optional[str] = None  # None for all


class MemoryMaintenanceResult(BaseModel):
    executed_at: datetime
    action: str
    status: str  # success, completed_with_warnings, failed
    records_processed: int
    records_repaired_or_cleaned: int
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class MemoriesExportResponse(BaseModel):
    exported_at: datetime
    version: str = "1.0"
    total_records: int
    document_memory: List[Dict[str, Any]]
    normative_memory: List[Dict[str, Any]]
    template_memory: List[Dict[str, Any]]
    decision_memory: List[Dict[str, Any]]
