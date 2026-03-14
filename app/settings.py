from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_host: str = "localhost"
    app_port: int = 8080
    app_user_session_ttl: int = 60

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
