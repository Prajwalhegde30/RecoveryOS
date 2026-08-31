from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt


class AuthError(ValueError):
    """Raised when a bearer token is absent, malformed, expired, or unverifiable."""


@dataclass(frozen=True)
class AuthContext:
    subject: str
    issuer: str
    merchant_id: str
    role: str
    correlation_id: str | None = None


def create_local_demo_token(
    *,
    subject: str,
    issuer: str,
    merchant_id: str,
    role: str,
    secret: str,
    audience: str,
    lifetime: timedelta,
    now: datetime | None = None,
) -> str:
    if not all((subject, issuer, merchant_id, role, secret, audience)):
        raise ValueError("local token identity and signing configuration are required")
    if lifetime <= timedelta(0):
        raise ValueError("token lifetime must be positive")
    issued_at = int((now or datetime.now(UTC)).timestamp())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "merchant_id": merchant_id,
        "role": role,
        "iat": issued_at,
        "exp": issued_at + int(lifetime.total_seconds()),
    }
    encoded_header = _encode_json(header)
    encoded_payload = _encode_json(payload)
    signing_input = f"{encoded_header}.{encoded_payload}".encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_encode(signature)}"


def decode_token(
    token: str,
    *,
    secret: str,
    issuer: str,
    audience: str,
    now: datetime | None = None,
) -> AuthContext:
    if not token or not secret or not issuer or not audience:
        raise AuthError("token validation is not configured")
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("malformed bearer token")
    try:
        header = _decode_json(parts[0])
        payload = _decode_json(parts[1])
        signature = _decode(parts[2])
    except (ValueError, json.JSONDecodeError) as exc:
        raise AuthError("malformed bearer token") from exc
    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise AuthError("unsupported token algorithm")
    expected = hmac.new(secret.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise AuthError("invalid bearer token signature")
    required = ("sub", "iss", "aud", "merchant_id", "exp")
    if any(not isinstance(payload.get(key), str if key != "exp" else int) for key in required):
        raise AuthError("bearer token claims are incomplete")
    if payload["iss"] != issuer or payload["aud"] != audience:
        raise AuthError("bearer token issuer or audience is invalid")
    now_seconds = int((now or datetime.now(UTC)).timestamp())
    if payload["exp"] <= now_seconds:
        raise AuthError("bearer token has expired")
    if "nbf" in payload and (not isinstance(payload["nbf"], int) or payload["nbf"] > now_seconds):
        raise AuthError("bearer token is not active")
    role = payload.get("role")
    if role is not None and not isinstance(role, str):
        raise AuthError("bearer token role is invalid")
    correlation_id = payload.get("correlation_id")
    return AuthContext(
        subject=payload["sub"],
        issuer=payload["iss"],
        merchant_id=payload["merchant_id"],
        role=role or "",
        correlation_id=correlation_id if isinstance(correlation_id, str) else None,
    )


def decode_jwks_token(
    token: str,
    *,
    jwks_url: str,
    issuer: str,
    audience: str,
) -> AuthContext:
    """Validate an asymmetric provider-issued JWT against a configured JWKS endpoint."""
    if not token or not jwks_url or not issuer or not audience:
        raise AuthError("token validation is not configured")
    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if algorithm not in {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}:
            raise AuthError("unsupported token algorithm")
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            audience=audience,
            issuer=issuer,
            options={"require": ["sub", "iss", "aud", "exp", "merchant_id"]},
        )
    except AuthError:
        raise
    except (jwt.PyJWTError, ValueError, OSError) as exc:
        raise AuthError("bearer token could not be verified") from exc
    if not isinstance(payload, dict):
        raise AuthError("bearer token claims are incomplete")
    required = ("sub", "iss", "aud", "merchant_id")
    if any(not isinstance(payload.get(key), str) for key in required):
        raise AuthError("bearer token claims are incomplete")
    role = payload.get("role")
    if role is not None and not isinstance(role, str):
        raise AuthError("bearer token role is invalid")
    correlation_id = payload.get("correlation_id")
    return AuthContext(
        subject=payload["sub"],
        issuer=payload["iss"],
        merchant_id=payload["merchant_id"],
        role=role or "",
        correlation_id=correlation_id if isinstance(correlation_id, str) else None,
    )


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url)


def _encode_json(value: dict[str, Any]) -> str:
    return _encode(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())


def _decode_json(value: str) -> dict[str, Any]:
    decoded = json.loads(_decode(value))
    if not isinstance(decoded, dict):
        raise ValueError("token section must be an object")
    return decoded


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
