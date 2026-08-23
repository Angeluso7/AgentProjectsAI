from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict

class CropOcrRequest(BaseModel):
    image_base64: str = Field(..., description="Recorte en Base64 (data:image/png;base64,... o raw)")
    sheet_id: Optional[str] = None
    bbox_normalized: Optional[List[float]] = None
    language: Optional[str] = "spa+eng"


class CropOcrResponse(BaseModel):
    text: str
    confidence: float = 1.0
    engine_used: str = "tesseract"
    line_count: int = 0


class ManualAnnotationCreate(BaseModel):
    project_id: str
    document_id: str
    sheet_id: str
    bbox_normalized: List[float] = Field(..., description="[x0, y0, x1, y1] normalizado")
    bbox_pixels: Optional[List[int]] = Field(default_factory=list)
    crop_image_base64: Optional[str] = None
    element_type: str = Field(..., description="symbol, table, layout_region, text_note, title_block, legend, view_elevation_plan, stamp_signature, diagram_sketch, other")
    name: str
    description: Optional[str] = None
    ocr_text: Optional[str] = None
    discipline: Optional[str] = "general"
    category: Optional[str] = None
    confidence: Optional[float] = 1.0
    tags: Optional[List[str]] = Field(default_factory=list)
    status: Optional[str] = "confirmed"
    extra_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ManualAnnotationUpdate(BaseModel):
    element_type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    ocr_text: Optional[str] = None
    discipline: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None



class ManualAnnotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    project_id: str
    document_id: str
    sheet_id: str
    user_id: Optional[str] = None
    bbox_normalized: List[float]
    bbox_pixels: Optional[List[int]] = None
    crop_image_path: Optional[str] = None
    element_type: str
    name: str
    description: Optional[str] = None
    ocr_text: Optional[str] = None
    discipline: str
    category: Optional[str] = None
    confidence: float
    tags: List[str]
    status: str
    extra_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class KnowledgeLibraryEntryCreate(BaseModel):
    source_annotation_id: Optional[str] = None
    entry_type: str = Field(..., description="symbol_template, table_template, title_block_spec, note_clause, standard_region, legend_entry, sketch_sample, other")
    name: str
    description: Optional[str] = None
    discipline: Optional[str] = "general"
    crop_image_path: Optional[str] = None
    crop_image_base64: Optional[str] = None
    canonical_text: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    extra_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class KnowledgeLibraryEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    source_annotation_id: Optional[str] = None
    entry_type: str
    name: str
    description: Optional[str] = None
    discipline: str
    crop_image_path: Optional[str] = None
    canonical_text: Optional[str] = None
    tags: List[str]
    is_verified: bool
    created_by_user_id: Optional[str] = None
    status: str
    extra_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class ActiveLearningPromotionCreate(BaseModel):
    knowledge_entry_id: Optional[str] = None
    manual_annotation_id: Optional[str] = None
    target_engine: str = Field(..., description="ocr, symbol_detector, layout_parser, table_extractor, qa_rules")
    dataset_split: Optional[str] = "few_shot_pool"
    label: str
    ground_truth_text: Optional[str] = None
    ground_truth_bbox: Optional[List[float]] = Field(default_factory=list)
    notes: Optional[str] = None


class ActiveLearningPromotionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    knowledge_entry_id: Optional[str] = None
    manual_annotation_id: Optional[str] = None
    target_engine: str
    dataset_split: str
    crop_image_path: Optional[str] = None
    label: str
    ground_truth_text: Optional[str] = None
    ground_truth_bbox: Optional[List[float]] = None
    promoted_by_user_id: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class IncorporateProjectSelectionsRequest(BaseModel):
    project_id: str
    annotation_ids: Optional[List[str]] = None


class IncorporateProjectSelectionsResponse(BaseModel):
    rule_document_id: str
    rule_document_title: str
    project_id: str
    incorporated_count: int
    message: str
