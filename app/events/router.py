import re
from datetime import datetime

from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.events.dependencies import get_event_repository
from app.events.models import ListEventsResponse
from app.events.repository import EventRepository
from app.sessions.dependencies import get_session_store
from app.sessions.service import (
    get_existing_session,
    get_existing_session_id,
    set_session_cookie,
)
from app.sessions.store import RedisSessionStore
from app.settings import get_settings

router = APIRouter()

RFC3339_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$")


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_valid_rfc3339(value: object) -> bool:
    if not isinstance(value, str) or value.strip() == "":
        return False
    if not RFC3339_RE.fullmatch(value):
        return False
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _error_response(
    status_code: int,
    message: str | None,
    sid: str | None,
    ttl: int,
    store: RedisSessionStore,
) -> Response:
    response: Response
    if message is None:
        response = Response(status_code=status_code)
    else:
        response = JSONResponse(status_code=status_code, content={"message": message})

    if sid is not None:
        store.touch_session(sid, ttl)
        set_session_cookie(response, sid, ttl)
    return response


@router.post("/events")
def create_event(
    request: Request,
    payload: object = Body(default_factory=dict),
    store: RedisSessionStore = Depends(get_session_store),
    repository: EventRepository = Depends(get_event_repository),
) -> Response:
    settings = get_settings()
    sid = get_existing_session_id(request.cookies.get("X-Session-Id"), store)
    session = get_existing_session(sid, store)
    if session is None or "user_id" not in session:
        return _error_response(401, None, sid, settings.app_user_session_ttl, store)
    body = payload if isinstance(payload, dict) else {}

    fields = {
        "title": body.get("title"),
        "address": body.get("address"),
        "started_at": body.get("started_at"),
        "finished_at": body.get("finished_at"),
        "description": body.get("description"),
    }
    for field_name, value in fields.items():
        if field_name in {"started_at", "finished_at"}:
            valid = _is_valid_rfc3339(value)
        else:
            valid = _is_non_empty_string(value)
        if not valid:
            return _error_response(
                400,
                f'invalid "{field_name}" field',
                sid,
                settings.app_user_session_ttl,
                store,
            )

    event_id = repository.create_event(
        {
            "title": str(fields["title"]).strip(),
            "description": str(fields["description"]).strip(),
            "location": {"address": str(fields["address"]).strip()},
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "created_by": session["user_id"],
            "started_at": str(fields["started_at"]),
            "finished_at": str(fields["finished_at"]),
        }
    )
    if event_id is None:
        return _error_response(
            409,
            "event already exists",
            sid,
            settings.app_user_session_ttl,
            store,
        )

    store.touch_session(sid, settings.app_user_session_ttl)
    response = JSONResponse(status_code=201, content={"id": event_id})
    set_session_cookie(response, sid, settings.app_user_session_ttl)
    return response


@router.get("/events", response_model=ListEventsResponse)
def list_events(
    request: Request,
    store: RedisSessionStore = Depends(get_session_store),
    repository: EventRepository = Depends(get_event_repository),
) -> Response:
    settings = get_settings()
    sid = get_existing_session_id(request.cookies.get("X-Session-Id"), store)
    title = request.query_params.get("title")
    limit_raw = request.query_params.get("limit")
    offset_raw = request.query_params.get("offset")

    if title is not None and not _is_non_empty_string(title):
        return _error_response(
            400,
            'invalid "title" parameter',
            sid,
            settings.app_user_session_ttl,
            store,
        )

    limit: int | None = None
    if limit_raw is not None:
        if not limit_raw.isdigit():
            return _error_response(
                400,
                'invalid "limit" parameter',
                sid,
                settings.app_user_session_ttl,
                store,
            )
        limit = int(limit_raw)

    offset: int | None = None
    if offset_raw is not None:
        if not offset_raw.isdigit():
            return _error_response(
                400,
                'invalid "offset" parameter',
                sid,
                settings.app_user_session_ttl,
                store,
            )
        offset = int(offset_raw)

    if limit is not None and limit < 0:
        return _error_response(
            400,
            'invalid "limit" parameter',
            sid,
            settings.app_user_session_ttl,
            store,
        )
    if offset is not None and offset < 0:
        return _error_response(
            400,
            'invalid "offset" parameter',
            sid,
            settings.app_user_session_ttl,
            store,
        )

    events = repository.list_events(title=title, limit=limit, offset=offset)
    response = JSONResponse(
        status_code=200,
        content={
            "events": [event.model_dump() for event in events],
            "count": len(events),
        },
    )
    if sid is not None:
        set_session_cookie(response, sid, settings.app_user_session_ttl)
    return response
