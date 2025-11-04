# api/auth/dao.py
import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.db.models import User


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(sa.select(User).filter(User.email == email))
    return result.scalars().first()


async def create_user(
    db: AsyncSession, email: str, hashed_password: str, test_id: Optional[str] = None
):
    user = User(email=email, hashed_password=hashed_password, test_id=test_id)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def join_user(db: AsyncSession, user: User, hashed_password: str):
    user.is_joined = True
    user.hashed_password = hashed_password

    await db.commit()
    await db.refresh(user)

    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    user_uuid = uuid.UUID(user_id)
    result = await db.execute(select(User).where(User.id == user_uuid))
    return result.scalar_one_or_none()
