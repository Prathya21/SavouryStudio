# app/services/booking_service.py

from sqlalchemy.orm import Session
from decimal import Decimal

from app.models.booking import Booking, BookingItem
from app.models.service import Service
from app.models.vendor import Vendor
from app.models.address import Address
from app.models.user import User
from app.models.notification import Notification
from app.schemas.booking import (
    CreateBookingRequest,
    CancelBookingRequest,
    VendorBookingActionRequest,
)
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    BadRequestException,
)
from app.core.logging import logger

TAX_RATE = Decimal("0.18")          # 18% GST
DELIVERY_FEE = Decimal("50.00")     # flat delivery fee


class BookingService:

    def __init__(self, db: Session):
        self.db = db

    # ── Create Booking ────────────────────────────────────────────────────────

    def create_booking(self, user: User, data: CreateBookingRequest) -> Booking:
        # Validate vendor exists and is approved
        vendor = self.db.query(Vendor).filter(
            Vendor.id == data.vendor_id,
            Vendor.status == "approved",
            Vendor.is_active == True,
        ).first()
        if not vendor:
            raise NotFoundException("Vendor", data.vendor_id)

        # Validate delivery address belongs to user
        address = self.db.query(Address).filter(
            Address.id == data.delivery_address_id,
            Address.user_id == user.id,
        ).first()
        if not address:
            raise NotFoundException("Address", data.delivery_address_id)

        # Build booking items and calculate totals
        subtotal = Decimal("0.00")
        booking_items = []

        for item_data in data.items:
            service = self.db.query(Service).filter(
                Service.id == item_data.service_id,
                Service.vendor_id == data.vendor_id,
                Service.status == "approved",
                Service.is_active == True,
            ).first()
            if not service:
                raise BadRequestException(
                    f"Service {item_data.service_id} is not available from this vendor"
                )

            # Use discount price if available
            unit_price = service.discount_price if service.discount_price else service.price
            line_total = unit_price * item_data.quantity
            subtotal += line_total

            booking_items.append(BookingItem(
                service_id=service.id,
                service_title=service.title,   # snapshot
                unit_price=unit_price,         # snapshot
                quantity=item_data.quantity,
                line_total=line_total,
            ))

        tax_amount = (subtotal * TAX_RATE).quantize(Decimal("0.01"))
        total_amount = subtotal + tax_amount + DELIVERY_FEE

        booking = Booking(
            user_id=user.id,
            vendor_id=data.vendor_id,
            delivery_address_id=data.delivery_address_id,
            status="pending",
            scheduled_date=data.scheduled_date,
            scheduled_time=data.scheduled_time,
            special_instructions=data.special_instructions,
            subtotal=subtotal,
            discount_amount=Decimal("0.00"),
            delivery_fee=DELIVERY_FEE,
            tax_amount=tax_amount,
            total_amount=total_amount,
        )
        self.db.add(booking)
        self.db.flush()   # get booking.id without committing

        for item in booking_items:
            item.booking_id = booking.id
            self.db.add(item)

        # Notify vendor
        self._notify(
            user_id=vendor.user_id,
            title="New Booking Received",
            body=f"You have a new booking #{booking.id} from {user.full_name}",
            notification_type="booking_update",
            reference_id=booking.id,
            reference_type="booking",
        )

        self.db.commit()
        self.db.refresh(booking)
        logger.info(f"Booking #{booking.id} created by user {user.id}")
        return booking

    # ── User Operations ───────────────────────────────────────────────────────

    def get_user_bookings(self, user: User, skip: int, limit: int, status: str = None):
        query = self.db.query(Booking).filter(Booking.user_id == user.id)
        if status:
            query = query.filter(Booking.status == status)
        total = query.count()
        bookings = query.order_by(Booking.id.desc()).offset(skip).limit(limit).all()
        return bookings, total

    def get_user_booking_by_id(self, user: User, booking_id: int) -> Booking:
        booking = self.db.query(Booking).filter(
            Booking.id == booking_id,
            Booking.user_id == user.id,
        ).first()
        if not booking:
            raise NotFoundException("Booking", booking_id)
        return booking

    def cancel_booking_by_user(self, user: User, booking_id: int, data: CancelBookingRequest) -> Booking:
        booking = self.get_user_booking_by_id(user, booking_id)

        if booking.status not in ("pending", "confirmed"):
            raise BadRequestException(
                f"Cannot cancel a booking with status '{booking.status}'"
            )

        booking.status = "cancelled"
        booking.cancellation_reason = data.reason
        booking.cancelled_by = "user"

        # Notify vendor
        self._notify(
            user_id=booking.vendor.user_id,
            title="Booking Cancelled",
            body=f"Booking #{booking.id} has been cancelled by the customer",
            notification_type="booking_update",
            reference_id=booking.id,
            reference_type="booking",
        )

        self.db.commit()
        self.db.refresh(booking)
        logger.info(f"Booking #{booking_id} cancelled by user {user.id}")
        return booking

    # ── Vendor Operations ─────────────────────────────────────────────────────

    def get_vendor_bookings(self, user: User, skip: int, limit: int, status: str = None):
        vendor = self.db.query(Vendor).filter(Vendor.user_id == user.id).first()
        if not vendor:
            raise NotFoundException("Vendor profile")
        query = self.db.query(Booking).filter(Booking.vendor_id == vendor.id)
        if status:
            query = query.filter(Booking.status == status)
        total = query.count()
        bookings = query.order_by(Booking.id.desc()).offset(skip).limit(limit).all()
        return bookings, total

    def vendor_booking_action(
        self, user: User, booking_id: int, data: VendorBookingActionRequest
    ) -> Booking:
        vendor = self.db.query(Vendor).filter(Vendor.user_id == user.id).first()
        if not vendor:
            raise NotFoundException("Vendor profile")

        booking = self.db.query(Booking).filter(
            Booking.id == booking_id,
            Booking.vendor_id == vendor.id,
        ).first()
        if not booking:
            raise NotFoundException("Booking", booking_id)

        if data.action == "confirm":
            if booking.status != "pending":
                raise BadRequestException("Only pending bookings can be confirmed")
            booking.status = "confirmed"
            notify_title = "Booking Confirmed"
            notify_body = f"Your booking #{booking.id} has been confirmed by the vendor"

        elif data.action == "reject":
            if booking.status != "pending":
                raise BadRequestException("Only pending bookings can be rejected")
            booking.status = "cancelled"
            booking.cancelled_by = "vendor"
            notify_title = "Booking Rejected"
            notify_body = f"Your booking #{booking.id} was rejected by the vendor"

        elif data.action == "complete":
            if booking.status != "confirmed":
                raise BadRequestException("Only confirmed bookings can be marked complete")
            booking.status = "completed"
            notify_title = "Booking Completed"
            notify_body = f"Your booking #{booking.id} has been marked as completed"

        # Notify user
        self._notify(
            user_id=booking.user_id,
            title=notify_title,
            body=notify_body,
            notification_type="booking_update",
            reference_id=booking.id,
            reference_type="booking",
        )

        self.db.commit()
        self.db.refresh(booking)
        logger.info(f"Vendor {data.action}d booking #{booking_id}")
        return booking

    # ── Admin Operations ──────────────────────────────────────────────────────

    def admin_get_all_bookings(self, skip: int, limit: int, status: str = None):
        query = self.db.query(Booking)
        if status:
            query = query.filter(Booking.status == status)
        total = query.count()
        bookings = query.order_by(Booking.id.desc()).offset(skip).limit(limit).all()
        return bookings, total

    def admin_get_booking(self, booking_id: int) -> Booking:
        booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise NotFoundException("Booking", booking_id)
        return booking

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _notify(
        self,
        user_id: int,
        title: str,
        body: str,
        notification_type: str,
        reference_id: int = None,
        reference_type: str = None,
    ):
        notification = Notification(
            user_id=user_id,
            title=title,
            body=body,
            notification_type=notification_type,
            reference_id=reference_id,
            reference_type=reference_type,
        )
        self.db.add(notification)