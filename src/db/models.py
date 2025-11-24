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
from sqlalchemy.dialects.postgresql import JSONB
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


class MealImage(Base):
    __tablename__ = "meal_image"
    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    meal_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("meal.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_path: Mapped[str] = mapped_column(String, nullable=False)
    # A meal can have multiple images
    meal: Mapped["Meal"] = relationship(back_populates="images")
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


class CuisineType(str, Enum):
    # European
    italian = "italian"
    french = "french"
    spanish = "spanish"
    greek = "greek"
    british = "british"

    # Asian
    chinese = "chinese"
    japanese = "japanese"
    korean = "korean"
    thai = "thai"
    vietnamese = "vietnamese"
    indian = "indian"
    filipino = "filipino"

    # American
    american = "american"
    mexican = "mexican"

    # Middle Eastern & African
    mediterranean = "mediterranean"
    african = "african"

    # Other
    fusion = "fusion"
    cafe = "cafe"
    bakery = "bakery"
    barbecue = "barbecue"
    seafood = "seafood"
    vegetarian_vegan = "vegetarian_vegan"
    other = "other"
    unspecified = "unspecified"


CuisineTypeEnum = SQLEnum(CuisineType, name="cuisine_type_enum")


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
    computed_preferences: Mapped["ComputedUserPreferences"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
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
    cuisine: Mapped[CuisineType] = mapped_column(
        CuisineTypeEnum, nullable=False, server_default=CuisineType.unspecified.value
    )

    test_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # --- Relationships ---
    images: Mapped[List[PlaceImage]] = relationship(
        back_populates="place", cascade="all, delete-orphan"
    )
    meals: Mapped[List["Meal"]] = relationship(
        back_populates="place", cascade="all, delete-orphan"
    )


class Meal(Base):
    __tablename__ = "meal"
    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=func.now(), onupdate=func.now()
    )

    place_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("place.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    test_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # --- Relationships ---
    place: Mapped["Place"] = relationship(back_populates="meals")
    images: Mapped[List[MealImage]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )
    meal_reviews: Mapped[List["MealReview"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )
    swipes: Mapped[List["Swipe"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )
    computed_features: Mapped["ComputedMealFeatures"] = relationship(
        back_populates="meal", cascade="all, delete-orphan", uselist=False
    )


class TriState(str, Enum):
    yes = "yes"
    no = "no"
    unspecified = "unspecified"


TriStateEnum = SQLEnum(TriState, name="tri_state_enum")


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
    meal_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), ForeignKey("meal.id", ondelete="CASCADE"), nullable=False
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    waiting_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Enums
    is_vegan: Mapped[TriState] = mapped_column(
        TriStateEnum, nullable=False, server_default=TriState.unspecified.value
    )
    is_halal: Mapped[TriState] = mapped_column(
        TriStateEnum, nullable=False, server_default=TriState.unspecified.value
    )
    is_vegetarian: Mapped[TriState] = mapped_column(
        TriStateEnum, nullable=False, server_default=TriState.unspecified.value
    )
    is_spicy: Mapped[TriState] = mapped_column(
        TriStateEnum, nullable=False, server_default=TriState.unspecified.value
    )
    is_gluten_free: Mapped[TriState] = mapped_column(
        TriStateEnum, nullable=False, server_default=TriState.unspecified.value
    )
    is_dairy_free: Mapped[TriState] = mapped_column(
        TriStateEnum, nullable=False, server_default=TriState.unspecified.value
    )
    is_nut_free: Mapped[TriState] = mapped_column(
        TriStateEnum, nullable=False, server_default=TriState.unspecified.value
    )

    test_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # --- Relationships ---
    user: Mapped["User"] = relationship(back_populates="meal_reviews")
    meal: Mapped["Meal"] = relationship(back_populates="meal_reviews")
    images: Mapped[List[MealReviewImage]] = relationship(
        back_populates="meal_review", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_rating_range"),
        CheckConstraint(
            "waiting_time_minutes >= 0", name="check_waiting_time_non_negative"
        ),
        CheckConstraint("price >= 0", name="check_price_non_negative"),
        CheckConstraint("price <= 10000000", name="check_price_max_value"),
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
        sa.UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    meal_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), ForeignKey("meal.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), nullable=False, index=True
    )
    liked: Mapped[bool] = mapped_column(Boolean, nullable=False)

    test_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # --- Relationships ---
    user: Mapped["User"] = relationship(back_populates="swipes")
    meal: Mapped["Meal"] = relationship(back_populates="swipes")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "meal_id",
            "session_id",
            name="unique_user_meal_session_swipe",
        ),
    )


class ComputedMealFeatures(Base):
    __tablename__ = "computed_meal_features"
    meal_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("meal.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_vector: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    cuisine_vector: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    avg_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_wait_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    meal: Mapped["Meal"] = relationship(back_populates="computed_features")


class ComputedUserPreferences(Base):
    __tablename__ = "computed_user_preferences"
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_prefs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    cuisine_prefs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    price_bin_prefs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    wait_bin_prefs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    user: Mapped["User"] = relationship(back_populates="computed_preferences")
