from functools import lru_cache

from app.reviews.repository import CassandraReviewRepository, ReviewRepository
from app.settings import get_settings


@lru_cache
def get_review_repository() -> ReviewRepository:
    settings = get_settings()
    repository = CassandraReviewRepository(
        hosts=[
            item.strip()
            for item in settings.cassandra_hosts.split(",")
            if item.strip()
        ],
        port=settings.cassandra_port,
        username=settings.cassandra_username,
        password=settings.cassandra_password,
        keyspace=settings.cassandra_keyspace,
        consistency=settings.cassandra_consistency,
        redis_host=settings.redis_host,
        redis_port=settings.redis_port,
        redis_password=settings.redis_password,
        redis_db=settings.redis_db,
        cache_ttl=settings.app_event_reviews_ttl,
    )
    repository.ensure_schema()
    return repository
