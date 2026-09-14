"""BiznesRadar.pl OpenBB provider extension — Polish TFI funds and Catalyst bonds."""

from openbb_core.provider.abstract.provider import Provider

from openbb_biznesradar.models.equity_historical import EquityHistoricalFetcher

biznesradar_provider = Provider(
    name="biznesradar",
    description="BiznesRadar.pl scraper — Polish TFI funds and Catalyst bonds",
    fetcher_dict={
        "EquityHistorical": EquityHistoricalFetcher,
    },
)

__all__ = ["biznesradar_provider"]