from typing import Protocol
from urllib.parse import quote_plus

from app.users.models import UserItem, UserRecord


class UserRepository(Protocol):
    def create_user(
        self,
        full_name: str,
        username: str,
        password_hash: str,
    ) -> str | None:
        pass

    def find_by_username(self, username: str) -> UserRecord | None:
        pass

    def list_users(
        self,
        name: str | None,
        user_id: str | None,
        limit: int | None,
        offset: int | None,
    ) -> list[UserItem]:
        pass

    def get_user_by_id(self, user_id: str) -> UserItem | None:
        pass


class MongoUserRepository:
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
        self.collection = client[database]["users"]
        self.collection.create_index([("username", ASCENDING)], unique=True)

    def create_user(
        self,
        full_name: str,
        username: str,
        password_hash: str,
    ) -> str | None:
        try:
            result = self.collection.insert_one(
                {
                    "full_name": full_name,
                    "username": username,
                    "password_hash": password_hash,
                }
            )
        except Exception as exc:
            if exc.__class__.__name__ == "DuplicateKeyError":
                return None
            raise

        return str(result.inserted_id)

    def find_by_username(self, username: str) -> UserRecord | None:
        document = self.collection.find_one({"username": username})
        if document is None:
            return None

        return UserRecord(
            id=str(document["_id"]),
            full_name=document["full_name"],
            username=document["username"],
            password_hash=document["password_hash"],
        )

    def list_users(
        self,
        name: str | None,
        user_id: str | None,
        limit: int | None,
        offset: int | None,
    ) -> list[UserItem]:
        query: dict[str, object] = {}
        if user_id:
            query["_id"] = self._normalize_id(user_id)
        if name:
            query["full_name"] = {"$regex": name, "$options": "i"}

        cursor = self.collection.find(query, {"password_hash": 0})
        if offset is not None:
            cursor = cursor.skip(offset)
        if limit is not None:
            cursor = cursor.limit(limit)

        return [
            UserItem(
                id=str(document["_id"]),
                full_name=document["full_name"],
                username=document["username"],
            )
            for document in cursor
        ]

    def get_user_by_id(self, user_id: str) -> UserItem | None:
        document = self.collection.find_one(
            {"_id": self._normalize_id(user_id)},
            {"password_hash": 0},
        )
        if document is None:
            return None

        return UserItem(
            id=str(document["_id"]),
            full_name=document["full_name"],
            username=document["username"],
        )

    def _normalize_id(self, value: str) -> object:
        if self.object_id_type.is_valid(value):
            return self.object_id_type(value)
        return value
