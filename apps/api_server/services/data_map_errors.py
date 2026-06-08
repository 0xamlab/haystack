from __future__ import annotations

from fastapi import HTTPException

from apps.api_server.schemas.common import ErrorDetail, ErrorResponse


class MojoInstrumentationError(RuntimeError):
    """Raised when strict runtime policy forbids degrading a Mojo profiling failure."""

    def __init__(self, engine_type: str, message: str) -> None:
        super().__init__(message)
        self.engine_type = engine_type


def http_error(
    status_code: int,
    *,
    code: str,
    message: str,
    details: list[tuple[str | None, str]] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse.make(
            code=code,
            message=message,
            details=[ErrorDetail(field=field, issue=issue) for field, issue in (details or [])],
        ).model_dump(mode="python"),
    )
