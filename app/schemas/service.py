# app/schemas/service.py

from pydantic import BaseModel, field_validator
from typing import Optional
from decimal import Decimal


# ── Request Schemas ───────────────────────────────────────────────────────────

class ServiceCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    price: Decimal
    discount_price: Optional[Decimal] = None
    unit: Optional[str] = None           # "per plate", "per kg", "per hour"
    category_id: Optional[int] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

    @field_validator("price")
    @classmethod
    def price_positive(cls, v):
        if v <= 0:
            raise ValueError("Price must be greater than 0")
        return v

    @field_validator("discount_price")
    @classmethod
    def discount_less_than_price(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Discount price must be greater than 0")
        return v


class ServiceUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    discount_price: Optional[Decimal] = None
    unit: Optional[str] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("price")
    @classmethod
    def price_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Price must be greater than 0")
        return v


class AdminServiceActionRequest(BaseModel):
    action: str                          # "approve" | "reject"
    rejection_reason: Optional[str] = None

    @field_validator("action")
    @classmethod
    def action_valid(cls, v):
        if v not in ("approve", "reject"):
            raise ValueError("Action must be 'approve' or 'reject'")
        return v


# ── Response Schemas ──────────────────────────────────────────────────────────

class ServiceImageOut(BaseModel):
    id: int
    image_url: str
    is_primary: bool
    sort_order: int

    class Config:
        from_attributes = True


class ServiceOut(BaseModel):
    id: int
    vendor_id: int
    category_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    price: Decimal
    discount_price: Optional[Decimal] = None
    unit: Optional[str] = None
    status: str
    is_active: bool
    images: list[ServiceImageOut] = []

    class Config:
        from_attributes = True


class ServiceListOut(BaseModel):
    id: int
    vendor_id: int
    category_id: Optional[int] = None
    title: str
    price: Decimal
    discount_price: Optional[Decimal] = None
    unit: Optional[str] = None
    status: str
    is_active: bool

    class Config:
        from_attributes = True