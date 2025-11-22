import asyncio

import uvicorn
from loguru import logger

IGNORE_DB = False


async def main() -> None:
    """Entrypoint of the application."""
    return
    # try:
    #     await setup.setup_database()
    # except Exception as e:
    #     if not IGNORE_DB:
    #         logger.error(f"Database setup failed: {e}")
    #         return


def dummy() -> int:
    """Return 42."""
    return 42


if __name__ == "__main__":
    logger.info("Starting")
    try:
        asyncio.run(main())
        import os

        port = int(os.getenv("PORT", 8000))
        app_env = os.getenv("APP_ENV", "dev")
        should_reload = app_env.lower() == "dev"
        uvicorn.run(
            "src.application:app",
            host="0.0.0.0",  # noqa: S104
            port=port,
            reload=should_reload,
        )
    except KeyboardInterrupt:
        logger.info("Cancelled")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        logger.info("Exiting")
