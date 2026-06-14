# app/api/v1/auth.py
# All authentication routes.
# Register this router in main.py:
#   from app.api.v1 import auth
#   app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps.auth import get_current_user
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    TokenOut,
    AccessTokenOut,
    UserOut,
)
from app.schemas.response import SuccessResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=SuccessResponse[UserOut], status_code=201)
def register(
    data: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Register a new user or vendor account.
    - role must be "user" or "vendor"
    - Duplicate email or phone returns 409
    - A welcome email is sent in the background
    """
    service = AuthService(db)
    user = service.register(data, background_tasks)
    return SuccessResponse(data=UserOut.model_validate(user), message="Account created successfully")


@router.post("/login", response_model=SuccessResponse[TokenOut])
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Login with email and password.
    Returns access_token (short-lived) and refresh_token (long-lived).
    """
    service = AuthService(db)
    result = service.login(data)
    token_out = TokenOut(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        user=UserOut.model_validate(result["user"]),
    )
    return SuccessResponse(data=token_out, message="Login successful")


@router.post("/refresh", response_model=SuccessResponse[AccessTokenOut])
def refresh_token(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access token.
    Call this when the frontend gets a 401 on any protected endpoint.
    """
    service = AuthService(db)
    new_access_token = service.refresh_access_token(data.refresh_token)
    return SuccessResponse(
        data=AccessTokenOut(access_token=new_access_token),
        message="Token refreshed successfully",
    )


@router.post("/forgot-password", response_model=SuccessResponse)
def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Request a password reset email.
    Always returns success — does not reveal if the email exists.
    """
    service = AuthService(db)
    service.forgot_password(data.email, background_tasks)
    return SuccessResponse(message="If this email is registered, a reset link has been sent")


@router.post("/reset-password", response_model=SuccessResponse)
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Reset password using the token from the reset email.
    Token expires after 1 hour.
    """
    service = AuthService(db)
    service.reset_password(data.token, data.new_password)
    return SuccessResponse(message="Password reset successfully. Please login with your new password.")


@router.post("/change-password", response_model=SuccessResponse)
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Change password for the currently logged-in user.
    Requires a valid access token in the Authorization header.
    """
    service = AuthService(db)
    service.change_password(current_user, data.current_password, data.new_password)
    return SuccessResponse(message="Password changed successfully")


@router.post("/logout", response_model=SuccessResponse)
def logout(current_user: User = Depends(get_current_user)):
    """
    Logout the current user.
    The frontend must delete the stored tokens on its side.
    For full server-side blacklisting, add Redis (future enhancement).
    """
    return SuccessResponse(message="Logged out successfully")


@router.get("/me", response_model=SuccessResponse[UserOut])
def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the currently authenticated user's profile.
    Useful for the frontend to validate a stored token on app load.
    """
    return SuccessResponse(
        data=UserOut.model_validate(current_user),
        message="Profile fetched successfully",
    )