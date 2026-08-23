from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class OrganizationRead(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    settings: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OrganizationCreate(BaseModel):
    name: str
    slug: str

class OrganizationMembershipRead(BaseModel):
    id: str
    organization_id: str
    user_id: str
    user_email: Optional[str] = None
    user_display_name: Optional[str] = None
    role: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OrganizationMembershipCreate(BaseModel):
    user_email: EmailStr
    display_name: Optional[str] = "Nuevo Miembro"
    role: str = Field(default="reviewer", description="admin, audit_lead, reviewer, contributor, viewer")
    initial_password: Optional[str] = "Temporal123!"

class OrganizationMembershipUpdate(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None # active, disabled
