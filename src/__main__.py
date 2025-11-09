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
        uvicorn.run("src.application:app", host="127.0.0.1", port=8000, reload=True)
    except KeyboardInterrupt:
        logger.info("Cancelled")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        logger.info("Exiting")
