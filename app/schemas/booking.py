# app/schemas/booking.py

from pydantic import BaseModel, field_validator
from typing import Optional
from decimal import Decimal
from datetime import date


# ── Request Schemas ───────────────────────────────────────────────────────────

class BookingItemRequest(BaseModel):
    service_id: int
    quantity: int = 1

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v):
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        return v


class CreateBookingRequest(BaseModel):
    vendor_id: int
    delivery_address_id: int
    items: list[BookingItemRequest]
    scheduled_date: Optional[date] = None
    scheduled_time: Optional[str] = None   # "14:30"
    special_instructions: Optional[str] = None

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v):
        if not v:
            raise ValueError("Booking must have at least one item")
        return v

    @field_validator("scheduled_time")
    @classmethod
    def time_format(cls, v):
        if v is not None:
            import re
            if not re.match(r"^\d{2}:\d{2}$", v):
                raise ValueError("Time must be in HH:MM format e.g. '14:30'")
        return v


class CancelBookingRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Cancellation reason cannot be empty")
        return v.strip()


class VendorBookingActionRequest(BaseModel):
    action: str    # "confirm" | "reject" | "complete"

    @field_validator("action")
    @classmethod
    def action_valid(cls, v):
        if v not in ("confirm", "reject", "complete"):
            raise ValueError("Action must be 'confirm', 'reject', or 'complete'")
        return v


# ── Response Schemas ──────────────────────────────────────────────────────────

class BookingItemOut(BaseModel):
    id: int
    service_id: Optional[int] = None
    service_title: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal

    class Config:
        from_attributes = True


class BookingOut(BaseModel):
    id: int
    user_id: int
    vendor_id: int
    delivery_address_id: Optional[int] = None
    status: str
    scheduled_date: Optional[date] = None
    scheduled_time: Optional[str] = None
    subtotal: Decimal
    discount_amount: Decimal
    delivery_fee: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    special_instructions: Optional[str] = None
    cancellation_reason: Optional[str] = None
    items: list[BookingItemOut] = []

    class Config:
        from_attributes = True


class BookingListOut(BaseModel):
    id: int
    vendor_id: int
    status: str
    total_amount: Decimal
    scheduled_date: Optional[date] = None

    class Config:
        from_attributes = True