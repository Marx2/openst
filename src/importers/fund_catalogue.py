"""Analizy.pl fund-category catalogue (plan §78).

Unlike every other catalogue here this one is **not** scraped per request.
`corp_bond_catalogue` reads a single server-rendered page; the fund catalogue is
734 category codes, each a separate JSON GET, and the full enumeration is ~960
requests across two passes. Scraping it on a request path is not possible, so it
is a **refreshed snapshot**: a refresh job rewrites the CSV below, and the routes
serve the file.

The enumeration is bounded and deliberately so, because the code space is not
derivable — of ING01's nine categories only ING01/U/W/T/F resolve, so a
``fund + letter`` transform would invent codes that do not exist. Two bounds are
in force, both data rather than code:

- code **prefixes** — the 8 that resolve on this source (ING PZU AXA ARK SKR VIG
  QRS PCS), each probed 01..120 because SKR110 is real;
- code **letters** for categories — the 11 observed here (A B E F I K P S T U W).

A category on a prefix or letter outside those sets is absent from the snapshot.
That is a limit of the catalogue, not a claim of completeness.

A category is the fund code plus a letter (``ING01`` -> ``ING01W``), and the
categories are the **majority** of the corpus: 259 funds against 475 categories.
A numeric-only sweep drops 65% of it and, worse, looks complete while missing
``ING01W`` — the symbol the whole class-W provider build exists for.
"""

import csv
import io
import os
from pathlib import Path

# Venue code for the listing_key namespace. Mirrors ``WSE::`` for corp bonds:
# namespacing keeps these rows from colliding with the adanos stock/ETF rows that
# ``tickerref-sync`` also upserts, and it is what step 5 reads to decide a
# symbol's price tier, so the exchange column carries meaning, not decoration.
VENUE = "ANALIZY"

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

#: Snapshot written by the refresh job. Tests point this at a fixture.
SNAPSHOT_PATH = Path(
    os.environ.get("FUND_CATALOGUE_PATH")
    or Path(__file__).resolve().parents[2] / "data" / "fund-catalogue.csv"
)

#: Every category on this source is PLN-denominated, and the snapshot carries the
#: currency the source declared. ``search`` surfaces it, and step 5's consumer
#: asserts it rather than assuming — the same discipline as the quotation route.
EXPECTED_CURRENCY = "PLN"


class CatalogueUnavailable(Exception):
    """The snapshot is missing or unparseable — a deployment fault, not a miss."""


def load_rows(path: Path | None = None) -> list[dict]:
    """Parse the snapshot into dicts. Raises CatalogueUnavailable if absent.

    Deliberately raises rather than returning []: an empty catalogue would make
    every fund unsearchable and every fund code a 404, which reads exactly like
    "this source has no funds" — the silent shape §72.39 exists to avoid.
    """
    p = path or SNAPSHOT_PATH
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        raise CatalogueUnavailable(f"catalogue snapshot unreadable at {p}: {e}") from e
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise CatalogueUnavailable(f"catalogue snapshot at {p} has no rows")
    return rows


def to_tickerref_csv(rows: list[dict]) -> str:
    """Render catalogue rows in the tickerref-sync CSV shape (``ANALIZY::`` keys).

    ``asset_type`` is pinned to ``fund``; sector/category/ISIN/aliases are empty
    because the source does not carry them. ``aliases`` gets the bare fund code
    for lettered categories (``ING01W`` -> ``ING01``) so a search for the fund
    also finds its categories.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for row in rows:
        code = row["code"].strip().upper()
        base = _base_fund_code(code)
        writer.writerow(
            [
                f"{VENUE}::{code}",
                code,
                VENUE,
                row.get("name", ""),
                "fund",
                "",
                "",
                "Poland",
                "PL",
                "",
                base if base != code else "",
            ]
        )
    return buf.getvalue()


def _base_fund_code(code: str) -> str:
    """``ING01W`` -> ``ING01``; ``ING01`` -> ``ING01`` (already a fund).

    Trailing letters are the unit category. Skarbiec's ``SKR120`` is a *fund*
    with a three-digit number, so only a single trailing letter is stripped.
    """
    if len(code) > 3 and code[-1].isalpha():
        return code[:-1]
    return code


def search(query: str, rows: list[dict], limit: int = 50) -> list[dict]:
    """Case-insensitive match on code, alias or name. Empty query -> [].

    Substring rather than prefix: the corpus mixes Polish names and codes, and a
    user typing ``akcji`` should find ``ING01W`` ("ING Akcji W") as readily as a
    fund literally starting with it.
    """
    q = (query or "").strip().lower()
    if not q:
        return []
    hits = []
    for row in rows:
        code = row["code"].strip().upper()
        name = row.get("name", "")
        base = _base_fund_code(code)
        if q in code.lower() or q in base.lower() or q in name.lower():
            hits.append(
                {
                    "symbol": code,
                    "name": name,
                    "currency": row.get("currency", ""),
                    "asset_type": "fund",
                    "exchange": VENUE,
                    "country": "PL",
                    "points": row.get("points", ""),
                    "last": row.get("last", ""),
                    "close": row.get("close", ""),
                }
            )
    hits.sort(key=lambda h: h["symbol"])
    return hits[:limit]
