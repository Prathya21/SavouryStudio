# app/schemas/review.py

from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


# ── Request Schemas ───────────────────────────────────────────────────────────

class CreateReviewRequest(BaseModel):
    """
    User submits a review after a completed booking.
    One review per booking — enforced at the DB level (unique constraint on booking_id).
    Rating must be between 1 and 5.
    """
    booking_id: int
    rating: int
    comment: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def rating_in_range(cls, v):
        if v < 1 or v > 5:
            raise ValueError("Rating must be between 1 and 5")
        return v

    @field_validator("comment")
    @classmethod
    def comment_not_too_long(cls, v):
        if v is not None and len(v) > 1000:
            raise ValueError("Comment cannot exceed 1000 characters")
        return v


class UpdateReviewRequest(BaseModel):
    """
    User can update their own review's rating or comment.
    They cannot change which booking the review is for.
    """
    rating: Optional[int] = None
    comment: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def rating_in_range(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Rating must be between 1 and 5")
        return v


class VendorReplyRequest(BaseModel):
    """
    Vendor replies to a review left on one of their services.
    Only one reply per review — subsequent calls overwrite the reply.
    """
    reply: str

    @field_validator("reply")
    @classmethod
    def reply_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Reply cannot be empty")
        if len(v) > 500:
            raise ValueError("Reply cannot exceed 500 characters")
        return v.strip()


# ── Response Schemas ──────────────────────────────────────────────────────────

class ReviewOut(BaseModel):
    id: int
    booking_id: int
    user_id: int
    vendor_id: int
    rating: int
    comment: Optional[str] = None
    vendor_reply: Optional[str] = None
    vendor_replied_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewListOut(BaseModel):
    id: int
    user_id: int
    rating: int
    comment: Optional[str] = None
    vendor_reply: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class VendorRatingSummary(BaseModel):
    """
    Aggregated rating stats for a vendor.
    Shown on the vendor's public profile page.
    """
    vendor_id: int
    total_reviews: int
    average_rating: float
    five_star: int
    four_star: int
    three_star: int
    two_star: int
    one_star: int