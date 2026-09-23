"""dividendmax client tests (plan §52.4) — parsers + resolution + page scrape.

Run against the captured 52.3 fixtures (``tests/fixtures/dividendmax/``) with
the plugin conftest's ``httpx_mock`` (patches ``client.httpx.get``).
"""

from datetime import date

from openbb_dividendmax import client
from openbb_dividendmax.client import (
    parse_en_date,
    parse_subunit_amount,
    resolve_path,
    scrape_dividend_history,
)


# ---------------------------------------------------------------------------
# parse_en_date
# ---------------------------------------------------------------------------


def test_parse_en_date_valid():
    assert parse_en_date("31 Oct 2030") == date(2030, 10, 31)
    assert parse_en_date("07 Nov 2012") == date(2012, 11, 7)
    assert parse_en_date("1 Feb 2013") == date(2013, 2, 1)


def test_parse_en_date_missing_and_bad():
    assert parse_en_date("–") is None  # en dash
    assert parse_en_date("—") is None
    assert parse_en_date("") is None
    assert parse_en_date("not a date") is None
    assert parse_en_date("31 Xyz 2030") is None
    assert parse_en_date("31 Feb 2030") is None  # invalid day for month


# ---------------------------------------------------------------------------
# parse_subunit_amount
# ---------------------------------------------------------------------------


def test_parse_subunit_amount_notation():
    assert parse_subunit_amount("265c") == 2.65
    assert parse_subunit_amount("4.5¢") == 0.045
    assert parse_subunit_amount("7.77p") == 0.0777
    assert parse_subunit_amount("27c") == 0.27
    assert parse_subunit_amount("2.36¢") == 0.0236
    assert parse_subunit_amount("1.5") == 1.5  # bare number = whole units


def test_parse_subunit_amount_gated_and_missing():
    assert parse_subunit_amount("Sign up") is None
    assert parse_subunit_amount("—") is None
    assert parse_subunit_amount("–") is None
    assert parse_subunit_amount("") is None
    assert parse_subunit_amount("n/a") is None


# ---------------------------------------------------------------------------
# resolve_path — against captured suggest.json fixtures
# ---------------------------------------------------------------------------


def test_resolve_exact_ticker(httpx_mock, read_fixture):
    calls = httpx_mock([(read_fixture("suggest-aapl.json"), 200)])
    path = resolve_path("AAPL")
    assert calls == [
        "https://www.dividendmax.com/suggest.json?q=AAPL"
    ]
    assert path == "/united-states/nasdaq/technology-hardware-and-equipment/apple-inc/dividends"


def test_resolve_is_case_insensitive(httpx_mock, read_fixture):
    httpx_mock([(read_fixture("suggest-aapl.json"), 200)])
    assert resolve_path("aapl").endswith("apple-inc/dividends")


def test_resolve_ignores_partial_name_matches(httpx_mock, read_fixture):
    """q=aapl also returns APLY (name contains 'AAPL') — only exact ticker counts."""
    httpx_mock([(read_fixture("suggest-aapl.json"), 200)])
    assert resolve_path("APLY").endswith("yieldmax-aapl-option-income-strategy-etf/dividends")


def test_resolve_prefers_us_listing_on_tie(httpx_mock, read_fixture):
    """VOD → UK plc + US ADR; a bare ticker prefers the US listing."""
    httpx_mock([(read_fixture("suggest-vodafone.json"), 200)])
    assert resolve_path("VOD").endswith("vodafone-group-plc-adr/dividends")


def test_resolve_dot_suffix_variant(httpx_mock, read_fixture):
    """A yfinance-style ``VOD.L`` resolves via the ``VOD.`` prefix fallback."""
    httpx_mock([(read_fixture("suggest-vodafone.json"), 200)])
    assert resolve_path("VOD.L").endswith("vodafone-group-plc-adr/dividends")


def test_resolve_unknown_symbol_returns_none(httpx_mock):
    httpx_mock([("[]", 200)])
    assert resolve_path("ZZZZZ") is None


def test_resolve_non_200_returns_none(httpx_mock):
    httpx_mock([("", 403)])
    assert resolve_path("AAPL") is None


# ---------------------------------------------------------------------------
# scrape_dividend_history — full flow against captured pages
# ---------------------------------------------------------------------------


def test_scrape_aapl_full_history(httpx_mock, read_fixture, no_delay):
    calls = httpx_mock([
        (read_fixture("suggest-aapl.json"), 200),
        (read_fixture("dividends-aapl.html"), 200),
    ])
    rows = scrape_dividend_history("AAPL")
    assert len(calls) == 2
    assert calls[1] == (
        "https://www.dividendmax.com/"
        "united-states/nasdaq/technology-hardware-and-equipment/apple-inc/dividends"
    )
    assert len(rows) == 58
    assert rows[0] == {
        "ex_dividend_date": date(2026, 8, 10),
        "payment_date": date(2026, 8, 13),
        "declaration_date": date(2026, 7, 30),
        "amount": 0.27,
        "currency": "USD",
        "dividend_type": "Quarterly",
        "status": "Paid",
        "symbol": "AAPL",
    }
    assert rows[-1]["ex_dividend_date"] == date(2011, 12, 31)
    assert rows[-1]["declaration_date"] is None
    assert all(r["status"] == "Paid" for r in rows)


def test_scrape_vodafone_mixed_currencies(httpx_mock, read_fixture, no_delay):
    httpx_mock([
        (read_fixture("suggest-vodafone.json"), 200),
        (read_fixture("dividends-vodafone.html"), 200),
    ])
    rows = scrape_dividend_history("VOD")
    assert len(rows) == 39
    assert rows[0]["amount"] == 0.0236
    assert rows[0]["currency"] == "EUR"
    assert rows[-1]["ex_dividend_date"] == date(2006, 12, 31)
    assert rows[-1]["currency"] == "GBP"
    assert {r["currency"] for r in rows} == {"EUR", "GBP", "USD"}
    assert all(r["symbol"] == "VOD" for r in rows)


def test_scrape_unknown_symbol_returns_empty(httpx_mock, no_delay):
    httpx_mock([("[]", 200)])
    assert scrape_dividend_history("ZZZZZ") == []


def test_scrape_page_404_returns_empty(httpx_mock, read_fixture, no_delay):
    httpx_mock([(read_fixture("suggest-aapl.json"), 200), ("", 404)])
    assert scrape_dividend_history("AAPL") == []


def test_scrape_no_table_returns_empty(httpx_mock, read_fixture, no_delay):
    httpx_mock([
        (read_fixture("suggest-aapl.json"), 200),
        ("<html><body>no table</body></html>", 200),
    ])
    assert scrape_dividend_history("AAPL") == []
