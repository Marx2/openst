"""CalendarDividendFetcher + Polish short-date parser tests (plan §52.2).

Tests run against the captured 52.1 fixtures
(``tests/fixtures/biznesradar-dywidendy/``) with the plugin conftest's
``httpx_mock`` (patches ``scraper.httpx.get``).
"""

from datetime import date
from pathlib import Path

import pytest

from openbb_biznesradar import scraper
from openbb_biznesradar.models.calendar_dividend import CalendarDividendFetcher

DYWIDENDY_FIXTURES = Path(__file__).parents[3] / "tests" / "fixtures" / "biznesradar-dywidendy"


def read_dywidendy(name: str) -> str:
    return (DYWIDENDY_FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# parse_pl_short_date
# ---------------------------------------------------------------------------


def test_parse_pl_short_date_valid():
    assert scraper.parse_pl_short_date("05 sie 26") == date(2026, 8, 5)
    assert scraper.parse_pl_short_date("28 wrz 26") == date(2026, 9, 28)
    assert scraper.parse_pl_short_date("30 gru 26") == date(2026, 12, 30)
    assert scraper.parse_pl_short_date("17 gru 25") == date(2025, 12, 17)


def test_parse_pl_short_date_all_months():
    """52.1 forms: sty/lut/mar/kwi/maj/cze/lip/sie/wrz/paź/lis/gru all parse."""
    for abbr, mon in scraper._PL_MONTHS.items():
        assert scraper.parse_pl_short_date(f"01 {abbr} 26") == date(2026, mon, 1)


def test_parse_pl_short_date_bad():
    assert scraper.parse_pl_short_date("bd.") is None
    assert scraper.parse_pl_short_date("") is None
    assert scraper.parse_pl_short_date("aa 99") is None
    assert scraper.parse_pl_short_date("32 sty 26") is None  # invalid day
    assert scraper.parse_pl_short_date("01 zzz 26") is None  # unknown month


# ---------------------------------------------------------------------------
# _dywidendy_url
# ---------------------------------------------------------------------------


def test_dywidendy_url_default_sort():
    assert scraper._dywidendy_url(2026) == (
        "https://www.biznesradar.pl/dywidendy/,2026,4,2"
    )
    assert scraper._dywidendy_url(2025) == (
        "https://www.biznesradar.pl/dywidendy/,2025,4,2"
    )


# ---------------------------------------------------------------------------
# scrape_dividend_calendar against the captured fixtures
# ---------------------------------------------------------------------------

_2026_WINDOW = [
    {
        "ex_dividend_date": date(2026, 9, 28),
        "payment_date": date(2026, 12, 30),
        "amount": 0.22,
        "status": "uchwalona",
        "symbol": "NTT",
    },
    {
        "ex_dividend_date": date(2026, 8, 26),
        "payment_date": date(2026, 12, 23),
        "amount": 0.01,
        "status": "uchwalona",
        "symbol": "VRB",
    },
]


def test_scrape_dividend_calendar_single_year(httpx_mock):
    calls = httpx_mock([(read_dywidendy("dywidendy-2026.html"), 200)])
    rows = scraper.scrape_dividend_calendar(date(2026, 1, 1), date(2026, 12, 31))
    assert calls == ["https://www.biznesradar.pl/dywidendy/,2026,4,2"]
    # 207 data rows total, minus the one STX-style row with no parseable date
    assert len(rows) == 206
    assert _2026_WINDOW[0] in rows
    assert _2026_WINDOW[1] in rows


def test_scrape_dividend_calendar_window_filter(httpx_mock):
    """rows with ex-/payment date inside [start, end] survive; others dropped."""
    httpx_mock([(read_dywidendy("dywidendy-2026.html"), 200)])
    rows = scraper.scrape_dividend_calendar(date(2026, 12, 23), date(2026, 12, 31))
    symbols = {r["symbol"] for r in rows}
    assert "NTT" in symbols
    assert "VRB" in symbols
    assert all(
        (r["payment_date"] or r["ex_dividend_date"]) >= date(2026, 12, 23)
        for r in rows
    )


def test_scrape_dividend_calendar_none_dates_skipped(httpx_mock):
    """A row with no ex- and no payment date at all is dropped."""
    html = (
        "<html><body><table>"
        "<tr><th>Profil</th><th>Dywidenda za rok</th><th>Data WZA</th>"
        "<th>Ostatnie notowanie z prawem do dywidendy</th><th>Dzień wypłaty</th>"
        "<th>Dywidenda na akcję</th><th>Stopa dywidendy*</th><th>Status</th></tr>"
        "<tr><td>STX (STALEXP)</td><td>2025</td><td>05 sie 26</td>"
        "<td><span class='value--light'>bd.</span></td>"
        "<td class='value--bold'><span class='value--light'>bd.</span></td>"
        "<td>0,74 PLN</td><td></td><td></td></tr>"
        "</table></body></html>"
    )
    httpx_mock([(html, 200)])
    rows = scraper.scrape_dividend_calendar(date(2026, 1, 1), date(2026, 12, 31))
    assert rows == []


def test_scrape_dividend_calendar_http_error_skips(httpx_mock):
    httpx_mock([("", 500)])
    assert scraper.scrape_dividend_calendar(date(2026, 1, 1), date(2026, 12, 31)) == []


# ---------------------------------------------------------------------------
# CalendarDividendFetcher
# ---------------------------------------------------------------------------


def test_transform_query_maps_dates():
    query = CalendarDividendFetcher.transform_query(
        {"start_date": "2026-01-01", "end_date": "2026-12-31"}
    )
    assert query.start_date == date(2026, 1, 1)
    assert query.end_date == date(2026, 12, 31)


def test_extract_data_defaults_to_current_year(monkeypatch):
    seen = {}

    def fake_scrape(start, end):
        seen["start"] = start
        seen["end"] = end
        return []

    import openbb_biznesradar.models.calendar_dividend as cd

    monkeypatch.setattr(cd, "scrape_dividend_calendar", fake_scrape)
    query = CalendarDividendFetcher.transform_query({})
    assert CalendarDividendFetcher.extract_data(query) == []
    assert seen["start"].year == date.today().year
    assert seen["start"].month == 1 and seen["start"].day == 1
    assert seen["end"].month == 12 and seen["end"].day == 31


def test_extract_data_reversed_window_returns_empty(monkeypatch):
    def fake_scrape(start, end):  # pragma: no cover - should not be reached
        raise AssertionError("scraper must not be called for a reversed window")

    monkeypatch.setattr(scraper, "scrape_dividend_calendar", fake_scrape)
    query = CalendarDividendFetcher.transform_query(
        {"start_date": "2026-06-01", "end_date": "2026-01-01"}
    )
    assert CalendarDividendFetcher.extract_data(query) == []


def test_transform_data_builds_standard_model(monkeypatch):
    query = CalendarDividendFetcher.transform_query({})
    data = [
        {
            "ex_dividend_date": date(2026, 9, 28),
            "payment_date": date(2026, 12, 30),
            "amount": 0.22,
            "status": "uchwalona",
            "symbol": "NTT",
        }
    ]
    out = CalendarDividendFetcher.transform_data(query, data)
    assert out[0].symbol == "NTT"
    assert out[0].ex_dividend_date == date(2026, 9, 28)
    assert out[0].payment_date == date(2026, 12, 30)
    assert out[0].amount == 0.22
    assert out[0].status == "uchwalona"


def test_registered_under_calendar_dividend():
    from openbb_biznesradar import biznesradar_provider

    assert biznesradar_provider.fetcher_dict["CalendarDividend"] is CalendarDividendFetcher


import pytest  # noqa: F401  (kept for parity with sibling test modules)