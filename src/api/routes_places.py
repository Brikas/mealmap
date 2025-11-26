import io
import math
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
from loguru import logger
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import String, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import jwt_utils
from src.api.common_schemas import (
    BackendImageResponse,
    MessageResponse,
    ObjectCreationResponse,
)
from src.api.dependencies import get_current_user
from src.api.response_schemas import PlaceResponse, PlaceResponseDetailed
from src.db.models import CuisineType, Meal, Place, PlaceImage, User
from src.db.session import get_async_db_session
from src.services import image_processing, storage
from src.services.recommendation import (
    RecommendationService,
    update_place_meals_features_background,
)
from src.services.response_builder import build_place_response
from src.utils.pagination import Page, PaginationInput, paginate_list

router = APIRouter()


@router.post("/places", response_model=ObjectCreationResponse)
async def create_place(
    name: Annotated[str, Form()],
    latitude: Annotated[float, Form()],
    longitude: Annotated[float, Form()],
    address: Annotated[Optional[str], Form()] = None,
    cuisine: Annotated[
        Optional[CuisineType],
        Form(
            description=(
                "Cuisine type of the place. Possible values: italian, french, spanish, "
                "greek, british, chinese, japanese, korean, thai, vietnamese, indian, "
                "filipino, american, mexican, mediterranean, african, fusion, cafe, "
                "bakery, barbecue, seafood, vegetarian_vegan, other, unspecified"
            )
        ),
    ] = None,
    test_id: Annotated[Optional[str], Form()] = None,
    images: Optional[List[UploadFile]] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> ObjectCreationResponse:
    """Create a new place with optional images."""
    if images is None:
        images = []

    # Validate images count and size
    if len(images) > 5:
        raise HTTPException(status_code=400, detail="Cannot upload more than 5 images.")

    for img in images:
        if img.size and img.size > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(
                status_code=413, detail=f"Image {img.filename} exceeds 5MB limit."
            )

    # Check if place with same lat/long already exists
    result = await db.execute(
        select(Place).where(Place.lat == latitude, Place.lng == longitude)
    )
    existing_place = result.scalars().first()
    if existing_place:
        raise HTTPException(
            status_code=400, detail="A place with these coordinates already exists."
        )

    # Create place
    new_place = Place(
        name=name,
        address=address or "",
        lat=latitude,
        lng=longitude,
        cuisine=cuisine,
        test_id=test_id,
    )
    db.add(new_place)
    await db.flush()  # Get new_place.id

    # Upload images
    for idx, img in enumerate(images):
        try:
            img_bytes = await img.read()
            with Image.open(io.BytesIO(img_bytes)) as pil_img:
                width, height = pil_img.size
        except Exception as e:
            logger.error(f"Error processing image {img.filename}: {e}")
            raise HTTPException(
                status_code=400, detail=f"Invalid image file: {img.filename}"
            ) from e

        object_name = storage.generate_image_object_name(
            storage.ObjectDescriptor.IMAGE_PLACE
        )
        object_name = storage.upload_image_from_bytes(
            image_bytes=img_bytes, object_name=object_name
        )
        img_obj = PlaceImage(
            place_id=new_place.id,
            image_path=object_name,
            sequence_index=idx,
        )
        db.add(img_obj)

    await db.commit()
    await db.refresh(new_place)

    return ObjectCreationResponse(id=new_place.id)


@router.get("/places", response_model=Page[PlaceResponse])
async def list_places(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., alias="long", description="Longitude"),
    radius_meters: float = Query(50000, ge=0, description="Search radius in meters"),
    name: Optional[str] = Query(None, description="Filter by name substring"),
    sort_by: Literal["distance", "average_rating", "review_count"] = Query("distance"),
    sort_order: Literal["asc", "desc"] = Query("asc"),
    pagination: PaginationInput = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> Page[PlaceResponse]:
    """List places with filters and sorting."""

    # Build query
    query = select(Place).options(
        selectinload(Place.images),
        selectinload(Place.meals).selectinload(Meal.meal_reviews),
    )

    # Apply name filter
    if name:
        query = query.where(Place.name.ilike(f"%{name}%"))

    # Execute query
    result = await db.execute(query)
    all_places = result.scalars().all()

    # Calculate distances and filter by radius
    processed_places = []
    for place in all_places:
        response = build_place_response(place, lat, lng)

        if (
            response.distance_meters is not None
            and response.distance_meters <= radius_meters
        ):
            processed_places.append(response)

    # Sort
    sort_attr_map = {
        "distance": "distance_meters",
        "average_rating": "average_rating",
        "review_count": "review_count",
    }
    sort_attr = sort_attr_map[sort_by]

    processed_places.sort(
        key=lambda x: getattr(x, sort_attr)
        if getattr(x, sort_attr) is not None
        else float("inf"),
        reverse=(sort_order == "desc"),
    )

    # Paginate the sorted list first (without building full responses yet)
    page_data = await paginate_list(
        items=processed_places,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    results = page_data.results

    # Return page with built response objects
    return Page[PlaceResponse](
        results=results,
        total_items=page_data.total_items,
        start_index=page_data.start_index,
        end_index=page_data.end_index,
        total_pages=page_data.total_pages,
        current_page=page_data.current_page,
        current_page_size=page_data.current_page_size,
    )


@router.get("/places/{place_id}", response_model=PlaceResponseDetailed)
async def get_place_details(
    place_id: uuid.UUID,
    lat: Optional[float] = Query(
        None, description="User latitude for distance calculation"
    ),
    lng: Optional[float] = Query(
        None, alias="long", description="User longitude for distance calculation"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> PlaceResponseDetailed:
    """Get detailed place information."""

    result = await db.execute(
        select(Place)
        .where(Place.id == place_id)
        .options(
            selectinload(Place.images),
            selectinload(Place.meals).selectinload(Meal.meal_reviews),
        )
    )
    place = result.scalars().first()

    if not place:
        raise HTTPException(status_code=404, detail="Place not found")

    # Check lat/long consistency
    if (lat is not None and lng is None) or (lat is None and lng is not None):
        raise HTTPException(
            status_code=400,
            detail="Both lat and long must be provided for distance calculation.",
        )

    base_response = build_place_response(place, lat, lng)

    # Build BackendImage objects (all of them)
    backend_images: List[BackendImageResponse] = []
    for img in sorted(place.images, key=lambda i: i.sequence_index):
        backend_images.append(
            BackendImageResponse(
                id=img.id,
                image_url=storage.generate_presigned_url(img.image_path),
                sequence_index=img.sequence_index,
            )
        )

    return PlaceResponseDetailed(
        **base_response.model_dump(),
        address=place.address,
        created_at=place.created_at.isoformat(),
        updated_at=place.updated_at.isoformat(),
        images=backend_images,
    )


@router.delete("/places/{place_id}", response_model=MessageResponse)
async def delete_place(
    place_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> MessageResponse:
    """Delete a place."""
    place = await db.get(Place, place_id)
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")

    await db.delete(place)
    await db.commit()
    return MessageResponse(message="Place deleted successfully")


@router.patch("/places/{place_id}", response_model=MessageResponse)
async def update_place(
    place_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    name: Annotated[Optional[str], Form()] = None,
    address: Annotated[Optional[str], Form()] = None,
    cuisine: Annotated[
        Optional[CuisineType],
        Form(
            description=(
                "Cuisine type of the place. Possible values: italian, french, spanish, "
                "greek, british, chinese, japanese, korean, thai, vietnamese, indian, "
                "filipino, american, mexican, mediterranean, african, fusion, cafe, "
                "bakery, barbecue, seafood, vegetarian_vegan, other, unspecified"
            )
        ),
    ] = None,
    add_images: Optional[List[UploadFile]] = None,
    test_id: Annotated[Optional[str], Form()] = None,
    remove_image_ids: Annotated[Optional[str], Form()] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> MessageResponse:
    """Update a place."""
    service = RecommendationService(db)
    if add_images is None:
        add_images = []

    result = await db.execute(
        select(Place).where(Place.id == place_id).options(selectinload(Place.images))
    )
    place = result.scalars().first()

    if not place:
        raise HTTPException(status_code=404, detail="Place not found")

    if name is not None:
        place.name = name

    if address is not None:
        place.address = address

    if cuisine is not None:
        if place.cuisine != cuisine:
            place.cuisine = cuisine
            # Trigger background update of meal features for this place
            background_tasks.add_task(update_place_meals_features_background, place_id)

    if test_id is not None:
        place.test_id = test_id

    # Handle image additions
    if add_images:
        if len(add_images) > 5:
            raise HTTPException(
                status_code=400, detail="Cannot upload more than 5 images at once."
            )

        current_image_count = len(place.images)
        if current_image_count + len(add_images) > 5:
            raise HTTPException(
                status_code=400, detail="Place cannot have more than 5 images total."
            )

        for idx, img in enumerate(add_images):
            img_bytes = await img.read()
            try:
                with Image.open(io.BytesIO(img_bytes)) as pil_img:
                    width, height = pil_img.size
            except Exception as e:
                logger.error(f"Error processing image {img.filename}: {e}")
                raise HTTPException(
                    status_code=400, detail=f"Invalid image file: {img.filename}"
                ) from e

            object_name = storage.generate_image_object_name(
                storage.ObjectDescriptor.IMAGE_PLACE
            )
            image_path = storage.upload_image_from_bytes(
                image_bytes=img_bytes, object_name=object_name
            )
            img_obj = PlaceImage(
                place_id=place.id,
                image_path=image_path,
                sequence_index=current_image_count + idx,
            )
            db.add(img_obj)

    # Handle image deletions
    if remove_image_ids:
        try:
            ids_to_remove = [
                uuid.UUID(id_str) for id_str in remove_image_ids.split(",")
            ]
            if ids_to_remove:
                stmt = select(PlaceImage).where(
                    PlaceImage.id.in_(ids_to_remove), PlaceImage.place_id == place_id
                )
                imgs_to_delete = (await db.execute(stmt)).scalars().all()
                for img in imgs_to_delete:
                    await db.delete(img)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail="Invalid image ID format"
            ) from e

    db.add(place)
    await db.commit()

    return MessageResponse(message="Place updated successfully.")
