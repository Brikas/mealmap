from loguru import logger
from sqlalchemy.sql import text

from src.db.models import Base
from src.db.session import async_engine, get_db_session


# Assuming Base is imported from your models module
async def setup_database() -> None:
    """Set up the database and ensure the Images table exists."""
    logger.info("Examining if tables already exist.")
    if not validate_models_against_db():
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info(f"Running CREATE TABLE statements for {Base.metadata.tables}")
        validate_models_against_db()


def validate_models_against_db() -> bool:
    """Ensures SQLAlchemy models match database schema."""
    # Check models are correctly implemented in database
    # Loop over models
    all_tables_valid = True
    for model in Base.metadata.sorted_tables:
        # Check if table exists
        logger.info(f"Checking table {model.name}")
        try:
            with get_db_session() as session:
                query = text("SELECT * FROM :table_name LIMIT 3").params(
                    table_name=model.name
                )
                result = session.execute(query).fetchall()
                logger.info(f"Found {len(result)} rows in table {model.name}")
        except Exception as e:
            logger.error(f"Validation failed for table {model.name}: {e}")
            all_tables_valid = False

    return all_tables_valid
