import os
import pytest
import redis
from cache import RedisCache


@pytest.fixture
def r():
    client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        password=os.environ.get("REDIS_PASSWORD") or None,
        db=int(os.environ.get("REDIS_DB", 0)),
        decode_responses=True,
    )
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture
def cache(r):
    return RedisCache(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        password=os.environ.get("REDIS_PASSWORD") or None,
        db=int(os.environ.get("REDIS_DB", 0)),
    )


def test_miss_returns_none(cache):
    assert cache.get("nonexistent") is None


def test_set_then_get(cache):
    cache.set("k", "hello")
    assert cache.get("k") == "hello"


def test_expired_returns_none(cache, r):
    cache.set("k", "hello", ttl=1)
    r.expire("k", -1)
    assert cache.get("k") is None


def test_set_overwrites(cache):
    cache.set("k", "first")
    cache.set("k", "second")
    assert cache.get("k") == "second"


def test_default_ttl_applied(cache, r):
    cache.set("k", "val")
    ttl = r.ttl("k")
    assert 86390 <= ttl <= 86400
