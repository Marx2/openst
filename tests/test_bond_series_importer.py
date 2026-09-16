"""Bond-series importer unit tests (D79 19.4).

The obligacjeskarbowe.pl emission offer pages carry a
``<ul class="product-details__list">`` of label/value rows plus a redemption-fee
schedule in prose — there is no HTML data-table. Tests run against the captured
per-series fixtures (``fixtures/obligacjeskarbowe/*.html``) and the current-offer
fixture, plus synthetic snippets for the parsing edge cases. The live site always
renders the *currently-active* emission per series, so each fixture is one emission.
"""

from datetime import date
from decimal import Decimal

import httpx
import pytest

from src import db
from src.importers import bond_series as b

needs_pg = pytest.mark.skipif(
    not db.database_url(),
    reason="DATABASE_URL not set (run via docker compose --profile test)",
)


def _fixture(name: str) -> str:
    from pathlib import Path

    return (Path(__file__).parent / "fixtures" / "obligacjeskarbowe" / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# add_months — calendar arithmetic
# ---------------------------------------------------------------------------


def test_add_months_same_year():
    assert b.add_months(date(2026, 9, 1), 3) == date(2026, 12, 1)


def test_add_months_rolls_year():
    assert b.add_months(date(2026, 9, 1), 12) == date(2027, 9, 1)
    assert b.add_months(date(2026, 9, 1), 120) == date(2036, 9, 1)


def test_add_months_clamps_day():
    # 31st + 1 month lands on the last day of the (shorter) target month.
    assert b.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert b.add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)  # leap


def test_add_months_zero():
    assert b.add_months(date(2026, 9, 1), 0) == date(2026, 9, 1)


# ---------------------------------------------------------------------------
# scalar helpers
# ---------------------------------------------------------------------------


def test_parse_pl_date():
    assert b._parse_pl_date("01.09.2026 - 30.09.2026") == date(2026, 9, 1)
    assert b._parse_pl_date("no date here") is None


def test_dec_comma_and_suffix():
    assert b._dec("5,35%") == Decimal("5.35")
    assert b._dec("100,00 zł") == Decimal("100.00")
    assert b._dec("2,00") == Decimal("2.00")
    assert b._dec("garbage") == Decimal("0")


def test_classify_rate():
    assert b._classify_rate("5,35% … + inflacja") == "cpi_12m+margin"
    assert b._classify_rate("… stopa referencyjna NBP + 0,15%") == "nbp_ref+margin"
    assert b._classify_rate("2,00% w skali roku, stałe") == "fixed"


def test_extract_margin_per_rule():
    assert b._extract_margin("5,35% …, marża 2,00% + inflacja", "cpi_12m+margin") == Decimal("2.00")
    assert b._extract_margin("4,15% …, NBP+0,15%", "nbp_ref+margin") == Decimal("0.15")
    assert b._extract_margin("4,40%, stałe przez cały okres", "fixed") == Decimal("4.40")


def test_extract_fee_last_occurrence_and_fallback():
    # A page can carry two fee schedules (old + current); the LAST is the live one.
    text = "Opłata wynosi 2,00 zł od każdej. … Nowa: opłata wynosi 3,00 zł od każdej."
    assert b._extract_fee(text, "EDO") == Decimal("3.00")
    # No fee prose at all -> per-series default.
    assert b._extract_fee("brak opłat", "OTS") == Decimal("0")
    assert b._extract_fee("brak opłat", "TOS") == Decimal("1.00")


# ---------------------------------------------------------------------------
# parse_detail_list
# ---------------------------------------------------------------------------


def test_parse_detail_list_rows():
    html = (
        '<ul class="product-details__list">'
        '<li><strong class="product-details__list-label">Seria:</strong>'
        '<span class="product-details__list-value"> EDO0936 <a>list</a> </span></li>'
        '<li><strong class="product-details__list-label">Sprzedaż:</strong>'
        '<span class="product-details__list-value">01.09.2026 - 30.09.2026</span></li>'
        "</ul>"
    )
    items = b.parse_detail_list(html)
    assert items["seria"].startswith("EDO0936")
    assert items["sprzedaż"] == "01.09.2026 - 30.09.2026"


def test_parse_detail_list_empty_for_unrelated_html():
    assert b.parse_detail_list("<html><body><p>nothing</p></body></html>") == {}


# ---------------------------------------------------------------------------
# parse_emission — captured fixtures (all eight series, three rate rules)
# ---------------------------------------------------------------------------


_EXPECTED = {
    # fixture: (symbol, series, rate_rule, margin, fee_b, issue, maturity, months)
    "edo":  ("EDO0936", "EDO", "cpi_12m+margin", Decimal("2.00"), Decimal("3.00"), date(2026, 9, 1), date(2036, 9, 1), 120),
    "ots":  ("OTS1226", "OTS", "fixed",           Decimal("2.00"), Decimal("0"),    date(2026, 9, 1), date(2026, 12, 1), 3),
    "ror":  ("ROR0927", "ROR", "nbp_ref+margin",  Decimal("0.00"), Decimal("0.50"), date(2026, 9, 1), date(2027, 9, 1), 12),
    "coi":  ("COI0930", "COI", "cpi_12m+margin",  Decimal("1.50"), Decimal("2.00"), date(2026, 9, 1), date(2030, 9, 1), 48),
    "dor":  ("DOR0928", "DOR", "nbp_ref+margin",  Decimal("0.15"), Decimal("0.70"), date(2026, 9, 1), date(2028, 9, 1), 24),
    "tos":  ("TOS0929", "TOS", "fixed",           Decimal("4.40"), Decimal("1.00"), date(2026, 9, 1), date(2029, 9, 1), 36),
    "ros":  ("ROS0932", "ROS", "cpi_12m+margin",  Decimal("2.00"), Decimal("2.00"), date(2026, 9, 1), date(2032, 9, 1), 72),
    "rod":  ("ROD0938", "ROD", "cpi_12m+margin",  Decimal("2.50"), Decimal("3.00"), date(2026, 9, 1), date(2038, 9, 1), 144),
}


@pytest.mark.parametrize("fixture", list(_EXPECTED))
def test_parse_emission_fixture(fixture):
    e = b.parse_emission(_fixture(f"{fixture}.html"))
    assert e is not None
    symbol, series, rule, margin, fee, issue, maturity, months = _EXPECTED[fixture]
    assert e["symbol"] == symbol
    assert e["series_code"] == series
    assert e["rate_rule"] == rule
    assert e["margin"] == margin
    assert e["fee_b"] == fee
    assert e["issue_date"] == issue
    assert e["maturity_date"] == maturity
    assert e["term_months"] == months
    assert e["nominal"] == Decimal("100.00")
    assert e["name"]  # a non-empty product name


def test_parse_emission_none_without_series_row():
    assert b.parse_emission("<html><body><h1>Obligacje</h1><p>no list</p></body></html>") is None


# ---------------------------------------------------------------------------
# parse_offer_emissions (incremental entry point)
# ---------------------------------------------------------------------------


def test_parse_offer_emissions_eight_unique():
    urls = b.parse_offer_emissions(_fixture("oferta.html"))
    assert len(urls) == 8
    assert len(set(urls)) == 8  # de-duplicated
    assert all(u.startswith("/oferta-obligacji/") and u.endswith("/") for u in urls)
    assert "/oferta-obligacji/obligacje-10-letnie-edo/edo0936/" in urls


def test_parse_offer_emissions_empty_for_unrelated():
    assert b.parse_offer_emissions("<html></html>") == []


# ---------------------------------------------------------------------------
# fetch_page — mocked httpx.get
# ---------------------------------------------------------------------------


def test_fetch_page_returns_text_on_200(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(200, text="OK", request=httpx.Request("GET", url))

    monkeypatch.setattr(b.httpx, "get", fake_get)
    assert b.fetch_page("/oferta-obligacji/x/") == "OK"


def test_fetch_page_full_url_passthrough(monkeypatch):
    seen = []

    def fake_get(url, **kwargs):
        seen.append(url)
        return httpx.Response(200, text="OK", request=httpx.Request("GET", url))

    monkeypatch.setattr(b.httpx, "get", fake_get)
    b.fetch_page(b.OFFER_URL)
    assert seen == [b.OFFER_URL]


def test_fetch_page_raises_on_non_200(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(404, text="nope", request=httpx.Request("GET", url))

    monkeypatch.setattr(b.httpx, "get", fake_get)
    with pytest.raises(b.BondFetchError):
        b.fetch_page("/oferta-obligacji/x/")


# ---------------------------------------------------------------------------
# run — mode plumbing (fetch mocked, DB disabled)
# ---------------------------------------------------------------------------


def _code_from_path(path: str) -> str | None:
    """Map a fetched path to its fixture file name (series code, lower)."""
    p = path.split("obligacjeskarbowe.pl", 1)[-1] if "obligacjeskarbowe.pl" in path else path
    segs = [s for s in p.split("/") if s]
    if len(segs) == 1:  # the bare /oferta-obligacji/ offer page
        return None
    return segs[1].rsplit("-", 1)[-1]


@pytest.fixture
def no_db(monkeypatch):
    monkeypatch.setattr(b.db, "database_url", lambda: None)


@pytest.fixture
def mock_fetch(monkeypatch):
    calls: list[str] = []

    def fake_fetch(path_or_url):
        calls.append(path_or_url)
        code = _code_from_path(path_or_url)
        return _fixture("oferta.html" if code is None else f"{code}.html")

    monkeypatch.setattr(b, "fetch_page", fake_fetch)
    monkeypatch.setattr(b.time, "sleep", lambda _s: None)
    return calls


def test_run_full_scrapes_all_series(no_db, mock_fetch):
    summary = b.run("full")
    assert summary["mode"] == "full"
    assert summary["fetched"] == 8
    assert summary["emissions"] == 8
    assert "inserted" not in summary
    assert set(summary["symbols"]) == {v[0] for v in _EXPECTED.values()}
    assert set(mock_fetch) == {f"/oferta-obligacji/{slug}/" for slug in b.SERIES_SLUGS.values()}


def test_run_incremental_uses_offer_page(no_db, mock_fetch):
    summary = b.run("incremental")
    assert summary["mode"] == "incremental"
    assert summary["fetched"] == 8
    assert summary["emissions"] == 8
    assert mock_fetch[0] == b.OFFER_URL  # the offer page is fetched first
    assert len(mock_fetch) == 9  # 1 offer page + 8 emissions
    assert set(summary["symbols"]) == {v[0] for v in _EXPECTED.values()}


def test_run_unknown_mode_raises(no_db, mock_fetch):
    with pytest.raises(ValueError):
        b.run("bogus")


def test_main_returns_zero(no_db, mock_fetch, capsys):
    assert b.main(["--mode", "full"]) == 0
    out = capsys.readouterr().out
    assert '"mode": "full"' in out or '"mode":"full"' in out


# ---------------------------------------------------------------------------
# upsert_bonds — idempotent on symbol (needs Postgres)
# ---------------------------------------------------------------------------


@pytest.fixture
def conn():
    c = db.get_conn()
    yield c
    c.close()


def _emission(symbol, **over):
    base = {
        "symbol": symbol,
        "name": f"Obligacje {symbol[:3]}",
        "series_code": symbol[:3],
        "issue_date": date(2026, 9, 1),
        "maturity_date": date(2036, 9, 1),
        "term_months": 120,
        "rate_rule": "cpi_12m+margin",
        "margin": Decimal("2.00"),
        "fee_b": Decimal("3.00"),
        "nominal": Decimal("100.00"),
    }
    base.update(over)
    return base


@needs_pg
def test_upsert_ignores_duplicate_symbols(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM openst.bond_series")
    conn.commit()

    first = b.upsert_bonds(conn, [_emission("EDO9999"), _emission("ROD9999")])
    assert first == 2

    # Re-inserting a known symbol (with a *different* value) plus a new one must
    # insert only the new row and leave the existing one untouched.
    second = b.upsert_bonds(conn, [_emission("EDO9999", margin=Decimal("9.99")), _emission("COI9999")])
    assert second == 1

    with conn.cursor() as cur:
        cur.execute("SELECT margin, symbol FROM openst.bond_series WHERE symbol = %s", ("EDO9999",))
        assert cur.fetchone()[0] == Decimal("2.00")  # original value preserved
        cur.execute("SELECT count(*) FROM openst.bond_series")
        assert cur.fetchone()[0] == 3

    with conn.cursor() as cur:
        cur.execute("DELETE FROM openst.bond_series")
    conn.commit()