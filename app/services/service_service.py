# app/services/service_service.py
# Business logic for vendor services and service images.

from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import UploadFile

from app.models.service import Service, ServiceImage
from app.models.vendor import Vendor
from app.models.user import User
from app.schemas.service import ServiceCreateRequest, ServiceUpdateRequest, AdminServiceActionRequest
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    BadRequestException,
    ConflictException,
)
from app.utils.s3 import upload_image, delete_file
from app.core.logging import logger


class ServiceService:

    def __init__(self, db: Session):
        self.db = db

    def _get_vendor_or_404(self, user: User) -> Vendor:
        vendor = self.db.query(Vendor).filter(Vendor.user_id == user.id).first()
        if not vendor:
            raise NotFoundException("Vendor profile")
        if vendor.status != "approved":
            raise ForbiddenException("Your vendor account must be approved before listing services")
        return vendor

    # ── Public Browse ─────────────────────────────────────────────────────────

    def get_public_services(
        self,
        skip: int,
        limit: int,
        category_id: int = None,
        vendor_id: int = None,
        search: str = None,
    ):
        """Public: approved and active services only."""
        query = self.db.query(Service).filter(
            Service.status == "approved",
            Service.is_active == True,
        )
        if category_id:
            query = query.filter(Service.category_id == category_id)
        if vendor_id:
            query = query.filter(Service.vendor_id == vendor_id)
        if search:
            query = query.filter(
                or_(
                    Service.title.ilike(f"%{search}%"),
                    Service.description.ilike(f"%{search}%"),
                )
            )
        total = query.count()
        services = query.order_by(Service.id.desc()).offset(skip).limit(limit).all()
        return services, total

    def get_public_service_by_id(self, service_id: int) -> Service:
        service = self.db.query(Service).filter(
            Service.id == service_id,
            Service.status == "approved",
            Service.is_active == True,
        ).first()
        if not service:
            raise NotFoundException("Service", service_id)
        return service

    # ── Vendor Operations ─────────────────────────────────────────────────────

    def create_service(self, user: User, data: ServiceCreateRequest) -> Service:
        vendor = self._get_vendor_or_404(user)

        service = Service(
            vendor_id=vendor.id,
            category_id=data.category_id,
            title=data.title,
            description=data.description,
            price=data.price,
            discount_price=data.discount_price,
            unit=data.unit,
            status="pending",
            is_active=True,
        )
        self.db.add(service)
        self.db.commit()
        self.db.refresh(service)
        logger.info(f"Service created by vendor {vendor.id}: {data.title}")
        return service

    def get_my_services(self, user: User, skip: int, limit: int):
        vendor = self.db.query(Vendor).filter(Vendor.user_id == user.id).first()
        if not vendor:
            raise NotFoundException("Vendor profile")
        query = self.db.query(Service).filter(Service.vendor_id == vendor.id)
        total = query.count()
        services = query.order_by(Service.id.desc()).offset(skip).limit(limit).all()
        return services, total

    def update_service(self, user: User, service_id: int, data: ServiceUpdateRequest) -> Service:
        service = self._get_service_owned_by(user, service_id)

        if data.title is not None:
            service.title = data.title
        if data.description is not None:
            service.description = data.description
        if data.price is not None:
            service.price = data.price
        if data.discount_price is not None:
            service.discount_price = data.discount_price
        if data.unit is not None:
            service.unit = data.unit
        if data.category_id is not None:
            service.category_id = data.category_id
        if data.is_active is not None:
            service.is_active = data.is_active

        # Editing a service resets it to pending for re-approval
        service.status = "pending"
        self.db.commit()
        self.db.refresh(service)
        logger.info(f"Service {service_id} updated — reset to pending")
        return service

    def delete_service(self, user: User, service_id: int) -> None:
        service = self._get_service_owned_by(user, service_id)
        for img in service.images:
            delete_file(img.image_url)
        self.db.delete(service)
        self.db.commit()
        logger.info(f"Service {service_id} deleted by vendor")

    def _get_service_owned_by(self, user: User, service_id: int) -> Service:
        vendor = self.db.query(Vendor).filter(Vendor.user_id == user.id).first()
        if not vendor:
            raise NotFoundException("Vendor profile")
        service = self.db.query(Service).filter(
            Service.id == service_id,
            Service.vendor_id == vendor.id,
        ).first()
        if not service:
            raise NotFoundException("Service", service_id)
        return service

    # ── Service Images ────────────────────────────────────────────────────────

    async def add_service_image(
        self, user: User, service_id: int, file: UploadFile, is_primary: bool = False
    ) -> ServiceImage:
        service = self._get_service_owned_by(user, service_id)

        # If setting as primary, clear existing primary flag
        if is_primary:
            for img in service.images:
                img.is_primary = False

        url = await upload_image(file, folder="services")
        image = ServiceImage(
            service_id=service.id,
            image_url=url,
            is_primary=is_primary or len(service.images) == 0,
            sort_order=len(service.images),
        )
        self.db.add(image)
        self.db.commit()
        self.db.refresh(image)
        return image

    def delete_service_image(self, user: User, service_id: int, image_id: int) -> None:
        self._get_service_owned_by(user, service_id)
        image = self.db.query(ServiceImage).filter(
            ServiceImage.id == image_id,
            ServiceImage.service_id == service_id,
        ).first()
        if not image:
            raise NotFoundException("Image", image_id)
        delete_file(image.image_url)
        self.db.delete(image)
        self.db.commit()

    # ── Admin Operations ──────────────────────────────────────────────────────

    def admin_get_all_services(self, skip: int, limit: int, status: str = None):
        query = self.db.query(Service)
        if status:
            query = query.filter(Service.status == status)
        total = query.count()
        services = query.order_by(Service.id.desc()).offset(skip).limit(limit).all()
        return services, total

    def admin_get_service(self, service_id: int) -> Service:
        service = self.db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise NotFoundException("Service", service_id)
        return service

    def admin_service_action(self, service_id: int, data: AdminServiceActionRequest) -> Service:
        service = self.admin_get_service(service_id)

        if data.action == "approve":
            service.status = "approved"
            service.rejection_reason = None
        elif data.action == "reject":
            if not data.rejection_reason:
                raise BadRequestException("A rejection reason is required")
            service.status = "rejected"
            service.rejection_reason = data.rejection_reason

        self.db.commit()
        self.db.refresh(service)
        logger.info(f"Admin {data.action}d service {service_id}")
        return service