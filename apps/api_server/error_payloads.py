"""Shared error payload helpers for public API contract responses."""
from __future__ import annotations

from typing import Any


def access_scope_denied_error(
    message: str,
    *,
    docs_code: str = "access_scope_denied",
    details: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": "access_scope_denied",
        "message": message,
        "docs_url": f"https://docs.algenta.ai/errors/{docs_code}",
    }
    if details:
        error["details"] = details
    if extra:
        error.update(extra)
    return {"error": error}
