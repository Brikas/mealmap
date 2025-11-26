from typing import Any, Dict, List, Optional, Union

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.security import APIKeyHeader
from loguru import logger
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import dao, jwt_utils
from src.api.auth.dto import TokenCreationData
from src.api.routes_users import UserResponse
from src.conf.settings import settings
from src.db.models import Meal, User
from src.db.session import get_async_db_session
from src.services import storage
from src.services.recommendation import (
    RecommendationService,
    update_meal_features_background,
)
from src.utils.pagination import Page, PaginationInput, paginate_query

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


@router.post("/impersonate/{user_id}")
async def impersonate_user(
    user_id: str,
    db: AsyncSession = Depends(get_async_db_session),
    admin_key: str = Depends(get_admin_api_key),
) -> Dict[str, Any]:
    """
    Generates an access token for the specified user.

    Requires admin access key.
    """
    try:
        user = await dao.get_user_by_id(db, user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        ) from None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    access_token = jwt_utils.create_access_token(
        TokenCreationData(
            sub=str(user.id),
            email=user.email,
            version=user.token_version,
        )
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
    }
