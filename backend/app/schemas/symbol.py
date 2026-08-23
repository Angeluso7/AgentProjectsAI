from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class DetectedSymbolRead(BaseModel):
    id: str
    document_id: str
    sheet_id: str
    region_id: Optional[str] = None
    symbol_type: str
    discipline: str
    bbox: List[float]
    bbox_normalized: List[float]
    polygon_points: Optional[List[List[float]]] = None
    confidence: float
    detection_status: str
    source_engine: str
    source_version: str
    source_asset_template_id: Optional[str] = None
    matched_library_entry_id: Optional[str] = None
    attributes: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SymbolDetectProcessRequest(BaseModel):
    force_reprocess: bool = Field(default=False, description="Fuerza re-detección descartando detecciones previas")
    engine: Optional[str] = Field(default="yolo_sahi_hybrid", description="Motor: yolo_sahi_hybrid, template_matching, geometric_heuristic")
    confidence_threshold: Optional[float] = Field(default=0.50, description="Umbral mínimo de aceptación")
    discipline: Optional[str] = Field(default=None, description="Filtra por disciplina")

class SymbolSummaryItem(BaseModel):
    symbol_type: str
    discipline: str
    count: int
    average_confidence: float

class SheetSymbolsSummaryResponse(BaseModel):
    sheet_id: str
    total_symbols: int
    by_category: List[SymbolSummaryItem]
