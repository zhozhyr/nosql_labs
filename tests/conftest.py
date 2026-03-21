import os

from fastapi.testclient import TestClient

from app.main import app
from app.sessions.dependencies import get_session_store
from app.settings import get_settings

# Храним конфигурацию тестов локально, чтобы тесты были изолированы
TEST_ENV = {
    "APP_HOST": "127.0.0.1",
    "APP_PORT": "8080",
    "APP_USER_SESSION_TTL": "60",
    "REDIS_HOST": "redis",
    "REDIS_PORT": "6379",
    "REDIS_PASSWORD": "",
    "REDIS_DB": "0",
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


def create_client() -> tuple[TestClient, FakeSessionStore]:
    get_settings.cache_clear()
    get_session_store.cache_clear()

    store = FakeSessionStore()
    app.dependency_overrides = {}
    app.dependency_overrides[get_session_store] = lambda: store
    return TestClient(app), store
