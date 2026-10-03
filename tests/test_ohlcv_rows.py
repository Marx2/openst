"""OHLCV record construction and the crypto profile/quote shape.

Two data bugs covered here:

* ``_safe_float(row.get("open")) or close`` rewrote a legitimate ``0.0`` open/high/low
  as the close price, because ``0.0`` is falsy. The fallback is for *absent* values
  only.
* ``get_crypto_profile`` emitted ``"name": quote.get("name")``, but the quote dict has
  no ``name`` key — so the field was permanently null, reading as "missing data"
  rather than "not available".
"""

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from src import openbb_client as c


def _frame(**row):
    return pd.DataFrame([row], index=pd.to_datetime(["2026-09-25"]))


# --- zero prices must survive ----------------------------------------------


def test_zero_open_is_not_replaced_by_close():
    """0.0 is falsy, so `x or close` silently turned a real 0.0 open into the close."""
    row = c._ohlcv_row("2026-09-25", {"open": 0.0, "high": 2.0, "low": 0.0, "close": 1.5, "volume": 10})
    assert row["open"] == 0.0
    assert row["low"] == 0.0
    assert row["close"] == 1.5


def test_zero_close_is_kept():
    row = c._ohlcv_row("2026-09-25", {"open": 1.0, "high": 1.0, "low": 1.0, "close": 0.0})
    assert row["close"] == 0.0


def test_missing_open_falls_back_to_close():
    """Absent is different from zero — only absent should fall back."""
    row = c._ohlcv_row("2026-09-25", {"open": None, "high": None, "low": None, "close": 4.0})
    assert (row["open"], row["high"], row["low"]) == (4.0, 4.0, 4.0)


def test_nan_open_falls_back_to_close():
    row = c._ohlcv_row("2026-09-25", {"open": float("nan"), "close": 4.0})
    assert row["open"] == 4.0


def test_bar_without_close_is_dropped():
    assert c._ohlcv_row("2026-09-25", {"open": 1.0}) is None


def test_volume_zero_is_preserved():
    row = c._ohlcv_row("2026-09-25", {"close": 1.0, "volume": 0})
    assert row["volume"] == 0


def test_date_is_stringified():
    row = c._ohlcv_row(pd.Timestamp("2026-09-25"), {"close": 1.0})
    assert row["date"] == "2026-09-25"


def test_ohlcv_rows_drops_unusable_bars_but_keeps_the_rest():
    df = pd.DataFrame(
        [{"open": 1.0, "close": 1.0}, {"open": 2.0, "close": float("nan")}, {"open": 0.0, "close": 3.0}],
        index=pd.to_datetime(["2026-09-23", "2026-09-24", "2026-09-25"]),
    )
    rows = c._ohlcv_rows(df)
    assert [r["date"] for r in rows] == ["2026-09-23", "2026-09-25"]
    assert rows[1]["open"] == 0.0


def test_ohlcv_rows_on_empty_frame():
    assert c._ohlcv_rows(pd.DataFrame()) == []


# --- crypto profile --------------------------------------------------------


def test_crypto_profile_omits_keys_the_search_leg_does_not_carry(monkeypatch):
    """No search row means no search keys — omitted, not emitted as null.

    The rule this test used to assert was narrower: that `name` was absent
    because a price bar cannot carry it. §86.3 supersedes that reasoning — the
    search leg does carry a name — so the rule is now the general one. A key the
    provider never sends is left out, because a key that is *always* null
    misleads a consumer into thinking the data is missing rather than
    unavailable.
    """
    monkeypatch.setattr(c, "get_crypto_quote", lambda pair: {
        "symbol": pair, "price": 64000.0, "open": 1.0, "high": 2.0, "low": 0.5,
        "volume": 10, "date": "2026-09-27", "change": 1.0, "change_percent": 0.1,
    })
    monkeypatch.setattr(c, "_crypto_search_row", lambda pair: None)
    profile = c.get_crypto_profile("BTC-USD")
    assert set(profile) == {"symbol", "currency", "price", "date"}
    assert profile["symbol"] == "BTC-USD"
    assert profile["currency"] == "USD"
    assert profile["price"] == 64000.0
    assert profile["date"] == "2026-09-27"


def test_crypto_profile_carries_a_null_the_provider_omitted(monkeypatch):
    """The other half of the rule: a value the provider *did* send as null is kept.

    `WBTCUSD` comes back with a circulating supply and no total supply. Omitting
    the key would claim we never asked; coercing it to 0 would claim the token
    issued nothing. Null is the only honest third option.
    """
    monkeypatch.setattr(c, "get_crypto_quote", lambda pair: {
        "symbol": pair, "price": 64000.0, "date": "2026-09-27",
    })
    monkeypatch.setattr(c, "_crypto_search_row", lambda pair: {
        "symbol": "WBTCUSD", "name": "Wrapped Bitcoin USD", "exchange": "CCC",
        "ico_date": "2019-01-30", "circulating_supply": 125330.0, "total_supply": None,
    })
    profile = c.get_crypto_profile("WBTC-USD")
    assert profile["name"] == "Wrapped Bitcoin USD"
    assert profile["circulating_supply"] == 125330.0
    assert profile["total_supply"] is None


def test_crypto_profile_without_quote_suffix_has_no_currency(monkeypatch):
    monkeypatch.setattr(c, "get_crypto_quote", lambda pair: {"price": 1.0, "date": "d"})
    monkeypatch.setattr(c, "_crypto_search_row", lambda pair: None)
    assert c.get_crypto_profile("BTC")["currency"] is None


def test_crypto_profile_none_when_no_quote(monkeypatch):
    monkeypatch.setattr(c, "get_crypto_quote", lambda pair: None)
    monkeypatch.setattr(c, "_crypto_search_row", lambda pair: None)
    assert c.get_crypto_profile("BTC-USD") is None


# --- crypto quote windowing ------------------------------------------------


@pytest.fixture(autouse=True)
def clear_provider_blocks():
    c._provider_blocked_until.clear()
    yield
    c._provider_blocked_until.clear()


def _obb_returning(df):
    result = MagicMock()
    result.to_df.return_value = df
    return result


@patch("src.openbb_client.obb")
def test_crypto_quote_requests_a_window_not_full_history(mock_obb):
    """Only the last two bars are used; fetching every bar since inception is slow
    and grows without bound."""
    mock_obb.crypto.price.historical.return_value = _obb_returning(
        _frame(open=1.0, high=2.0, low=0.5, close=1.5, volume=10)
    )
    c.get_crypto_quote("BTC-USD")
    mock_obb.crypto.price.historical.assert_called_once()
    kwargs = mock_obb.crypto.price.historical.call_args.kwargs
    assert kwargs["start_date"] and kwargs["end_date"]
    assert kwargs["start_date"] < kwargs["end_date"]


@patch("src.openbb_client.obb")
def test_crypto_quote_uses_a_short_window(mock_obb):
    from datetime import date, timedelta
    mock_obb.crypto.price.historical.return_value = _obb_returning(
        _frame(open=1.0, high=2.0, low=0.5, close=1.5, volume=10)
    )
    c.get_crypto_quote("BTC-USD")
    start = date.fromisoformat(mock_obb.crypto.price.historical.call_args.kwargs["start_date"])
    assert start == date.today() - timedelta(days=c.CRYPTO_QUOTE_WINDOW_DAYS)


@patch("src.openbb_client.obb")
def test_crypto_quote_single_bar_omits_change(mock_obb):
    mock_obb.crypto.price.historical.return_value = _obb_returning(
        _frame(open=1.0, high=1.0, low=1.0, close=1.0, volume=1)
    )
    quote = c.get_crypto_quote("BTC-USD")
    assert "change" not in quote
    assert "change_percent" not in quote


@patch("src.openbb_client.obb")
def test_crypto_quote_change_pct_is_none_on_zero_prev_close(mock_obb):
    df = pd.DataFrame(
        [{"open": 0.0, "high": 1.0, "low": 0.0, "close": 0.0, "volume": 1},
         {"open": 1.0, "high": 2.0, "low": 1.0, "close": 2.0, "volume": 1}],
        index=pd.to_datetime(["2026-09-26", "2026-09-27"]),
    )
    mock_obb.crypto.price.historical.return_value = _obb_returning(df)
    quote = c.get_crypto_quote("BTC-USD")
    assert quote["change_percent"] is None
    assert quote["change"] == 2.0
