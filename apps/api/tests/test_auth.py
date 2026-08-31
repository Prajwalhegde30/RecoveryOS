from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import service
from app.auth.service import AuthError, create_local_demo_token, decode_jwks_token, decode_token


def token(**overrides: object) -> str:
    values: dict[str, object] = {
        "subject": "subject",
        "issuer": "issuer",
        "merchant_id": "merchant",
        "role": "VIEWER",
        "secret": "secret",
        "audience": "audience",
        "lifetime": timedelta(minutes=5),
    }
    values.update(overrides)
    return create_local_demo_token(**values)  # type: ignore[arg-type]


def test_valid_token_is_decoded_without_trusting_unvalidated_role() -> None:
    decoded = decode_token(
        token(),
        secret="secret",
        issuer="issuer",
        audience="audience",
    )
    assert decoded.subject == "subject"
    assert decoded.merchant_id == "merchant"
    assert decoded.role == "VIEWER"


@pytest.mark.parametrize(
    "bad_token",
    ["", "not.a.jwt", token(secret="wrong")],
)
def test_malformed_or_invalid_signature_is_rejected(bad_token: str) -> None:
    with pytest.raises(AuthError):
        decode_token(bad_token, secret="secret", issuer="issuer", audience="audience")


def test_expired_token_is_rejected() -> None:
    expired = token(
        lifetime=timedelta(minutes=1),
        now=datetime(2026, 1, 1, 12, tzinfo=UTC),
    )
    with pytest.raises(AuthError):
        decode_token(
            expired,
            secret="secret",
            issuer="issuer",
            audience="audience",
            now=datetime(2026, 1, 1, 13, tzinfo=UTC),
        )


def test_jwks_token_is_validated_with_asymmetric_key(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = {
        "sub": "subject",
        "iss": "issuer",
        "aud": "audience",
        "merchant_id": "merchant",
        "role": "ADMIN",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    encoded = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})

    class FakeClient:
        def get_signing_key_from_jwt(self, _: str) -> object:
            return type("SigningKey", (), {"key": private_key.public_key()})()

    monkeypatch.setattr(service, "_jwks_client", lambda _: FakeClient())
    decoded = decode_jwks_token(
        encoded,
        jwks_url="https://identity.example/.well-known/jwks.json",
        issuer="issuer",
        audience="audience",
    )

    assert decoded.subject == "subject"
    assert decoded.merchant_id == "merchant"
    assert decoded.role == "ADMIN"


def test_jwks_validation_rejects_symmetric_algorithm(monkeypatch: pytest.MonkeyPatch) -> None:
    encoded = token()
    monkeypatch.setattr(service, "_jwks_client", lambda _: pytest.fail("JWKS must not be queried"))

    with pytest.raises(AuthError, match="unsupported token algorithm"):
        decode_jwks_token(
            encoded,
            jwks_url="https://identity.example/.well-known/jwks.json",
            issuer="issuer",
            audience="audience",
        )


def test_jwks_validation_rejects_wrong_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    encoded = jwt.encode(
        {
            "sub": "subject",
            "iss": "wrong-issuer",
            "aud": "audience",
            "merchant_id": "merchant",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
    )

    class FakeClient:
        def get_signing_key_from_jwt(self, _: str) -> object:
            return type("SigningKey", (), {"key": private_key.public_key()})()

    monkeypatch.setattr(service, "_jwks_client", lambda _: FakeClient())
    with pytest.raises(AuthError, match="could not be verified"):
        decode_jwks_token(
            encoded,
            jwks_url="https://identity.example/jwks",
            issuer="issuer",
            audience="audience",
        )
