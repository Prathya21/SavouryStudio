# app/api/deps/auth.py
# FastAPI dependencies for authentication and role-based access.
# Use these as Depends() in your route functions.

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.models.user import User

bearer_scheme = HTTPBearer()


def _get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Extract and validate the JWT from the Authorization header."""
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise UnauthorizedException("Invalid token type")
        return payload
    except JWTError:
        raise UnauthorizedException("Token is invalid or expired")


def get_current_user(
    payload: dict = Depends(_get_token_payload),
    db: Session = Depends(get_db),
) -> User:
    """
    Returns the authenticated User object.
    Raises 401 if token is invalid, 404 if user no longer exists.

    Usage:
        @router.get("/me")
        def get_me(current_user: User = Depends(get_current_user)):
            ...
    """
    user_id = int(payload.get("sub"))
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise UnauthorizedException("User not found or inactive")
    return user


def get_current_vendor(current_user: User = Depends(get_current_user)) -> User:
    """
    Allows only users with role 'vendor'.
    Usage:
        @router.post("/services")
        def create_service(current_user: User = Depends(get_current_vendor)):
            ...
    """
    if current_user.role != "vendor":
        raise ForbiddenException("Vendor access required")
    return current_user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Allows only users with role 'admin'.
    Usage:
        @router.get("/admin/users")
        def list_users(current_user: User = Depends(get_current_admin)):
            ...
    """
    if current_user.role != "admin":
        raise ForbiddenException("Admin access required")
    return current_user


def get_current_user_or_vendor(current_user: User = Depends(get_current_user)) -> User:
    """Allows both regular users and vendors."""
    if current_user.role not in ("user", "vendor"):
        raise ForbiddenException("Access denied")
    return current_user