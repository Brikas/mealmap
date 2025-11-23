from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from src.api.auth.routes import router as auth_router
from src.api.routes_admin import router as admin_router
from src.api.routes_meals import router as meals_router
from src.api.routes_places import router as places_router
from src.api.routes_reviews import router as reviews_router
from src.api.routes_swipes import router as swipes_router
from src.api.routes_test import router as test_router
from src.api.routes_users import router as users_router
from src.conf.settings import settings

## General TODO's
# TODO When places are deleted with direct db connection AND/OR with cascade,
#   ensure images are also deleted from S3.


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    logger.info("Starting application...")

    # try:
    #     if not settings.ignore_db:
    #         await setup.setup_database()
    #     logger.info("Database initialized")
    # except Exception as e:
    #     logger.error(f"Database setup failed: {e}")
    #     if not settings.ignore_db:
    #         raise e  # Crash the app if DB setup is required

    yield

    logger.info("Shutting down application...")


# ------------------ FastAPI Application ------------------

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(admin_router, tags=["admin"])
app.include_router(users_router, tags=["users"])
app.include_router(places_router, tags=["places"])
app.include_router(meals_router, tags=["meals"])
app.include_router(reviews_router, tags=["reviews"])
app.include_router(test_router, tags=["test"])
app.include_router(swipes_router, tags=["swipes"])
