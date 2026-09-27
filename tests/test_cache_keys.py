"""Cache-key normalization and in-flight gating.

Two problems covered:

* ``/dividend/yield``, ``/price/history`` and ``/dividend/history`` hand-rolled their
  cache logic, so they were the only routes that bypassed both the plan §37.4
  in-flight gate and the plan §37.3 negative cache. An unauthenticated caller
  hammering a dead symbol on those three re-ran the full provider walk every time.
* Cache keys were built inconsistently — five routes upper-cased, two lower-cased,
  eighteen used the raw input — so ``/equity/profile/aapl`` and ``/AAPL`` were
  separate entries, and varying case defeated the negative cache.
"""

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src import main
from src.main import app, _query_key, _symbol_key


# --- key construction ------------------------------------------------------


@pytest.mark.parametrize("raw", ["aapl", "AAPL", " Aapl ", "AaPl"])
def test_symbol_keys_are_case_and_whitespace_insensitive(raw):
    assert _symbol_key("equity_profile", raw) == "equity_profile:AAPL"


def test_symbol_key_with_multiple_parts():
    assert _symbol_key("price_ohlcv", "aapl", "2026-01-01", "2026-02-01") == \
        "price_ohlcv:AAPL:2026-01-01:2026-02-01"


def test_symbol_key_renders_none_parts_as_empty():
    assert _symbol_key("news_company", "AAPL", 50, None, None, None) == \
        "news_company:AAPL:50:::"


def test_query_keys_are_lowercased_and_stripped():
    assert _query_key("equity_search", "  Dividend ") == "equity_search:dividend"
    assert _query_key("equity_search", "DIVIDEND") == _query_key("equity_search", "dividend")


def test_query_key_keeps_later_parts_verbatim():
    assert _query_key("x", "Q", "A", None) == "x:q:A"


def test_every_route_shares_one_key_per_symbol():
    """The bug: two spellings of one ticker produced two provider walks."""
    assert _symbol_key("equity_profile", "aapl") == _symbol_key("equity_profile", "AAPL")


# --- the three routes that bypassed the gate and negative cache ------------


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.parametrize("path,attr,ns", [
    ("/dividend/yield/{t}", "get_dividend_yield", "dividend_yield"),
    ("/price/history/{t}", "get_price_history", "price_history"),
    ("/dividend/history/{t}", "get_dividend_history", "dividend_history"),
])
def test_dividend_routes_are_negative_cached(client, path, attr, ns):
    """A 404 on these routes used to re-run the full provider walk every single time."""
    with patch(f"src.main.{attr}", return_value=None) as fn:
        assert client.get(path.format(t="DEADBEEF")).status_code == 404
        assert client.get(path.format(t="DEADBEEF")).status_code == 404
        assert client.get(path.format(t="DEADBEEF")).status_code == 404
        assert fn.call_count == 1, "negative cache did not engage"


@pytest.mark.parametrize("path,attr", [
    ("/dividend/yield/{t}", "get_dividend_yield"),
    ("/price/history/{t}", "get_price_history"),
    ("/dividend/history/{t}", "get_dividend_history"),
])
def test_dividend_routes_go_through_the_inflight_gate(client, path, attr):
    """plan §37.4 — these three bypassed the gate, so a burst was unbounded."""
    with patch(f"src.main.{attr}", return_value=0.0) as fn:
        with patch.object(main, "_upstream_gate") as gate:
            client.get(path.format(t="AAPL"))
            assert gate.__enter__.called, "provider walk was not gated"


def test_dividend_routes_use_the_shared_cache_path(client):
    """They should no longer hand-roll read/serialize/store."""
    src = __import__("inspect").getsource(main)
    for ns in ("dividend_yield", "price_history", "dividend_history"):
        route_src = src.split(f'_symbol_key("{ns}"')[1].split("def ")[0]
        assert "json.loads" not in route_src
        assert "_cache.set" not in route_src


def test_zero_yield_is_cached_as_a_real_value_not_negative(client):
    """0.0 is a confirmed non-payer, not "no data" — it must not be negative-cached."""
    with patch("src.main.get_dividend_yield", return_value=0.0) as fn:
        r = client.get("/dividend/yield/AAPL")
        assert r.status_code == 200
        assert r.json() == 0.0
        client.get("/dividend/yield/AAPL")
        assert fn.call_count == 1, "0.0 should be served from cache"


# --- no route builds a raw key any more ------------------------------------


def test_no_route_builds_an_unnormalized_cache_key():
    """Guards against a new route reintroducing the inconsistency."""
    import inspect
    src = inspect.getsource(main)
    # Every key now goes through a builder; no inline f-string keys remain.
    offenders = [
        line for line in src.splitlines()
        if line.strip().startswith("f\"") and ":" in line and "key" in line.lower()
    ]
    assert not offenders, f"inline cache keys reintroduced: {offenders}"
