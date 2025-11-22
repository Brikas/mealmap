import asyncio
import os
import random
import sys
import uuid
from collections import defaultdict

from faker import Faker
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.conf.settings import settings
from src.db.models import (
    MealReview,
    Place,
    Swipe,
    TriState,
    User,
    UserFeedItem,
)
from src.services.recommendation import RecommendationService

faker = Faker()

NUM_USERS = 10
REVIEWS_PER_USER = 5
LIKES_PER_USER = 8


def _fix_local_db_url(db_url: str) -> str:
    if "postgres:5432" in db_url:
        return db_url.replace("postgres:5432", "localhost:5432")
    return db_url


DB_URL = _fix_local_db_url(settings.sqlalchemy_async_database_url)
engine = create_async_engine(DB_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def random_tri_state() -> TriState:
    return random.choice(
        [TriState.yes, TriState.no, TriState.unspecified, TriState.unspecified]
    )


async def ensure_places(session: AsyncSession, count: int = 5) -> list[Place]:
    result = await session.execute(select(Place))
    places = result.scalars().all()
    if len(places) >= count:
        return places

    for _ in range(count - len(places)):
        place = Place(
            name=faker.company(),
            address=faker.address().replace("\n", ", "),
            lat=random.uniform(-90, 90),
            lng=random.uniform(-180, 180),
        )
        session.add(place)
    await session.commit()
    result = await session.execute(select(Place))
    return result.scalars().all()


async def ensure_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User))
    users = result.scalars().all()
    if len(users) >= NUM_USERS:
        return users

    for _ in range(NUM_USERS - len(users)):
        user = User(
            email=faker.unique.email(),
            first_name=faker.first_name(),
            last_name=faker.last_name(),
        )
        session.add(user)
    await session.commit()
    result = await session.execute(select(User))
    return result.scalars().all()


async def seed_reviews(session: AsyncSession, users: list[User], places: list[Place]):
    for user in users:
        result = await session.execute(
            select(func.count(MealReview.id)).where(MealReview.user_id == user.id)
        )
        review_count = result.scalar_one()
        missing = max(0, REVIEWS_PER_USER - review_count)
        for _ in range(missing):
            place = random.choice(places)
            review = MealReview(
                user_id=user.id,
                place_id=place.id,
                meal_name=faker.word().title() + " " + random.choice(
                    ["Burger", "Bibimbap", "Taco", "Pizza", "Salad"]
                ),
                rating=random.randint(3, 5),
                text=faker.paragraph(nb_sentences=2),
                waiting_time_minutes=random.randint(5, 40),
                price=round(random.uniform(5, 35), 2),
                is_spicy=random_tri_state(),
                is_vegan=random_tri_state(),
                is_vegetarian=random_tri_state(),
                is_halal=random_tri_state(),
                is_gluten_free=random_tri_state(),
                is_dairy_free=random_tri_state(),
                is_nut_free=random_tri_state(),
            )
            session.add(review)
    await session.commit()


async def seed_swipes(session: AsyncSession, users: list[User]):
    result = await session.execute(select(MealReview))
    reviews = result.scalars().all()
    if not reviews:
        return

    reviews_by_user = defaultdict(list)
    for review in reviews:
        reviews_by_user[review.user_id].append(review.id)

    for user in users:
        current_swipes = await session.execute(
            select(func.count(Swipe.id)).where(Swipe.user_id == user.id)
        )
        missing = max(0, LIKES_PER_USER - current_swipes.scalar_one())
        possible_reviews = [r.id for r in reviews if r.user_id != user.id]
        if not possible_reviews:
            continue
        for review_id in random.sample(
            possible_reviews, k=min(missing, len(possible_reviews))
        ):
            swipe = Swipe(
                user_id=user.id,
                meal_review_id=review_id,
                session_id=uuid.uuid4(),
                liked=random.choice([True, True, False]),
            )
            session.add(swipe)
    await session.commit()


async def generate_feeds(session: AsyncSession, users: list[User]):
    service = RecommendationService(session)
    for user in users:
        await session.execute(
            select(UserFeedItem)
            .where(UserFeedItem.user_id == user.id)
            .limit(1)
        )
        await service.generate_feed(user.id)


async def main():
    print(f"Connecting to {DB_URL}")
    async with AsyncSessionLocal() as session:
        places = await ensure_places(session)
        users = await ensure_users(session)
        await seed_reviews(session, users, places)
        await seed_swipes(session, users)
        await generate_feeds(session, users[:5])
        print("✅ Seed complete. Check the DB and run the notebook for vibes.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

