"""CPI importer (D79 19.3) — obligacje.pl 12m inflation -> openst.cpi_12m.

Data source: https://obligacje.pl/pl/narzedzia/inflacja

The CPI series is embedded in a ``google.visualization.arrayToDataTable([...])``
JavaScript block (header row ``["Data", "Wartość"]``); every data row is a JS
``[new Date(YYYY, M, D), value]`` literal — a 0-BASED month and a dot-decimal
value (e.g. ``[new Date(2000,0,31), 10.1]`` = 31 Jan 2000, 10.1%). There is no
HTML table, so this differs from the biznesradar scraper pattern.

Range filtering is done server-side via the URL: appending
``,data_od-YYYY_MM_DD,data_do-YYYY_MM_DD`` returns only the rows in range; the
bare ``/pl/narzedzia/inflacja`` URL returns MAX history back to Jan 2000.

Modes (the importer runs as a one-shot k8s Job reusing the openst image):
  full        — ``--mode full``       fetch MAX history (initial import)
  incremental — ``--mode incremental`` fetch the last ~60 days (daily CronJob)
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from decimal import Decimal

import httpx

CPI_URL = "https://obligacje.pl/pl/narzedzia/inflacja"
USER_AGENT = "Mozilla/5.0"
REQUEST_TIMEOUT = 30.0

# JS Date has 0-based months: new Date(2000,0,31) == 2000-01-31. Values are
# dot-decimal or plain integers, and may be NEGATIVE (Poland saw deflation in
# 2014-2015): e.g. "10.1", "3", "-0.3". The value column is the last element of
# a row literal, so it is anchored to the closing "]" — this stops it swallowing
# the "," that separates consecutive rows.
_ROW_RE = re.compile(r"new Date\((\d{4}),(\d{1,2}),(\d{1,2})\)\s*,\s*(-?[\d.,]+)\s*\]")


class CpiFetchError(RuntimeError):
    """Raised when obligacje.pl returns a non-200 or a page with no CPI rows."""


def build_url(from_date: date | None = None, to_date: date | None = None) -> str:
    """Build the obligacje.pl inflacja URL for a date range (MAX when empty)."""
    if from_date is None and to_date is None:
        return CPI_URL
    segments: list[str] = []
    if from_date is not None:
        segments.append(f"data_od-{from_date:%Y_%m_%d}")
    if to_date is not None:
        segments.append(f"data_do-{to_date:%Y_%m_%d}")
    return f"{CPI_URL},{','.join(segments)}"


def parse_cpi_rows(html: str) -> list[tuple[date, Decimal]]:
    """Extract ``(date, value)`` rows from the arrayToDataTable JS block.

    Rows come back in ascending order as published by obligacje.pl (oldest
    first). Values are parsed with a comma->dot normalisation so the parser is
    robust if the site ever switches decimal separators.
    """
    rows: list[tuple[date, Decimal]] = []
    for match in _ROW_RE.finditer(html):
        year = int(match.group(1))
        month = int(match.group(2)) + 1  # JS months are 0-based
        day = int(match.group(3))
        value = Decimal(match.group(4).strip().replace(",", "."))
        rows.append((date(year, month, day), value))
    return rows


def fetch_cpi(
    from_date: date | None = None, to_date: date | None = None
) -> list[tuple[date, Decimal]]:
    """Fetch CPI rows from obligacje.pl for the given range (MAX when empty)."""
    url = build_url(from_date, to_date)
    response = httpx.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
    )
    if response.status_code != 200:
        raise CpiFetchError(f"{url} -> HTTP {response.status_code}")
    rows = parse_cpi_rows(response.text)
    if not rows:
        raise CpiFetchError(f"{url} -> no CPI rows parsed")
    return rows


def upsert_cpi(conn, rows: list[tuple[date, Decimal]]) -> int:
    """Insert CPI rows into ``openst.cpi_12m``, ignoring duplicate dates.

    Returns the number of rows actually inserted (conflicts count 0).
    """
    inserted = 0
    with conn.cursor() as cur:
        for day, value in rows:
            cur.execute(
                "INSERT INTO openst.cpi_12m (date, value) VALUES (%s, %s) "
                "ON CONFLICT (date) DO NOTHING",
                (day, value),
            )
            inserted += cur.rowcount
    conn.commit()
    return inserted


def run(mode: str) -> dict:
    """Fetch (+ possibly insert) CPI data for a mode; returns a summary dict."""
    if mode == "full":
        rows = fetch_cpi()
    elif mode == "incremental":
        today = date.today()
        rows = fetch_cpi(today - timedelta(days=60), today)
    else:
        raise ValueError(f"unknown mode: {mode}")

    from src import db

    conn = db.get_conn()
    try:
        inserted = upsert_cpi(conn, rows)
    finally:
        conn.close()
    return {"mode": mode, "rows": len(rows), "inserted": inserted}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="src.importers.cpi",
        description="Import 12m CPI history from obligacje.pl into openst.cpi_12m.",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="incremental",
        help="full = MAX history (initial import); incremental = last 60 days (default)",
    )
    args = parser.parse_args(argv)
    summary = run(args.mode)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())