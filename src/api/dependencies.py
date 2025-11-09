# src/api/auth/dependencies.py

from typing import Annotated

from fastapi import Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.dao import get_user_by_id  # Import new function!
from src.api.auth.jwt_utils import (
    oauth2_scheme,
    verify_token,  # Import verify_token
)
from src.db.models import User
from src.db.session import get_async_db_session  # Import session dependency


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_async_db_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = await verify_token(token, db)
    logger.info("Token data in dependency:", token_data)
    if token_data is None:
        raise credentials_exception

    if not token_data.sub:
        logger.warning("Token does not contain user ID.")
        raise credentials_exception

    # OPTIMIZE: User is retrieved in verify_token already.
    user_id = token_data.sub
    user = await get_user_by_id(db, user_id)

    if user is None:
        raise credentials_exception
    return user
