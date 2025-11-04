import time

from pytest_benchmark.fixture import BenchmarkFixture


def example_function() -> None:
    """This is an example function."""
    time.sleep(0.1)  # This is just an example, replace with your actual function


def test_example_function(benchmark: BenchmarkFixture) -> None:
    """This is a test function for example_function."""
    result = benchmark(example_function)
