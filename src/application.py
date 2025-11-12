from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from src.api.auth.routes import router as auth_router
from src.api.routes_places import router as places_router
from src.api.routes_users import router as users_router
from src.conf.settings import settings


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
app.include_router(users_router, tags=["users"])
app.include_router(places_router, tags=["places"])
