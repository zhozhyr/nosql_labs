from fastapi.testclient import TestClient

from app.main import app
from app.sessions.dependencies import get_session_store


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
    store = FakeSessionStore()
    app.dependency_overrides = {}
    app.dependency_overrides[get_session_store] = lambda: store
    return TestClient(app), store
