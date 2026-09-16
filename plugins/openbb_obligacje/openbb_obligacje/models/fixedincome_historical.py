"""Obligacje FixedIncomeHistorical fetcher — priced redemption history (D79 19.5 stub).

OpenBB 4.7.2 ships no fixed-income price router or ``FixedIncomeHistorical``
standard model, so this fetcher derives its param/data classes from the
abstract ``QueryParams``/``Data`` bases. ``extract_data`` is a stub: step 19.6
plumbs the pricing engine to ``openst.bond_series`` + ``openst.cpi_12m``.
The engine and its worked-example tests are the source of truth for the math.
"""

from __future__ import annotations

from datetime import date

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams


class ObligacjeFixedIncomeHistoricalQueryParams(QueryParams):
    """Pricing-history query for one savings-bond emission."""

    symbol: str
    start_date: date | None = None
    end_date: date | None = None


class ObligacjeFixedIncomeHistoricalData(Data):
    """One daily OHLCV row valuing a savings bond (``close`` = gross redemption value)."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class FixedIncomeHistoricalFetcher(
    Fetcher[
        ObligacjeFixedIncomeHistoricalQueryParams,
        list[ObligacjeFixedIncomeHistoricalData],
    ]
):
    """Fetch the priced daily redemption history of a savings bond (stub)."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> ObligacjeFixedIncomeHistoricalQueryParams:
        """Build the query params."""
        return ObligacjeFixedIncomeHistoricalQueryParams(
            symbol=params["symbol"],
            start_date=params.get("start_date") or params.get("startDate"),
            end_date=params.get("end_date") or params.get("endDate"),
        )

    @staticmethod
    def extract_data(
        query: ObligacjeFixedIncomeHistoricalQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """Stub: the DB-backed fetch is wired in step 19.6."""
        del credentials
        del kwargs
        return []

    @staticmethod
    def transform_data(
        query: ObligacjeFixedIncomeHistoricalQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[ObligacjeFixedIncomeHistoricalData]:
        """Map ``openbb_obligacje.engine.price_series`` rows to the output model."""
        del kwargs
        return [ObligacjeFixedIncomeHistoricalData(**row) for row in data]