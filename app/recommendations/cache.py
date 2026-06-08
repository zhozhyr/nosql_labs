import json
from typing import Protocol

import redis


class RecommendationsCache(Protocol):
    def get(self, user_id: str) -> list[dict[str, object]] | None:
        pass

    def set(self, user_id: str, events: list[dict[str, object]]) -> None:
        pass


class RedisRecommendationsCache:
    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        db: int,
        ttl: int,
    ) -> None:
        self._client = redis.Redis(
            host=host,
            port=port,
            password=password or None,
            db=db,
            decode_responses=True,
        )
        self._ttl = ttl

    def _key(self, user_id: str) -> str:
        return f"user:{user_id}:recomms"

    def get(self, user_id: str) -> list[dict[str, object]] | None:
        key = self._key(user_id)
        if not self._client.exists(key):
            return None
        raw = self._client.hget(key, "events")
        if raw is None:
            return []
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return []
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    def set(self, user_id: str, events: list[dict[str, object]]) -> None:
        key = self._key(user_id)
        payload = json.dumps(events, ensure_ascii=False)
        pipeline = self._client.pipeline()
        pipeline.delete(key)
        pipeline.hset(key, "events", payload)
        pipeline.expire(key, self._ttl)
        pipeline.execute()
