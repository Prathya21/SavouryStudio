# app/models/__init__.py
# Import every model here so that:
#   1. Base.metadata knows about all tables
#   2. Alembic autogenerate detects all models
#   3. SQLAlchemy can resolve all relationship references

from app.models.base import Base
from app.models.user import User
from app.models.address import Address
from app.models.vendor import Vendor
from app.models.category import Category
from app.models.service import Service, ServiceImage
from app.models.booking import Booking, BookingItem
from app.models.payment import Payment
from app.models.review import Review
from app.models.notification import Notification

__all__ = [
    "Base",
    "User",
    "Address",
    "Vendor",
    "Category",
    "Service",
    "ServiceImage",
    "Booking",
    "BookingItem",
    "Payment",
    "Review",
    "Notification",
]