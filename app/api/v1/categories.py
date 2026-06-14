# app/api/v1/categories.py
# Register in main.py:
#   from app.api.v1 import categories
#   app.include_router(categories.router, prefix="/api/v1/categories", tags=["Categories"])

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps.auth import get_current_admin
from app.models.user import User
from app.schemas.category import CategoryCreateRequest, CategoryUpdateRequest, CategoryOut
from app.schemas.response import SuccessResponse, PaginatedResponse
from app.schemas.pagination import PaginationParams
from app.services.category_service import CategoryService

router = APIRouter()


# ── Public Routes ─────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[CategoryOut])
def list_categories(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """
    Public: list all active categories.
    Used on the browse/home page — no auth required.
    """
    service = CategoryService(db)
    categories, total = service.get_all(
        skip=pagination.skip,
        limit=pagination.limit,
        active_only=True,
    )
    return PaginatedResponse(
        data=[CategoryOut.model_validate(c) for c in categories],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Categories fetched successfully",
    )


@router.get("/{category_id}", response_model=SuccessResponse[CategoryOut])
def get_category(category_id: int, db: Session = Depends(get_db)):
    """Public: get a single category by ID."""
    service = CategoryService(db)
    category = service.get_by_id(category_id)
    return SuccessResponse(
        data=CategoryOut.model_validate(category),
        message="Category fetched successfully",
    )


# ── Admin Routes ──────────────────────────────────────────────────────────────

@router.post("", response_model=SuccessResponse[CategoryOut], status_code=201)
def create_category(
    data: CategoryCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin only: create a new service category."""
    service = CategoryService(db)
    category = service.create(data)
    return SuccessResponse(
        data=CategoryOut.model_validate(category),
        message="Category created successfully",
    )


@router.put("/{category_id}", response_model=SuccessResponse[CategoryOut])
def update_category(
    category_id: int,
    data: CategoryUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin only: update a category's name, description, image, or active status."""
    service = CategoryService(db)
    category = service.update(category_id, data)
    return SuccessResponse(
        data=CategoryOut.model_validate(category),
        message="Category updated successfully",
    )


@router.put("/{category_id}/image", response_model=SuccessResponse[CategoryOut])
async def update_category_image(
    category_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Admin only: upload a category image to S3."""
    service = CategoryService(db)
    category = await service.update_image(category_id, file)
    return SuccessResponse(
        data=CategoryOut.model_validate(category),
        message="Category image updated successfully",
    )


@router.delete("/{category_id}", response_model=SuccessResponse)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Admin only: permanently delete a category.
    Note: existing services linked to this category will have category set to NULL.
    """
    service = CategoryService(db)
    service.delete(category_id)
    return SuccessResponse(message=f"Category {category_id} deleted successfully")