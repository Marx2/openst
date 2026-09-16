"""Pure pricing engine for Polish retail savings bonds (D79 19.5).

There is no secondary market for savings bonds — the Ministry of Finance
publishes each emission's issue parameters and, for CPI-linked series, the
redemption value is computed from those parameters plus the 12-month CPI
history. This module implements that computation as pure functions (no I/O, no
database): the catalogue rows (``BondSeries``) and CPI observations
(``CpiRow``) are passed in and a daily OHLCV redemption-value series comes out.

The formulas follow the official "listy emisyjne" (Załączniki nr 2/3) as
validated against the worked examples published on obligacjeskarbowe.pl:

* Capitalized series (TOS, ROS, EDO, ROD) accrue on the running capital. At
  each annual boundary the accrued interest is added to the nominal with
  grosz rounding::

      K_0 = N
      K_k = round(K_{k-1} * (1 + r_k), 2)

* Redemption during an annual period returns the capital plus the current
  period's annual interest pro-rated on ACT/ACT::

      WP(d) = K_{k-1} + K_{k-1} * r_k * a / ACT - fee

  where ``a`` = days from the period start to ``d`` (start included, ``d``
  excluded) and ``ACT`` = actual days in the period. ``K_{k-1} - N`` is the
  fully-capitalised interest of the earlier years.

* Non-capitalized series: OTS and COI accrue interest on the flat 100 PLN
  nominal (COI pays it out annually). OTS pays no interest before maturity —
  the site's published rule is that early redemption returns exactly the
  purchase amount — while COI redeems mid-year for ``N + current-year
  accrual``.

* Fees: the early-redemption fee ``b`` is taken from the accrued interest.
  In the first period it is capped at the accrued interest ("opłata pobierana
  do wysokości narosłych odsetek") so the redemption never drops below the
  nominal; for capitalized series that cap applies in every period; COI is
  charged in full from the second period on, even when the accrued interest
  is smaller (per-site rule). A 100 PLN floor protects the first period.

Rate schedule:

* ``fixed``            — the same annual rate (``margin``) every period.
* ``cpi_12m+margin``   — year 1 uses the published first-year rate
  (``BondSeries.first_rate``). The openst catalogue does not store that number
  (``bond_series`` keeps only the ongoing margin), so when ``first_rate`` is
  ``None`` the engine approximates year 1 as ``max(cpi, 0) + margin``. Years
  >= 2 use ``max(cpi, 0) + margin`` where ``cpi`` is the 12-month index
  published in the month preceding the period start; a negative (deflation)
  index is floored at 0% so the rate never drops below the margin.
* ``nbp_ref+margin``   — not priceable here; needs NBP reference-rate history
  that lands in D83. The engine raises ``ValueError`` for these series.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

# Rate rules the engine can price today (nbp_ref+margin arrives in D83).
_ANNUAL_RULES = frozenset({"fixed", "cpi_12m+margin"})

# Series that capitalise interest (monthly/annual compounding into the nominal).
_CAPITALIZED = frozenset({"TOS", "ROS", "EDO", "ROD"})


class BondRateError(RuntimeError):
    """Raised when a period's rate cannot be determined (e.g. stale CPI data)."""


@dataclass(frozen=True)
class CpiRow:
    """One 12-month CPI observation.

    ``date`` is the observation's month-end (the CPI the GUS publishes at that
    month), ``value`` the 12-month index in percent (``Decimal('3.89')`` = 3.89%).
    """

    date: date
    value: Decimal


@dataclass(frozen=True)
class BondSeries:
    """One savings-bond emission, mirroring the ``openst.bond_series`` row.

    ``rate_rule`` is one of ``fixed``, ``cpi_12m+margin`` or
    ``nbp_ref+margin``. ``margin`` is a percentage: the flat rate for ``fixed``
    series, the inflation/NBP add-on otherwise. ``first_rate`` is the published
    year-1 rate of CPI-linked series (see module docstring for the fallback).
    """

    symbol: str
    name: str
    series_code: str
    issue_date: date
    maturity_date: date
    term_months: int
    rate_rule: str
    margin: Decimal
    fee_b: Decimal
    nominal: Decimal = Decimal("100.00")
    first_rate: Decimal | None = None


# ---------------------------------------------------------------------------
# calendar / lookup helpers
# ---------------------------------------------------------------------------


def add_months(value: date, months: int) -> date:
    """Calendar-add whole months, clamping the day to the target month's last day."""
    total = value.month - 1 + months
    year = value.year + total // 12
    month = total % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _annual_periods(bond: BondSeries) -> list[tuple[date, date]]:
    """Annual interest periods [(start, end)) covering the term, per the list emisyjny."""
    periods: list[tuple[date, date]] = []
    start = bond.issue_date
    k = 1
    while start < bond.maturity_date:
        end = min(add_months(bond.issue_date, 12 * k), bond.maturity_date)
        periods.append((start, end))
        start = end
        k += 1
    return periods


def _period_count(bond: BondSeries) -> int:
    return len(_annual_periods(bond))


def _cpi_before(cpi_rows: list[CpiRow], at: date) -> CpiRow | None:
    """The CPI observation published in the calendar month before ``at``."""
    year, month = at.year, at.month - 1
    if month == 0:
        year, month = year - 1, 12
    for row in cpi_rows:
        if row.date.year == year and row.date.month == month:
            return row
    return None


# ---------------------------------------------------------------------------
# rate schedule
# ---------------------------------------------------------------------------


def _validate_rate_schedule(bond: BondSeries, cpi_rows: list[CpiRow]) -> None:
    """Fail fast: raise on non-priceable rules and on missing year-1 CPI."""
    rate_for_period(bond, cpi_rows, 1)


def rate_for_period(bond: BondSeries, cpi_rows: list[CpiRow], period_no: int) -> Decimal:
    """Annual rate (Decimal fraction) for ``period_no`` (1-based).

    CPI-linked series take ``max(cpi, 0) + margin`` for year 2 onwards, with
    the CPI published in the month preceding the period start; year 1 uses
    ``first_rate`` when given, else the same cpi+margin rule as a documented
    approximation (the catalog does not store the published year-1 rate).
    """
    if bond.rate_rule == "fixed":
        return bond.margin / Decimal(100)
    if bond.rate_rule == "cpi_12m+margin":
        if period_no == 1:
            if bond.first_rate is not None:
                return bond.first_rate / Decimal(100)
            anchor = bond.issue_date
        else:
            anchor = add_months(bond.issue_date, 12 * (period_no - 1))
        row = _cpi_before(cpi_rows, anchor)
        if row is None:
            raise BondRateError(
                f"{bond.symbol}: no CPI published in the month before {anchor} "
                f"needed for period {period_no}"
            )
        inflation = max(row.value, Decimal(0))
        return (inflation + bond.margin) / Decimal(100)
    raise ValueError(
        f"{bond.rate_rule!r} bonds are not priceable yet "
        "(NBP reference rates land in D83)"
    )


def _period_factor(bond: BondSeries, cpi_rows: list[CpiRow], period_no: int) -> Decimal:
    """Full-period growth factor ``(1 + r)``; the OTS quarter is scaled by 3/12."""
    rate = rate_for_period(bond, cpi_rows, period_no)
    if bond.series_code == "OTS":
        rate = rate * (Decimal(bond.term_months) / Decimal(12))
    return Decimal(1) + rate


# ---------------------------------------------------------------------------
# value functions
# ---------------------------------------------------------------------------


def capitalized_value(bond: BondSeries, cpi_rows: list[CpiRow], k: int) -> Decimal:
    """``K_k``: value after ``k`` full annual periods (grosz rounding per step).

    For the single-period OTS series this is the maturity redemption value.
    """
    value = bond.nominal
    for period_no in range(1, k + 1):
        factor = _period_factor(bond, cpi_rows, period_no)
        value = (value * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return value


def _period_at(bond: BondSeries, day: date) -> tuple[int, date, date]:
    """(period_no, start, end) for ``day`` inside the term (maturity excluded)."""
    for period_no, (start, end) in enumerate(_annual_periods(bond), start=1):
        if start <= day < end:
            return period_no, start, end
    raise BondRateError(f"{bond.symbol}: {day} is outside the interest periods")


def _validate_day(bond: BondSeries, day: date) -> None:
    if day < bond.issue_date or day > bond.maturity_date:
        raise ValueError(f"{day} is outside the term of {bond.symbol}")


def accrued_interest(bond: BondSeries, cpi_rows: list[CpiRow], day: date) -> Decimal:
    """Total interest accrued since purchase through ``day`` ("odsetki narosłe"),
    rounded to the grosz like the site's published figures.

    OTS earns no interest before maturity (published early-redemption rule).
    """
    _validate_day(bond, day)
    if day == bond.maturity_date:
        return (capitalized_value(bond, cpi_rows, _period_count(bond)) - bond.nominal).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    if bond.series_code == "OTS":
        return Decimal("0")
    period_no, start, end = _period_at(bond, day)
    if period_no == 1 or bond.series_code not in _CAPITALIZED:
        base = bond.nominal
        prior = Decimal("0")
    else:
        base = capitalized_value(bond, cpi_rows, period_no - 1)
        prior = base - bond.nominal
    rate = rate_for_period(bond, cpi_rows, period_no)
    elapsed = Decimal((day - start).days)
    actual = Decimal((end - start).days)
    total = prior + base * rate * elapsed / actual
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def redemption_value(bond: BondSeries, cpi_rows: list[CpiRow], day: date) -> Decimal:
    """Gross redemption value (PLN, one bond) if redeemed on ``day`` (pre-Belka tax).

    ``N + O - fee`` with the fee capped at the accrued interest for capitalized
    series (all periods) and in the first period for non-capitalized series, a
    100 PLN floor in the first period, and no fee at maturity.
    """
    _validate_day(bond, day)
    if day == bond.maturity_date:
        return capitalized_value(bond, cpi_rows, _period_count(bond))
    if bond.series_code == "OTS":
        return bond.nominal
    period_no, start, end = _period_at(bond, day)
    total_interest = accrued_interest(bond, cpi_rows, day)
    cap_fee = bond.series_code in _CAPITALIZED or period_no == 1
    fee = min(bond.fee_b, total_interest) if cap_fee else bond.fee_b
    value = bond.nominal + total_interest - fee
    if period_no == 1:
        value = max(value, bond.nominal)
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# daily price series
# ---------------------------------------------------------------------------


def price_series(
    bond: BondSeries,
    cpi_rows: list[CpiRow],
    start: date,
    end: date,
) -> list[dict]:
    """Daily OHLCV rows valuing one bond in the requested range.

    ``close`` is the gross redemption value on that day. Only dates inside the
    term are produced (the range is clamped to ``[issue_date, maturity_date]``
    and an empty range yields ``[]``). A missing CPI observation for a period
    covered by the range raises :class:`BondRateError` — the fetcher surfaces
    that as a stale-CPI error.
    """
    # Fail fast on priceable-rate checks and first-period CPI before walking days.
    _validate_rate_schedule(bond, cpi_rows)
    low = max(start, bond.issue_date)
    high = min(end, bond.maturity_date)
    if high < low:
        return []
    rows: list[dict] = []
    prev_close: float | None = None
    day = low
    while day <= high:
        close = redemption_value(bond, cpi_rows, day)
        close_float = float(close)
        open_float = prev_close if prev_close is not None else close_float
        rows.append(
            {
                "date": day.isoformat(),
                "open": open_float,
                "high": max(open_float, close_float),
                "low": min(open_float, close_float),
                "close": close_float,
                "volume": 0,
            }
        )
        prev_close = close_float
        day += timedelta(days=1)
    return rows


__all__ = [
    "BondRateError",
    "BondSeries",
    "CpiRow",
    "accrued_interest",
    "capitalized_value",
    "price_series",
    "rate_for_period",
    "redemption_value",
]