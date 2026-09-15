"""Shared test fixtures for the openst test suite (D79 19.3)."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def read_fixture():
    """Return a function reading a captured fixture page."""

    def _read(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    return _read