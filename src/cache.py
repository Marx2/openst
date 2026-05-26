import redis


class RedisCache:
    def __init__(self, host: str, port: int, password: str | None, db: int):
        self._client = redis.Redis(
            host=host,
            port=port,
            password=password or None,
            db=db,
            decode_responses=True,
        )

    def get(self, key: str) -> str | None:
        return self._client.get(key)

    def set(self, key: str, value: str, ttl: int = 86400) -> None:
        self._client.setex(key, ttl, value)
