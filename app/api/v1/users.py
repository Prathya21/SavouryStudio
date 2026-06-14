# app/api/v1/users.py
# User management routes — own profile + admin controls.
# Register in main.py:
#   from app.api.v1 import users
#   app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])

from fastapi import APIRouter, Depends, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.api.deps.auth import get_current_user, get_current_admin
from app.models.user import User
from app.schemas.user import UpdateProfileRequest, AdminUpdateUserRequest, UserOut, UserListOut
from app.schemas.response import SuccessResponse, PaginatedResponse
from app.schemas.pagination import PaginationParams
from app.services.user_service import UserService

router = APIRouter()


# ── Own Profile Routes (any authenticated user) ───────────────────────────────

@router.get("/me", response_model=SuccessResponse[UserOut])
def get_my_profile(current_user: User = Depends(get_current_user)):
    """Get the logged-in user's full profile."""
    return SuccessResponse(
        data=UserOut.model_validate(current_user),
        message="Profile fetched successfully",
    )


@router.put("/me", response_model=SuccessResponse[UserOut])
def update_my_profile(
    data: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the logged-in user's name or phone number."""
    service = UserService(db)
    user = service.update_profile(current_user, data)
    return SuccessResponse(data=UserOut.model_validate(user), message="Profile updated successfully")


@router.put("/me/avatar", response_model=SuccessResponse[UserOut])
async def update_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a profile avatar image (JPEG, PNG, WebP — max 5MB).
    Replaces the existing avatar if one exists.
    """
    service = UserService(db)
    user = await service.update_avatar(current_user, file)
    return SuccessResponse(data=UserOut.model_validate(user), message="Avatar updated successfully")


@router.delete("/me/avatar", response_model=SuccessResponse)
def delete_my_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove the logged-in user's avatar."""
    service = UserService(db)
    service.delete_avatar(current_user)
    return SuccessResponse(message="Avatar removed successfully")


# ── Admin Routes ──────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[UserListOut])
def list_all_users(
    pagination: PaginationParams = Depends(),
    role: Optional[str] = Query(default=None, description="Filter by role: user | vendor | admin"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Admin only: paginated list of all users.
    Supports filtering by role and active status.
    """
    service = UserService(db)
    users, total = service.get_all_users(
        skip=pagination.skip,
        limit=pagination.limit,
        role=role,
        is_active=is_active,
    )
    return PaginatedResponse(
        data=[UserListOut.model_validate(u) for u in users],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Users fetched successfully",
    )


@router.get("/{user_id}", response_model=SuccessResponse[UserOut])
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin only: get any user by ID."""
    service = UserService(db)
    user = service.get_user_by_id(user_id)
    return SuccessResponse(data=UserOut.model_validate(user), message="User fetched successfully")


@router.put("/{user_id}", response_model=SuccessResponse[UserOut])
def admin_update_user(
    user_id: int,
    data: AdminUpdateUserRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin only: update a user's role, active status, name, or phone."""
    service = UserService(db)
    user = service.admin_update_user(user_id, data)
    return SuccessResponse(data=UserOut.model_validate(user), message="User updated successfully")


@router.patch("/{user_id}/deactivate", response_model=SuccessResponse[UserOut])
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin only: deactivate a user account (soft delete — user cannot login)."""
    service = UserService(db)
    user = service.deactivate_user(user_id)
    return SuccessResponse(data=UserOut.model_validate(user), message="User deactivated successfully")


@router.patch("/{user_id}/reactivate", response_model=SuccessResponse[UserOut])
def reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin only: reactivate a deactivated user account."""
    service = UserService(db)
    user = service.reactivate_user(user_id)
    return SuccessResponse(data=UserOut.model_validate(user), message="User reactivated successfully")


@router.delete("/{user_id}", response_model=SuccessResponse)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Admin only: permanently delete a user and all their data.
    This cannot be undone — use deactivate instead for reversible suspension.
    """
    service = UserService(db)
    service.delete_user(user_id)
    return SuccessResponse(message=f"User {user_id} permanently deleted")