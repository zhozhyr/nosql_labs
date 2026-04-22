from functools import lru_cache

from app.reactions.repository import CassandraReactionRepository, ReactionRepository
from app.settings import get_settings


@lru_cache
def get_reaction_repository() -> ReactionRepository:
    settings = get_settings()
    repository = CassandraReactionRepository(
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
        cache_ttl=settings.app_like_ttl,
    )
    repository.ensure_schema()
    return repository


def initialize_reactions_storage() -> None:
    get_reaction_repository()
