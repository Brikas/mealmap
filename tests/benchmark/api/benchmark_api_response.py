from typing import Any, Dict

import requests
from pytest_benchmark.fixture import BenchmarkFixture

API_ENDPOINT = "https://jsonplaceholder.typicode.com/posts"


def fetch_api_data(endpoint: str) -> Dict[str, Any]:
    """Fetch data from API."""
    response = requests.get(endpoint, timeout=5)
    response.raise_for_status()
    return response.json()


def test_api_response_time(benchmark: BenchmarkFixture) -> None:
    """Benchmark API response time."""
    benchmark(fetch_api_data, API_ENDPOINT)
