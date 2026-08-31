from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Header, HTTPException, status
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


def get_merchant_scope(
    merchant_id: Annotated[str | None, Header(alias="X-Merchant-Id")] = None,
) -> str:
    """Temporary tenant-scope seam; JWT/RBAC enforcement is added in Phase 14."""
    if not merchant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authenticated merchant scope is required",
        )
    return merchant_id
