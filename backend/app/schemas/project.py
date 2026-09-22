from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.common import DisciplineEnum

class ProjectBase(BaseModel):
    code: str = Field(..., example="PRJ-2026-001", description="Código único del proyecto")
    name: str = Field(..., example="Edificio Los Alerces", description="Nombre del proyecto")
    description: Optional[str] = Field(None, example="Edificio residencial de 15 pisos")
    client_name: Optional[str] = Field(None, example="Inmobiliaria Andina")
    discipline: DisciplineEnum = Field(default=DisciplineEnum.ARCHITECTURE)
    stage: Optional[str] = Field(default="Ingeniería de Detalle", description="Etapa actual del proyecto")
    project_type: Optional[str] = Field(default="edificacion", description="Tipo de proyecto (edificacion, mineria, infraestructura, industrial, energia, otro)")
    status: Optional[str] = Field(default="active", description="Estado del proyecto (active, archived, draft, completed, deleted)")
    settings: Dict[str, Any] = Field(default_factory=dict)

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    discipline: Optional[DisciplineEnum] = None
    stage: Optional[str] = None
    project_type: Optional[str] = None
    status: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class ProjectVersionBase(BaseModel):
    version_tag: str = Field(..., example="Rev A")
    description: Optional[str] = Field(None, example="Entrega inicial para anteproyecto")
    status: str = Field(default="draft")

class ProjectVersionCreate(ProjectVersionBase):
    pass

class ProjectVersionRead(ProjectVersionBase):
    id: str
    project_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class ProjectRead(ProjectBase):
    id: str
    organization_id: str
    normalized_code: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    versions: List[ProjectVersionRead] = []
    documents_count: int = 0
    sheets_count: int = 0
    findings_count: int = 0

    class Config:
        from_attributes = True

class ProjectConflictItem(BaseModel):
    id: str
    code: str
    name: str
    status: str
    is_archived: bool = False

class ProjectConflictDetail(BaseModel):
    message: str
    conflict_type: str = "duplicate_code"
    existing_project: Optional[ProjectConflictItem] = None

class ProjectExportSummary(BaseModel):
    versions_count: int = 0
    documents_count: int = 0
    sheets_count: int = 0
    annotations_count: int = 0
    findings_count: int = 0
    reports_count: int = 0

class ProjectExportPayload(BaseModel):
    schema_version: str = "1.0"
    exported_at: datetime
    project_id: str
    stage: str
    summary: ProjectExportSummary
    project: ProjectRead
    entities: Dict[str, Any]

