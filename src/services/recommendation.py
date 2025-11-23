import math
import uuid
from typing import Dict, List, Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import (
    ComputedMealFeatures,
    ComputedUserPreferences,
    CuisineType,
    Meal,
    MealReview,
    Place,
    Swipe,
    TriState,
)
from src.db.session import async_session_factory

# Constants
WEIGHT_TAGS = 0.50
WEIGHT_CUISINE = 0.30
WEIGHT_PRICE = 0.10
WEIGHT_WAIT = 0.10
LEARNING_RATE = 0.15
ACCEL_MAX = 2.5
ACCEL_DECAY = 0.2
RECENCY_HALF_LIFE_DAYS = 90
PRICE_BINS = [0, 5000, 10000, 15000, 20000, 30000, 50000]
WAIT_BINS = [0, 10, 20, 30, 45, 60, 90]


class RecommendationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_meal_features(self, meal_id: uuid.UUID) -> None:
        """
        Re-computes the feature vector for a meal based on all its reviews.
        """
        # Fetch all reviews for the meal
        query = (
            select(MealReview)
            .where(MealReview.meal_id == meal_id)
            .options(selectinload(MealReview.meal).selectinload(Meal.place))
        )
        result = await self.db.execute(query)
        reviews = result.scalars().all()

        # If no reviews, we still need to update features based on Meal/Place attributes
        # (e.g. price, cuisine)
        # So we fetch the meal directly if reviews are empty
        if not reviews:
            meal_query = (
                select(Meal).where(Meal.id == meal_id).options(selectinload(Meal.place))
            )
            meal_res = await self.db.execute(meal_query)
            meal = meal_res.scalars().first()
            if not meal:
                return
        else:
            meal = reviews[0].meal

        # 1. Tag Aggregation
        tag_vector = {}
        tags = [
            "is_vegan",
            "is_halal",
            "is_vegetarian",
            "is_spicy",
            "is_gluten_free",
            "is_dairy_free",
            "is_nut_free",
        ]

        for tag in tags:
            score = 0.0
            count = 0
            for r in reviews:
                val = getattr(r, tag)
                if val == TriState.yes:
                    score += 1.0
                    count += 1
                elif val == TriState.no:
                    score -= 1.0
                    count += 1
                # unspecified is 0

            if len(reviews) > 0:
                tag_vector[tag] = score / len(reviews)
            else:
                tag_vector[tag] = 0.0

        # 2. Cuisine Aggregation
        cuisine_vector = {}
        if meal.place.cuisine and meal.place.cuisine != CuisineType.unspecified:
            c = meal.place.cuisine.lower().strip()
            cuisine_vector[c] = 1.0

        # 3. Scalar Aggregation
        prices = [r.price for r in reviews if r.price is not None]
        avg_price = sum(prices) / len(prices) if prices else (meal.price or 0.0)

        wait_times = [
            r.waiting_time_minutes
            for r in reviews
            if r.waiting_time_minutes is not None
        ]
        avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0.0

        # Update or Create ComputedMealFeatures
        computed = await self.db.get(ComputedMealFeatures, meal_id)
        if not computed:
            computed = ComputedMealFeatures(meal_id=meal_id)
            self.db.add(computed)

        computed.tag_vector = tag_vector
        computed.cuisine_vector = cuisine_vector
        computed.avg_price = avg_price
        computed.avg_wait_time = avg_wait_time
        computed.review_count = len(reviews)

        await self.db.commit()

    async def update_place_meals_features(self, place_id: uuid.UUID) -> None:
        """
        Re-computes features for all meals in a place.
        Useful when place attributes (like cuisine) change.
        """
        query = select(Meal.id).where(Meal.place_id == place_id)
        result = await self.db.execute(query)
        meal_ids = result.scalars().all()

        for meal_id in meal_ids:
            await self.update_meal_features(meal_id)

    async def update_user_preferences(
        self, user_id: uuid.UUID, signal_strength: float, meal_id: uuid.UUID
    ):
        """
        Updates user preference vector based on an interaction (Swipe or Review).
        """
        # Fetch ComputedMealFeatures
        meal_features = await self.db.get(ComputedMealFeatures, meal_id)
        if not meal_features:
            # If not computed yet, compute it now
            await self.update_meal_features(meal_id)
            meal_features = await self.db.get(ComputedMealFeatures, meal_id)
            if not meal_features:
                return  # Should not happen if meal exists

        # Fetch ComputedUserPreferences
        user_prefs = await self.db.get(ComputedUserPreferences, user_id)
        if not user_prefs:
            user_prefs = ComputedUserPreferences(
                user_id=user_id,
                tag_prefs={},
                cuisine_prefs={},
                price_bin_prefs={},
                wait_bin_prefs={},
            )
            self.db.add(user_prefs)

        # Real-time update, so time decay is 1.0 (t=0)
        w_time = 1.0

        # Update Logic
        def update_feature_group(prefs_dict, feature_vector):
            new_prefs = dict(prefs_dict)  # Copy
            for key, val in feature_vector.items():
                # Spec: Meal Strength |S_m| > 0.2
                if abs(val) <= 0.2:
                    continue

                # Get current pref
                current = new_prefs.get(key, {"val": 0.0, "count": 0})
                old_val = current["val"]
                count = current["count"]

                # Cold Start Multiplier
                multiplier = 1 + (ACCEL_MAX * math.exp(-ACCEL_DECAY * count))

                # Effective Signal
                effective_signal = signal_strength * w_time * val

                # Delta Update
                new_val = old_val + LEARNING_RATE * multiplier * (
                    effective_signal - old_val
                )

                # Clamp
                new_val = max(-1.0, min(1.0, new_val))

                new_prefs[key] = {"val": new_val, "count": count + 1}
            return new_prefs

        # Update Tags
        user_prefs.tag_prefs = update_feature_group(
            user_prefs.tag_prefs, meal_features.tag_vector
        )

        # Update Cuisines
        user_prefs.cuisine_prefs = update_feature_group(
            user_prefs.cuisine_prefs, meal_features.cuisine_vector
        )

        # Update Price (Scalar to Soft Bin)
        price_vector = self._scalar_to_soft_bin(meal_features.avg_price, PRICE_BINS)
        user_prefs.price_bin_prefs = update_feature_group(
            user_prefs.price_bin_prefs, price_vector
        )

        # Update Wait Time (Scalar to Soft Bin)
        wait_vector = self._scalar_to_soft_bin(meal_features.avg_wait_time, WAIT_BINS)
        user_prefs.wait_bin_prefs = update_feature_group(
            user_prefs.wait_bin_prefs, wait_vector
        )

        # Force update of JSONB fields (SQLAlchemy sometimes doesn't detect changes in mutable dicts)
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(user_prefs, "tag_prefs")
        flag_modified(user_prefs, "cuisine_prefs")
        flag_modified(user_prefs, "price_bin_prefs")
        flag_modified(user_prefs, "wait_bin_prefs")

        await self.db.commit()

    def _scalar_to_soft_bin(self, value: float, bins: List[int]) -> Dict[str, float]:
        target_bin = 0
        for i in range(len(bins) - 1):
            if bins[i] <= value < bins[i + 1]:
                target_bin = i
                break
        if value >= bins[-1]:
            target_bin = len(bins) - 1

        vector = {}
        vector[f"r{target_bin}"] = 1.0
        if target_bin > 0:
            vector[f"r{target_bin-1}"] = 0.25
        if target_bin < len(bins) - 1:
            vector[f"r{target_bin+1}"] = 0.25

        return vector

    async def get_recommendations(
        self, user_id: uuid.UUID, limit: int = 20
    ) -> Sequence[Meal]:
        """
        Generates feed items for the user based on similarity scores on the fly.
        Returns a list of Meal objects.
        """
        # 1. Fetch User Preferences
        user_prefs = await self.db.get(ComputedUserPreferences, user_id)
        if not user_prefs:
            # No prefs, return recent meals as fallback
            query = (
                select(Meal)
                .order_by(Meal.created_at.desc())
                .limit(limit)
                .options(
                    selectinload(Meal.place),
                    selectinload(Meal.meal_reviews).selectinload(MealReview.images),
                )
            )
            result = await self.db.execute(query)
            return result.scalars().all()

        # 2. Fetch Candidate Meals (ComputedMealFeatures)
        # Exclude already swiped meals
        swiped_meals_query = select(Swipe.meal_id).where(Swipe.user_id == user_id)

        # Also exclude meals the user has reviewed
        reviewed_meals_query = select(MealReview.meal_id).where(
            MealReview.user_id == user_id
        )

        # Fetch candidates
        # We fetch ComputedMealFeatures directly
        query = (
            select(ComputedMealFeatures)
            .where(
                and_(
                    ComputedMealFeatures.meal_id.notin_(swiped_meals_query),
                    ComputedMealFeatures.meal_id.notin_(reviewed_meals_query),
                )
            )
            .limit(500)
        )  # Limit candidate pool for performance

        result = await self.db.execute(query)
        candidates = result.scalars().all()

        scores = []
        for candidate in candidates:
            score = self._calculate_similarity(user_prefs, candidate)
            scores.append((candidate.meal_id, score))

        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        top_candidates = scores[:limit]

        # Fetch Meal objects for the top candidates
        top_meal_ids = [x[0] for x in top_candidates]
        if not top_meal_ids:
            return []

        meal_query = (
            select(Meal)
            .where(Meal.id.in_(top_meal_ids))
            .options(
                selectinload(Meal.place),
                selectinload(Meal.meal_reviews).selectinload(MealReview.images),
            )
        )
        meal_res = await self.db.execute(meal_query)
        meals = meal_res.scalars().all()

        # Sort meals based on the order in top_meal_ids
        meal_map = {m.id: m for m in meals}
        recommendations = []
        for meal_id in top_meal_ids:
            if meal_id in meal_map:
                recommendations.append(meal_map[meal_id])

        return recommendations

    def _calculate_similarity(
        self,
        user_prefs: ComputedUserPreferences,
        meal_features: ComputedMealFeatures,
    ) -> float:
        def cosine_sim(vec1: Dict, vec2: Dict) -> float:
            # vec1 is user prefs: {key: {val: float, count: int}}
            # vec2 is meal features: {key: float}

            dot_product = 0.0
            norm1 = 0.0
            norm2 = 0.0

            # Keys in vec1
            for key, pref in vec1.items():
                val1 = pref["val"]
                norm1 += val1**2
                if key in vec2:
                    val2 = vec2[key]
                    dot_product += val1 * val2

            # Keys in vec2 (for norm2)
            for val in vec2.values():
                norm2 += val**2

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (math.sqrt(norm1) * math.sqrt(norm2))

        # Tags
        sim_tags = cosine_sim(user_prefs.tag_prefs, meal_features.tag_vector)

        # Cuisine
        sim_cuisine = cosine_sim(user_prefs.cuisine_prefs, meal_features.cuisine_vector)

        # Price
        price_vec = self._scalar_to_soft_bin(meal_features.avg_price, PRICE_BINS)
        sim_price = cosine_sim(user_prefs.price_bin_prefs, price_vec)

        # Wait
        wait_vec = self._scalar_to_soft_bin(meal_features.avg_wait_time, WAIT_BINS)
        sim_wait = cosine_sim(user_prefs.wait_bin_prefs, wait_vec)

        final_score = (
            sim_tags * WEIGHT_TAGS
            + sim_cuisine * WEIGHT_CUISINE
            + sim_price * WEIGHT_PRICE
            + sim_wait * WEIGHT_WAIT
        )

        return final_score


async def update_meal_features_background(meal_id: uuid.UUID) -> None:
    """Background task wrapper for updating meal features."""
    async with async_session_factory() as session:
        service = RecommendationService(session)
        await service.update_meal_features(meal_id)


async def update_place_meals_features_background(place_id: uuid.UUID) -> None:
    """Background task wrapper for updating all meals in a place."""
    async with async_session_factory() as session:
        service = RecommendationService(session)
        await service.update_place_meals_features(place_id)


async def update_user_preferences_background(
    user_id: uuid.UUID, signal_strength: float, meal_id: uuid.UUID
) -> None:
    """Background task wrapper for updating user preferences."""
    async with async_session_factory() as session:
        service = RecommendationService(session)
        await service.update_user_preferences(user_id, signal_strength, meal_id)
