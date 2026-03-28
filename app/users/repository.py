from typing import Protocol
from urllib.parse import quote_plus

from app.users.models import UserRecord


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
            from pymongo import ASCENDING, MongoClient
        except ImportError as exc:
            raise RuntimeError("pymongo dependency is required") from exc

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
