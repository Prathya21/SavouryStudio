# app/utils/validators.py
# Reusable Pydantic field validators.
# Import these into your request schemas.

import re
from typing import Any


def validate_phone_number(value: str) -> str:
    """Validates Indian mobile numbers (10 digits, optionally prefixed with +91)."""
    cleaned = re.sub(r"[\s\-\(\)]", "", value)
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    if not re.match(r"^[6-9]\d{9}$", cleaned):
        raise ValueError("Invalid phone number. Must be a valid 10-digit Indian mobile number.")
    return cleaned


def validate_password_strength(value: str) -> str:
    """
    Enforces: min 8 chars, at least one uppercase, one lowercase, one digit.
    """
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", value):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one digit.")
    return value


def validate_pincode(value: str) -> str:
    """Validates a 6-digit Indian PIN code."""
    if not re.match(r"^\d{6}$", value):
        raise ValueError("Invalid PIN code. Must be exactly 6 digits.")
    return value

    