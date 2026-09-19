"""obligacje.pl scraper — Catalyst corporate-bond profile (D80, step 25.2).

Extends the biznesradar plugin's scraping infrastructure (same httpx/BS4
stack, same politeness defaults) with a second target site:

  https://obligacje.pl/pl/obligacja/{SYMBOL}

Selectors are pinned against the captured fixture
``tests/fixtures/obligacje_bond_profile_BST0327.html`` (see
``tests/fixtures/obligacje/README.md`` for the full field map):

- profile table ``table.table-9``: two-column ``<tr><th>LABEL:</th><td>...</td></tr>``
  rows — Emitent, Seria, ISIN, Rynek, Status, Wartość nominalna, Zabezpieczenie,
  Typ oprocentowania, Oprocentowanie bieżące.
- maturity: ``Ważne daty`` block → ``h4:Dzień wykupu`` → first ``<li>`` (ISO date).

Numeric conventions: space thousands separator, dot decimal, ISO currency code
suffix (``100.00 PLN``).  Variable-rate margins live in the coupon-type text
(``zmienne WIBOR 3M +  4%``); there is no separate margin column on the detail
page — the catalogue page carries it (see 25.3 importer).
"""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

OBLIGACJE_BASE_URL = "https://obligacje.pl"
OBLIGACJE_PROFILE_PATH = "/pl/obligacja/{symbol}"
OBLIGACJE_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
OBLIGACJE_TIMEOUT = 30.0

# Catalyst corporate-bond code: 3 uppercase letters + 4 digits, optional `.WA`
# exchange tag, optional `-K` suffix (e.g. BOS0735-K).
CATALYST_BOND_RE = re.compile(r"^[A-Z]{3}\d{4}(?:\.WA)?(?:-K)?$")

# detail-page field label (incl. trailing colon) -> output key
_PROFILE_LABELS = {
    "Emitent:": "issuer",
    "Seria:": "series",
    "ISIN:": "isin",
    "Rynek:": "market",
    "Status:": "status",
    "Wartość nominalna:": "nominal",
    "Zabezpieczenie:": "secured",
    "Typ oprocentowania:": "coupon_type",
    "Oprocentowanie bieżące:": "current_rate",
}


def is_catalyst_bond_symbol(symbol: str) -> bool:
    """True for Catalyst corporate-bond codes (``BST0327``, ``BST0327.WA``, ``BOS0735-K``)."""
    return CATALYST_BOND_RE.match(symbol.strip().upper()) is not None


def parse_bond_profile_html(html: str) -> dict | None:
    """Parse an obligacje.pl bond-detail page into the corp-bond profile shape.

    Returns ``None`` when the page is not a bond detail page (no ``table-9``).
    Output keys: ``issuer, series, isin, market, status, nominal_value,
    nominal_currency, secured, coupon_type, current_rate, maturity,
    asset_type, country, currency``.  ``margin`` is ``None`` — the detail page
    embeds the margin in ``coupon_type`` for variable-rate bonds.
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="table-9")
    if table is None:
        return None

    fields: dict[str, str] = {}
    for th in table.find_all("th"):
        label = th.get_text(strip=True)
        key = _PROFILE_LABELS.get(label)
        if key is None:
            continue
        td = th.find_next_sibling("td")
        if td is None:
            continue
        fields[key] = _clean_cell(td)

    nominal_value: float | None = None
    nominal_currency: str | None = None
    nominal_raw = fields.pop("nominal", None)
    if nominal_raw:
        m = re.match(r"([\d\s.]+)\s*([A-Z]{3})\s*$", nominal_raw)
        if m:
            nominal_currency = m.group(2)
            nominal_value = _to_float(m.group(1))

    maturity = _parse_maturity(soup)

    return {
        "issuer": fields.get("issuer"),
        "series": fields.get("series"),
        "isin": fields.get("isin"),
        "market": fields.get("market"),
        "status": fields.get("status"),
        "nominal_value": nominal_value,
        "nominal_currency": nominal_currency,
        "secured": fields.get("secured"),
        "coupon_type": fields.get("coupon_type"),
        "current_rate": fields.get("current_rate"),
        "margin": None,
        "maturity": maturity,
        "asset_type": "corp_bond",
        "country": "PL",
        "currency": nominal_currency or "PLN",
    }


def scrape_bond_profile(symbol: str) -> dict | None:
    """Fetch and parse ``/pl/obligacja/{symbol}``; ``None`` on failure/404."""
    clean = symbol.strip().upper()
    if clean.endswith(".WA"):
        clean = clean[:-3]
    url = OBLIGACJE_BASE_URL + OBLIGACJE_PROFILE_PATH.format(symbol=clean)
    try:
        response = httpx.get(
            url, headers={"User-Agent": OBLIGACJE_USER_AGENT}, timeout=OBLIGACJE_TIMEOUT
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    profile = parse_bond_profile_html(response.text)
    if profile is None:
        return None
    profile["symbol"] = symbol
    return profile


def _clean_cell(td) -> str:
    return re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip()


def _to_float(text: str) -> float | None:
    try:
        return float(text.replace(" ", ""))
    except ValueError:
        return None


def _parse_maturity(soup) -> str | None:
    """Redemption date: ``Ważne daty`` block → ``Dzień wykupu`` h4 → first ``<li>``."""
    for h4 in soup.find_all("h4"):
        if "Dzień wykupu" in h4.get_text(strip=True):
            container = h4.find_next("div", class_="txt")
            if container is None:
                return None
            li = container.find("li")
            if li is None:
                return None
            m = re.search(r"\d{4}-\d{2}-\d{2}", li.get_text())
            return m.group(0) if m else None
    return None
