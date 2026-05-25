from typing import Protocol
from urllib.parse import quote_plus

from app.events.models import EventItem


class EventRepository(Protocol):
    def create_event(self, document: dict[str, str | dict[str, str]]) -> str | None:
        pass

    def list_events(
        self,
        title: str | None,
        limit: int | None,
        offset: int | None,
    ) -> list[EventItem]:
        pass


class MongoEventRepository:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
    ):
        try:
            from pymongo import ASCENDING, MongoClient
        except ImportError as exc:
            raise RuntimeError("pymongo dependency is required") from exc

        credentials = ""
        if username:
            credentials = f"{quote_plus(username)}:{quote_plus(password)}@"

        auth_source = "?authSource=admin" if username else ""
        uri = f"mongodb://{credentials}{host}:{port}/{auth_source}"
        client = MongoClient(uri)
        self.collection = client[database]["events"]
        self.collection.create_index([("title", ASCENDING)], unique=True)
        self.collection.create_index([("title", ASCENDING), ("created_by", ASCENDING)])
        self.collection.create_index([("created_by", ASCENDING)])

    def create_event(self, document: dict[str, str | dict[str, str]]) -> str | None:
        try:
            result = self.collection.insert_one(document)
        except Exception as exc:
            if exc.__class__.__name__ == "DuplicateKeyError":
                return None
            raise

        return str(result.inserted_id)

    def list_events(
        self,
        title: str | None,
        limit: int | None,
        offset: int | None,
    ) -> list[EventItem]:
        query: dict[str, object] = {}
        if title:
            query["title"] = {"$regex": title, "$options": "i"}

        cursor = self.collection.find(query)
        if offset is not None:
            cursor = cursor.skip(offset)
        if limit is not None:
            cursor = cursor.limit(limit)

        events: list[EventItem] = []
        for document in cursor:
            events.append(
                EventItem(
                    id=str(document["_id"]),
                    title=document["title"],
                    description=document["description"],
                    location=document["location"],
                    created_at=document["created_at"],
                    created_by=document["created_by"],
                    started_at=document["started_at"],
                    finished_at=document["finished_at"],
                )
            )
        return events
