from fastapi import APIRouter
from app.core.logging_config import logger

router = APIRouter()

@router.get("/health")
def health_check():
    logger.info("Health check requested")

    return {
        "status": "healthy"
    }

@router.get("/db-health")
def database_health():
    logger.info("Database health requested")

    return {
        "database": "connected"
    }