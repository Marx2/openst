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

# ---------------------------------------------------------------------------
# priceCurrency meta tag (45.1)
# ---------------------------------------------------------------------------


def test_currency_from_soup_parsing(httpx_mock, read_fixture):
    httpx_mock([(read_fixture("INGAKC.TFI_notowania.html"), 200)])
    name, currency = scraper.probe_notowania_full("INGAKC.TFI")
    assert name == "ING Akcji (ING Parasol FIO)"
    assert currency == "PLN"


def test_currency_missing_tag_returns_none():
    html = (
        "<html><head><title>Notowania XYZ- BiznesRadar.pl</title></head>"
        "<body><table class='qTableFull'></table></body></html>"
    )
    from bs4 import BeautifulSoup

    assert scraper._currency_from_soup(BeautifulSoup(html, "lxml")) is None


def test_default_currency_for_symbol_matrix():
    assert scraper.default_currency_for_symbol("NNEP25.TFI") == "PLN"
    assert scraper.default_currency_for_symbol("NNEP25.tfi") == "PLN"
    assert scraper.default_currency_for_symbol("KSENG.FIZ") == "PLN"
    assert scraper.default_currency_for_symbol("NNEP25.TFI.WA") is None  # suffix passes through, not .TFI
    assert scraper.default_currency_for_symbol("BST0327.WA") is None
    assert scraper.default_currency_for_symbol("AAPL") is None
    assert scraper.default_currency_for_symbol("") is None


def test_currency_empty_content_returns_none():
    html = (
        "<html><head><title>Notowania XYZ- BiznesRadar.pl</title></head>"
        "<body><meta itemprop='priceCurrency' content=''>"
        "<table class='qTableFull'></table></body></html>"
    )
    from bs4 import BeautifulSoup

    assert scraper._currency_from_soup(BeautifulSoup(html, "lxml")) is None


def test_scrape_quote_includes_currency(httpx_mock, read_fixture):
    httpx_mock([(read_fixture("INGAKC.TFI_notowania.html"), 200)])
    result = scraper.scrape_quote("INGAKC.TFI")
    assert result is not None
    assert result["name"] == "ING Akcji (ING Parasol FIO)"
    assert result["last_price"] == 812.36
    assert result["currency"] == "PLN"


def test_nnep65_fixture_carries_currency(httpx_mock, read_fixture):
    """47.1 — the captured NNEP65.TFI page truth: it DOES carry priceCurrency.

    The live page carries the meta and a fresh scrape now returns PLN (a stale
    openst Redis quote — cached before biznesradar added the tag — was why prod
    showed no currency).  This pins the fixture bytes: re-capture must still
    yield ``PLN`` or the test fails.
    """
    httpx_mock([(read_fixture("NNEP65.TFI_notowania.html"), 200)])
    result = scraper.scrape_quote("NNEP65.TFI")
    assert result is not None
    assert result["currency"] == "PLN"
    assert result["name"] == "ING Emerytura 2065 (ING Emerytura SFIO)"


def test_scrape_quote_missing_tag_omits_key(httpx_mock):
    """47.2 (c) — meta absent + non-Polish symbol ('XAUR') → key omitted."""
    html = (
        "<html><head><title>Notowania XAUR- BiznesRadar.pl</title></head>"
        "<body><table class='qTableFull'></table>"
        "<table><tr><td id='pr_t_close'>14.66</td></tr></table></body></html>"
    )
    httpx_mock([(html, 200)])
    result = scraper.scrape_quote("XAUR")
    assert result is not None
    assert result["last_price"] == 14.66
    assert "currency" not in result


def test_scrape_quote_meta_absent_tfi_defaults_pln(httpx_mock):
    """47.2 (b) — meta absent + .TFI symbol → PLN from the universe default."""
    html = (
        "<html><head><title>Notowania NNEP25.TFI- BiznesRadar.pl</title></head>"
        "<body><table class='qTableFull'></table>"
        "<table><tr><td id='pr_t_close'>14.66</td></tr></table></body></html>"
    )
    httpx_mock([(html, 200)])
    result = scraper.scrape_quote("NNEP25.TFI")
    assert result is not None
    assert result["last_price"] == 14.66
    assert result["currency"] == "PLN"


def test_scrape_quote_meta_absent_fiz_defaults_pln(httpx_mock):
    """47.2 (b) — .FIZ symbol with no meta also defaults to PLN."""
    html = (
        "<html><head><title>Notowania KSENG.FIZ- BiznesRadar.pl</title></head>"
        "<body><table class='qTableFull'></table>"
        "<table><tr><td id='pr_t_close'>120.00</td></tr></table></body></html>"
    )
    httpx_mock([(html, 200)])
    result = scraper.scrape_quote("KSENG.FIZ")
    assert result is not None
    assert result["currency"] == "PLN"


# ---------------------------------------------------------------------------
# first-NAV probe (45.5)
# ---------------------------------------------------------------------------


def test_probe_first_nav_reads_oldest_page(httpx_mock, read_fixture):
    # page 1 (footer -> last page 143), then the last page (oldest row 1998-03-11)
    httpx_mock([
        (read_fixture("INGAKC.TFI_history_p1.html"), 200),
        (read_fixture("INGAKC.TFI_history_last.html"), 200),
    ])
    assert scraper.probe_first_nav("INGAKC.TFI") == date(1998, 3, 11)


def test_probe_first_nav_strips_wa(httpx_mock, read_fixture):
    calls = httpx_mock([
        (read_fixture("INGAKC.TFI_history_p1.html"), 200),
        (read_fixture("INGAKC.TFI_history_last.html"), 200),
    ])
    assert scraper.probe_first_nav("INGAKC.TFI.WA") == date(1998, 3, 11)
    assert all("INGAKC.TFI" in u for u in calls)


def test_probe_first_nav_single_page_returns_none(httpx_mock, build_page):
    # a single-page history has no pages_pos link -> cannot locate oldest page
    page = build_page([("11.09.2026", "10.00"), ("10.09.2026", "9.90")], nxt=False)
    httpx_mock([(page, 200)])
    assert scraper.probe_first_nav("NNEP99.TFI") is None


def test_probe_first_nav_404_returns_none(httpx_mock):
    httpx_mock([("", 404)])
    assert scraper.probe_first_nav("ZZZZZ.TFI") is None


def test_probe_first_nav_last_page_no_table_returns_none(httpx_mock, build_page):
    httpx_mock([
        (build_page([("01.01.2026", "1")], nxt=True), 200),
        ("<html><body>no table</body></html>", 200),
    ])
    assert scraper.probe_first_nav("NNEP99.TFI") is None


def test_last_page_number_parsing(httpx_mock, read_fixture):
    from bs4 import BeautifulSoup

    html = read_fixture("INGAKC.TFI_history_p1.html")
    # the footer's highest pages_pos index is the true last page
    assert scraper._last_page_number(BeautifulSoup(html, "lxml")) == 143
