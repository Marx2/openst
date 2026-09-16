"""CPI importer unit tests (D79 19.3).

The live obligacje.pl inflacja page embeds the CPI series in a
``google.visualization.arrayToDataTable([...])`` JS block — rows are
``[new Date(YYYY, M, D), value]`` with a 0-BASED month and dot-decimal values —
so there is no HTML table to scrape. Tests run against the captured MAX fixture
(``fixtures/obligacje/inflacja.html``) plus synthetic snippets for the
date/value parsing edge cases.
"""

from datetime import date
from decimal import Decimal

import httpx
import pytest

from src import db
from src.importers import cpi

needs_pg = pytest.mark.skipif(
    not db.database_url(),
    reason="DATABASE_URL not set (run via docker compose --profile test)",
)

# Valid day for every 0-based month index in the leap year 2000.
_MONTH_DAYS_2000 = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _snippet(month: int, day: int, value: str) -> str:
    return f'[new Date(2000,{month},{day}), {value}]'


# ---------------------------------------------------------------------------
# parse_cpi_rows — date and value parsing
# ---------------------------------------------------------------------------


def test_parses_all_twelve_months_js_date():
    rows = [
        _snippet(m, _MONTH_DAYS_2000[m], "1.1") for m in range(12)
    ]
    html = 'google.visualization.arrayToDataTable([["Data", "Wartość"],' + ",".join(rows) + "]);"
    parsed = cpi.parse_cpi_rows(html)
    assert [d for d, _ in parsed] == [date(2000, m + 1, _MONTH_DAYS_2000[m]) for m in range(12)]


def test_parses_dot_decimal_and_integer_values():
    html = (
        'google.visualization.arrayToDataTable([["Data", "Wartość"],'
        + ",".join(
            [
                _snippet(0, 31, "10.1"),
                _snippet(1, 29, "3"),
                _snippet(2, 31, "0.4"),
            ]
        )
        + "]);"
    )
    parsed = cpi.parse_cpi_rows(html)
    assert [v for _, v in parsed] == [Decimal("10.1"), Decimal("3"), Decimal("0.4")]
    assert all(isinstance(v, Decimal) for _, v in parsed)


def test_parses_negative_values():
    html = (
        'google.visualization.arrayToDataTable([["Data", "Wartość"],'
        + ",".join([_snippet(0, 31, "-0.3"), _snippet(1, 29, "-1")])
        + "]);"
    )
    parsed = cpi.parse_cpi_rows(html)
    assert [v for _, v in parsed] == [Decimal("-0.3"), Decimal("-1")]


def test_parses_comma_decimal_as_fallback():
    html = 'google.visualization.arrayToDataTable([["Data", "Wartość"],' + _snippet(0, 31, "10,1") + "]);"
    assert cpi.parse_cpi_rows(html)[0][1] == Decimal("10.1")


def test_parses_nothing_from_unrelated_html():
    assert cpi.parse_cpi_rows("<html><body><p>no inflacja chart here</p></body></html>") == []


# ---------------------------------------------------------------------------
# parse_cpi_rows — captured MAX fixture
# ---------------------------------------------------------------------------


def test_fixture_full_history_roundtrip(read_fixture):
    rows = cpi.parse_cpi_rows(read_fixture("obligacje/inflacja.html"))
    assert rows[0] == (date(2000, 1, 31), Decimal("10.1"))
    assert len(rows) >= 300
    dates = [d for d, _ in rows]
    assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# build_url
# ---------------------------------------------------------------------------


def test_build_url_max_without_range():
    assert cpi.build_url() == "https://obligacje.pl/pl/narzedzia/inflacja"


def test_build_url_appends_range_segments():
    url = cpi.build_url(date(2026, 7, 17), date(2026, 9, 15))
    assert url.endswith("inflacja,data_od-2026_07_17,data_do-2026_09_15")


# ---------------------------------------------------------------------------
# fetch_cpi — mocked httpx.get
# ---------------------------------------------------------------------------


def test_fetch_cpi_full_hits_max_url(monkeypatch, read_fixture):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, text=read_fixture("obligacje/inflacja.html"),
                              request=httpx.Request("GET", url))

    monkeypatch.setattr(cpi.httpx, "get", fake_get)
    rows = cpi.fetch_cpi()
    assert calls == ["https://obligacje.pl/pl/narzedzia/inflacja"]
    assert rows[0] == (date(2000, 1, 31), Decimal("10.1"))


def test_fetch_cpi_incremental_hits_range_url(monkeypatch, read_fixture):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, text=read_fixture("obligacje/inflacja.html"),
                              request=httpx.Request("GET", url))

    monkeypatch.setattr(cpi.httpx, "get", fake_get)
    cpi.fetch_cpi(date(2026, 7, 17), date(2026, 9, 15))
    assert calls == ["https://obligacje.pl/pl/narzedzia/inflacja,data_od-2026_07_17,data_do-2026_09_15"]


def test_fetch_cpi_raises_on_non_200(monkeypatch, read_fixture):
    def fake_get(url, **kwargs):
        return httpx.Response(404, text="nope", request=httpx.Request("GET", url))

    monkeypatch.setattr(cpi.httpx, "get", fake_get)
    with pytest.raises(cpi.CpiFetchError):
        cpi.fetch_cpi()


def test_fetch_cpi_raises_when_no_rows_parsed(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(200, text="<html></html>", request=httpx.Request("GET", url))

    monkeypatch.setattr(cpi.httpx, "get", fake_get)
    with pytest.raises(cpi.CpiFetchError):
        cpi.fetch_cpi()


# ---------------------------------------------------------------------------
# upsert_cpi — duplicate rows are silently ignored (needs Postgres)
# ---------------------------------------------------------------------------


@pytest.fixture
def conn():
    c = db.get_conn()
    db.migrate(conn=c)  # ensure openst schema/tables exist (fresh test Postgres)
    yield c
    c.close()


@needs_pg
def test_upsert_ignores_duplicate_rows(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE openst.cpi_12m")
    conn.commit()

    first = cpi.upsert_cpi(
        conn,
        [(date(2000, 1, 31), Decimal("10.1")), (date(2000, 2, 29), Decimal("10.4"))],
    )
    assert first == 2

    # Re-inserting one existing date (with a different value) and one new date
    # must insert only the new row and leave the existing value untouched.
    second = cpi.upsert_cpi(
        conn,
        [(date(2000, 1, 31), Decimal("99.9")), (date(2000, 3, 31), Decimal("7.0"))],
    )
    assert second == 1
    with conn.cursor() as cur:
        cur.execute("SELECT value FROM openst.cpi_12m WHERE date = %s", (date(2000, 1, 31),))
        assert cur.fetchone()[0] == Decimal("10.1")