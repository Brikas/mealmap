from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.conf.settings import settings
from src.db.models import Meal
from src.db.session import get_async_db_session
from src.services.recommendation import (
    RecommendationService,
    update_meal_features_background,
)

router = APIRouter(prefix="/admin")

API_KEY_NAME = "X-Admin-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_admin_api_key(
    api_key_header: str = Depends(api_key_header),
) -> str:
    if api_key_header == settings.admin_access_key:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate admin credentials",
    )


@router.post("/recompute-features")
async def recompute_all_meal_features(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db_session),
    admin_key: str = Depends(get_admin_api_key),
) -> Dict[str, Any]:
    """
    Triggers re-computation of features for ALL meals in the database.

    Useful for backfilling data or after changing the feature extraction logic.
    Requires admin access key.
    """
    try:
        # 1. Fetch all meal IDs
        result = await db.execute(select(Meal.id))
        meal_ids = result.scalars().all()

        # 2. Schedule background updates
        count = 0
        for meal_id in meal_ids:
            background_tasks.add_task(update_meal_features_background, meal_id)
            count += 1

        return {
            "status": "success",
            "message": f"Scheduled re-computation for {count} meals",
            "count": count,
        }
    except Exception as e:
        logger.error(f"Recompute scheduling failed: {e}")
        return {
            "status": "error",
            "message": "Recompute scheduling failed",
            "details": str(e),
        }
