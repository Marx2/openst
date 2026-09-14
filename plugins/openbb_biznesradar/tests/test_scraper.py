"""Shared scraper unit tests (D77 16.3) — mock httpx.get against captured fixtures."""

from datetime import date
from pathlib import Path

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

FIXTURES = Path(__file__).parents[3] / "tests" / "fixtures" / "biznesradar"

TERMINAL_PAGE = "<html><body><table class='qTableFull'></table></body></html>"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _page(rows: list[tuple], *, nxt: bool) -> str:
    body = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows
    )
    footer = (
        '<div class="buttons pages"><a class="pages_right" title="następna"></a></div>'
        if nxt
        else '<div class="buttons pages"></div>'
    )
    return f"<html><body><table class='qTableFull'>{body}</table>{footer}</body></html>"


def _set_fetch(monkeypatch, pages: list[tuple[str, int]]):
    """Patch httpx.get to return ``pages`` in order, then a terminal page."""
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if pages:
            html, status = pages.pop(0)
        else:
            html, status = TERMINAL_PAGE, 200
        return httpx.Response(status, text=html, request=httpx.Request("GET", url))

    monkeypatch.setattr(scraper.httpx, "get", fake_get)
    return calls


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


def test_fund_table_extraction(monkeypatch):
    _set_fetch(monkeypatch, [(_fixture("NNEP25.TFI.html"), 200)])
    rows = list(
        _scrape_pages("NNEP25.TFI", date(2000, 1, 1), date(2026, 12, 31), 0.0, FUND_COLUMNS)
    )
    assert len(rows) == 50
    assert rows[0] == {"date": date(2026, 9, 11), "close": 14.66}
    assert rows[1] == {"date": date(2026, 9, 10), "close": 14.65}
    assert rows[2] == {"date": date(2026, 9, 9), "close": 14.70}


def test_bond_table_extraction(monkeypatch):
    _set_fetch(monkeypatch, [(_fixture("BST0327.html"), 200)])
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


def test_date_range_inclusive_bounds(monkeypatch):
    html = _page(rows=[("11.09.2026", "1.00"), ("10.09.2026", "2.00")], nxt=True)
    _set_fetch(monkeypatch, [(html, 200)])
    rows = list(
        _scrape_pages("AAPL", date(2026, 9, 10), date(2026, 9, 11), 0.0, FUND_COLUMNS)
    )
    assert [r["date"] for r in rows] == [date(2026, 9, 11), date(2026, 9, 10)]
    _set_fetch(monkeypatch, [(html, 200)])
    rows = list(
        _scrape_pages("AAPL", date(2026, 1, 1), date(2026, 9, 10), 0.0, FUND_COLUMNS)
    )
    assert [r["date"] for r in rows] == [date(2026, 9, 10)]


def test_early_stop_before_start_date(monkeypatch):
    html = _page(
        rows=[("11.09.2026", "14.66"), ("10.09.2026", "14.65"), ("31.12.2025", "14.00")],
        nxt=True,
    )
    calls = _set_fetch(monkeypatch, [(html, 200)])
    rows = list(
        _scrape_pages("NNEP25.TFI", date(2026, 1, 1), date(2026, 12, 31), 0.0, FUND_COLUMNS)
    )
    assert [r["date"] for r in rows] == [date(2026, 9, 11), date(2026, 9, 10)]
    assert len(calls) == 1  # never fetched the next page


def test_sleep_between_pages_not_before_first(monkeypatch):
    p1 = _page(rows=[("11.09.2026", "14.66")], nxt=True)
    p2 = _page(rows=[("10.09.2026", "14.65")], nxt=False)
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


def test_raises_on_non_200(monkeypatch):
    _set_fetch(monkeypatch, [("", 404)])
    with pytest.raises(BiznesRadarNotFound):
        list(
            _scrape_pages("BST0327", date(2000, 1, 1), date(2026, 12, 31), 0.0, BOND_COLUMNS)
        )


def test_raises_on_missing_table(monkeypatch):
    _set_fetch(monkeypatch, [("<html><body>no table here</body></html>", 200)])
    with pytest.raises(BiznesRadarNotFound):
        list(
            _scrape_pages("BST0327", date(2000, 1, 1), date(2026, 12, 31), 0.0, BOND_COLUMNS)
        )