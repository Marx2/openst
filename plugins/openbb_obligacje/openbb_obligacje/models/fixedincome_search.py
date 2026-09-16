"""Obligacje EquitySearch fetcher — emissions by symbol/name (D79 19.6).

Queries ``openst.bond_series`` by symbol prefix or name substring (see
:func:`openbb_obligacje.store.search_bond_series`). Output rows carry the
standard ``{symbol, name}`` pair plus ``maturity_date`` as a provider-specific
extra field, mirroring how the biznesradar plugin overloads the equity models.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_search import (
    EquitySearchData,
    EquitySearchQueryParams,
)

from openbb_obligacje import store


class ObligacjeEquitySearchQueryParams(EquitySearchQueryParams):
    """Search query over the savings-bond catalogue."""


class ObligacjeEquitySearchData(EquitySearchData):
    """One matching emission (``maturity_date`` is obligacje-specific)."""

    maturity_date: Optional[date] = None


class FixedIncomeSearchFetcher(
    Fetcher[
        ObligacjeEquitySearchQueryParams,
        list[ObligacjeEquitySearchData],
    ]
):
    """Find savings-bond emissions matching the free-text query."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> ObligacjeEquitySearchQueryParams:
        """Build the query params."""
        return ObligacjeEquitySearchQueryParams(
            query=params.get("query") or params.get("q") or params.get("symbol", ""),
            is_symbol=params.get("is_symbol", False),
        )

    @staticmethod
    def extract_data(
        query: ObligacjeEquitySearchQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """Return matching catalogue rows; ``[]`` for an empty query."""
        del credentials
        del kwargs  # router forwards router-level extras (preferences, …)
        term = query.query.strip().upper()
        if not term:
            return []
        matches = store.search_bond_series(term, query.is_symbol)
        return [
            {
                "symbol": bond.symbol,
                "name": bond.name,
                "maturity_date": bond.maturity_date,
            }
            for bond in matches
        ]

    @staticmethod
    def transform_data(
        query: ObligacjeEquitySearchQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[ObligacjeEquitySearchData]:
        """Map raw rows to the standard search shape."""
        del kwargs
        return [ObligacjeEquitySearchData(**row) for row in data]