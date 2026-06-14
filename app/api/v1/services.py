# app/api/v1/services.py
# Register in main.py:
#   from app.api.v1 import services
#   app.include_router(services.router, prefix="/api/v1/services", tags=["Services"])

from fastapi import APIRouter, Depends, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.api.deps.auth import get_current_vendor, get_current_admin
from app.models.user import User
from app.schemas.service import (
    ServiceCreateRequest,
    ServiceUpdateRequest,
    AdminServiceActionRequest,
    ServiceOut,
    ServiceListOut,
    ServiceImageOut,
)
from app.schemas.response import SuccessResponse, PaginatedResponse
from app.schemas.pagination import PaginationParams
from app.services.service_service import ServiceService

router = APIRouter()


# ── Public Routes ─────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[ServiceListOut])
def list_services(
    pagination: PaginationParams = Depends(),
    category_id: Optional[int] = Query(default=None, description="Filter by category"),
    vendor_id: Optional[int] = Query(default=None, description="Filter by vendor"),
    search: Optional[str] = Query(default=None, description="Search by title or description"),
    db: Session = Depends(get_db),
):
    """
    Public: browse all approved and active services.
    Supports filtering by category, vendor, and keyword search.
    """
    service = ServiceService(db)
    services, total = service.get_public_services(
        skip=pagination.skip,
        limit=pagination.limit,
        category_id=category_id,
        vendor_id=vendor_id,
        search=search,
    )
    return PaginatedResponse(
        data=[ServiceListOut.model_validate(s) for s in services],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Services fetched successfully",
    )


@router.get("/{service_id}", response_model=SuccessResponse[ServiceOut])
def get_service(service_id: int, db: Session = Depends(get_db)):
    """Public: get full details of a single approved service including images."""
    service = ServiceService(db)
    svc = service.get_public_service_by_id(service_id)
    return SuccessResponse(
        data=ServiceOut.model_validate(svc),
        message="Service fetched successfully",
    )


# ── Vendor Routes ─────────────────────────────────────────────────────────────

@router.post("", response_model=SuccessResponse[ServiceOut], status_code=201)
def create_service(
    data: ServiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """
    Vendor only: create a new service listing.
    Status is set to 'pending' — admin must approve before it appears publicly.
    Vendor account must be approved first.
    """
    service = ServiceService(db)
    svc = service.create_service(current_user, data)
    return SuccessResponse(
        data=ServiceOut.model_validate(svc),
        message="Service created successfully. Awaiting admin approval.",
    )


@router.get("/vendor/my-services", response_model=PaginatedResponse[ServiceListOut])
def get_my_services(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """Vendor only: list all their own services (all statuses)."""
    service = ServiceService(db)
    services, total = service.get_my_services(
        current_user,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        data=[ServiceListOut.model_validate(s) for s in services],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Your services fetched successfully",
    )


@router.put("/vendor/{service_id}", response_model=SuccessResponse[ServiceOut])
def update_service(
    service_id: int,
    data: ServiceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """
    Vendor only: update their own service.
    Note: editing a service resets it to 'pending' for re-approval.
    """
    service = ServiceService(db)
    svc = service.update_service(current_user, service_id, data)
    return SuccessResponse(
        data=ServiceOut.model_validate(svc),
        message="Service updated. Re-submitted for approval.",
    )


@router.delete("/vendor/{service_id}", response_model=SuccessResponse)
def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """Vendor only: permanently delete their own service and all its images."""
    service = ServiceService(db)
    service.delete_service(current_user, service_id)
    return SuccessResponse(message="Service deleted successfully")


# ── Service Image Routes ──────────────────────────────────────────────────────

@router.post("/vendor/{service_id}/images", response_model=SuccessResponse[ServiceImageOut], status_code=201)
async def add_service_image(
    service_id: int,
    file: UploadFile = File(...),
    is_primary: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """Vendor only: upload an image for a service (JPEG, PNG, WebP — max 5MB)."""
    service = ServiceService(db)
    image = await service.add_service_image(current_user, service_id, file, is_primary)
    return SuccessResponse(
        data=ServiceImageOut.model_validate(image),
        message="Image uploaded successfully",
    )


@router.delete("/vendor/{service_id}/images/{image_id}", response_model=SuccessResponse)
def delete_service_image(
    service_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """Vendor only: delete a specific image from their service."""
    service = ServiceService(db)
    service.delete_service_image(current_user, service_id, image_id)
    return SuccessResponse(message="Image deleted successfully")


# ── Admin Routes ──────────────────────────────────────────────────────────────

@router.get("/admin/all", response_model=PaginatedResponse[ServiceListOut])
def admin_list_services(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: pending | approved | rejected"
    ),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin only: list all services across all vendors. Filter by status to review pending."""
    service = ServiceService(db)
    services, total = service.admin_get_all_services(
        skip=pagination.skip,
        limit=pagination.limit,
        status=status,
    )
    return PaginatedResponse(
        data=[ServiceListOut.model_validate(s) for s in services],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Services fetched successfully",
    )


@router.get("/admin/{service_id}", response_model=SuccessResponse[ServiceOut])
def admin_get_service(
    service_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin only: get any service by ID regardless of status."""
    service = ServiceService(db)
    svc = service.admin_get_service(service_id)
    return SuccessResponse(
        data=ServiceOut.model_validate(svc),
        message="Service fetched successfully",
    )


@router.post("/admin/{service_id}/action", response_model=SuccessResponse[ServiceOut])
def admin_service_action(
    service_id: int,
    data: AdminServiceActionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Admin only: approve or reject a service listing.
    - approve: service becomes publicly visible
    - reject: requires rejection_reason, vendor should update and resubmit
    """
    service = ServiceService(db)
    svc = service.admin_service_action(service_id, data)
    return SuccessResponse(
        data=ServiceOut.model_validate(svc),
        message=f"Service {data.action}d successfully",
    )