"""Shared Pydantic schemas used across all endpoints."""
from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Individual field-level error detail."""
    model_config = ConfigDict(strict=True)

    field: str | None = Field(None, description="Field path that caused the error")
    issue: str = Field(..., description="Human-readable description of the issue")


class ErrorResponse(BaseModel):
    """Standard error envelope returned on all 4xx/5xx responses."""
    model_config = ConfigDict(strict=True)

    class ErrorBody(BaseModel):
        code: str = Field(..., description="Snake_case error code")
        message: str = Field(..., description="Human-readable error message")
        details: list[ErrorDetail] = Field(default_factory=list)
        request_id: str | None = Field(None, description="Correlation ID from request")
        docs_url: str | None = Field(
            None, description="Link to documentation explaining this error"
        )

    error: ErrorBody

    @classmethod
    def make(
        cls,
        code: str,
        message: str,
        request_id: str | None = None,
        details: list[ErrorDetail] | None = None,
        docs_url: str | None = None,
    ) -> "ErrorResponse":
        base_url = "https://docs.algenta.ai/errors"
        return cls(
            error=cls.ErrorBody(
                code=code,
                message=message,
                request_id=request_id,
                details=details or [],
                docs_url=docs_url or f"{base_url}/{code}",
            )
        )


class PaginationMeta(BaseModel):
    """Pagination metadata for list endpoints."""
    total: int
    page: int
    per_page: int
    pages: int
