from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ExtractedTableCellRead(BaseModel):
    id: str
    table_id: str
    row_index: int
    column_index: int
    row_span: int = 1
    col_span: int = 1
    text: str
    normalized_text: Optional[str] = None
    confidence: float
    bbox: List[float]
    bbox_normalized: List[float]
    is_header: bool = False
    source_text_refs: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True

class ExtractedTableRead(BaseModel):
    id: str
    document_id: str
    sheet_id: Optional[str] = None
    region_id: Optional[str] = None
    table_type: str
    title: Optional[str] = None
    bbox: List[float]
    bbox_normalized: List[float]
    row_count: int
    column_count: int
    confidence: float
    extraction_status: str
    source_engine: str
    source_version: str
    raw_structure: Dict[str, Any] = {}
    cells: Optional[List[ExtractedTableCellRead]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TableExtractProcessRequest(BaseModel):
    force_reprocess: bool = Field(default=False, description="Fuerza re-extracción descartando tablas previas")
    region_id: Optional[str] = Field(default=None, description="Filtra extracción a una macro-región table_candidate específica")
