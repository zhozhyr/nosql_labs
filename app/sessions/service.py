import re
import secrets

from fastapi import Response
from fastapi.responses import JSONResponse

from app.sessions.store import COOKIE_NAME, RedisSessionStore

SID_RE = re.compile(r"^[0-9a-f]{32}$")


def is_valid_sid(value: str | None) -> bool:
    if value is None:
        return False
    return bool(SID_RE.fullmatch(value))


def generate_sid() -> str:
    return secrets.token_hex(16)


def set_session_cookie(response: Response, sid: str, ttl_seconds: int) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=sid,
        httponly=True,
        path="/",
        max_age=ttl_seconds,
    )


def build_health_response(sid: str | None, ttl_seconds: int) -> JSONResponse:
    response = JSONResponse(content={"status": "ok"}, status_code=200)
    if sid is not None:
        set_session_cookie(response, sid, ttl_seconds)
    return response


def handle_session_request(
    sid: str | None,
    ttl_seconds: int,
    store: RedisSessionStore,
) -> Response:
    if is_valid_sid(sid) and store.session_exists(sid):
        store.touch_session(sid, ttl_seconds)

        response = Response(status_code=200)
        set_session_cookie(response, sid, ttl_seconds)
        return response

    while True:
        new_sid = generate_sid()
        if store.create_session(new_sid, ttl_seconds):
            response = Response(status_code=201)
            set_session_cookie(response, new_sid, ttl_seconds)
            return response
