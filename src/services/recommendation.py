import math
import random
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from loguru import logger
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import (
    ComputedMealFeatures,
    ComputedUserPreferences,
    CuisineType,
    Meal,
    MealImage,
    MealReview,
    MealReviewImage,
    Place,
    Swipe,
    TriState,
)
from src.db.session import async_session_factory
from src.utils.misc_utils import calculate_distance

### Constants
# Weights
WEIGHT_TAGS = 0.50
WEIGHT_CUISINE = 0.30
WEIGHT_PRICE = 0.10
WEIGHT_WAIT = 0.10
WEIGHT_DISTANCE = 0.20

LEARNING_RATE = 0.15
ACCEL_MAX = 2.5
ACCEL_DECAY = 0.2
RECENCY_HALF_LIFE_DAYS = 90
PRICE_BINS = [0, 5000, 10000, 15000, 20000, 30000, 50000]
WAIT_BINS = [0, 10, 20, 30, 45, 60, 90]

DISTANCE_DECAY_KM = 3.0
MAX_RADIUS_KM = 25.0

EPSILON_RANDOM = 0.1
EPSILON_IGNORE_METRIC = 0.1


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
        self,
        user_id: uuid.UUID,
        limit: int = 20,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> Sequence[Tuple[Meal, float]]:
        """
        Generates feed items for the user based on similarity scores on the fly.
        Returns a list of (Meal, score) tuples.
        """
        # Define image filter condition
        # Meal has images OR Meal has reviews with images
        meal_has_image_filter = or_(
            select(MealImage.id).where(MealImage.meal_id == Meal.id).exists(),
            select(MealReviewImage.id)
            .join(MealReview)
            .where(
                and_(
                    MealReview.meal_id == Meal.id,
                    MealReviewImage.meal_review_id == MealReview.id,
                )
            )
            .exists(),
        )

        # Check total meal count for fallback logic
        total_meals_query = select(func.count(Meal.id))
        total_meals_res = await self.db.execute(total_meals_query)
        total_meals = total_meals_res.scalar() or 0

        # 1. Fetch User Preferences
        user_prefs = await self.db.get(ComputedUserPreferences, user_id)
        if not user_prefs:
            # No prefs, return recent meals as fallback
            # Apply image filter if total meals >= 200
            query = select(Meal)
            if total_meals >= 200:
                query = query.where(meal_has_image_filter)

            # Apply distance filter if location provided
            if lat is not None and lng is not None:
                # Simple bounding box or just fetch and filter in python?
                # For now, let's fetch recent and filter in python if needed,
                # but since this is fallback, maybe just return recent.
                pass

            query = (
                query.order_by(Meal.created_at.desc())
                .limit(limit)
                .options(
                    selectinload(Meal.place),
                    selectinload(Meal.meal_reviews).selectinload(MealReview.images),
                )
            )
            result = await self.db.execute(query)
            meals = result.scalars().all()
            logger.info(f"Returning fallback recent meals for user {user_id}")
            return [(m, 0.0) for m in meals]

        # 2. Fetch Candidate Meals (ComputedMealFeatures)
        # Exclude already swiped meals
        swiped_meals_query = select(Swipe.meal_id).where(Swipe.user_id == user_id)

        # Also exclude meals the user has reviewed
        reviewed_meals_query = select(MealReview.meal_id).where(
            MealReview.user_id == user_id
        )

        # Filter for ComputedMealFeatures
        computed_has_image_filter = or_(
            select(MealImage.id)
            .where(MealImage.meal_id == ComputedMealFeatures.meal_id)
            .exists(),
            select(MealReviewImage.id)
            .join(MealReview)
            .where(
                and_(
                    MealReview.meal_id == ComputedMealFeatures.meal_id,
                    MealReviewImage.meal_review_id == MealReview.id,
                )
            )
            .exists(),
        )

        # Build query
        query = (
            select(ComputedMealFeatures)
            .join(ComputedMealFeatures.meal)
            .join(Meal.place)
            .where(
                and_(
                    ComputedMealFeatures.meal_id.notin_(swiped_meals_query),
                    ComputedMealFeatures.meal_id.notin_(reviewed_meals_query),
                )
            )
        )

        # Apply image filter if total meals >= 200
        if total_meals >= 200:
            query = query.where(computed_has_image_filter)

        # Apply distance filter (25km radius)
        # We can't easily do great circle distance in pure SQL without PostGIS or complex math.
        # We'll fetch candidates and filter in Python, or use a bounding box approximation.
        # Given "only consider places in 25 km radius only", let's try bounding box first.
        # 1 deg lat ~= 111 km. 1 deg lng ~= 111 * cos(lat) km.
        # 25 km ~= 0.225 deg lat.
        if lat is not None and lng is not None:
            lat_delta = MAX_RADIUS_KM / 111.0
            lng_delta = MAX_RADIUS_KM / (111.0 * math.cos(math.radians(lat)))
            query = query.where(
                and_(
                    Place.lat.between(lat - lat_delta, lat + lat_delta),
                    Place.lng.between(lng - lng_delta, lng + lng_delta),
                )
            )

        result = await self.db.execute(query)
        candidates = result.scalars().all()

        # If no candidates found with distance filter, try relaxing it
        if not candidates and lat is not None and lng is not None:
            logger.info("No candidates found within radius, relaxing distance filter")
            # Re-run query without distance filter
            query = select(ComputedMealFeatures).where(
                and_(
                    ComputedMealFeatures.meal_id.notin_(swiped_meals_query),
                    ComputedMealFeatures.meal_id.notin_(reviewed_meals_query),
                )
            )
            if total_meals >= 200:
                query = query.where(computed_has_image_filter)
            result = await self.db.execute(query)
            candidates = result.scalars().all()

        # Epsilon Greedy: Decide if we ignore a metric
        ignored_metric = None
        if random.random() < EPSILON_IGNORE_METRIC:
            metrics = ["tags", "cuisine", "price", "wait"]
            ignored_metric = random.choice(metrics)
            logger.info(f"Exploration: Ignoring metric {ignored_metric}")

        # Fetch places for candidates to calculate distance
        candidate_meal_ids = [c.meal_id for c in candidates]
        if not candidate_meal_ids:
            # Fallback
            query = select(Meal)
            if total_meals >= 200:
                query = query.where(meal_has_image_filter)
            query = (
                query.where(
                    and_(
                        Meal.id.notin_(swiped_meals_query),
                        Meal.id.notin_(reviewed_meals_query),
                    )
                )
                .order_by(Meal.created_at.desc())
                .limit(limit)
                .options(
                    selectinload(Meal.place),
                    selectinload(Meal.meal_reviews).selectinload(MealReview.images),
                )
            )
            result = await self.db.execute(query)
            meals = result.scalars().all()
            logger.info("Returning fallback recent meals (no candidates)")
            return [(m, 0.0) for m in meals]

        places_query = (
            select(Meal.id, Place.lat, Place.lng)
            .join(Place)
            .where(Meal.id.in_(candidate_meal_ids))
        )
        places_res = await self.db.execute(places_query)
        places_map = {r[0]: (r[1], r[2]) for r in places_res.all()}

        scores = []
        for candidate in candidates:
            distance_km = None
            if lat is not None and lng is not None:
                p_lat, p_lng = places_map.get(candidate.meal_id, (None, None))
                if p_lat is not None and p_lng is not None:
                    distance_km = calculate_distance(lat, lng, p_lat, p_lng) / 1000.0

            score = self._calculate_similarity(
                user_prefs,
                candidate,
                distance_km=distance_km,
                ignored_metric=ignored_metric,
            )
            scores.append((candidate.meal_id, score))

        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)

        # Shuffling logic: take top limit + 20, shuffle, then take limit
        if len(scores) > 100:
            pool_size = limit + 20
            top_pool = scores[:pool_size]
            random.shuffle(top_pool)
            top_candidates = top_pool[:limit]
        else:
            top_candidates = scores[:limit]

        # Epsilon Greedy: Random Meal Injection
        # 10% chance for each meal in the top list to be replaced by a random one
        current_top_ids = {x[0] for x in top_candidates}

        debug_random_meal_injections = 0
        for i in range(len(top_candidates)):
            if random.random() < EPSILON_RANDOM:
                # Find candidates not currently in the top list
                available_candidates = [
                    c for c in candidates if c.meal_id not in current_top_ids
                ]

                if available_candidates:
                    random_candidate = random.choice(available_candidates)

                    # Replace the current recommendation with the random one
                    top_candidates[i] = (random_candidate.meal_id, 0.0)

                    # Add to current_top_ids to ensure uniqueness in this batch
                    current_top_ids.add(random_candidate.meal_id)
                    debug_random_meal_injections += 1
        if debug_random_meal_injections > 0:
            logger.info(
                f"Exploration: Injected {debug_random_meal_injections} random meals"
            )

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

        # Create a map for scores
        score_map = {x[0]: x[1] for x in top_candidates}

        for meal_id in top_meal_ids:
            if meal_id in meal_map:
                meal = meal_map[meal_id]
                score = score_map.get(meal_id, 0.0)
                # Log the reason/score
                logger.debug(f"Recommended meal {meal.id} with score {score}")
                recommendations.append((meal, score))

        return recommendations

    def _calculate_similarity(
        self,
        user_prefs: ComputedUserPreferences,
        meal_features: ComputedMealFeatures,
        distance_km: Optional[float] = None,
        ignored_metric: Optional[str] = None,
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
        sim_tags = 0.0
        if ignored_metric != "tags":
            sim_tags = cosine_sim(user_prefs.tag_prefs, meal_features.tag_vector)

        # Cuisine
        sim_cuisine = 0.0
        if ignored_metric != "cuisine":
            sim_cuisine = cosine_sim(
                user_prefs.cuisine_prefs, meal_features.cuisine_vector
            )

        # Price
        sim_price = 0.0
        if ignored_metric != "price":
            price_vec = self._scalar_to_soft_bin(meal_features.avg_price, PRICE_BINS)
            sim_price = cosine_sim(user_prefs.price_bin_prefs, price_vec)

        # Wait
        sim_wait = 0.0
        if ignored_metric != "wait":
            wait_vec = self._scalar_to_soft_bin(meal_features.avg_wait_time, WAIT_BINS)
            sim_wait = cosine_sim(user_prefs.wait_bin_prefs, wait_vec)

        # Distance
        sim_dist = 0.0
        if distance_km is not None:
            # Decay function: exp(-lambda * d)
            # Half-life at 3km -> exp(-lambda * 3) = 0.5 -> lambda = ln(2)/3 ~= 0.231
            decay_rate = math.log(2) / DISTANCE_DECAY_KM
            sim_dist = math.exp(-decay_rate * distance_km)

        final_score = (
            sim_tags * WEIGHT_TAGS
            + sim_cuisine * WEIGHT_CUISINE
            + sim_price * WEIGHT_PRICE
            + sim_wait * WEIGHT_WAIT
            + sim_dist * WEIGHT_DISTANCE
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
