"""Savings-bond series importer (D79 19.4) — obligacjeskarbowe.pl -> openst.bond_series.

Data source: ``https://www.obligacjeskarbowe.pl/oferta-obligacji/``

The Ministry of Finance publishes the *currently active* emission of each of the
eight retail savings-bond series (OTS, ROR, DOR, TOS, COI, ROS, EDO, ROD). Every
emission offer page carries a ``<ul class="product-details__list">`` of
``<strong>label</strong> <span>value</span>`` rows (Seria, Oprocentowanie,
Sprzedaż, Cena sprzedaży, …) plus the redemption-fee schedule in the "Zamiana"
prose. There is no HTML data-table, so this is a DOM-field scraper (same
regex-based spirit as :mod:`src.importers.cpi`, not the biznesradar table pattern).

Site behaviour (verified 2026-09): the *offer/series* pages (``full``/``incremental``)
*always* render the currently-active emission — the URL's trailing symbol is cosmetic
there and every parameter (dates, rate, fee) is the live one. Those modes therefore
accumulate at most one emission per series per run, and new monthly emissions are
picked up over time. Archived emissions are different: each one has its own
``/oferta-obligacji/{slug}/{symbol}/`` page that renders its own historical parameters
(e.g. ``rod1033`` shows the sold-in-2021 emission, not the current one). The full
catalogue is enumerable from ``/listy-emisyjne/``, and ``--mode archive`` backfills it
by parsing every emission code from that selector and fetching each emission page;
``ON CONFLICT DO NOTHING`` keeps re-runs idempotent.

``rate_rule`` classification (from the "Oprocentowanie" row):
  * ``cpi_12m+margin``  — "… + inflacja" (COI, ROS, EDO, ROD)  -> margin = the "marża X%" add-on
  * ``nbp_ref+margin``  — "… stopa referencyjna NBP + X%" (ROR, DOR) -> margin = the NBP add-on
  * ``fixed``           — a flat annual rate (OTS, TOS)        -> margin = the flat rate

The schema comment lists the first two values; ``nbp_ref+margin`` is a third, honest
value for the short-term NBP-indexed series. Pricing those needs a reference-rate
history that is deferred to D83, so the 19.5 engine prices the ``fixed`` and
``cpi_12m+margin`` series and treats ``nbp_ref+margin`` as "variable, not yet priced".

Modes (the importer runs as a one-shot k8s Job reusing the openst image):
  full        — ``--mode full``         scrape all 8 series offer pages (initial import)
  incremental — ``--mode incremental``  scrape the current-offer page (~8 active) (daily CronJob)
  archive     — ``--mode archive``      backfill every emission enumerated on /listy-emisyjne/
                                        (all modern-series emissions, ~450 pages; monthly CronJob)
"""

from __future__ import annotations

import argparse
import calendar
import json
import re
import time
from datetime import date
from decimal import Decimal

import httpx

from src import db

BASE = "https://www.obligacjeskarbowe.pl"
OFFER_URL = f"{BASE}/oferta-obligacji/"
USER_AGENT = "Mozilla/5.0"
REQUEST_TIMEOUT = 30.0
SLEEP_BETWEEN = 0.5  # polite pause between per-emission fetches

# Offer-page slug per series code (path segment of /oferta-obligacji/{slug}/).
SERIES_SLUGS = {
    "OTS": "obligacje-3-miesieczne-ots",
    "ROR": "obligacje-roczne-ror",
    "DOR": "obligacje-2-letnie-dor",
    "TOS": "obligacje-3-letnie-tos",
    "COI": "obligacje-4-letnie-coi",
    "ROS": "obligacje-6-letnie-ros",
    "EDO": "obligacje-10-letnie-edo",
    "ROD": "obligacje-12-letnie-rod",
}

# Term in months per series code (from the product name: "3-miesięczne", "roczne", …).
TERM_MONTHS = {
    "OTS": 3,
    "ROR": 12,
    "DOR": 24,
    "TOS": 36,
    "COI": 48,
    "ROS": 72,
    "EDO": 120,
    "ROD": 144,
}

# Redemption fee `b` (PLN per bond) per series, used as a fallback when the page's
# fee prose is absent (e.g. OTS has no fee). Values reflect the current published
# schedule as of 2026-09.
FEE_DEFAULT = {
    "OTS": Decimal("0"),
    "ROR": Decimal("0.50"),
    "DOR": Decimal("0.70"),
    "TOS": Decimal("1.00"),
    "COI": Decimal("2.00"),
    "ROS": Decimal("2.00"),
    "EDO": Decimal("3.00"),
    "ROD": Decimal("3.00"),
}

# One <li> row of the product-details list: a label <strong> and a value <span>.
_DETAIL_ROW_RE = re.compile(
    r'<strong class="product-details__list-label">(.*?)</strong>\s*'
    r'<span class="product-details__list-value">(.*?)</span>',
    flags=re.S,
)

# Offer-page links to per-emission pages, e.g.
#   href="/oferta-obligacji/obligacje-10-letnie-edo/edo0936/"
_OFFER_HREF_RE = re.compile(r'href="(/oferta-obligacji/([a-z0-9\-]+)/([a-z0-9]+)/)"')

_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", flags=re.S)
_SYMBOL_RE = re.compile(r"\b([A-Za-z]{3}\d{4})\b")
_PL_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")

# One `<option … data-id="{series}">{SYMBOL}</option>` row of the /listy-emisyjne/
# emission selector. data-id is the series code (lower-case); the symbol is the
# option's display text — NOT the URL id, which the site has shipped with typos
# (e.g. id=edo07829 for the EDO0829 emission).
_ARCHIVE_ROW_RE = re.compile(
    r'<option\b[^>]*?\bdata-id="([a-z]{3})"[^>]*>\s*([A-Z]{3}\d{4})\s*</option>',
    flags=re.S,
)


class BondFetchError(RuntimeError):
    """Raised when obligacjeskarbowe.pl returns a non-200 for a fetch."""


# ---------------------------------------------------------------------------
# small text helpers
# ---------------------------------------------------------------------------


def _strip_tags(fragment: str) -> str:
    """Drop tags / entities-ish whitespace from an HTML fragment and normalise it."""
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    fragment = fragment.replace("\xa0", " ")
    fragment = fragment.replace(" ", " ")
    return re.sub(r"\s+", " ", fragment).strip()


def _dec(value: str) -> Decimal:
    """Parse a Polish number (comma decimal, possible "zł"/"%" suffix) as a Decimal."""
    value = value.replace("\xa0", " ").strip()
    value = re.sub(r"[^\d,.-]", "", value)
    if value in ("", "-", "."):
        return Decimal("0")
    return Decimal(value.replace(",", "."))


def _page_text(html: str) -> str:
    """Whole-page text with scripts/styles stripped and whitespace normalised."""
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("\xa0", " ").replace(" ", " ")
    return re.sub(r"[ \t]+", " ", text)


def _parse_pl_date(fragment: str) -> date | None:
    """Parse the first ``DD.MM.YYYY`` date in a fragment (Polish format)."""
    match = _PL_DATE_RE.search(fragment)
    if not match:
        return None
    day, month, year = (int(match.group(i)) for i in (1, 2, 3))
    return date(year, month, day)


def add_months(value: date, months: int) -> date:
    """Calendar-add whole months, clamping the day to the target month's last day."""
    total = value.month - 1 + months
    year = value.year + total // 12
    month = total % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# ---------------------------------------------------------------------------
# detail-page parsing
# ---------------------------------------------------------------------------


def parse_detail_list(html: str) -> dict[str, str]:
    """Extract the ``product-details__list`` rows into a ``{label: value}`` map.

    Labels are lower-cased, de-colonised and stripped; values have their tags and
    trailing helper links ("Zobacz list emisyjny", "Zobacz tabelę odsetkową")
    stripped out by :func:`_strip_tags` (tags removed, text kept and normalised).
    """
    items: dict[str, str] = {}
    for label, value in _DETAIL_ROW_RE.findall(html):
        key = _strip_tags(label).rstrip(":").strip().lower()
        if key:
            items[key] = _strip_tags(value)
    return items


def _row(items: dict[str, str], prefix: str) -> str | None:
    """First value whose normalised label starts with ``prefix`` (ASCII-safe)."""
    for key, value in items.items():
        if key.startswith(prefix):
            return value
    return None


def _classify_rate(rate_text: str) -> str:
    """Map the "Oprocentowanie" prose to a ``rate_rule`` value."""
    lowered = rate_text.lower()
    if "inflacja" in lowered or "cpi" in lowered:
        return "cpi_12m+margin"
    if "nbp" in lowered or "referencyjn" in lowered or "wibor" in lowered:
        return "nbp_ref+margin"
    return "fixed"


def _extract_margin(rate_text: str, rate_rule: str) -> Decimal:
    """Pull the rate/margin percentage out of the "Oprocentowanie" prose.

    * cpi-linked  -> the "marża X%" add-on (the ongoing margin over inflation)
    * NBP-indexed -> the "NBP + X%" add-on
    * fixed       -> the flat "X%" annual rate (first percentage in the prose)
    """
    if rate_rule == "cpi_12m+margin":
        match = re.search(r"marż[aę]\s+([\d,]+)\s*%", rate_text, flags=re.I)
        if match:
            return _dec(match.group(1))
    elif rate_rule == "nbp_ref+margin":
        match = re.search(r"nbp\s*\+?\s*([\d,]+)\s*%", rate_text, flags=re.I)
        if match:
            return _dec(match.group(1))
    match = re.search(r"([\d,]+)\s*%", rate_text)
    if match:
        return _dec(match.group(1))
    return Decimal("0")


def _extract_fee(page_text: str, series_code: str) -> Decimal:
    """Redemption fee ``b``: the *last* "opłata wynosi X zł" (current schedule),
    falling back to the per-series default when the prose is absent."""
    fees = re.findall(r"opłata wynosi ([\d,]+)\s*zł", page_text, flags=re.I)
    if fees:
        return _dec(fees[-1])
    return FEE_DEFAULT.get(series_code, Decimal("0"))


def parse_emission(html: str) -> dict | None:
    """Parse one emission offer page into a ``bond_series`` row dict.

    Returns ``None`` when the page has no usable "Seria" row (e.g. a series page
    with no currently-active emission) so callers can skip it gracefully.
    """
    items = parse_detail_list(html)
    seria = _row(items, "seria")
    if not seria:
        return None

    symbol_match = _SYMBOL_RE.search(seria)
    if not symbol_match:
        return None
    symbol = symbol_match.group(1).upper()
    series_code = symbol[:3]

    h1 = _H1_RE.search(html)
    name = _strip_tags(h1.group(1)) if h1 else f"Obligacje {series_code}"

    issue_date = _parse_pl_date(_row(items, "sprzeda") or "")
    if issue_date is None:
        return None
    term_months = TERM_MONTHS.get(series_code, 0)

    rate_text = _row(items, "oprocentowanie") or ""
    rate_rule = _classify_rate(rate_text)
    margin = _extract_margin(rate_text, rate_rule)

    return {
        "symbol": symbol,
        "name": name,
        "series_code": series_code,
        "issue_date": issue_date,
        "maturity_date": add_months(issue_date, term_months),
        "term_months": term_months,
        "rate_rule": rate_rule,
        "margin": margin,
        "fee_b": _extract_fee(_page_text(html), series_code),
        "nominal": Decimal("100.00"),
    }


# ---------------------------------------------------------------------------
# offer-page parsing (incremental entry point)
# ---------------------------------------------------------------------------


def parse_offer_emissions(html: str) -> list[str]:
    """Per-emission path URLs (``/oferta-obligacji/{slug}/{symbol}/``) listed on
    the current-offer page, de-duplicated and in page order."""
    seen: set[str] = set()
    urls: list[str] = []
    for path, _slug, _symbol in _OFFER_HREF_RE.findall(html):
        if path not in seen:
            seen.add(path)
            urls.append(path)
    return urls


def parse_archive_codes(html: str) -> list[tuple[str, str]]:
    """Emission ``(series_code, symbol)`` pairs from the ``/listy-emisyjne/`` selector.

    The selector enumerates the full catalogue — past and active emissions across
    all series — as ``<option data-id="{series}">{SYMBOL}</option>`` rows. The
    symbol is always read from the display text (not the URL ``id=``), which is the
    site's typos for archived EDO codes (``id=edo07829`` renders ``EDO0829``).
    """
    return [(series.upper(), symbol) for series, symbol in _ARCHIVE_ROW_RE.findall(html)]


# ---------------------------------------------------------------------------
# fetching
# ---------------------------------------------------------------------------


def fetch_page(path_or_url: str) -> str:
    """GET a page (following redirects); raise :class:`BondFetchError` on a non-200.

    The site 302-redirects some paths (e.g. the bare ``/oferta-obligacji/`` and
    per-series slugs), so redirects are followed and the final status is checked.
    """
    url = path_or_url if path_or_url.startswith("http") else BASE + path_or_url
    response = httpx.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    )
    if response.status_code != 200:
        raise BondFetchError(f"{url} -> HTTP {response.status_code}")
    return response.text


def _sleep() -> None:
    if SLEEP_BETWEEN > 0:
        time.sleep(SLEEP_BETWEEN)


def run(mode: str) -> dict:
    """Fetch (and, with a DB, insert) emissions for a mode; returns a summary dict."""
    if mode == "full":
        # Authoritative pass: one page per series (all eight), robust even if a
        # series drops off the aggregated offer page.
        paths = [f"/oferta-obligacji/{slug}/" for slug in SERIES_SLUGS.values()]
    elif mode == "incremental":
        offer_html = fetch_page(OFFER_URL)
        paths = parse_offer_emissions(offer_html)
    elif mode == "archive":
        # Backfill: enumerate every emission code on /listy-emisyjne/, then parse
        # each emission's own historical page. The modern 8 series only — the
        # selector also carries the legacy POS/DOS/TOZ/KOS codes, which have no
        # term map and are out of scope.
        archive_html = fetch_page("/listy-emisyjne/")
        paths = [
            f"/oferta-obligacji/{SERIES_SLUGS[series]}/{symbol.lower()}/"
            for series, symbol in parse_archive_codes(archive_html)
            if series in SERIES_SLUGS
        ]
    else:
        raise ValueError(f"unknown mode: {mode}")

    emissions: list[dict] = []
    for i, path in enumerate(paths):
        if i:
            _sleep()
        page = fetch_page(path)
        emission = parse_emission(page)
        if emission is not None:
            emissions.append(emission)

    summary: dict = {"mode": mode, "fetched": len(paths), "emissions": len(emissions)}
    symbols = [e["symbol"] for e in emissions]
    if any(symbols):
        summary["symbols"] = symbols

    if db.database_url():
        conn = db.get_conn()
        try:
            summary["inserted"] = upsert_bonds(conn, emissions)
        finally:
            conn.close()
    return summary


def upsert_bonds(conn, emissions: list[dict]) -> int:
    """Insert emissions into ``openst.bond_series``, ignoring duplicate symbols.

    Emissions are immutable once published, so re-imports of a known symbol are
    no-ops (``ON CONFLICT DO NOTHING``). Returns the number of rows inserted.
    """
    inserted = 0
    with conn.cursor() as cur:
        for e in emissions:
            cur.execute(
                """
                INSERT INTO openst.bond_series (
                    symbol, name, series_code, issue_date, maturity_date,
                    term_months, rate_rule, margin, fee_b, nominal
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO NOTHING
                """,
                (
                    e["symbol"],
                    e["name"],
                    e["series_code"],
                    e["issue_date"],
                    e["maturity_date"],
                    e["term_months"],
                    e["rate_rule"],
                    e["margin"],
                    e["fee_b"],
                    e["nominal"],
                ),
            )
            inserted += cur.rowcount
    conn.commit()
    return inserted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="src.importers.bond_series",
        description=(
            "Import retail savings-bond emissions from obligacjeskarbowe.pl "
            "into openst.bond_series."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental", "archive"],
        default="incremental",
        help=(
            "full = all 8 series offer pages (initial import); "
            "incremental = current-offer page only (default, daily CronJob); "
            "archive = backfill every emission on /listy-emisyjne/ (monthly CronJob)"
        ),
    )
    args = parser.parse_args(argv)
    summary = run(args.mode)
    print(json.dumps(summary, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())