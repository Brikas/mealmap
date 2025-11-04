from typing import Any, Sequence

from pytest_benchmark.fixture import BenchmarkFixture
from sqlalchemy import MetaData, Row, create_engine

from .conftest import DATABASE_URL

engine = create_engine(DATABASE_URL)
metadata = MetaData()


def read_from_db(table_name: str) -> Sequence[Row[Any]]:
    """Read from specified database table."""
    metadata.reflect(bind=engine)
    table = metadata.tables[table_name]
    with engine.connect() as connection:
        result = connection.execute(table.select())
        return result.fetchall()


def test_db_read(benchmark: BenchmarkFixture, setup_database: None) -> None:
    """Benchmark the database read operation."""
    benchmark(read_from_db, "test_table")
