import os
from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.events.dependencies import get_event_repository
from app.events.models import EventItem
from app.main import app
from app.security import PasswordHasher
from app.sessions.dependencies import get_session_store
from app.settings import get_settings
from app.users.dependencies import get_password_hasher, get_user_repository
from app.users.models import UserRecord

# Храним конфигурацию тестов локально, чтобы тесты были изолированы
TEST_ENV = {
    "APP_HOST": "127.0.0.1",
    "APP_PORT": "8080",
    "APP_USER_SESSION_TTL": "60",
    "REDIS_HOST": "redis",
    "REDIS_PORT": "6379",
    "REDIS_PASSWORD": "",
    "REDIS_DB": "0",
    "MONGODB_DATABASE": "eventhub_test",
    "MONGODB_USER": "root",
    "MONGODB_PASSWORD": "root",
    "MONGODB_HOST": "mongodb",
    "MONGODB_PORT": "27017",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)


class FakeSessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, str | int]] = {}

    def create_session(self, session_id: str, ttl_seconds: int) -> bool:
        if session_id in self.sessions:
            return False

        self.sessions[session_id] = {
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "ttl": ttl_seconds,
        }
        return True

    def session_exists(self, session_id: str) -> bool:
        return session_id in self.sessions

    def touch_session(self, session_id: str, ttl_seconds: int) -> None:
        self.sessions[session_id]["updated_at"] = "2026-01-01T00:01:00Z"
        self.sessions[session_id]["ttl"] = ttl_seconds

    def get_session(self, session_id: str) -> dict[str, str | int] | None:
        return self.sessions.get(session_id)

    def set_session_user_id(
        self,
        session_id: str,
        user_id: str,
        ttl_seconds: int,
    ) -> None:
        self.sessions[session_id]["user_id"] = user_id
        self.touch_session(session_id, ttl_seconds)

    def delete_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, UserRecord] = {}
        self.counter = 1

    def create_user(
        self,
        full_name: str,
        username: str,
        password_hash: str,
    ) -> str | None:
        if username in self.users:
            return None

        user_id = f"user-{self.counter}"
        self.counter += 1
        self.users[username] = UserRecord(
            id=user_id,
            full_name=full_name,
            username=username,
            password_hash=password_hash,
        )
        return user_id

    def find_by_username(self, username: str) -> UserRecord | None:
        return self.users.get(username)


class FakePasswordHasher(PasswordHasher):
    def hash_password(self, password: str) -> str:
        return f"hashed::{password}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        return password_hash == self.hash_password(password)


class FakeEventRepository:
    def __init__(self) -> None:
        self.events: list[dict[str, str | dict[str, str]]] = []
        self.counter = 1

    def create_event(self, document: dict[str, str | dict[str, str]]) -> str | None:
        title = str(document["title"])
        if any(str(event["title"]) == title for event in self.events):
            return None

        event_id = f"event-{self.counter}"
        self.counter += 1
        stored = {"_id": event_id, **document}
        self.events.append(stored)
        return event_id

    def list_events(
        self,
        title: str | None,
        limit: int | None,
        offset: int | None,
    ) -> list[EventItem]:
        filtered = self.events
        if title:
            filtered = [
                event
                for event in filtered
                if title.lower() in str(event["title"]).lower()
            ]

        start = offset or 0
        end = None if limit is None else start + limit
        paginated = filtered[start:end]

        return [
            EventItem(
                id=str(event["_id"]),
                title=str(event["title"]),
                description=str(event["description"]),
                location=event["location"],
                created_at=str(event["created_at"]),
                created_by=str(event["created_by"]),
                started_at=str(event["started_at"]),
                finished_at=str(event["finished_at"]),
            )
            for event in paginated
        ]


@dataclass
class TestDependencies:
    store: FakeSessionStore
    user_repository: FakeUserRepository
    event_repository: FakeEventRepository
    password_hasher: FakePasswordHasher


def create_client() -> tuple[TestClient, TestDependencies]:
    get_settings.cache_clear()
    get_session_store.cache_clear()
    get_user_repository.cache_clear()
    get_event_repository.cache_clear()
    get_password_hasher.cache_clear()

    deps = TestDependencies(
        store=FakeSessionStore(),
        user_repository=FakeUserRepository(),
        event_repository=FakeEventRepository(),
        password_hasher=FakePasswordHasher(),
    )
    app.dependency_overrides = {}
    app.dependency_overrides[get_session_store] = lambda: deps.store
    app.dependency_overrides[get_user_repository] = lambda: deps.user_repository
    app.dependency_overrides[get_event_repository] = lambda: deps.event_repository
    app.dependency_overrides[get_password_hasher] = lambda: deps.password_hasher
    return TestClient(app), deps
