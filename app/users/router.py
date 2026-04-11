from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.events.dependencies import get_event_repository
from app.events.models import ListEventsResponse
from app.events.repository import EventRepository
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
from app.users.models import ListUsersResponse, UserItem
from app.users.repository import UserRepository

router = APIRouter()


def _validate_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _error_response(
    status_code: int,
    message: str,
    sid: str | None,
    ttl: int,
    store: RedisSessionStore,
) -> Response:
    response = JSONResponse(status_code=status_code, content={"message": message})
    if sid is not None:
        store.touch_session(sid, ttl)
        set_session_cookie(response, sid, ttl)
    return response


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


@router.get("/users", response_model=ListUsersResponse)
def list_users(
    request: Request,
    store: RedisSessionStore = Depends(get_session_store),
    repository: UserRepository = Depends(get_user_repository),
) -> Response:
    settings = get_settings()
    sid = get_existing_session_id(request.cookies.get("X-Session-Id"), store)
    params = request.query_params

    name = params.get("name")
    if name is not None and not _validate_non_empty_string(name):
        return _error_response(
            400,
            'invalid "name" field',
            sid,
            settings.app_user_session_ttl,
            store
        )

    user_id = params.get("id")
    if user_id is not None and not _validate_non_empty_string(user_id):
        return _error_response(
            400,
            'invalid "id" field',
            sid,
            settings.app_user_session_ttl,
            store
        )

    limit: int | None = None
    limit_raw = params.get("limit")
    if limit_raw is not None:
        if not limit_raw.isdigit():
            return _error_response(
                400,
                'invalid "limit" field',
                sid,
                settings.app_user_session_ttl,
                store
            )
        limit = int(limit_raw)

    offset: int | None = None
    offset_raw = params.get("offset")
    if offset_raw is not None:
        if not offset_raw.isdigit():
            return _error_response(
                400,
                'invalid "offset" field',
                sid,
                settings.app_user_session_ttl,
                store
            )
        offset = int(offset_raw)

    users = repository.list_users(
        name=name,
        user_id=user_id,
        limit=limit,
        offset=offset
    )
    response = JSONResponse(
        status_code=200,
        content={"users": [user.model_dump() for user in users], "count": len(users)},
    )
    if sid is not None:
        set_session_cookie(response, sid, settings.app_user_session_ttl)
    return response


@router.get("/users/{user_id}", response_model=UserItem)
def get_user(
    user_id: str,
    request: Request,
    store: RedisSessionStore = Depends(get_session_store),
    repository: UserRepository = Depends(get_user_repository),
) -> Response:
    settings = get_settings()
    sid = get_existing_session_id(request.cookies.get("X-Session-Id"), store)
    user = repository.get_user_by_id(user_id)
    if user is None:
        return _error_response(
            404,
            "Not found",
            sid,
            settings.app_user_session_ttl,
            store
        )

    response = JSONResponse(status_code=200, content=user.model_dump())
    if sid is not None:
        set_session_cookie(response, sid, settings.app_user_session_ttl)
    return response


@router.get("/users/{user_id}/events", response_model=ListEventsResponse)
def get_user_events(
    user_id: str,
    request: Request,
    store: RedisSessionStore = Depends(get_session_store),
    user_repository: UserRepository = Depends(get_user_repository),
    event_repository: EventRepository = Depends(get_event_repository),
) -> Response:
    settings = get_settings()
    sid = get_existing_session_id(request.cookies.get("X-Session-Id"), store)
    if user_repository.get_user_by_id(user_id) is None:
        return _error_response(
            404,
            "User not found",
            sid,
            settings.app_user_session_ttl,
            store
        )

    events = event_repository.list_events(
        filters={"created_by": user_id},
        limit=None,
        offset=None,
    )
    response = JSONResponse(
        status_code=200,
        content={
            "events": [event.model_dump() for event in events], "count": len(events)
        },
    )
    if sid is not None:
        set_session_cookie(response, sid, settings.app_user_session_ttl)
    return response
