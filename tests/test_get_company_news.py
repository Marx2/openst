import types
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import src.openbb_client as openbb_client
from src.openbb_client import get_company_news


@pytest.fixture(autouse=True)
def clear_caches():
    openbb_client._provider_blocked_until.clear()
    yield
    openbb_client._provider_blocked_until.clear()


def _polygon_df() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "title": "Apple launches new iPhone",
                "url": "https://example.com/iphone",
                "symbols": "AAPL,NVDA",
                "source": "Jane Doe",
                "publisher": {"name": "The Motley Fool"},
                "text": "Apple unveiled its latest iPhone today.",
            },
            {
                "title": "Nvidia earnings beat",
                "url": "https://example.com/nvda",
                "symbols": None,
                "source": "John Smith",
                "publisher": None,
                "text": "Nvidia reported strong earnings.",
            },
        ],
        index=pd.to_datetime(["2026-09-07 16:02:29+00:00", "2026-09-08 08:10:00+00:00"]),
    )
    df.index.name = "date"
    return df


def _fmp_df() -> pd.DataFrame:
    df = pd.DataFrame(
        [{"title": "FMP headline", "url": "https://fmp.example.com/a", "symbols": "AAPL"}],
        index=pd.to_datetime(["2026-09-05 10:00:00+00:00"]),
    )
    df.index.name = "date"
    return df


# ---------------------------------------------------------------------------
# get_company_news — mapping & translation
# ---------------------------------------------------------------------------


@patch("src.openbb_client.obb")
def test_get_company_news_maps_records(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _polygon_df()
    mock_obb.news.company.return_value = mock_result

    rows = get_company_news("AAPL", limit=10)

    assert rows == [
        {
            "date": "2026-09-07T16:02:29+00:00",
            "title": "Apple launches new iPhone",
            "text": "Apple unveiled its latest iPhone today.",
            "url": "https://example.com/iphone",
            "symbols": ["AAPL", "NVDA"],
            "source": "The Motley Fool",
        },
        {
            "date": "2026-09-08T08:10:00+00:00",
            "title": "Nvidia earnings beat",
            "text": "Nvidia reported strong earnings.",
            "url": "https://example.com/nvda",
            "symbols": [],
            "source": "John Smith",
        },
    ]
    mock_obb.news.company.assert_called_once_with(
        symbol="AAPL", limit=10, provider="polygon"
    )


@patch("src.openbb_client.obb")
def test_get_company_news_default_limit(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _polygon_df()
    mock_obb.news.company.return_value = mock_result

    get_company_news("AAPL")

    assert mock_obb.news.company.call_args.kwargs["limit"] == 50


@patch("src.openbb_client.obb")
def test_get_company_news_passes_dates(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _polygon_df()
    mock_obb.news.company.return_value = mock_result

    get_company_news("AAPL", start_date="2026-08-01", end_date="2026-09-01")

    args = mock_obb.news.company.call_args.kwargs
    assert args["start_date"] == "2026-08-01"
    assert args["end_date"] == "2026-09-01"


@patch("src.openbb_client.obb")
def test_get_company_news_fallbacks_to_fmp(mock_obb):
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _fmp_df()
    mock_obb.news.company.side_effect = [Exception("402 payment required"), mock_ok]

    rows = get_company_news("AAPL", limit=5)

    assert rows == [
        {
            "date": "2026-09-05T10:00:00+00:00",
            "title": "FMP headline",
            "text": None,
            "url": "https://fmp.example.com/a",
            "symbols": ["AAPL"],
            "source": None,
        }
    ]
    assert "polygon" in openbb_client._provider_blocked_until
    assert mock_obb.news.company.call_count == 2
    # second call is fmp
    assert mock_obb.news.company.call_args_list[1].kwargs["provider"] == "fmp"


@patch("src.openbb_client.obb")
def test_get_company_news_explicit_provider(mock_obb):
    mock_result = MagicMock()
    mock_result.to_df.return_value = _polygon_df()
    mock_obb.news.company.return_value = mock_result

    get_company_news("AAPL", provider="polygon")

    mock_obb.news.company.assert_called_once_with(
        symbol="AAPL", limit=50, provider="polygon"
    )


@patch("src.openbb_client.obb")
def test_get_company_news_yfinance_symbols_none_sources_outlet(mock_obb):
    df = pd.DataFrame(
        [{"title": "WSJ", "url": "https://example.com/w", "symbols": None, "source": "Bloomberg"}],
        index=pd.to_datetime(["2026-09-08 06:05:00+00:00"]),
    )
    mock_result = MagicMock()
    mock_result.to_df.return_value = df
    mock_obb.news.company.return_value = mock_result

    rows = get_company_news("AAPL")

    assert rows[0]["symbols"] == []
    assert rows[0]["source"] == "Bloomberg"


# ---------------------------------------------------------------------------
# get_company_news — provider fallback edge cases
# ---------------------------------------------------------------------------


@patch("src.openbb_client.obb")
def test_get_company_news_empty_df_tries_next_provider(mock_obb):
    empty = MagicMock()
    empty.to_df.return_value = pd.DataFrame()
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _polygon_df()
    mock_obb.news.company.side_effect = [empty, mock_ok]

    rows = get_company_news("AAPL")

    assert len(rows) == 2
    assert mock_obb.news.company.call_count == 2


@patch("src.openbb_client.obb")
def test_get_company_news_invalid_ticker_returns_empty(mock_obb):
    mock_obb.news.company.side_effect = Exception("not found for symbol FAKE")

    rows = get_company_news("FAKE")

    assert rows == []
    assert mock_obb.news.company.call_count == 1


@patch("src.openbb_client.obb")
def test_get_company_news_all_providers_fail_returns_empty(mock_obb):
    mock_obb.news.company.side_effect = Exception("connection error")

    rows = get_company_news("AAPL")

    assert rows == []
    assert mock_obb.news.company.call_count == len(openbb_client.COMPANY_NEWS_PROVIDERS)


@patch("src.openbb_client.obb")
def test_get_company_news_blocked_provider_skipped(mock_obb):
    openbb_client._provider_blocked_until["polygon"] = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_ok = MagicMock()
    mock_ok.to_df.return_value = _fmp_df()
    mock_obb.news.company.return_value = mock_ok

    rows = get_company_news("AAPL")

    assert rows
    assert mock_obb.news.company.call_args_list[0].kwargs["provider"] == "fmp"


def test_split_symbols_variants():
    assert openbb_client._split_symbols("AAPL,NVDA, msft ") == ["AAPL", "NVDA", "MSFT"]
    assert openbb_client._split_symbols(["aapl", "nvda"]) == ["AAPL", "NVDA"]
    assert openbb_client._split_symbols(None) == []
    assert openbb_client._split_symbols("") == []
