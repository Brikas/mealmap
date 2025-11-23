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
from src.db.models import Meal, Place, PlaceImage, User
from src.db.session import get_async_db_session
from src.services import image_processing, storage
from src.utils.misc_utils import calculate_distance
from src.utils.pagination import Page, PaginationInput, paginate_list

router = APIRouter()


class PlaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    image_count: int
    first_image: Optional[BackendImageResponse] = None
    distance_meters: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    average_rating: Optional[float] = None
    review_count: Optional[int] = None
    cuisine: Optional[str] = None
    test_id: Optional[str] = None


class PlaceResponseDetailed(PlaceResponse):
    address: Optional[str] = None
    created_at: str = Field(
        ..., description="ISO formatted. YYYY-MM-DD HH:MM:SS.mmmmmm"
    )
    updated_at: str = Field(
        ..., description="ISO formatted. YYYY-MM-DD HH:MM:SS.mmmmmm"
    )
    images: List[BackendImageResponse] = []


@router.post("/places", response_model=ObjectCreationResponse)
async def create_place(
    name: Annotated[str, Form()],
    latitude: Annotated[float, Form()],
    longitude: Annotated[float, Form()],
    address: Annotated[Optional[str], Form()] = None,
    cuisine: Annotated[Optional[str], Form()] = None,
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
    places_with_distance = []
    for place in all_places:
        distance = calculate_distance(lat, lng, place.lat, place.lng)
        if distance <= radius_meters:
            # Calculate average rating and review count
            reviews = [r for m in place.meals for r in m.meal_reviews]
            avg_rating = (
                sum(r.rating for r in reviews) / len(reviews) if reviews else None
            )
            review_count = len(reviews)

            places_with_distance.append(
                {
                    "place": place,
                    "distance": distance,
                    "avg_rating": avg_rating,
                    "review_count": review_count,
                }
            )

    # Sort
    sort_key_map = {
        "distance": "distance",
        "average_rating": "avg_rating",
        "review_count": "review_count",
    }
    sort_key = sort_key_map[sort_by]

    places_with_distance.sort(
        key=lambda x: x[sort_key] if x[sort_key] is not None else float("inf"),
        reverse=(sort_order == "desc"),
    )

    # Paginate the sorted list first (without building full responses yet)
    page_data = await paginate_list(
        items=places_with_distance,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    # Build response list only for paginated items
    results = []
    for item in page_data.results:
        place = item["place"]
        first_image = None
        image_count = 0
        if place.images:
            image_count = len(place.images)
            sorted_images = sorted(place.images, key=lambda i: i.sequence_index)
            first_image = BackendImageResponse(
                id=sorted_images[0].id,
                image_url=storage.generate_presigned_url(sorted_images[0].image_path),
                sequence_index=sorted_images[0].sequence_index,
            )

        results.append(
            PlaceResponse(
                id=place.id,
                name=place.name,
                image_count=image_count,
                first_image=first_image,
                distance_meters=item["distance"],
                latitude=place.lat,
                longitude=place.lng,
                average_rating=item["avg_rating"],
                review_count=item["review_count"],
                test_id=place.test_id,
            )
        )

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

    # Build BackendImage objects
    backend_images: List[BackendImageResponse] = []
    for img in sorted(place.images, key=lambda i: i.sequence_index):
        backend_images.append(
            BackendImageResponse(
                id=img.id,
                image_url=storage.generate_presigned_url(img.image_path),
                sequence_index=img.sequence_index,
            )
        )

    # Calculate average rating and review count
    reviews = [r for m in place.meals for r in m.meal_reviews]
    avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else None
    review_count = len(reviews)

    # Calculate distance if user coordinates provided
    distance_meters = None
    if lat is not None and lng is not None:
        distance_meters = calculate_distance(lat, lng, place.lat, place.lng)
    elif lat is not None or lng is not None:
        raise HTTPException(
            status_code=400,
            detail="Both lat and long must be provided for distance calculation.",
        )

    return PlaceResponseDetailed(
        id=place.id,
        name=place.name,
        image_count=len(backend_images),
        first_image=backend_images[0] if backend_images else None,
        distance_meters=distance_meters,
        latitude=place.lat,
        longitude=place.lng,
        average_rating=avg_rating,
        review_count=review_count,
        address=place.address,
        created_at=place.created_at.isoformat(),
        updated_at=place.updated_at.isoformat(),
        images=backend_images,
        test_id=place.test_id,
    )


@router.put("/places/{place_id}", response_model=MessageResponse)
async def update_place(
    place_id: uuid.UUID,
    name: Annotated[Optional[str], Form()] = None,
    address: Annotated[Optional[str], Form()] = None,
    cuisine: Annotated[Optional[str], Form()] = None,
    add_images: Optional[List[UploadFile]] = None,
    test_id: Annotated[Optional[str], Form()] = None,
    remove_image_ids: Annotated[Optional[str], Form()] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> MessageResponse:
    """Update a place with approval logic.

    - Any user can instantly add/append new attributes (address, images)
    - Admin verification needed for editing/deleting existing attributes
    """
    if add_images is None:
        add_images = []

    result = await db.execute(
        select(Place).where(Place.id == place_id).options(selectinload(Place.images))
    )
    place = result.scalars().first()

    if not place:
        raise HTTPException(status_code=404, detail="Place not found")

    approval_needed = []

    # Handle name update (requires approval if editing existing)
    if name is not None and name != place.name:
        approval_needed.append("name edit")
        # Don't apply the change yet - would require admin approval system

    # Handle address update (can add if empty, edit requires approval)
    if address is not None:
        if not place.address or place.address == "":
            place.address = address
        elif address != place.address:
            approval_needed.append("address edit")
            # Don't apply the change yet

    # Handle cuisine update
    if cuisine is not None:
        if not place.cuisine:
            place.cuisine = cuisine
        elif place.cuisine != cuisine:
            approval_needed.append(f"cuisine: {cuisine}")

    if test_id is not None:
        # Directly allow test_id updates
        place.test_id = test_id

    # Handle image additions (allowed instantly)
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
                )

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

    # Handle image deletions (requires approval)
    if remove_image_ids:
        try:
            ids_to_remove = [
                uuid.UUID(id_str) for id_str in remove_image_ids.split(",")
            ]
            if ids_to_remove:
                approval_needed.append("image deletion")
                # Don't apply deletions yet
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid image ID format")

    db.add(place)
    await db.commit()

    message = "Place updated successfully."
    if approval_needed:
        message += (
            f" Admin approval needed for: {', '.join(approval_needed)} (unimplemented)"
        )

    return MessageResponse(message=message)
