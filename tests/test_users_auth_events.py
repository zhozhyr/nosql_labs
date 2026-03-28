import pytest

from app.sessions.store import COOKIE_NAME
from tests.conftest import create_client


def create_anonymous_session(client, deps) -> str:
    sid = f"{len(deps.store.sessions) + 1:032x}"
    deps.store.create_session(sid, 60)
    client.cookies.set(COOKIE_NAME, sid, domain="testserver.local", path="/")
    return sid


def register_user(
    client,
    deps,
    username: str = "j0hnd0e42",
    password: str = "strong-pass",
):
    create_anonymous_session(client, deps)
    return client.post(
        "/users",
        json={
            "full_name": "Иван Иванов",
            "username": username,
            "password": password,
        },
    )


def test_create_user_registers_user_and_binds_new_session():
    client, deps = create_client()

    old_sid = create_anonymous_session(client, deps)
    response = client.post(
        "/users",
        json={
            "full_name": "Иван Иванов",
            "username": "j0hnd0e42",
            "password": "svp4_dvp4_str0ng_passw0rd",
        },
    )

    assert response.status_code == 201
    new_sid = response.cookies.get(COOKIE_NAME)
    assert new_sid is not None
    assert new_sid != old_sid
    assert deps.store.sessions[new_sid]["user_id"] == "user-1"
    assert deps.user_repository.find_by_username("j0hnd0e42") is not None


def test_create_user_requires_existing_session():
    client, deps = create_client()

    response = client.post(
        "/users",
        json={
            "full_name": "Иван Иванов",
            "username": "j0hnd0e42",
            "password": "svp4_dvp4_str0ng_passw0rd",
        },
    )

    assert response.status_code == 401
    assert deps.store.sessions == {}


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"full_name": "", "username": "j0hnd0e42", "password": "password"},
            'invalid "full_name" field',
        ),
        (
            {"full_name": "Джон Доу", "username": "", "password": "password"},
            'invalid "username" field',
        ),
        (
            {"full_name": "Джон Доу", "username": "j0hnd0e42", "password": ""},
            'invalid "password" field',
        ),
    ],
)
def test_create_user_returns_400_without_creating_session_when_payload_invalid(
    payload,
    message,
):
    client, deps = create_client()
    sid = create_anonymous_session(client, deps)

    response = client.post(
        "/users",
        json=payload,
    )

    assert response.status_code == 400
    assert response.json() == {"message": message}
    assert response.cookies.get(COOKIE_NAME) == sid
    assert deps.store.sessions[sid]["updated_at"] == "2026-01-01T00:01:00Z"


def test_create_user_returns_409_and_keeps_existing_session():
    client, deps = create_client()

    register_user(client, deps)
    existing_sid = create_anonymous_session(client, deps)
    response = client.post(
        "/users",
        json={
            "full_name": "Петр Петров",
            "username": "j0hnd0e42",
            "password": "new-password",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"message": "user already exists"}
    assert response.cookies.get(COOKIE_NAME) == existing_sid
    assert deps.store.sessions[existing_sid]["updated_at"] == "2026-01-01T00:01:00Z"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"username": "", "password": "strong-pass"},
            'invalid "username" field',
        ),
        (
            {"username": "j0hnd0e42", "password": ""},
            'invalid "password" field',
        ),
    ],
)
def test_login_returns_400_for_invalid_payload(payload, message):
    client, deps = create_client()

    register_user(client, deps)
    sid = create_anonymous_session(client, deps)
    response = client.post("/auth/login", json=payload)

    assert response.status_code == 400
    assert response.json() == {"message": message}
    assert response.cookies.get(COOKIE_NAME) == sid


def test_login_reuses_existing_session_and_sets_user_id():
    client, deps = create_client()

    register_user(client, deps)
    sid = create_anonymous_session(client, deps)
    response = client.post(
        "/auth/login",
        json={"username": "j0hnd0e42", "password": "strong-pass"},
    )

    assert response.status_code == 204
    assert response.cookies.get(COOKIE_NAME) == sid
    assert deps.store.sessions[sid]["user_id"] == "user-1"


def test_login_returns_401_for_invalid_credentials():
    client, deps = create_client()

    register_user(client, deps)
    sid = create_anonymous_session(client, deps)
    response = client.post(
        "/auth/login",
        json={"username": "j0hnd0e42", "password": "wrong-pass"},
    )

    assert response.status_code == 401
    assert response.json() == {"message": "invalid credentials"}
    assert response.cookies.get(COOKIE_NAME) == sid
    assert "user_id" not in deps.store.sessions[sid]


def test_logout_requires_authenticated_user():
    client, deps = create_client()

    sid = create_anonymous_session(client, deps)
    response = client.post("/auth/logout")

    assert response.status_code == 401
    assert sid in deps.store.sessions
    assert response.cookies.get(COOKIE_NAME) == sid


def test_logout_deletes_authenticated_session_and_expires_cookie():
    client, deps = create_client()

    register_user(client, deps)
    sid = client.cookies.get(COOKIE_NAME)

    response = client.post("/auth/logout")

    assert response.status_code == 204
    assert sid not in deps.store.sessions
    set_cookie = response.headers["set-cookie"]
    assert "Max-Age=0" in set_cookie


def test_create_event_requires_authorized_user():
    client, deps = create_client()

    sid = create_anonymous_session(client, deps)
    response = client.post(
        "/events",
        json={
            "title": "Праздник",
            "address": "СПб",
            "started_at": "2026-04-01T12:00:00+03:00",
            "finished_at": "2026-04-01T23:00:00+03:00",
            "description": "Праздник",
        },
    )

    assert response.status_code == 401
    assert response.cookies.get(COOKIE_NAME) == sid


def test_create_event_persists_document_and_returns_id():
    client, deps = create_client()

    register_user(client, deps)
    response = client.post(
        "/events",
        json={
            "title": "Мой день рождения",
            "address": "г. Санкт-Петербург, ул. Пушкина",
            "started_at": "2026-04-01T12:00:00+03:00",
            "finished_at": "2026-04-01T23:00:00+03:00",
            "description": "Праздник",
        },
    )

    assert response.status_code == 201
    assert response.json() == {"id": "event-1"}
    stored = deps.event_repository.events[0]
    assert stored["created_by"] == "user-1"
    assert stored["location"] == {"address": "г. Санкт-Петербург, ул. Пушкина"}


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "title": "",
                "address": "СПб",
                "started_at": "2026-04-01T12:00:00+03:00",
                "finished_at": "2026-04-01T23:00:00+03:00",
                "description": "Праздник",
            },
            'invalid "title" field',
        ),
        (
            {
                "title": "Мой день рождения",
                "address": "",
                "started_at": "2026-04-01T12:00:00+03:00",
                "finished_at": "2026-04-01T23:00:00+03:00",
                "description": "Праздник",
            },
            'invalid "address" field',
        ),
        (
            {
                "title": "Мой день рождения",
                "address": "СПб",
                "started_at": "not-a-date",
                "finished_at": "2026-04-01T23:00:00+03:00",
                "description": "Праздник",
            },
            'invalid "started_at" field',
        ),
        (
            {
                "title": "Мой день рождения",
                "address": "СПб",
                "started_at": "2026-04-01T12:00:00+03:00",
                "finished_at": "not-a-date",
                "description": "Праздник",
            },
            'invalid "finished_at" field',
        ),
        (
            {
                "title": "Мой день рождения",
                "address": "СПб",
                "started_at": "2026-04-01T12:00:00+03:00",
                "finished_at": "2026-04-01T23:00:00+03:00",
                "description": "",
            },
            'invalid "description" field',
        ),
    ],
)
def test_create_event_validates_fields(payload, message):
    client, deps = create_client()

    register_user(client, deps)
    response = client.post("/events", json=payload)

    assert response.status_code == 400
    assert response.json() == {"message": message}


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("title=", 'invalid "title" parameter'),
        ("limit=-1", 'invalid "limit" parameter'),
        ("limit=abc", 'invalid "limit" parameter'),
        ("offset=-1", 'invalid "offset" parameter'),
        ("offset=abc", 'invalid "offset" parameter'),
    ],
)
def test_list_events_returns_400_for_invalid_query_params(query, message):
    client, deps = create_client()

    sid = create_anonymous_session(client, deps)
    response = client.get(f"/events?{query}")

    assert response.status_code == 400
    assert response.json() == {"message": message}
    assert response.cookies.get(COOKIE_NAME) == sid


def test_list_events_returns_filtered_paginated_events():
    client, deps = create_client()

    register_user(client, deps)
    client.post(
        "/events",
        json={
            "title": "Python meetup",
            "address": "Moscow",
            "started_at": "2026-04-01T12:00:00+03:00",
            "finished_at": "2026-04-01T14:00:00+03:00",
            "description": "Meetup",
        },
    )
    client.post(
        "/events",
        json={
            "title": "Java meetup",
            "address": "SPb",
            "started_at": "2026-04-02T12:00:00+03:00",
            "finished_at": "2026-04-02T14:00:00+03:00",
            "description": "Meetup",
        },
    )

    response = client.get("/events?title=meetup&limit=1&offset=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["events"][0]["title"] == "Java meetup"
