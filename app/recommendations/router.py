from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.events.dependencies import get_event_repository
from app.events.models import EventItem
from app.events.repository import EventRepository
from app.recommendations.cache import RecommendationsCache
from app.recommendations.dependencies import (
    get_graph_repository,
    get_recommendations_cache,
)
from app.recommendations.graph import GraphRepository
from app.sessions.dependencies import get_session_store
from app.sessions.service import (
    get_existing_session,
    get_existing_session_id,
    set_session_cookie,
)
from app.sessions.store import RedisSessionStore
from app.settings import get_settings

router = APIRouter()


def _serialize_event(event: EventItem) -> dict[str, object]:
    return event.model_dump(exclude_none=True)


def _build_recommendations(
    user_id: str,
    graph: GraphRepository,
    events_repo: EventRepository,
) -> list[dict[str, object]]:
    grouped = graph.get_recommended_titles(user_id)
    recommended: list[dict[str, object]] = []
    for _, event_ids, _ in grouped:
        events: list[EventItem] = []
        for event_id in event_ids:
            event = events_repo.get_event_by_id(event_id)
            if event is not None:
                events.append(event)
        if not events:
            continue
        events.sort(key=lambda e: e.started_at)
        recommended.append(_serialize_event(events[0]))
    return recommended


@router.get("/recommendations")
def get_recommendations(
    request: Request,
    store: RedisSessionStore = Depends(get_session_store),
    graph: GraphRepository = Depends(get_graph_repository),
    cache: RecommendationsCache = Depends(get_recommendations_cache),
    events_repo: EventRepository = Depends(get_event_repository),
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

    user_id = str(session["user_id"])
    events = cache.get(user_id)
    if events is None:
        events = _build_recommendations(user_id, graph, events_repo)
        cache.set(user_id, events)

    store.touch_session(sid, settings.app_user_session_ttl)
    response = JSONResponse(status_code=200, content={"events": events})
    set_session_cookie(response, sid, settings.app_user_session_ttl)
    return response
