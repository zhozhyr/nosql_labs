from functools import lru_cache

from app.security import BcryptPasswordHasher, PasswordHasher
from app.settings import get_settings
from app.users.repository import MongoUserRepository, UserRepository


@lru_cache
def get_user_repository() -> UserRepository:
    settings = get_settings()
    return MongoUserRepository(
        host=settings.mongodb_host,
        port=settings.mongodb_port,
        username=settings.mongodb_user,
        password=settings.mongodb_password,
        database=settings.mongodb_database,
    )


@lru_cache
def get_password_hasher() -> PasswordHasher:
    return BcryptPasswordHasher()
