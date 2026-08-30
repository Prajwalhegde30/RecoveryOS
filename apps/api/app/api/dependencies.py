from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session

from app.config import get_settings
from app.persistence.base import build_engine, build_session_factory


@lru_cache
def get_session_factory():
    settings = get_settings()
    return build_session_factory(build_engine(settings.database_url))


def get_db_session() -> Generator[Session, None, None]:
    with get_session_factory()() as session:
        yield session
