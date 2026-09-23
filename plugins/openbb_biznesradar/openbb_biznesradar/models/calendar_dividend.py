"""BiznesRadar CalendarDividend fetcher — GPW dividend calendar (plan §52.2).

Scrapes ``/dywidendy/,YYYY,4,2`` (payment-date-ordered dividend calendar for
the Warsaw Stock Exchange, no API key) and maps the rows onto the standard
OpenBB ``CalendarDividendData`` shape. Column mapping confirmed from the 52.1
fixtures:

  Profil                            → symbol    (ticker, pre-paren token)
  Ostatnie notowanie z prawem...    → ex_dividend_date
  Dzień wypłaty                     → payment_date
  Dywidenda na akcję                → amount    (PLN, comma-decimal)
  Status                            → (extra, non-standard: raw PL status)
  Stopa dywidendy*                  → Premium-gated, not scraped
  Data WZA                          → not exposed

Only the yield column is Premium-gated on the page; every other cell parses as
plain text. ``status`` is a provider-specific extra kept on the model so the
wallets layer can distinguish announced vs resolved payments.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.calendar_dividend import (
    CalendarDividendData,
    CalendarDividendQueryParams,
)

from openbb_biznesradar.scraper import scrape_dividend_calendar


class BiznesRadarCalendarDividendQueryParams(CalendarDividendQueryParams):
    """Calendar dividend query params for biznesradar."""


class BiznesRadarCalendarDividendData(CalendarDividendData):
    """Calendar dividend data for biznesradar.

    ``status`` is a provider-specific extra (the raw Polish status string:
    ``rekomendowana`` / ``uchwalona`` / ``wypłacona``) — the standard
    ``CalendarDividendData`` has no such field; ``extra="allow"`` keeps it
    through transform, mirroring ``EquityProfileData.currency``.
    """

    status: Optional[str] = None


class CalendarDividendFetcher(
    Fetcher[
        BiznesRadarCalendarDividendQueryParams,
        list[BiznesRadarCalendarDividendData],
    ]
):
    """Fetch the GPW dividend calendar from biznesradar /dywidendy/."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> BiznesRadarCalendarDividendQueryParams:
        """Build the query params."""
        return BiznesRadarCalendarDividendQueryParams(
            start_date=params.get("start_date") or params.get("startDate"),
            end_date=params.get("end_date") or params.get("endDate"),
        )

    @staticmethod
    def extract_data(
        query: BiznesRadarCalendarDividendQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """Scrape the /dywidendy/ pages for the requested window."""
        del credentials
        del kwargs  # router forwards router-level extras (preferences, …)
        start = query.start_date or date(date.today().year, 1, 1)
        end = query.end_date or start.replace(month=12, day=31)
        if end < start:
            return []
        return scrape_dividend_calendar(start, end)

    @staticmethod
    def transform_data(
        query: BiznesRadarCalendarDividendQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[BiznesRadarCalendarDividendData]:
        """Normalize scraped rows to CalendarDividendData."""
        del query
        del kwargs
        return [BiznesRadarCalendarDividendData(**row) for row in data]