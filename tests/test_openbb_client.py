import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.openbb_client import get_dividend_history, get_dividend_yield
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
    # 3 providers tried on first call, 0 on second (cached)
    assert mock_obb.equity.fundamental.dividends.call_count == 3


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
    # 3 providers tried on first call (all return empty → cached False), 0 on second
    assert mock_obb.equity.fundamental.dividends.call_count == 3


@patch("src.openbb_client.obb")
def test_get_dividend_history_empty_df_returns_empty(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame()
    mock_obb.equity.fundamental.dividends.return_value = mock_result
    assert get_dividend_history("AAPL") == []


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
    assert "yfinance" in openbb_client._provider_blocked_until
    assert mock_obb.equity.fundamental.dividends.call_count == 2


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
    openbb_client._provider_blocked_until["yfinance"] = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _dividends_df()
    mock_obb.equity.fundamental.dividends.return_value = mock_ok

    result = get_dividend_history("AAPL")

    assert result is not None
    first_call = mock_obb.equity.fundamental.dividends.call_args_list[0]
    assert first_call[1]["provider"] == "fmp"
