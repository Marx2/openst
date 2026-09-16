"""FixedIncomeSearch fetcher stub tests (D79 19.5)."""

from datetime import date

from openbb_obligacje import obligacje_provider
from openbb_obligacje.models.fixedincome_search import (
    FixedIncomeSearchFetcher,
    ObligacjeFixedIncomeSearchData,
)


def test_transform_query_defaults():
    q = FixedIncomeSearchFetcher.transform_query({"query": "EDO"})
    assert q.query == "EDO"
    assert q.is_symbol is False


def test_transform_query_symbol_alias():
    q = FixedIncomeSearchFetcher.transform_query({"symbol": "EDO0936"})
    assert q.query == "EDO0936"


def test_extract_data_stub_is_empty():
    q = FixedIncomeSearchFetcher.transform_query({"query": "EDO"})
    assert FixedIncomeSearchFetcher.extract_data(q) == []


def test_transform_data_round_trip():
    q = FixedIncomeSearchFetcher.transform_query({"query": "EDO"})
    rows = [
        {
            "symbol": "EDO0936",
            "name": "EDO0936",
            "series_code": "EDO",
            "maturity_date": "2036-09-01",
        }
    ]
    out = FixedIncomeSearchFetcher.transform_data(q, rows)
    assert isinstance(out[0], ObligacjeFixedIncomeSearchData)
    assert out[0].maturity_date == date(2036, 9, 1)


def test_registered_under_fixedincome_search():
    assert obligacje_provider.fetcher_dict["FixedIncomeSearch"] is FixedIncomeSearchFetcher