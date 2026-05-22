from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()

from openbb import obb  # noqa: E402


def get_dividend_yield(ticker: str) -> str | None:
    for provider in ["yfinance", "fmp"]:
        try:
            df = obb.equity.fundamental.metrics(ticker, provider=provider).to_df()
            if df.empty:
                continue
            raw = df.iloc[0]["dividend_yield"]
            return str(Decimal(str(raw)).quantize(Decimal("0.01")))
        except Exception:
            continue
    return None


def get_dividend_history(ticker: str) -> list[dict] | None:
    for provider in ["yfinance", "fmp"]:
        try:
            df = obb.equity.fundamental.dividends(ticker, provider=provider).to_df()
            if df.empty:
                continue
            rows = []
            for idx, row in df.iterrows():
                date = idx.date() if hasattr(idx, "date") else idx
                amount = str(Decimal(str(row["amount"])).quantize(Decimal("0.0001")))
                rows.append({"date": str(date), "amount": amount})
            return rows
        except Exception:
            continue
    return None
