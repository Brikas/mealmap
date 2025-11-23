import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user
from src.db.models import ComputedUserPreferences, Meal, Swipe, User
from src.db.session import get_async_db_session
from src.services.recommendation import RecommendationService

router = APIRouter()


class SwipeRequest(BaseModel):
    meal_id: uuid.UUID
    liked: bool
    session_id: uuid.UUID


@router.post("/swipes", status_code=status.HTTP_201_CREATED)
async def create_swipe(
    swipe_data: SwipeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    debug: bool = False,
    db: AsyncSession = Depends(get_async_db_session),
) -> dict[str, Any]:
    # Check if meal exists
    meal = await db.get(Meal, swipe_data.meal_id)
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    # Check if already swiped
    existing_swipe = await db.execute(
        select(Swipe).where(
            Swipe.user_id == current_user.id,
            Swipe.meal_id == swipe_data.meal_id,
            Swipe.session_id == swipe_data.session_id,
        )
    )
    if existing_swipe.scalars().first():
        return {"message": "Swipe already recorded"}

    # Create Swipe
    swipe = Swipe(
        user_id=current_user.id,
        meal_id=swipe_data.meal_id,
        session_id=swipe_data.session_id,
        liked=swipe_data.liked,
    )
    db.add(swipe)

    # Update User Preferences
    service = RecommendationService(db)
    signal = 1.0 if swipe_data.liked else -0.8
    await service.update_user_preferences(current_user.id, signal, swipe_data.meal_id)

    await db.commit()

    response: dict[str, Any] = {"message": "Swipe recorded"}

    if debug:
        # Fetch updated preferences
        prefs = await db.get(ComputedUserPreferences, current_user.id)
        if prefs:
            response["debug_preferences"] = {
                "tag_prefs": prefs.tag_prefs,
                "cuisine_prefs": prefs.cuisine_prefs,
                "price_bin_prefs": prefs.price_bin_prefs,
                "wait_bin_prefs": prefs.wait_bin_prefs,
            }

    return response
