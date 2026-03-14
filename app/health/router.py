from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.sessions.service import build_health_response
from app.sessions.store import COOKIE_NAME
from app.settings import get_settings

router = APIRouter()


@router.get("/health")
def health(request: Request) -> JSONResponse:
    settings = get_settings()
    sid = request.cookies.get(COOKIE_NAME)
    return build_health_response(sid, settings.app_user_session_ttl)
