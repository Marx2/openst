"""Cache degradation and readiness.

Regression cover for an availability bug: a Redis outage returned HTTP 500 on
every data endpoint, because ``ConnectionError`` escaped ``RedisCache.get`` with
no handler. ``/health`` kept reporting ok throughout, so the pod looked healthy
to Kubernetes while serving nothing.
"""

import pytest
import redis
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.cache import RedisCache
from src.main import app


@pytest.fixture
def cache():
    c = RedisCache.__new__(RedisCache)
    c._client = MagicMock()
    return c


def _boom(exc=redis.ConnectionError("redis down")):
    return exc


# --- degradation -----------------------------------------------------------


def test_get_returns_none_when_redis_is_down(cache):
    """A miss, not an exception — the endpoint must still be able to serve."""
    cache._client.get.side_effect = _boom()
    assert cache.get("k") is None


def test_set_swallows_the_error(cache):
    cache._client.setex.side_effect = _boom()
    cache.set("k", "v")  # must not raise


@pytest.mark.parametrize("exc", [
    redis.ConnectionError("down"),
    redis.TimeoutError("slow"),
    redis.RedisError("generic"),
])
def test_every_redis_error_is_contained(cache, exc):
    cache._client.get.side_effect = exc
    assert cache.get("k") is None


def test_successful_get_returns_the_value(cache):
    cache._client.get.return_value = "cached"
    assert cache.get("k") == "cached"


def test_successful_set_writes(cache):
    cache.set("k", "v", ttl=60)
    cache._client.setex.assert_called_once_with("k", 60, "v")


# --- ping ------------------------------------------------------------------


def test_ping_true_when_reachable(cache):
    cache._client.ping.return_value = True
    assert cache.ping() is True


def test_ping_false_when_unreachable(cache):
    cache._client.ping.side_effect = _boom()
    assert cache.ping() is False


# --- the outage that mattered ---------------------------------------------


def _dead_cache() -> RedisCache:
    """A real RedisCache pointed at a closed port.

    Deliberately not a Mock: the fix lives inside RedisCache.get/set, so mocking the
    cache would test the mock's behaviour instead of the code that was broken.
    """
    return RedisCache(host="127.0.0.1", port=6399, password=None, db=0)


def test_the_dead_cache_really_is_unreachable():
    assert _dead_cache().ping() is False


def test_data_endpoints_survive_a_redis_outage():
    """Previously 500 on every route. A dead cache must degrade to slow, not down."""
    with patch("src.main._cache", _dead_cache()), \
         patch("src.main.get_quote", return_value={"symbol": "AAPL", "price": 1.0}):
        r = TestClient(app).get("/equity/quote/AAPL")
        assert r.status_code == 200, r.text
        assert r.json()["symbol"] == "AAPL"


def test_negative_cache_write_survives_a_redis_outage():
    """The sentinel write is a cache write too, and 404s must still be raised."""
    with patch("src.main._cache", _dead_cache()), \
         patch("src.main.get_quote", return_value=None):
        r = TestClient(app).get("/equity/quote/AAPL")
        assert r.status_code == 404


def test_health_stays_ok_while_redis_is_down():
    """Liveness must not depend on Redis, or k8s restarts the pod during a blip."""
    with patch("src.main._cache", _dead_cache()):
        r = TestClient(app).get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_ready_reports_503_when_redis_is_unreachable():
    with patch("src.main._cache", _dead_cache()):
        r = TestClient(app).get("/ready")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "degraded"
        assert body["redis"] == "unreachable"


def test_ready_reports_200_when_redis_is_reachable():
    with patch("src.main._cache") as c:
        c.ping.return_value = True
        r = TestClient(app).get("/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"
        assert body["redis"] == "ok"


def test_ready_reports_database_presence(monkeypatch):
    # No `with TestClient(...)`: entering the context runs lifespan, which would try
    # to migrate against whatever DATABASE_URL is set.
    with patch("src.main._cache") as c:
        c.ping.return_value = True
        monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
        assert TestClient(app).get("/ready").json()["database"] == "configured"
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert TestClient(app).get("/ready").json()["database"] == "unset"
