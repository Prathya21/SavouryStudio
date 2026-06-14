# app/services/review_service.py

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone

from app.models.review import Review
from app.models.booking import Booking
from app.models.vendor import Vendor
from app.models.notification import Notification
from app.models.user import User
from app.schemas.review import CreateReviewRequest, UpdateReviewRequest, VendorReplyRequest
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    BadRequestException,
    ConflictException,
)
from app.core.logging import logger


class ReviewService:

    def __init__(self, db: Session):
        self.db = db

    # ── Create Review ─────────────────────────────────────────────────────────

    def create_review(self, user: User, data: CreateReviewRequest) -> Review:
        """
        User submits a review after a completed booking.

        Rules enforced here:
        1. Booking must exist and belong to this user
           — prevents users from reviewing bookings that aren't theirs
        2. Booking must be in 'completed' status
           — prevents reviews on cancelled or still-active bookings
        3. Only one review per booking
           — the DB has a unique constraint on booking_id but we check
             here first to return a cleaner error message
        4. After creation, the vendor gets a notification so they can
           respond to the review
        """
        # Verify booking belongs to user
        booking = self.db.query(Booking).filter(
            Booking.id == data.booking_id,
            Booking.user_id == user.id,
        ).first()
        if not booking:
            raise NotFoundException("Booking", data.booking_id)

        # Only completed bookings can be reviewed
        if booking.status != "completed":
            raise BadRequestException(
                f"You can only review completed bookings. "
                f"This booking has status '{booking.status}'"
            )

        # One review per booking
        existing = self.db.query(Review).filter(
            Review.booking_id == data.booking_id
        ).first()
        if existing:
            raise ConflictException("You have already reviewed this booking")

        review = Review(
            booking_id=data.booking_id,
            user_id=user.id,
            vendor_id=booking.vendor_id,
            rating=data.rating,
            comment=data.comment,
        )
        self.db.add(review)

        # Notify the vendor about the new review
        if booking.vendor:
            self.db.add(Notification(
                user_id=booking.vendor.user_id,
                title="New Review Received",
                body=f"{user.full_name} left a {data.rating}-star review on booking #{booking.id}",
                notification_type="review",
                reference_id=booking.id,
                reference_type="booking",
            ))

        self.db.commit()
        self.db.refresh(review)
        logger.info(f"Review created by user {user.id} for booking #{data.booking_id}")
        return review

    # ── Update Own Review ─────────────────────────────────────────────────────

    def update_review(self, user: User, review_id: int, data: UpdateReviewRequest) -> Review:
        """
        User updates their own review's rating or comment.

        We verify the review belongs to this user before allowing the update.
        Updating a review clears the vendor's reply since the review content changed
        — the vendor should re-read and reply to the updated version.
        """
        review = self.db.query(Review).filter(
            Review.id == review_id,
            Review.user_id == user.id,
        ).first()
        if not review:
            raise NotFoundException("Review", review_id)

        if data.rating is not None:
            review.rating = data.rating
        if data.comment is not None:
            review.comment = data.comment

        # Clear vendor reply since the review changed
        if data.rating is not None or data.comment is not None:
            review.vendor_reply = None
            review.vendor_replied_at = None

        self.db.commit()
        self.db.refresh(review)
        logger.info(f"Review {review_id} updated by user {user.id}")
        return review

    def delete_review(self, user: User, review_id: int) -> None:
        """
        User deletes their own review.
        Once deleted the booking becomes reviewable again — though this is
        unlikely to happen in practice.
        """
        review = self.db.query(Review).filter(
            Review.id == review_id,
            Review.user_id == user.id,
        ).first()
        if not review:
            raise NotFoundException("Review", review_id)
        self.db.delete(review)
        self.db.commit()
        logger.info(f"Review {review_id} deleted by user {user.id}")

    # ── Vendor Reply ──────────────────────────────────────────────────────────

    def vendor_reply(self, user: User, review_id: int, data: VendorReplyRequest) -> Review:
        """
        Vendor replies to a review on one of their services.

        We first get the vendor profile for the logged-in user, then verify
        the review is for one of their bookings. This prevents vendors from
        replying to reviews that aren't theirs.

        Subsequent calls overwrite the previous reply — vendors can update
        their reply at any time.
        """
        # Get vendor profile for this user
        vendor = self.db.query(Vendor).filter(Vendor.user_id == user.id).first()
        if not vendor:
            raise NotFoundException("Vendor profile")

        # Verify the review is for this vendor
        review = self.db.query(Review).filter(
            Review.id == review_id,
            Review.vendor_id == vendor.id,
        ).first()
        if not review:
            raise NotFoundException("Review", review_id)

        review.vendor_reply = data.reply
        review.vendor_replied_at = datetime.now(timezone.utc)

        # Notify the user that the vendor replied
        self.db.add(Notification(
            user_id=review.user_id,
            title="Vendor Replied to Your Review",
            body=f"The vendor has responded to your review",
            notification_type="review",
            reference_id=review.id,
            reference_type="review",
        ))

        self.db.commit()
        self.db.refresh(review)
        logger.info(f"Vendor {vendor.id} replied to review {review_id}")
        return review

    # ── Read Operations ───────────────────────────────────────────────────────

    def get_vendor_reviews(self, vendor_id: int, skip: int, limit: int):
        """
        Public: get all reviews for a specific vendor.
        Used on the vendor's public profile page.
        Ordered by newest first so the most recent feedback is shown first.
        """
        # Verify vendor exists
        vendor = self.db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if not vendor:
            raise NotFoundException("Vendor", vendor_id)

        query = self.db.query(Review).filter(Review.vendor_id == vendor_id)
        total = query.count()
        reviews = query.order_by(Review.id.desc()).offset(skip).limit(limit).all()
        return reviews, total

    def get_vendor_rating_summary(self, vendor_id: int) -> dict:
        """
        Aggregated rating stats for a vendor's public profile.
        Computes average rating and star distribution in a single DB query.
        """
        vendor = self.db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if not vendor:
            raise NotFoundException("Vendor", vendor_id)

        reviews = self.db.query(Review).filter(Review.vendor_id == vendor_id).all()
        total = len(reviews)

        if total == 0:
            return {
                "vendor_id": vendor_id,
                "total_reviews": 0,
                "average_rating": 0.0,
                "five_star": 0,
                "four_star": 0,
                "three_star": 0,
                "two_star": 0,
                "one_star": 0,
            }

        avg = sum(r.rating for r in reviews) / total
        return {
            "vendor_id": vendor_id,
            "total_reviews": total,
            "average_rating": round(avg, 2),
            "five_star": sum(1 for r in reviews if r.rating == 5),
            "four_star": sum(1 for r in reviews if r.rating == 4),
            "three_star": sum(1 for r in reviews if r.rating == 3),
            "two_star": sum(1 for r in reviews if r.rating == 2),
            "one_star": sum(1 for r in reviews if r.rating == 1),
        }

    def get_my_reviews(self, user: User, skip: int, limit: int):
        """User: list all reviews they have written."""
        query = self.db.query(Review).filter(Review.user_id == user.id)
        total = query.count()
        reviews = query.order_by(Review.id.desc()).offset(skip).limit(limit).all()
        return reviews, total

    def get_review_by_booking(self, user: User, booking_id: int) -> Review:
        """
        User: get the review they wrote for a specific booking.
        Useful to check if a booking has been reviewed before showing
        the 'Write a Review' button on the frontend.
        """
        review = self.db.query(Review).filter(
            Review.booking_id == booking_id,
            Review.user_id == user.id,
        ).first()
        if not review:
            raise NotFoundException("Review for this booking")
        return review

    # ── Admin Operations ──────────────────────────────────────────────────────

    def admin_delete_review(self, review_id: int) -> None:
        """
        Admin deletes any review.
        Used to remove fake, abusive, or spam reviews.
        """
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise NotFoundException("Review", review_id)
        self.db.delete(review)
        self.db.commit()
        logger.info(f"Admin deleted review {review_id}")

    def admin_get_all_reviews(self, skip: int, limit: int, vendor_id: int = None):
        """Admin: list all reviews with optional vendor filter."""
        query = self.db.query(Review)
        if vendor_id:
            query = query.filter(Review.vendor_id == vendor_id)
        total = query.count()
        reviews = query.order_by(Review.id.desc()).offset(skip).limit(limit).all()
        return reviews, total