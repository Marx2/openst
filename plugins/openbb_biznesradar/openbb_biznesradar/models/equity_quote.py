"""BiznesRadar EquityQuote fetcher — current price from /notowania/{symbol} (D78 17.3).

Scrapes the live quote fields (last price, open/high/low, volume, change,
change_percent, prev_close, name) from the biznesradar instrument page.
Returns a single-element list; raises EmptyDataError when the page is
unavailable or the symbol does not resolve.
"""

from __future__ import annotations

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_quote import (
    EquityQuoteData,
    EquityQuoteQueryParams,
)

from openbb_biznesradar.scraper import scrape_quote


class BiznesRadarEquityQuoteQueryParams(EquityQuoteQueryParams):
    """Equity quote query params for biznesradar."""


class BiznesRadarEquityQuoteData(EquityQuoteData):
    """Equity quote data for biznesradar."""


class EquityQuoteFetcher(
    Fetcher[BiznesRadarEquityQuoteQueryParams, list[BiznesRadarEquityQuoteData]]
):
    """Fetch current price quote from biznesradar /notowania/{symbol}."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> BiznesRadarEquityQuoteQueryParams:
        """Build the query params."""
        return BiznesRadarEquityQuoteQueryParams(symbol=params["symbol"])

    @staticmethod
    def extract_data(
        query: BiznesRadarEquityQuoteQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """Scrape quote from biznesradar; return empty list when not found."""
        del credentials
        del kwargs
        row = scrape_quote(query.symbol)
        if row is None:
            return []
        return [row]

    @staticmethod
    def transform_data(
        query: BiznesRadarEquityQuoteQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[BiznesRadarEquityQuoteData]:
        """Map raw quote dict to the standard EquityQuoteData shape."""
        del query
        del kwargs
        return [BiznesRadarEquityQuoteData(**row) for row in data]
