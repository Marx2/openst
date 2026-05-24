import logging
from decimal import Decimal

from openbb import obb

PROVIDERS = ["yfinance", "fmp", "intrinio"]

logger = logging.getLogger(__name__)

# In-process cache: None = unknown, True/False = confirmed
_pays_dividend: dict[str, bool] = {}


def _check_pays_dividend(ticker: str) -> bool:
    """Return True if ticker has any dividend history across all providers."""
    if ticker in _pays_dividend:
        return _pays_dividend[ticker]
    any_success = False
    for provider in PROVIDERS:
        try:
            df = obb.equity.fundamental.dividends(ticker, provider=provider).to_df()
            any_success = True
            if not df.empty:
                _pays_dividend[ticker] = True
                return True
        except Exception:
            continue
    if any_success:
        _pays_dividend[ticker] = False
        return False
    return True  # all providers failed — can't confirm non-payer


def get_dividend_yield(ticker: str) -> float | None:
    got_data = False
    for provider in PROVIDERS:
        try:
            df = obb.equity.fundamental.metrics(ticker, provider=provider).to_df()
            got_data = True
            if df.empty:
                continue
            if "dividend_yield" not in df.columns:
                _pays_dividend[ticker] = False
                return 0.0
            raw = df.iloc[0]["dividend_yield"]
            return float(Decimal(str(raw)).quantize(Decimal("0.01")))
        except Exception as e:
            logger.warning("Provider %s failed for %s: %s", provider, ticker, e)
            continue
    if not got_data and not _check_pays_dividend(ticker):
        return 0.0
    return None


def get_dividend_history(ticker: str) -> list[dict] | None:
    if _pays_dividend.get(ticker) is False:
        return []
    any_success = False
    for provider in PROVIDERS:
        try:
            df = obb.equity.fundamental.dividends(ticker, provider=provider).to_df()
            any_success = True
            if df.empty:
                continue
            rows = []
            for idx, row in df.iterrows():
                date = idx.date() if hasattr(idx, "date") else idx
                amount = str(Decimal(str(row["amount"])).quantize(Decimal("0.0001")))
                rows.append({"date": str(date), "amount": amount})
            _pays_dividend[ticker] = True
            return rows
        except Exception as e:
            logger.warning("Provider %s failed for %s: %s", provider, ticker, e)
            continue
    if any_success:
        _pays_dividend[ticker] = False
    return []
