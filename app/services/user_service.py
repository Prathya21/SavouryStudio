# app/services/user_service.py
# All user management business logic.

from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.models.user import User
from app.schemas.user import UpdateProfileRequest, AdminUpdateUserRequest
from app.core.exceptions import ConflictException, NotFoundException
from app.utils.s3 import upload_image, delete_file
from app.core.logging import logger


class UserService:

    def __init__(self, db: Session):
        self.db = db

    # ── Own Profile ───────────────────────────────────────────────────────────

    def update_profile(self, user: User, data: UpdateProfileRequest) -> User:
        """User updates their own name and/or phone."""
        if data.phone and data.phone != user.phone:
            existing = self.db.query(User).filter(
                User.phone == data.phone,
                User.id != user.id
            ).first()
            if existing:
                raise ConflictException("Phone number already in use by another account")

        if data.full_name is not None:
            user.full_name = data.full_name
        if data.phone is not None:
            user.phone = data.phone

        self.db.commit()
        self.db.refresh(user)
        logger.info(f"User {user.id} updated their profile")
        return user

    async def update_avatar(self, user: User, file: UploadFile) -> User:
        """Upload a new avatar to S3, delete the old one if it exists."""
        if user.avatar_url:
            delete_file(user.avatar_url)

        url = await upload_image(file, folder="avatars")
        user.avatar_url = url
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"User {user.id} updated avatar: {url}")
        return user

    def delete_avatar(self, user: User) -> User:
        """Remove the user's avatar from S3 and clear the field."""
        if user.avatar_url:
            delete_file(user.avatar_url)
            user.avatar_url = None
            self.db.commit()
            self.db.refresh(user)
        return user

    # ── Admin Operations ──────────────────────────────────────────────────────

    def get_all_users(self, skip: int, limit: int, role: str = None, is_active: bool = None):
        """Admin: paginated list of all users with optional filters."""
        query = self.db.query(User)

        if role:
            query = query.filter(User.role == role)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        total = query.count()
        users = query.order_by(User.id.desc()).offset(skip).limit(limit).all()
        return users, total

    def get_user_by_id(self, user_id: int) -> User:
        """Admin: get any user by ID."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundException("User", user_id)
        return user

    def admin_update_user(self, user_id: int, data: AdminUpdateUserRequest) -> User:
        """Admin: update role, active status, name, or phone of any user."""
        user = self.get_user_by_id(user_id)

        if data.phone and data.phone != user.phone:
            existing = self.db.query(User).filter(
                User.phone == data.phone,
                User.id != user_id
            ).first()
            if existing:
                raise ConflictException("Phone number already in use")

        if data.full_name is not None:
            user.full_name = data.full_name
        if data.phone is not None:
            user.phone = data.phone
        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active

        self.db.commit()
        self.db.refresh(user)
        logger.info(f"Admin updated user {user_id}: {data.model_dump(exclude_none=True)}")
        return user

    def deactivate_user(self, user_id: int) -> User:
        """Admin: soft-deactivate a user (does not delete)."""
        user = self.get_user_by_id(user_id)
        user.is_active = False
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"Admin deactivated user {user_id}")
        return user

    def reactivate_user(self, user_id: int) -> User:
        """Admin: reactivate a previously deactivated user."""
        user = self.get_user_by_id(user_id)
        user.is_active = True
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"Admin reactivated user {user_id}")
        return user

    def delete_user(self, user_id: int) -> None:
        """Admin: permanently delete a user and all their data."""
        user = self.get_user_by_id(user_id)
        if user.avatar_url:
            delete_file(user.avatar_url)
        self.db.delete(user)
        self.db.commit()
        logger.info(f"Admin permanently deleted user {user_id}")