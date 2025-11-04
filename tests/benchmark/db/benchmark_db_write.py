from typing import Any, Dict

from pytest_benchmark.fixture import BenchmarkFixture
from sqlalchemy import MetaData, create_engine

from .conftest import DATABASE_URL

engine = create_engine(DATABASE_URL)
metadata = MetaData()


def write_to_db(table_name: str, data: Dict[str, Any]) -> None:
    """Write to the specified database table."""
    metadata.reflect(bind=engine)
    table = metadata.tables[table_name]
    with engine.connect() as connection:
        connection.execute(table.insert(), data)


def test_db_write(benchmark: BenchmarkFixture, setup_database: None) -> None:
    """Benchmark the database write operation."""
    data = [{"id": i, "name": f"name_{i}"} for i in range(100)]
    benchmark(write_to_db, "test_table", data)
