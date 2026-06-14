# app/services/vendor_service.py
# All vendor management business logic.

from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.models.vendor import Vendor
from app.models.user import User
from app.schemas.vendor import VendorRegisterRequest, VendorUpdateRequest, AdminVendorActionRequest
from app.core.exceptions import (
    ConflictException,
    NotFoundException,
    ForbiddenException,
    BadRequestException,
)
from app.utils.s3 import upload_image, delete_file
from app.utils.email import send_vendor_approval_email
from app.core.logging import logger


class VendorService:

    def __init__(self, db: Session):
        self.db = db

    # ── Vendor Registration ───────────────────────────────────────────────────

    def register_vendor(self, user: User, data: VendorRegisterRequest) -> Vendor:
        """
        Create a vendor profile for an existing user.
        The user's role is updated to 'vendor'.
        Raises ConflictException if user already has a vendor profile.
        """
        existing = self.db.query(Vendor).filter(Vendor.user_id == user.id).first()
        if existing:
            raise ConflictException("You already have a vendor profile")

        vendor = Vendor(
            user_id=user.id,
            business_name=data.business_name,
            business_description=data.business_description,
            business_phone=data.business_phone,
            business_email=data.business_email,
            status="pending",
            is_active=True,
        )
        self.db.add(vendor)

        # Upgrade user role to vendor
        user.role = "vendor"
        self.db.commit()
        self.db.refresh(vendor)

        logger.info(f"Vendor profile created for user {user.id}: {data.business_name}")
        return vendor

    # ── Own Profile ───────────────────────────────────────────────────────────

    def get_my_vendor_profile(self, user: User) -> Vendor:
        """Get the vendor profile of the currently logged-in vendor."""
        vendor = self.db.query(Vendor).filter(Vendor.user_id == user.id).first()
        if not vendor:
            raise NotFoundException("Vendor profile")
        return vendor

    def update_vendor_profile(self, user: User, data: VendorUpdateRequest) -> Vendor:
        """Vendor updates their own business details."""
        vendor = self.get_my_vendor_profile(user)

        if data.business_name is not None:
            vendor.business_name = data.business_name
        if data.business_description is not None:
            vendor.business_description = data.business_description
        if data.business_phone is not None:
            vendor.business_phone = data.business_phone
        if data.business_email is not None:
            vendor.business_email = data.business_email
        if data.bank_account_name is not None:
            vendor.bank_account_name = data.bank_account_name
        if data.bank_account_number is not None:
            vendor.bank_account_number = data.bank_account_number
        if data.bank_ifsc_code is not None:
            vendor.bank_ifsc_code = data.bank_ifsc_code

        self.db.commit()
        self.db.refresh(vendor)
        logger.info(f"Vendor {vendor.id} updated their profile")
        return vendor

    async def update_vendor_logo(self, user: User, file: UploadFile) -> Vendor:
        """Upload a new logo to S3 and update the vendor profile."""
        vendor = self.get_my_vendor_profile(user)
        if vendor.logo_url:
            delete_file(vendor.logo_url)
        vendor.logo_url = await upload_image(file, folder="vendor_logos")
        self.db.commit()
        self.db.refresh(vendor)
        return vendor

    async def update_vendor_banner(self, user: User, file: UploadFile) -> Vendor:
        """Upload a new banner image to S3."""
        vendor = self.get_my_vendor_profile(user)
        if vendor.banner_url:
            delete_file(vendor.banner_url)
        vendor.banner_url = await upload_image(file, folder="vendor_banners")
        self.db.commit()
        self.db.refresh(vendor)
        return vendor

    # ── Admin Operations ──────────────────────────────────────────────────────

    def get_all_vendors(self, skip: int, limit: int, status: str = None):
        """Admin: paginated list of all vendors with optional status filter."""
        query = self.db.query(Vendor)
        if status:
            query = query.filter(Vendor.status == status)
        total = query.count()
        vendors = query.order_by(Vendor.id.desc()).offset(skip).limit(limit).all()
        return vendors, total

    def get_vendor_by_id(self, vendor_id: int) -> Vendor:
        """Admin: get any vendor by ID."""
        vendor = self.db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if not vendor:
            raise NotFoundException("Vendor", vendor_id)
        return vendor

    def admin_vendor_action(
        self,
        vendor_id: int,
        data: AdminVendorActionRequest,
        background_tasks=None,
    ) -> Vendor:
        """
        Admin approves, rejects, or suspends a vendor.
        Sends an email notification to the vendor in the background.
        """
        vendor = self.get_vendor_by_id(vendor_id)

        if data.action == "approve":
            if vendor.status == "approved":
                raise BadRequestException("Vendor is already approved")
            vendor.status = "approved"
            vendor.rejection_reason = None
            vendor.is_active = True
            approved = True

        elif data.action == "reject":
            if not data.rejection_reason:
                raise BadRequestException("A rejection reason is required")
            vendor.status = "rejected"
            vendor.rejection_reason = data.rejection_reason
            vendor.is_active = False
            approved = False

        elif data.action == "suspend":
            vendor.status = "suspended"
            vendor.is_active = False
            approved = False

        self.db.commit()
        self.db.refresh(vendor)

        # Send email notification in background
        if background_tasks and vendor.business_email:
            background_tasks.add_task(
                send_vendor_approval_email,
                vendor.business_email,
                vendor.business_name,
                approved,
                data.rejection_reason,
            )

        logger.info(f"Admin performed '{data.action}' on vendor {vendor_id}")
        return vendor

    def delete_vendor(self, vendor_id: int) -> None:
        """Admin: permanently delete a vendor profile."""
        vendor = self.get_vendor_by_id(vendor_id)
        user = self.db.query(User).filter(User.id == vendor.user_id).first()

        # Clean up S3 assets
        if vendor.logo_url:
            delete_file(vendor.logo_url)
        if vendor.banner_url:
            delete_file(vendor.banner_url)

        # Downgrade user role back to regular user
        if user:
            user.role = "user"

        self.db.delete(vendor)
        self.db.commit()
        logger.info(f"Admin deleted vendor {vendor_id}")