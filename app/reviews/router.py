from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.events.dependencies import get_event_repository
from app.events.repository import EventRepository
from app.reviews.dependencies import get_review_repository
from app.reviews.repository import ReviewRepository
from app.sessions.dependencies import get_session_store
from app.sessions.service import (
    get_existing_session,
    get_existing_session_id,
    set_session_cookie,
)
from app.sessions.store import RedisSessionStore
from app.settings import get_settings

router = APIRouter()


def _error_response(
    status_code: int,
    message: str | None,
    sid: str | None,
    ttl: int,
    store: RedisSessionStore,
) -> Response:
    if message is None:
        response = Response(status_code=status_code)
    else:
        response = JSONResponse(status_code=status_code, content={"message": message})
    if sid is not None:
        store.touch_session(sid, ttl)
        set_session_cookie(response, sid, ttl)
    return response


def _resolve_event_repository(request: Request) -> EventRepository:
    provider = request.app.dependency_overrides.get(get_event_repository)
    if provider is not None:
        return provider()
    return get_event_repository()


def _resolve_review_repository(request: Request) -> ReviewRepository:
    provider = request.app.dependency_overrides.get(get_review_repository)
    if provider is not None:
        return provider()
    return get_review_repository()


@router.post("/events/{event_id}/reviews")
def create_review(
    event_id: str,
    request: Request,
    payload: object = Body(default_factory=dict),
    store: RedisSessionStore = Depends(get_session_store),
) -> Response:
    settings = get_settings()
    sid = get_existing_session_id(request.cookies.get("X-Session-Id"), store)
    session = get_existing_session(sid, store)

    if session is None or "user_id" not in session:
        return _error_response(401, None, None, settings.app_user_session_ttl, store)

    body = payload if isinstance(payload, dict) else {}

    rating = body.get("rating")
    if (
        not isinstance(rating, int)
        or isinstance(rating, bool)
        or rating < 1
        or rating > 5
    ):
        return _error_response(
            400, 'invalid "rating" field', sid, settings.app_user_session_ttl, store
        )

    comment = body.get("comment")
    if not isinstance(comment, str) or len(comment) > 300:
        return _error_response(
            400, 'invalid "comment" field', sid, settings.app_user_session_ttl, store
        )

    event_repository = _resolve_event_repository(request)
    event = event_repository.get_event_by_id(event_id)
    if event is None:
        return _error_response(
            404, "Event not found", sid, settings.app_user_session_ttl, store
        )

    user_id = str(session["user_id"])
    review_repository = _resolve_review_repository(request)
    review_id = review_repository.create_review(event_id, user_id, rating, comment)

    if review_id is None:
        return _error_response(
            409, "Already exists", sid, settings.app_user_session_ttl, store
        )

    event_ids = event_repository.get_event_ids_by_title(event.title)
    review_repository.update_reviews_cache(event.title, event_ids)

    store.touch_session(sid, settings.app_user_session_ttl)
    response = JSONResponse(status_code=201, content={"id": review_id})
    set_session_cookie(response, sid, settings.app_user_session_ttl)
    return response


@router.get("/events/{event_id}/reviews")
def list_reviews(
    event_id: str,
    request: Request,
    store: RedisSessionStore = Depends(get_session_store),
) -> Response:
    settings = get_settings()
    sid = get_existing_session_id(request.cookies.get("X-Session-Id"), store)

    limit: int | None = None
    offset: int | None = None

    limit_raw = request.query_params.get("limit")
    if limit_raw is not None:
        if not limit_raw.isdigit():
            return _error_response(
                400, 'invalid "limit" field', sid, settings.app_user_session_ttl, store
            )
        limit = int(limit_raw)

    offset_raw = request.query_params.get("offset")
    if offset_raw is not None:
        if not offset_raw.isdigit():
            return _error_response(
                400,
                'invalid "offset" field',
                sid,
                settings.app_user_session_ttl,
                store,
            )
        offset = int(offset_raw)

    review_repository = _resolve_review_repository(request)
    reviews = review_repository.list_reviews(event_id, limit, offset)

    response = JSONResponse(
        status_code=200,
        content={
            "reviews": [r.model_dump() for r in reviews],
            "count": len(reviews),
        },
    )
    if sid is not None:
        set_session_cookie(response, sid, settings.app_user_session_ttl)
    return response


@router.patch("/events/{event_id}/reviews/{review_id}")
def update_review(
    event_id: str,
    review_id: str,
    request: Request,
    payload: object = Body(default_factory=dict),
    store: RedisSessionStore = Depends(get_session_store),
) -> Response:
    settings = get_settings()
    sid = get_existing_session_id(request.cookies.get("X-Session-Id"), store)
    session = get_existing_session(sid, store)

    if session is None or "user_id" not in session:
        return _error_response(401, None, None, settings.app_user_session_ttl, store)

    body = payload if isinstance(payload, dict) else {}

    rating: int | None = None
    comment: str | None = None

    if "rating" in body:
        rating = body["rating"]
        if (
            not isinstance(rating, int)
            or isinstance(rating, bool)
            or rating < 1
            or rating > 5
        ):
            return _error_response(
                400,
                'invalid "rating" field',
                sid,
                settings.app_user_session_ttl,
                store,
            )

    if "comment" in body:
        comment = body["comment"]
        if not isinstance(comment, str) or len(comment) > 300:
            return _error_response(
                400,
                'invalid "comment" field',
                sid,
                settings.app_user_session_ttl,
                store,
            )

    event_repository = _resolve_event_repository(request)
    event = event_repository.get_event_by_id(event_id)
    if event is None:
        return _error_response(
            404, "Event not found", sid, settings.app_user_session_ttl, store
        )

    user_id = str(session["user_id"])
    review_repository = _resolve_review_repository(request)
    updated = review_repository.update_review(
        event_id,
        review_id,
        user_id,
        rating,
        comment
    )

    if not updated:
        return _error_response(
            404, "Event not found", sid, settings.app_user_session_ttl, store
        )

    event_ids = event_repository.get_event_ids_by_title(event.title)
    review_repository.update_reviews_cache(event.title, event_ids)

    store.touch_session(sid, settings.app_user_session_ttl)
    response = Response(status_code=204)
    set_session_cookie(response, sid, settings.app_user_session_ttl)
    return response
