import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src.api.common_schemas import BackendImageResponse
from src.api.response_schemas import MealResponse, MealTags, PlaceResponse
from src.db.models import Meal, MealReview, Place
from src.services import storage
from src.utils.misc_utils import calculate_distance, calculate_majority_tag


def build_meal_response(
    meal: Meal,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    now: Optional[datetime] = None,
) -> MealResponse:
    if now is None:
        now = datetime.now(timezone.utc)

    # Separate real vs synthetic reviews; only real ones contribute stats
    real_reviews = [r for r in meal.meal_reviews if not r.is_synthetic]
    synthetic_reviews = [r for r in meal.meal_reviews if r.is_synthetic]
    place = meal.place

    review_count = len(real_reviews)
    avg_rating = (
        sum(r.rating for r in real_reviews) / review_count if review_count > 0 else None
    )

    waiting_times = [
        r.waiting_time_minutes
        for r in real_reviews
        if r.waiting_time_minutes is not None
    ]
    avg_waiting_time = (
        sum(waiting_times) / len(waiting_times) if waiting_times else None
    )

    prices = [r.price for r in real_reviews if r.price is not None]
    avg_price = sum(prices) / len(prices) if prices else None

    # Tags can consider both real and synthetic feedback
    review_tag_pool = real_reviews + synthetic_reviews
    is_vegan = calculate_majority_tag(review_tag_pool, "is_vegan")
    is_halal = calculate_majority_tag(review_tag_pool, "is_halal")
    is_vegetarian = calculate_majority_tag(review_tag_pool, "is_vegetarian")
    is_spicy = calculate_majority_tag(review_tag_pool, "is_spicy")
    is_gluten_free = calculate_majority_tag(review_tag_pool, "is_gluten_free")
    is_dairy_free = calculate_majority_tag(review_tag_pool, "is_dairy_free")
    is_nut_free = calculate_majority_tag(review_tag_pool, "is_nut_free")

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

    # If no meal image, check review images preferring real reviews first
    def first_review_image(reviews: list[MealReview]) -> Optional[BackendImageResponse]:
        sorted_reviews = sorted(reviews, key=lambda r: r.created_at, reverse=True)
        for r in sorted_reviews:
            sorted_imgs = sorted(r.images, key=lambda x: x.sequence_index)
            for img_obj in sorted_imgs:
                url = storage.generate_presigned_url_or_none(img_obj.image_path)
                if url:
                    return BackendImageResponse(
                        id=img_obj.id,
                        image_url=url,
                        sequence_index=img_obj.sequence_index,
                    )
        return None

    if not first_image:
        first_image = first_review_image(real_reviews) or first_review_image(
            synthetic_reviews
        )

    distance_meters = None
    if lat is not None and lng is not None and place:
        distance_meters = calculate_distance(lat, lng, place.lat, place.lng)

    return MealResponse(
        id=meal.id,
        name=meal.name,
        price=meal.price,
        place_id=meal.place_id,
        place_name=place.name if place else "",
        avg_rating=avg_rating,
        review_count=review_count,
        avg_waiting_time=avg_waiting_time,
        avg_price=avg_price,
        first_image=first_image,
        distance_meters=distance_meters,
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
    )


def build_place_response(
    place: Place,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> PlaceResponse:
    # Calculate place stats from loaded meals if available
    # Note: This assumes place.meals is loaded and populated with reviews.
    # If not loaded, values fall back to empty lists; ensure relationships are loaded.

    avg_rating = None
    review_count = 0

    if place.meals:
        all_reviews = []
        for m in place.meals:
            if m.meal_reviews:
                # Only count non-synthetic reviews toward stats
                all_reviews.extend([r for r in m.meal_reviews if not r.is_synthetic])

        if all_reviews:
            review_count = len(all_reviews)
            avg_rating = sum(r.rating for r in all_reviews) / review_count

    distance_meters = None
    if lat is not None and lng is not None:
        distance_meters = calculate_distance(lat, lng, place.lat, place.lng)

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

    return PlaceResponse(
        id=place.id,
        name=place.name,
        image_count=image_count,
        first_image=first_image,
        distance_meters=distance_meters,
        latitude=place.lat,
        longitude=place.lng,
        average_rating=avg_rating,
        review_count=review_count,
        cuisine=place.cuisine,
        test_id=place.test_id,
    )
