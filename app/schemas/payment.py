# app/schemas/payment.py

from pydantic import BaseModel, field_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime


# ── Request Schemas ───────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    """
    User initiates payment for a booking.
    The server creates a Razorpay order and returns order_id to the frontend.
    """
    booking_id: int


class VerifyPaymentRequest(BaseModel):
    """
    After the user completes payment in Razorpay's checkout popup,
    the frontend sends these three values back to us for verification.
    In mock mode, dummy values are accepted.
    """
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class RefundRequest(BaseModel):
    """Admin initiates a refund."""
    payment_id: int
    razorpay_payment_id: Optional[str] = None   # required in real mode
    amount: Optional[Decimal] = None             # None = full refund
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Refund reason cannot be empty")
        return v.strip()

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Refund amount must be greater than 0")
        return v


# ── Response Schemas ──────────────────────────────────────────────────────────

class OrderOut(BaseModel):
    """
    Returned to the frontend after creating a Razorpay order.
    Frontend uses order_id and key_id to open the Razorpay checkout popup.
    """
    order_id: str
    amount: Decimal
    currency: str
    key_id: str
    booking_id: int
    mock_mode: bool = False


class PaymentOut(BaseModel):
    id: int
    booking_id: int
    amount: Decimal
    currency: str
    payment_method: Optional[str] = None
    status: str
    refund_amount: Optional[Decimal] = None
    refund_reason: Optional[str] = None
    refunded_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaymentListOut(BaseModel):
    id: int
    booking_id: int
    amount: Decimal
    status: str
    payment_method: Optional[str] = None
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True