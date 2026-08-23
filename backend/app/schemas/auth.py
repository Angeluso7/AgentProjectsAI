from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserProfileRead(BaseModel):
    id: str
    email: str
    display_name: str
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserMembershipSummary(BaseModel):
    membership_id: str
    organization_id: str
    organization_name: str
    organization_slug: str
    role: str
    status: str

class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int = 1800
    user: UserProfileRead
    active_organization_id: str
    active_role: str
    memberships: List[UserMembershipSummary] = []

class CurrentUserResponse(BaseModel):
    user: UserProfileRead
    memberships: List[UserMembershipSummary] = []


class UpdateProfileRequest(BaseModel):
    display_name: str = Field(..., min_length=2, max_length=150)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


class EmailChangeRequestSchema(BaseModel):
    current_password: str
    new_email: EmailStr


class EmailChangeConfirmSchema(BaseModel):
    token: str


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetConfirmSchema(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)


class GenericMessageResponse(BaseModel):
    message: str
    success: bool = True

