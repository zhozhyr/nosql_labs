from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_host: str
    app_port: int
    app_user_session_ttl: int

    redis_host: str
    redis_port: int
    redis_password: str
    redis_db: int
    mongodb_database: str = Field(
        validation_alias=AliasChoices("MONGODB_DATABASE", "MONGODB_DATABSE")
    )
    mongodb_user: str
    mongodb_password: str
    mongodb_host: str
    mongodb_port: int

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
