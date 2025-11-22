import uuid
from typing import List, Dict, Any, Set
from sqlalchemy import select, and_, func, desc, not_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi.concurrency import run_in_threadpool
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.db.models import User, MealReview, Swipe, UserFeedItem, TriState, Place
from loguru import logger

class RecommendationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_feed(self, user_id: uuid.UUID, limit: int = 10) -> List[MealReview]:
        """
        Get the next batch of recommended meals for the user.
        If the queue is empty, generates new recommendations.
        """
        # 1. Try to fetch from existing queue
        query = (
            select(MealReview)
            .join(UserFeedItem, MealReview.id == UserFeedItem.meal_review_id)
            .where(UserFeedItem.user_id == user_id)
            .order_by(UserFeedItem.score.desc())
            .limit(limit)
            .options(
                selectinload(MealReview.images),
                selectinload(MealReview.place).selectinload(Place.images),
                selectinload(MealReview.user)
            )
        )
        result = await self.db.execute(query)
        feed_items = result.scalars().all()
        
        if not feed_items:
            logger.info(f"Feed empty for user {user_id}, generating recommendations...")
            await self.generate_feed(user_id)
            # Re-fetch
            result = await self.db.execute(query)
            feed_items = result.scalars().all()
            
        return feed_items

    async def generate_feed(self, user_id: uuid.UUID) -> None:
        """
        Populates UserFeedItem table with smart recommendations.
        Uses a hybrid of Content-Based and Collaborative Filtering.
        """
        # 1. Get user's liked reviews (positive swipes) to build profile
        liked_swipes_query = (
            select(Swipe)
            .where(and_(Swipe.user_id == user_id, Swipe.liked == True))
            .options(selectinload(Swipe.meal_review))
        )
        liked_swipes_res = await self.db.execute(liked_swipes_query)
        liked_reviews = [s.meal_review for s in liked_swipes_res.scalars().all()]

        # 1b. Get user's own high-rated reviews (Self-authored content indicates preference)
        authored_reviews_query = (
            select(MealReview)
            .where(and_(MealReview.user_id == user_id, MealReview.rating >= 4))
        )
        authored_reviews_res = await self.db.execute(authored_reviews_query)
        authored_reviews = authored_reviews_res.scalars().all()
        
        # Combine swipes and own reviews for the "User Profile"
        # We use a set logic to avoid duplicates if one somehow swiped their own review
        liked_reviews_map = {r.id: r for r in liked_reviews}
        for r in authored_reviews:
            liked_reviews_map[r.id] = r
        liked_reviews = list(liked_reviews_map.values())
        
        # 2. Identify what to exclude (already swiped)
        swiped_ids_query = select(Swipe.meal_review_id).where(Swipe.user_id == user_id)
        swiped_ids_res = await self.db.execute(swiped_ids_query)
        swiped_ids = set(swiped_ids_res.scalars().all())
        
        # 3. Collaborative Candidate Generation (Meals liked by similar users)
        collab_boost_ids = set()
        if liked_reviews:
            liked_review_ids = [r.id for r in liked_reviews]
            
            # Find users who liked what I liked
            similar_users_query = (
                select(Swipe.user_id)
                .where(Swipe.meal_review_id.in_(liked_review_ids))
                .where(Swipe.liked == True)
                .where(Swipe.user_id != user_id)
                .distinct()
                .limit(50)
            )
            similar_users_res = await self.db.execute(similar_users_query)
            similar_user_ids = similar_users_res.scalars().all()
            
            if similar_user_ids:
                # Find meals liked by those users that I haven't seen
                collab_candidates_query = (
                    select(MealReview.id)
                    .join(Swipe, MealReview.id == Swipe.meal_review_id)
                    .where(Swipe.user_id.in_(similar_user_ids))
                    .where(Swipe.liked == True)
                    .where(MealReview.id.notin_(swiped_ids))
                    .group_by(MealReview.id)
                    .order_by(func.count(Swipe.user_id).desc())
                    .limit(30)
                )
                collab_res = await self.db.execute(collab_candidates_query)
                collab_boost_ids = set(collab_res.scalars().all())

        # 4. Content Candidates (General pool + Collab candidates)
        # We fetch a pool of candidates to rank. 
        # Include collab candidates and some random/recent popular ones to ensure variety.
        
        # Ensure we don't exclude if swiped_ids is empty (SQLAlchemy handles empty IN/NOT IN gracefully usually, but safe check)
        # Using run_in_threadpool for heavy lifting later, but fetching data is async IO
        
        candidates_query = (
            select(MealReview)
            .where(MealReview.id.notin_(swiped_ids))
            .where(MealReview.user_id != user_id) 
            .order_by(MealReview.created_at.desc()) # Bias recency for pool
            .limit(100)
        )
        candidates_res = await self.db.execute(candidates_query)
        candidates = candidates_res.scalars().all()
        
        # If we have collab candidates that weren't in the top 100 recent, fetch them specifically
        missing_collab_ids = collab_boost_ids - {c.id for c in candidates}
        if missing_collab_ids:
            extra_query = select(MealReview).where(MealReview.id.in_(missing_collab_ids))
            extra_res = await self.db.execute(extra_query)
            candidates.extend(extra_res.scalars().all())

        if not candidates:
            return

        # 5. Calculate Scores (Hybrid)
        scores = await run_in_threadpool(
            self._calculate_affinity_scores, liked_reviews, candidates, collab_boost_ids
        )
        
        # 6. Store Recommendations
        # Clear old queue? Or append?
        # For now, we append.
        
        # Sort by score
        top_candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:20]
        
        for review_id, score in top_candidates:
            # Check uniqueness again just in case (race conditions)
            exists_query = select(UserFeedItem).where(
                and_(UserFeedItem.user_id == user_id, UserFeedItem.meal_review_id == review_id)
            )
            exists = (await self.db.execute(exists_query)).first()
            if not exists:
                feed_item = UserFeedItem(
                    user_id=user_id,
                    meal_review_id=review_id,
                    score=float(score)
                )
                self.db.add(feed_item)
            
        await self.db.commit()

    def _calculate_affinity_scores(
        self, 
        liked_reviews: List[MealReview], 
        candidates: List[MealReview],
        collab_ids: Set[uuid.UUID]
    ) -> Dict[uuid.UUID, float]:
        
        # Base scores: Rating
        scores = {c.id: float(c.rating) * 0.2 for c in candidates}
        
        # Collaborative Boost
        for cid in scores:
            if cid in collab_ids:
                scores[cid] += 2.0 # Significant boost for collaborative matches
        
        if not liked_reviews:
            # Cold start: rely on rating and collab
            return scores

        # Content-Based Filtering (TF-IDF on text + tags)
        def extract_features(review: MealReview) -> str:
            tags = [
                "vegan" if review.is_vegan == TriState.yes else "",
                "halal" if review.is_halal == TriState.yes else "",
                "vegetarian" if review.is_vegetarian == TriState.yes else "",
                "spicy" if review.is_spicy == TriState.yes else "",
            ]
            # Weight the meal name heavily
            text_content = f"{review.meal_name} {review.meal_name} {review.text or ''}" 
            return f"{text_content} {' '.join(tags)}"

        liked_docs = [extract_features(r) for r in liked_reviews]
        candidate_docs = [extract_features(r) for r in candidates]
        
        # TF-IDF Vectorization
        # min_df=1 because we might have small dataset
        vectorizer = TfidfVectorizer(stop_words='english', min_df=1)
        all_docs = liked_docs + candidate_docs
        
        try:
            tfidf_matrix = vectorizer.fit_transform(all_docs)
            
            liked_vecs = tfidf_matrix[:len(liked_docs)]
            candidate_vecs = tfidf_matrix[len(liked_docs):]
            
            # Similarity: (n_candidates, n_liked)
            similarity_matrix = cosine_similarity(candidate_vecs, liked_vecs)
            
            # Mean similarity score (can also use max for "most similar to something I liked")
            # Using Max is often better for "finding something similar to my favorite dish"
            content_scores = similarity_matrix.max(axis=1) 
            
            # Normalize and add to scores
            # content_scores is numpy array
            for i, candidate in enumerate(candidates):
                # Scale content score (0-1 usually) to be comparable to our other components
                scores[candidate.id] += content_scores[i] * 3.0 
                
        except ValueError as e:
            logger.warning(f"Error in TF-IDF (likely empty vocabulary): {e}")
            
        return scores

