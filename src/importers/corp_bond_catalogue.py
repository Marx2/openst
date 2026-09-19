"""Catalyst corporate-bond catalogue importer (D80 25.3).

Data source: ``https://obligacje.pl/pl/narzedzia/wyszukiwarka-obligacji-notowanych``

That page lists **every listed corporate bond** in a single server-rendered
``table#tabela`` (the site's client-side DataTables only pages *within* the
browser — there is no server-side pagination to follow, verified 2026-09-19
against ``tests/fixtures/obligacje_bond_catalogue_page1.html``: 937 rows,
932 unique symbols, no ``table_info``/page links in the HTML). Each row is
seven ``<td>`` cells::

    0  Emitent           <a href="/pl/emitent/{slug}">{issuer}</a>
    1  Kod obligacji     <a href="/pl/obligacja/{SYMBOL}">{SYMBOL}</a>
    2  Termin wykupu     ISO date (plain text)
    3  Rodzaj oprocentowania  e.g. "zmienne WIBOR 6M" (plain text)
    4  Marża/kupon        dot-decimal number (plain text)
    5  Aktualny kupon     e.g. "8.64%" (plain text)
    6  Rentowność         calculator link (ignored)

The importer emits rows in the exact CSV shape consumed by
``portfoliost-instruments`` ``tickerref-sync`` (``syncTickerReference``), so a
one-shot k8s Job can scrape here and the instruments ticker sync can upsert
them into ``ticker_reference`` with ``asset_type=corp_bond`` — enabling bond
search without an openst roundtrip. The header / column order must stay in
lock-step with ``src/scripts/tickerref-sync.ts``.

Listing key: ``WSE::{SYMBOL}`` (Catalyst bonds trade on the Warsaw venue; the
three-letters-four-digits code cannot collide with a WSE equity). ISIN is not
on the catalogue page (only the detail page, D80 25.2) so that column is left
empty; the daily re-import picks up newly listed bonds.

Modes (one-shot k8s Job reusing the openst image; no DB writes):
  full — scrape the whole catalogue and emit the tickerref CSV
         (``--out FILE`` writes to a file, otherwise stdout).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import sys

from bs4 import BeautifulSoup

logger = logging.getLogger("openst.corp_bond_catalogue")

CATALOGUE_URL = (
    "https://obligacje.pl/pl/narzedzia/wyszukiwarka-obligacji-notowanych"
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30.0

# Listing venue for Catalyst corporate bonds (Warsaw). Used both for the
# ``listing_key`` prefix and the ``exchange`` column.
VENUE = "WSE"

# tickerref-sync.ts column order (see syncTickerReference) — the emitted CSV
# header must match this exactly.
CSV_HEADER = [
    "listing_key",
    "ticker",
    "exchange",
    "name",
    "asset_type",
    "stock_sector",
    "etf_category",
    "country",
    "country_code",
    "isin",
    "aliases",
]


def _cell_text(td) -> str:
    """Normalise a ``<td>`` to stripped, single-spaced text."""
    return " ".join(td.get_text(" ", strip=True).split())


def parse_catalogue_page(html: str) -> list[dict]:
    """Parse one ``wyszukiwarka-obligacji-notowanych`` page into row dicts.

    Returns ``[]`` when the ``table#tabela`` catalogue is absent. Each row is
    ``{symbol, issuer, maturity, coupon_type, margin, current_rate}``; the
    symbol is upper-cased and de-duplicated (a bond can appear twice in the
    table, e.g. after a re-listing).
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="tabela")
    if table is None:
        return []
    tbody = table.find("tbody")
    if tbody is None:
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        code_anchor = tds[1].find("a")
        symbol = _cell_text(tds[1])
        if not symbol or not code_anchor:
            continue
        rows.append(
            {
                "symbol": symbol,
                "issuer": _cell_text(tds[0]),
                "maturity": _cell_text(tds[2]),
                "coupon_type": _cell_text(tds[3]),
                "margin": _cell_text(tds[4]),
                "current_rate": _cell_text(tds[5]),
            }
        )

    deduped: list[dict] = []
    for row in rows:
        if row["symbol"] in seen:
            continue
        seen.add(row["symbol"])
        deduped.append(row)
    return deduped


def to_tickerref_csv(rows: list[dict]) -> str:
    """Render parsed catalogue rows as the tickerref-sync CSV.

    ``asset_type`` is pinned to ``corp_bond``; venue is ``WSE``; ISIN and the
    sector/category/aliases columns are empty (not on the catalogue page).
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for row in rows:
        symbol = row["symbol"].upper()
        writer.writerow(
            [
                f"{VENUE}::{symbol}",
                symbol,
                VENUE,
                row["issuer"],
                "corp_bond",
                "",
                "",
                "Poland",
                "PL",
                "",
                "",
            ]
        )
    return buf.getvalue()


def fetch_catalogue() -> list[dict]:
    """Fetch (and parse) the whole listed-bond catalogue.

    The page is server-complete (no server-side pagination), so a single
    fetch returns every bond. Raises ``RuntimeError`` on a non-200 response.
    """
    import httpx

    response = httpx.get(
        CATALOGUE_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise RuntimeError(f"catalogue fetch failed: HTTP {response.status_code}")
    return parse_catalogue_page(response.text)


def configure_logging(level: int = logging.INFO) -> None:
    """Route importer log lines to stdout (the CSV/summary stay on stdout too)."""
    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format="%(asctime)s %(levelname)-7s %(message)s",
    )


def run(output: str | None = None) -> dict:
    """Scrape the catalogue and emit the tickerref CSV.

    ``output`` is a file path (writes there); when ``None`` the CSV goes to
    stderr so the JSON summary stays the single stdout line for k8s logs.
    """
    rows = fetch_catalogue()
    csv_text = to_tickerref_csv(rows)
    logger.info(
        "corp_bond_catalogue: scraped %d unique bond(s) from %s",
        len(rows),
        CATALOGUE_URL,
    )
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(csv_text)
        logger.info("corp_bond_catalogue: wrote CSV to %s", output)
    else:
        sys.stderr.write(csv_text)
    return {"bonds": len(rows), "emitted": len(rows), "out": output}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="src.importers.corp_bond_catalogue",
        description=(
            "Scrape the obligacje.pl listed corporate-bond catalogue and emit a "
            "tickerref-sync CSV (asset_type=corp_bond)."
        ),
    )
    parser.add_argument(
        "--out",
        default=None,
        help="write the CSV to this file (default: stderr, JSON summary on stdout)",
    )
    args = parser.parse_args(argv)
    configure_logging()
    summary = run(args.out)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
