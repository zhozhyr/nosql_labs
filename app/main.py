from fastapi import FastAPI

from app.health.router import router as health_router
from app.sessions.router import router as sessions_router


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_router)
    app.include_router(sessions_router)
    return app


app = create_app()
