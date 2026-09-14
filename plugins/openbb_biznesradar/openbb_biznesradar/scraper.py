"""BiznesRadar.pl page scraper — shared by the fund and bond fetchers (D77).

Selectors below were confirmed from the live fixtures captured for step 16.1
(``tests/fixtures/biznesradar/``).

Data source: https://www.biznesradar.pl/notowania-historyczne/{SYMBOL}
  page N (N>=2): /notowania-historyczne/{SYMBOL},{N}   (comma-separated page number)
  Rows are NEWEST-FIRST. 50 data rows per page.

Main data table ("qTableFull"):
  <table class="qTableFull">                          -- exactly one per page
    <tr> <th>...header...</th> </tr>                  -- first <tr> = header row
    <tr> <td>...</td> ... </tr>                       -- subsequent rows = data

Fund / TFI / FIZ table — 2 columns:
  header text:  Data | Kurs
  indices:      [0] Data (DD.MM.YYYY)
                [1] Kurs (close; dot decimal separator)

Bond / Catalyst table — 7 columns:
  header text:  Data | Otwarcie | Max | Min | Zamknięcie | Wolumen | Obrót
  indices:      [0] Data        (DD.MM.YYYY)
                [1] Otwarcie     (open)
                [2] Max          (high)
                [3] Min          (low)
                [4] Zamknięcie   (close)
                [5] Wolumen      (volume; plain integer)
                [6] Obrót        (turnover; NOT exposed in the output model.
                                  NOTE: thousands separator is a space, e.g. "6 078")

Date format: DD.MM.YYYY (e.g. "11.09.2026") -> datetime.strptime(d, "%d.%m.%Y").
Decimal separator: dot (standard float parse).

Pagination footer ("buttons pages"):
  <div class="buttons pages">
    <span class="pages_pos_current">N</span>               current page (not a link)
    <a class="pages_pos" href="/notowania-historyczne/{SYMBOL},{N}">N</a>
    <span class="pages_pos dots">...</span>                ellipsis, ignore
    <a class="pages_right" href="/notowania-historyczne/{SYMBOL},{N+1}"
       title="następna">...następna...</a>                 next-page link
  Next page => /notowania-historyczne/{SYMBOL},{N} with N = current page + 1.
"""

import time
from collections.abc import Iterator
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.biznesradar.pl"
HISTORY_PATH = "/notowania-historyczne"
USER_AGENT = "Mozilla/5.0"
DATE_FORMAT = "%d.%m.%Y"
REQUEST_TIMEOUT = 30.0

# Dotted exchange tags that upstream providers append (yfinance/FMP use `.WA`
# for the Warsaw Stock Exchange). biznesradar URLs must NOT carry them, while
# the `.TFI` / `.FIZ` venue codes and Catalyst symbol codes must be preserved.
_EXCHANGE_SUFFIXES = ("WA",)

# Value columns that are plain integers rather than dot-decimal prices.
_INT_COLUMNS = {"volume"}


class BiznesRadarNotFound(Exception):
    """Raised when biznesradar returns no parseable price table for a symbol."""


def strip_wa_suffix(symbol: str) -> str:
    """Strip a trailing Polish exchange suffix (``.WA``) from a symbol.

    ``NNEP25.TFI.WA`` -> ``NNEP25.TFI``; ``BST0327.WA`` -> ``BST0327``;
    ``NNEP25.TFI`` and ``AAPL`` pass through unchanged.
    """
    for suffix in _EXCHANGE_SUFFIXES:
        tag = f".{suffix}"
        if symbol.endswith(tag):
            return symbol[: -len(tag)]
    return symbol


def _parse_cell(text: str, name: str):
    """Parse a value cell: volume as int, prices as float; None if unparseable."""
    text = text.strip().replace(" ", "")
    if text in ("", "-", "—"):
        return None
    try:
        if name in _INT_COLUMNS:
            return int(float(text))
        return float(text)
    except ValueError:
        return None


def _scrape_pages(
    symbol: str,
    start_date: date,
    end_date: date,
    fetch_delay_s: float,
    col_indices: dict[str, int],
) -> Iterator[dict]:
    """Yield history rows within ``[start_date, end_date]`` (newest-first).

    Paginates ``/notowania-historyczne/{symbol}`` one page at a time.  Stops
    early as soon as a row is older than ``start_date`` (rows are newest-first,
    so nothing older can be in range).  ``col_indices`` maps row fields to
    table column indices, e.g. ``{"date": 0, "close": 1}`` for funds.
    Sleeps ``fetch_delay_s`` between page fetches (never before the first).
    Raises ``BiznesRadarNotFound`` on a non-200 response or a missing table.
    """
    symbol = strip_wa_suffix(symbol)
    page = 1
    while True:
        if page > 1:
            time.sleep(fetch_delay_s)
        url = f"{BASE_URL}{HISTORY_PATH}/{symbol}"
        if page > 1:
            url = f"{url},{page}"
        response = httpx.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
        )
        if response.status_code != 200:
            raise BiznesRadarNotFound(symbol)
        soup = BeautifulSoup(response.text, "lxml")
        table = soup.find("table")
        if table is None:
            raise BiznesRadarNotFound(symbol)
        exhausted = False
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) <= max(col_indices.values()):
                continue
            try:
                row_date = datetime.strptime(cells[col_indices["date"]], DATE_FORMAT).date()
            except ValueError:
                continue
            if row_date < start_date:
                exhausted = True
                break
            if row_date > end_date:
                continue
            row = {"date": row_date}
            for name, idx in col_indices.items():
                if name != "date":
                    row[name] = _parse_cell(cells[idx], name)
            yield row
        if exhausted:
            break
        next_link = soup.select_one('a.pages_right[title="następna"]')
        if next_link is None:
            break
        page += 1