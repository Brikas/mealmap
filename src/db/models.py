# src/db/models.py
import uuid
from typing import List, Optional

import sqlalchemy as sa
from passlib.context import CryptContext
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
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
    phone_number: Mapped[Optional[str]] = mapped_column(
        String, unique=True, index=True, nullable=True
    )  # New: allow signup with phone
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    image_path: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # Example: Used for testing purposes

    instagram: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # Example: Used for testing purposes

    created_at: Mapped[float] = mapped_column(
        sa.Float, server_default=func.extract("epoch", func.now())
    )

    test_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # If None, the user has only been invired, but never signed up
    joined_at: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)

    is_joined: Mapped[bool] = mapped_column(Boolean, default=True)

    # New field for JWT invalidation support
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )

    # Relationships
    items = relationship("Item", back_populates="owner", passive_deletes=True)
    # TODO Check if I need the passive_deletes=True here

    # group_memberships = relationship("GroupMembers", back_populates="user")
    group_memberships = relationship(
        "GroupMembers",
        foreign_keys=lambda: [
            GroupMembers.user_id
        ],  # Use lambda to avoid circular import issues. Typecheking.
        back_populates="user",
        cascade="all, delete-orphan",  # This ensures proper cascade behavior
        passive_deletes=True,  # Let the database handle the CASCADE
    )

    @staticmethod
    def update_joined_at(target, connection):
        """
        Sets the joined_at timestamp when is_joined becomes True.
        """
        if target.is_joined and target.joined_at is None:
            connection.execute(
                sa.update(User)
                .where(User.id == target.id)
                .values(joined_at=func.extract("epoch", func.now()))
            )


@event.listens_for(User, "after_insert")
def set_joined_at_on_insert(mapper, connection, target):
    User.update_joined_at(target, connection)


@event.listens_for(User, "after_update")
def set_joined_at_on_update(mapper, connection, target):
    User.update_joined_at(target, connection)
