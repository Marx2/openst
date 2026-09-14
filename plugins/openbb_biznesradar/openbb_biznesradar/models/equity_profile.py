"""BiznesRadar EquityProfile (EquityInfo) fetcher — minimal profile (D78 17.4).

Returns ``{symbol, name, hq_country: "PL", currency: "PLN"}`` when the
biznesradar ``/notowania/{symbol}`` page resolves, or an empty list when it
does not (allowing fallback to the next provider in PROFILE_PROVIDERS).

Note: OpenBB registers profile under the ``EquityInfo`` model key (the router
uses ``EquityInfoQueryParams`` / ``EquityInfoData``).  ``EquityInfoData`` has no
``currency`` field so that is omitted; ``hq_country`` is used as the PL marker.
"""

from __future__ import annotations

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_info import (
    EquityInfoData,
    EquityInfoQueryParams,
)

from openbb_biznesradar.scraper import probe_notowania


class BiznesRadarEquityProfileQueryParams(EquityInfoQueryParams):
    """Equity profile query params for biznesradar."""


class BiznesRadarEquityProfileData(EquityInfoData):
    """Equity profile data for biznesradar."""


class EquityProfileFetcher(
    Fetcher[BiznesRadarEquityProfileQueryParams, list[BiznesRadarEquityProfileData]]
):
    """Fetch minimal equity profile by probing biznesradar /notowania/{symbol}."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> BiznesRadarEquityProfileQueryParams:
        """Build the query params."""
        return BiznesRadarEquityProfileQueryParams(symbol=params["symbol"])

    @staticmethod
    def extract_data(
        query: BiznesRadarEquityProfileQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """Return minimal profile when the symbol resolves on biznesradar."""
        del credentials
        del kwargs
        name = probe_notowania(query.symbol)
        if not name:
            return []
        return [
            {
                "symbol": query.symbol,
                "name": name,
                "hq_country": "PL",
                "stock_exchange": "GPW",
            }
        ]

    @staticmethod
    def transform_data(
        query: BiznesRadarEquityProfileQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[BiznesRadarEquityProfileData]:
        """Map raw profile dict to the standard EquityInfoData shape."""
        del query
        del kwargs
        return [BiznesRadarEquityProfileData(**row) for row in data]
