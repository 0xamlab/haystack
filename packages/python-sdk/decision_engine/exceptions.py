"""SDK exception hierarchy."""
from typing import Any


class DecisionEngineError(Exception):
    """Base exception for all Decision Engine SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 0,
        response_body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body or {}
        self.error_code = self.response_body.get("error", {}).get("code", "unknown_error")

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={str(self)!r}, "
            f"status_code={self.status_code}, "
            f"error_code={self.error_code!r})"
        )


class AuthenticationError(DecisionEngineError):
    """Raised on 401 — invalid or missing API key."""
    pass


class RateLimitError(DecisionEngineError):
    """Raised on 429 — quota or rate limit exceeded."""
    def __init__(self, message: str, retry_after: int = 60, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ValidationError(DecisionEngineError):
    """Raised on 422 — request validation failed."""
    @property
    def field_errors(self) -> list[dict[str, str]]:
        return self.response_body.get("error", {}).get("details", [])


class NotFoundError(DecisionEngineError):
    """Raised on 404 — resource not found."""
    pass


class ServerError(DecisionEngineError):
    """Raised on 5xx — server-side error."""
    pass
