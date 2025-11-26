import uuid
from typing import List, Optional

from pydantic import BaseModel, Field

from src.api.common_schemas import BackendImageResponse
from src.db.models import CuisineType


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
    match_score: Optional[float] = None

    tags: MealTags

    test_id: Optional[str] = None


class MealDetailedResponse(MealResponse):
    images: List[BackendImageResponse] = []
    description: Optional[str] = None
    created_at: str
    updated_at: str


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
    cuisine: Optional[CuisineType] = Field(
        None,
        description=(
            "Cuisine type of the place. Possible values: italian, french, spanish, "
            "greek, british, chinese, japanese, korean, thai, vietnamese, indian, "
            "filipino, american, mexican, mediterranean, african, fusion, cafe, "
            "bakery, barbecue, seafood, vegetarian_vegan, other, unspecified"
        ),
    )
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
