import uuid
from typing import Annotated, Dict, List, Literal, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from loguru import logger
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from sqlalchemy import String, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import jwt_utils
from src.api.common_schemas import BackendImageResponse
from src.api.dependencies import get_current_user

# Import schemas from reviews route (assuming no circular dependency issues for schemas)
# If this fails, we might need to move schemas to common_schemas.py
from src.api.routes_reviews import (
    PlaceBasicInfo,
    ReviewResponse,
    ReviewTags,
    UserBasicInfo,
)
from src.db.models import MealReview, MealReviewImage, Place, User
from src.db.session import get_async_db_session
from src.services import image_processing, storage
from src.services.recommendation import RecommendationService
from src.utils.pagination import Page, PaginationInput, paginate_query

router = APIRouter()


class UserResponse(BaseModel):
    id: uuid.UUID
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    image_url: Optional[str] = None
    test_id: Optional[str] = None


class UserUpdate(BaseModel):
    """Data transfer object for updating user information."""

    # email: str TODO Implement
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    # image: Optional[str] = Field(
    #     default=None,
    #     max_length=3 * 1024 * 1024,
    #     description="Base64-encoded JPEG image, max size 3MB",
    # )


@router.get("/users", response_model=Page[UserResponse])
async def search_users(
    q: str = Query(..., min_length=1, description="Search query (name or email)"),
    pagination: PaginationInput = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> Page[UserResponse]:
    """
    Search users by name or email (case-insensitive, paginated).
    """
    q = q.strip()

    query = select(User).where(
        (
            (User.email.ilike(f"%{q}%"))
            | (User.first_name.ilike(f"%{q}%"))
            | (User.last_name.ilike(f"%{q}%"))
            | (func.concat(User.first_name, " ", User.last_name).ilike(f"%{q}%"))
        )
        & (User.id != current_user.id)
    )
    page_obj = await paginate_query(
        query, db, page=pagination.page, page_size=pagination.page_size
    )
    results = [
        UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            image_url=storage.generate_presigned_url_or_none(user.image_path),
            test_id=getattr(user, "test_id", None),
        )
        for user in page_obj.results
    ]
    return Page[UserResponse](
        results=results,
        total_items=page_obj.total_items,
        start_index=page_obj.start_index,
        end_index=page_obj.end_index,
        total_pages=page_obj.total_pages,
        current_page=page_obj.current_page,
        current_page_size=page_obj.current_page_size,
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_async_db_session),
) -> UserResponse:
    """
    Get user details by ID.
    """
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        image_url=storage.generate_presigned_url_or_none(user.image_path),
        test_id=getattr(user, "test_id", None),
    )


class UserProfileImageUpdate(BaseModel):
    image: UploadFile = Field(description="Profile image file")

    @field_validator("image")
    @classmethod
    def validate_image_size(cls, img: UploadFile) -> UploadFile:
        max_size = 5 * 1024 * 1024  # 5MB in bytes
        if img.size is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "File size could not be determined. "
                    "Please ensure the file is valid."
                ),
            )

        if img.size > max_size:
            raise HTTPException(
                status_code=413,
                detail=(
                    "File size exceeds 5MB limit. "
                    f"Uploaded file size: {img.size / (1024 * 1024):.2f}MB"
                ),
            )
        return img


class ImageUploadResponse(BaseModel):
    image_url: str


@router.post("/users/{user_id}/profile-image")
async def upload_profile_image(
    image_data: Annotated[UserProfileImageUpdate, Form()],
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db_session),
) -> ImageUploadResponse:
    """
    Upload a new profile image for the user.

    Delete the old image as a background task if it exists.
    """

    img_bytes = await image_data.image.read()
    try:
        processed_image_bytes, _metadata = await run_in_threadpool(
            image_processing.process_image_to_jpeg_fill_center, img_bytes, (1024, 1024)
        )

    except image_processing.InvalidImageError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid image.",
        ) from e
    except image_processing.ImageTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image resolution too large.",
        ) from e
    except image_processing.ImageProcessingError as e:
        logger.error(f"Error processing image: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error processing image. Please try another image.",
        ) from e

    object_name = storage.generate_image_object_name(
        storage.ObjectDescriptor.IMAGE_USER_PROFILE,
    )
    image_path = storage.upload_image_from_bytes(
        image_bytes=processed_image_bytes,
        object_name=object_name,
    )

    user = await db.get(User, current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth and db user mismatch. Db user not found.",
        )

    old_image_path = user.image_path
    user.image_path = image_path
    await db.commit()

    # background task to delete old image if it exists
    if old_image_path:
        background_tasks.add_task(
            storage.delete_image,
            old_image_path,
        )

    presigned_image_url = storage.generate_presigned_url(object_name=image_path)
    return ImageUploadResponse(image_url=presigned_image_url)


@router.post("/users/{user_id}")
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_async_db_session),
) -> UserResponse:
    if current_user.id != uuid.UUID(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )
    # Fetch the user from the database

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user_data.first_name is not None:
        user.first_name = user_data.first_name
    if user_data.last_name is not None:
        user.last_name = user_data.last_name

    # if user_data.image is not None:
    #     object_name = storage.generate_image_object_name(
    #         storage.ObjectDescriptor.IMAGE_USER_PROFILE,
    #     )
    #     user.image_path = storage.upload_image_from_base64(
    #         base64_image=user_data.image, object_name=object_name
    #     )

    db.add(user)  # Explicitly add the user object
    await db.commit()
    await db.refresh(user)

    presigned_image_url = None
    if user.image_path is not None:
        presigned_image_url = storage.generate_presigned_url(
            object_name=user.image_path,
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        image_url=presigned_image_url,
        test_id=user.test_id,
    )  # Return the updated user object


# src/api/routes_users.py (add this endpoint)
@router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """
    Delete the current user's account.
    """
    user = await db.get(
        User,
        current_user.id,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Add user profile image if exists
    s3_path_to_delete = None
    if user.image_path:
        s3_path_to_delete = user.image_path

    # Avoid FK violation on app_group.creator_id if present
    # await db.execute(
    #     update(Group).where(Group.creator_id == current_user.id).values(creator_id=None)  # noqa: E501
    # )

    # Delete the user (CASCADE will handle items, group_memberships, etc.)
    await db.delete(user)
    await db.commit()

    # Schedule S3 cleanup in background
    if s3_path_to_delete:
        background_tasks.add_task(
            storage.delete_image,
            s3_path_to_delete,
        )

    logger.info(f"User {current_user.id} deleted successfully")


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=7)
    new_password: str = Field(..., min_length=7)


@router.post("/users/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """
    Change the current user's password. Requires current password for verification.
    """
    user = await db.get(User, current_user.id)
    if not user or not user.hashed_password:
        raise HTTPException(status_code=404, detail="User not found")
    # Verify current password
    if not jwt_utils.verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=403, detail="Current password is incorrect")
    # Hash and set new password
    user.hashed_password = jwt_utils.get_password_hash(data.new_password)
    user.token_version += 1  # Invalidate all previous tokens
    db.add(user)
    await db.commit()
    await db.refresh(user)
    # Optionally: send notification email here


@router.get("/users/me/feed", response_model=List[ReviewResponse])
async def get_my_feed(
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db_session),
) -> List[ReviewResponse]:
    """
    Get personalized meal feed for the current user.
    """
    service = RecommendationService(db)
    reviews = await service.get_user_feed(current_user.id, limit=limit)

    results = []
    for review in reviews:
        meal = review.meal
        place = meal.place
        user = review.user

        # Get first image
        first_review_image = None
        image_count = len(review.images)
        if review.images:
            sorted_images = sorted(review.images, key=lambda i: i.sequence_index)
            first_review_image = BackendImageResponse(
                id=sorted_images[0].id,
                image_url=storage.generate_presigned_url(sorted_images[0].image_path),
                sequence_index=sorted_images[0].sequence_index,
            )

        # Get first place image
        first_place_image = None
        if place.images:
            sorted_place_images = sorted(place.images, key=lambda i: i.sequence_index)
            first_place_image = BackendImageResponse(
                id=sorted_place_images[0].id,
                image_url=storage.generate_presigned_url(
                    sorted_place_images[0].image_path
                ),
                sequence_index=sorted_place_images[0].sequence_index,
            )

        results.append(
            ReviewResponse(
                id=review.id,
                meal_id=meal.id,
                meal_name=meal.name,
                rating=review.rating,
                text=review.text,
                waiting_time_minutes=review.waiting_time_minutes,
                price=review.price,
                test_id=review.test_id,
                tags=ReviewTags(
                    is_vegan=review.is_vegan.value,
                    is_halal=review.is_halal.value,
                    is_vegetarian=review.is_vegetarian.value,
                    is_spicy=review.is_spicy.value,
                    is_gluten_free=review.is_gluten_free.value,
                    is_dairy_free=review.is_dairy_free.value,
                    is_nut_free=review.is_nut_free.value,
                ),
                image_count=image_count,
                first_image=first_review_image,
                place=PlaceBasicInfo(
                    id=place.id,
                    name=place.name,
                    address=place.address,
                    latitude=place.lat,
                    longitude=place.lng,
                    first_image=first_place_image,
                ),
                user=UserBasicInfo(
                    id=user.id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    image_url=storage.generate_presigned_url_or_none(user.image_path),
                ),
                created_at=review.created_at.isoformat(),
                # distance is None for feed
                distance_meters=None,
            )
        )

    return results
