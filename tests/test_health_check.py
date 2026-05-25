from app.sessions.store import COOKIE_NAME
from tests.conftest import create_client


def test_health_without_cookie():
    client, _ = create_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "set-cookie" not in response.headers


def test_health_with_cookie_returns_same_cookie_without_creating_session():
    client, deps = create_client()

    response = client.get(
        "/health",
        cookies={COOKIE_NAME: "a" * 32},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.cookies.get(COOKIE_NAME) == "a" * 32
    assert deps.store.sessions == {}
