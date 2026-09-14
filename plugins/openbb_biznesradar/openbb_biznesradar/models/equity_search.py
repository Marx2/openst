"""BiznesRadar EquitySearch fetcher — symbol existence probe (D78 17.1).

biznesradar's public ``/szukaj`` results page does not index by symbol, so a
search can only resolve symbols that direct-probe successfully:
``GET /notowania/{symbol}`` with HTTP 200 plus a ``qTableFull`` quote table
yields a single hit (``{name, symbol, cik: None}``); anything else yields
an empty list.
"""

from __future__ import annotations

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_search import (
    EquitySearchData,
    EquitySearchQueryParams,
)

from openbb_biznesradar.scraper import probe_notowania


class BiznesRadarEquitySearchQueryParams(EquitySearchQueryParams):
    """Equity search query params for biznesradar."""


class BiznesRadarEquitySearchData(EquitySearchData):
    """Equity search data for biznesradar."""


class EquitySearchFetcher(
    Fetcher[BiznesRadarEquitySearchQueryParams, list[BiznesRadarEquitySearchData]]
):
    """Resolve a single symbol by probing its biznesradar ``/notowania`` page."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> BiznesRadarEquitySearchQueryParams:
        """Build the query params."""
        return BiznesRadarEquitySearchQueryParams(
            query=params.get("query") or params.get("q") or "",
            is_symbol=params.get("is_symbol", False),
        )

    @staticmethod
    def extract_data(
        query: BiznesRadarEquitySearchQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """Return a single search hit when the symbol probes successfully."""
        del credentials
        del kwargs  # router forwards router-level extras (preferences, …)
        symbol = query.query.strip().upper()
        if not symbol:
            return []
        name = probe_notowania(symbol)
        if not name:
            return []
        return [{"name": name, "symbol": symbol, "cik": None}]

    @staticmethod
    def transform_data(
        query: BiznesRadarEquitySearchQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[BiznesRadarEquitySearchData]:
        """Normalize probe hits to the standard search shape."""
        del query
        del kwargs
        return [BiznesRadarEquitySearchData(**row) for row in data]