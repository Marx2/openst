"""dividendmax HistoricalDividends fetcher — dividend history from public pages (plan §52.4).

Maps the dividendmax ``/dividends`` history table onto the standard OpenBB
``HistoricalDividendsData`` shape.  Column mapping confirmed from the 52.3
fixtures:

  Status          → (Paid rows only; kept as the extra ``status``)
  Type            → extra ``dividend_type`` (Quarterly/Final/Interim/Special)
  Decl. date      → declaration_date (en dash → None)
  Ex-div date     → ex_dividend_date (standard, required)
  Pay date        → payment_date (en dash → None)
  Decl. Currency  → extra ``currency`` (per-row: EUR/GBP/USD seen)
  Decl. amount    → amount (subunit notation, standard, required)
  Forecast amount → not scraped (sign-up gated)

The provider is registered on ``equity.fundamental.dividends`` only.  It is
deliberately NOT a calendar provider: ``CalendarDividendQueryParams`` carries
no symbol, and dividendmax has no public cross-company calendar (its
cross-company "Countdown" calendar is Premium).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.historical_dividends import (
    HistoricalDividendsData,
    HistoricalDividendsQueryParams,
)

from openbb_dividendmax.client import scrape_dividend_history


class DividendmaxHistoricalDividendsQueryParams(HistoricalDividendsQueryParams):
    """Dividend history query params for dividendmax."""


class DividendmaxHistoricalDividendsData(HistoricalDividendsData):
    """Dividend history data for dividendmax.

    The standard model only carries ``symbol`` / ``ex_dividend_date`` /
    ``amount``; the extras below are provider-specific and survive transform
    via ``extra="allow"`` (mirroring the biznesradar ``currency`` pattern).
    """

    payment_date: Optional[date] = None
    declaration_date: Optional[date] = None
    currency: Optional[str] = None
    dividend_type: Optional[str] = None
    status: Optional[str] = None


class HistoricalDividendsFetcher(
    Fetcher[
        DividendmaxHistoricalDividendsQueryParams,
        list[DividendmaxHistoricalDividendsData],
    ]
):
    """Fetch a company's dividend history from the dividendmax public pages."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> DividendmaxHistoricalDividendsQueryParams:
        """Build the query params."""
        return DividendmaxHistoricalDividendsQueryParams(
            symbol=params["symbol"],
            start_date=params.get("start_date") or params.get("startDate"),
            end_date=params.get("end_date") or params.get("endDate"),
        )

    @staticmethod
    def extract_data(
        query: DividendmaxHistoricalDividendsQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """Resolve the symbol and scrape its /dividends page."""
        del credentials
        del kwargs  # router forwards router-level extras (preferences, …)
        return scrape_dividend_history(query.symbol)

    @staticmethod
    def transform_data(
        query: DividendmaxHistoricalDividendsQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[DividendmaxHistoricalDividendsData]:
        """Normalize scraped rows to HistoricalDividendsData."""
        del query
        del kwargs
        return [DividendmaxHistoricalDividendsData(**row) for row in data]
