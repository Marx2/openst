import json
import logging
import types
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src import openbb_client
from src.openbb_client import (
    get_calendar,
    get_dividend_history,
    get_dividend_yield,
    get_filings,
    get_fundamentals,
    get_insider_trading,
    get_institutional_ownership,
    get_mda,
    get_metrics,
    get_ohlcv_history,
    get_price_history,
    get_profile,
    get_projections,
    get_quote,
    search_equities,
)
import src.openbb_client as openbb_client


@pytest.fixture(autouse=True)
def clear_caches():
    openbb_client._pays_dividend.clear()
    openbb_client._provider_blocked_until.clear()
    yield
    openbb_client._pays_dividend.clear()
    openbb_client._provider_blocked_until.clear()


def _metrics_df(dividend_yield: float) -> pd.DataFrame:
    return pd.DataFrame([{"dividend_yield": dividend_yield}])


def _dividends_df() -> pd.DataFrame:
    df = pd.DataFrame(
        [{"amount": 0.25}, {"amount": 0.30}],
        index=pd.to_datetime(["2024-03-15", "2024-06-15"]),
    )
    df.index.name = "ex_dividend_date"
    return df


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


def test_is_rate_limited_matches_402():
    assert openbb_client._is_rate_limited("HTTP 402 payment required")


def test_is_rate_limited_matches_rate_limit():
    assert openbb_client._is_rate_limited("Rate limit exceeded")


def test_is_rate_limited_matches_too_many_requests():
    assert openbb_client._is_rate_limited("Too Many Requests")


def test_is_rate_limited_matches_premium():
    assert openbb_client._is_rate_limited("This is a premium feature")


def test_is_rate_limited_matches_quota():
    assert openbb_client._is_rate_limited("quota exhausted")


def test_is_rate_limited_no_match():
    assert not openbb_client._is_rate_limited("connection timeout")


def test_is_invalid_ticker_matches_not_found_for_symbol():
    assert openbb_client._is_invalid_ticker("not found for symbol MPW")


def test_is_invalid_ticker_matches_results_not_found():
    assert openbb_client._is_invalid_ticker("Results not found")


def test_is_invalid_ticker_matches_no_timezone_found():
    assert openbb_client._is_invalid_ticker("no timezone found for ticker")


def test_is_invalid_ticker_matches_possibly_delisted():
    assert openbb_client._is_invalid_ticker("possibly delisted")


def test_is_invalid_ticker_matches_no_data_found():
    assert openbb_client._is_invalid_ticker("No data found")


def test_is_invalid_ticker_no_match():
    assert not openbb_client._is_invalid_ticker("connection refused")


# ---------------------------------------------------------------------------
# get_dividend_yield — existing tests
# ---------------------------------------------------------------------------


@patch("src.openbb_client.obb")
def test_get_dividend_yield_returns_decimal_string(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _metrics_df(2.456789)
    mock_obb.equity.fundamental.metrics.return_value = mock_result

    result = get_dividend_yield("AAPL")

    assert result == 2.46
    mock_obb.equity.fundamental.metrics.assert_called_once_with("AAPL", provider="yfinance")


@patch("src.openbb_client.obb")
def test_get_dividend_yield_fallback_to_fmp(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _metrics_df(1.5)
    mock_obb.equity.fundamental.metrics.side_effect = [Exception("yfinance down"), mock_ok]

    result = get_dividend_yield("AAPL")

    assert result == 1.50
    assert mock_obb.equity.fundamental.metrics.call_count == 2


@patch("src.openbb_client.obb")
def test_get_dividend_yield_fallback_logs_warning(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _metrics_df(1.5)
    mock_obb.equity.fundamental.metrics.side_effect = [Exception("yfinance down"), mock_ok]

    with patch("src.openbb_client.logger") as mock_logger:
        get_dividend_yield("AAPL")
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "yfinance" in str(call_args)
        assert "AAPL" in str(call_args)


@patch("src.openbb_client.obb")
def test_get_dividend_yield_all_providers_fail_returns_none(mock_obb):
    mock_obb.equity.fundamental.metrics.side_effect = Exception("fail")
    # dividends also fail → can't confirm non-payer → None
    mock_obb.equity.fundamental.dividends.side_effect = Exception("fail")
    assert get_dividend_yield("AAPL") is None


@patch("src.openbb_client.obb")
def test_get_dividend_yield_non_payer_returns_zero(mock_obb):
    mock_obb.equity.fundamental.metrics.side_effect = Exception("fail")
    empty = MagicMock()
    empty.to_df.return_value = pd.DataFrame()
    mock_obb.equity.fundamental.dividends.return_value = empty
    assert get_dividend_yield("AAPL") == 0.0


@patch("src.openbb_client.obb")
def test_get_dividend_yield_missing_column_returns_zero(mock_obb):
    # yfinance returns df without dividend_yield column (e.g. SNPS)
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame([{"market_cap": 1e11}])
    mock_obb.equity.fundamental.metrics.return_value = mock_result
    assert get_dividend_yield("SNPS") == 0.0


@patch("src.openbb_client.obb")
def test_get_dividend_yield_non_payer_caches_result(mock_obb):
    mock_obb.equity.fundamental.metrics.side_effect = Exception("fail")
    empty = MagicMock()
    empty.to_df.return_value = pd.DataFrame()
    mock_obb.equity.fundamental.dividends.return_value = empty

    get_dividend_yield("AAPL")
    get_dividend_yield("AAPL")
    # all dividend providers tried on first call, 0 on second (cached)
    assert mock_obb.equity.fundamental.dividends.call_count == len(
        openbb_client.DIVIDEND_PROVIDERS
    )


@patch("src.openbb_client.obb")
def test_get_dividend_yield_empty_df_returns_none(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame()
    mock_obb.equity.fundamental.metrics.return_value = mock_result
    assert get_dividend_yield("AAPL") is None


# ---------------------------------------------------------------------------
# get_dividend_yield — rate-limit / invalid ticker
# ---------------------------------------------------------------------------


@patch("src.openbb_client.obb")
def test_get_dividend_yield_rate_limit_blocks_provider_tries_next(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _metrics_df(1.5)
    mock_obb.equity.fundamental.metrics.side_effect = [
        Exception("402 payment required"),
        mock_ok,
    ]

    result = get_dividend_yield("AAPL")

    assert result == 1.50
    assert "yfinance" in openbb_client._provider_blocked_until
    assert mock_obb.equity.fundamental.metrics.call_count == 2


@patch("src.openbb_client.obb")
def test_get_dividend_yield_invalid_ticker_returns_zero_no_further_providers(mock_obb):
    mock_obb.equity.fundamental.metrics.side_effect = Exception("possibly delisted")

    result = get_dividend_yield("MPW")

    assert result == 0.0
    assert openbb_client._pays_dividend.get("MPW") is False
    # only yfinance tried — loop exited immediately
    assert mock_obb.equity.fundamental.metrics.call_count == 1


@patch("src.openbb_client.obb")
def test_get_dividend_yield_cached_false_skips_all_providers(mock_obb):
    openbb_client._pays_dividend["MPW"] = False

    result = get_dividend_yield("MPW")

    assert result == 0.0
    mock_obb.equity.fundamental.metrics.assert_not_called()


@patch("src.openbb_client.obb")
def test_get_dividend_yield_blocked_provider_skipped(mock_obb):
    openbb_client._provider_blocked_until["yfinance"] = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _metrics_df(2.0)
    mock_obb.equity.fundamental.metrics.return_value = mock_ok

    result = get_dividend_yield("AAPL")

    assert result == 2.0
    # first call must be fmp, not yfinance
    first_call = mock_obb.equity.fundamental.metrics.call_args_list[0]
    assert first_call[1]["provider"] == "fmp"


def _price_history_df() -> pd.DataFrame:
    df = pd.DataFrame(
        [{"close": 195.5}, {"close": 197.0}],
        index=pd.to_datetime(["2025-08-01", "2025-08-02"]),
    )
    df.index.name = "date"
    return df


def _pence_history_df() -> pd.DataFrame:
    """yfinance-style LSE history: prices in pence (GBX) — BYG.L 820p = £8.20."""
    df = pd.DataFrame(
        [{"close": 820.0}, {"close": 830.5}],
        index=pd.to_datetime(["2026-09-22", "2026-09-23"]),
    )
    df.index.name = "date"
    return df


def _pence_ohlcv_df() -> pd.DataFrame:
    df = pd.DataFrame(
        [{"open": 810.0, "high": 830.0, "low": 805.0, "close": 820.0, "volume": 1000}],
        index=pd.to_datetime(["2026-09-23"]),
    )
    df.index.name = "date"
    return df


# ---------------------------------------------------------------------------
# get_price_history
# ---------------------------------------------------------------------------


@patch("src.openbb_client.obb")
def test_get_price_history_returns_list(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _price_history_df()
    mock_obb.equity.price.historical.return_value = mock_result

    result = get_price_history("AAPL", "2025-08-01", "2026-08-01")

    assert result == [
        {"date": "2025-08-01", "close": 195.5},
        {"date": "2025-08-02", "close": 197.0},
    ]
    mock_obb.equity.price.historical.assert_called_once_with(
        "AAPL", start_date="2025-08-01", end_date="2026-08-01", provider="yfinance"
    )


@patch("src.openbb_client.obb")
def test_get_price_history_empty_df_tries_next_provider(mock_obb):
    empty = MagicMock()
    empty.to_df.return_value = pd.DataFrame()
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _price_history_df()
    mock_obb.equity.price.historical.side_effect = [empty, mock_ok]

    result = get_price_history("AAPL", "2025-08-01", "2026-08-01")

    assert result is not None and len(result) == 2
    assert mock_obb.equity.price.historical.call_count == 2


@patch("src.openbb_client.obb")
def test_get_price_history_rate_limit_blocks_provider_tries_next(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _price_history_df()
    mock_obb.equity.price.historical.side_effect = [
        Exception("402 payment required"),
        mock_ok,
    ]

    result = get_price_history("AAPL", "2025-08-01", "2026-08-01")

    assert result is not None and len(result) == 2
    assert "yfinance" in openbb_client._provider_blocked_until
    assert mock_obb.equity.price.historical.call_count == 2


@patch("src.openbb_client.obb")
def test_get_price_history_invalid_ticker_returns_empty(mock_obb):
    mock_obb.equity.price.historical.side_effect = Exception("possibly delisted")

    result = get_price_history("FAKE", "2025-08-01", "2026-08-01")

    assert result == []
    assert mock_obb.equity.price.historical.call_count == 1


# ---------------------------------------------------------------------------
# GBX (pence) normalization for yfinance LSE tickers (plan §63.5, §63.13)
#
# The `.L` suffix alone must NOT trigger the ÷100. Many LSE lines are quoted in
# USD by yfinance and are already in major units; scaling those produced 100×
# too small bars (CNYA.L 0.0447 for ~4.46, DEAM.L 0.583 for ~58.3,
# IWDA.L 1.4691 for ~146.9). The provider-declared currency decides.
# ---------------------------------------------------------------------------


def _set_currency(ticker, currency):
    openbb_client._symbol_currency_cache[ticker.upper()] = currency


@pytest.fixture(autouse=True)
def _clear_currency_cache():
    openbb_client._symbol_currency_cache.clear()
    yield
    openbb_client._symbol_currency_cache.clear()


def test_is_pence_currency_excludes_iso_gbp_case_sensitively():
    assert openbb_client._is_pence_currency("GBp")
    assert openbb_client._is_pence_currency("GBX")
    assert not openbb_client._is_pence_currency("GBP")
    assert not openbb_client._is_pence_currency("USD")
    assert not openbb_client._is_pence_currency("EUR")
    assert not openbb_client._is_pence_currency(None)
    assert not openbb_client._is_pence_currency("")


def test_needs_gbx_normalization_only_pence_quoted_lse_on_yfinance():
    _set_currency("BYG.L", "GBp")
    _set_currency("CSN.L", "GBp")
    assert openbb_client._needs_gbx_normalization("yfinance", "BYG.L")
    assert openbb_client._needs_gbx_normalization("yfinance", "byg.l")

    # a USD-quoted LSE line is already major units — must NOT be scaled
    _set_currency("CNYA.L", "USD")
    _set_currency("DEAM.L", "USD")
    assert not openbb_client._needs_gbx_normalization("yfinance", "CNYA.L")
    assert not openbb_client._needs_gbx_normalization("yfinance", "DEAM.L")

    # a GBP-quoted LSE line is already major units too
    _set_currency("IWDA.GB", "GBP")
    assert not openbb_client._needs_gbx_normalization("yfinance", "IWDA.GB")

    # other providers / other suffixes never normalize
    assert not openbb_client._needs_gbx_normalization("fmp", "BYG.L")
    assert not openbb_client._needs_gbx_normalization("yfinance", "AAPL")
    assert not openbb_client._needs_gbx_normalization("yfinance", "VRC.WA")
    assert not openbb_client._needs_gbx_normalization("yfinance", "SAP.DE")


def test_needs_gbx_normalization_does_not_scale_when_currency_unknown():
    # deliberately fail open the other way: scaling a USD line is unbounded,
    # missing a pence line is bounded and flagged by instruments
    assert not openbb_client._needs_gbx_normalization("yfinance", "NOCURRENCY.L")


@patch("src.openbb_client.get_quote")
def test_symbol_currency_uses_quote_and_caches_success(mock_quote):
    mock_quote.return_value = {"currency": "GBp"}

    assert openbb_client._symbol_currency("BYG.L") == "GBp"
    assert openbb_client._symbol_currency("byg.l") == "GBp"
    assert mock_quote.call_count == 1  # second call served from cache


@patch("src.openbb_client.get_quote")
def test_symbol_currency_does_not_cache_failures(mock_quote):
    mock_quote.side_effect = Exception("upstream down")

    assert openbb_client._symbol_currency("BYG.L") is None
    assert openbb_client._symbol_currency("BYG.L") is None
    assert mock_quote.call_count == 2  # retried, not remembered


@patch("src.openbb_client.obb")
def test_get_price_history_yfinance_lse_pence_normalized(mock_obb):
    _set_currency("BYG.L", "GBp")
    mock_obb.equity.price.historical.return_value.to_df.return_value = _pence_history_df()

    result = get_price_history("BYG.L", "2026-09-22", "2026-09-25")

    # 820p -> 8.20 GBP, 830.5p -> 8.305 GBP (matches the live GBP quote)
    assert [r["close"] for r in result] == [8.2, 8.305]


@patch("src.openbb_client.obb")
def test_get_price_history_yfinance_usd_lse_untouched(mock_obb):
    _set_currency("CNYA.L", "USD")
    mock_obb.equity.price.historical.return_value.to_df.return_value = _pence_history_df()

    # Same input magnitudes, but a USD-quoted .L line: kept as-is.
    result = get_price_history("CNYA.L", "2026-09-22", "2026-09-25")
    assert [r["close"] for r in result] == [820.0, 830.5]


@patch("src.openbb_client.obb")
def test_get_price_history_yfinance_non_lse_unchanged(mock_obb):
    mock_obb.equity.price.historical.return_value.to_df.return_value = _pence_history_df()

    # Same pence-magnitude values, but a non-LSE ticker: no normalization.
    result = get_price_history("FAKEUS", "2026-09-22", "2026-09-25")
    assert [r["close"] for r in result] == [820.0, 830.5]


@patch("src.openbb_client.obb")
def test_get_ohlcv_history_yfinance_lse_pence_normalizes_all_price_fields(mock_obb):
    _set_currency("BYG.L", "GBp")
    mock_obb.equity.price.historical.return_value.to_df.return_value = _pence_ohlcv_df()

    result = get_ohlcv_history("BYG.L", "2026-09-23", "2026-09-25")

    r = result[0]
    assert (r["open"], r["high"], r["low"], r["close"]) == (8.1, 8.3, 8.05, 8.2)
    assert r["volume"] == 1000  # volume untouched


@patch("src.openbb_client.obb")
def test_get_ohlcv_history_yfinance_usd_lse_untouched(mock_obb):
    _set_currency("DEAM.L", "USD")
    mock_obb.equity.price.historical.return_value.to_df.return_value = _pence_ohlcv_df()

    result = get_ohlcv_history("DEAM.L", "2026-09-23", "2026-09-25")
    assert (result[0]["open"], result[0]["close"]) == (810.0, 820.0)


@patch("src.openbb_client.obb")
def test_get_ohlcv_history_yfinance_non_lse_unchanged(mock_obb):
    mock_obb.equity.price.historical.return_value.to_df.return_value = _pence_ohlcv_df()

    result = get_ohlcv_history("AAPL", "2026-09-23", "2026-09-25")
    assert (result[0]["open"], result[0]["close"]) == (810.0, 820.0)


@patch("src.openbb_client.obb")
def test_get_price_history_all_providers_fail_returns_none(mock_obb):
    mock_obb.equity.price.historical.side_effect = Exception("connection error")

    result = get_price_history("AAPL", "2025-08-01", "2026-08-01")

    assert result is None
    assert mock_obb.equity.price.historical.call_count == len(openbb_client.PRICE_PROVIDERS)


# ---------------------------------------------------------------------------
# get_dividend_history — existing tests
# ---------------------------------------------------------------------------


@patch("src.openbb_client.obb")
def test_get_dividend_history_returns_list(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _dividends_df()
    mock_obb.equity.fundamental.dividends.return_value = mock_result

    result = get_dividend_history("AAPL")

    assert result == [
        {"date": "2024-03-15", "amount": "0.2500"},
        {"date": "2024-06-15", "amount": "0.3000"},
    ]


@patch("src.openbb_client.obb")
def test_get_dividend_history_fallback_to_fmp(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _dividends_df()
    mock_obb.equity.fundamental.dividends.side_effect = [Exception("fail"), mock_ok]

    result = get_dividend_history("AAPL")
    assert result is not None
    assert len(result) == 2


@patch("src.openbb_client.obb")
def test_get_dividend_history_all_providers_fail_returns_empty(mock_obb):
    mock_obb.equity.fundamental.dividends.side_effect = Exception("fail")
    assert get_dividend_history("AAPL") == []


@patch("src.openbb_client.obb")
def test_get_dividend_history_non_payer_caches_result(mock_obb):
    empty = MagicMock()
    empty.to_df.return_value = pd.DataFrame()
    mock_obb.equity.fundamental.dividends.return_value = empty

    get_dividend_history("AAPL")
    get_dividend_history("AAPL")
    # all dividend providers tried on first call (all return empty → cached
    # False), 0 on second
    assert mock_obb.equity.fundamental.dividends.call_count == len(
        openbb_client.DIVIDEND_PROVIDERS
    )


@patch("src.openbb_client.obb")
def test_get_dividend_history_empty_df_returns_empty(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame()
    mock_obb.equity.fundamental.dividends.return_value = mock_result
    assert get_dividend_history("AAPL") == []


def _nasdaq_dividends_df() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {"ex_dividend_date": "2026-08-10", "amount": 0.27, "record_date": "2026-08-10",
             "payment_date": "2026-08-13", "declaration_date": "2026-07-30"},
            {"ex_dividend_date": "2026-05-11", "amount": 0.27, "record_date": "2026-05-11",
             "payment_date": "2026-05-14", "declaration_date": "2026-04-30"},
        ]
    )
    df = df.set_index(pd.to_datetime(df["ex_dividend_date"]))
    df.index.name = "ex_dividend_date"
    return df.drop(columns=["ex_dividend_date"])


@patch("src.openbb_client.obb")
def test_get_dividend_history_nasdaq_first_carries_payment_date(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _nasdaq_dividends_df()
    mock_obb.equity.fundamental.dividends.return_value = mock_result

    result = get_dividend_history("AAPL")

    assert result == [
        {"date": "2026-08-10", "amount": "0.2700", "payment_date": "2026-08-13"},
        {"date": "2026-05-11", "amount": "0.2700", "payment_date": "2026-05-14"},
    ]
    # nasdaq first; dividendmax is then consulted for its forecast rows and
    # contributes none (mock returns the same no-status paid df), so the body
    # stays the paid history.
    mock_obb.equity.fundamental.dividends.assert_any_call("AAPL", provider="nasdaq")
    assert mock_obb.equity.fundamental.dividends.call_count == 2


@patch("src.openbb_client.obb")
def test_get_dividend_history_merges_declared_and_forecast_rows(mock_obb):
    paid = MagicMock()
    paid.to_df.return_value = _nasdaq_dividends_df()

    fx_df = pd.DataFrame(
        [
            {"ex_dividend_date": "2026-10-15", "amount": 1.73, "status": "Declared",
             "payment_date": "2026-11-16", "declaration_date": "2026-09-10", "currency": "USD"},
            {"ex_dividend_date": "2027-01-15", "amount": float("nan"), "status": "Forecast",
             "payment_date": "2027-02-14", "declaration_date": "2026-11-01", "currency": "USD"},
            {"ex_dividend_date": "2026-08-10", "amount": 0.27, "status": "Paid"},
        ]
    )
    fx_df = fx_df.set_index(pd.to_datetime(fx_df["ex_dividend_date"]))
    fx = MagicMock()
    fx.to_df.return_value = fx_df.drop(columns=["ex_dividend_date"])
    mock_obb.equity.fundamental.dividends.side_effect = [paid, fx]

    result = get_dividend_history("ABBV")

    declared = [r for r in result if r.get("status") == "Declared"]
    forecast = [r for r in result if r.get("status") == "Forecast"]
    # declared row carries the public amount through to the body
    assert declared == [
        {"date": "2026-10-15", "amount": "1.7300", "payment_date": "2026-11-16",
         "status": "Declared"}
    ]
    assert len(forecast) == 1
    assert forecast[0]["date"] == "2027-01-15"
    assert forecast[0]["payment_date"] == "2027-02-14"
    # dividendmax's paid duplicate of a date nasdaq already returned is skipped
    assert len([r for r in result if r["date"] == "2026-08-10"]) == 1


@patch("src.openbb_client.obb")
def test_get_dividend_history_no_payment_date_column_stays_two_key(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _dividends_df()
    mock_obb.equity.fundamental.dividends.return_value = mock_result

    result = get_dividend_history("AAPL")

    assert result == [
        {"date": "2024-03-15", "amount": "0.2500"},
        {"date": "2024-06-15", "amount": "0.3000"},
    ]


@patch("src.openbb_client.obb")
def test_get_dividend_history_nasdaq_rate_limited_falls_back_to_yfinance(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _dividends_df()
    mock_obb.equity.fundamental.dividends.side_effect = [Exception("rate limit exceeded"), mock_ok]

    result = get_dividend_history("AAPL")

    assert result is not None
    assert len(result) == 2


# ---------------------------------------------------------------------------
# get_dividend_history — rate-limit / invalid ticker
# ---------------------------------------------------------------------------


@patch("src.openbb_client.obb")
def test_get_dividend_history_rate_limit_blocks_provider_tries_next(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _dividends_df()
    mock_obb.equity.fundamental.dividends.side_effect = [
        Exception("rate limit exceeded"),
        mock_ok,
    ]

    result = get_dividend_history("AAPL")

    assert result is not None
    assert len(result) == 2
    assert "nasdaq" in openbb_client._provider_blocked_until
    # one nasdaq failure + one successful provider + the dividendmax forecast merge
    assert mock_obb.equity.fundamental.dividends.call_count == 3


@patch("src.openbb_client.obb")
def test_get_dividend_history_invalid_ticker_returns_empty_no_further_providers(mock_obb):
    mock_obb.equity.fundamental.dividends.side_effect = Exception("not found for symbol ALGN")

    result = get_dividend_history("ALGN")

    assert result == []
    assert openbb_client._pays_dividend.get("ALGN") is False
    assert mock_obb.equity.fundamental.dividends.call_count == 1


@patch("src.openbb_client.obb")
def test_get_dividend_history_cached_false_skips_all_providers(mock_obb):
    openbb_client._pays_dividend["MPW"] = False

    result = get_dividend_history("MPW")

    assert result == []
    mock_obb.equity.fundamental.dividends.assert_not_called()


@patch("src.openbb_client.obb")
def test_get_dividend_history_blocked_provider_skipped(mock_obb):
    openbb_client._provider_blocked_until["nasdaq"] = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _dividends_df()
    mock_obb.equity.fundamental.dividends.return_value = mock_ok

    result = get_dividend_history("AAPL")

    assert result is not None
    first_call = mock_obb.equity.fundamental.dividends.call_args_list[0]
    assert first_call[1]["provider"] == "yfinance"


# ---------------------------------------------------------------------------
# New instruments-surface functions: profile / quote / metrics / projections /
# ohlcv / fundamentals / calendar / search
# ---------------------------------------------------------------------------


def _profile_df() -> pd.DataFrame:
    return pd.DataFrame([{"name": "Apple Inc", "sector": "Technology", "employees": 164000}])


def _quote_df() -> pd.DataFrame:
    return pd.DataFrame([{"last_price": 232.14, "change_percent": 1.24, "prev_close": 229.3}])


def _consensus_df() -> pd.DataFrame:
    return pd.DataFrame([{"target_high": 300.0, "target_low": 180.0, "target_median": 250.0}])


def _ohlcv_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{
            "open": 194.0,
            "high": 196.2,
            "low": 193.5,
            "close": 195.5,
            "volume": 52301400.0,
        }],
        index=pd.to_datetime(["2025-08-01"]),
    )


def _fund_ohlcv_df() -> pd.DataFrame:
    """OpenBB to_df shape for a biznesradar fund (NNEP25.TFI): OHLC identical, volume 0."""
    return pd.DataFrame(
        [
            {"open": 14.70, "high": 14.70, "low": 14.70, "close": 14.70, "volume": 0.0},
            {"open": 14.68, "high": 14.68, "low": 14.68, "close": 14.68, "volume": 0.0},
        ],
        index=pd.to_datetime(["2026-09-01", "2026-09-02"]),
    )


def _crypto_ohlcv_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"open": 40000.0, "high": 40800.0, "low": 39600.0, "close": 40500.0, "volume": 900.0},
            {"open": 40500.0, "high": 41200.0, "low": 40200.0, "close": 41000.0, "volume": 1200.0},
        ],
        index=pd.to_datetime(["2026-06-01", "2026-06-02"]),
    )


def _crypto_single_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{"open": 40000.0, "high": 40800.0, "low": 39600.0, "close": 40500.0, "volume": 900.0}],
        index=pd.to_datetime(["2026-06-01"]),
    )


def _income_df() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {"fiscal_year": 2024, "net_income": 93736_000_000},
            {"fiscal_year": 2023, "net_income": 96995_000_000},
        ],
        index=pd.to_datetime(["2024-09-28", "2023-09-30"]),
    )
    df.index.name = "period_ending"
    return df


def _earnings_calendar_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{"symbol": "AAPL", "eps_actual": 1.57, "eps_consensus": 1.51}]
    )


def _search_df() -> pd.DataFrame:
    return pd.DataFrame([{"cik": 320193, "name": "Apple Inc", "symbol": "AAPL"}])


def _crypto_search_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"symbol": "BTC-USD", "name": "Bitcoin USD"},
            {"symbol": "ETH-USD", "name": "Ethereum USD"},
        ]
    )


@patch("src.openbb_client.obb")
def test_get_profile_returns_first_record(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _profile_df()
    mock_obb.equity.profile.return_value = mock_result

    result = get_profile("AAPL")

    assert result == {"name": "Apple Inc", "sector": "Technology", "employees": 164000}
    mock_obb.equity.profile.assert_called_once_with("AAPL", provider="fmp")


@patch("src.openbb_client.obb")
def test_get_profile_falls_back_to_yfinance(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _profile_df()
    mock_obb.equity.profile.side_effect = [Exception("402 payment required"), mock_ok]

    result = get_profile("AAPL")

    assert result["name"] == "Apple Inc"
    assert "fmp" in openbb_client._provider_blocked_until


@patch("src.openbb_client.obb")
def test_get_profile_invalid_ticker_returns_none(mock_obb):
    mock_obb.equity.profile.side_effect = Exception("possibly delisted")
    assert get_profile("FAKE") is None


@patch("src.openbb_client.obb")
def test_get_quote_returns_first_record(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _quote_df()
    mock_obb.equity.price.quote.return_value = mock_result

    result = get_quote("AAPL")

    assert result == {"last_price": 232.14, "change_percent": 1.24, "prev_close": 229.3}
    mock_obb.equity.price.quote.assert_called_once_with("AAPL", provider="fmp")


@patch("src.openbb_client.obb")
def test_get_quote_all_fail_returns_none(mock_obb):
    mock_obb.equity.price.quote.side_effect = Exception("connection error")
    assert get_quote("AAPL") is None


@patch("src.openbb_client.obb")
def test_get_quote_fmp_yfinance_cboe_empty_falls_back_to_biznesradar(mock_obb):
    empty = MagicMock()
    empty.to_df.return_value = pd.DataFrame()
    biznes = MagicMock()
    biznes.to_df.return_value = pd.DataFrame(
        [{"symbol": "BST0327.WA", "last_price": 101.30, "change_percent": 0.003}]
    )
    mock_obb.equity.price.quote.side_effect = [empty, empty, empty, biznes]

    result = get_quote("BST0327.WA")

    assert result == {"symbol": "BST0327.WA", "last_price": 101.30, "change_percent": 0.003}
    assert mock_obb.equity.price.quote.call_count == 4
    assert [c.kwargs["provider"] for c in mock_obb.equity.price.quote.call_args_list] == [
        "fmp", "yfinance", "cboe", "biznesradar"
    ]


@patch("src.openbb_client.obb")
def test_get_profile_fmp_yfinance_empty_falls_back_to_biznesradar(mock_obb):
    empty = MagicMock()
    empty.to_df.return_value = pd.DataFrame()
    biznes = MagicMock()
    biznes.to_df.return_value = pd.DataFrame(
        [{"symbol": "BST0327.WA", "name": "BEST SA", "hq_country": "PL"}]
    )
    mock_obb.equity.profile.side_effect = [empty, empty, biznes]

    result = get_profile("BST0327.WA")

    assert result == {"symbol": "BST0327.WA", "name": "BEST SA", "hq_country": "PL"}
    assert mock_obb.equity.profile.call_count == 3
    assert [c.kwargs["provider"] for c in mock_obb.equity.profile.call_args_list] == [
        "fmp", "yfinance", "biznesradar"
    ]



    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame([{"market_cap": 3.1e12, "dividend_yield": 0.44}])
    mock_obb.equity.fundamental.metrics.return_value = mock_result

    result = get_metrics("AAPL")

    assert result == {"market_cap": 3.1e12, "dividend_yield": 0.44}


@patch("src.openbb_client.obb")
def test_get_projections_prefers_fmp(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _consensus_df()
    mock_obb.equity.estimates.consensus.return_value = mock_result

    result = get_projections("AAPL")

    assert result["target_high"] == 300.0
    assert result["target_low"] == 180.0
    assert result["target_median"] == 250.0
    # yfinance recommendation is best-effort; with a consensus df lacking
    # recommendation columns it degrades to a null-valued block.
    assert result["recommendation"] == {"mean": None, "rating": None, "analysts": None}


@patch("src.openbb_client.obb")
def test_get_projections_falls_back_to_yfinance(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _consensus_df()
    mock_obb.equity.estimates.consensus.side_effect = [Exception("yfinance down"), mock_ok]

    result = get_projections("AAPL")

    assert result is not None
    assert mock_obb.equity.estimates.consensus.call_count == 3


@patch("src.openbb_client.obb")
def test_get_projections_includes_yfinance_recommendation(mock_obb):
    mock_targets = MagicMock()
    mock_targets.to_df.return_value = pd.DataFrame(
        [{"target_high": 300.0, "target_low": 180.0, "target_consensus": 250.0, "target_median": 250.0}]
    )
    mock_rec = MagicMock()
    mock_rec.to_df.return_value = pd.DataFrame(
        [{"recommendation": "buy", "recommendation_mean": 2.18182, "number_of_analysts": 39}]
    )
    # first call (fmp targets) succeeds; second call (yf recommendation) succeeds
    mock_obb.equity.estimates.consensus.side_effect = [mock_targets, mock_rec]

    result = get_projections("AAPL")

    assert result["recommendation"]["mean"] == 2.18
    assert result["recommendation"]["rating"] == "buy"
    assert result["recommendation"]["analysts"] == 39


@patch("src.openbb_client.obb")
def test_get_ohlcv_history_row_shape(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _ohlcv_df()
    mock_obb.equity.price.historical.return_value = mock_result

    result = openbb_client.get_ohlcv_history("AAPL", "2025-08-01", "2026-08-01")

    assert result == [
        {
            "date": "2025-08-01",
            "open": 194.0,
            "high": 196.2,
            "low": 193.5,
            "close": 195.5,
            "volume": 52301400,
        }
    ]


@patch("src.openbb_client.obb")
def test_get_ohlcv_history_rate_limit_blocks_provider_tries_next(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _ohlcv_df()
    mock_obb.equity.price.historical.side_effect = [
        Exception("402 premium"),
        mock_ok,
    ]

    result = openbb_client.get_ohlcv_history("AAPL", "2025-08-01", "2026-08-01")

    assert len(result) == 1
    assert "yfinance" in openbb_client._provider_blocked_until


def test_pride_providers_biznesradar_is_last_resort():
    assert openbb_client.PRICE_PROVIDERS[-1] == "biznesradar"


@patch("src.openbb_client.obb")
def test_get_ohlcv_history_biznesradar_fallback(mock_obb):
    """All free US venues fail → biznesradar serves fixture-shaped NNEP25.TFI rows."""
    biz = openbb_client.PRICE_PROVIDERS.index("biznesradar")
    mock_fund = MagicMock()
    mock_fund.to_df.return_value = _fund_ohlcv_df()
    mock_obb.equity.price.historical.side_effect = (
        [Exception("provider down")] * biz + [mock_fund]
    )

    result = openbb_client.get_ohlcv_history("NNEP25.TFI", "2026-09-01", "2026-09-11")

    assert result == [
        {"date": "2026-09-01", "open": 14.7, "high": 14.7, "low": 14.7, "close": 14.7, "volume": 0},
        {"date": "2026-09-02", "open": 14.68, "high": 14.68, "low": 14.68, "close": 14.68, "volume": 0},
    ]
    calls = mock_obb.equity.price.historical.call_args_list
    assert len(calls) == biz + 1
    assert calls[biz].kwargs["provider"] == "biznesradar"
    assert calls[biz].args[0] == "NNEP25.TFI"


@patch("src.openbb_client.obb")
def test_get_ohlcv_history_biznesradar_empty_then_none(mock_obb):
    biz = openbb_client.PRICE_PROVIDERS.index("biznesradar")
    mock_empty = MagicMock()
    mock_empty.to_df.return_value = pd.DataFrame()
    mock_obb.equity.price.historical.side_effect = [mock_empty] * (biz + 1)

    assert openbb_client.get_ohlcv_history("NNEP25.TFI", "2026-09-01", "2026-09-11") is None


@patch("src.openbb_client.obb")
def test_get_ohlcv_history_all_fail_returns_none(mock_obb):
    mock_obb.equity.price.historical.side_effect = Exception("timeout")
    assert openbb_client.get_ohlcv_history("AAPL", "2025-08-01", "2026-08-01") is None


@patch("src.openbb_client.obb")
def test_get_crypto_ohlcv_row_shape(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _crypto_ohlcv_df()
    mock_obb.crypto.price.historical.return_value = mock_result

    result = openbb_client.get_crypto_ohlcv("BTC-USD", "2026-06-01", "2026-06-05")

    assert result == [
        {"date": "2026-06-01", "open": 40000.0, "high": 40800.0, "low": 39600.0, "close": 40500.0, "volume": 900},
        {"date": "2026-06-02", "open": 40500.0, "high": 41200.0, "low": 40200.0, "close": 41000.0, "volume": 1200},
    ]
    mock_obb.crypto.price.historical.assert_called_with(
        "BTC-USD", start_date="2026-06-01", end_date="2026-06-05", provider="yfinance"
    )


@patch("src.openbb_client.obb")
def test_get_crypto_ohlcv_all_empty_returns_none(mock_obb, monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setenv("TIINGO_TOKEN", "test-key")
    mock_empty = MagicMock()
    mock_empty.to_df.return_value = pd.DataFrame()
    mock_obb.crypto.price.historical.return_value = mock_empty

    assert openbb_client.get_crypto_ohlcv("BTC-USD", "2026-06-01", "2026-06-05") is None
    assert mock_obb.crypto.price.historical.call_count == len(openbb_client.CRYPTO_PROVIDERS)


@patch("src.openbb_client.obb")
def test_get_crypto_ohlcv_rate_limit_blocks_provider_tries_next(mock_obb, monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _crypto_ohlcv_df()
    mock_obb.crypto.price.historical.side_effect = [
        Exception("402 premium"),
        mock_ok,
    ]

    result = openbb_client.get_crypto_ohlcv("BTC-USD", "2026-06-01", "2026-06-05")

    assert len(result) == 2
    assert "yfinance" in openbb_client._provider_blocked_until
    assert result[0]["date"] == "2026-06-01"


@patch("src.openbb_client.obb")
def test_get_crypto_ohlcv_skips_keyless_providers(mock_obb, monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.delenv("TIINGO_TOKEN", raising=False)
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame()
    mock_obb.crypto.price.historical.return_value = mock_result

    assert openbb_client.get_crypto_ohlcv("BTC-USD", "2026-06-01", "2026-06-05") is None
    calls = [
        c.kwargs["provider"]
        for c in mock_obb.crypto.price.historical.call_args_list
    ]
    assert calls == ["yfinance"]


@patch("src.openbb_client.obb")
def test_get_crypto_quote_happy_path(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _crypto_ohlcv_df()
    mock_obb.crypto.price.historical.return_value = mock_result

    result = openbb_client.get_crypto_quote("ETH-USD")

    assert set(result) == {
        "symbol", "price", "change", "change_percent", "open", "high", "low", "volume", "date",
    }
    assert result["symbol"] == "ETH-USD"
    assert result["price"] == 41000.0
    assert result["change"] == 500.0
    assert result["change_percent"] == pytest.approx(round(500.0 / 40500.0, 2))
    assert result["date"] == "2026-06-02"


@patch("src.openbb_client.obb")
def test_get_crypto_quote_single_row_omits_change_fields(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _crypto_single_df()
    mock_obb.crypto.price.historical.return_value = mock_result

    result = openbb_client.get_crypto_quote("ETH-USD")

    assert result["price"] == 40500.0
    assert "change" not in result
    assert "change_percent" not in result


@patch("src.openbb_client.obb")
def test_get_crypto_quote_all_fail_returns_none(mock_obb, monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setenv("TIINGO_TOKEN", "test-key")
    mock_obb.crypto.price.historical.side_effect = Exception("timeout")

    assert openbb_client.get_crypto_quote("ETH-USD") is None


@patch("src.openbb_client.obb")
def test_get_crypto_search_returns_rows(mock_obb, monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    mock_result = MagicMock()
    mock_result.to_df.return_value = _crypto_search_df()
    mock_obb.crypto.search.return_value = mock_result

    result = openbb_client.get_crypto_search("btc")

    assert result == [
        {"symbol": "BTC-USD", "name": "Bitcoin USD"},
        {"symbol": "ETH-USD", "name": "Ethereum USD"},
    ]
    mock_obb.crypto.search.assert_called_once_with("btc", provider="fmp")


@patch("src.openbb_client.obb")
def test_get_crypto_search_empty_df_returns_empty(mock_obb, monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    mock_empty = MagicMock()
    mock_empty.to_df.return_value = pd.DataFrame()
    mock_obb.crypto.search.return_value = mock_empty

    assert openbb_client.get_crypto_search("btc") == []


@patch("src.openbb_client.obb")
def test_get_crypto_search_rate_limit_blocks_provider(mock_obb, monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    mock_obb.crypto.search.side_effect = Exception("402 premium")

    assert openbb_client.get_crypto_search("btc") == []
    assert "fmp" in openbb_client._provider_blocked_until

    # subsequent call sees the blocked provider and is skipped, yet still returns []
    mock_obb.crypto.search.side_effect = None
    mock_obb.crypto.search.return_value = MagicMock(to_df=lambda: _crypto_search_df())
    assert openbb_client.get_crypto_search("btc") == []
    assert mock_obb.crypto.search.call_count == 1


@patch("src.openbb_client.obb")
def test_get_crypto_search_skips_keyless_provider(mock_obb, monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    mock_obb.crypto.search.return_value = MagicMock(to_df=lambda: _crypto_search_df())

    assert openbb_client.get_crypto_search("btc") == []
    mock_obb.crypto.search.assert_not_called()


# ---------------------------------------------------------------------------
# crypto profile — quote body plus the search leg (§86.1 fixtures, §86.3)
# ---------------------------------------------------------------------------

CRYPTO_FIXTURES = Path(__file__).parent / "fixtures" / "crypto"


def _crypto_search_fixture() -> list[dict]:
    """The recorded 17-row `btcusd` search response, verbatim (§86.1)."""
    return json.loads((CRYPTO_FIXTURES / "search_BTC-USD.json").read_text(encoding="utf-8"))


def _search_fixture_df() -> pd.DataFrame:
    return pd.DataFrame(_crypto_search_fixture())


def _profile_fixture() -> dict:
    return json.loads((CRYPTO_FIXTURES / "profile_BTC-USD.json").read_text(encoding="utf-8"))


@patch("src.openbb_client.obb")
def test_crypto_profile_fixture_is_the_shape_the_widening_preserves(mock_obb, monkeypatch):
    """The recorded four-field body is a strict subset of what we now emit.

    Guards the "additive, not a replacement" claim: if the quote-derived keys
    ever move or change type, this fails before §86.3's merge test does.
    """
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    mock_obb.crypto.price.historical.return_value = MagicMock(to_df=_crypto_single_df)
    mock_obb.crypto.search.return_value = MagicMock(to_df=_search_fixture_df)

    before = _profile_fixture()
    after = openbb_client.get_crypto_profile("BTC-USD")

    assert set(before) < set(after)
    for key, value in before.items():
        if key in ("price", "date"):
            # The fixture recorded the live quote; these tests serve a mocked bar.
            assert isinstance(after[key], type(value))
            continue
        assert after[key] == value


@patch("src.openbb_client.obb")
def test_get_crypto_profile_merges_the_exact_search_row(mock_obb, monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    mock_obb.crypto.price.historical.return_value = MagicMock(to_df=_crypto_single_df)
    mock_obb.crypto.search.return_value = MagicMock(to_df=_search_fixture_df)

    result = openbb_client.get_crypto_profile("BTC-USD")

    # The quote leg is untouched: same keys, same types, same values.
    assert result["symbol"] == "BTC-USD"
    assert result["currency"] == "USD"
    assert result["price"] == 40500.0
    assert result["date"]

    # The five search fields come from BTCUSD (row 12 of 17), never from row 1,
    # which is TBTCUSD — "tBTC USD", a different coin that also matches "BTC".
    assert result["name"] == "Bitcoin USD"
    assert result["exchange"] == "CCC"
    assert result["ico_date"] == "2014-09-17"
    assert result["circulating_supply"] == 19972590.0
    assert result["total_supply"] == 19972590.0


@patch("src.openbb_client.obb")
def test_get_crypto_profile_null_supplies_stay_null(mock_obb, monkeypatch):
    """A supply FMP omits is null, never 0.

    WBTCUSD is one of six rows in the fixture with no `total_supply`. Coercing
    it to 0 would state that Wrapped Bitcoin has issued nothing, which is a
    different and much worse claim than "the provider does not say".
    """
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    mock_obb.crypto.price.historical.return_value = MagicMock(to_df=_crypto_single_df)
    mock_obb.crypto.search.return_value = MagicMock(to_df=_search_fixture_df)

    result = openbb_client.get_crypto_profile("WBTC-USD")

    assert result["name"] == "Wrapped Bitcoin USD"
    assert result["circulating_supply"] == 125330.0
    assert result["total_supply"] is None


@patch("src.openbb_client.obb")
def test_get_crypto_profile_no_exact_match_keeps_the_quote_body(mock_obb, monkeypatch):
    """No exact row means no search fields — omitted, not null.

    NMBTCUSD is in the response but is not the pair asked for, so a profile for
    NMBTCUSD-USD must come back exactly as it did before this step: four keys.
    """
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    mock_obb.crypto.price.historical.return_value = MagicMock(to_df=_crypto_single_df)
    mock_obb.crypto.search.return_value = MagicMock(to_df=_search_fixture_df)

    result = openbb_client.get_crypto_profile("NMBTCUSD-USD")

    assert set(result) == {"symbol", "currency", "price", "date"}
    assert result["price"] == 40500.0
    mock_obb.crypto.search.assert_called_once_with("NMBTCUSD-USD", provider="fmp")


@patch("src.openbb_client.obb")
def test_get_crypto_profile_keyless_search_provider_does_not_raise(mock_obb, monkeypatch):
    """No FMP key means no search leg, and still a usable profile.

    The gating is the established `_provider_has_key` pattern from
    get_crypto_quote: the profile degrades to the quote body instead of raising,
    because a research page with no name beats a 404.
    """
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    mock_obb.crypto.price.historical.return_value = MagicMock(to_df=_crypto_single_df)

    result = openbb_client.get_crypto_profile("BTC-USD")

    assert set(result) == {"symbol", "currency", "price", "date"}
    mock_obb.crypto.search.assert_not_called()


@patch("src.openbb_client.obb")
def test_get_crypto_profile_search_failure_keeps_the_quote_body(mock_obb, monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    mock_obb.crypto.price.historical.return_value = MagicMock(to_df=_crypto_single_df)
    mock_obb.crypto.search.side_effect = Exception("402 payment required")

    result = openbb_client.get_crypto_profile("BTC-USD")

    assert set(result) == {"symbol", "currency", "price", "date"}
    # …and the provider is blocked for the walk, as with any other search.
    assert "fmp" in openbb_client._provider_blocked_until


@patch("src.openbb_client.obb")
def test_get_fundamentals_calls_statement_and_period(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _income_df()
    mock_obb.equity.fundamental.income.return_value = mock_result

    result = get_fundamentals("AAPL", "income", "annual")

    # §79.2 — the provider travels with the rows, in the body.
    assert result["provider"] == "fmp"
    assert [r["fiscal_year"] for r in result["rows"]] == [2024, 2023]
    assert result["rows"][0]["period_ending"] == "2024-09-28 00:00:00"
    mock_obb.equity.fundamental.income.assert_called_once_with(
        "AAPL", period="annual", provider="fmp"
    )


@patch("src.openbb_client.obb")
def test_get_fundamentals_falls_back_to_yfinance(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _income_df()
    mock_obb.equity.fundamental.balance.side_effect = [Exception("fail"), mock_ok]

    result = get_fundamentals("AAPL", "balance", "quarter")

    assert len(result["rows"]) == 2
    # The point of the envelope: a mixed-provider table is only visible if the
    # fallback names itself. Without this the consumer could not tell a yfinance
    # balance sheet from an fmp one.
    assert result["provider"] == "yfinance"
    assert mock_obb.equity.fundamental.balance.call_count == 2


@patch("src.openbb_client.obb")
def test_get_fundamentals_all_fail_returns_none(mock_obb):
    mock_obb.equity.fundamental.cash.side_effect = Exception("fail")
    assert get_fundamentals("AAPL", "cash", "annual") is None


@patch("src.openbb_client.obb")
def test_get_fundamentals_empty_provider_result_is_not_attributed(mock_obb):
    """A provider that returns nothing has not answered, so no name is recorded."""
    mock_obb.equity.fundamental.income.side_effect = [
        MagicMock(to_df=lambda: pd.DataFrame()),
        MagicMock(to_df=lambda: pd.DataFrame()),
        MagicMock(to_df=lambda: pd.DataFrame()),
        MagicMock(to_df=lambda: pd.DataFrame()),
    ]
    assert get_fundamentals("AAPL", "income", "annual") is None


@patch("src.openbb_client.obb")
def test_get_calendar_passes_window(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _earnings_calendar_df()
    mock_obb.equity.calendar.earnings.return_value = mock_result

    result = get_calendar("earnings", "2026-08-20", "2026-08-25")

    assert result == [{"symbol": "AAPL", "eps_actual": 1.57, "eps_consensus": 1.51}]
    mock_obb.equity.calendar.earnings.assert_called_once_with(
        start_date="2026-08-20", end_date="2026-08-25", provider="fmp"
    )


@patch("src.openbb_client.obb")
def test_get_calendar_empty_window_returns_empty(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame()
    mock_obb.equity.calendar.dividend.return_value = mock_result
    assert get_calendar("dividend", "2026-08-20", "2026-08-25") == []


def _dividend_calendar_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


@patch("src.openbb_client.obb")
def test_get_calendar_dividend_merges_providers(mock_obb):
    """§52.6 — GPW (biznesradar) rows must surface alongside US (nasdaq) rows:
    the calendar is consumed per-symbol downstream, so first-non-empty would
    mask the GPW payers whenever a US provider answers for the window."""
    us_df = _dividend_calendar_df(
        [
            {
                "ex_dividend_date": "2026-08-10",
                "symbol": "AAPL",
                "amount": 0.27,
                "payment_date": "2026-08-13",
            }
        ]
    )
    pl_df = _dividend_calendar_df(
        [
            {
                "ex_dividend_date": "2026-09-28",
                "symbol": "NTT",
                "amount": 0.22,
                "payment_date": "2026-12-30",
                "status": "uchwalona",
            }
        ]
    )
    empty = MagicMock()
    empty.to_df.return_value = pd.DataFrame()

    def by_provider(**kwargs):
        if kwargs.get("provider") == "nasdaq":
            r = MagicMock()
            r.to_df.return_value = us_df
            return r
        if kwargs.get("provider") == "biznesradar":
            r = MagicMock()
            r.to_df.return_value = pl_df
            return r
        return empty

    mock_obb.equity.calendar.dividend.side_effect = by_provider
    result = get_calendar("dividend", "2026-08-20", "2026-12-31")
    assert {r["symbol"] for r in result} == {"AAPL", "NTT"}
    assert len(mock_obb.equity.calendar.dividend.call_args_list) == 3


@patch("src.openbb_client.obb")
def test_get_calendar_dividend_dedupes_identical_rows(mock_obb):
    dup_df = _dividend_calendar_df(
        [
            {
                "ex_dividend_date": "2026-08-10",
                "symbol": "AAPL",
                "amount": 0.27,
                "payment_date": "2026-08-13",
            }
        ]
    )

    def by_provider(**kwargs):
        if kwargs.get("provider") in ("nasdaq", "biznesradar"):
            r = MagicMock()
            r.to_df.return_value = dup_df
            return r
        r = MagicMock()
        r.to_df.return_value = pd.DataFrame()
        return r

    mock_obb.equity.calendar.dividend.side_effect = by_provider
    result = get_calendar("dividend", "2026-08-20", "2026-12-31")
    assert result == [
        {
            "ex_dividend_date": "2026-08-10",
            "symbol": "AAPL",
            "amount": 0.27,
            "payment_date": "2026-08-13",
        }
    ]


@patch("src.openbb_client.obb")
def test_get_calendar_dividend_skips_rate_limited_provider(mock_obb):
    """fmp 402 (premium) must not abort the merge — nasdaq rows still surface."""
    us_df = _dividend_calendar_df(
        [
            {
                "ex_dividend_date": "2026-08-10",
                "symbol": "AAPL",
                "amount": 0.27,
                "payment_date": "2026-08-13",
            }
        ]
    )

    def by_provider(**kwargs):
        if kwargs.get("provider") == "fmp":
            raise Exception("402 Premium Query Parameter")
        if kwargs.get("provider") == "nasdaq":
            r = MagicMock()
            r.to_df.return_value = us_df
            return r
        r = MagicMock()
        r.to_df.return_value = pd.DataFrame()
        return r

    mock_obb.equity.calendar.dividend.side_effect = by_provider
    result = get_calendar("dividend", "2026-08-20", "2026-12-31")
    assert [r["symbol"] for r in result] == ["AAPL"]
    assert openbb_client._provider_is_blocked("fmp")


@patch("src.openbb_client.obb")
def test_get_calendar_earnings_never_uses_biznesradar(mock_obb):
    """§52 follow-up — biznesradar only implements CalendarDividend; the Earnings
    model rejects it ("Input should be 'fmp', 'nasdaq' or 'tmx'"), so earnings
    must iterate only its own provider list. Empty fmp + nasdaq fall through to
    tmx, and biznesradar is never attempted."""
    def by_provider(**kwargs):
        r = MagicMock()
        r.to_df.return_value = pd.DataFrame()
        return r

    mock_obb.equity.calendar.earnings.side_effect = by_provider
    assert get_calendar("earnings", "2026-08-20", "2027-01-22") == []
    providers = [c.kwargs["provider"] for c in mock_obb.equity.calendar.earnings.call_args_list]
    assert "biznesradar" not in providers
    assert providers == ["fmp", "nasdaq", "tmx"]


@patch("src.openbb_client.obb")
def test_search_equities_uses_sec_provider(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _search_df()
    mock_obb.equity.search.return_value = mock_result

    result = search_equities("apple")

    assert result == [{"cik": 320193, "name": "Apple Inc", "symbol": "AAPL"}]
    mock_obb.equity.search.assert_called_once_with("apple", provider="sec")


@patch("src.openbb_client.obb")
def test_search_equities_sec_nasdaq_cboe_empty_falls_back_to_biznesradar(mock_obb):
    empty = MagicMock()
    empty.to_df.return_value = pd.DataFrame()
    biznes = MagicMock()
    biznes.to_df.return_value = pd.DataFrame(
        [{"name": "BEST S.A.", "symbol": "BST0327.WA", "cik": None}]
    )
    mock_obb.equity.search.side_effect = [empty, empty, empty, biznes]

    result = search_equities("bst0327.wa")

    assert result == [{"name": "BEST S.A.", "symbol": "BST0327.WA", "cik": None}]
    assert mock_obb.equity.search.call_count == 4
    assert [c.kwargs["provider"] for c in mock_obb.equity.search.call_args_list] == [
        "sec",
        "nasdaq",
        "cboe",
        "biznesradar",
    ]


@patch("src.openbb_client.obb")
def test_search_equities_failure_returns_empty(mock_obb):
    mock_obb.equity.search.side_effect = Exception("boom")
    assert search_equities("apple") == []


def test_plain_converts_nan_to_none():
    assert openbb_client._plain(float("nan")) is None


def test_plain_converts_pandas_na_to_none():
    assert openbb_client._plain(pd.NA) is None


def test_plain_keeps_primitives():
    assert openbb_client._plain(42) == 42
    assert openbb_client._plain(3.14) == 3.14
    assert openbb_client._plain("x") == "x"


def test_plain_stringifies_unknown_types():
    from decimal import Decimal
    assert openbb_client._plain(Decimal("1.5")) == "1.5"


def test_dividend_history_handles_non_datetime_index():
    """Providers that return a RangeIndex (date as a column) still yield ISO dates."""
    df = pd.DataFrame(
        [{"ex_dividend_date": "2026-05-12", "amount": 0.26},
         {"ex_dividend_date": "2026-02-09", "amount": 0.25}],
    )
    fake = types.SimpleNamespace(
        equity=types.SimpleNamespace(
            fundamental=types.SimpleNamespace(
                dividends=lambda ticker, provider: types.SimpleNamespace(to_df=lambda: df),
            ),
        ),
    )
    with patch.object(openbb_client, "obb", fake):
        rows = openbb_client.get_dividend_history("AAPL")
    assert [r["date"] for r in rows] == ["2026-05-12", "2026-02-09"]
    assert rows[0]["amount"] == "0.2600"


# ---------------------------------------------------------------------------
# SEC endpoints — insider trading / institutional ownership / filings / MD&A
# ---------------------------------------------------------------------------


def _insider_trading_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{
            "transaction_type": "P",
            "shares_transacted": 1000,
            "value_transacted": 195000.0,
            "insider_name": "Tim Cook",
            "insider_title": "CEO",
        }]
    )


def _form_13f_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{
            "symbol": "AAPL",
            "fund_name": "Vanguard Group",
            "total_shares": 1000000,
            "value": 195000000.0,
            "pct_ownership": 6.2,
        }]
    )


def _filings_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{
            "symbol": "AAPL",
            "filing_date": "2026-08-21",
            "form_type": "10-K",
            "report_url": "https://www.sec.gov/Archives/edgar/data/0000320193/...",
        }]
    )


def _mda_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{"symbol": "AAPL", "period": "FY2025", "content": "Results of Operations..."}]
    )


def _mda_long_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"index": "symbol", "SecManagementDiscussionAnalysisData": "AAPL"},
            {"index": "calendar_year", "SecManagementDiscussionAnalysisData": 2026},
            {"index": "calendar_period", "SecManagementDiscussionAnalysisData": 2},
            {"index": "period_ending", "SecManagementDiscussionAnalysisData": "2026-06-27"},
            {"index": "content", "SecManagementDiscussionAnalysisData": "## Item 2. Management's Discussion and Analysis"},
            {"index": "url", "SecManagementDiscussionAnalysisData": "https://www.sec.gov/Archives/edgar/data/320193/x.htm"},
        ]
    )


@patch("src.openbb_client.obb")
def test_get_insider_trading_returns_records(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _insider_trading_df()
    mock_obb.equity.ownership.insider_trading.return_value = mock_result

    result = get_insider_trading("AAPL")

    assert result == [{
        "transaction_type": "P",
        "shares_transacted": 1000,
        "value_transacted": 195000.0,
        "insider_name": "Tim Cook",
        "insider_title": "CEO",
    }]
    mock_obb.equity.ownership.insider_trading.assert_called_once_with("AAPL", provider="sec")


@patch("src.openbb_client.obb")
def test_get_insider_trading_invalid_ticker_returns_empty(mock_obb):
    mock_obb.equity.ownership.insider_trading.side_effect = Exception("possibly delisted")
    assert get_insider_trading("FAKE") == []
    assert mock_obb.equity.ownership.insider_trading.call_count == 1


@patch("src.openbb_client.obb")
def test_get_insider_trading_all_fail_returns_empty(mock_obb):
    mock_obb.equity.ownership.insider_trading.side_effect = Exception("connection error")
    assert get_insider_trading("AAPL") == []


@patch("src.openbb_client.obb")
def test_get_institutional_ownership_returns_records(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _form_13f_df()
    mock_obb.equity.ownership.form_13f.return_value = mock_result

    result = get_institutional_ownership("AAPL")

    assert result == [{
        "symbol": "AAPL",
        "fund_name": "Vanguard Group",
        "total_shares": 1000000,
        "value": 195000000.0,
        "pct_ownership": 6.2,
    }]
    mock_obb.equity.ownership.form_13f.assert_called_once_with("AAPL", provider="sec")


@patch("src.openbb_client.obb")
def test_get_institutional_ownership_all_fail_returns_empty(mock_obb):
    mock_obb.equity.ownership.form_13f.side_effect = Exception("connection error")
    assert get_institutional_ownership("AAPL") == []


@patch("src.openbb_client.obb")
def test_get_filings_returns_records(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _filings_df()
    mock_obb.equity.fundamental.filings.return_value = mock_result

    result = get_filings("AAPL")

    assert result[0]["form_type"] == "10-K"
    assert result[0]["report_url"].startswith("https://www.sec.gov/")
    mock_obb.equity.fundamental.filings.assert_called_once_with("AAPL", provider="sec")


@patch("src.openbb_client.obb")
def test_get_filings_invalid_ticker_returns_empty(mock_obb):
    mock_obb.equity.fundamental.filings.side_effect = Exception("not found for symbol FAKE")
    assert get_filings("FAKE") == []


@patch("src.openbb_client.obb")
def test_get_mda_returns_first_record(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _mda_df()
    mock_obb.equity.fundamental.management_discussion_analysis.return_value = mock_result

    result = get_mda("AAPL")

    assert result["period"] == "FY2025"
    mock_obb.equity.fundamental.management_discussion_analysis.assert_called_once_with(
        "AAPL", provider="sec"
    )


@patch("src.openbb_client.obb")
def test_get_mda_pivots_long_two_column_frame(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _mda_long_df()
    mock_obb.equity.fundamental.management_discussion_analysis.return_value = mock_result

    result = get_mda("AAPL")

    assert result == {
        "symbol": "AAPL",
        "calendar_year": 2026,
        "calendar_period": 2,
        "period_ending": "2026-06-27",
        "content": "## Item 2. Management's Discussion and Analysis",
        "url": "https://www.sec.gov/Archives/edgar/data/320193/x.htm",
    }


@patch("src.openbb_client.obb")
def test_get_mda_no_data_returns_none(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame()
    mock_obb.equity.fundamental.management_discussion_analysis.return_value = mock_result
    assert get_mda("AAPL") is None


@patch("src.openbb_client.obb")
def test_get_mda_invalid_ticker_returns_none(mock_obb):
    mock_obb.equity.fundamental.management_discussion_analysis.side_effect = Exception(
        "possibly delisted"
    )
    assert get_mda("FAKE") is None
    assert mock_obb.equity.fundamental.management_discussion_analysis.call_count == 1


# ---------------------------------------------------------------------------
# Savings-bond DB-first search / profile (D79 21.3)
# ---------------------------------------------------------------------------


def _bond_series(
    symbol: str = "EDO0936",
    name: str = "Obligacje 10-letnie EDO",
    series_code: str = "EDO",
    issue_date: date = date(2026, 1, 1),
    maturity_date: date = date(2036, 1, 1),
    term_months: int = 120,
    rate_rule: str = "fixed",
    margin: Decimal = Decimal("3.50"),
    fee_b: Decimal = Decimal("3.00"),
    nominal: Decimal = Decimal("100.00"),
):
    from openbb_obligacje.engine import BondSeries

    return BondSeries(
        symbol=symbol,
        name=name,
        series_code=series_code,
        issue_date=issue_date,
        maturity_date=maturity_date,
        term_months=term_months,
        rate_rule=rate_rule,
        margin=margin,
        fee_b=fee_b,
        nominal=nominal,
    )


def _use_bond_db(monkeypatch) -> None:
    monkeypatch.setattr(
        openbb_client.db, "database_url", lambda: "postgresql://user:pass@host/openst"
    )


_SEARCH_ROW = [{"symbol": "EDO0936", "name": "Obligacje 10-letnie EDO", "maturity_date": "2036-01-01"}]


@patch("src.openbb_client.obb")
def test_search_bonds_db_row_maps_to_search_shape_and_skips_openbb(mock_obb, monkeypatch):
    _use_bond_db(monkeypatch)
    from openbb_obligacje import store

    monkeypatch.setattr(store, "search_bond_series", lambda term, is_symbol=False: [_bond_series()])

    result = openbb_client.search_bonds("edo")

    assert result == _SEARCH_ROW
    mock_obb.equity.search.assert_not_called()


@patch("src.openbb_client.obb")
def test_search_bonds_db_empty_falls_back_to_openbb(mock_obb, monkeypatch):
    _use_bond_db(monkeypatch)
    from openbb_obligacje import store

    monkeypatch.setattr(store, "search_bond_series", lambda term, is_symbol=False: [])
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame(_SEARCH_ROW)
    mock_obb.equity.search.return_value = mock_result

    result = openbb_client.search_bonds("edo")

    assert result == _SEARCH_ROW
    mock_obb.equity.search.assert_called_once_with("edo", provider="obligacje")


@patch("src.openbb_client.obb")
def test_search_bonds_db_error_falls_back_to_openbb(mock_obb, monkeypatch):
    _use_bond_db(monkeypatch)
    from openbb_obligacje import store

    def boom(term, is_symbol=False):
        raise RuntimeError("db down")

    monkeypatch.setattr(store, "search_bond_series", boom)
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame(_SEARCH_ROW)
    mock_obb.equity.search.return_value = mock_result

    assert openbb_client.search_bonds("edo") == _SEARCH_ROW
    mock_obb.equity.search.assert_called_once_with("edo", provider="obligacje")


@patch("src.openbb_client.obb")
def test_search_bonds_no_db_uses_pure_openbb_path(mock_obb, monkeypatch):
    monkeypatch.setattr(openbb_client.db, "database_url", lambda: None)
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame(_SEARCH_ROW)
    mock_obb.equity.search.return_value = mock_result

    result = openbb_client.search_bonds("edo")

    assert result == _SEARCH_ROW
    mock_obb.equity.search.assert_called_once_with("edo", provider="obligacje")


@patch("src.openbb_client.obb")
def test_get_bond_profile_db_row_maps_ten_columns_and_skips_openbb(mock_obb, monkeypatch):
    _use_bond_db(monkeypatch)
    from openbb_obligacje import store

    seen = {}

    def fake_fetch(symbol):
        seen["symbol"] = symbol
        return _bond_series()

    monkeypatch.setattr(store, "fetch_bond_series", fake_fetch)

    result = openbb_client.get_bond_profile("edo0936")

    assert result == {
        "symbol": "EDO0936",
        "name": "Obligacje 10-letnie EDO",
        "series_code": "EDO",
        "issue_date": "2026-01-01",
        "maturity_date": "2036-01-01",
        "term_months": 120,
        "rate_rule": "fixed",
        "margin": "3.50",
        "fee_b": "3.00",
        "nominal": "100.00",
    }
    assert seen == {"symbol": "EDO0936"}
    mock_obb.equity.profile.assert_not_called()


@patch("src.openbb_client.obb")
def test_get_bond_profile_db_empty_falls_back_to_openbb(mock_obb, monkeypatch):
    _use_bond_db(monkeypatch)
    from openbb_obligacje import store

    monkeypatch.setattr(store, "fetch_bond_series", lambda symbol: None)
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame(
        [{"symbol": "EDO0936", "name": "Obligacje 10-letnie EDO"}]
    )
    mock_obb.equity.profile.return_value = mock_result

    result = openbb_client.get_bond_profile("EDO0936")

    assert result == {"symbol": "EDO0936", "name": "Obligacje 10-letnie EDO"}
    mock_obb.equity.profile.assert_called_once_with("EDO0936", provider="obligacje")


@patch("src.openbb_client.obb")
def test_get_corp_bond_profile_routes_biznesradar(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame(
        [{"symbol": "BST0327", "name": "Best S.A.", "asset_type": "corp_bond"}]
    )
    mock_obb.equity.profile.return_value = mock_result

    result = openbb_client.get_corp_bond_profile("BST0327")

    assert result["symbol"] == "BST0327"
    assert result["asset_type"] == "corp_bond"
    mock_obb.equity.profile.assert_called_once_with("BST0327", provider="biznesradar")


@patch("src.openbb_client.obb")
def test_get_corp_bond_profile_empty_returns_none(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame()
    mock_obb.equity.profile.return_value = mock_result

    assert openbb_client.get_corp_bond_profile("BST9999") is None


@patch("src.openbb_client.obb")
def test_get_corp_bond_profile_error_returns_none(mock_obb):
    mock_obb.equity.profile.side_effect = Exception("scrape failed")

    assert openbb_client.get_corp_bond_profile("BST0327") is None


@patch("src.openbb_client.obb")
def test_get_bond_profile_no_db_uses_pure_openbb_path(mock_obb, monkeypatch):
    monkeypatch.setattr(openbb_client.db, "database_url", lambda: None)
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame(
        [{"symbol": "EDO0936", "name": "Obligacje 10-letnie EDO"}]
    )
    mock_obb.equity.profile.return_value = mock_result

    result = openbb_client.get_bond_profile("EDO0936")

    assert result == {"symbol": "EDO0936", "name": "Obligacje 10-letnie EDO"}
    mock_obb.equity.profile.assert_called_once_with("EDO0936", provider="obligacje")


@patch("src.openbb_client.obb")
def test_symbol_currency_cache_is_bounded(mock_obb):
    """§73.4 — the currency memo is keyed on a caller-controlled ticker and these
    routes are unauthenticated, so an unbounded dict would grow for the life of
    the process. Same bound and same trade as `_pays_dividend`: dropping an entry
    costs one extra quote fetch, never a wrong answer.

    NOT the §73 memory leak — see the note on the dict in openbb_client. This is a
    defect on its own merits, found while walking §73.4's checklist.
    """
    openbb_client._symbol_currency_cache.clear()
    mock_obb.equity.price.quote.return_value = MagicMock(
        to_df=lambda: pd.DataFrame([{"currency": "USD"}])
    )
    # Shrink the cap so the test does not have to insert 20k entries.
    with patch.object(openbb_client, "SYMBOL_CURRENCY_MAX", 10):
        for i in range(40):
            openbb_client._remember_symbol_currency(f"SYM{i}", "USD")
        assert len(openbb_client._symbol_currency_cache) <= 10
        # The most recent write is always retained — a bounded cache that evicted
        # the newest key would turn a memory bound into a correctness bug.
        assert openbb_client._symbol_currency_cache.get("SYM39") == "USD"
        # The oldest were dropped, which is the point.
        assert "SYM0" not in openbb_client._symbol_currency_cache
    openbb_client._symbol_currency_cache.clear()


@patch("src.openbb_client.obb")
def test_symbol_currency_reads_through_the_bounded_store(mock_obb):
    """The write path must go through the bounding helper, not assign directly —
    a test that only exercised `_remember_symbol_currency` would pass even if
    `_symbol_currency` bypassed it."""
    openbb_client._symbol_currency_cache.clear()
    mock_obb.equity.price.quote.return_value = MagicMock(
        to_df=lambda: pd.DataFrame([{"currency": "GBP"}])
    )
    assert openbb_client._symbol_currency("TESTCO") == "GBP"
    assert openbb_client._symbol_currency_cache.get("TESTCO") == "GBP"
    openbb_client._symbol_currency_cache.clear()


@patch("src.openbb_client.obb")
def test_symbol_currency_does_not_cache_a_failure(mock_obb):
    """A None is a transient failure and must be retried, not remembered. Unchanged
    by §73.4 and worth pinning next to the bound: bounding a cache is exactly the
    kind of change that starts caching failures to save a lookup."""
    openbb_client._symbol_currency_cache.clear()
    mock_obb.equity.price.quote.side_effect = Exception("upstream down")
    assert openbb_client._symbol_currency("FAILCO") is None
    assert "FAILCO" not in openbb_client._symbol_currency_cache
