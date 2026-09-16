"""Obligacje EquityHistorical fetcher — priced redemption history (D79 19.6).

OpenBB 4.7.x ships no fixed-income price router or ``FixedIncomeHistorical``
standard model, so the obligacje fetchers are registered under the *equity*
model keys (``EquityHistorical`` / ``EquitySearch`` / ``EquityInfo``) — the same
decision the biznesradar plugin made for Catalyst bonds. This fetcher prices one
savings-bond emission on demand: ``openst.bond_series`` + ``openst.cpi_12m`` are
read from Postgres via :mod:`openbb_obligacje.store` and fed to
:func:`openbb_obligacje.engine.price_series`.
"""

from __future__ import annotations

from datetime import date

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_historical import (
    EquityHistoricalData,
    EquityHistoricalQueryParams,
)

from openbb_obligacje import store
from openbb_obligacje.engine import price_series

# CPI-linked series need a recent 12-month CPI observation; the daily importers
# keep ``openst.cpi_12m`` fresh, so anything older than 40 days is stale.
_STALE_CPI_DAYS = 40


class CpiStaleError(RuntimeError):
    """Raised when the CPI history is too old to price a CPI-linked emission."""


class ObligacjeEquityHistoricalQueryParams(EquityHistoricalQueryParams):
    """Pricing-history query for one savings-bond emission."""


class ObligacjeEquityHistoricalData(EquityHistoricalData):
    """One daily OHLCV row valuing a savings bond (``close`` = gross redemption value)."""


class FixedIncomeHistoricalFetcher(
    Fetcher[
        ObligacjeEquityHistoricalQueryParams,
        list[ObligacjeEquityHistoricalData],
    ]
):
    """Fetch the priced daily redemption history of a savings bond."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> ObligacjeEquityHistoricalQueryParams:
        """Build the query params."""
        return ObligacjeEquityHistoricalQueryParams(
            symbol=params["symbol"],
            start_date=params.get("start_date") or params.get("startDate"),
            end_date=params.get("end_date") or params.get("endDate"),
        )

    @staticmethod
    def extract_data(
        query: ObligacjeEquityHistoricalQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """Price the series from ``bond_series`` + ``cpi_12m`` (DB-backed).

        ``[]`` when the symbol is unknown; a :class:`CpiStaleError` when the CPI
        history is too old to price a CPI-linked emission.
        """
        del credentials
        del kwargs  # router forwards router-level extras (preferences, …)
        conn = store.get_conn()
        try:
            bond = store.fetch_bond_series(query.symbol, conn)
            if bond is None:
                return []
            cpi_rows = store.fetch_cpi_rows(conn)
            if bond.rate_rule == "cpi_12m+margin":
                latest = store.latest_cpi_date(conn)
                if latest is None:
                    raise CpiStaleError(
                        f"{bond.symbol}: openst.cpi_12m is empty — run the CPI "
                        "importer (src.importers.cpi) first"
                    )
                age_days = (date.today() - latest).days
                if age_days > _STALE_CPI_DAYS:
                    raise CpiStaleError(
                        f"{bond.symbol}: openst.cpi_12m is stale — latest row is "
                        f"{latest} ({age_days} days old, max {_STALE_CPI_DAYS}); "
                        "run the CPI importer (src.importers.cpi --mode incremental)"
                    )
            start = query.start_date or bond.issue_date
            end = query.end_date or bond.maturity_date
            return price_series(bond, cpi_rows, start, end)
        finally:
            conn.close()

    @staticmethod
    def transform_data(
        query: ObligacjeEquityHistoricalQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[ObligacjeEquityHistoricalData]:
        """Map ``engine.price_series`` rows to the standard OHLCV shape."""
        del kwargs
        return [ObligacjeEquityHistoricalData(**row) for row in data]