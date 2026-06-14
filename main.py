# main.py  (project root)
# FastAPI application entry point.
# Run with: uvicorn main:app --reload

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import logger

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME}...")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


# ── App instance ──────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description="Service Booking Platform API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handlers ─────────────────────────────────────────────────

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handles all custom AppExceptions (NotFoundException, ForbiddenException, etc.)"""
    logger.warning(f"{exc.__class__.__name__}: {exc.message} | Path: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message, "detail": None},
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handles Pydantic validation errors from request bodies."""
    errors = exc.errors()
    message = errors[0]["msg"] if errors else "Validation error"
    return JSONResponse(
        status_code=422,
        content={"success": False, "message": message, "detail": errors},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    import traceback
    print("=" * 60)
    print("UNHANDLED EXCEPTION:")
    print(traceback.format_exc())
    print("=" * 60)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": str(exc), "detail": traceback.format_exc()},
    )


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health_check():
    return {"success": True, "message": f"{settings.APP_NAME} is running"}

# ── Routers ───────────────────────────────────────────────────────────────────
# Uncomment each router as you build the corresponding module.

from app.api.v1 import auth
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])

from app.api.v1 import users
app.include_router(users.router,         prefix="/api/v1/users",         tags=["Users"])
from app.api.v1 import vendors
app.include_router(vendors.router,       prefix="/api/v1/vendors",       tags=["Vendors"])
from app.api.v1 import categories
app.include_router(categories.router,    prefix="/api/v1/categories",    tags=["Categories"])
from app.api.v1 import services
app.include_router(services.router,      prefix="/api/v1/services",      tags=["Services"])
from app.api.v1 import bookings
app.include_router(bookings.router,      prefix="/api/v1/bookings",      tags=["Bookings"])
from app.api.v1 import payments
app.include_router(payments.router,      prefix="/api/v1/payments",      tags=["Payments"])
from app.api.v1 import reviews
app.include_router(reviews.router,       prefix="/api/v1/reviews",       tags=["Reviews"])
# from app.api.v1 import notifications
# app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
