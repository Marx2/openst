"""dividendmax.com public-page scraper — dividend history (plan §52.4).

Key-free scrape of the dividendmax.com website (no paid API key).  Two requests
per symbol:

  1. ``GET /suggest.json?q={symbol}`` — unauthenticated JSON
     ``[{search, id, name, ticker, flag, image, path}]`` — resolve the ticker to
     the per-company ``/dividends`` page ``path``.  Partial *name* matches are
     included and one ticker can map to several listings (e.g. VOD UK plc + US
     ADR), so we match on an **exact ticker** (falling back to a dot-suffixed
     variant such as ``VOD.L`` → ``VOD``) and prefer the US listing on ties.
  2. ``GET {path}`` — the per-company page whose server-rendered table
     ``table[aria-label='Declared and forecast {NAME} dividends']`` carries the
     full dividend history (roughly the last 20 years of ``Paid`` rows plus a
     few ``Forecast`` rows) in a single unpaginated page.

Only ``Paid`` rows are exposed: the ``Forecast amount`` cell is sign-up gated
(``Sign up``) and the standard model requires a real amount.  Dates are English
``DD Mon YYYY`` (``31 Oct 2030``); a missing date is an en dash ``–``.  Amounts
are subunit notation — ``265c`` / ``4.5¢`` (US cents) / ``7.77p`` (pence) — and
are divided by 100.  The currency is per-row (``Decl. Currency``).

TOS: personal non-commercial use only — hence a politeness delay between the
two requests (``DIVIDENDMAX_FETCH_DELAY_S``, default 1 s) and the caller is
expected to cache aggressively.
"""

from __future__ import annotations

import os
import re
import time
from datetime import date
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.dividendmax.com"
SUGGEST_PATH = "/suggest.json"
USER_AGENT = "Mozilla/5.0"
REQUEST_TIMEOUT = 30.0

DEFAULT_FETCH_DELAY_S = 1.0
FETCH_DELAY_ENV = "DIVIDENDMAX_FETCH_DELAY_S"

# English month abbreviations for "DD Mon YYYY" (e.g. "31 Oct 2030").
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_EN_DATE_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$")
# Subunit amount: a number optionally followed by c / ¢ / p.
_AMOUNT_RE = re.compile(r"^([\d.,]+)\s*([c¢p]?)$")

# Cell text that means "no value".
_MISSING = {"", "-", "–", "—"}


def parse_en_date(text: str) -> date | None:
    """Parse an English ``DD Mon YYYY`` date (e.g. ``31 Oct 2030``).

    Returns ``None`` for a missing cell (``–``/``-``/``—``/empty) or any
    unparseable text — callers must omit the date rather than emit ``None``.
    """
    text = (text or "").strip()
    if text in _MISSING:
        return None
    m = _EN_DATE_RE.match(text)
    if m is None:
        return None
    day_s, month_s, year_s = m.groups()
    month = _MONTHS.get(month_s.lower()[:3])
    if month is None:
        return None
    try:
        return date(int(year_s), month, int(day_s))
    except ValueError:
        return None


def parse_subunit_amount(text: str) -> float | None:
    """Parse a subunit amount cell into a float.

    ``265c`` → 2.65, ``4.5¢`` → 0.045, ``7.77p`` → 0.0777, a bare ``1.5`` →
    1.5.  Returns ``None`` for a gated cell (``Sign up``), a missing value
    (``—``/``–``/empty), or anything unparseable.
    """
    text = (text or "").strip()
    if text in _MISSING or text.lower() == "sign up":
        return None
    m = _AMOUNT_RE.match(text)
    if m is None:
        return None
    number, suffix = m.groups()
    try:
        value = float(number.replace(",", ""))
    except ValueError:
        return None
    if suffix in ("c", "¢", "p"):
        value = value / 100
    return round(value, 4)


def _fetch_json(url: str):
    """GET a JSON endpoint; return the parsed object or ``None`` on any failure."""
    try:
        response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def resolve_path(symbol: str) -> str | None:
    """Resolve a ticker to its dividendmax ``/dividends`` page path.

    Matches an exact ticker (case-insensitive); if none, matches a dot-suffixed
    variant (``VOD.L`` → ``VOD``).  Among the candidates the US listing (path
    under ``/united-states``) is preferred — the pfire universe uses bare
    tickers for US.  Returns ``None`` when nothing matches.
    """
    clean = (symbol or "").strip().upper()
    if not clean:
        return None
    data = _fetch_json(f"{BASE_URL}{SUGGEST_PATH}?q={quote(clean)}")
    if not isinstance(data, list):
        return None
    exact = [e for e in data if str(e.get("ticker", "")).upper() == clean]
    candidates = exact or [
        e for e in data if clean.startswith(str(e.get("ticker", "")).upper() + ".")
    ]
    if not candidates:
        return None
    us = [e for e in candidates if str(e.get("path", "")).startswith("/united-states")]
    chosen = (us or candidates)[0]
    path = chosen.get("path")
    return path or None


def _history_table(soup: BeautifulSoup):
    """Locate the 'Declared and forecast … dividends' history table."""
    table = soup.find("table", attrs={"aria-label": re.compile(r"^Declared and forecast")})
    if table is None:
        table = soup.find("table", class_="mdc-data-table__table")
    return table


def _rows_from_table(table) -> list[dict]:
    """Parse the history table into raw ``Paid``-row dicts (no symbol set)."""
    rows: list[dict] = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) != 9:
            continue
        status, dividend_type, decl_date, ex_date, pay_date, currency, _forecast, declared, _accuracy = cells
        if status != "Paid":
            continue
        ex_dividend_date = parse_en_date(ex_date)
        amount = parse_subunit_amount(declared)
        if ex_dividend_date is None or amount is None:
            continue
        rows.append(
            {
                "ex_dividend_date": ex_dividend_date,
                "payment_date": parse_en_date(pay_date),
                "declaration_date": parse_en_date(decl_date),
                "amount": amount,
                "currency": currency or None,
                "dividend_type": dividend_type or None,
                "status": status,
            }
        )
    return rows


def scrape_dividend_history(symbol: str, fetch_delay_s: float | None = None) -> list[dict]:
    """Scrape the full ``Paid`` dividend history for ``symbol``.

    Two polite requests: ``/suggest.json`` then the ``/dividends`` page, with
    ``fetch_delay_s`` (default from ``DIVIDENDMAX_FETCH_DELAY_S``, 1 s) slept
    between them.  Returns rows shaped
    ``{symbol, ex_dividend_date, payment_date, declaration_date, amount,
    currency, dividend_type, status}`` — ``amount`` a float, dates ``date``
    objects (``None`` when the page shows ``–``).  Returns ``[]`` when the
    symbol is unknown on dividendmax or the page is unavailable.
    """
    if fetch_delay_s is None:
        fetch_delay_s = float(os.getenv(FETCH_DELAY_ENV, str(DEFAULT_FETCH_DELAY_S)))
    path = resolve_path(symbol)
    if not path:
        return []
    if fetch_delay_s > 0:
        time.sleep(fetch_delay_s)
    try:
        response = httpx.get(
            f"{BASE_URL}{path}", headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
        )
    except httpx.HTTPError:
        return []
    if response.status_code != 200:
        return []
    table = _history_table(BeautifulSoup(response.text, "lxml"))
    if table is None:
        return []
    rows = _rows_from_table(table)
    for row in rows:
        row["symbol"] = symbol
    return rows
