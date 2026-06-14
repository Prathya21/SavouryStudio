# app/utils/repository.py
# Generic base repository. Extend this in every service module
# to get free CRUD without repeating boilerplate.

from typing import Generic, Type, TypeVar, Optional
from sqlalchemy.orm import Session
from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Provides get, get_or_404, list, create, update, delete for any model.

    Usage:
        class UserRepository(BaseRepository[User]):
            def __init__(self, db: Session):
                super().__init__(User, db)

        repo = UserRepository(db)
        user = repo.get(1)
        users, total = repo.list(skip=0, limit=20)
    """

    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get(self, id: int) -> Optional[ModelType]:
        """Return record by primary key, or None."""
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_or_404(self, id: int) -> ModelType:
        """Return record or raise NotFoundException."""
        from app.core.exceptions import NotFoundException
        record = self.get(id)
        if not record:
            raise NotFoundException(resource=self.model.__tablename__, id=id)
        return record

    def list(self, skip: int = 0, limit: int = 20) -> tuple[list[ModelType], int]:
        """Return (records, total_count) for pagination."""
        query = self.db.query(self.model)
        total = query.count()
        records = query.offset(skip).limit(limit).all()
        return records, total

    def create(self, obj_in: dict) -> ModelType:
        """Create and commit a new record from a dict."""
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: ModelType, obj_in: dict) -> ModelType:
        """Update an existing record with provided fields."""
        for field, value in obj_in.items():
            if value is not None and hasattr(db_obj, field):
                setattr(db_obj, field, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: ModelType) -> None:
        """Hard delete a record."""
        self.db.delete(db_obj)
        self.db.commit()

    def save(self, db_obj: ModelType) -> ModelType:
        """Commit and refresh an already-modified object."""
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj