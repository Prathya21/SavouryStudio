# app/schemas/response.py
# Standard API response wrappers.
# Every endpoint should return one of these so the frontend
# always gets a consistent shape: { success, message, data }

from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """
    Single-object success response.

    Example:
        return SuccessResponse(data=user, message="User fetched successfully")
    """
    success: bool = True
    message: str = "Success"
    data: Optional[T] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Paginated list response.

    Example:
        return PaginatedResponse(data=users, total=100, page=1, limit=20)
    """
    success: bool = True
    message: str = "Success"
    data: list[T] = []
    total: int = 0
    page: int = 1
    limit: int = 20
    total_pages: int = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.limit > 0:
            import math
            self.total_pages = math.ceil(self.total / self.limit)


class ErrorResponse(BaseModel):
    """
    Error response shape — produced automatically by the global exception handler.
    You do not need to return this manually; just raise an AppException.
    """
    success: bool = False
    message: str
    detail: Optional[Any] = None