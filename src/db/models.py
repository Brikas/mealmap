import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

import sqlalchemy as sa
from passlib.context import CryptContext
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    event,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.base import Base
from src.services import storage

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

## poetry run alembic revision --autogenerate -m "WIP"
## poetry run alembic upgrade head
### IS RAN BY THE make run migrator within docker-compose

# --- Helper Models for Image Associations ---


class PlaceImage(Base):
    __tablename__ = "place_image"
    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    place_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("place.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_path: Mapped[str] = mapped_column(String, nullable=False)
    # A place can have multiple images
    place: Mapped["Place"] = relationship(back_populates="images")
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MealReviewImage(Base):
    __tablename__ = "meal_review_image"
    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    meal_review_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("meal_review.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_path: Mapped[str] = mapped_column(String, nullable=False)
    # A review can have multiple images
    meal_review: Mapped["MealReview"] = relationship(back_populates="images")
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# --- Core Application Models ---


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

    # --- Relationships ---
    meal_reviews: Mapped[List["MealReview"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    swipes: Mapped[List["Swipe"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Place(Base):
    __tablename__ = "place"
    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=func.now(), onupdate=func.now()
    )

    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)

    # --- Relationships ---
    images: Mapped[List[PlaceImage]] = relationship(
        back_populates="place", cascade="all, delete-orphan"
    )
    meal_reviews: Mapped[List["MealReview"]] = relationship(
        back_populates="place", cascade="all, delete-orphan"
    )


class MealReview(Base):
    __tablename__ = "meal_review"
    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=func.now(), onupdate=func.now()
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    place_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), ForeignKey("place.id"), nullable=False
    )

    meal_name: Mapped[str] = mapped_column(String, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    waiting_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)

    # Enums
    is_vegan: Mapped[str] = mapped_column(
        SQLEnum("no", "not specified", "yes", name="vegan_status_enum"),
        nullable=False,
        server_default="not specified",
    )
    is_halal: Mapped[str] = mapped_column(
        SQLEnum("no", "not specified", "yes", name="halal_status_enum"),
        nullable=False,
        server_default="not specified",
    )
    is_vegetarian: Mapped[str] = mapped_column(
        SQLEnum("no", "not specified", "yes", name="vegetarian_status_enum"),
        nullable=False,
        server_default="not specified",
    )
    is_spicy: Mapped[str] = mapped_column(
        SQLEnum("no", "not specified", "yes", name="spicy_status_enum"),
        nullable=False,
        server_default="not specified",
    )
    is_gluten_free: Mapped[str] = mapped_column(
        SQLEnum("no", "not specified", "yes", name="gluten_free_status_enum"),
        nullable=False,
        server_default="not specified",
    )
    is_dairy_free: Mapped[str] = mapped_column(
        SQLEnum("no", "not specified", "yes", name="dairy_free_status_enum"),
        nullable=False,
        server_default="not specified",
    )
    is_nut_free: Mapped[str] = mapped_column(
        SQLEnum("no", "not specified", "yes", name="nut_free_status_enum"),
        nullable=False,
        server_default="not specified",
    )

    # --- Relationships ---
    user: Mapped["User"] = relationship(back_populates="meal_reviews")
    place: Mapped["Place"] = relationship(back_populates="meal_reviews")
    images: Mapped[List[MealReviewImage]] = relationship(
        back_populates="meal_review", cascade="all, delete-orphan"
    )
    swipes: Mapped[List["Swipe"]] = relationship(
        back_populates="meal_review", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_rating_range"),
    )


class Swipe(Base):
    __tablename__ = "swipe"
    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=func.now(), onupdate=func.now()
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    meal_review_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), ForeignKey("meal_review.id"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), nullable=False, index=True
    )
    liked: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # --- Relationships ---
    user: Mapped["User"] = relationship(back_populates="swipes")
    meal_review: Mapped["MealReview"] = relationship(back_populates="swipes")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "meal_review_id",
            "session_id",
            name="unique_user_meal_session_swipe",
        ),
    )
