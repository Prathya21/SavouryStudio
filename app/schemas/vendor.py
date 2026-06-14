# app/schemas/vendor.py
# Request and response schemas for vendor management.

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import re


# ── Request Schemas ───────────────────────────────────────────────────────────

class VendorRegisterRequest(BaseModel):
    """User registers as a vendor — creates a vendor profile linked to their account."""
    business_name: str
    business_description: Optional[str] = None
    business_phone: str
    business_email: EmailStr

    @field_validator("business_phone")
    @classmethod
    def phone_valid(cls, v):
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if cleaned.startswith("+91"):
            cleaned = cleaned[3:]
        if not re.match(r"^[6-9]\d{9}$", cleaned):
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return cleaned

    @field_validator("business_name")
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Business name cannot be empty")
        return v.strip()


class VendorUpdateRequest(BaseModel):
    """Vendor updates their own profile."""
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    business_phone: Optional[str] = None
    business_email: Optional[EmailStr] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None

    @field_validator("bank_ifsc_code")
    @classmethod
    def ifsc_valid(cls, v):
        if v is not None and not re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", v):
            raise ValueError("Invalid IFSC code format (e.g. SBIN0001234)")
        return v


class AdminVendorActionRequest(BaseModel):
    """Admin approves or rejects a vendor application."""
    action: str                          # "approve" | "reject" | "suspend"
    rejection_reason: Optional[str] = None

    @field_validator("action")
    @classmethod
    def action_valid(cls, v):
        if v not in ("approve", "reject", "suspend"):
            raise ValueError("Action must be 'approve', 'reject', or 'suspend'")
        return v


# ── Response Schemas ──────────────────────────────────────────────────────────

class VendorOut(BaseModel):
    id: int
    user_id: int
    business_name: str
    business_description: Optional[str] = None
    business_phone: Optional[str] = None
    business_email: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    status: str
    is_active: bool

    class Config:
        from_attributes = True


class VendorDetailOut(BaseModel):
    """Full vendor detail including bank info — for vendor themselves and admin."""
    id: int
    user_id: int
    business_name: str
    business_description: Optional[str] = None
    business_phone: Optional[str] = None
    business_email: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    status: str
    rejection_reason: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class VendorListOut(BaseModel):
    """Slim version for list views."""
    id: int
    business_name: str
    business_email: Optional[str] = None
    status: str
    is_active: bool

    class Config:
        from_attributes = True