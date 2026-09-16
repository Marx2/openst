"""FixedIncomeProfile fetcher stub tests (D79 19.5)."""

from datetime import date
from decimal import Decimal

from openbb_obligacje import obligacje_provider
from openbb_obligacje.models.fixedincome_profile import (
    FixedIncomeProfileFetcher,
    ObligacjeFixedIncomeProfileData,
)


def test_transform_query():
    q = FixedIncomeProfileFetcher.transform_query({"symbol": "EDO0936"})
    assert q.symbol == "EDO0936"


def test_extract_data_stub_is_empty():
    q = FixedIncomeProfileFetcher.transform_query({"symbol": "EDO0936"})
    assert FixedIncomeProfileFetcher.extract_data(q) == {}


def test_transform_data_round_trip():
    q = FixedIncomeProfileFetcher.transform_query({"symbol": "EDO0936"})
    row = {
        "symbol": "EDO0936",
        "name": "EDO0936",
        "series_code": "EDO",
        "issue_date": "2026-09-01",
        "maturity_date": "2036-09-01",
        "term_months": 120,
        "rate_rule": "cpi_12m+margin",
        "margin": "2.00",
        "fee_b": "3.00",
        "nominal": "100.00",
    }
    out = FixedIncomeProfileFetcher.transform_data(q, row)
    assert isinstance(out, ObligacjeFixedIncomeProfileData)
    assert out.maturity_date == date(2036, 9, 1)
    assert out.margin == Decimal("2.00")
    assert out.fee_b == Decimal("3.00")


def test_registered_under_fixedincome_profile():
    assert obligacje_provider.fetcher_dict["FixedIncomeProfile"] is FixedIncomeProfileFetcher