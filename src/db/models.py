# src/db/models.py
import uuid
from typing import List, Optional

import sqlalchemy as sa
from passlib.context import CryptContext
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.base import Base
from src.services import storage

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

## poetry run alembic revision --autogenerate -m "WIP"
## poetry run alembic upgrade head
### IS RAN BY THE make run migrator within docker-compose


class User(Base):
    __tablename__ = "app_user"
    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[Optional[str]] = mapped_column(
        String, unique=True, index=True, nullable=True
    )

    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    image_path: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # Example: Used for testing purposes

    created_at: Mapped[float] = mapped_column(
        sa.Float, server_default=func.extract("epoch", func.now())
    )

    test_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # New field for JWT invalidation support
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
