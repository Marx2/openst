"""Obligacje FixedIncomeProfile fetcher — one emission's issue parameters (D79 19.5 stub).

Scaffold only; ``extract_data`` is stubbed until 19.6 loads
``openst.bond_series``. The shape mirrors the catalogue row so the fetcher
needs no translation later.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams


class ObligacjeFixedIncomeProfileQueryParams(QueryParams):
    """Profile query: one savings-bond symbol."""

    symbol: str


class ObligacjeFixedIncomeProfileData(Data):
    """Issue parameters of one savings-bond emission."""

    symbol: str
    name: str
    series_code: str
    issue_date: date
    maturity_date: date
    term_months: int
    rate_rule: str
    margin: Decimal
    fee_b: Decimal
    nominal: Decimal


class FixedIncomeProfileFetcher(
    Fetcher[ObligacjeFixedIncomeProfileQueryParams, ObligacjeFixedIncomeProfileData]
):
    """Fetch the issue parameters of one savings-bond emission (stub)."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> ObligacjeFixedIncomeProfileQueryParams:
        """Build the query params."""
        return ObligacjeFixedIncomeProfileQueryParams(symbol=params["symbol"])

    @staticmethod
    def extract_data(
        query: ObligacjeFixedIncomeProfileQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> dict:
        """Stub: the ``bond_series`` lookup is wired in step 19.6."""
        del credentials
        del kwargs
        return {}

    @staticmethod
    def transform_data(
        query: ObligacjeFixedIncomeProfileQueryParams,
        data: dict,
        **kwargs,
    ) -> ObligacjeFixedIncomeProfileData:
        """Map the raw row to the output model."""
        del kwargs
        return ObligacjeFixedIncomeProfileData(**data)