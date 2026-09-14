"""BiznesRadar EquityHistorical fetcher — dispatches TFI/FIZ funds vs Catalyst bonds (D77 16.4).

One fetcher is registered under OpenBB's ``EquityHistorical`` model key.  It
routes by symbol shape: symbols ending in ``.TFI`` / ``.FIZ`` are open-end funds
(2-column Data|Kurs scraper), everything else (``BST*``, ``INS*``, ``KRI*``
Catalyst bonds) uses the 7-column OHLCV scraper.  Both paths map to the same
standard ``EquityHistoricalData`` model.
"""

from __future__ import annotations

import os
from datetime import date

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_historical import (
    EquityHistoricalData,
    EquityHistoricalQueryParams,
)

from openbb_biznesradar.models.bond_historical import BOND_COLUMNS, parse_bond_row
from openbb_biznesradar.models.fund_historical import FUND_COLUMNS, parse_fund_row
from openbb_biznesradar.scraper import _scrape_pages, strip_wa_suffix

# Open-end fund symbols carry a venue suffix that identifies the 2-col table.
_FUND_SUFFIXES = (".tfi", ".fiz")

# Fallback bounds for the scraper when start/end are not given.
_MIN_DATE = date(1900, 1, 1)
_MAX_DATE = date(9999, 12, 31)

# Inter-page politeness delay (s); overridable in production through compose env.
_DEFAULT_FETCH_DELAY_S = 2.0


def _is_fund(symbol: str) -> bool:
    return symbol.lower().endswith(_FUND_SUFFIXES)


def _fetch_delay_s() -> float:
    return float(os.getenv("BIZNESRADAR_FETCH_DELAY_S", str(_DEFAULT_FETCH_DELAY_S)))


class BiznesRadarEquityHistoricalQueryParams(EquityHistoricalQueryParams):
    """Equity historical query params for biznesradar."""


class BiznesRadarEquityHistoricalData(EquityHistoricalData):
    """Equity historical data for biznesradar."""


class EquityHistoricalFetcher(
    Fetcher[BiznesRadarEquityHistoricalQueryParams, list[BiznesRadarEquityHistoricalData]]
):
    """Fetch TFI/FIZ fund or Catalyst bond history for the ``EquityHistorical`` model."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> BiznesRadarEquityHistoricalQueryParams:
        """Build the query params."""
        return BiznesRadarEquityHistoricalQueryParams(
            symbol=params["symbol"],
            start_date=params.get("start_date") or params.get("startDate"),
            end_date=params.get("end_date") or params.get("endDate"),
        )

    @staticmethod
    def extract_data(
        query: BiznesRadarEquityHistoricalQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """Scrape biznesradar pages for the symbol, returning raw rows."""
        del credentials
        del kwargs  # router forwards router-level extras (preferences, timeframe,…)
        symbol = strip_wa_suffix(query.symbol)
        cols = FUND_COLUMNS if _is_fund(symbol) else BOND_COLUMNS
        return list(
            _scrape_pages(
                symbol,
                query.start_date or _MIN_DATE,
                query.end_date or _MAX_DATE,
                _fetch_delay_s(),
                cols,
            )
        )

    @staticmethod
    def transform_data(
        query: BiznesRadarEquityHistoricalQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[BiznesRadarEquityHistoricalData]:
        """Normalize scraped rows to the standard OHLCV shape."""
        del kwargs
        mapper = (
            parse_fund_row
            if _is_fund(strip_wa_suffix(query.symbol))
            else parse_bond_row
        )
        return [BiznesRadarEquityHistoricalData(**mapper(row)) for row in data]