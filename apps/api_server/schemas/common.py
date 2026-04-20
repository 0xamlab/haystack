"""Shared Pydantic schemas used across all endpoints."""
from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    model_config = ConfigDict(strict=True)
    field: str | None = Field(None, description="Field path that caused the error")
    issue: str = Field(..., description="Human-readable description of the issue")


class ErrorResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    class ErrorBody(BaseModel):
        code: str
        message: str
        details: list[ErrorDetail] = Field(default_factory=list)
        request_id: str | None = None
        docs_url: str | None = None

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
    total: int
    page: int
    per_page: int
    pages: int
