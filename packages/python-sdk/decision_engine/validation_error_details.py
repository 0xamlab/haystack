from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError as PydanticValidationError


_VALIDATION_ERROR_PREFIX = re.compile(r"^(?P<path>[A-Za-z0-9_.\[\]-]+)(?::|\s)(?P<message>.+)$")
_KNOWN_PYDANTIC_ERROR_PREFIXES = (
    "Value error, ",
    "Value error: ",
    "Assertion failed, ",
    "Assertion failed: ",
)


def _format_validation_error_path(location: tuple[Any, ...]) -> str:
    parts: list[str] = []
    for item in location:
        parts.append(str(item))
    return ".".join(part for part in parts if part)


def build_validation_error_details(exc: Exception) -> dict[str, Any]:
    if not isinstance(exc, PydanticValidationError):
        return _build_prefixed_error_details(str(exc))
    try:
        errors = exc.errors(include_url=False, include_context=False, include_input=False)
    except TypeError:  # pragma: no cover - compatibility guard
        errors = exc.errors()
    normalized_errors: list[dict[str, str]] = []
    for error in errors:
        path = _format_validation_error_path(tuple(error.get("loc") or ()))
        message = str(error.get("msg", "Invalid value"))
        if not path:
            prefixed = _build_prefixed_error_details(message)
            prefixed_path = prefixed.get("cause")
            if isinstance(prefixed_path, str) and prefixed_path != message:
                normalized_errors.append(
                    {
                        "path": prefixed_path,
                        "message": str(
                            prefixed.get("validation_errors", [{}])[0].get(
                                "message",
                                message,
                            )
                        ),
                        "type": str(error.get("type", "validation_error")),
                    }
                )
                continue
        normalized_errors.append(
            {
                "path": path,
                "message": message,
                "type": str(error.get("type", "validation_error")),
            }
        )
    cause = next((item["path"] for item in normalized_errors if item["path"]), str(exc))
    details: dict[str, Any] = {"cause": cause}
    if normalized_errors:
        details["validation_errors"] = normalized_errors
    return details


def _build_prefixed_error_details(message: str) -> dict[str, Any]:
    normalized_message = message
    for prefix in _KNOWN_PYDANTIC_ERROR_PREFIXES:
        if normalized_message.startswith(prefix):
            normalized_message = normalized_message[len(prefix) :]
            break
    match = _VALIDATION_ERROR_PREFIX.match(normalized_message)
    if not match:
        return {"cause": message}
    path = match.group("path")
    detail = match.group("message").strip()
    if not path or not detail:
        return {"cause": message}
    return {
        "cause": path,
        "validation_errors": [
            {
                "path": path,
                "message": detail,
                "type": "value_error",
            }
        ],
    }


__all__ = ["build_validation_error_details"]
