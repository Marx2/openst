"""Catalyst corporate-bond profile fetcher (D80, step 25.2).

Scrapes ``obligacje.pl/pl/obligacja/{symbol}`` for Catalyst corporate bonds
(``{3 letters}{4 digits}`` codes, e.g. ``BST0327``) and returns bond profile
metadata: issuer, ISIN, market, nominal, coupon type, current rate, maturity,
``asset_type="corp_bond"``, ``country="PL"``, ``currency="PLN"``.

Registered under ``EquityInfo``; the bond-specific fields ride along as
provider-specific extra fields, exactly like
``openbb_obligacje.ObligacjeEquityInfoData`` does for savings bonds.
``EquityProfileFetcher.__call__`` dispatches Catalyst symbols here and keeps
its existing biznesradar path for everything else, so a single provider
entry covers both surfaces.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_info import (
    EquityInfoData,
    EquityInfoQueryParams,
)

from openbb_biznesradar import obligacje


class CorporateBondProfileQueryParams(EquityInfoQueryParams):
    """Profile query: one Catalyst corporate-bond symbol."""


class CorporateBondProfileData(EquityInfoData):
    """Corporate-bond profile from obligacje.pl."""

    asset_type: Optional[str] = None
    issuer: Optional[str] = None
    series: Optional[str] = None
    market: Optional[str] = None
    status: Optional[str] = None
    nominal_value: Optional[Decimal] = None
    nominal_currency: Optional[str] = None
    secured: Optional[str] = None
    coupon_type: Optional[str] = None
    current_rate: Optional[str] = None
    margin: Optional[Decimal] = None
    maturity_date: Optional[date] = None
    country: Optional[str] = None
    currency: Optional[str] = None


class CorporateBondProfileFetcher(
    Fetcher[CorporateBondProfileQueryParams, list[CorporateBondProfileData]]
):
    """Fetch Catalyst corporate-bond profile metadata from obligacje.pl."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict) -> CorporateBondProfileQueryParams:
        """Build the query params."""
        return CorporateBondProfileQueryParams(symbol=params["symbol"])

    @staticmethod
    def extract_data(
        query: CorporateBondProfileQueryParams,
        credentials: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """Scrape the obligacje.pl detail page; ``[]`` when the bond is unknown."""
        del credentials
        del kwargs  # router forwards router-level extras (preferences, …)
        profile = obligacje.scrape_bond_profile(query.symbol)
        if profile is None:
            return []
        return [profile]

    @staticmethod
    def transform_data(
        query: CorporateBondProfileQueryParams,
        data: list[dict],
        **kwargs,
    ) -> list[CorporateBondProfileData]:
        """Map the raw profile dict to the standard EquityInfo shape."""
        del query
        del kwargs
        out = []
        for row in data:
            nominal_value = row.get("nominal_value")
            maturity = row.get("maturity")
            out.append(
                CorporateBondProfileData(
                    symbol=row["symbol"],
                    name=row.get("issuer"),
                    isin=row.get("isin"),
                    stock_exchange=row.get("market"),
                    hq_country=row.get("country", "PL"),
                    asset_type=row.get("asset_type"),
                    issuer=row.get("issuer"),
                    series=row.get("series"),
                    market=row.get("market"),
                    status=row.get("status"),
                    nominal_value=Decimal(str(nominal_value))
                    if nominal_value is not None
                    else None,
                    nominal_currency=row.get("nominal_currency"),
                    secured=row.get("secured"),
                    coupon_type=row.get("coupon_type"),
                    current_rate=row.get("current_rate"),
                    maturity_date=date.fromisoformat(maturity) if maturity else None,
                    country=row.get("country", "PL"),
                    currency=row.get("currency"),
                )
            )
        return out
