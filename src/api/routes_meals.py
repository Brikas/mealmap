import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, List, Literal, Optional

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
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.common_schemas import (
    BackendImageResponse,
    MessageResponse,
    ObjectCreationResponse,
)
from src.api.dependencies import get_current_user
from src.db.models import Meal, MealImage, MealReview, Place, User
from src.db.session import get_async_db_session
from src.services import image_processing, storage
from src.services.recommendation import (
    RecommendationService,
    update_meal_features_background,
)
from src.utils.misc_utils import calculate_distance, calculate_majority_tag
from src.utils.pagination import Page, PaginationInput, paginate_list

router = APIRouter()


class MealTags(BaseModel):
    is_vegan: Optional[str] = None
    is_halal: Optional[str] = None
    is_vegetarian: Optional[str] = None
    is_spicy: Optional[str] = None
    is_gluten_free: Optional[str] = None
    is_dairy_free: Optional[str] = None
    is_nut_free: Optional[str] = None


class MealResponse(BaseModel):
    id: uuid.UUID
    name: str
    price: Optional[float] = None
    place_id: uuid.UUID
    place_name: str
    avg_rating: Optional[float] = None
    review_count: int
    avg_waiting_time: Optional[float] = None
    avg_price: Optional[float] = None
    first_image: Optional[BackendImageResponse] = None
    distance_meters: Optional[float] = None
    is_new: bool
    is_popular: bool

    tags: MealTags

    test_id: Optional[str] = None


class MealDetailedResponse(MealResponse):
    images: List[BackendImageResponse] = []
    description: Optional[str] = None
    created_at: str
    updated_at: str


@router.post("/meals", response_model=ObjectCreationResponse)
async def create_meal(
    name: Annotated[str, Form(min_length=1)],
    place_id: Annotated[uuid.UUID, Form()],
    background_tasks: BackgroundTasks,
    price: Annotated[Optional[float], Form(ge=0)] = None,
    test_id: Annotated[Optional[str], Form()] = None,
    images: Optional[List[UploadFile]] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> ObjectCreationResponse:
    """
    Create a new meal associated with a place explicitly.

    A meal does not need to be neccessarily created this way, as meals can also be
    created implicitly when a user submits a review for a meal that does not yet exist,
    by providing the meal name and place id in the review submission.
    """
    if images is None:
        images = []

    # Validate images count
    if len(images) > 5:
        raise HTTPException(
            status_code=400,
            detail="You can upload a maximum of 5 images.",
        )

    # Check if place exists
    place = await db.get(Place, place_id)
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")

    # Check if meal already exists
    existing = await db.execute(
        select(Meal).where(Meal.place_id == place_id, Meal.name == name)
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=400, detail="Meal with this name already exists at this place."
        )

    new_meal = Meal(name=name, place_id=place_id, price=price, test_id=test_id)
    db.add(new_meal)
    await db.flush()

    # Upload images
    for idx, img in enumerate(images):
        try:
            contents = await img.read()
            processed_bytes, metadata = image_processing.process_image_to_jpeg_flexible(
                contents, max_size=1024, max_aspect_ratio=1.5
            )

            object_name = storage.generate_image_object_name(
                storage.ObjectDescriptor.IMAGE_MEAL
            )

            storage.upload_image_from_bytes(processed_bytes, object_name)

            meal_image = MealImage(
                meal_id=new_meal.id,
                image_path=object_name,
                sequence_index=idx,
            )
            db.add(meal_image)
        except Exception as e:
            # In a real app, we might want to handle this better (e.g. rollback or partial success)
            # For now, we'll skip the failed image
            logger.error(
                f"Failed to process/upload image for new meal {new_meal.id}. {e}"
            )

    await db.commit()
    await db.refresh(new_meal)

    # Trigger background update of meal features
    background_tasks.add_task(update_meal_features_background, new_meal.id)

    return ObjectCreationResponse(id=new_meal.id)


@router.put("/meals/{meal_id}", response_model=MessageResponse)
async def update_meal(
    meal_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    name: Annotated[Optional[str], Form(min_length=1)] = None,
    price: Annotated[Optional[float], Form(ge=0)] = None,
    test_id: Annotated[Optional[str], Form()] = None,
    add_images: Optional[List[UploadFile]] = None,
    remove_image_ids: Annotated[
        Optional[str], Form(description="Comma-separated list of image IDs to remove")
    ] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> MessageResponse:
    if add_images is None:
        add_images = []

    query = select(Meal).where(Meal.id == meal_id).options(selectinload(Meal.images))
    result = await db.execute(query)
    meal = result.scalars().first()

    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    if name is not None:
        meal.name = name
    if price is not None:
        meal.price = price
    if test_id is not None:
        meal.test_id = test_id

    # Handle image removals
    images_to_delete = []
    if remove_image_ids:
        ids_to_remove = []
        for id_str in remove_image_ids.split(","):
            try:
                ids_to_remove.append(uuid.UUID(id_str.strip()))
            except ValueError:
                logger.warning(f"Invalid image ID format in update_meal: {id_str}")

        # Find images to remove
        to_remove = [img for img in meal.images if img.id in ids_to_remove]

        for img in to_remove:
            images_to_delete.append(img.image_path)
            meal.images.remove(img)
            # We don't strictly need db.delete(img) if we remove from relationship and cascade is set,
            # but explicit delete is safer if cascade isn't perfect.
            # With cascade="all, delete-orphan", removing from list is enough.

    # Handle image additions
    current_image_count = len(meal.images)
    if add_images:
        if current_image_count + len(add_images) > 5:
            raise HTTPException(
                status_code=400,
                detail=f"You can only have up to 5 images. You currently have \
                    {current_image_count} and are trying to add {len(add_images)}.",
            )

        # Determine starting sequence index
        next_idx = 0
        if meal.images:
            next_idx = max(img.sequence_index for img in meal.images) + 1

        for idx, img in enumerate(add_images):
            try:
                contents = await img.read()
                processed_bytes, metadata = (
                    image_processing.process_image_to_jpeg_flexible(
                        contents, max_size=1024, max_aspect_ratio=1.5
                    )
                )

                object_name = storage.generate_image_object_name(
                    storage.ObjectDescriptor.IMAGE_MEAL
                )

                storage.upload_image_from_bytes(processed_bytes, object_name)

                meal_image = MealImage(
                    meal_id=meal.id,
                    image_path=object_name,
                    sequence_index=next_idx + idx,
                )
                meal.images.append(meal_image)
            except Exception:
                pass

    db.add(meal)
    await db.commit()

    # Trigger background update of meal features
    background_tasks.add_task(update_meal_features_background, meal_id)

    # Schedule S3 cleanup for deleted images
    for img_path in images_to_delete:
        background_tasks.add_task(storage.delete_image, img_path)
        logger.info(f"Scheduled deletion of image from S3: {img_path}")

    return MessageResponse(message="Meal updated successfully")


@router.delete("/meals/{meal_id}", status_code=status.HTTP_200_OK)
async def delete_meal(
    meal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> MessageResponse:
    meal = await db.get(Meal, meal_id)
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    return MessageResponse(message="Delete request submitted")


@router.get("/meals", response_model=Page[MealResponse])
async def get_meals(
    place_id: Optional[uuid.UUID] = Query(None),
    name: Optional[str] = Query(None),
    cuisine: Optional[str] = Query(None),
    min_rating: Optional[float] = Query(None, ge=1, le=5),
    max_price: Optional[float] = Query(None, ge=0),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None, alias="long"),
    radius_m: Optional[float] = Query(None),
    sort_by: Literal[
        "rating", "price", "waiting_time", "distance", "review_count"
    ] = Query("rating"),
    sort_order: Literal["asc", "desc"] = Query("desc"),
    pagination: PaginationInput = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> Page[MealResponse]:
    query = select(Meal).options(
        selectinload(Meal.place),
        selectinload(Meal.meal_reviews).selectinload(MealReview.images),
        selectinload(Meal.images),
    )

    if place_id:
        query = query.where(Meal.place_id == place_id)
    if name:
        query = query.where(Meal.name.ilike(f"%{name}%"))

    if cuisine:
        query = query.join(Meal.place).where(
            cast(Place.cuisine, String).ilike(f"%{cuisine}%")
        )

    result = await db.execute(query)
    meals = result.scalars().all()

    processed_meals = []
    now = datetime.now(timezone.utc)
    for meal in meals:
        reviews = meal.meal_reviews

        review_count = len(reviews)
        avg_rating = (
            sum(r.rating for r in reviews) / review_count if review_count > 0 else None
        )

        waiting_times = [
            r.waiting_time_minutes
            for r in reviews
            if r.waiting_time_minutes is not None
        ]
        avg_waiting_time = (
            sum(waiting_times) / len(waiting_times) if waiting_times else None
        )

        prices = [r.price for r in reviews if r.price is not None]
        avg_price = sum(prices) / len(prices) if prices else None

        is_vegan = calculate_majority_tag(reviews, "is_vegan")
        is_halal = calculate_majority_tag(reviews, "is_halal")
        is_vegetarian = calculate_majority_tag(reviews, "is_vegetarian")
        is_spicy = calculate_majority_tag(reviews, "is_spicy")
        is_gluten_free = calculate_majority_tag(reviews, "is_gluten_free")
        is_dairy_free = calculate_majority_tag(reviews, "is_dairy_free")
        is_nut_free = calculate_majority_tag(reviews, "is_nut_free")

        is_new = False
        if meal.created_at:
            created_at = meal.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            is_new = (now - created_at) < timedelta(days=14)

        first_image = None

        # Check meal images first
        if meal.images:
            sorted_meal_images = sorted(meal.images, key=lambda x: x.sequence_index)
            if sorted_meal_images:
                first_img_obj = sorted_meal_images[0]
                url = storage.generate_presigned_url_or_none(first_img_obj.image_path)
                if url:
                    first_image = BackendImageResponse(
                        id=first_img_obj.id,
                        image_url=url,
                        sequence_index=first_img_obj.sequence_index,
                    )

        # If no meal image, check reviews
        if not first_image:
            sorted_reviews = sorted(reviews, key=lambda r: r.created_at, reverse=True)
            for r in sorted_reviews:
                if r.images:
                    # Sort images by sequence index if available, or just take first
                    # Assuming r.images is a list of MealReviewImage objects
                    # They have sequence_index
                    sorted_imgs = sorted(r.images, key=lambda x: x.sequence_index)
                    if sorted_imgs:
                        img_obj = sorted_imgs[0]
                        url = storage.generate_presigned_url_or_none(img_obj.image_path)
                        if url:
                            first_image = BackendImageResponse(
                                id=img_obj.id,
                                image_url=url,
                                sequence_index=img_obj.sequence_index,
                            )
                            break

        distance = None
        if lat is not None and lng is not None:
            distance = calculate_distance(lat, lng, meal.place.lat, meal.place.lng)
            if radius_m is not None and distance > radius_m:
                continue

        if min_rating is not None:
            if avg_rating is None or avg_rating < min_rating:
                continue

        if max_price is not None:
            price_to_check = avg_price if avg_price is not None else meal.price
            if price_to_check is None or price_to_check > max_price:
                continue

        processed_meals.append(
            {
                "meal": meal,
                "avg_rating": avg_rating,
                "review_count": review_count,
                "avg_waiting_time": avg_waiting_time,
                "avg_price": avg_price,
                "first_image": first_image,
                "distance": distance,
                "tags": {
                    "is_vegan": is_vegan,
                    "is_halal": is_halal,
                    "is_vegetarian": is_vegetarian,
                    "is_spicy": is_spicy,
                    "is_gluten_free": is_gluten_free,
                    "is_dairy_free": is_dairy_free,
                    "is_nut_free": is_nut_free,
                },
                "is_new": is_new,
                "is_popular": False,
            }
        )

    def get_sort_key(item):
        key = sort_by
        val = item.get(key)
        if key == "rating":
            val = item["avg_rating"]
        elif key == "price":
            val = item["avg_price"]
        elif key == "waiting_time":
            val = item["avg_waiting_time"]
        elif key == "distance":
            val = item["distance"]
        elif key == "review_count":
            val = item["review_count"]

        if val is None:
            return float("-inf") if sort_order == "desc" else float("inf")
        return val

    processed_meals.sort(key=get_sort_key, reverse=(sort_order == "desc"))

    page_data = await paginate_list(
        items=processed_meals,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    results = []
    for item in page_data.results:
        m = item["meal"]
        tags = item["tags"]
        results.append(
            MealResponse(
                id=m.id,
                name=m.name,
                price=m.price,
                place_id=m.place_id,
                place_name=m.place.name,
                avg_rating=item["avg_rating"],
                review_count=item["review_count"],
                avg_waiting_time=item["avg_waiting_time"],
                avg_price=item["avg_price"],
                first_image=item["first_image"],
                distance_meters=item["distance"],
                is_new=item["is_new"],
                is_popular=item["is_popular"],
                tags=MealTags(**tags),
                test_id=m.test_id,
            )
        )

    return Page[MealResponse](
        results=results,
        total_items=page_data.total_items,
        start_index=page_data.start_index,
        end_index=page_data.end_index,
        total_pages=page_data.total_pages,
        current_page=page_data.current_page,
        current_page_size=page_data.current_page_size,
    )


@router.get("/meals/{meal_id}", response_model=MealDetailedResponse)
async def get_meal_details(
    meal_id: uuid.UUID,
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None, alias="long"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> MealDetailedResponse:
    query = (
        select(Meal)
        .where(Meal.id == meal_id)
        .options(
            selectinload(Meal.place),
            selectinload(Meal.meal_reviews).selectinload(MealReview.images),
            selectinload(Meal.images),
        )
    )
    result = await db.execute(query)
    meal = result.scalars().first()

    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    reviews = meal.meal_reviews

    review_count = len(reviews)
    avg_rating = (
        sum(r.rating for r in reviews) / review_count if review_count > 0 else None
    )

    waiting_times = [
        r.waiting_time_minutes for r in reviews if r.waiting_time_minutes is not None
    ]
    avg_waiting_time = (
        sum(waiting_times) / len(waiting_times) if waiting_times else None
    )

    prices = [r.price for r in reviews if r.price is not None]
    avg_price = sum(prices) / len(prices) if prices else None

    is_vegan = calculate_majority_tag(reviews, "is_vegan")
    is_halal = calculate_majority_tag(reviews, "is_halal")
    is_vegetarian = calculate_majority_tag(reviews, "is_vegetarian")
    is_spicy = calculate_majority_tag(reviews, "is_spicy")
    is_gluten_free = calculate_majority_tag(reviews, "is_gluten_free")
    is_dairy_free = calculate_majority_tag(reviews, "is_dairy_free")
    is_nut_free = calculate_majority_tag(reviews, "is_nut_free")

    all_images = []

    # Add meal images first
    if meal.images:
        for img in sorted(meal.images, key=lambda x: x.sequence_index):
            url = storage.generate_presigned_url_or_none(img.image_path)
            if url:
                all_images.append(
                    BackendImageResponse(
                        id=img.id,
                        image_url=url,
                        sequence_index=img.sequence_index,
                    )
                )

    sorted_reviews = sorted(reviews, key=lambda r: r.created_at, reverse=True)
    for r in sorted_reviews:
        if r.images:
            sorted_imgs = sorted(r.images, key=lambda x: x.sequence_index)
            for img in sorted_imgs:
                url = storage.generate_presigned_url_or_none(img.image_path)
                if url:
                    all_images.append(
                        BackendImageResponse(
                            id=img.id,
                            image_url=url,
                            sequence_index=img.sequence_index,
                        )
                    )
                if len(all_images) >= 20:
                    break
        if len(all_images) >= 10:
            break

    first_image = all_images[0] if all_images else None

    distance = None
    if lat is not None and lng is not None:
        distance = calculate_distance(lat, lng, meal.place.lat, meal.place.lng)

    now = datetime.now(timezone.utc)
    created_at = meal.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    is_new = (now - created_at) < timedelta(days=14)

    return MealDetailedResponse(
        id=meal.id,
        name=meal.name,
        price=meal.price,
        place_id=meal.place_id,
        place_name=meal.place.name,
        avg_rating=avg_rating,
        review_count=review_count,
        avg_waiting_time=avg_waiting_time,
        avg_price=avg_price,
        first_image=first_image,
        distance_meters=distance,
        is_new=is_new,
        is_popular=False,
        tags=MealTags(
            is_vegan=is_vegan,
            is_halal=is_halal,
            is_vegetarian=is_vegetarian,
            is_spicy=is_spicy,
            is_gluten_free=is_gluten_free,
            is_dairy_free=is_dairy_free,
            is_nut_free=is_nut_free,
        ),
        test_id=meal.test_id,
        images=all_images,
        created_at=meal.created_at.isoformat(),
        updated_at=meal.updated_at.isoformat(),
    )
