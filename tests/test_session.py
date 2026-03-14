from app.sessions.store import COOKIE_NAME
from tests.conftest import create_client


def test_session_creates_new_session_on_first_visit():
    client, store = create_client()

    response = client.post("/session")

    assert response.status_code == 201

    sid = response.cookies.get(COOKIE_NAME)
    assert sid is not None
    assert len(sid) == 32
    assert sid in store.sessions


def test_session_updates_existing_session():
    client, store = create_client()
    existing_sid = "b" * 32
    store.create_session(existing_sid, 60)

    response = client.post(
        "/session",
        cookies={COOKIE_NAME: existing_sid},
    )

    assert response.status_code == 200
    assert response.cookies.get(COOKIE_NAME) == existing_sid
    assert store.sessions[existing_sid]["updated_at"] == "2026-01-01T00:01:00Z"


def test_session_creates_new_one_if_cookie_is_invalid():
    client, store = create_client()

    response = client.post(
        "/session",
        cookies={COOKIE_NAME: "not-a-valid-sid"},
    )

    assert response.status_code == 201

    sid = response.cookies.get(COOKIE_NAME)
    assert sid is not None
    assert sid != "not-a-valid-sid"
    assert sid in store.sessions
