import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.common_schemas import BackendImageResponse
from src.api.dependencies import get_current_user
from src.api.response_schemas import MealResponse, PlaceResponse
from src.db.models import (
    Meal,
    MealReview,
    Place,
    User,
    UserMealBookmarks,
    UserPlaceBookmarks,
)
from src.db.session import get_async_db_session
from src.services.response_builder import build_meal_response, build_place_response
from src.utils.pagination import Page, PaginationInput, paginate_query

router = APIRouter()


class BookmarkCreationResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime


class MealBookmarkResponse(BaseModel):
    meal_id: uuid.UUID
    place_id: uuid.UUID
    created_at: datetime
    meal: Optional[MealResponse] = None
    place: Optional[PlaceResponse] = None


class PlaceBookmarkResponse(BaseModel):
    place_id: uuid.UUID
    created_at: datetime
    place: Optional[PlaceResponse] = None
    bookmarked_meal_count: Optional[int] = None


@router.post(
    "/users/me/bookmarks/meals/{meal_id}",
    response_model=BookmarkCreationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_meal_bookmark(
    meal_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_async_db_session),
) -> BookmarkCreationResponse:
    """
    Bookmark a meal for the current user.
    """
    # Check if meal exists
    meal = await db.get(Meal, meal_id)
    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found"
        )

    # Check if already bookmarked
    existing_bookmark = await db.get(UserMealBookmarks, (current_user.id, meal_id))
    if existing_bookmark:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bookmark already exists"
        )

    bookmark = UserMealBookmarks(user_id=current_user.id, meal_id=meal_id)
    db.add(bookmark)
    await db.commit()
    await db.refresh(bookmark)

    return BookmarkCreationResponse(id=bookmark.meal_id, created_at=bookmark.created_at)


@router.get("/users/me/bookmarks/meals", response_model=Page[MealBookmarkResponse])
async def list_meal_bookmarks(
    current_user: Annotated[User, Depends(get_current_user)],
    place_id: Optional[uuid.UUID] = Query(None),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None, alias="long"),
    expand: Optional[str] = Query(
        None, description="Comma-separated list of resources to expand: 'meal', 'place'"
    ),
    pagination: PaginationInput = Depends(),
    db: AsyncSession = Depends(get_async_db_session),
) -> Page[MealBookmarkResponse]:
    """
    List all meal bookmarks for the current user.
    """
    expand_list = [e.strip() for e in expand.split(",")] if expand else []

    query = (
        select(UserMealBookmarks)
        .where(UserMealBookmarks.user_id == current_user.id)
        .order_by(UserMealBookmarks.created_at.desc())
    )

    # Always load meal to get place_id
    meal_load = selectinload(UserMealBookmarks.meal)

    if "meal" in expand_list:
        meal_load = meal_load.options(
            selectinload(Meal.meal_reviews).selectinload(MealReview.images),
            selectinload(Meal.images),
            selectinload(Meal.place),
        )

    if "place" in expand_list:
        meal_load = meal_load.options(
            selectinload(Meal.place).options(
                selectinload(Place.images),
                selectinload(Place.meals).selectinload(Meal.meal_reviews),
            )
        )

    query = query.options(meal_load)

    if place_id:
        query = query.join(UserMealBookmarks.meal).where(Meal.place_id == place_id)

    page_obj = await paginate_query(
        query, db, page=pagination.page, page_size=pagination.page_size
    )

    results = []
    now = datetime.now(timezone.utc)

    for bookmark in page_obj.results:
        meal = bookmark.meal

        meal_response = None
        place_response = None

        if "meal" in expand_list:
            meal_response = build_meal_response(meal, lat, lng, now)

        if "place" in expand_list:
            place_response = build_place_response(meal.place, lat, lng)

        results.append(
            MealBookmarkResponse(
                meal_id=meal.id,
                place_id=meal.place_id,
                meal=meal_response,
                place=place_response,
                created_at=bookmark.created_at,
            )
        )

    return Page[MealBookmarkResponse](
        results=results,
        total_items=page_obj.total_items,
        start_index=page_obj.start_index,
        end_index=page_obj.end_index,
        total_pages=page_obj.total_pages,
        current_page=page_obj.current_page,
        current_page_size=page_obj.current_page_size,
    )


@router.delete(
    "/users/me/bookmarks/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_meal_bookmark(
    meal_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """
    Delete a bookmark.
    """
    bookmark = await db.get(UserMealBookmarks, (current_user.id, meal_id))
    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found"
        )

    await db.delete(bookmark)
    await db.commit()


# --- Place Bookmarks ---


@router.post(
    "/users/me/bookmarks/places/{place_id}",
    response_model=BookmarkCreationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_place_bookmark(
    place_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_async_db_session),
) -> BookmarkCreationResponse:
    """
    Bookmark a place for the current user.
    """
    # Check if place exists
    place = await db.get(Place, place_id)
    if not place:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Place not found"
        )

    # Check if already bookmarked
    existing_bookmark = await db.get(UserPlaceBookmarks, (current_user.id, place_id))
    if existing_bookmark:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bookmark already exists"
        )

    bookmark = UserPlaceBookmarks(user_id=current_user.id, place_id=place_id)
    db.add(bookmark)
    await db.commit()
    await db.refresh(bookmark)

    return BookmarkCreationResponse(
        id=bookmark.place_id, created_at=bookmark.created_at
    )


@router.get("/users/me/bookmarks/places", response_model=Page[PlaceBookmarkResponse])
async def list_place_bookmarks(
    current_user: Annotated[User, Depends(get_current_user)],
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None, alias="long"),
    expand: Optional[str] = Query(
        None, description="Comma-separated list of resources to expand: 'place'"
    ),
    pagination: PaginationInput = Depends(),
    db: AsyncSession = Depends(get_async_db_session),
) -> Page[PlaceBookmarkResponse]:
    """
    List all place bookmarks for the current user.
    """
    expand_list = [e.strip() for e in expand.split(",")] if expand else []

    query = (
        select(UserPlaceBookmarks)
        .where(UserPlaceBookmarks.user_id == current_user.id)
        .order_by(UserPlaceBookmarks.created_at.desc())
    )

    if "place" in expand_list:
        query = query.options(
            selectinload(UserPlaceBookmarks.place).options(
                selectinload(Place.images),
                selectinload(Place.meals).selectinload(Meal.meal_reviews),
            )
        )
    else:
        pass

    page_obj = await paginate_query(
        query, db, page=pagination.page, page_size=pagination.page_size
    )

    results = []
    for bookmark in page_obj.results:
        place_response = None
        bookmarked_meals_count = None

        if "place" in expand_list:
            place = bookmark.place
            place_response = build_place_response(place, lat, lng)

            # Count bookmarked meals in this place
            bookmarked_meals_count = await db.scalar(
                select(func.count(UserMealBookmarks.meal_id))
                .join(Meal, UserMealBookmarks.meal_id == Meal.id)
                .where(
                    UserMealBookmarks.user_id == current_user.id,
                    Meal.place_id == place.id,
                )
            )

        results.append(
            PlaceBookmarkResponse(
                place_id=bookmark.place_id,
                place=place_response,
                bookmarked_meal_count=bookmarked_meals_count,
                created_at=bookmark.created_at,
            )
        )

    return Page[PlaceBookmarkResponse](
        results=results,
        total_items=page_obj.total_items,
        start_index=page_obj.start_index,
        end_index=page_obj.end_index,
        total_pages=page_obj.total_pages,
        current_page=page_obj.current_page,
        current_page_size=page_obj.current_page_size,
    )


@router.delete(
    "/users/me/bookmarks/places/{place_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_place_bookmark(
    place_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """
    Delete a place bookmark.
    """
    bookmark = await db.get(UserPlaceBookmarks, (current_user.id, place_id))
    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found"
        )

    await db.delete(bookmark)
    await db.commit()
