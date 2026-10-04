from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.common import DisciplineEnum, SeverityEnum

# Activo de conocimiento general
class KnowledgeAssetBase(BaseModel):
    code: str = Field(..., example="OGUC-CHILE-2024-ASSET")
    title: str = Field(..., example="Guía Normativa OGUC Edificación")
    asset_type: str = Field(default="standard", example="standard") # standard, guide_manual, title_block_template, symbol_library, ontology
    discipline: DisciplineEnum = DisciplineEnum.GENERAL
    version: str = "1.0"
    description: Optional[str] = None
    file_path: Optional[str] = None
    content_payload: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

class KnowledgeAssetCreate(KnowledgeAssetBase):
    pass

class KnowledgeAssetRead(KnowledgeAssetBase):
    id: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

# Normativas
class NormativeCriterionBase(BaseModel):
    criterion_code: str
    name: str
    description: Optional[str] = None
    target_entity: str
    property_name: str
    operator: str # gte, lte, eq, range
    threshold_value: Dict[str, Any]
    severity: SeverityEnum = SeverityEnum.HIGH

class NormativeCriterionRead(NormativeCriterionBase):
    id: str
    clause_id: str
    created_at: datetime
    class Config:
        from_attributes = True

class NormativeClauseBase(BaseModel):
    clause_number: str
    title: Optional[str] = None
    content_text: str
    summary: Optional[str] = None
    scope_keywords: List[str] = []

class NormativeClauseRead(NormativeClauseBase):
    id: str
    document_id: str
    created_at: datetime
    criteria: List[NormativeCriterionRead] = []
    class Config:
        from_attributes = True

class NormativeDocumentCreate(BaseModel):
    code: str
    title: str
    authority: Optional[str] = None
    country: str = "CL"
    discipline: DisciplineEnum
    version_year: Optional[int] = None
    metadata_info: Dict[str, Any] = {}

class NormativeDocumentRead(NormativeDocumentCreate):
    id: str
    is_active: bool
    created_at: datetime
    clauses: List[NormativeClauseRead] = []
    class Config:
        from_attributes = True

# Plantillas de viñeta
class TitleBlockTemplateCreate(BaseModel):
    name: str
    client_or_standard: Optional[str] = None
    discipline: str = "general"
    relative_position: str = "bottom_right"
    expected_bbox: List[float] # [x0, y0, x1, y1]
    field_anchors: Dict[str, List[str]] # {"sheet_code": ["PLANO N°"]}

class TitleBlockTemplateRead(TitleBlockTemplateCreate):
    id: str
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

# Librerías de símbolos
class SymbolTemplateRead(BaseModel):
    id: str
    symbol_class: str
    display_name: str
    aliases: List[str] = []
    image_template_path: Optional[str] = None
    vector_svg_path: Optional[str] = None
    class Config:
        from_attributes = True

class SymbolLibraryCreate(BaseModel):
    name: str
    discipline: DisciplineEnum
    standard_name: Optional[str] = None
    description: Optional[str] = None

class SymbolLibraryRead(SymbolLibraryCreate):
    id: str
    created_at: datetime
    symbols: List[SymbolTemplateRead] = []
    class Config:
        from_attributes = True

# Ontologías
class OntologyCreate(BaseModel):
    domain: str
    canonical_term: str
    display_label: str
    synonyms: List[str]
    unit: Optional[str] = None
    description: Optional[str] = None

class OntologyRead(OntologyCreate):
    id: str
    created_at: datetime
    class Config:
        from_attributes = True
