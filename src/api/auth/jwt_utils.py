import traceback
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from loguru import logger
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import dao
from src.api.auth.dto import Token, TokenCreationData, TokenData
from src.conf.settings import settings  # Assuming you store secrets in settings.py
from src.db.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token-docs")


SECRET_KEY = settings.secret_key  # e.g., a strong random string
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 3000


async def login_user(db, email: str, password: str) -> Optional[Dict[str, str]]:
    """
    Return {"access_token": access_token, "token_type": "bearer"}.
    """
    user = await _try_login_user(db, email, password)
    if not user:
        return None

    access_token = create_access_token(
        TokenCreationData(
            sub=str(user.id),
            email=user.email,
            version=user.token_version,
        )
    )
    return {
        "access_token": access_token,
        "user_id": user.id,
    }


def create_access_token(data: TokenCreationData) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = data.model_dump()
    to_encode.update({"exp": int(expire.timestamp())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


async def verify_token(token: str, db: AsyncSession) -> Optional[TokenData]:
    """Verifies a JWT and checks version against the database."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenData(**payload)
        if token_data.sub is None:
            return None
        # Check version
        user = await dao.get_user_by_id(db, token_data.sub)
        if not user:
            return None
        if token_data.version != user.token_version:
            return None
        return token_data
    except PyJWTError as e:
        logger.warning("JTW verification failed: ", e)
        return None


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# TODO Refactor to login_email etc.
async def _try_login_user(db, email: str, password: str) -> Optional[Any]:
    user = await dao.get_user_by_email(db, email)
    if (
        not user
        or not user.hashed_password
        or not verify_password(password, user.hashed_password)
    ):
        return None
    return user
