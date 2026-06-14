# app/services/auth_service.py
# All authentication business logic lives here.
# Routes call this service — never put DB queries directly in routes.

from sqlalchemy.orm import Session
from jose import JWTError
from fastapi import BackgroundTasks

from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    create_password_reset_token,
    verify_password_reset_token,
)
from app.core.exceptions import (
    ConflictException,
    UnauthorizedException,
    BadRequestException,
    NotFoundException,
)
from app.utils.email import (
    send_welcome_email,
    send_password_reset_email,
)
from app.core.logging import logger


class AuthService:

    def __init__(self, db: Session):
        self.db = db

    # ── Register ──────────────────────────────────────────────────────────────

    def register(self, data: RegisterRequest, background_tasks: BackgroundTasks) -> User:
        try:
        # Check for duplicate email
            if self.db.query(User).filter(User.email == data.email).first():
                raise ConflictException("An account with this email already exists")

            if self.db.query(User).filter(User.phone == data.phone).first():
                raise ConflictException("An account with this phone number already exists")

            user = User(
                full_name=data.full_name,
                email=data.email,
                phone=data.phone,
                hashed_password=hash_password(data.password),
                role=data.role,
                is_active=True,
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

            background_tasks.add_task(send_welcome_email, user.email, user.full_name)
            logger.info(f"New user registered: {user.email} (role={user.role})")
            return user

        except Exception as e:
            import traceback
            print("REGISTER ERROR:", e)
            print(traceback.format_exc())
            raise

    # ── Login ─────────────────────────────────────────────────────────────────

    def login(self, data: LoginRequest) -> dict:
        """
        Verify credentials and return access + refresh tokens.
        Raises UnauthorizedException for wrong email or password.
        """
        user = self.db.query(User).filter(User.email == data.email).first()

        if not user or not verify_password(data.password, user.hashed_password):
            # Same message for both cases — don't reveal which is wrong
            raise UnauthorizedException("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedException("Your account has been deactivated. Please contact support.")

        access_token = create_access_token(subject=user.id, role=user.role)
        refresh_token = create_refresh_token(subject=user.id, role=user.role)

        logger.info(f"User logged in: {user.email}")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user,
        }

    # ── Refresh Token ─────────────────────────────────────────────────────────

    def refresh_access_token(self, refresh_token: str) -> str:
        """
        Validate a refresh token and issue a new access token.
        Raises UnauthorizedException if token is invalid or expired.
        """
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise UnauthorizedException("Invalid token type")

            user_id = int(payload.get("sub"))
            user = self.db.query(User).filter(User.id == user_id, User.is_active == True).first()
            if not user:
                raise UnauthorizedException("User not found")

            return create_access_token(subject=user.id, role=user.role)

        except JWTError:
            raise UnauthorizedException("Refresh token is invalid or expired")

    # ── Forgot Password ───────────────────────────────────────────────────────

    def forgot_password(self, email: str, background_tasks: BackgroundTasks) -> None:
        """
        Send a password reset email if the account exists.
        Always returns success — don't reveal whether email exists.
        """
        user = self.db.query(User).filter(User.email == email).first()
        if user:
            token = create_password_reset_token(email=email)
            background_tasks.add_task(send_password_reset_email, email, token)
            logger.info(f"Password reset requested for: {email}")

    # ── Reset Password ────────────────────────────────────────────────────────

    def reset_password(self, token: str, new_password: str) -> None:
        """
        Verify reset token and update the password.
        Raises BadRequestException if token is invalid or expired.
        """
        email = verify_password_reset_token(token)
        if not email:
            raise BadRequestException("Password reset link is invalid or has expired")

        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise NotFoundException("User")

        user.hashed_password = hash_password(new_password)
        self.db.commit()
        logger.info(f"Password reset successfully for: {email}")

    # ── Change Password ───────────────────────────────────────────────────────

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """
        Verify current password then update to new password.
        Raises UnauthorizedException if current password is wrong.
        """
        if not verify_password(current_password, user.hashed_password):
            raise UnauthorizedException("Current password is incorrect")

        user.hashed_password = hash_password(new_password)
        self.db.commit()
        logger.info(f"Password changed for user: {user.email}")