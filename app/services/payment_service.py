# app/services/payment_service.py
#
# RAZORPAY PAYMENT FLOW:
#
# Step 1 — User creates a booking (status: pending)
# Step 2 — User calls POST /payments/create-order
#           → We create a Razorpay Order server-side
#           → Razorpay returns an order_id
#           → We return order_id + key_id to the frontend
# Step 3 — Frontend uses order_id with Razorpay's JS checkout
#           → User pays via UPI / Card / NetBanking / Wallet
#           → Card/UPI details NEVER touch our server
#           → Razorpay returns razorpay_payment_id, razorpay_signature
# Step 4 — Frontend sends those back to POST /payments/verify
#           → We verify the signature to confirm payment is genuine
#           → We update Payment record to "completed"
#           → We update Booking to "confirmed"
# Step 5 — For refunds: Admin calls POST /payments/refund
#           → We call Razorpay's refund API
#           → Payment updated to "refunded" or "partially_refunded"
#
# TO GO LIVE: Replace the dummy values in .env with real Razorpay keys:
#   RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxxxxx
#   RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx

import hmac
import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.booking import Booking
from app.models.notification import Notification
from app.models.user import User
from app.schemas.payment import CreateOrderRequest, VerifyPaymentRequest, RefundRequest
from app.core.config import settings
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ServiceUnavailableException,
)
from app.core.logging import logger

# ── Razorpay client setup ─────────────────────────────────────────────────────
# We import razorpay only if the package is installed.
# In mock mode (dummy keys) we skip real API calls entirely.

MOCK_MODE = (
    not settings.RAZORPAY_KEY_ID
    or settings.RAZORPAY_KEY_ID == "rzp_test_dummy"
)

if not MOCK_MODE:
    try:
        import razorpay
        razorpay_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
    except ImportError:
        MOCK_MODE = True
        razorpay_client = None
else:
    razorpay_client = None


class PaymentService:

    def __init__(self, db: Session):
        self.db = db

    # ── Create Razorpay Order ─────────────────────────────────────────────────

    def create_order(self, user: User, data: CreateOrderRequest) -> dict:
        """
        Creates a Razorpay Order for a booking.

        What happens here:
        1. We find the booking and verify it belongs to this user
        2. We check the booking hasn't already been paid
        3. In REAL mode: we call razorpay_client.order.create() with the
           booking total in paise (INR × 100, because Razorpay always
           works in the smallest currency unit)
        4. In MOCK mode: we generate a fake order_id locally so you can
           test the full flow without real Razorpay credentials
        5. We store a Payment record with status='pending'
        6. We return the order_id and key_id to the frontend

        The frontend then uses:
            var rzp = new Razorpay({ key: key_id, order_id: order_id, ... })
            rzp.open()
        to show the Razorpay checkout popup.
        """
        # Verify booking exists and belongs to this user
        booking = self.db.query(Booking).filter(
            Booking.id == data.booking_id,
            Booking.user_id == user.id,
        ).first()
        if not booking:
            raise NotFoundException("Booking", data.booking_id)

        # Only pending bookings can initiate payment
        if booking.status not in ("pending", "confirmed"):
            raise BadRequestException(
                f"Cannot pay for a booking with status '{booking.status}'"
            )

        # Check if already paid
        existing = self.db.query(Payment).filter(
            Payment.booking_id == data.booking_id
        ).first()
        if existing and existing.status == "completed":
            raise BadRequestException("This booking has already been paid")

        # Amount in paise (multiply by 100) — e.g. ₹250.00 → 25000 paise
        amount_paise = int(booking.total_amount * 100)

        if MOCK_MODE:
            # ── MOCK MODE ─────────────────────────────────────────────────────
            # Generates a fake Razorpay order so the whole flow can be tested
            # locally without real credentials.
            # When real keys are added to .env, this block is never reached.
            order_id = f"order_MOCK_{uuid.uuid4().hex[:16]}"
            logger.info(f"[MOCK] Created fake Razorpay order: {order_id}")
        else:
            # ── REAL MODE ─────────────────────────────────────────────────────
            try:
                order = razorpay_client.order.create({
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": f"booking_{booking.id}",
                    "notes": {
                        "booking_id": str(booking.id),
                        "user_id": str(user.id),
                    }
                })
                order_id = order["id"]
            except Exception as e:
                logger.error(f"Razorpay order creation failed: {e}")
                raise ServiceUnavailableException("Payment gateway")

        # Save or update the Payment record
        if existing:
            existing.stripe_payment_intent_id = order_id   # reusing field for razorpay order_id
            existing.amount = booking.total_amount
            payment = existing
        else:
            payment = Payment(
                booking_id=booking.id,
                amount=booking.total_amount,
                currency="INR",
                status="pending",
                stripe_payment_intent_id=order_id,   # storing razorpay order_id here
            )
            self.db.add(payment)

        self.db.commit()
        self.db.refresh(payment)

        logger.info(f"Razorpay order created for booking #{booking.id}: {order_id}")
        return {
            "order_id": order_id,
            "amount": booking.total_amount,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID or "rzp_test_dummy",
            "booking_id": booking.id,
            "mock_mode": MOCK_MODE,
        }

    # ── Verify Payment After Checkout ─────────────────────────────────────────

    def verify_payment(self, user: User, data: VerifyPaymentRequest) -> Payment:
        """
        Called by the frontend AFTER the user completes payment in the
        Razorpay checkout popup.

        What happens here:
        1. Razorpay's checkout gives the frontend three values:
           - razorpay_order_id   (the order we created in step 1)
           - razorpay_payment_id (Razorpay's internal payment ID)
           - razorpay_signature  (HMAC-SHA256 hash we must verify)
        2. We re-compute the signature ourselves using our KEY_SECRET
        3. If signatures match → payment is genuine → we mark it complete
        4. If they don't match → someone tampered with the request → reject

        In MOCK MODE: we skip signature verification and auto-approve.
        This lets you test the complete flow end-to-end without real keys.

        NEVER skip signature verification in production.
        """
        # Find the payment by order_id
        payment = self.db.query(Payment).filter(
            Payment.stripe_payment_intent_id == data.razorpay_order_id,
        ).first()
        if not payment:
            raise NotFoundException("Payment for this order")

        # Make sure this booking belongs to the user
        booking = self.db.query(Booking).filter(
            Booking.id == payment.booking_id,
            Booking.user_id == user.id,
        ).first()
        if not booking:
            raise BadRequestException("Booking does not belong to this user")

        if MOCK_MODE:
            # ── MOCK: skip signature check, auto-approve ───────────────────
            logger.info(f"[MOCK] Auto-approving payment for booking #{booking.id}")
        else:
            # ── REAL: verify Razorpay signature ────────────────────────────
            # Razorpay signs the response as:
            #   HMAC_SHA256(order_id + "|" + payment_id, key_secret)
            # We recompute and compare — if they match, payment is authentic.
            body = f"{data.razorpay_order_id}|{data.razorpay_payment_id}"
            expected_signature = hmac.new(
                settings.RAZORPAY_KEY_SECRET.encode(),
                body.encode(),
                hashlib.sha256,
            ).hexdigest()

            if expected_signature != data.razorpay_signature:
                logger.warning(f"Razorpay signature mismatch for order {data.razorpay_order_id}")
                raise BadRequestException("Payment verification failed — invalid signature")

        # Mark payment as completed
        payment.status = "completed"
        payment.paid_at = datetime.now(timezone.utc)
        payment.payment_method = "razorpay"
        payment.gateway_response = str({
            "razorpay_payment_id": data.razorpay_payment_id,
            "razorpay_order_id": data.razorpay_order_id,
        })

        # Confirm the booking
        booking.status = "confirmed"

        # Notify user
        self.db.add(Notification(
            user_id=booking.user_id,
            title="Payment Successful",
            body=f"Payment of ₹{payment.amount} for booking #{booking.id} was successful",
            notification_type="payment",
            reference_id=payment.id,
            reference_type="payment",
        ))

        # Notify vendor
        vendor_user_id = booking.vendor.user_id if booking.vendor else None
        if vendor_user_id:
            self.db.add(Notification(
                user_id=vendor_user_id,
                title="Payment Received",
                body=f"Payment received for booking #{booking.id}",
                notification_type="payment",
                reference_id=payment.id,
                reference_type="payment",
            ))

        self.db.commit()
        self.db.refresh(payment)
        logger.info(f"Payment verified and completed for booking #{booking.id}")
        return payment

    # ── Refunds ───────────────────────────────────────────────────────────────

    def refund_payment(self, data: RefundRequest) -> Payment:
        """
        Admin issues a full or partial refund via Razorpay.

        What happens here:
        1. We find the Payment and verify it's 'completed'
        2. In REAL mode: we call razorpay_client.payment.refund()
           with the razorpay_payment_id and amount in paise
        3. In MOCK mode: we just update the DB record directly
        4. Payment status → 'refunded' or 'partially_refunded'
        5. Booking status → 'refunded'
        6. Customer gets an in-app notification

        The refund appears in the customer's bank/UPI within 5-7 business days.
        """
        payment = self.db.query(Payment).filter(Payment.id == data.payment_id).first()
        if not payment:
            raise NotFoundException("Payment", data.payment_id)

        if payment.status != "completed":
            raise BadRequestException(
                f"Cannot refund a payment with status '{payment.status}'"
            )

        refund_amount = data.amount or payment.amount

        if refund_amount > payment.amount:
            raise BadRequestException(
                f"Refund amount ₹{refund_amount} exceeds payment total ₹{payment.amount}"
            )

        if MOCK_MODE:
            logger.info(f"[MOCK] Refund of ₹{refund_amount} processed for payment {payment.id}")
        else:
            try:
                # gateway_response stores the razorpay_payment_id
                razorpay_payment_id = data.razorpay_payment_id
                razorpay_client.payment.refund(
                    razorpay_payment_id,
                    {"amount": int(refund_amount * 100)}
                )
            except Exception as e:
                logger.error(f"Razorpay refund failed: {e}")
                raise ServiceUnavailableException("Payment gateway")

        payment.refund_amount = refund_amount
        payment.refund_reason = data.reason
        payment.refunded_at = datetime.now(timezone.utc)
        payment.status = "refunded" if refund_amount == payment.amount else "partially_refunded"

        booking = self.db.query(Booking).filter(Booking.id == payment.booking_id).first()
        if booking:
            booking.status = "refunded"
            self.db.add(Notification(
                user_id=booking.user_id,
                title="Refund Processed",
                body=f"A refund of ₹{refund_amount} has been processed for booking #{booking.id}",
                notification_type="payment",
                reference_id=payment.id,
                reference_type="payment",
            ))

        self.db.commit()
        self.db.refresh(payment)
        logger.info(f"Refund of ₹{refund_amount} completed for payment {payment.id}")
        return payment

    # ── Read Operations ───────────────────────────────────────────────────────

    def get_payment_for_booking(self, user: User, booking_id: int) -> Payment:
        booking = self.db.query(Booking).filter(
            Booking.id == booking_id,
            Booking.user_id == user.id,
        ).first()
        if not booking:
            raise NotFoundException("Booking", booking_id)
        payment = self.db.query(Payment).filter(Payment.booking_id == booking_id).first()
        if not payment:
            raise NotFoundException("Payment for this booking")
        return payment

    def admin_get_all_payments(self, skip: int, limit: int, status: str = None):
        query = self.db.query(Payment)
        if status:
            query = query.filter(Payment.status == status)
        total = query.count()
        payments = query.order_by(Payment.id.desc()).offset(skip).limit(limit).all()
        return payments, total