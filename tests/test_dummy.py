import warnings

import pytest
from trio import TrioDeprecationWarning

from src import __main__

pytestmark = pytest.mark.anyio
warnings.filterwarnings(action="ignore", category=TrioDeprecationWarning)


def test_dummy() -> None:
    """Test dummy function."""
    assert __main__.dummy() == 42
