from typing import Protocol
from urllib.parse import quote_plus

from app.events.models import EventItem


class EventRepository(Protocol):
    def create_event(self, document: dict[str, str | dict[str, str]]) -> str | None:
        pass

    def list_events(
        self,
        filters: dict[str, object],
        limit: int | None,
        offset: int | None,
    ) -> list[EventItem]:
        pass

    def get_event_by_id(self, event_id: str) -> EventItem | None:
        pass

    def update_event(
        self,
        event_id: str,
        user_id: str,
        updates: dict[str, object],
        unset_fields: list[str],
    ) -> bool:
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
            from bson import ObjectId
            from pymongo import ASCENDING, MongoClient
        except ImportError as exc:
            raise RuntimeError("pymongo dependency is required") from exc

        self.object_id_type = ObjectId
        credentials = ""
        if username:
            credentials = f"{quote_plus(username)}:{quote_plus(password)}@"

        auth_source = "?authSource=admin" if username else ""
        uri = f"mongodb://{credentials}{host}:{port}/{auth_source}"
        client = MongoClient(uri)
        db = client[database]
        self.collection = db["events"]
        self.users_collection = db["users"]
        self.collection.create_index([("created_by", ASCENDING)])
        self.collection.create_index([("title", ASCENDING)])
        self.collection.create_index([("title", ASCENDING), ("created_by", ASCENDING)])
        self.collection.create_index([("category", ASCENDING)])
        self.collection.create_index([("price", ASCENDING)])
        self.collection.create_index([("location.city", ASCENDING)])

    def create_event(self, document: dict[str, str | dict[str, str]]) -> str | None:
        existing = self.collection.find_one(
            {"title": document.get("title"), "created_by": document.get("created_by")},
            {"_id": 1},
        )
        if existing is not None:
            return None
        try:
            result = self.collection.insert_one(document)
        except Exception as exc:
            if exc.__class__.__name__ == "DuplicateKeyError":
                return None
            raise

        return str(result.inserted_id)

    def list_events(
        self,
        filters: dict[str, object],
        limit: int | None,
        offset: int | None,
    ) -> list[EventItem]:
        query: dict[str, object] = {}
        title = filters.get("title")
        if isinstance(title, str) and title:
            query["title"] = {"$regex": title, "$options": "i"}
        event_id = filters.get("id")
        if isinstance(event_id, str) and event_id:
            query["_id"] = self._normalize_id(event_id)
        category = filters.get("category")
        if isinstance(category, str) and category:
            query["category"] = category
        city = filters.get("city")
        if isinstance(city, str) and city:
            query["location.city"] = city
        created_by = filters.get("created_by")
        if isinstance(created_by, str) and created_by:
            query["created_by"] = created_by
        price_range: dict[str, int] = {}
        price_from = filters.get("price_from")
        if isinstance(price_from, int):
            price_range["$gte"] = price_from
        price_to = filters.get("price_to")
        if isinstance(price_to, int):
            price_range["$lte"] = price_to
        if price_range:
            query["price"] = price_range

        username = filters.get("user")
        if isinstance(username, str) and username:
            user = self.users_collection.find_one({"username": username}, {"_id": 1})
            if user is None:
                return []
            query["created_by"] = str(user["_id"])

        cursor = self.collection.find(query)
        if offset is not None:
            cursor = cursor.skip(offset)
        if limit is not None:
            cursor = cursor.limit(limit)

        events: list[EventItem] = []
        for document in cursor:
            if not self._matches_date_filters(document, filters):
                continue
            events.append(
                self._document_to_item(document)
            )
        return events

    def get_event_by_id(self, event_id: str) -> EventItem | None:
        document = self.collection.find_one({"_id": self._normalize_id(event_id)})
        if document is None:
            return None
        return self._document_to_item(document)

    def update_event(
        self,
        event_id: str,
        user_id: str,
        updates: dict[str, object],
        unset_fields: list[str],
    ) -> bool:
        payload: dict[str, object] = {}
        if updates:
            payload["$set"] = updates
        if unset_fields:
            payload["$unset"] = {field: "" for field in unset_fields}
        if not payload:
            return self.collection.find_one(
                {"_id": self._normalize_id(event_id), "created_by": user_id}
            ) is not None

        result = self.collection.update_one(
            {"_id": self._normalize_id(event_id), "created_by": user_id},
            payload,
        )
        return result.matched_count > 0

    def _document_to_item(self, document: dict[str, object]) -> EventItem:
        return EventItem(
            id=str(document["_id"]),
            title=str(document["title"]),
            category=str(document["category"]) if document.get("category") else None,
            price=int(document["price"]) if document.get("price") is not None else None,
            description=str(document["description"]),
            location=document["location"],
            created_at=str(document["created_at"]),
            created_by=str(document["created_by"]),
            started_at=str(document["started_at"]),
            finished_at=str(document["finished_at"]),
        )

    def _normalize_id(self, value: str) -> object:
        if self.object_id_type.is_valid(value):
            return self.object_id_type(value)
        return value

    def _matches_date_filters(
        self,
        document: dict[str, object],
        filters: dict[str, object],
    ) -> bool:
        started_at = str(document["started_at"])
        date_from = filters.get("date_from")
        if isinstance(date_from, str) and started_at[:10] < date_from:
            return False
        date_to = filters.get("date_to")
        if isinstance(date_to, str) and started_at[:10] > date_to:
            return False
        return True
