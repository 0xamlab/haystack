from __future__ import annotations

from typing import Any, NoReturn

from algenta.runtime_errors import RuntimeValidationError


def inline_preview_error_code(exc: Exception) -> str | None:
    error_code = getattr(exc, "error_code", None)
    return error_code if isinstance(error_code, str) and error_code else None


def inline_preview_error_details(exc: Exception) -> dict[str, Any]:
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        return dict(details)
    body = getattr(exc, "response_body", {})
    if not isinstance(body, dict):
        return {}
    error = body.get("error")
    if not isinstance(error, dict):
        return {}
    details = error.get("details")
    return dict(details) if isinstance(details, dict) else {}


def should_fallback_to_ephemeral_preview(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code in {404, 405}


def raise_inline_preview_error(exc: Exception) -> NoReturn:
    error_code = inline_preview_error_code(exc)
    if error_code in {"connector_test_failed", "inline_preview_rate_limited"}:
        raise RuntimeValidationError(
            error_code,
            str(exc),
            inline_preview_error_details(exc),
        ) from exc
    raise exc


__all__ = [
    "inline_preview_error_code",
    "inline_preview_error_details",
    "raise_inline_preview_error",
    "should_fallback_to_ephemeral_preview",
]
