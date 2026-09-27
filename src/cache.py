"""Redis access for openst.

Every read and write degrades to a miss/None instead of raising. A Redis outage
must not take the service down: the provider walks behind these endpoints are
slow and metered, so failing closed turns a cache problem into a total outage
*and* burns upstream quota on the retry storm that follows. The previous
implementation let ``ConnectionError`` escape, which returned HTTP 500 on every
data endpoint while ``/health`` still reported ok.
"""

import logging

import redis

logger = logging.getLogger("openst.cache")


class RedisCache:
    def __init__(self, host: str, port: int, password: str | None, db: int):
        self._client = redis.Redis(
            host=host,
            port=port,
            password=password or None,
            db=db,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

    def get(self, key: str) -> str | None:
        try:
            return self._client.get(key)
        except redis.RedisError as e:
            # Treated as a miss by every caller, so a request still succeeds — it just
            # re-fetches and pays the provider walk.
            logger.warning("cache GET %r failed, serving as miss: %s", key, e)
            return None

    def set(self, key: str, value: str, ttl: int = 86400) -> None:
        try:
            self._client.setex(key, ttl, value)
        except redis.RedisError as e:
            logger.warning("cache SET %r failed, value not stored: %s", key, e)

    def ping(self) -> bool:
        """True when Redis is reachable. Used by the readiness probe, not /health."""
        try:
            return bool(self._client.ping())
        except redis.RedisError as e:
            logger.warning("cache ping failed: %s", e)
            return False
