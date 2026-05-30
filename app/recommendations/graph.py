import time
from typing import Protocol


class GraphRepository(Protocol):
    def add_user(self, user_id: str) -> None:
        pass

    def add_event(self, event_id: str, title: str) -> None:
        pass

    def add_like(self, user_id: str, event_id: str, title: str) -> None:
        pass

    def get_recommended_event_ids(self, user_id: str) -> list[str]:
        pass


class Neo4jGraphRepository:
    def __init__(self, url: str, username: str, password: str) -> None:
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise RuntimeError("neo4j dependency is required") from exc

        auth = (username, password) if username else None
        self._driver = GraphDatabase.driver(url, auth=auth)
        self._connect_with_retry()

    def _connect_with_retry(self) -> None:
        attempts = 30
        delay_seconds = 2
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                self._driver.verify_connectivity()
                return
            except Exception as exc:
                last_error = exc
                time.sleep(delay_seconds)
        if last_error is not None:
            raise last_error

    def add_user(self, user_id: str) -> None:
        with self._driver.session() as session:
            session.run(
                "MERGE (u:User {id: $user_id})",
                user_id=user_id,
            )

    def add_event(self, event_id: str, title: str) -> None:
        with self._driver.session() as session:
            session.run(
                "MERGE (e:Event {id: $event_id}) SET e.title = $title",
                event_id=event_id,
                title=title,
            )

    def add_like(self, user_id: str, event_id: str, title: str) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MERGE (u:User {id: $user_id})
                MERGE (e:Event {id: $event_id})
                SET e.title = $title
                MERGE (u)-[:LIKED]->(e)
                """,
                user_id=user_id,
                event_id=event_id,
                title=title,
            )

    def get_recommended_titles(
        self,
        user_id: str,
    ) -> list[tuple[str, list[str], int]]:
        """Return list of (title, event_ids, popularity) tuples.

        Algorithm:
          1. Collect events the user already liked (E1).
          2. Find other users who liked any event in E1.
          3. Collect events those other users liked (E2).
          4. Exclude E1 from E2 (per-event, not per-title).
          5. Group by title; popularity is the count of distinct other
             users who liked any candidate event with that title.
          6. Order by popularity desc, then title.
        """
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (me:User {id: $user_id})-[:LIKED]->(liked:Event)
                WITH collect(DISTINCT liked.id) AS likedIds
                MATCH (me:User {id: $user_id})-[:LIKED]->(le:Event)
                MATCH (other:User)-[:LIKED]->(le)
                WHERE other.id <> $user_id
                WITH likedIds, collect(DISTINCT other) AS others
                UNWIND others AS o
                MATCH (o)-[:LIKED]->(rec:Event)
                WHERE NOT rec.id IN likedIds
                WITH rec.title AS title,
                     collect(DISTINCT rec.id) AS event_ids,
                     count(DISTINCT o) AS likers
                RETURN title, event_ids, likers
                ORDER BY likers DESC, title ASC
                """,
                user_id=user_id,
            )
            grouped: list[tuple[str, list[str], int]] = []
            for record in result:
                grouped.append(
                    (
                        record["title"],
                        list(record["event_ids"]),
                        int(record["likers"]),
                    )
                )
            return grouped
