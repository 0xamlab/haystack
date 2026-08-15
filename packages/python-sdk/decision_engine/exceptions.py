"""SDK exception hierarchy."""

from typing import Any


class DecisionEngineError(Exception):
    """Base exception for all Algenta SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 0,
        response_body: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body or {}
        self.error_code = self.response_body.get("error", {}).get("code", "unknown_error")
        self.request_id = request_id or self.response_body.get("request_id")

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={str(self)!r}, "
            f"status_code={self.status_code}, "
            f"error_code={self.error_code!r}, "
            f"request_id={self.request_id!r})"
        )

    @property
    def details(self) -> Any:
        error = self.response_body.get("error", {})
        if not isinstance(error, dict):
            return None
        return error.get("details")

    @property
    def validation_errors(self) -> list[dict[str, Any]]:
        details = self.details
        if isinstance(details, list):
            return [item for item in details if isinstance(item, dict)]
        if isinstance(details, dict):
            validation_errors = details.get("validation_errors")
            if isinstance(validation_errors, list):
                return [item for item in validation_errors if isinstance(item, dict)]
        return []

    @property
    def field_errors(self) -> list[dict[str, Any]]:
        return self.validation_errors


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
    def field_errors(self) -> list[dict[str, Any]]:
        return super().field_errors


class NotFoundError(DecisionEngineError):
    """Raised on 404 — resource not found."""

    pass


class ServerError(DecisionEngineError):
    """Raised on 5xx — server-side error."""

    pass
