"""Shared test fixtures for the openst test suite (D79 19.3)."""

import os
from pathlib import Path

import pytest

import src.cache as cache_module

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def flush_redis():
    """Give every test an empty cache.

    Autouse for the whole suite, not just the endpoint tests: the cache is shared
    module state, and a key left behind by one file silently satisfies another
    file's request — which looks exactly like a broken cache. This previously lived
    only in test_main.py, so any new test file silently inherited stale keys.
    """
    c = cache_module.RedisCache(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        password=os.environ.get("REDIS_PASSWORD") or None,
        db=int(os.environ.get("REDIS_DB", 0)),
    )
    c._client.flushdb()
    yield
    c._client.flushdb()


@pytest.fixture
def read_fixture():
    """Return a function reading a captured fixture page."""

    def _read(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    return _read