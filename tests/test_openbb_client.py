import logging
import types
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src import openbb_client
from src.openbb_client import (
    get_calendar,
    get_dividend_history,
    get_dividend_yield,
    get_fundamentals,
    get_metrics,
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
    # 4 providers tried on first call, 0 on second (cached)
    assert mock_obb.equity.fundamental.dividends.call_count == 4


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


@patch("src.openbb_client.obb")
def test_get_price_history_all_providers_fail_returns_none(mock_obb):
    mock_obb.equity.price.historical.side_effect = Exception("connection error")

    result = get_price_history("AAPL", "2025-08-01", "2026-08-01")

    assert result is None
    assert mock_obb.equity.price.historical.call_count == 3


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
    # 4 providers tried on first call (all return empty → cached False), 0 on second
    assert mock_obb.equity.fundamental.dividends.call_count == 4


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
def test_get_metrics_returns_first_record(mock_obb):
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

    assert result == {"target_high": 300.0, "target_low": 180.0, "target_median": 250.0}
    mock_obb.equity.estimates.consensus.assert_called_once_with("AAPL", provider="fmp")


@patch("src.openbb_client.obb")
def test_get_projections_falls_back_to_yfinance(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _consensus_df()
    mock_obb.equity.estimates.consensus.side_effect = [Exception("yfinance down"), mock_ok]

    result = get_projections("AAPL")

    assert result is not None
    assert mock_obb.equity.estimates.consensus.call_count == 2


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


@patch("src.openbb_client.obb")
def test_get_ohlcv_history_all_fail_returns_none(mock_obb):
    mock_obb.equity.price.historical.side_effect = Exception("timeout")
    assert openbb_client.get_ohlcv_history("AAPL", "2025-08-01", "2026-08-01") is None


@patch("src.openbb_client.obb")
def test_get_fundamentals_calls_statement_and_period(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _income_df()
    mock_obb.equity.fundamental.income.return_value = mock_result

    result = get_fundamentals("AAPL", "income", "annual")

    assert [r["fiscal_year"] for r in result] == [2024, 2023]
    assert result[0]["period_ending"] == "2024-09-28 00:00:00"
    mock_obb.equity.fundamental.income.assert_called_once_with(
        "AAPL", period="annual", provider="fmp"
    )


@patch("src.openbb_client.obb")
def test_get_fundamentals_falls_back_to_yfinance(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _income_df()
    mock_obb.equity.fundamental.balance.side_effect = [Exception("fail"), mock_ok]

    result = get_fundamentals("AAPL", "balance", "quarter")

    assert len(result) == 2
    assert mock_obb.equity.fundamental.balance.call_count == 2


@patch("src.openbb_client.obb")
def test_get_fundamentals_all_fail_returns_empty(mock_obb):
    mock_obb.equity.fundamental.cash.side_effect = Exception("fail")
    assert get_fundamentals("AAPL", "cash", "annual") == []


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


@patch("src.openbb_client.obb")
def test_search_equities_uses_sec_provider(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _search_df()
    mock_obb.equity.search.return_value = mock_result

    result = search_equities("apple")

    assert result == [{"cik": 320193, "name": "Apple Inc", "symbol": "AAPL"}]
    mock_obb.equity.search.assert_called_once_with("apple", provider="sec")


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
