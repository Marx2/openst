"""BiznesRadar EquityHistorical fetcher — dispatch stub (D77 16.2 scaffold)."""

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_historical import (
    EquityHistoricalData,
    EquityHistoricalQueryParams,
)


class BiznesRadarEquityHistoricalQueryParams(EquityHistoricalQueryParams):
    """Equity historical query params for biznesradar."""


class BiznesRadarEquityHistoricalData(EquityHistoricalData):
    """Equity historical data for biznesradar."""


class EquityHistoricalFetcher(
    Fetcher[BiznesRadarEquityHistoricalQueryParams, list[BiznesRadarEquityHistoricalData]]
):
    """Fetch TFI/FIZ fund or Catalyst bond history, dispatching by symbol shape.

    Symbols ending in ``.TFI`` / ``.FIZ`` hit the 2-column fund scraper; anything
    else (``BST*``, ``INS*``, ``KRI*`` Catalyst bonds) hits the 7-column bond
    scraper.  Scraper and parsers are implemented in steps 16.3/16.4.
    """

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> BiznesRadarEquityHistoricalQueryParams:
        """Build the query params (implemented in 16.4)."""
        raise NotImplementedError

    @staticmethod
    async def aextract_data(
        query: BiznesRadarEquityHistoricalQueryParams,
        credentials: dict | None = None,
    ) -> list[dict]:
        """Scrape biznesradar pages for the symbol (implemented in 16.4)."""
        raise NotImplementedError

    @staticmethod
    def transform_data(
        query: BiznesRadarEquityHistoricalQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[BiznesRadarEquityHistoricalData]:
        """Normalize scraped rows to the standard shape (implemented in 16.4)."""
        raise NotImplementedError