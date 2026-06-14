# app/core/exceptions.py
# All custom exceptions for the application.
# Raise these from service layers — the global handler in main.py converts
# them into consistent JSON responses automatically.

from typing import Optional


class AppException(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundException(AppException):
    """Resource does not exist."""
    def __init__(self, resource: str = "Resource", id: Optional[int] = None):
        msg = f"{resource} not found" if id is None else f"{resource} with id {id} not found"
        super().__init__(message=msg, status_code=404)


class UnauthorizedException(AppException):
    """Request is not authenticated."""
    def __init__(self, message: str = "Not authenticated"):
        super().__init__(message=message, status_code=401)


class ForbiddenException(AppException):
    """Authenticated but not allowed to perform this action."""
    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(message=message, status_code=403)


class ConflictException(AppException):
    """Resource already exists."""
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message=message, status_code=409)


class ValidationException(AppException):
    """Business rule validation failed (beyond Pydantic schema validation)."""
    def __init__(self, message: str):
        super().__init__(message=message, status_code=422)


class BadRequestException(AppException):
    """Generic bad request."""
    def __init__(self, message: str):
        super().__init__(message=message, status_code=400)


class ServiceUnavailableException(AppException):
    """External service (Stripe, S3, email) is unavailable."""
    def __init__(self, service: str = "Service"):
        super().__init__(message=f"{service} is currently unavailable", status_code=503)