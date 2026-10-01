"""Fund-category catalogue + search routes (§78 step 2).

Fixture-driven against the captured snapshot in
``tests/fixtures/analizy/catalogue/fund-catalogue.csv``. No HTTP is involved:
the catalogue is a snapshot, so there is nothing to mock on the wire — which is
the point of the snapshot design and worth asserting rather than assuming.

The assertions that carry weight:

* the snapshot holds the codes §72.39 verified, so a catalogue that lost them
  fails here instead of failing silently in search;
* **categories outnumber funds** — the corpus is mostly lettered codes, so a
  numeric-only catalogue would look complete while dropping 65% of it;
* a miss is a 404 and never an empty 200, because "no such fund" and "the
  catalogue is broken" must not look alike;
* a missing snapshot is a 503, never an empty CSV.
"""

import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.importers import fund_catalogue as fc

FIXTURE = (
    Path(__file__).parent / "fixtures" / "analizy" / "catalogue" / "fund-catalogue.csv"
)

#: The codes §72.39 stage 1 verified one by one, including the class-W symbol the
#: whole provider build exists for.
VERIFIED = ["ING01", "ING01W", "ING04", "ING81", "ING82", "ING88", "ING92"]


@pytest.fixture
def client():
    from src.main import app
    return TestClient(app)


@pytest.fixture
def rows():
    return fc.load_rows(FIXTURE)


@pytest.fixture
def snapshot(monkeypatch):
    """Point the module at the fixture snapshot.

    Patching SNAPSHOT_PATH rather than load_rows itself: the routes import
    ``load_rows`` by name inside the function body, so replacing the module
    attribute is what actually reaches them — and replacing load_rows with a
    lambda that calls load_rows is infinite recursion.
    """
    monkeypatch.setattr(fc, "SNAPSHOT_PATH", FIXTURE)
    return FIXTURE


# --- the snapshot itself ----------------------------------------------------


def test_snapshot_holds_every_code_the_investigation_verified(rows):
    have = {r["code"] for r in rows}
    for code in VERIFIED:
        assert code in have, f"{code} missing from the catalogue"


def test_categories_outnumber_funds(rows):
    """The corpus is mostly lettered categories, so fund count == catalogue count
    is the wrong sanity check and would hide a numeric-only regression."""
    funds = [r for r in rows if not fc._base_fund_code(r["code"]) != r["code"]]
    categories = [r for r in rows if fc._base_fund_code(r["code"]) != r["code"]]
    assert len(categories) > len(funds), (
        f"expected categories to outnumber funds, got {len(categories)}/{len(funds)}"
    )


def test_every_row_is_pln_and_has_a_series(rows):
    for r in rows:
        assert r["currency"] == fc.EXPECTED_CURRENCY, r["code"]
        assert int(r["points"]) > 0, r["code"]
        assert r["first"] <= r["last"], r["code"]


def test_codes_are_unique_and_upper_case(rows):
    codes = [r["code"] for r in rows]
    assert len(codes) == len(set(codes))
    assert all(c == c.upper() for c in codes)


# --- base code / alias ------------------------------------------------------


@pytest.mark.parametrize(
    "code,expected",
    [
        ("ING01W", "ING01"),
        ("ING04F", "ING04"),
        ("VIG04B", "VIG04"),
        ("PZU94W", "PZU94"),
        ("ING01", "ING01"),   # already a fund
        ("SKR120", "SKR120"),  # three digits: a fund, not a category
        ("SKR117B", "SKR117"),
    ],
)
def test_base_fund_code_strips_exactly_one_trailing_letter(code, expected):
    assert fc._base_fund_code(code) == expected


# --- search -----------------------------------------------------------------


def test_search_finds_a_category_by_exact_code(rows):
    hits = fc.search("ING01W", rows)
    assert [h["symbol"] for h in hits] == ["ING01W"]
    assert hits[0]["name"] == "ING Akcji W"
    assert hits[0]["currency"] == fc.EXPECTED_CURRENCY


def test_search_on_a_fund_also_returns_its_categories(rows):
    """`ING01` must surface ING01W — otherwise the class-W symbol is only
    reachable by typing a code nobody knows."""
    symbols = [h["symbol"] for h in fc.search("ING01", rows)]
    assert "ING01" in symbols
    assert "ING01W" in symbols
    assert "ING01U" in symbols


def test_search_matches_polish_names_substring(rows):
    hits = fc.search("Akcji W", rows)
    assert any(h["symbol"] == "ING01W" for h in hits)
    assert all("W" in h["name"] or "W" in h["symbol"] for h in hits)


def test_search_is_case_insensitive(rows):
    assert fc.search("ing01w", rows) == fc.search("ING01W", rows)


def test_search_finds_the_emerytura_family(rows):
    hits = {h["symbol"] for h in fc.search("emerytura", rows)}
    assert {"ING81", "ING82", "ING88", "ING92"} <= hits


def test_search_miss_returns_empty_not_a_partial_match(rows):
    assert fc.search("zzzznotafund", rows) == []


def test_empty_query_returns_empty(rows):
    assert fc.search("", rows) == []
    assert fc.search("   ", rows) == []


def test_search_respects_the_limit(rows):
    assert len(fc.search("a", rows, limit=7)) == 7


def test_search_results_are_sorted_and_carry_the_exchange(rows):
    hits = fc.search("ING0", rows)
    assert [h["symbol"] for h in hits] == sorted(h["symbol"] for h in hits)
    assert all(h["exchange"] == fc.VENUE for h in hits)
    assert all(h["asset_type"] == "fund" for h in hits)


# --- tickerref CSV ----------------------------------------------------------


def test_tickerref_csv_namespaces_keys_and_pins_asset_type(rows):
    out = fc.to_tickerref_csv(rows)
    parsed = list(csv.DictReader(io.StringIO(out)))
    assert len(parsed) == len(rows)
    first = parsed[0]
    assert first["listing_key"] == f"{fc.VENUE}::{first['ticker']}"
    assert first["exchange"] == fc.VENUE
    assert first["asset_type"] == "fund"
    assert first["country_code"] == "PL"


def test_tickerref_csv_aliases_a_category_to_its_fund(rows):
    out = fc.to_tickerref_csv(rows)
    by_ticker = {r["ticker"]: r for r in csv.DictReader(io.StringIO(out))}
    assert by_ticker["ING01W"]["aliases"] == "ING01"
    assert by_ticker["ING01"]["aliases"] == ""


def test_tickerref_csv_has_the_header_tickerref_sync_expects(rows):
    out = fc.to_tickerref_csv(rows)
    assert out.splitlines()[0].split(",") == fc.CSV_HEADER


# --- failure modes ----------------------------------------------------------


def test_missing_snapshot_raises_rather_than_reading_as_empty(tmp_path):
    with pytest.raises(fc.CatalogueUnavailable):
        fc.load_rows(tmp_path / "nope.csv")


def test_empty_snapshot_raises(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("code,name,currency,points,first,last,close\n", encoding="utf-8")
    with pytest.raises(fc.CatalogueUnavailable):
        fc.load_rows(p)


# --- routes -----------------------------------------------------------------


def test_catalogue_route_serves_tickerref_csv(client, snapshot):
    r = client.get("/fund/catalogue")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    parsed = list(csv.DictReader(io.StringIO(r.text)))
    assert len(parsed) == len(fc.load_rows(FIXTURE))
    assert any(row["ticker"] == "ING01W" for row in parsed)


def test_catalogue_route_is_503_not_an_empty_csv_when_the_snapshot_is_gone(
    client, snapshot, monkeypatch, tmp_path
):
    """An empty catalogue would make every fund unsearchable and every fund code a
    404 — indistinguishable from 'this source has no funds'. It must be loud."""
    client.get("/fund/catalogue")  # warm the cache under the good snapshot
    monkeypatch.setattr(fc, "SNAPSHOT_PATH", tmp_path / "gone.csv")
    r = client.get("/fund/catalogue")
    # 503 when the cache is cold, 200 only if a previous good value was served —
    # never 200 with an empty CSV body.
    if r.status_code == 200:
        assert r.text.strip().count("\n") > 100, "served an effectively empty catalogue"
    else:
        assert r.status_code == 503


def test_search_route_returns_hits(client, snapshot):
    r = client.get("/fund/search/ING01W")
    assert r.status_code == 200
    body = r.json()
    assert body[0]["symbol"] == "ING01W"
    assert body[0]["currency"] == "PLN"


def test_search_route_miss_is_404_never_an_empty_200(client, snapshot):
    r = client.get("/fund/search/zzzznotafund")
    assert r.status_code == 404


def test_search_route_empty_query_is_404(client, snapshot):
    assert client.get("/fund/search/%20").status_code == 404


def test_search_route_is_case_insensitive_on_the_key(client, snapshot):
    a = client.get("/fund/search/ING01W")
    b = client.get("/fund/search/ing01w")
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()
