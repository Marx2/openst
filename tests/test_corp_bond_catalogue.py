"""Corp-bond catalogue importer tests (D80 25.3).

Pins the obligacje.pl catalogue parsing against the captured fixture
``tests/fixtures/obligacje_bond_catalogue_page1.html`` and the emitted
tickerref CSV contract consumed by
``portfoliost-instruments`` ``syncTickerReference``.
"""

import json
from pathlib import Path

import pytest

from src.importers import corp_bond_catalogue as c

FIXTURE = Path(__file__).parent / "fixtures" / "obligacje_bond_catalogue_page1.html"


def _fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_fixture_full_catalogue():
    rows = c.parse_catalogue_page(_fixture_html())
    assert len(rows) == 937
    # no duplicate symbols
    symbols = [r["symbol"] for r in rows]
    assert len(set(symbols)) == len(symbols)
    # first fixture row: 7R S.A. / SIR0228
    first = rows[0]
    assert first == {
        "symbol": "SIR0228",
        "issuer": "7R S.A.",
        "maturity": "2028-02-04",
        "coupon_type": "zmienne WIBOR 6M",
        "margin": "4.8",
        "current_rate": "8.64%",
    }
    # hyphenated codes are preserved (a [A-Z0-9.]-only regex would miss them)
    assert "BOS0735-K" in symbols
    assert "PKO1034-K" in symbols


def test_parse_missing_table_returns_empty():
    assert c.parse_catalogue_page("<html><body><p>no table</p></body></html>") == []


def test_parse_dedupes_repeated_symbol():
    html = (
        '<table id="tabela"><tbody>'
        "<tr>"
        '<td><a href="/pl/emitent/best-s-a">Best S.A.</a></td>'
        '<td><a href="/pl/obligacja/BST0327">BST0327</a></td>'
        "<td>2027-03-07</td><td>zmienne WIBOR 3M</td><td>4</td><td>7.8%</td><td></td>"
        "</tr>"
        "<tr>"
        '<td><a href="/pl/emitent/best-s-a">Best S.A.</a></td>'
        '<td><a href="/pl/obligacja/BST0327">BST0327</a></td>'
        "<td>2027-03-07</td><td>zmienne WIBOR 3M</td><td>4</td><td>7.8%</td><td></td>"
        "</tr>"
        "</tbody></table>"
    )
    rows = c.parse_catalogue_page(html)
    assert [r["symbol"] for r in rows] == ["BST0327"]


def test_to_tickerref_csv_contract():
    rows = c.parse_catalogue_page(_fixture_html())
    csv_text = c.to_tickerref_csv(rows)
    lines = csv_text.split("\n")
    # header must match the tickerref-sync.ts column order exactly
    assert lines[0] == (
        "listing_key,ticker,exchange,name,asset_type,"
        "stock_sector,etf_category,country,country_code,isin,aliases"
    )
    data = [l for l in lines[1:] if l]
    assert len(data) == 937
    first = next(l for l in data if l.startswith("WSE::SIR0228,"))
    assert first == "WSE::SIR0228,SIR0228,WSE,7R S.A.,corp_bond,,,Poland,PL,,"
    # every row is a corp_bond on the WSE venue
    for line in data:
        parts = line.split(",")
        assert parts[0] == f"WSE::{parts[1]}"
        assert parts[2] == "WSE"
        assert parts[4] == "corp_bond"
        assert parts[7] == "Poland" and parts[8] == "PL"


def test_fetch_catalogue_non_200_raises(monkeypatch):
    import httpx

    class R:
        status_code = 500
        text = ""

    monkeypatch.setattr(httpx, "get", lambda *a, **k: R())
    with pytest.raises(RuntimeError, match="HTTP 500"):
        c.fetch_catalogue()


def test_fetch_catalogue_parses(monkeypatch):
    import httpx

    html = _fixture_html()
    seen = {}

    def fake_get(url, headers=None, timeout=None):
        seen["url"] = url

        class R:
            status_code = 200
            text = html

        return R()

    monkeypatch.setattr(httpx, "get", fake_get)
    rows = c.fetch_catalogue()
    assert seen["url"] == "https://obligacje.pl/pl/narzedzia/wyszukiwarka-obligacji-notowanych"
    assert len(rows) == 937


def test_run_writes_csv_file(tmp_path, monkeypatch):
    import httpx

    html = _fixture_html()

    class R:
        status_code = 200
        text = html

    monkeypatch.setattr(httpx, "get", lambda *a, **k: R())
    out = tmp_path / "corp_bonds.csv"
    summary = c.run(output=str(out))
    assert summary["bonds"] == 937
    text = out.read_text(encoding="utf-8")
    assert text.startswith("listing_key,ticker,exchange")
    assert "WSE::SIR0228" in text


def test_main_emits_json_summary_on_stdout(tmp_path, monkeypatch, capsys):
    import httpx

    html = _fixture_html()

    class R:
        status_code = 200
        text = html

    monkeypatch.setattr(httpx, "get", lambda *a, **k: R())
    out = tmp_path / "corp_bonds.csv"
    rc = c.main(["--out", str(out)])
    assert rc == 0
    stdout = capsys.readouterr().out
    assert out.exists()
    # single stdout line = JSON summary (log lines go to stderr via basicConfig)
    summary = json.loads(stdout.strip().splitlines()[-1])
    assert summary["bonds"] == 937


def test_no_db_writes():
    """The catalogue importer is DB-free — the CSV is the contract, the
    instruments ticker sync does the upsert into ``ticker_reference``. Guard
    against accidental coupling to openst Postgres."""
    import inspect

    src = inspect.getsource(c)
    assert "INSERT" not in src
    assert "psycopg" not in src
