from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)

    # type: booking_update | payment | review | system | promotion
    notification_type = Column(String(50), nullable=False, default="system")

    # Optional deep-link reference
    reference_id = Column(Integer, nullable=True)        # e.g. booking_id or payment_id
    reference_type = Column(String(50), nullable=True)   # e.g. "booking", "payment"

    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="notifications")