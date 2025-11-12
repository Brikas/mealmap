from typing import Annotated, Generic, List, Optional, Type, TypeVar

from fastapi import Depends
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import Base

MAX_RESULTS_PER_PAGE = 50
T = TypeVar("T")


class PaginationInput(BaseModel):
    """Model passed in the request to validate pagination input."""

    page: int = Field(
        default=1, ge=1, description="Requested page number. Starts at 1."
    )
    page_size: int = Field(
        default=10,
        ge=1,
        le=MAX_RESULTS_PER_PAGE,
        description="Requested number of items per page",
    )


class Page(BaseModel, Generic[T]):
    results: List[T] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    start_index: int = Field(default=0, ge=0, description="Starting item index")
    end_index: int = Field(default=0, ge=0, description="Ending item index")
    total_pages: int = Field(default=0, ge=0)
    current_page: int = Field(
        default=1, ge=0, description="Page number (could differ from request)"
    )
    current_page_size: int = Field(
        default=0,
        ge=0,
        description="Number of items per page (could differ from request)",
    )


async def paginate_list(
    items: List[T],
    page: int = 1,
    page_size: int = 20,
) -> Page[T]:
    """
    Paginate a list of items.

    This is useful for paginating in-memory lists when database queries are not involved.
    """

    total_items = len(items)
    total_pages = (total_items + page_size - 1) // page_size if page_size else 1
    current_page = min(page, total_pages) if total_pages > 0 else 1
    offset = (current_page - 1) * page_size

    # If requested page exceeds total_pages, return empty results
    if page > total_pages:
        return Page(
            results=[],
            total_items=total_items,
            start_index=0,
            end_index=0,
            total_pages=total_pages,
            current_page=page,
            current_page_size=0,
        )

    paginated_items = items[offset : offset + page_size]

    start_index = offset + 1 if total_items > 0 else 0
    end_index = offset + len(paginated_items)
    return Page(
        results=paginated_items,
        total_items=total_items,
        start_index=start_index,
        end_index=end_index,
        total_pages=total_pages,
        current_page=current_page,
        current_page_size=len(paginated_items),
    )


async def paginate_query(
    # TODO Investigate, how can I have type hinting on the returned results.
    query,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    model: type | None = None,  # Optional model for conversion
) -> Page:
    """
    Paginate a SQLAlchemy query using AsyncSession.

    Optionally convert ORM results to a Pydantic model.
    """

    count_query = select(func.count()).select_from(query.subquery())
    total_items = (await db.execute(count_query)).scalar_one()
    total_pages = (total_items + page_size - 1) // page_size if page_size else 1
    current_page = min(page, total_pages) if total_pages > 0 else 1
    offset = (current_page - 1) * page_size

    # If requested page exceeds total_pages, return empty results
    if page > total_pages:
        return Page(
            results=[],
            total_items=total_items,
            start_index=0,
            end_index=0,
            total_pages=total_pages,
            current_page=page,
            current_page_size=0,
        )

    result = await db.execute(query.offset(offset).limit(page_size))
    results = list(result.scalars().all())

    # The model is used to convert ORM results to Pydantic models if provided
    # This is useful for returning a consistent response format
    # and for validation purposes.
    # This can be error prone, if it gets annoying, fuck it.
    if model is not None:
        validated_items = []
        for item in results:
            try:
                if hasattr(model, "model_validate"):
                    validated_items.append(model.model_validate(item))
                elif hasattr(model, "from_orm"):
                    validated_items.append(model.from_orm(item))
                else:
                    validated_items.append(model(**item.__dict__))
            except Exception as e:
                logger.error(f"Validation failed for item: {item}\nError: {e}")
                raise
        results = validated_items

    start_index = offset + 1 if total_items > 0 else 0
    end_index = offset + len(results)
    return Page(
        results=results,
        total_items=total_items,
        start_index=start_index,
        end_index=end_index,
        total_pages=total_pages,
        current_page=current_page,
        current_page_size=len(results),
    )
