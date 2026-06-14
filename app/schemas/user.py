# app/schemas/user.py
# Request and response schemas for user management endpoints.

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from app.utils.validators import validate_phone_number


# ── Request Schemas ───────────────────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    """User updates their own profile."""
    full_name: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v):
        if v is not None:
            return validate_phone_number(v)
        return v


class AdminUpdateUserRequest(BaseModel):
    """Admin updates any user's account."""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def role_valid(cls, v):
        if v is not None and v not in ("user", "vendor", "admin"):
            raise ValueError("Role must be 'user', 'vendor', or 'admin'")
        return v


# ── Response Schemas ──────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class UserListOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    is_active: bool
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True