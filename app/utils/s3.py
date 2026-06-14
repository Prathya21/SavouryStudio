# app/utils/s3.py
# S3 file upload helper. Used for profile images, service images, vendor docs.

import boto3
import uuid
import os
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableException
from app.core.logging import logger

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_MB = 5


def _get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


async def upload_image(file: UploadFile, folder: str) -> str:
    """
    Upload an image to S3 and return the public URL.

    Args:
        file:   FastAPI UploadFile object
        folder: S3 folder prefix, e.g. "profiles", "services", "vendors"

    Returns:
        Public URL string of the uploaded file.

    Raises:
        BadRequestException if file type is not allowed or too large.
        ServiceUnavailableException if S3 upload fails.

    Usage:
        url = await upload_image(file, folder="services")
    """
    from app.core.exceptions import BadRequestException

    # Validate type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise BadRequestException(
            f"File type {file.content_type} not allowed. Use JPEG, PNG, or WebP."
        )

    # Validate size
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise BadRequestException(f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.")

    # Generate unique filename
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{folder}/{uuid.uuid4().hex}.{ext}"

    try:
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=filename,
            Body=contents,
            ContentType=file.content_type,
        )
        url = f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{filename}"
        logger.info(f"Uploaded file to S3: {url}")
        return url
    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        raise ServiceUnavailableException("File storage")


def delete_file(file_url: str) -> None:
    """
    Delete a file from S3 by its URL.
    Silently logs errors rather than raising — deletion failures are non-critical.
    """
    try:
        key = file_url.split(".amazonaws.com/")[-1]
        s3 = _get_s3_client()
        s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        logger.info(f"Deleted S3 file: {key}")
    except ClientError as e:
        logger.warning(f"Failed to delete S3 file {file_url}: {e}")