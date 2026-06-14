# app/api/v1/reviews.py
# Register in main.py:
#   from app.api.v1 import reviews
#   app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["Reviews"])

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.api.deps.auth import get_current_user, get_current_vendor, get_current_admin
from app.models.user import User
from app.schemas.review import (
    CreateReviewRequest,
    UpdateReviewRequest,
    VendorReplyRequest,
    ReviewOut,
    ReviewListOut,
    VendorRatingSummary,
)
from app.schemas.response import SuccessResponse, PaginatedResponse
from app.schemas.pagination import PaginationParams
from app.services.review_service import ReviewService

router = APIRouter()


# ── Public Routes ─────────────────────────────────────────────────────────────

@router.get("/vendor/{vendor_id}", response_model=PaginatedResponse[ReviewListOut])
def get_vendor_reviews(
    vendor_id: int,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """
    Public: get all reviews for a specific vendor.
    No authentication required — shown on the vendor's public profile.
    Ordered newest first.
    """
    service = ReviewService(db)
    reviews, total = service.get_vendor_reviews(
        vendor_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[ReviewListOut.model_validate(r) for r in reviews],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Reviews fetched successfully",
    )


@router.get("/vendor/{vendor_id}/summary", response_model=SuccessResponse[VendorRatingSummary])
def get_vendor_rating_summary(
    vendor_id: int,
    db: Session = Depends(get_db),
):
    """
    Public: get aggregated rating stats for a vendor.
    Returns average rating and breakdown by star count (1★ through 5★).
    Used to display the rating bar on the vendor's profile page.
    """
    service = ReviewService(db)
    summary = service.get_vendor_rating_summary(vendor_id)
    return SuccessResponse(
        data=VendorRatingSummary(**summary),
        message="Rating summary fetched successfully",
    )


# ── User Routes ───────────────────────────────────────────────────────────────

@router.post("", response_model=SuccessResponse[ReviewOut], status_code=201)
def create_review(
    data: CreateReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a review for a completed booking.

    Rules:
    - Booking must belong to the logged-in user
    - Booking status must be 'completed'
    - Only one review per booking (returns 409 if already reviewed)
    - Rating must be 1 to 5
    - Vendor is notified automatically
    """
    service = ReviewService(db)
    review = service.create_review(current_user, data)
    return SuccessResponse(
        data=ReviewOut.model_validate(review),
        message="Review submitted successfully",
    )


@router.get("/my-reviews", response_model=PaginatedResponse[ReviewListOut])
def get_my_reviews(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User: list all reviews they have written across all bookings."""
    service = ReviewService(db)
    reviews, total = service.get_my_reviews(
        current_user,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[ReviewListOut.model_validate(r) for r in reviews],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Your reviews fetched successfully",
    )


@router.get("/booking/{booking_id}", response_model=SuccessResponse[ReviewOut])
def get_review_for_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the review the logged-in user wrote for a specific booking.
    Returns 404 if no review exists yet.
    Use this to check if a booking has been reviewed before showing
    the 'Write a Review' button on the frontend.
    """
    service = ReviewService(db)
    review = service.get_review_by_booking(current_user, booking_id)
    return SuccessResponse(
        data=ReviewOut.model_validate(review),
        message="Review fetched successfully",
    )


@router.put("/{review_id}", response_model=SuccessResponse[ReviewOut])
def update_review(
    review_id: int,
    data: UpdateReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    User updates their own review.
    Updating the review clears the vendor's reply since the content changed.
    Returns 404 if the review doesn't belong to this user.
    """
    service = ReviewService(db)
    review = service.update_review(current_user, review_id, data)
    return SuccessResponse(
        data=ReviewOut.model_validate(review),
        message="Review updated successfully",
    )


@router.delete("/{review_id}", response_model=SuccessResponse)
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User: delete their own review."""
    service = ReviewService(db)
    service.delete_review(current_user, review_id)
    return SuccessResponse(message="Review deleted successfully")


# ── Vendor Routes ─────────────────────────────────────────────────────────────

@router.post("/{review_id}/reply", response_model=SuccessResponse[ReviewOut])
def vendor_reply_to_review(
    review_id: int,
    data: VendorReplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """
    Vendor replies to a review on one of their bookings.

    - Only the vendor who received the review can reply
    - Calling this again overwrites the previous reply
    - The user who wrote the review gets a notification
    - Reply is limited to 500 characters
    """
    service = ReviewService(db)
    review = service.vendor_reply(current_user, review_id, data)
    return SuccessResponse(
        data=ReviewOut.model_validate(review),
        message="Reply posted successfully",
    )


# ── Admin Routes ──────────────────────────────────────────────────────────────

@router.get("/admin/all", response_model=PaginatedResponse[ReviewOut])
def admin_list_reviews(
    pagination: PaginationParams = Depends(),
    vendor_id: Optional[int] = Query(default=None, description="Filter by vendor"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Admin only: list all reviews across all vendors.
    Filter by vendor_id to see reviews for a specific vendor.
    Used for moderation — spotting fake or abusive reviews.
    """
    service = ReviewService(db)
    reviews, total = service.admin_get_all_reviews(
        skip=pagination.skip,
        limit=pagination.limit,
        vendor_id=vendor_id,
    )
    return PaginatedResponse(
        data=[ReviewOut.model_validate(r) for r in reviews],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Reviews fetched successfully",
    )


@router.delete("/admin/{review_id}", response_model=SuccessResponse)
def admin_delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Admin only: delete any review.
    Use this to remove fake, spam, or abusive reviews.
    This action cannot be undone.
    """
    service = ReviewService(db)
    service.admin_delete_review(review_id)
    return SuccessResponse(message=f"Review {review_id} deleted successfully")