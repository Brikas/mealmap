from contextlib import contextmanager
from typing import Any, AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.conf.settings import settings

DATABASE_URL = settings.sqlalchemy_database_url
DATABASE_ASYNC_URL = settings.sqlalchemy_async_database_url


async_engine = create_async_engine(
    DATABASE_ASYNC_URL,
    echo=False,
    pool_size=30,
    max_overflow=60,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,  # Ensures connections are alive
)

async_session_factory = async_sessionmaker(
    async_engine,
    autoflush=True,
    expire_on_commit=False,
)

# scoped_session_factory = async_scoped_session(
#     sessionmaker(
#         async_engine,
#         autoflush=True,  # default
#         autocommit=False,  # default
#         expire_on_commit=False,
#         class_=AsyncSession,
#     ),
# )


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional scope for asynchronous database operations."""
    session: AsyncSession = async_session_factory()
    try:
        yield session
        await session.commit()
    except DBAPIError:
        await session.rollback()
        raise
    finally:
        await session.close()


engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_size=5,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,  # Ensures connections are alive
)

Session = sessionmaker(engine)


@contextmanager
def get_db_session() -> Any:
    """Provide a transactional scope for synchronous database operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except DBAPIError:
        session.rollback()
        raise
    finally:
        session.close()
