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

import re
import time
from collections.abc import Iterator
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.biznesradar.pl"
HISTORY_PATH = "/notowania-historyczne"
NOTOWANIA_PATH = "/notowania"
USER_AGENT = "Mozilla/5.0"
DATE_FORMAT = "%d.%m.%Y"
REQUEST_TIMEOUT = 30.0

# Dividend calendar (52.2): /dywidendy/,YYYY,{sortCol},{dir} — sortCol 4
# (Dzień wypłaty) gives a payment-date-ordered page. Pages carry a full year's
# rows in a single tbody (no pagination footer), so the date-window filter is
# applied client-side after parsing.
DYWIDENDY_PATH = "/dywidendy"
DYWIDENDY_SORT_COL = 4
DYWIDENDY_SORT_DIR = 2

# Polish short month abbreviations as used in "05 sie 26" / "30 gru 26".
_PL_MONTHS = {
    "sty": 1, "lut": 2, "mar": 3, "kwi": 4, "maj": 5, "cze": 6,
    "lip": 7, "sie": 8, "wrz": 9, "paź": 10, "lis": 11, "gru": 12,
}


def _dywidendy_url(year: int, sort_col: int = DYWIDENDY_SORT_COL, sort_dir: int = DYWIDENDY_SORT_DIR) -> str:
    """Build a /dywidendy/ calendar URL for a given year (52.2).

    Format: ``/dywidendy/,YYYY,{sortCol},{dir}`` (e.g. ``,2026,4,2`` — sorted
    by Dzień wypłaty descending, i.e. payment-date-ordered). ``sort_col=4`` is
    the payment-date column; ``sort_dir=2`` is descending.
    """
    return f"{BASE_URL}{DYWIDENDY_PATH}/,{year},{sort_col},{sort_dir}"

# Page-title wrapping used for the /notowania probe: "Notowania {NAME}..."
# followed by "...- BiznesRadar.pl".
_TITLE_PREFIX = "Notowania"
_TITLE_SUFFIX = "- BiznesRadar.pl"

# Dotted exchange tags that upstream providers append (yfinance/FMP use `.WA`
# for the Warsaw Stock Exchange). biznesradar URLs must NOT carry them, while
# the `.TFI` / `.FIZ` venue codes and Catalyst symbol codes must be preserved.
_EXCHANGE_SUFFIXES = ("WA",)

# Value columns that are plain integers rather than dot-decimal prices.
_INT_COLUMNS = {"volume"}


class BiznesRadarNotFound(Exception):
    """Raised when biznesradar returns no parseable price table for a symbol."""


_FUND_SUFFIXES = (".tfi", ".fiz")


def default_currency_for_symbol(symbol: str) -> str | None:
    """Known-universe default currency when the page meta is absent (47.2).

    Every TFI/FIZ fund on biznesradar (Catalyst fund universe) prices in PLN
    by construction — the page ``<meta itemprop="priceCurrency">`` always agrees
    when present, and omitting it (as some fund pages do, e.g. NNEP65.TFI
    before biznesradar added the tag) must NOT silently fall back to USD.
    Returns ``"PLN"`` for ``.TFI`` / ``.FIZ`` symbols (case-insensitive),
    ``None`` otherwise — callers omit the key when both meta and default are
    absent.
    """
    return "PLN" if symbol.lower().endswith(_FUND_SUFFIXES) else None


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


def probe_notowania(symbol: str, fetch_delay_s: float = 0.0) -> str | None:
    """Probe ``/notowania/{symbol}`` for a resolvable instrument name (D78).

    Returns the instrument's display name when the page resolves — HTTP 200
    plus at least one ``qTableFull`` quote table — otherwise ``None``.  ``.WA``
    is stripped for the URL (biznesradar never carries it); the name is read
    from the page title (``Notowania {NAME}- BiznesRadar.pl``), with the page
    ``h2`` as a fallback.  Reuses the D77 fetch infrastructure (User-Agent,
    timeout, ``BeautifulSoup``), so politeness/rate-limit behaviour stays in a
    single place.  ``fetch_delay_s``, when > 0, sleeps before the request.
    """
    name, _ = probe_notowania_full(symbol, fetch_delay_s=fetch_delay_s)
    return name


def probe_notowania_full(symbol: str, fetch_delay_s: float = 0.0) -> tuple[str | None, str | None]:
    """Like :func:`probe_notowania` but also returns the page currency (45.1).

    Returns ``(name, currency)``: the display name (see
    :func:`probe_notowania`) plus the ``<meta itemprop="priceCurrency">``
    value from the same page (e.g. ``"PLN"`` for every Polish fund page).
    Either element may be ``None``; both are ``None`` when the page does not
    resolve.  The profile probe and the quote scrape share this single fetch
    of ``/notowania/{symbol}``.
    """
    symbol = strip_wa_suffix(symbol)
    if fetch_delay_s > 0:
        time.sleep(fetch_delay_s)
    url = f"{BASE_URL}{NOTOWANIA_PATH}/{symbol}"
    try:
        response = httpx.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
        )
    except httpx.HTTPError:
        return None, None
    if response.status_code != 200:
        return None, None
    soup = BeautifulSoup(response.text, "lxml")
    if soup.find("table", class_=lambda c: c and "qTableFull" in c) is None:
        return None, None
    return _name_from_soup(soup), _currency_from_soup(soup) or default_currency_for_symbol(symbol)


def _currency_from_soup(soup) -> str | None:
    """Read the price currency from the page meta tag (45.1).

    ``<meta itemprop="priceCurrency" content="PLN" />`` declares the quote
    currency of every biznesradar instrument page (Polish fund pages say
    ``PLN``).  Returns the upper-cased ISO code, or ``None`` when the tag is
    absent — callers must omit the key rather than emit ``None`` so the raw
    row stays backwards-compatible.
    """
    tag = soup.find("meta", attrs={"itemprop": "priceCurrency"})
    if tag is None:
        return None
    content = (tag.get("content") or "").strip().upper()
    return content or None


def _name_from_soup(soup) -> str | None:
    """Read the instrument name from a page title, ``h2`` as fallback."""
    title = soup.title.get_text(strip=True) if soup.title else ""
    name = title
    if name.startswith(_TITLE_PREFIX):
        name = name[len(_TITLE_PREFIX):].lstrip()
    if _TITLE_SUFFIX in name:
        name = name.split(_TITLE_SUFFIX, 1)[0].strip()
    if name:
        return name
    h2 = soup.find("h2")
    if h2:
        text = h2.get_text(strip=True)
        if text:
            return text
    return None


def probe_first_nav(symbol: str, fetch_delay_s: float = 0.0) -> date | None:
    """A fund's oldest NAV date, from the **oldest** history page (45.5).

    Fetches page 1 of ``/notowania-historyczne/{symbol}`` only to read the
    pagination footer's last page number (a ``pages_pos`` link — the highest
    index, e.g. the ``34`` in the ellipsis-then-``34`` footer), then fetches
    that last page (the oldest rows, since pages are newest-first) and returns
    the minimum row date.  Two page fetches total, **once per fund lifetime**
    (the caller caches the result in Redis — inception never changes), so it
    costs one extra probe per fund, not per request.  Returns ``None`` when the
    page does not resolve or has no parseable rows — callers must keep the
    requested start (never block the request on a probe failure).
    """
    symbol = strip_wa_suffix(symbol)
    if fetch_delay_s > 0:
        time.sleep(fetch_delay_s)
    response = httpx.get(
        f"{BASE_URL}{HISTORY_PATH}/{symbol}",
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        return None
    last = _last_page_number(BeautifulSoup(response.text, "lxml"))
    if last is None or last < 2:
        return None
    if fetch_delay_s > 0:
        time.sleep(fetch_delay_s)
    response = httpx.get(
        f"{BASE_URL}{HISTORY_PATH}/{symbol},{last}",
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        return None
    return _oldest_date_on_page(BeautifulSoup(response.text, "lxml"))


def _last_page_number(soup) -> int | None:
    """Highest page index referenced by a ``pages_pos`` footer link."""
    numbers: list[int] = []
    for a in soup.select("a.pages_pos"):
        m = re.search(r",(\d+)\s*$", a.get("href") or "")
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers) if numbers else None


def _oldest_date_on_page(soup) -> date | None:
    """Minimum data-row date on a history page (last-page rows are the oldest)."""
    table = soup.find("table")
    if table is None:
        return None
    oldest: date | None = None
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if not cells:
            continue
        try:
            d = datetime.strptime(cells[0], DATE_FORMAT).date()
        except ValueError:
            continue
        if oldest is None or d < oldest:
            oldest = d
    return oldest


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


# ---------------------------------------------------------------------------
# Dividend calendar (plan §52.2) — Polish short dates + /dywidendy/ table
# ---------------------------------------------------------------------------

_PL_SHORT_DATE_RE = re.compile(r"^(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{2})$")


def parse_pl_short_date(text: str) -> date | None:
    """Parse a Polish short date ``DD MMM YY`` (e.g. ``05 sie 26``).

    Confirmed against the 52.1 fixtures: every date cell on the /dywidendy/
    page is ``DD MMM YY`` with a 3-letter Polish month abbreviation
    (sty/lut/mar/kwi/maj/cze/lip/sie/wrz/paź/lis/gru) and a 2-digit year
    mapped onto ``2000+YY``. Returns ``None`` for empty / ``bd.`` / unparseable
    text — callers must omit the date rather than emit ``None``.
    """
    m = _PL_SHORT_DATE_RE.match(text.strip())
    if m is None:
        return None
    day_s, month_s, year_s = m.groups()
    month = _PL_MONTHS.get(month_s.lower())
    if month is None:
        return None
    try:
        return date(2000 + int(year_s), month, int(day_s))
    except ValueError:
        return None


def _parse_pln_amount(text: str) -> float | None:
    """Parse a PLN amount cell (``0,74 PLN``) into a float; None if missing."""
    text = text.strip()
    if text in ("", "bd.", "-", "—"):
        return None
    text = text.replace(" ", "").replace("PLN", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def scrape_dividend_calendar(start_date: date, end_date: date) -> list[dict]:
    """Scrape the GPW dividend calendar for ``[start_date, end_date]`` (52.2).

    Fetches one ``/dywidendy/,YYYY,4,2`` page per year in the window (pages
    are payment-date-ordered; a full year's rows land in one table, never
    paginated) and filters the parsed rows client-side to the requested
    window. Returns rows shaped
    ``{ex_dividend_date, payment_date, amount, status, symbol}`` — ``amount``
    is a float (PLN, comma-decimal parsed), the dates are ``date`` objects,
    ``status`` is the raw Polish status string (``rekomendowana`` /
    ``uchwalona`` / ``wypłacona``), and dates/amount-only cells that are
    ``bd.`` are ``None``.
    """
    rows: list[dict] = []
    for year in range(start_date.year, end_date.year + 1):
        url = _dywidendy_url(year)
        try:
            response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        except httpx.HTTPError:
            continue
        if response.status_code != 200:
            continue
        soup = BeautifulSoup(response.text, "lxml")
        table = soup.find("table")
        if table is None:
            continue
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) != 8:
                continue
            ex_dividend_date = parse_pl_short_date(cells[3])
            payment_date = parse_pl_short_date(cells[4])
            amount = _parse_pln_amount(cells[5])
            if ex_dividend_date is None and payment_date is None:
                continue
            if start_date <= (payment_date or ex_dividend_date) <= end_date:
                rows.append(
                    {
                        "ex_dividend_date": ex_dividend_date,
                        "payment_date": payment_date,
                        "amount": amount,
                        "status": cells[7] or None,
                        "symbol": _symbol_from_profil_cell(cells[0]),
                    }
                )
    return rows


def _symbol_from_profil_cell(text: str) -> str | None:
    """Extract the ticker from a Profil cell (``STX (STALEXP)`` → ``STX``).

    The Profil column is ``SYMBOL (NAME)``; the symbol is the pre-paren token.
    """
    token = text.split(" (")[0].strip()
    return token or None


def scrape_quote(symbol: str) -> dict | None:
    """Scrape the current quote from ``/notowania/{symbol}`` (D78 17.3).

    Returns a dict with keys ``symbol``, ``name``, ``last_price``,
    ``change``, ``change_percent``, ``prev_close``, ``open``, ``high``,
    ``low``, ``volume`` when the page resolves; ``None`` otherwise.  The dict
    carries ``currency`` with the ISO code when the page declares
    ``<meta itemprop="priceCurrency" content="...">`` or the symbol belongs to
    the known Polish fund universe (``.TFI``/``.FIZ`` → ``"PLN"``, 47.2) — the
    key is omitted, not set to ``None``, only when neither applies.

    All numeric values are ``float`` (volume is ``int``); missing fields are
    ``None``.  ``.WA`` is stripped for the URL as in other scraper helpers.
    """
    clean = strip_wa_suffix(symbol)
    url = f"{BASE_URL}{NOTOWANIA_PATH}/{clean}"
    try:
        response = httpx.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    soup = BeautifulSoup(response.text, "lxml")
    # Require a qTableFull table — confirms it is an instrument page.
    if soup.find("table", class_=lambda c: c and "qTableFull" in c) is None:
        return None

    def _td(id_: str) -> str | None:
        tag = soup.find("td", id=id_)
        return tag.get_text(strip=True) if tag else None

    def _flt(id_: str) -> float | None:
        raw = _td(id_)
        if raw is None:
            return None
        return _parse_cell(raw, "price")

    def _int_val(id_: str) -> int | None:
        raw = _td(id_)
        if raw is None:
            return None
        v = _parse_cell(raw, "volume")
        return int(v) if v is not None else None

    # Change and change_percent come from the tr.current.compare_past row spans.
    change: float | None = None
    change_percent: float | None = None
    prev_close: float | None = None
    for tr in soup.find_all("tr", class_="current"):
        if "compare_past" in (tr.get("class") or []):
            pkt = tr.find("span", class_="q_ch_pkt")
            per = tr.find("span", class_="q_ch_per")
            prev = tr.find("span", class_="q_ch_prev")
            if pkt:
                try:
                    change = float(pkt.get_text(strip=True).replace(",", "."))
                except ValueError:
                    pass
            if per:
                raw_per = per.get_text(strip=True).strip("()")
                try:
                    change_percent = float(raw_per.rstrip("%").replace(",", ".")) / 100
                except ValueError:
                    pass
            if prev:
                try:
                    prev_close = float(prev.get_text(strip=True).replace(",", "."))
                except ValueError:
                    pass
            break

    quote = {
        "symbol": symbol,
        "name": _name_from_soup(soup),
        "last_price": _flt("pr_t_close"),
        "open": _flt("pr_t_open"),
        "high": _flt("pr_t_max"),
        "low": _flt("pr_t_min"),
        "volume": _int_val("pr_t_vol"),
        "change": change,
        "change_percent": change_percent,
        "prev_close": prev_close,
    }
    currency = _currency_from_soup(soup) or default_currency_for_symbol(clean)
    if currency is not None:
        quote["currency"] = currency
    return quote


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