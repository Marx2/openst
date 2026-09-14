"""BiznesRadar.pl OpenBB provider extension — Polish TFI funds and Catalyst bonds."""

from openbb_core.provider.abstract.provider import Provider

from openbb_biznesradar.models.equity_historical import EquityHistoricalFetcher
from openbb_biznesradar.models.equity_profile import EquityProfileFetcher
from openbb_biznesradar.models.equity_quote import EquityQuoteFetcher
from openbb_biznesradar.models.equity_search import EquitySearchFetcher

biznesradar_provider = Provider(
    name="biznesradar",
    description="BiznesRadar.pl scraper — Polish TFI funds and Catalyst bonds",
    fetcher_dict={
        "EquityHistorical": EquityHistoricalFetcher,
        "EquityInfo": EquityProfileFetcher,
        "EquityQuote": EquityQuoteFetcher,
        "EquitySearch": EquitySearchFetcher,
    },
)

__all__ = ["biznesradar_provider"]