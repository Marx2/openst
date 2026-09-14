"""Shared scraper unit tests (D77 16.3) — mock httpx.get against captured fixtures."""

from datetime import date

import httpx
import pytest

from openbb_biznesradar import scraper
from openbb_biznesradar.models.bond_historical import BOND_COLUMNS
from openbb_biznesradar.models.fund_historical import FUND_COLUMNS
from openbb_biznesradar.scraper import (
    BiznesRadarNotFound,
    _scrape_pages,
    strip_wa_suffix,
)


# ---------------------------------------------------------------------------
# strip_wa_suffix
# ---------------------------------------------------------------------------


def test_strip_wa_suffix_matrix():
    assert strip_wa_suffix("NNEP25.TFI.WA") == "NNEP25.TFI"
    assert strip_wa_suffix("BST0327.WA") == "BST0327"
    assert strip_wa_suffix("NNEP25.TFI") == "NNEP25.TFI"
    assert strip_wa_suffix("AAPL") == "AAPL"


# ---------------------------------------------------------------------------
# table extraction from the captured fixtures
# ---------------------------------------------------------------------------


def test_fund_table_extraction(httpx_mock, read_fixture):
    httpx_mock([(read_fixture("NNEP25.TFI.html"), 200)])
    rows = list(
        _scrape_pages("NNEP25.TFI", date(2000, 1, 1), date(2026, 12, 31), 0.0, FUND_COLUMNS)
    )
    assert len(rows) == 50
    assert rows[0] == {"date": date(2026, 9, 11), "close": 14.66}
    assert rows[1] == {"date": date(2026, 9, 10), "close": 14.65}
    assert rows[2] == {"date": date(2026, 9, 9), "close": 14.70}


def test_bond_table_extraction(httpx_mock, read_fixture):
    httpx_mock([(read_fixture("BST0327.html"), 200)])
    rows = list(
        _scrape_pages(
            "BST0327.WA", date(2000, 1, 1), date(2026, 12, 31), 0.0, BOND_COLUMNS
        )
    )
    assert len(rows) == 50
    assert rows[0] == {
        "date": date(2026, 9, 10),
        "open": 101.30,
        "high": 101.30,
        "low": 101.30,
        "close": 101.30,
        "volume": 60,
    }
    assert rows[1] == {
        "date": date(2026, 9, 9),
        "open": 101.50,
        "high": 101.50,
        "low": 101.00,
        "close": 101.00,
        "volume": 45,
    }


# ---------------------------------------------------------------------------
# pagination / range behavior
# ---------------------------------------------------------------------------


def test_date_range_inclusive_bounds(httpx_mock, build_page):
    html = build_page(rows=[("11.09.2026", "1.00"), ("10.09.2026", "2.00")], nxt=True)
    httpx_mock([(html, 200)])
    rows = list(
        _scrape_pages("AAPL", date(2026, 9, 10), date(2026, 9, 11), 0.0, FUND_COLUMNS)
    )
    assert [r["date"] for r in rows] == [date(2026, 9, 11), date(2026, 9, 10)]
    httpx_mock([(html, 200)])
    rows = list(
        _scrape_pages("AAPL", date(2026, 1, 1), date(2026, 9, 10), 0.0, FUND_COLUMNS)
    )
    assert [r["date"] for r in rows] == [date(2026, 9, 10)]


def test_early_stop_before_start_date(httpx_mock, build_page):
    html = build_page(
        rows=[("11.09.2026", "14.66"), ("10.09.2026", "14.65"), ("31.12.2025", "14.00")],
        nxt=True,
    )
    calls = httpx_mock([(html, 200)])
    rows = list(
        _scrape_pages("NNEP25.TFI", date(2026, 1, 1), date(2026, 12, 31), 0.0, FUND_COLUMNS)
    )
    assert [r["date"] for r in rows] == [date(2026, 9, 11), date(2026, 9, 10)]
    assert len(calls) == 1  # never fetched the next page


def test_sleep_between_pages_not_before_first(monkeypatch, build_page):
    p1 = build_page(rows=[("11.09.2026", "14.66")], nxt=True)
    p2 = build_page(rows=[("10.09.2026", "14.65")], nxt=False)
    events = []

    def fake_get(url, **kwargs):
        events.append("get")
        html = p1 if len(events) == 1 else p2
        return httpx.Response(200, text=html, request=httpx.Request("GET", url))

    def fake_sleep(seconds):
        events.append("sleep")

    monkeypatch.setattr(scraper.httpx, "get", fake_get)
    monkeypatch.setattr(scraper.time, "sleep", fake_sleep)
    rows = list(
        _scrape_pages("NNEP25.TFI", date(2000, 1, 1), date(2026, 12, 31), 5.0, FUND_COLUMNS)
    )
    assert len(rows) == 2
    assert events == ["get", "sleep", "get"]


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------


def test_raises_on_non_200(httpx_mock):
    httpx_mock([("", 404)])
    with pytest.raises(BiznesRadarNotFound):
        list(
            _scrape_pages("BST0327", date(2000, 1, 1), date(2026, 12, 31), 0.0, BOND_COLUMNS)
        )


def test_raises_on_missing_table(httpx_mock):
    httpx_mock([("<html><body>no table here</body></html>", 200)])
    with pytest.raises(BiznesRadarNotFound):
        list(
            _scrape_pages("BST0327", date(2000, 1, 1), date(2026, 12, 31), 0.0, BOND_COLUMNS)
        )