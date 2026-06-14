# app/api/v1/vendors.py
# Vendor management routes.
# Register in main.py:
#   from app.api.v1 import vendors
#   app.include_router(vendors.router, prefix="/api/v1/vendors", tags=["Vendors"])

from fastapi import APIRouter, Depends, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.api.deps.auth import get_current_user, get_current_vendor, get_current_admin
from app.models.user import User
from app.schemas.vendor import (
    VendorRegisterRequest,
    VendorUpdateRequest,
    AdminVendorActionRequest,
    VendorOut,
    VendorDetailOut,
    VendorListOut,
)
from app.schemas.response import SuccessResponse, PaginatedResponse
from app.schemas.pagination import PaginationParams
from app.services.vendor_service import VendorService

router = APIRouter()


# ── Public Routes ─────────────────────────────────────────────────────────────

@router.get("/public", response_model=PaginatedResponse[VendorListOut])
def list_approved_vendors(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """
    Public: list all approved and active vendors.
    No authentication required — used for the browse page.
    """
    service = VendorService(db)
    vendors, total = service.get_all_vendors(
        skip=pagination.skip,
        limit=pagination.limit,
        status="approved",
    )
    return PaginatedResponse(
        data=[VendorListOut.model_validate(v) for v in vendors],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Vendors fetched successfully",
    )


@router.get("/public/{vendor_id}", response_model=SuccessResponse[VendorOut])
def get_public_vendor(vendor_id: int, db: Session = Depends(get_db)):
    """Public: get a single approved vendor's public profile."""
    service = VendorService(db)
    vendor = service.get_vendor_by_id(vendor_id)
    return SuccessResponse(
        data=VendorOut.model_validate(vendor),
        message="Vendor fetched successfully",
    )


# ── Vendor Own Profile Routes ─────────────────────────────────────────────────

@router.post("/register", response_model=SuccessResponse[VendorDetailOut], status_code=201)
def register_as_vendor(
    data: VendorRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Any logged-in user can apply to become a vendor.
    Creates a vendor profile with status 'pending' awaiting admin approval.
    The user's role is automatically upgraded to 'vendor'.
    """
    service = VendorService(db)
    vendor = service.register_vendor(current_user, data)
    return SuccessResponse(
        data=VendorDetailOut.model_validate(vendor),
        message="Vendor application submitted successfully. Awaiting admin approval.",
    )


@router.get("/me", response_model=SuccessResponse[VendorDetailOut])
def get_my_vendor_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """Vendor: get their own full vendor profile including bank details."""
    service = VendorService(db)
    vendor = service.get_my_vendor_profile(current_user)
    return SuccessResponse(
        data=VendorDetailOut.model_validate(vendor),
        message="Vendor profile fetched successfully",
    )


@router.put("/me", response_model=SuccessResponse[VendorDetailOut])
def update_my_vendor_profile(
    data: VendorUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """Vendor: update their own business details and bank info."""
    service = VendorService(db)
    vendor = service.update_vendor_profile(current_user, data)
    return SuccessResponse(
        data=VendorDetailOut.model_validate(vendor),
        message="Vendor profile updated successfully",
    )


@router.put("/me/logo", response_model=SuccessResponse[VendorDetailOut])
async def update_vendor_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """Vendor: upload a business logo (JPEG, PNG, WebP — max 5MB)."""
    service = VendorService(db)
    vendor = await service.update_vendor_logo(current_user, file)
    return SuccessResponse(
        data=VendorDetailOut.model_validate(vendor),
        message="Logo updated successfully",
    )


@router.put("/me/banner", response_model=SuccessResponse[VendorDetailOut])
async def update_vendor_banner(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_vendor),
):
    """Vendor: upload a banner image for their storefront."""
    service = VendorService(db)
    vendor = await service.update_vendor_banner(current_user, file)
    return SuccessResponse(
        data=VendorDetailOut.model_validate(vendor),
        message="Banner updated successfully",
    )


# ── Admin Routes ──────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[VendorListOut])
def admin_list_vendors(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: pending | approved | rejected | suspended"
    ),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin: paginated list of all vendors. Filter by status to review pending applications."""
    service = VendorService(db)
    vendors, total = service.get_all_vendors(
        skip=pagination.skip,
        limit=pagination.limit,
        status=status,
    )
    return PaginatedResponse(
        data=[VendorListOut.model_validate(v) for v in vendors],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Vendors fetched successfully",
    )


@router.get("/{vendor_id}", response_model=SuccessResponse[VendorDetailOut])
def admin_get_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin: get full vendor details including bank info."""
    service = VendorService(db)
    vendor = service.get_vendor_by_id(vendor_id)
    return SuccessResponse(
        data=VendorDetailOut.model_validate(vendor),
        message="Vendor fetched successfully",
    )


@router.post("/{vendor_id}/action", response_model=SuccessResponse[VendorDetailOut])
def admin_vendor_action(
    vendor_id: int,
    data: AdminVendorActionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Admin: approve, reject, or suspend a vendor.
    - approve: vendor can now list services
    - reject: requires a rejection_reason, email sent to vendor
    - suspend: temporarily disables the vendor
    """
    service = VendorService(db)
    vendor = service.admin_vendor_action(vendor_id, data, background_tasks)
    return SuccessResponse(
        data=VendorDetailOut.model_validate(vendor),
        message=f"Vendor {data.action}d successfully",
    )


@router.delete("/{vendor_id}", response_model=SuccessResponse)
def admin_delete_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin: permanently delete a vendor profile. User's role is downgraded back to 'user'."""
    service = VendorService(db)
    service.delete_vendor(vendor_id)
    return SuccessResponse(message=f"Vendor {vendor_id} deleted successfully")