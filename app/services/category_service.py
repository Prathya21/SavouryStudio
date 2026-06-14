# app/services/category_service.py

from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.models.category import Category
from app.schemas.category import CategoryCreateRequest, CategoryUpdateRequest
from app.core.exceptions import ConflictException, NotFoundException
from app.utils.s3 import upload_image, delete_file
from app.core.logging import logger


class CategoryService:

    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int, limit: int, active_only: bool = True):
        query = self.db.query(Category)
        if active_only:
            query = query.filter(Category.is_active == True)
        total = query.count()
        categories = query.order_by(Category.name).offset(skip).limit(limit).all()
        return categories, total

    def get_by_id(self, category_id: int) -> Category:
        category = self.db.query(Category).filter(Category.id == category_id).first()
        if not category:
            raise NotFoundException("Category", category_id)
        return category

    def create(self, data: CategoryCreateRequest) -> Category:
        existing = self.db.query(Category).filter(Category.name == data.name).first()
        if existing:
            raise ConflictException(f"Category '{data.name}' already exists")

        category = Category(
            name=data.name,
            description=data.description,
            image_url=data.image_url,
            is_active=True,
        )
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        logger.info(f"Category created: {data.name}")
        return category

    def update(self, category_id: int, data: CategoryUpdateRequest) -> Category:
        category = self.get_by_id(category_id)

        if data.name and data.name != category.name:
            existing = self.db.query(Category).filter(
                Category.name == data.name,
                Category.id != category_id
            ).first()
            if existing:
                raise ConflictException(f"Category '{data.name}' already exists")

        if data.name is not None:
            category.name = data.name
        if data.description is not None:
            category.description = data.description
        if data.image_url is not None:
            category.image_url = data.image_url
        if data.is_active is not None:
            category.is_active = data.is_active

        self.db.commit()
        self.db.refresh(category)
        logger.info(f"Category {category_id} updated")
        return category

    async def update_image(self, category_id: int, file: UploadFile) -> Category:
        category = self.get_by_id(category_id)
        if category.image_url:
            delete_file(category.image_url)
        category.image_url = await upload_image(file, folder="categories")
        self.db.commit()
        self.db.refresh(category)
        return category

    def delete(self, category_id: int) -> None:
        category = self.get_by_id(category_id)
        if category.image_url:
            delete_file(category.image_url)
        self.db.delete(category)
        self.db.commit()
        logger.info(f"Category {category_id} deleted")