"""dividendmax.com OpenBB provider extension — dividend history from public pages.

Key-free scrape (plan §52.4): the public `GET /suggest.json?q=` endpoint
resolves a ticker to a per-company `/dividends` page, whose server-rendered
history table carries declaration/ex-dividend/payment dates and subunit
amounts. Only `Paid` rows are exposed (forecast amounts are sign-up gated).
"""

from openbb_core.provider.abstract.provider import Provider

from openbb_dividendmax.models.historical_dividends import HistoricalDividendsFetcher

dividendmax_provider = Provider(
    name="dividendmax",
    description="dividendmax.com scraper — UK/EU/US dividend history (public pages)",
    fetcher_dict={
        "HistoricalDividends": HistoricalDividendsFetcher,
    },
)

__all__ = ["dividendmax_provider"]
