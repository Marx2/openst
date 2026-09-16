"""Obligacje EquityInfo fetcher — one emission's issue parameters (D79 19.6).

Returns the ``openst.bond_series`` row for a known symbol as a
``list[ObligacjeEquityInfoData]`` (one element), or an empty list when the
symbol is unknown (the 404-equivalent — allows fallback to the next provider).
Registered under the ``EquityInfo`` model key like the biznesradar profile
fetcher; the emission fields ride along as provider-specific extra fields.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_info import (
    EquityInfoData,
    EquityInfoQueryParams,
)

from openbb_obligacje import store


class ObligacjeEquityInfoQueryParams(EquityInfoQueryParams):
    """Profile query: one savings-bond symbol."""


class ObligacjeEquityInfoData(EquityInfoData):
    """Issue parameters of one savings-bond emission."""

    series_code: Optional[str] = None
    issue_date: Optional[date] = None
    maturity_date: Optional[date] = None
    term_months: Optional[int] = None
    rate_rule: Optional[str] = None
    margin: Optional[Decimal] = None
    fee_b: Optional[Decimal] = None
    nominal: Optional[Decimal] = None


class FixedIncomeProfileFetcher(
    Fetcher[
        ObligacjeEquityInfoQueryParams,
        list[ObligacjeEquityInfoData],
    ]
):
    """Fetch the issue parameters of one savings-bond emission."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> ObligacjeEquityInfoQueryParams:
        """Build the query params."""
        return ObligacjeEquityInfoQueryParams(symbol=params["symbol"])

    @staticmethod
    def extract_data(
        query: ObligacjeEquityInfoQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """Return the catalogue row for the symbol; ``[]`` when unknown."""
        del credentials
        del kwargs  # router forwards router-level extras (preferences, …)
        bond = store.fetch_bond_series(query.symbol)
        if bond is None:
            return []
        return [
            {
                "symbol": bond.symbol,
                "name": bond.name,
                "series_code": bond.series_code,
                "issue_date": bond.issue_date,
                "maturity_date": bond.maturity_date,
                "term_months": bond.term_months,
                "rate_rule": bond.rate_rule,
                "margin": bond.margin,
                "fee_b": bond.fee_b,
                "nominal": bond.nominal,
            }
        ]

    @staticmethod
    def transform_data(
        query: ObligacjeEquityInfoQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[ObligacjeEquityInfoData]:
        """Map the raw row to the standard EquityInfo shape."""
        del query
        del kwargs
        return [ObligacjeEquityInfoData(**row) for row in data]