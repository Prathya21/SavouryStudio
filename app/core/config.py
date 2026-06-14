# app/core/config.py
# Central settings — reads everything from your .env file.
# Access anywhere with: from app.core.config import settings

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # AWS / S3
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = "ap-south-1"
    S3_BUCKET_NAME: Optional[str] = None

    # App
    APP_NAME: str = "SavouryStudio"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8100"]

    RAZORPAY_KEY_ID: Optional[str] = "rzp_test_dummy"
    RAZORPAY_KEY_SECRET: Optional[str] = "dummy_secret"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()