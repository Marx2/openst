"""Pricing engine tests (D79 19.5) — validated against obligacjeskarbowe.pl worked examples.

The expected values below come from the site's published worked examples
(EDO0524: 102,16 / 4,16; TOS0825: 107,26 / 7,96 and 105,88 net; ROS1022:
2,91; OTS0118: early redemption returns the purchase amount). The treasury
multi-year EDO/TOS values are hand-computed from the official "listy emisyjne"
formulas with grosz (ROUND_HALF_UP) capitalisation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from openbb_obligacje import engine
from openbb_obligacje.engine import (
    BondRateError,
    BondSeries,
    CpiRow,
    accrued_interest,
    add_months,
    capitalized_value,
    price_series,
    rate_for_period,
    redemption_value,
)


def _bond(**over) -> BondSeries:
    base = {
        "symbol": "TEST0000",
        "name": "test",
        "series_code": "EDO",
        "issue_date": date(2026, 9, 1),
        "maturity_date": date(2036, 9, 1),
        "term_months": 120,
        "rate_rule": "cpi_12m+margin",
        "margin": Decimal("2.00"),
        "fee_b": Decimal("3.00"),
        "first_rate": None,
    }
    base.update(over)
    return BondSeries(**base)


def _cpi_rows(values: dict[date, str]) -> list[CpiRow]:
    return [CpiRow(d, Decimal(v)) for d, v in values.items()]


# ---------------------------------------------------------------------------
# add_months
# ---------------------------------------------------------------------------


def test_add_months_round_trip_and_clamping():
    assert add_months(date(2024, 5, 10), 12) == date(2025, 5, 10)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2024, 3, 31), -1) == date(2024, 2, 29)
    assert add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)


# ---------------------------------------------------------------------------
# OTS0118 — published early-redemption rule (D79 19.5, worked example from ots.html)
# ---------------------------------------------------------------------------


def _ots0118() -> BondSeries:
    return _bond(
        symbol="OTS0118",
        name="OTS0118",
        series_code="OTS",
        issue_date=date(2017, 10, 10),
        maturity_date=date(2018, 1, 10),
        term_months=3,
        rate_rule="fixed",
        margin=Decimal("1.50"),
        fee_b=Decimal("0.00"),
    )


def test_ots_early_redemption_pays_no_interest():
    bond = _ots0118()
    assert redemption_value(bond, [], date(2017, 11, 29)) == Decimal("100.00")
    assert accrued_interest(bond, [], date(2017, 11, 29)) == Decimal("0")


def test_ots_issue_day_value():
    bond = _ots0118()
    assert redemption_value(bond, [], date(2017, 10, 10)) == Decimal("100.00")


def test_ots_maturity_carries_promised_quarterly_rate():
    bond = _ots0118()
    assert redemption_value(bond, [], date(2018, 1, 10)) == Decimal("100.38")
    assert accrued_interest(bond, [], date(2018, 1, 10)) == Decimal("0.38")


# ---------------------------------------------------------------------------
# TOS0825 — published mid-year accrual (7,96 at 17.10.2023; 107,26 gross; 105,88 net)
# ---------------------------------------------------------------------------


def _tos0825() -> BondSeries:
    return _bond(
        symbol="TOS0825",
        name="TOS0825",
        series_code="TOS",
        issue_date=date(2022, 8, 1),
        maturity_date=date(2025, 8, 1),
        term_months=36,
        rate_rule="fixed",
        margin=Decimal("6.50"),
        fee_b=Decimal("0.70"),
    )


def test_tos_published_year_two_accrual():
    bond = _tos0825()
    assert accrued_interest(bond, [], date(2023, 10, 17)) == Decimal("7.96")
    assert redemption_value(bond, [], date(2023, 10, 17)) == Decimal("107.26")


def test_tos_first_period_mid_year_capitalised_accrual():
    bond = _tos0825()
    assert redemption_value(bond, [], date(2022, 12, 1)) == Decimal("101.47")


def test_tos_period_boundaries_and_maturity():
    bond = _tos0825()
    assert redemption_value(bond, [], date(2022, 8, 1)) == Decimal("100.00")
    assert redemption_value(bond, [], date(2023, 8, 1)) == Decimal("105.80")
    assert redemption_value(bond, [], date(2024, 8, 1)) == Decimal("112.72")
    assert capitalized_value(bond, [], 3) == Decimal("120.79")
    assert redemption_value(bond, [], date(2025, 8, 1)) == Decimal("120.79")


# ---------------------------------------------------------------------------
# EDO0524 — published year-2 accrual (4,16 at 16.06.2015; 102,16 gross; 101,75 net)
# ---------------------------------------------------------------------------


def _edo0524() -> BondSeries:
    return _bond(
        symbol="EDO0524",
        name="EDO0524",
        series_code="EDO",
        issue_date=date(2014, 5, 10),
        maturity_date=date(2024, 5, 10),
        term_months=120,
        rate_rule="cpi_12m+margin",
        margin=Decimal("0.50"),
        fee_b=Decimal("2.00"),
        first_rate=Decimal("4.00"),
    )


def test_edo_published_year_two_accrual():
    bond = _edo0524()
    rows = _cpi_rows({date(2015, 4, 30): "1.00"})
    assert accrued_interest(bond, rows, date(2015, 6, 16)) == Decimal("4.16")
    assert redemption_value(bond, rows, date(2015, 6, 16)) == Decimal("102.16")


def test_edo_period_two_start_after_capitalisation_and_fee():
    bond = _edo0524()
    rows = _cpi_rows({date(2015, 4, 30): "1.00"})
    assert redemption_value(bond, rows, date(2014, 5, 10)) == Decimal("100.00")
    assert redemption_value(bond, rows, date(2015, 5, 10)) == Decimal("102.00")


def test_edo_ten_year_capitalisation():
    bond = _edo0524()
    rows = _cpi_rows({date(y, 4, 30): "2.00" for y in range(2015, 2024)})
    assert capitalized_value(bond, rows, 10) == Decimal("129.89")
    assert redemption_value(bond, rows, date(2024, 5, 10)) == Decimal("129.89")


# ---------------------------------------------------------------------------
# COI — non-capitalized: fee capped in period 1, full fee in later periods
# ---------------------------------------------------------------------------


def _coi0930() -> BondSeries:
    return _bond(
        symbol="COI0930",
        name="COI0930",
        series_code="COI",
        issue_date=date(2026, 9, 1),
        maturity_date=date(2030, 9, 1),
        term_months=48,
        rate_rule="cpi_12m+margin",
        margin=Decimal("1.50"),
        fee_b=Decimal("2.00"),
        first_rate=Decimal("4.75"),
    )


def test_coi_first_period_fee_capped_at_accrued_interest():
    bond = _coi0930()
    rows = _cpi_rows({date(2027, 8, 31): "3.00"})
    assert redemption_value(bond, rows, date(2026, 10, 1)) == Decimal("100.00")


def test_coi_later_period_charges_full_fee():
    bond = _coi0930()
    rows = _cpi_rows({date(2027, 8, 31): "3.00"})
    assert redemption_value(bond, rows, date(2027, 9, 1)) == Decimal("98.00")
    assert redemption_value(bond, rows, date(2027, 10, 1)) == Decimal("98.37")


# ---------------------------------------------------------------------------
# CPI rate schedule
# ---------------------------------------------------------------------------


def test_cpi_rate_uses_month_before_period_start_with_negative_floor():
    bond = _bond(margin=Decimal("2.00"))  # first_rate None -> fallback for year 1
    rows = _cpi_rows(
        {
            date(2026, 8, 31): "3.00",   # year-1 fallback: 3.00 + 2.00 = 5.00%
            date(2027, 8, 31): "-0.50",  # floored to 0 -> 0.00 + 2.00 = 2.00%
        }
    )
    assert rate_for_period(bond, rows, 1) == Decimal("0.05")
    assert rate_for_period(bond, rows, 2) == Decimal("0.02")
    assert accrued_interest(bond, rows, date(2027, 9, 1)) == Decimal("5.00")
    assert accrued_interest(bond, rows, date(2027, 11, 1)) == Decimal("5.35")
    assert redemption_value(bond, rows, date(2027, 11, 1)) == Decimal("102.35")


def test_year_one_falls_back_to_cpi_plus_margin():
    rows = _cpi_rows({date(2026, 8, 31): "3.00", date(2027, 8, 31): "0.00"})
    bond = _bond(margin=Decimal("1.50"))
    assert rate_for_period(bond, rows, 1) == Decimal("0.045")
    assert accrued_interest(bond, rows, date(2026, 10, 16)) == Decimal("0.55")


def test_missing_cpi_raises_bond_rate_error():
    bond = _bond()  # 120 months; period 3 starts 2028-09-01
    rows = _cpi_rows({date(2026, 8, 31): "3.00"})
    with pytest.raises(BondRateError):
        redemption_value(bond, rows, date(2028, 9, 15))
    with pytest.raises(BondRateError):
        price_series(bond, rows, date(2028, 9, 15), date(2028, 9, 15))


def test_nbp_linked_series_are_not_priceable_yet():
    bond = _bond(
        series_code="ROR",
        rate_rule="nbp_ref+margin",
        margin=Decimal("0.00"),
        fee_b=Decimal("0.50"),
        maturity_date=date(2027, 9, 1),
        term_months=12,
    )
    with pytest.raises(ValueError):
        rate_for_period(bond, [], 1)
    with pytest.raises(ValueError):
        price_series(bond, [], date(2026, 9, 1), date(2026, 9, 2))


# ---------------------------------------------------------------------------
# price_series shape / clamping
# ---------------------------------------------------------------------------


def test_price_series_ohlcv_shape():
    bond = _edo0524()
    rows = _cpi_rows({date(2015, 4, 30): "1.00"})
    series = price_series(bond, rows, date(2015, 6, 15), date(2015, 6, 17))
    assert len(series) == 3
    first, second = series[0], series[1]
    assert first["date"] == "2015-06-15"
    assert first["open"] == first["close"] == 102.15
    assert second["open"] == 102.15
    assert second["close"] == 102.16
    assert second["high"] == 102.16
    assert second["low"] == 102.15
    assert second["volume"] == 0
    for row in series:
        assert set(row) == {"date", "open", "high", "low", "close", "volume"}


def test_price_series_clamps_to_term_and_returns_empty_outside():
    bond = _ots0118()
    assert price_series(bond, [], date(2017, 1, 1), date(2017, 10, 9)) == []
    assert price_series(bond, [], date(2018, 1, 11), date(2020, 1, 1)) == []
    term = price_series(bond, [], date(2017, 10, 10), date(2018, 1, 10))
    assert len(term) == 93
    assert term[0]["close"] == term[-2]["close"] == 100.0
    assert term[-1]["close"] == 100.38