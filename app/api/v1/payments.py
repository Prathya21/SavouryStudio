# app/api/v1/payments.py
# Register in main.py:
#   from app.api.v1 import payments
#   app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"])

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.api.deps.auth import get_current_user, get_current_admin
from app.models.user import User
from app.schemas.payment import (
    CreateOrderRequest,
    VerifyPaymentRequest,
    RefundRequest,
    OrderOut,
    PaymentOut,
    PaymentListOut,
)
from app.schemas.response import SuccessResponse, PaginatedResponse
from app.schemas.pagination import PaginationParams
from app.services.payment_service import PaymentService, MOCK_MODE

router = APIRouter()


@router.get("/mode", response_model=SuccessResponse)
def get_payment_mode():
    """
    Check whether the payment system is running in mock or live mode.
    Useful for the frontend to know if it should show a real Razorpay
    checkout or a simulated one.
    """
    mode = "mock" if MOCK_MODE else "live"
    return SuccessResponse(
        data={"mode": mode},
        message=f"Payment system is running in {mode} mode",
    )


# ── User Routes ───────────────────────────────────────────────────────────────

@router.post("/create-order", response_model=SuccessResponse[OrderOut])
def create_order(
    data: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 1 of the payment flow — create a Razorpay order.

    The frontend calls this first. We return an order_id which the
    frontend passes to Razorpay's JS SDK to open the checkout popup.

    In mock mode: returns a fake order_id starting with 'order_MOCK_'
    so you can test the full flow without real Razorpay credentials.

    Full flow:
      1. POST /payments/create-order → get order_id + key_id
      2. Frontend opens Razorpay popup with order_id
      3. User pays via UPI/Card/NetBanking
      4. Razorpay returns razorpay_payment_id + razorpay_signature
      5. Frontend sends those to POST /payments/verify
    """
    service = PaymentService(db)
    result = service.create_order(current_user, data)
    return SuccessResponse(
        data=OrderOut(**result),
        message="Order created. Proceed to payment." if not MOCK_MODE
                else "Mock order created. Call /verify with any values to complete.",
    )


@router.post("/verify", response_model=SuccessResponse[PaymentOut])
def verify_payment(
    data: VerifyPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 2 of the payment flow — verify payment after Razorpay checkout.

    After the user completes payment in Razorpay's popup, the frontend
    receives three values from Razorpay:
      - razorpay_order_id   (same as what we returned in step 1)
      - razorpay_payment_id (Razorpay's unique payment ID)
      - razorpay_signature  (cryptographic proof the payment is genuine)

    We verify the signature server-side to confirm authenticity,
    then mark the payment completed and the booking confirmed.

    In mock mode: signature is not verified — any values are accepted.
    To test in mock mode, send:
      {
        "razorpay_order_id": "<order_id from step 1>",
        "razorpay_payment_id": "pay_mock_test",
        "razorpay_signature": "mock_signature"
      }
    """
    service = PaymentService(db)
    payment = service.verify_payment(current_user, data)
    return SuccessResponse(
        data=PaymentOut.model_validate(payment),
        message="Payment verified and booking confirmed successfully",
    )


@router.get("/booking/{booking_id}", response_model=SuccessResponse[PaymentOut])
def get_payment_for_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get payment status for a specific booking.
    Users can only view payment for their own bookings.
    Use this on the booking detail screen to show payment status.
    """
    service = PaymentService(db)
    payment = service.get_payment_for_booking(current_user, booking_id)
    return SuccessResponse(
        data=PaymentOut.model_validate(payment),
        message="Payment fetched successfully",
    )


# ── Admin Routes ──────────────────────────────────────────────────────────────

@router.get("/admin/all", response_model=PaginatedResponse[PaymentListOut])
def admin_list_payments(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(
        default=None,
        description="Filter: pending | completed | failed | refunded | partially_refunded"
    ),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Admin only: paginated list of all payments.
    Filter by status to find failed payments or pending ones.
    """
    service = PaymentService(db)
    payments, total = service.admin_get_all_payments(
        skip=pagination.skip,
        limit=pagination.limit,
        status=status,
    )
    return PaginatedResponse(
        data=[PaymentListOut.model_validate(p) for p in payments],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Payments fetched successfully",
    )


@router.post("/admin/refund", response_model=SuccessResponse[PaymentOut])
def refund_payment(
    data: RefundRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Admin only: issue a full or partial refund.

    Full refund: leave 'amount' empty
    Partial refund: specify 'amount' less than the original total

    In mock mode: no real refund is processed, DB is updated directly.
    In live mode: Razorpay processes the refund, customer gets money
    back in their UPI/bank within 5-7 business days.
    """
    service = PaymentService(db)
    payment = service.refund_payment(data)
    return SuccessResponse(
        data=PaymentOut.model_validate(payment),
        message="Refund processed successfully",
    )