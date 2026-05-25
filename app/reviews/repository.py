import hashlib
import time
import uuid
from datetime import UTC, datetime
from typing import Protocol

import redis
from cassandra import ConsistencyLevel
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile

from app.reviews.models import ReviewCounters, ReviewItem


class ReviewRepository(Protocol):
    def ensure_schema(self) -> None: ...

    def create_review(
        self,
        event_id: str,
        user_id: str,
        rating: int,
        comment: str,
    ) -> str | None: ...

    def list_reviews(
        self,
        event_id: str,
        limit: int | None,
        offset: int | None,
    ) -> list[ReviewItem]: ...

    def update_review(
        self,
        event_id: str,
        review_id: str,
        user_id: str,
        rating: int | None,
        comment: str | None,
    ) -> bool: ...

    def update_reviews_cache(
        self,
        title: str,
        event_ids: list[str],
    ) -> None: ...

    def get_reviews_for_title(
        self,
        title: str,
        event_ids: list[str],
    ) -> ReviewCounters: ...


class CassandraReviewRepository:
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
                f"CREATE TABLE IF NOT EXISTS {self._keyspace}.event_reviews ("
                "event_id text, "
                "created_by text, "
                "id uuid, "
                "rating tinyint, "
                "comment text, "
                "created_at timestamp, "
                "updated_at timestamp, "
                "PRIMARY KEY ((event_id), created_by)"
                ")"
            ),
            (
                f"CREATE TABLE IF NOT EXISTS {self._keyspace}.event_reviews_by_id ("
                "id uuid, "
                "event_id text, "
                "created_by text, "
                "PRIMARY KEY (id)"
                ")"
            ),
        ]
        for statement in statements:
            self._execute_with_retry(statement)

    def create_review(
        self,
        event_id: str,
        user_id: str,
        rating: int,
        comment: str,
    ) -> str | None:
        existing = self._execute_with_retry(
            f"SELECT id FROM {self._keyspace}.event_reviews "
            "WHERE event_id = %s AND created_by = %s",
            (event_id, user_id),
        )
        if existing and list(existing):
            return None

        review_id = uuid.uuid4()
        now = datetime.now(UTC)

        self._execute_with_retry(
            f"INSERT INTO {self._keyspace}.event_reviews "
            "(event_id, created_by, id, rating, comment, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (event_id, user_id, review_id, rating, comment, now, now),
        )
        self._execute_with_retry(
            f"INSERT INTO {self._keyspace}.event_reviews_by_id "
            "(id, event_id, created_by) VALUES (%s, %s, %s)",
            (review_id, event_id, user_id),
        )
        return str(review_id)

    def list_reviews(
        self,
        event_id: str,
        limit: int | None,
        offset: int | None,
    ) -> list[ReviewItem]:
        rows = self._execute_with_retry(
            f"SELECT id, event_id, rating, comment, created_at, created_by, updated_at "
            f"FROM {self._keyspace}.event_reviews WHERE event_id = %s",
            (event_id,),
        )
        reviews: list[ReviewItem] = []
        for row in rows:
            reviews.append(
                ReviewItem(
                    id=str(row.id),
                    event_id=str(row.event_id),
                    comment=str(row.comment),
                    rating=int(row.rating),
                    created_at=row.created_at.replace(tzinfo=UTC).astimezone()
                    .isoformat(timespec="seconds"),
                    created_by=str(row.created_by),
                    updated_at=row.updated_at.replace(tzinfo=UTC).astimezone()
                    .isoformat(timespec="seconds"),
                )
            )

        if offset:
            reviews = reviews[offset:]
        if limit is not None:
            reviews = reviews[:limit]

        return reviews

    def update_review(
        self,
        event_id: str,
        review_id: str,
        user_id: str,
        rating: int | None,
        comment: str | None,
    ) -> bool:
        try:
            review_uuid = uuid.UUID(review_id)
        except ValueError:
            return False

        rows = self._execute_with_retry(
            f"SELECT event_id, created_by FROM {self._keyspace}.event_reviews_by_id "
            "WHERE id = %s",
            (review_uuid,),
        )
        row_list = list(rows)
        if not row_list:
            return False

        row = row_list[0]
        if str(row.event_id) != event_id:
            return False
        if str(row.created_by) != user_id:
            return False

        set_parts = ["updated_at = %s"]
        values: list[object] = [datetime.now(UTC)]

        if rating is not None:
            set_parts.append("rating = %s")
            values.append(rating)
        if comment is not None:
            set_parts.append("comment = %s")
            values.append(comment)

        values.extend([event_id, user_id])

        self._execute_with_retry(
            f"UPDATE {self._keyspace}.event_reviews "
            f"SET {', '.join(set_parts)} "
            "WHERE event_id = %s AND created_by = %s",
            tuple(values),
        )
        return True

    def update_reviews_cache(self, title: str, event_ids: list[str]) -> None:
        total_count = 0
        total_rating = 0.0

        for eid in event_ids:
            rows = self._execute_with_retry(
                f"SELECT rating FROM {self._keyspace}.event_reviews WHERE event_id = %s",
                (eid,),
            )
            for row in rows:
                total_count += 1
                total_rating += int(row.rating)

        avg_rating = round(total_rating / total_count, 1) if total_count > 0 else 0.0

        key = self._cache_key(title)
        pipe = self._redis.pipeline()
        pipe.delete(key)
        pipe.hset(key, mapping={"count": total_count, "rating": avg_rating})
        pipe.expire(key, self._cache_ttl)
        pipe.execute()

    def get_reviews_for_title(
        self,
        title: str,
        event_ids: list[str],
    ) -> ReviewCounters:
        cached = self._redis.hgetall(self._cache_key(title))
        if cached:
            return ReviewCounters(
                count=int(cached.get("count", 0)),
                rating=float(cached.get("rating", 0.0)),
            )

        total_count = 0
        total_rating = 0.0

        for eid in event_ids:
            rows = self._execute_with_retry(
                f"SELECT rating FROM {self._keyspace}.event_reviews WHERE event_id = %s",
                (eid,),
            )
            for row in rows:
                total_count += 1
                total_rating += int(row.rating)

        avg_rating = round(total_rating / total_count, 1) if total_count > 0 else 0.0

        if total_count > 0:
            key = self._cache_key(title)
            pipe = self._redis.pipeline()
            pipe.delete(key)
            pipe.hset(key, mapping={"count": total_count, "rating": avg_rating})
            pipe.expire(key, self._cache_ttl)
            pipe.execute()

        return ReviewCounters(count=total_count, rating=avg_rating)

    def _cache_key(self, title: str) -> str:
        title_hash = hashlib.md5(title.encode("utf-8")).hexdigest()
        return f"event:{title_hash}:reviews"

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
