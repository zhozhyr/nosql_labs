from functools import lru_cache

from app.recommendations.cache import RecommendationsCache, RedisRecommendationsCache
from app.recommendations.graph import GraphRepository, Neo4jGraphRepository
from app.settings import get_settings


@lru_cache
def get_graph_repository() -> GraphRepository:
    settings = get_settings()
    return Neo4jGraphRepository(
        url=settings.neo4j_url,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
    )


@lru_cache
def get_recommendations_cache() -> RecommendationsCache:
    settings = get_settings()
    return RedisRecommendationsCache(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        db=settings.redis_db,
        ttl=settings.app_recommendations_ttl,
    )


def initialize_recommendations_storage() -> None:
    get_graph_repository()
    get_recommendations_cache()
