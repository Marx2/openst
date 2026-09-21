"""BiznesRadar EquityProfile (EquityInfo) fetcher — minimal profile (D78 17.4).

Returns ``{symbol, name, hq_country: "PL", currency: "PLN"}`` when the
biznesradar ``/notowania/{symbol}`` page resolves, or an empty list when it
does not (allowing fallback to the next provider in PROFILE_PROVIDERS).

Note: OpenBB registers profile under the ``EquityInfo`` model key (the router
uses ``EquityInfoQueryParams`` / ``EquityInfoData``).  ``EquityInfoData`` has no
``currency`` field so that is omitted; ``hq_country`` is used as the PL marker.

D80 25.2: ``fetch_data`` (the entry point the OpenBB router calls — there is
no ``__call__`` on ``Fetcher``) dispatches Catalyst corporate-bond symbols to
:class:`~openbb_biznesradar.models.corp_bond_profile.CorporateBondProfileFetcher`
(obligacje.pl) before trying biznesradar.
"""

from __future__ import annotations

from typing import Optional

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_info import (
    EquityInfoData,
    EquityInfoQueryParams,
)

from openbb_biznesradar import obligacje
from openbb_biznesradar.models.corp_bond_profile import CorporateBondProfileFetcher
from openbb_biznesradar.scraper import probe_notowania_full


class BiznesRadarEquityProfileQueryParams(EquityInfoQueryParams):
    """Equity profile query params for biznesradar."""


class BiznesRadarEquityProfileData(EquityInfoData):
    """Equity profile data for biznesradar.

    ``currency`` is a provider-specific extra (``EquityInfoData`` has no such
    field; ``extra="allow"`` keeps it through transform, mirroring
    ``CorporateBondProfileData.currency``).
    """

    currency: Optional[str] = None


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
        name, currency = probe_notowania_full(query.symbol)
        if not name:
            return []
        row = {
            "symbol": query.symbol,
            "name": name,
            "hq_country": "PL",
            "stock_exchange": "GPW",
        }
        if currency is not None:
            row["currency"] = currency
        return [row]

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

    @classmethod
    async def fetch_data(cls, params, credentials=None, **kwargs):
        r"""Dispatch Catalyst corporate-bond symbols to obligacje.pl (D80 25.2).

        ``[A-Z]{3}\d{4}(\.WA)?(-K)?`` codes (e.g. ``BST0327``) scrape
        ``obligacje.pl/pl/obligacja/{symbol}`` via
        :class:`CorporateBondProfileFetcher`.  The code shape alone is
        ambiguous — retail savings-bond codes (``ROD1033``, ``EDO0936``)
        match it too, but obligacje.pl only lists corporate bonds, so a 404
        there is expected: the dispatch *probes* the bond page and falls
        back to the biznesradar ``/notowania`` path when it resolves
        nothing.  Savings bonds never reach biznesradar (their profile
        lives on the ``/fixedincome/profile`` surface, D79), so the fallback
        only costs one extra 404 for genuinely unknown codes.
        """
        symbol = str(params.get("symbol", "")).strip()
        if obligacje.is_catalyst_bond_symbol(symbol):
            try:
                result = await CorporateBondProfileFetcher.fetch_data(
                    params=params, credentials=credentials, **kwargs
                )
            except Exception:
                result = []
            if result:
                return result
        return await super().fetch_data(
            params=params, credentials=credentials, **kwargs
        )
