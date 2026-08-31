from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import AuthContext, AuthError, decode_jwks_token, decode_token
from app.config import get_settings
from app.persistence.base import build_engine, build_session_factory
from app.persistence.models import MerchantMembership, User


@lru_cache
def get_session_factory():
    settings = get_settings()
    return build_session_factory(build_engine(settings.database_url))


def get_db_session() -> Generator[Session, None, None]:
    with get_session_factory()() as session:
        yield session


db_session_dependency = Depends(get_db_session)


def get_auth_context(
    request: Request,
    session: Session = db_session_dependency,
) -> AuthContext:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bearer authentication is required",
        )
    settings = get_settings()
    try:
        token = authorization[7:].strip()
        if settings.auth_mode == "local":
            if not settings.auth_hmac_secret:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="authentication is not configured",
                )
            token_context = decode_token(
                token,
                secret=settings.auth_hmac_secret,
                issuer=settings.auth_issuer,
                audience=settings.auth_audience,
            )
        elif settings.auth_mode == "jwks":
            if not settings.auth_jwks_url:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="authentication is not configured",
                )
            token_context = decode_jwks_token(
                token,
                jwks_url=settings.auth_jwks_url,
                issuer=settings.auth_issuer,
                audience=settings.auth_audience,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="authentication is not configured",
            )
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    membership = session.scalar(
        select(MerchantMembership.role)
        .join(User, User.id == MerchantMembership.user_id)
        .where(
            MerchantMembership.merchant_id == token_context.merchant_id,
            User.subject == token_context.subject,
            User.issuer == token_context.issuer,
            User.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="merchant access denied")
    return AuthContext(
        subject=token_context.subject,
        issuer=token_context.issuer,
        merchant_id=token_context.merchant_id,
        role=str(membership),
        correlation_id=token_context.correlation_id,
    )


auth_context_dependency = Depends(get_auth_context)


def get_merchant_scope(context: AuthContext = auth_context_dependency) -> str:
    return context.merchant_id


def require_role(*roles: str):
    allowed_roles = frozenset(roles)

    def dependency(context: AuthContext = auth_context_dependency) -> AuthContext:
        if context.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="operation is not permitted for this role",
            )
        return context

    return dependency


admin_dependency = Depends(require_role("ADMIN"))
operator_dependency = Depends(require_role("OPERATOR", "ADMIN"))
