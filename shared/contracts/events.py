from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class BaseEvent(BaseModel):
    event_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class DocumentUploadedEvent(BaseEvent):
    document_id: str
    project_id: str
    filename: str
    file_path: str

class SheetProcessingCompletedEvent(BaseEvent):
    sheet_id: str
    document_id: str
    sheet_code: Optional[str] = None
    extracted_text_count: int
    detected_symbols_count: int

class ReviewRunRequestedEvent(BaseEvent):
    run_id: str
    project_id: str
    sheet_ids: List[str]
