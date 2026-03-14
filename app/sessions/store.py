from datetime import UTC, datetime

import redis
from redis.exceptions import WatchError

COOKIE_NAME = "X-Session-Id"
SESSION_KEY_PREFIX = "sid:"


class RedisSessionStore:
    def __init__(self, host: str, port: int, password: str, db: int) -> None:
        self.client = redis.Redis(
            host=host,
            port=port,
            password=password or None,
            db=db,
            decode_responses=True,
        )

    def _key(self, sid: str) -> str:
        return f"{SESSION_KEY_PREFIX}{sid}"

    def _now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def create_session(self, sid: str, ttl: int) -> bool:
        key = self._key(sid)
        now = self._now()

        with self.client.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(key)
                    if pipe.exists(key):
                        pipe.unwatch()
                        return False

                    pipe.multi()
                    pipe.hset(
                        key,
                        mapping={
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    pipe.expire(key, ttl)
                    pipe.execute()
                    return True
                except WatchError:
                    continue

    def session_exists(self, sid: str) -> bool:
        return bool(self.client.exists(self._key(sid)))

    def touch_session(self, sid: str, ttl: int) -> None:
        key = self._key(sid)

        now = self._now()

        pipe = self.client.pipeline()
        pipe.hset(key, "updated_at", now)
        pipe.expire(key, ttl)
        pipe.execute()
