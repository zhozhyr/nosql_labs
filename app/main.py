from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.events.router import router as events_router
from app.health.router import router as health_router
from app.sessions.router import router as sessions_router
from app.users.router import router as users_router


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(users_router)
    app.include_router(auth_router)
    app.include_router(events_router)
    return app


app = create_app()
