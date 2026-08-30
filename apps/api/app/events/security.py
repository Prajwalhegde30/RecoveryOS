import hashlib
import hmac


def verify_signature(payload: bytes, signature_header: str | None, secret: str | None) -> bool:
    """Verify a sha256 HMAC without revealing secret or provider payload details."""
    if not signature_header or not secret:
        return False
    supplied = signature_header.removeprefix("sha256=")
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)
