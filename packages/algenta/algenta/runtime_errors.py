from __future__ import annotations

from typing import Any


class CodnaRuntimeError(Exception):
    """Base error for the Runtime facade."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def to_error(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": str(self), "details": self.details}}

    @staticmethod
    def _normalize_validation_errors(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    @property
    def validation_errors(self) -> list[dict[str, Any]]:
        details = self.details
        if not isinstance(details, dict):
            return []
        direct_errors = self._normalize_validation_errors(details.get("validation_errors"))
        if direct_errors:
            return direct_errors
        source_error_details = details.get("source_error_details")
        if not isinstance(source_error_details, dict):
            return []
        return self._normalize_validation_errors(source_error_details.get("validation_errors"))

    @property
    def field_errors(self) -> list[dict[str, Any]]:
        return self.validation_errors


AlgentaRuntimeError = CodnaRuntimeError


class RuntimeConfigurationError(CodnaRuntimeError):
    """Raised when the runtime is not configured for the requested mode."""


class RuntimeValidationError(CodnaRuntimeError):
    """Raised when the runtime request is invalid or not executable."""
