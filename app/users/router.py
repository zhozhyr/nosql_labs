from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.security import PasswordHasher
from app.sessions.dependencies import get_session_store
from app.sessions.service import (
    get_existing_session_id,
    set_session_cookie,
    start_fresh_authenticated_session,
)
from app.sessions.store import RedisSessionStore
from app.settings import get_settings
from app.users.dependencies import get_password_hasher, get_user_repository
from app.users.repository import UserRepository

router = APIRouter()


def _validate_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


@router.post("/users")
def create_user(
    request: Request,
    payload: object = Body(default_factory=dict),
    store: RedisSessionStore = Depends(get_session_store),
    repository: UserRepository = Depends(get_user_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
) -> Response:
    settings = get_settings()
    current_sid = get_existing_session_id(request.cookies.get("X-Session-Id"), store)
    if current_sid is None:
        return Response(status_code=401)
    body = payload if isinstance(payload, dict) else {}

    fields = {
        "full_name": body.get("full_name"),
        "username": body.get("username"),
        "password": body.get("password"),
    }
    for field_name, value in fields.items():
        if not _validate_non_empty_string(value):
            response = JSONResponse(
                status_code=400,
                content={"message": f'invalid "{field_name}" field'},
            )
            if current_sid is not None:
                store.touch_session(current_sid, settings.app_user_session_ttl)
                set_session_cookie(response, current_sid, settings.app_user_session_ttl)
            return response

    user_id = repository.create_user(
        full_name=str(fields["full_name"]).strip(),
        username=str(fields["username"]).strip(),
        password_hash=hasher.hash_password(str(fields["password"])),
    )
    if user_id is None:
        response = JSONResponse(
            status_code=409,
            content={"message": "user already exists"},
        )
        if current_sid is not None:
            store.touch_session(current_sid, settings.app_user_session_ttl)
            set_session_cookie(response, current_sid, settings.app_user_session_ttl)
        return response

    sid = start_fresh_authenticated_session(
        user_id,
        settings.app_user_session_ttl,
        store,
    )
    response = Response(status_code=201)
    set_session_cookie(response, sid, settings.app_user_session_ttl)
    return response
