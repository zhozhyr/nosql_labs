import re
from datetime import datetime

from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.events.dependencies import get_event_repository
from app.events.models import EventItem, ListEventsResponse
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
DATE_RE = re.compile(r"^\d{8}$")
VALID_CATEGORIES = {"meetup", "concert", "exhibition", "party", "other"}


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


def _is_valid_date(value: object) -> bool:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return False
    return True


def _normalize_date(value: str) -> str:
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"


def _is_valid_category(value: object) -> bool:
    return isinstance(value, str) and value in VALID_CATEGORIES


def _is_valid_uint(value: object) -> bool:
    return isinstance(value, int) and value >= 0 and not isinstance(value, bool)


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
    filters: dict[str, object] = {}

    str_params = ("title", "id", "city", "user")
    for name in str_params:
        value = request.query_params.get(name)
        if value is not None:
            if not _is_non_empty_string(value):
                return _error_response(
                    400,
                    f'invalid "{name}" field',
                    sid,
                    settings.app_user_session_ttl,
                    store,
                )
            filters[name] = value

    category = request.query_params.get("category")
    if category is not None:
        if not _is_valid_category(category):
            return _error_response(
                400,
                'invalid "category" field',
                sid,
                settings.app_user_session_ttl,
                store,
            )
        filters["category"] = category

    for name in ("limit", "offset", "price_from", "price_to"):
        raw = request.query_params.get(name)
        if raw is None:
            continue
        if not raw.isdigit():
            return _error_response(
                400,
                f'invalid "{name}" field',
                sid,
                settings.app_user_session_ttl,
                store,
            )
        filters[name] = int(raw)

    for name in ("date_from", "date_to"):
        value = request.query_params.get(name)
        if value is None:
            continue
        if not _is_valid_date(value):
            return _error_response(
                400,
                f'invalid "{name}" field',
                sid,
                settings.app_user_session_ttl,
                store,
            )
        filters[name] = _normalize_date(value)

    events = repository.list_events(
        filters=filters,
        limit=filters.get("limit") if isinstance(filters.get("limit"), int) else None,
        offset=filters.get("offset") if isinstance(filters.get("offset"), int) else None,
    )
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


@router.get("/events/{event_id}", response_model=EventItem)
def get_event(
    event_id: str,
    request: Request,
    store: RedisSessionStore = Depends(get_session_store),
    repository: EventRepository = Depends(get_event_repository),
) -> Response:
    settings = get_settings()
    sid = get_existing_session_id(request.cookies.get("X-Session-Id"), store)
    event = repository.get_event_by_id(event_id)
    if event is None:
        return _error_response(
            404,
            "Not found",
            sid,
            settings.app_user_session_ttl,
            store
        )

    response = JSONResponse(status_code=200, content=event.model_dump())
    if sid is not None:
        set_session_cookie(response, sid, settings.app_user_session_ttl)
    return response


@router.patch("/events/{event_id}")
def update_event(
    event_id: str,
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
    updates: dict[str, object] = {}
    unset_fields: list[str] = []

    if "category" in body:
        if not _is_valid_category(body["category"]):
            return _error_response(
                400,
                'invalid "category" field',
                sid,
                settings.app_user_session_ttl,
                store,
            )
        updates["category"] = body["category"]

    if "price" in body:
        if not _is_valid_uint(body["price"]):
            return _error_response(
                400,
                'invalid "price" field',
                sid,
                settings.app_user_session_ttl,
                store,
            )
        updates["price"] = body["price"]

    if "city" in body:
        city = body["city"]
        if not isinstance(city, str):
            return _error_response(
                400,
                'invalid "city" field',
                sid,
                settings.app_user_session_ttl,
                store,
            )
        if city == "":
            unset_fields.append("location.city")
        elif city.strip() == "":
            return _error_response(
                400,
                'invalid "city" field',
                sid,
                settings.app_user_session_ttl,
                store,
            )
        else:
            updates["location.city"] = city

    updated = repository.update_event(
        event_id=event_id,
        user_id=str(session["user_id"]),
        updates=updates,
        unset_fields=unset_fields,
    )
    if not updated:
        return _error_response(
            404,
            "Not found. Be sure that event exists and you are the organizer",
            sid,
            settings.app_user_session_ttl,
            store,
        )

    store.touch_session(sid, settings.app_user_session_ttl)
    response = Response(status_code=204)
    set_session_cookie(response, sid, settings.app_user_session_ttl)
    return response
