# app/api/v1/bookings.py
# Register in main.py:
#   from app.api.v1 import bookings
#   app.include_router(bookings.router, prefix="/api/v1/bookings", tags=["Bookings"])

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.api.deps.auth import get_current_user, get_current_vendor, get_current_admin
from app.models.user import User
from app.schemas.booking import (
    CreateBookingRequest,
    CancelBookingRequest,
    VendorBookingActionRequest,
    BookingOut,
    BookingListOut,
)
from app.schemas.response import SuccessResponse, PaginatedResponse
from app.schemas.pagination import PaginationParams
from app.services.booking_service import BookingService

router = APIRouter()


# ── User Routes ───────────────────────────────────────────────────────────────

@router.post("", response_model=SuccessResponse[BookingOut], status_code=201)
def create_booking(
    data: CreateBookingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new booking.
    - All services must belong to the specified vendor
    - Delivery address must belong to the logged-in user
    - Price, tax (18% GST), and delivery fee are calculated automatically
    - Status starts as 'pending' until vendor confirms
    """
    service = BookingService(db)
    booking = service.create_booking(current_user, data)
    return SuccessResponse(
        data=BookingOut.model_validate(booking),
        message="Booking created successfully",
    )


@router.get("/my-bookings", response_model=PaginatedResponse[BookingListOut])
def get_my_bookings(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(
        default=None,
        description="Filter: pending | confirmed | completed | cancelled"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User: list all their own bookings with optional status filter."""
    service = BookingService(db)
    bookings, total = service.get_user_bookings(
        current_user,
        skip=pagination.skip,
        limit=pagination.limit,
        status=status,
    )
    return PaginatedResponse(
        data=[BookingListOut.model_validate(b) for b in bookings],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Bookings fetched successfully",
    )


@router.get("/my-bookings/{booking_id}", response_model=SuccessResponse[BookingOut])
def get_my_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User: get full details of one of their bookings including all items."""
    service = BookingService(db)
    booking = service.get_user_booking_by_id(current_user, booking_id)
    return SuccessResponse(
        data=BookingOut.model_validate(booking),
        message="Booking fetched successfully",
    )


@router.post("/my-bookings/{booking_id}/cancel", response_model=SuccessResponse[BookingOut])
def cancel_my_booking(
    booking_id: int,
    data: CancelBookingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    User: cancel their own booking.
    Can only cancel bookings that are 'pending' or 'confirmed'.
    Vendor is notified automatically.
    """
    service = BookingService(db)
    booking = service.cancel_booking_by_user(current_user, booking_id, data)
    return SuccessResponse(
        data=BookingOut.model_validate(booking),
        message="Booking cancelled successfully",
    )


# ── Vendor Routes ─────────────────────────────────────────────────────────────

@router.get("/vendor/bookings", response_model=PaginatedResponse[BookingListOut])
def get_vendor_bookings(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """Vendor: list all bookings for their business."""
    service = BookingService(db)
    bookings, total = service.get_vendor_bookings(
        current_user,
        skip=pagination.skip,
        limit=pagination.limit,
        status=status,
    )
    return PaginatedResponse(
        data=[BookingListOut.model_validate(b) for b in bookings],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Bookings fetched successfully",
    )


@router.post("/vendor/bookings/{booking_id}/action", response_model=SuccessResponse[BookingOut])
def vendor_booking_action(
    booking_id: int,
    data: VendorBookingActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """
    Vendor: confirm, reject, or complete a booking.
    - confirm: pending → confirmed (customer is notified)
    - reject:  pending → cancelled (customer is notified)
    - complete: confirmed → completed (triggers review eligibility)
    """
    service = BookingService(db)
    booking = service.vendor_booking_action(current_user, booking_id, data)
    return SuccessResponse(
        data=BookingOut.model_validate(booking),
        message=f"Booking {data.action}d successfully",
    )


# ── Admin Routes ──────────────────────────────────────────────────────────────

@router.get("/admin/all", response_model=PaginatedResponse[BookingListOut])
def admin_list_bookings(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin: list all bookings across all users and vendors."""
    service = BookingService(db)
    bookings, total = service.admin_get_all_bookings(
        skip=pagination.skip,
        limit=pagination.limit,
        status=status,
    )
    return PaginatedResponse(
        data=[BookingListOut.model_validate(b) for b in bookings],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Bookings fetched successfully",
    )


@router.get("/admin/{booking_id}", response_model=SuccessResponse[BookingOut])
def admin_get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin: get any booking by ID with full details."""
    service = BookingService(db)
    booking = service.admin_get_booking(booking_id)
    return SuccessResponse(
        data=BookingOut.model_validate(booking),
        message="Booking fetched successfully",
    )