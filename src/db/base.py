import uuid
from typing import Any, Callable

import sqlalchemy as sa
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)

from src.db.meta import meta


class Base(DeclarativeBase):
    """Base setup for all models including UUID."""

    metadata = meta

    __tablename__: str
    __init__: Callable[..., Any]
    __abstract__ = True
