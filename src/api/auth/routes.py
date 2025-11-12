# api/auth/routes.py
import asyncio
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordRequestForm  # Import
from loguru import logger
from sqlalchemy import UUID, String, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.dao import create_user, join_user
from src.api.auth.dto import LoginResponse, TokenRequest, UserCreate
from src.api.auth.jwt_utils import get_password_hash, login_user
from src.api.dependencies import get_current_user
from src.db.models import User  # Import your models
from src.db.session import get_async_db_session

router = APIRouter(tags=["auth"])


# async def send_welcome_email_async(email: str) -> None:
#     try:
#         send_welcome_email(email)  # Send email to new user
#     except Exception as e:
#         logger.warning(f"Failed to send welcome email: {e}")


@router.post("/register", response_model=LoginResponse)
async def register(
    user_create: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db_session),
) -> LoginResponse:
    """Register a new user with the provided email and password."""

    # Check if user already exists
    existing_user = await db.execute(
        select(User).where(User.email == user_create.email)
    )
    user = existing_user.scalars().first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists",
        )

    # Create new user
    hashed_password = get_password_hash(user_create.password)
    new_user = await create_user(
        db, user_create.email, hashed_password, test_id=user_create.test_id
    )

    # Get token
    token_data = await login_user(db, user_create.email, user_create.password)
    if not token_data:
        raise ValueError("Failed to create user token during registration")

    return LoginResponse(
        access_token=token_data["access_token"],
        user_id=str(new_user.id),
    )


@router.get("/users/me")
async def read_users_me(  # noqa: ANN201
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_async_db_session),
):
    return current_user


@router.post("/token")
async def login_for_access_token(
    request_data: TokenRequest,  # Use the Pydantic model
    db: AsyncSession = Depends(get_async_db_session),
) -> LoginResponse:
    token_data = await login_user(db, request_data.email, request_data.password)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return LoginResponse(
        access_token=token_data["access_token"],
        user_id=str(token_data["user_id"]),
    )


@router.post("/token-docs", response_model=LoginResponse)
async def login_for_access_token_docs(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_async_db_session),
) -> LoginResponse:
    """Login endpoint for Swagger UI docs - uses OAuth2PasswordRequestForm."""
    # OAuth2PasswordRequestForm uses 'username' field, map it to email
    token_data = await login_user(db, form_data.username, form_data.password)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return LoginResponse(
        access_token=token_data["access_token"],
        user_id=str(token_data["user_id"]),
    )
