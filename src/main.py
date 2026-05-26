import base64
import json
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from .cache import RedisCache
from .openbb_client import get_dividend_history, get_dividend_yield

app = FastAPI()

_FAVICON = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAbklEQVR4nI2SwQ3AIAwD"
    "eTNO58yI7EJbggxKnEDkRwU+W0BLYdPbr9tR95nR7WmVoZxZwbIpYoy1PfVTxsCtVghM"
    "GG+AyZiSxE1KEE/dpCSPJyXH+L2EAP5aORCaxjc79/0t+Wcm8o/NfyRZ65gXP1AKlpa+"
    "AnUAAAAASUVORK5CYII="
)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(_FAVICON, media_type="image/png")

_cache = RedisCache(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    password=os.environ.get("REDIS_PASSWORD") or None,
    db=int(os.environ.get("REDIS_DB", 0)),
)


@app.get("/dividend/yield/{ticker}")
def dividend_yield(ticker: str):
    key = f"dividend_yield:{ticker}"
    cached = _cache.get(key)
    if cached is not None:
        return json.loads(cached)

    value = get_dividend_yield(ticker)
    if value is None:
        raise HTTPException(status_code=404, detail=f"No dividend yield data for {ticker}")

    _cache.set(key, json.dumps(value))
    return value


@app.get("/dividend/history/{ticker}")
def dividend_history(ticker: str):
    key = f"dividend_history:{ticker}"
    cached = _cache.get(key)
    if cached is not None:
        return json.loads(cached)

    value = get_dividend_history(ticker)
    if value is None:
        raise HTTPException(status_code=404, detail=f"No dividend history data for {ticker}")

    _cache.set(key, json.dumps(value))
    return value
