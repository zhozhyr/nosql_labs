from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.security import PasswordHasher
from app.sessions.dependencies import get_session_store
from app.sessions.service import (
    expire_session_cookie,
    get_existing_session,
    get_existing_session_id,
    set_session_cookie,
    start_or_rebind_authenticated_session,
)
from app.sessions.store import RedisSessionStore
from app.settings import get_settings
from app.users.dependencies import get_password_hasher, get_user_repository
from app.users.repository import UserRepository

router = APIRouter(prefix="/auth")


def _invalid_field_response(
    field_name: str,
    sid: str | None,
    ttl: int,
    store: RedisSessionStore,
) -> Response:
    response = JSONResponse(
        status_code=400,
        content={"message": f'invalid "{field_name}" field'},
    )
    if sid is not None:
        store.touch_session(sid, ttl)
        set_session_cookie(response, sid, ttl)
    return response


@router.post("/login")
def login(
    request: Request,
    payload: object = Body(default_factory=dict),
    store: RedisSessionStore = Depends(get_session_store),
    repository: UserRepository = Depends(get_user_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
) -> Response:
    settings = get_settings()
    sid = get_existing_session_id(request.cookies.get("X-Session-Id"), store)
    body = payload if isinstance(payload, dict) else {}

    username = body.get("username")
    password = body.get("password")

    if not isinstance(username, str) or username.strip() == "":
        return _invalid_field_response(
            "username",
            sid,
            settings.app_user_session_ttl,
            store,
        )
    if not isinstance(password, str) or password == "":
        return _invalid_field_response(
            "password",
            sid,
            settings.app_user_session_ttl,
            store,
        )

    user = repository.find_by_username(username.strip())
    if user is None or not hasher.verify_password(password, user.password_hash):
        response = JSONResponse(
            status_code=401,
            content={"message": "invalid credentials"},
        )
        if sid is not None:
            store.touch_session(sid, settings.app_user_session_ttl)
            set_session_cookie(response, sid, settings.app_user_session_ttl)
        return response

    authenticated_sid = start_or_rebind_authenticated_session(
        sid=sid,
        user_id=user.id,
        ttl_seconds=settings.app_user_session_ttl,
        store=store,
    )
    response = Response(status_code=204)
    set_session_cookie(response, authenticated_sid, settings.app_user_session_ttl)
    return response


@router.post("/logout")
def logout(
    request: Request,
    store: RedisSessionStore = Depends(get_session_store),
) -> Response:
    settings = get_settings()
    sid = get_existing_session_id(request.cookies.get("X-Session-Id"), store)
    session = get_existing_session(sid, store)
    if session is None or "user_id" not in session:
        response = Response(status_code=401)
        if sid is not None:
            store.touch_session(sid, settings.app_user_session_ttl)
            set_session_cookie(response, sid, settings.app_user_session_ttl)
        return response

    store.delete_session(sid)

    response = Response(status_code=204)
    expire_session_cookie(response)
    return response
