from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests
from pytest_benchmark.fixture import BenchmarkFixture

API_ENDPOINT = "https://jsonplaceholder.typicode.com/posts"


def fetch_api_data(endpoint: str) -> dict[str, Any]:
    """Fetch data from API."""
    response = requests.get(endpoint, timeout=5)
    response.raise_for_status()
    return response.json()


def test_api_throughput(benchmark: BenchmarkFixture) -> None:
    """Benchmark API throughput."""

    def multiple_requests() -> None:
        with ThreadPoolExecutor(max_workers=50) as executor:
            executor.map(fetch_api_data, [API_ENDPOINT] * 10)

    benchmark(multiple_requests)
