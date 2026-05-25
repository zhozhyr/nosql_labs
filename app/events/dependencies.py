from functools import lru_cache

from app.events.repository import EventRepository, MongoEventRepository
from app.settings import get_settings


@lru_cache
def get_event_repository() -> EventRepository:
    settings = get_settings()
    return MongoEventRepository(
        host=settings.mongodb_host,
        port=settings.mongodb_port,
        username=settings.mongodb_user,
        password=settings.mongodb_password,
        database=settings.mongodb_database,
    )
