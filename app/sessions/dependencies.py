from functools import lru_cache

from app.sessions.store import RedisSessionStore
from app.settings import get_settings


@lru_cache
def get_session_store() -> RedisSessionStore:
    settings = get_settings()
    return RedisSessionStore(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        db=settings.redis_db,
    )
