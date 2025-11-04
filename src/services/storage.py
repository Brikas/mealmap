import base64
import datetime
import io
import uuid
from enum import Enum

import boto3
from loguru import logger
from mypy_boto3_s3 import S3Client

from src.conf.settings import settings

# LARS: Can I keep this root level?
s3_client: S3Client = boto3.client(
    "s3",  # type: ignore
    region_name=settings.AWS_REGION_NAME,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


class ObjectDescriptor(str, Enum):
    """Enum for object descriptors."""

    IMAGE_GROUP = "image_group"
    IMAGE_ITEM = "image_item"
    IMAGE_USER_PROFILE = "image_user_profile"
    IMAGE_OTHER = "image_other"


def generate_image_object_name(
    descriptor: ObjectDescriptor,
    file_extension: str = ".jpg",
) -> str:
    """Generate a unique object name for the image with timestamp."""
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M")
    random_string = uuid.uuid4().hex[
        :12
    ]  # 8-character random stringExtract the filename and extension

    if descriptor == ObjectDescriptor.IMAGE_ITEM:
        descriptor_str = "item"
    elif descriptor == ObjectDescriptor.IMAGE_GROUP:
        descriptor_str = "group"
    elif descriptor == ObjectDescriptor.IMAGE_USER_PROFILE:
        descriptor_str = "profile"
    elif descriptor == ObjectDescriptor.IMAGE_OTHER:
        descriptor_str = "other"
    else:
        raise ValueError(f"Invalid descriptor: {descriptor}")

    return f"{descriptor_str}_{timestamp}_{random_string}{file_extension}"


# TODO: Optimize to run this as a background task and return a smth similar to promise
def upload_image_from_base64(
    base64_image: str,
    object_name: str,
) -> str:
    """Uploads an image from a base64 string to S3.

    Args:
        base64_image: The base64 encoded image string.
        object_name: The desired file name in S3. If None, a unique name is generated.

    Returns:
        The S3 image object name. (To get a URL, it needs to be presigned.)

    Raises:
        ValueError: If the base64 string is invalid.
        Exception: If there is an error uploading to S3 or signing image.
    """
    if settings.AWS_BUCKET_NAME is None:
        raise ValueError("AWS_BUCKET_NAME not found in environment variables.")

    try:
        image_data = base64.b64decode(base64_image)
    except Exception as e:
        raise ValueError(f"Invalid base64 string: {e}") from e

    # Ensure the file name has a valid extension
    if not object_name.lower().endswith((".jpg", ".jpeg", ".png")):
        raise ValueError("File name must end with .jpg, .jpeg, or .png")

    # Upload the image to S3
    s3_client.upload_fileobj(
        io.BytesIO(image_data),
        settings.AWS_BUCKET_NAME,
        object_name,
        ExtraArgs={"ContentType": "image/jpeg"},
    )
    logger.info(f"Image uploaded to S3: {object_name}")

    return object_name


def upload_image_from_bytes(
    image_bytes: bytes,
    object_name: str,
) -> str:
    """Uploads an image from bytes to S3.

    Args:
        image_bytes: The image data as bytes.
        filename: The desired file name in S3. If None, a unique name is generated.

    Returns:
        The S3 image object name.
    """
    if settings.AWS_BUCKET_NAME is None:
        raise ValueError("AWS_BUCKET_NAME not found in environment variables.")

    # Ensure the file name has a valid extension
    if not object_name.lower().endswith((".jpg", ".jpeg", ".png")):
        raise ValueError("File name must end with .jpg, .jpeg, or .png")

    s3_client.upload_fileobj(
        io.BytesIO(image_bytes),
        settings.AWS_BUCKET_NAME,
        object_name,
        ExtraArgs={"ContentType": "image/jpeg"},
    )
    logger.info(f"Image uploaded to S3: {object_name}")
    return object_name


def generate_presigned_url_or_none(
    object_name: str | None,
    mime_type: str = "image/jpeg",
    expiration: int = 604800,  # 7 days
) -> str | None:
    """Generate a presigned URL for the given object in S3."""
    if object_name is None:
        return None
    return generate_presigned_url(object_name, mime_type, expiration)


def generate_presigned_url(
    object_name: str,
    mime_type: str = "image/jpeg",
    expiration: int = 604800,
) -> str:
    """Generate a presigned URL for the given object in S3."""
    if settings.AWS_BUCKET_NAME is None:
        raise ValueError("AWS_BUCKET_NAME not found in environment variables.")

    url = s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.AWS_BUCKET_NAME,
            "Key": object_name,
            "ResponseContentType": mime_type,
        },
        ExpiresIn=expiration,
    )
    return url  # noqa: RET504


def delete_image(object_name: str) -> None:
    """Delete an image from S3."""
    if settings.AWS_BUCKET_NAME is None:
        raise ValueError("AWS_BUCKET_NAME not found in environment variables.")
    try:
        s3_client.delete_object(Bucket=settings.AWS_BUCKET_NAME, Key=object_name)
        logger.info(f"Image deleted from S3: {object_name}")
    except Exception as e:
        logger.error(f"Failed to delete image from S3: {object_name} - {e}")


def delete_images(object_names: list[str]) -> None:
    """Delete multiple images from S3."""
    for object_name in object_names:
        delete_image(object_name)
