from __future__ import annotations

from typing import Any

from pydantic import ValidationError as PydanticValidationError


def _format_validation_error_path(location: tuple[Any, ...]) -> str:
    return ".".join(str(item) for item in location if str(item))


def build_validation_error_details(exc: Exception) -> dict[str, Any]:
    if not isinstance(exc, PydanticValidationError):
        return {"cause": str(exc)}
    try:
        errors = exc.errors(include_url=False, include_context=False, include_input=False)
    except TypeError:  # pragma: no cover - compatibility guard
        errors = exc.errors()
    normalized_errors: list[dict[str, str]] = []
    for error in errors:
        path = _format_validation_error_path(tuple(error.get("loc") or ()))
        normalized_errors.append(
            {
                "path": path,
                "message": str(error.get("msg", "Invalid value")),
                "type": str(error.get("type", "validation_error")),
            }
        )
    cause = next((item["path"] for item in normalized_errors if item["path"]), str(exc))
    details: dict[str, Any] = {"cause": cause}
    if normalized_errors:
        details["validation_errors"] = normalized_errors
    return details


def format_validation_error_message(prefix: str, exc: Exception) -> str:
    details = build_validation_error_details(exc)
    cause = details.get("cause")
    if isinstance(cause, str) and cause:
        normalized_prefix = prefix[:-1] if prefix.endswith(".") else prefix
        return f"{normalized_prefix}: {cause}"
    return prefix


__all__ = ["build_validation_error_details", "format_validation_error_message"]
