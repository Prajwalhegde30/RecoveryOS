from __future__ import annotations


class ProviderError(Exception):
    """Safe, typed integration failure that never carries raw provider payloads."""

    def __init__(self, category: str, safe_message: str, *, retryable: bool) -> None:
        super().__init__(safe_message)
        self.category = category
        self.safe_message = safe_message
        self.retryable = retryable


class ProviderTimeoutError(ProviderError):
    def __init__(self, provider: str) -> None:
        super().__init__(f"{provider}_timeout", f"{provider} did not respond", retryable=True)


class ProviderTransportError(ProviderError):
    def __init__(self, provider: str) -> None:
        super().__init__(
            f"{provider}_transport_error", f"{provider} request failed", retryable=True
        )


class ProviderRateLimitError(ProviderError):
    def __init__(self, provider: str) -> None:
        super().__init__(
            f"{provider}_rate_limited", f"{provider} rate limit reached", retryable=True
        )


class ProviderResponseError(ProviderError):
    def __init__(self, provider: str) -> None:
        super().__init__(
            f"{provider}_invalid_response",
            f"{provider} returned an invalid response",
            retryable=False,
        )


class ProviderAmbiguousError(ProviderError):
    def __init__(self, provider: str) -> None:
        super().__init__(
            f"{provider}_ambiguous_result",
            f"{provider} result requires reconciliation before retry",
            retryable=True,
        )
