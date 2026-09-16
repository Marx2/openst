"""Obligacje FixedIncomeSearch fetcher — emissions by symbol/name (D79 19.5 stub).

Like :mod:`openbb_obligacje.models.fixedincome_historical` this is a scaffold:
``OpenBB`` has no fixed-income search standard model either, so the classes
derive from the abstract bases and ``extract_data`` is stubbed until 19.6
queries ``openst.bond_series``.
"""

from __future__ import annotations

from datetime import date

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams


class ObligacjeFixedIncomeSearchQueryParams(QueryParams):
    """Search query: a free-text term (name/series) or an exact symbol."""

    query: str
    is_symbol: bool = False


class ObligacjeFixedIncomeSearchData(Data):
    """One matching emission."""

    symbol: str
    name: str
    series_code: str
    maturity_date: date


class FixedIncomeSearchFetcher(
    Fetcher[
        ObligacjeFixedIncomeSearchQueryParams,
        list[ObligacjeFixedIncomeSearchData],
    ]
):
    """Find savings-bond emissions matching the query (stub)."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> ObligacjeFixedIncomeSearchQueryParams:
        """Build the query params."""
        return ObligacjeFixedIncomeSearchQueryParams(
            query=params.get("query", params.get("symbol", "")),
            is_symbol=bool(params.get("is_symbol", params.get("provider", ""))),
        )

    @staticmethod
    def extract_data(
        query: ObligacjeFixedIncomeSearchQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """Stub: the ``bond_series`` lookup is wired in step 19.6."""
        del credentials
        del kwargs
        return []

    @staticmethod
    def transform_data(
        query: ObligacjeFixedIncomeSearchQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[ObligacjeFixedIncomeSearchData]:
        """Map raw rows to the output model."""
        del kwargs
        return [ObligacjeFixedIncomeSearchData(**row) for row in data]