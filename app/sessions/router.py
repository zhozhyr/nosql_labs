from fastapi import APIRouter, Depends, Request, Response

from app.sessions.dependencies import get_session_store
from app.sessions.service import handle_session_request
from app.sessions.store import COOKIE_NAME, RedisSessionStore
from app.settings import get_settings

router = APIRouter()


@router.post("/session")
def session(
        request: Request,
        store: RedisSessionStore = Depends(get_session_store)
) -> Response:
    settings = get_settings()
    sid = request.cookies.get(COOKIE_NAME)
    return handle_session_request(sid, settings.app_user_session_ttl, store)
