import io
import math
import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, List, Literal, Optional, Union

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from loguru import logger
from PIL import Image
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.common_schemas import (
    BackendImageResponse,
    MessageResponse,
    ObjectCreationResponse,
)
from src.api.dependencies import get_current_user
from src.db.models import Meal, MealReview, MealReviewImage, Place, TriState, User
from src.db.session import get_async_db_session
from src.services import image_processing, storage
from src.services.recommendation import RecommendationService
from src.utils.misc_utils import calculate_distance
from src.utils.pagination import Page, PaginationInput, paginate_list

# Constants for gamification
SCORE_BASE = 10
SCORE_TEXT = 20
SCORE_TEXT_LONG = 20
SCORE_TAG = 20
SCORE_IMAGE = 50
SCORE_WAIT_TIME = 10

router = APIRouter()


# --- Request/Response Models ---


class TriStateInput(str, Enum):
    """Tri-state: "yes", "no", "unspecified"."""

    yes = "yes"
    no = "no"
    unspecified = "unspecified"


class ReviewCreationResponse(ObjectCreationResponse):
    reward: int


class PlaceBasicInfo(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    latitude: float
    longitude: float
    first_image: Optional[BackendImageResponse] = None


class UserBasicInfo(BaseModel):
    id: uuid.UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    image_url: Optional[str] = None


class ReviewTags(BaseModel):
    is_vegan: str
    is_halal: str
    is_vegetarian: str
    is_spicy: str
    is_gluten_free: str
    is_dairy_free: str
    is_nut_free: str


class ReviewResponse(BaseModel):
    id: uuid.UUID
    meal_id: uuid.UUID
    meal_name: str
    rating: int
    text: Optional[str] = None
    waiting_time_minutes: Optional[int] = None
    price: Optional[float] = None
    test_id: Optional[str] = None
    tags: ReviewTags
    image_count: int
    first_image: Optional[BackendImageResponse] = None
    place: PlaceBasicInfo
    user: UserBasicInfo
    created_at: str
    distance_meters: Optional[float] = None


class ReviewDetailedResponse(ReviewResponse):
    images: List[BackendImageResponse] = Field(
        default_factory=list, description="All review images"
    )
    updated_at: str


# --- Endpoints ---


@router.post("/reviews", response_model=ReviewCreationResponse)
async def create_review(
    rating: Annotated[int, Form(ge=1, le=5)],
    place_id: Annotated[Optional[uuid.UUID], Form()] = None,
    meal_id: Annotated[Optional[uuid.UUID], Form()] = None,
    meal_name: Annotated[Optional[str], Form(min_length=1, max_length=200)] = None,
    text: Annotated[Optional[str], Form(max_length=10000)] = None,
    waiting_time_minutes: Annotated[Optional[int], Form(ge=0)] = None,
    price: Annotated[Optional[float], Form(ge=0, le=10000000)] = None,
    test_id: Annotated[Optional[str], Form()] = None,
    is_vegan: Annotated[TriStateInput, Form()] = TriStateInput.unspecified,
    is_halal: Annotated[TriStateInput, Form()] = TriStateInput.unspecified,
    is_vegetarian: Annotated[TriStateInput, Form()] = TriStateInput.unspecified,
    is_spicy: Annotated[TriStateInput, Form()] = TriStateInput.unspecified,
    is_gluten_free: Annotated[TriStateInput, Form()] = TriStateInput.unspecified,
    is_dairy_free: Annotated[TriStateInput, Form()] = TriStateInput.unspecified,
    is_nut_free: Annotated[TriStateInput, Form()] = TriStateInput.unspecified,
    images: Optional[List[UploadFile]] = None,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_async_db_session),
) -> ObjectCreationResponse:
    """Create a new meal review with optional images (max 5).

    Either meal_id or (place_id and meal_name) must be provided to determine the meal.
    If the meal does not exist when using place_id and meal_name, it will be created.
    """
    if images is None:
        images = []

    # Validate images count
    if len(images) > 5:
        raise HTTPException(status_code=400, detail="Cannot upload more than 5 images.")

    # Determine meal
    meal = None
    if meal_id:
        meal = await db.get(Meal, meal_id)
        if not meal:
            raise HTTPException(status_code=404, detail="Meal not found")
    elif place_id and meal_name:
        # Check if place exists
        place = await db.get(Place, place_id)
        if not place:
            raise HTTPException(status_code=404, detail="Place not found")

        # Find or create meal
        result = await db.execute(
            select(Meal).where(Meal.place_id == place_id, Meal.name == meal_name)
        )
        meal = result.scalars().first()
        if not meal:
            meal = Meal(name=meal_name, place_id=place_id, test_id=test_id)
            db.add(meal)
            await db.flush()  # get ID
    else:
        raise HTTPException(
            status_code=400,
            detail="Either meal_id or (place_id and meal_name) must be provided.",
        )

    # Update meal price if provided and different
    if price is not None:
        price = round(price, 2)
        if meal.price != price:
            meal.price = price
            db.add(meal)

    # Create review
    new_review = MealReview(
        user_id=current_user.id,
        meal_id=meal.id,
        rating=rating,
        text=text,
        waiting_time_minutes=waiting_time_minutes,
        price=price,
        test_id=test_id,
        is_vegan=TriState(is_vegan.value),
        is_halal=TriState(is_halal.value),
        is_vegetarian=TriState(is_vegetarian.value),
        is_spicy=TriState(is_spicy.value),
        is_gluten_free=TriState(is_gluten_free.value),
        is_dairy_free=TriState(is_dairy_free.value),
        is_nut_free=TriState(is_nut_free.value),
    )
    db.add(new_review)
    await db.flush()

    # Upload images
    for idx, img in enumerate(images):
        if img.size and img.size > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(
                status_code=413, detail=f"Image {img.filename} exceeds 5MB limit."
            )

        try:
            img_bytes = await img.read()
            processed_image_bytes, _metadata = await run_in_threadpool(
                image_processing.process_image_to_jpeg_flexible,
                img_bytes,
                max_size=1024,
                max_aspect_ratio=2.0,
            )
        except image_processing.InvalidImageError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid image file: {img.filename}"
            ) from e
        except image_processing.ImageTooLargeError as e:
            raise HTTPException(
                status_code=400, detail=f"Image {img.filename} resolution too large."
            ) from e
        except image_processing.ImageProcessingError as e:
            logger.error(f"Error processing image {img.filename}: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Error processing image {img.filename}. Please try another.",
            ) from e

        object_name = storage.generate_image_object_name(
            storage.ObjectDescriptor.IMAGE_MEAL
        )
        image_path = storage.upload_image_from_bytes(
            image_bytes=processed_image_bytes, object_name=object_name
        )
        img_obj = MealReviewImage(
            meal_review_id=new_review.id,
            image_path=image_path,
            sequence_index=idx,
        )
        db.add(img_obj)

    await db.commit()
    await db.refresh(new_review)

    # Update Recommendation Engine
    service = RecommendationService(db)
    background_tasks.add_task(service.update_meal_features, meal.id)

    # Signal: 2.5 if rating > 2 else -2.5
    signal = 2.5 if rating > 2 else -2.5
    background_tasks.add_task(
        service.update_user_preferences, current_user.id, signal, meal.id
    )

    # Gamification
    reward = SCORE_BASE
    if text:
        reward += SCORE_TEXT
        if len(text) > 50:
            reward += SCORE_TEXT_LONG

    has_tag = any(
        tag.value in ("yes", "no")
        for tag in [
            is_vegan,
            is_halal,
            is_vegetarian,
            is_spicy,
            is_gluten_free,
            is_dairy_free,
            is_nut_free,
        ]
    )
    if has_tag:
        reward += SCORE_TAG

    if images:
        reward += SCORE_IMAGE

    if waiting_time_minutes is not None:
        reward += SCORE_WAIT_TIME

    # Update user score
    user = await db.get(User, current_user.id)
    if user:
        user.score += reward
        db.add(user)
        await db.commit()

    return ReviewCreationResponse(id=new_review.id, reward=reward)


@router.put("/reviews/{review_id}", response_model=MessageResponse)
async def update_review(
    review_id: uuid.UUID,
    meal_id: Annotated[Optional[uuid.UUID], Form()] = None,
    meal_name: Annotated[Optional[str], Form(min_length=1, max_length=200)] = None,
    rating: Annotated[Optional[int], Form(ge=1, le=5)] = None,
    text: Annotated[Optional[str], Form(max_length=10000)] = None,
    waiting_time_minutes: Annotated[Optional[int], Form(ge=0)] = None,
    price: Annotated[Optional[float], Form(ge=0, le=10000000)] = None,
    test_id: Annotated[Optional[str], Form()] = None,
    is_vegan: Annotated[Optional[TriStateInput], Form()] = None,
    is_halal: Annotated[Optional[TriStateInput], Form()] = None,
    is_vegetarian: Annotated[Optional[TriStateInput], Form()] = None,
    is_spicy: Annotated[Optional[TriStateInput], Form()] = None,
    is_gluten_free: Annotated[Optional[TriStateInput], Form()] = None,
    is_dairy_free: Annotated[Optional[TriStateInput], Form()] = None,
    is_nut_free: Annotated[Optional[TriStateInput], Form()] = None,
    add_images: Optional[List[UploadFile]] = None,
    remove_image_ids: Annotated[
        Optional[str], Form(description="Comma-separated list of image IDs to remove")
    ] = None,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_async_db_session),
) -> MessageResponse:
    """Update an existing review. Only the review creator can update."""
    if add_images is None:
        add_images = []

    result = await db.execute(
        select(MealReview)
        .where(MealReview.id == review_id)
        .options(selectinload(MealReview.images))
    )
    review = result.scalars().first()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this review"
        )

    # Update fields
    if meal_id is not None:
        meal = await db.get(Meal, meal_id)
        if not meal:
            raise HTTPException(status_code=404, detail="Meal not found")

        review.meal_id = meal_id
    elif meal_name is not None:
        # If meal name changed, we might need to switch to another meal or create one
        # Assuming we stay in the same place
        current_meal = await db.get(Meal, review.meal_id)
        if current_meal is None:
            logger.error(
                f"Current meal with id {review.meal_id} not found for review \
                {review_id}. This should not happen on a valid review. \
                Is the meal deleted?"
            )
            raise HTTPException(
                status_code=500, detail="Internal server error: meal does not exist"
            )

        if current_meal.name != meal_name:
            place_id = current_meal.place_id
            result = await db.execute(
                select(Meal).where(Meal.place_id == place_id, Meal.name == meal_name)
            )
            meal = result.scalars().first()
            if not meal:
                meal = Meal(name=meal_name, place_id=place_id, test_id=test_id)
                db.add(meal)
                await db.flush()
            review.meal_id = meal.id

    if rating is not None:
        review.rating = rating
    if text is not None:
        review.text = text
    if waiting_time_minutes is not None:
        review.waiting_time_minutes = waiting_time_minutes
    if price is not None:
        review.price = round(price, 2)
        # Update meal price if different
        meal = await db.get(Meal, review.meal_id)
        if meal and meal.price != review.price:
            meal.price = review.price
            db.add(meal)
    if test_id is not None:
        review.test_id = test_id
    if is_vegan is not None:
        review.is_vegan = TriState(is_vegan.value)
    if is_halal is not None:
        review.is_halal = TriState(is_halal.value)
    if is_vegetarian is not None:
        review.is_vegetarian = TriState(is_vegetarian.value)
    if is_spicy is not None:
        review.is_spicy = TriState(is_spicy.value)
    if is_gluten_free is not None:
        review.is_gluten_free = TriState(is_gluten_free.value)
    if is_dairy_free is not None:
        review.is_dairy_free = TriState(is_dairy_free.value)
    if is_nut_free is not None:
        review.is_nut_free = TriState(is_nut_free.value)

    # Handle image removals
    images_to_delete = []
    if remove_image_ids:
        try:
            ids_to_remove = [
                uuid.UUID(id_str.strip()) for id_str in remove_image_ids.split(",")
            ]
            for img_id in ids_to_remove:
                img = await db.get(MealReviewImage, img_id)
                if img and img.meal_review_id == review_id:
                    images_to_delete.append(img.image_path)
                    await db.delete(img)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail="Invalid image ID format"
            ) from e

    # Handle image additions
    current_image_count = len(review.images) - len(images_to_delete)
    if add_images:
        if current_image_count + len(add_images) > 5:
            raise HTTPException(
                status_code=400, detail="Review cannot have more than 5 images total."
            )

        for idx, img in enumerate(add_images):
            if img.size and img.size > 5 * 1024 * 1024:
                raise HTTPException(
                    status_code=413, detail=f"Image {img.filename} exceeds 5MB limit."
                )

            try:
                img_bytes = await img.read()
                processed_image_bytes, _metadata = await run_in_threadpool(
                    image_processing.process_image_to_jpeg_flexible, img_bytes
                )
            except image_processing.InvalidImageError as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid image file: {img.filename}"
                ) from e
            except image_processing.ImageTooLargeError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Image {img.filename} resolution too large.",
                ) from e
            except image_processing.ImageProcessingError as e:
                logger.error(f"Error processing image {img.filename}: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Error processing image {img.filename}. Please try another.",
                ) from e

            object_name = storage.generate_image_object_name(
                storage.ObjectDescriptor.IMAGE_MEAL
            )
            image_path = storage.upload_image_from_bytes(
                image_bytes=processed_image_bytes, object_name=object_name
            )
            img_obj = MealReviewImage(
                meal_review_id=review.id,
                image_path=image_path,
                sequence_index=current_image_count + idx,
            )
            db.add(img_obj)

    db.add(review)
    await db.commit()

    # Update meal features and user preferences in the recommendation engine
    service = RecommendationService(db)
    background_tasks.add_task(service.update_meal_features, review.meal_id)
    if rating is not None:
        signal = 2.5 if rating > 2 else -2.5
        background_tasks.add_task(
            service.update_user_preferences, current_user.id, signal, review.meal_id
        )

    # Schedule S3 cleanup for deleted images
    for img_path in images_to_delete:
        background_tasks.add_task(storage.delete_image, img_path)

    return MessageResponse(message="Review updated successfully")


@router.get("/reviews", response_model=Page[ReviewResponse])
async def get_reviews(
    place_id: Optional[uuid.UUID] = Query(None),
    meal_id: Optional[uuid.UUID] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    min_rating: Optional[int] = Query(None, ge=1, le=5),
    max_rating: Optional[int] = Query(None, ge=1, le=5),
    has_text: Optional[bool] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_waiting_time: Optional[int] = Query(None, ge=0),
    max_waiting_time: Optional[int] = Query(None, ge=0),
    meal_name: Optional[str] = Query(None),
    cuisine: Optional[str] = Query(None),
    text: Optional[str] = Query(
        None, description="Search in review text (partial match)"
    ),
    created_after: Optional[datetime] = Query(None),
    created_before: Optional[datetime] = Query(None),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None, alias="long"),
    radius_m: Optional[float] = Query(None, ge=0),
    is_vegan: Optional[str] = Query(None),
    is_halal: Optional[str] = Query(None),
    is_vegetarian: Optional[str] = Query(None),
    is_spicy: Optional[str] = Query(None),
    is_gluten_free: Optional[str] = Query(None),
    is_dairy_free: Optional[str] = Query(None),
    is_nut_free: Optional[str] = Query(None),
    sort_by: Literal[
        "created_at", "rating", "price", "meal_name", "waiting_time_minutes", "distance"
    ] = Query("created_at"),
    sort_order: Literal["asc", "desc"] = Query("desc"),
    pagination: PaginationInput = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> Page[ReviewResponse]:
    """Get paginated list of reviews with filtering and sorting."""

    # Validate location parameters
    if (lat is not None or lng is not None or radius_m is not None) and not (
        lat is not None and lng is not None and radius_m is not None
    ):
        raise HTTPException(
            status_code=400,
            detail="lat, long, and radius_m must all be provided together for location filtering.",
        )

    # Validate tag values
    valid_tags = {TriState.yes.value, TriState.no.value, TriState.unspecified.value}
    tag_filters = {
        "is_vegan": is_vegan,
        "is_halal": is_halal,
        "is_vegetarian": is_vegetarian,
        "is_spicy": is_spicy,
        "is_gluten_free": is_gluten_free,
        "is_dairy_free": is_dairy_free,
        "is_nut_free": is_nut_free,
    }
    for tag_name, tag_value in tag_filters.items():
        if tag_value is not None and tag_value not in valid_tags:
            raise HTTPException(
                status_code=400, detail=f"Invalid value for {tag_name}: {tag_value}"
            )

    # Build query
    query = select(MealReview).options(
        selectinload(MealReview.images),
        selectinload(MealReview.meal)
        .selectinload(Meal.place)
        .selectinload(Place.images),
        selectinload(MealReview.user),
    )

    # Apply filters
    if place_id:
        query = query.join(MealReview.meal).where(Meal.place_id == place_id)
    if meal_id:
        query = query.where(MealReview.meal_id == meal_id)
    if user_id:
        query = query.where(MealReview.user_id == user_id)
    if min_rating:
        query = query.where(MealReview.rating >= min_rating)
    if max_rating:
        query = query.where(MealReview.rating <= max_rating)
    if has_text is not None:
        if has_text:
            query = query.where(MealReview.text.isnot(None))
        else:
            query = query.where(MealReview.text.is_(None))
    if min_price is not None:
        query = query.where(MealReview.price >= min_price)
    if max_price is not None:
        query = query.where(MealReview.price <= max_price)
    if min_waiting_time is not None:
        query = query.where(MealReview.waiting_time_minutes >= min_waiting_time)
    if max_waiting_time is not None:
        query = query.where(MealReview.waiting_time_minutes <= max_waiting_time)
    if meal_name:
        query = query.join(MealReview.meal).where(Meal.name.ilike(f"%{meal_name}%"))
    if cuisine:
        query = (
            query.join(MealReview.meal)
            .join(Meal.place)
            .where(cast(Place.cuisine, String).ilike(f"%{cuisine}%"))
        )
    if text:
        query = query.where(MealReview.text.ilike(f"%{text}%"))
    if created_after:
        query = query.where(MealReview.created_at >= created_after)
    if created_before:
        query = query.where(MealReview.created_at <= created_before)

    # Apply tag filters
    for tag_name, tag_value in tag_filters.items():
        if tag_value is not None:
            query = query.where(getattr(MealReview, tag_name) == TriState(tag_value))

    # Execute query
    # TODO only select all reviews if location is provided
    result = await db.execute(query)
    all_reviews = result.scalars().all()

    # Filter by location if provided
    reviews_with_data = []
    for review in all_reviews:
        distance = None
        if lat is not None and lng is not None:
            distance = calculate_distance(
                lat, lng, review.meal.place.lat, review.meal.place.lng
            )
            if radius_m is not None and distance > radius_m:
                continue

        reviews_with_data.append({"review": review, "distance": distance})

    # Sort
    if sort_by == "distance" and (lat is None or lng is None):
        raise HTTPException(
            status_code=400,
            detail="Cannot sort by distance without providing location (lat, long).",
        )

    sort_key_map = {
        "created_at": lambda x: x["review"].created_at,
        "rating": lambda x: x["review"].rating,
        "price": lambda x: x["review"].price
        if x["review"].price is not None
        else float("inf"),
        "meal_name": lambda x: x["review"].meal.name.lower(),
        "waiting_time_minutes": lambda x: x["review"].waiting_time_minutes
        if x["review"].waiting_time_minutes is not None
        else float("inf"),
        "distance": lambda x: x["distance"]
        if x["distance"] is not None
        else float("inf"),
    }

    reviews_with_data.sort(key=sort_key_map[sort_by], reverse=(sort_order == "desc"))

    # Paginate
    page_data = await paginate_list(
        items=reviews_with_data,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    # Build response
    results = []
    for item in page_data.results:
        review = item["review"]
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
                distance_meters=item["distance"],
            )
        )

    return Page[ReviewResponse](
        results=results,
        total_items=page_data.total_items,
        start_index=page_data.start_index,
        end_index=page_data.end_index,
        total_pages=page_data.total_pages,
        current_page=page_data.current_page,
        current_page_size=page_data.current_page_size,
    )


@router.get("/reviews/{review_id}", response_model=ReviewDetailedResponse)
async def get_review(
    review_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> ReviewDetailedResponse:
    """Get detailed information about a single review."""

    result = await db.execute(
        select(MealReview)
        .where(MealReview.id == review_id)
        .options(
            selectinload(MealReview.images),
            selectinload(MealReview.meal).selectinload(Place.images),
            selectinload(MealReview.user),
        )
    )
    review = result.scalars().first()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Build image responses
    backend_images: List[BackendImageResponse] = []
    for img in sorted(review.images, key=lambda i: i.sequence_index):
        backend_images.append(
            BackendImageResponse(
                id=img.id,
                image_url=storage.generate_presigned_url(img.image_path),
                sequence_index=img.sequence_index,
            )
        )

    # Get first place image
    first_place_image = None
    if review.meal.place.images:
        sorted_place_images = sorted(
            review.meal.place.images, key=lambda i: i.sequence_index
        )
        first_place_image = BackendImageResponse(
            id=sorted_place_images[0].id,
            image_url=storage.generate_presigned_url(sorted_place_images[0].image_path),
            sequence_index=sorted_place_images[0].sequence_index,
        )

    return ReviewDetailedResponse(
        id=review.id,
        meal_id=review.meal.id,
        meal_name=review.meal.name,
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
        image_count=len(backend_images),
        first_image=backend_images[0] if backend_images else None,
        place=PlaceBasicInfo(
            id=review.meal.place.id,
            name=review.meal.place.name,
            address=review.meal.place.address,
            latitude=review.meal.place.lat,
            longitude=review.meal.place.lng,
            first_image=first_place_image,
        ),
        user=UserBasicInfo(
            id=review.user.id,
            first_name=review.user.first_name,
            last_name=review.user.last_name,
            image_url=storage.generate_presigned_url_or_none(review.user.image_path),
        ),
        created_at=review.created_at.isoformat(),
        updated_at=review.updated_at.isoformat(),
        images=backend_images,
    )


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Delete a review. Only the review creator can delete."""

    result = await db.execute(
        select(MealReview)
        .where(MealReview.id == review_id)
        .options(selectinload(MealReview.images))
    )
    review = result.scalars().first()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this review"
        )

    # Collect image paths for deletion
    image_paths = [img.image_path for img in review.images]
    meal_id = review.meal_id

    # Delete review (CASCADE will handle images)
    await db.delete(review)
    await db.commit()

    # Update meal features
    service = RecommendationService(db)
    background_tasks.add_task(service.update_meal_features, meal_id)

    # Schedule S3 cleanup
    for img_path in image_paths:
        background_tasks.add_task(storage.delete_image, img_path)

    logger.info(f"Review {review_id} deleted by user {current_user.id}")
