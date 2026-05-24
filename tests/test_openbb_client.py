import logging
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from openbb_client import get_dividend_history, get_dividend_yield
import openbb_client


@pytest.fixture(autouse=True)
def clear_pays_dividend_cache():
    openbb_client._pays_dividend.clear()
    yield
    openbb_client._pays_dividend.clear()


def _metrics_df(dividend_yield: float) -> pd.DataFrame:
    return pd.DataFrame([{"dividend_yield": dividend_yield}])


def _dividends_df() -> pd.DataFrame:
    df = pd.DataFrame(
        [{"amount": 0.25}, {"amount": 0.30}],
        index=pd.to_datetime(["2024-03-15", "2024-06-15"]),
    )
    df.index.name = "ex_dividend_date"
    return df


@patch("openbb_client.obb")
def test_get_dividend_yield_returns_decimal_string(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _metrics_df(2.456789)
    mock_obb.equity.fundamental.metrics.return_value = mock_result

    result = get_dividend_yield("AAPL")

    assert result == 2.46
    mock_obb.equity.fundamental.metrics.assert_called_once_with("AAPL", provider="yfinance")


@patch("openbb_client.obb")
def test_get_dividend_yield_fallback_to_fmp(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _metrics_df(1.5)
    mock_obb.equity.fundamental.metrics.side_effect = [Exception("yfinance down"), mock_ok]

    result = get_dividend_yield("AAPL")

    assert result == 1.50
    assert mock_obb.equity.fundamental.metrics.call_count == 2


@patch("openbb_client.obb")
def test_get_dividend_yield_fallback_logs_warning(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _metrics_df(1.5)
    mock_obb.equity.fundamental.metrics.side_effect = [Exception("yfinance down"), mock_ok]

    with patch("openbb_client.logger") as mock_logger:
        get_dividend_yield("AAPL")
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "yfinance" in str(call_args)
        assert "AAPL" in str(call_args)


@patch("openbb_client.obb")
def test_get_dividend_yield_all_providers_fail_returns_none(mock_obb):
    mock_obb.equity.fundamental.metrics.side_effect = Exception("fail")
    # dividends also fail → can't confirm non-payer → None
    mock_obb.equity.fundamental.dividends.side_effect = Exception("fail")
    assert get_dividend_yield("AAPL") is None


@patch("openbb_client.obb")
def test_get_dividend_yield_non_payer_returns_zero(mock_obb):
    mock_obb.equity.fundamental.metrics.side_effect = Exception("fail")
    empty = MagicMock()
    empty.to_df.return_value = pd.DataFrame()
    mock_obb.equity.fundamental.dividends.return_value = empty
    assert get_dividend_yield("AAPL") == 0.0


@patch("openbb_client.obb")
def test_get_dividend_yield_non_payer_caches_result(mock_obb):
    mock_obb.equity.fundamental.metrics.side_effect = Exception("fail")
    empty = MagicMock()
    empty.to_df.return_value = pd.DataFrame()
    mock_obb.equity.fundamental.dividends.return_value = empty

    get_dividend_yield("AAPL")
    get_dividend_yield("AAPL")
    # 3 providers tried on first call, 0 on second (cached)
    assert mock_obb.equity.fundamental.dividends.call_count == 3


@patch("openbb_client.obb")
def test_get_dividend_yield_empty_df_returns_none(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame()
    mock_obb.equity.fundamental.metrics.return_value = mock_result
    assert get_dividend_yield("AAPL") is None


@patch("openbb_client.obb")
def test_get_dividend_history_returns_list(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _dividends_df()
    mock_obb.equity.fundamental.dividends.return_value = mock_result

    result = get_dividend_history("AAPL")

    assert result == [
        {"date": "2024-03-15", "amount": "0.2500"},
        {"date": "2024-06-15", "amount": "0.3000"},
    ]


@patch("openbb_client.obb")
def test_get_dividend_history_fallback_to_fmp(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _dividends_df()
    mock_obb.equity.fundamental.dividends.side_effect = [Exception("fail"), mock_ok]

    result = get_dividend_history("AAPL")
    assert result is not None
    assert len(result) == 2


@patch("openbb_client.obb")
def test_get_dividend_history_all_providers_fail_returns_empty(mock_obb):
    mock_obb.equity.fundamental.dividends.side_effect = Exception("fail")
    assert get_dividend_history("AAPL") == []


@patch("openbb_client.obb")
def test_get_dividend_history_non_payer_caches_result(mock_obb):
    empty = MagicMock()
    empty.to_df.return_value = pd.DataFrame()
    mock_obb.equity.fundamental.dividends.return_value = empty

    get_dividend_history("AAPL")
    get_dividend_history("AAPL")
    # 3 providers tried on first call (all return empty → cached False), 0 on second
    assert mock_obb.equity.fundamental.dividends.call_count == 3


@patch("openbb_client.obb")
def test_get_dividend_history_empty_df_returns_empty(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = pd.DataFrame()
    mock_obb.equity.fundamental.dividends.return_value = mock_result
    assert get_dividend_history("AAPL") == []
