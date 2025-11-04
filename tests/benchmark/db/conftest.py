import os

import psycopg2
import pytest

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "postgres")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)


def create_database_if_not_exists() -> None:
    """Create the database if it does not exist."""
    connection = psycopg2.connect(DATABASE_URL)
    connection.autocommit = True
    cursor = connection.cursor()
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
    exists = cursor.fetchone()
    if not exists:
        cursor.execute(f"CREATE DATABASE {DB_NAME}")

    cursor.close()
    connection.close()


@pytest.fixture(scope="module")
def setup_database() -> None:
    """Setup the database for testing."""
    # Create the database if it doesn't exist
    create_database_if_not_exists()

    # Connect to your database
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()
    # Create the table if it does not exist
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS test_table (
            id SERIAL PRIMARY KEY,
            data TEXT
        )
    """
    )
    connection.commit()

    # Cleanup code can be added here if necessary
    cursor.close()
    connection.close()
