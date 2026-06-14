from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)

    business_name = Column(String(255), nullable=False)
    business_description = Column(Text, nullable=True)
    business_phone = Column(String(20), nullable=True)
    business_email = Column(String(255), nullable=True)
    logo_url = Column(String(500), nullable=True)
    banner_url = Column(String(500), nullable=True)

    # status: pending | approved | rejected | suspended
    status = Column(String(20), nullable=False, default="pending")
    rejection_reason = Column(Text, nullable=True)

    # Payout / bank details
    bank_account_name = Column(String(255), nullable=True)
    bank_account_number = Column(String(50), nullable=True)
    bank_ifsc_code = Column(String(20), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="vendor_profile")
    services = relationship("Service", back_populates="vendor")
    bookings = relationship("Booking", back_populates="vendor")
    reviews = relationship("Review", back_populates="vendor")