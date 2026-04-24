import hashlib
import time
from datetime import UTC, datetime
from typing import Protocol

import redis
from cassandra import ConsistencyLevel
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile

from app.reactions.models import ReactionCounters


class ReactionRepository(Protocol):
    def ensure_schema(self) -> None:
        pass

    def set_reaction(
        self,
        event_id: str,
        user_id: str,
        title: str,
        like_value: int,
    ) -> None:
        pass

    def get_reactions_for_title(
        self,
        title: str,
        event_ids: list[str],
    ) -> ReactionCounters:
        pass


class CassandraReactionRepository:
    def __init__(
        self,
        hosts: list[str],
        port: int,
        username: str,
        password: str,
        keyspace: str,
        consistency: str,
        redis_host: str,
        redis_port: int,
        redis_password: str,
        redis_db: int,
        cache_ttl: int,
    ) -> None:
        auth_provider = None
        if username:
            auth_provider = PlainTextAuthProvider(username=username, password=password)

        execution_profiles = None
        consistency_level = getattr(ConsistencyLevel, consistency.upper(), None)
        if consistency_level is not None:
            execution_profiles = {
                EXEC_PROFILE_DEFAULT: ExecutionProfile(
                    consistency_level=consistency_level
                )
            }

        self._cluster = Cluster(
            contact_points=hosts,
            port=port,
            auth_provider=auth_provider,
            execution_profiles=execution_profiles,
        )
        self._session = self._connect_with_retry()
        self._keyspace = keyspace
        self._redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password or None,
            db=redis_db,
            decode_responses=True,
        )
        self._cache_ttl = cache_ttl

    def ensure_schema(self) -> None:
        replication = "{'class': 'SimpleStrategy', 'replication_factor': 1}"
        statements = [
            (
                f"CREATE KEYSPACE IF NOT EXISTS {self._keyspace} "
                f"WITH replication = {replication}"
            ),
            (
                f"CREATE TABLE IF NOT EXISTS {self._keyspace}.event_reactions ("
                "event_id text, "
                "created_by text, "
                "like_value tinyint, "
                "created_at timestamp, "
                "PRIMARY KEY ((event_id), created_by)"
                ")"
            ),
            (
                f"CREATE INDEX IF NOT EXISTS event_reactions_like_value_idx "
                f"ON {self._keyspace}.event_reactions (like_value)"
            ),
        ]
        for statement in statements:
            self._execute_with_retry(statement)

    def set_reaction(
        self,
        event_id: str,
        user_id: str,
        title: str,
        like_value: int,
    ) -> None:
        statement = (
            f"INSERT INTO {self._keyspace}.event_reactions "
            "(event_id, created_by, like_value, created_at) "
            "VALUES (%s, %s, %s, %s)"
        )
        self._execute_with_retry(
            statement,
            (event_id, user_id, like_value, datetime.now(UTC)),
        )
        self._redis.delete(self._cache_key(title))

    def get_reactions_for_title(
        self,
        title: str,
        event_ids: list[str],
    ) -> ReactionCounters:
        cached = self._redis.hgetall(self._cache_key(title))
        if cached:
            return ReactionCounters(
                likes=int(cached.get("likes", 0)),
                dislikes=int(cached.get("dislikes", 0)),
            )

        counters = ReactionCounters()
        if not event_ids:
            return counters

        for event_id in event_ids:
            rows = self._execute_with_retry(
                (
                    f"SELECT like_value FROM {self._keyspace}.event_reactions "
                    "WHERE event_id = %s"
                ),
                (event_id,),
            )
            for row in rows:
                if int(row.like_value) > 0:
                    counters.likes += 1
                elif int(row.like_value) < 0:
                    counters.dislikes += 1

        if counters.likes > 0 or counters.dislikes > 0:
            pipeline = self._redis.pipeline()
            pipeline.delete(self._cache_key(title))
            pipeline.hset(
                self._cache_key(title),
                mapping={
                    "likes": counters.likes,
                    "dislikes": counters.dislikes,
                },
            )
            pipeline.expire(self._cache_key(title), self._cache_ttl)
            pipeline.execute()
        return counters

    def _cache_key(self, title: str) -> str:
        title_hash = hashlib.md5(title.encode("utf-8")).hexdigest()
        return f"event:{title_hash}:reactions"

    def _execute_with_retry(
        self,
        statement: str,
        parameters: tuple[object, ...] | None = None,
    ):
        attempts = 30
        delay_seconds = 2
        last_error: Exception | None = None

        for _ in range(attempts):
            try:
                return self._session.execute(statement, parameters)
            except Exception as exc:
                last_error = exc
                time.sleep(delay_seconds)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Cassandra query failed")

    def _connect_with_retry(self):
        attempts = 30
        delay_seconds = 2
        last_error: Exception | None = None

        for _ in range(attempts):
            try:
                return self._cluster.connect()
            except Exception as exc:
                last_error = exc
                time.sleep(delay_seconds)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Cassandra connection failed")
