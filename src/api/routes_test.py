from typing import Any, Dict

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_async_db_session

router = APIRouter()


@router.get("/test")
async def hello_world() -> Dict[str, str]:
    """
    Simple hello world route to test connection.
    """
    return {"message": "Hello World"}


@router.get("/test/db")
async def test_db_connection(
    db: AsyncSession = Depends(get_async_db_session),
) -> Dict[str, Any]:
    """
    Test database connection.

    Returns a success message if connection works,
    or an error message if it fails.
    """
    try:
        # Execute a simple query to check connection
        await db.execute(text("SELECT 1"))
        return {"status": "success", "message": "Database connection is working"}
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return {
            "status": "error",
            "message": "Database connection failed",
            "details": str(e),
        }
