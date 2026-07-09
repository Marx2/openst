import json
import logging
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import src.cache as cache_module


@pytest.fixture(autouse=True)
def flush_redis():
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
def client():
    from src.main import app
    return TestClient(app)


@patch("src.main.get_dividend_yield", return_value=2.45)
def test_yield_miss_fetches_and_returns(mock_fn, client):
    r = client.get("/dividend/yield/AAPL")
    assert r.status_code == 200
    assert r.json() == 2.45
    mock_fn.assert_called_once_with("AAPL")


@patch("src.main.get_dividend_yield", return_value=2.45)
def test_yield_hit_returns_cached(mock_fn, client):
    client.get("/dividend/yield/AAPL")
    client.get("/dividend/yield/AAPL")
    assert mock_fn.call_count == 1


@patch("src.main.get_dividend_yield", return_value=None)
def test_yield_not_found_returns_404(mock_fn, client):
    r = client.get("/dividend/yield/UNKNOWN")
    assert r.status_code == 404


@patch("src.main.get_dividend_history", return_value=[{"date": "2024-03-15", "amount": "0.2500"}])
def test_history_miss_fetches_and_returns(mock_fn, client):
    r = client.get("/dividend/history/AAPL")
    assert r.status_code == 200
    assert r.json() == [{"date": "2024-03-15", "amount": "0.2500"}]
    mock_fn.assert_called_once_with("AAPL")


@patch("src.main.get_dividend_history", return_value=[{"date": "2024-03-15", "amount": "0.2500"}])
def test_history_hit_returns_cached(mock_fn, client):
    client.get("/dividend/history/AAPL")
    client.get("/dividend/history/AAPL")
    assert mock_fn.call_count == 1


@patch("src.main.get_dividend_history", return_value=None)
def test_history_not_found_returns_404(mock_fn, client):
    r = client.get("/dividend/history/UNKNOWN")
    assert r.status_code == 404


@patch("src.main.get_dividend_yield", return_value=2.45)
def test_middleware_logs_response(mock_fn, client, caplog):
    with caplog.at_level(logging.INFO, logger="uvicorn.access"):
        r = client.get("/dividend/yield/AAPL")
    assert r.status_code == 200
    assert any("2.45" in m and "/dividend/yield/AAPL" in m for m in caplog.messages)
