from datetime import UTC, datetime, timedelta

import pytest

from app.auth.service import AuthError, create_local_demo_token, decode_token


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
