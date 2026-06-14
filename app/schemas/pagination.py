# app/schemas/pagination.py
# Reusable pagination query params — use as Depends() in list endpoints.

from fastapi import Query


class PaginationParams:
    """
    Inject into any list endpoint:

        @router.get("/users")
        def list_users(pagination: PaginationParams = Depends()):
            skip = pagination.skip
            limit = pagination.limit
    """
    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="Page number"),
        limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.limit = limit
        self.skip = (page - 1) * limit