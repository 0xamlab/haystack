from __future__ import annotations

import json
from typing import Any


def _extract_error_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return error
    return {}


def _extract_error_code(payload: Any) -> str | None:
    error = _extract_error_payload(payload)
    code = error.get("code")
    if isinstance(code, str) and code:
        return code
    return None


def _extract_error_message(payload: Any) -> str | None:
    error = _extract_error_payload(payload)
    message = error.get("message")
    if isinstance(message, str) and message:
        return message
    return None


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.split()).lower()


def classify_simulation_capacity_blocker(
    *,
    status: int | None = None,
    payload: Any = None,
    text: str | None = None,
) -> str | None:
    code = _extract_error_code(payload)
    message = _extract_error_message(payload)
    normalized_text = _normalize_text(text)

    if status == 429 and code == "quota_exceeded":
        return message or "simulation quota exhausted"

    if status == 429 and code == "rate_limit_exceeded":
        return message or "simulation rate limit exceeded"

    if "quota_exceeded" in normalized_text or "monthly simulation quota exhausted" in normalized_text:
        return message or "simulation quota exhausted"

    if "rate_limit_exceeded" in normalized_text:
        return message or "simulation rate limit exceeded"

    return None


def parse_cli_error_payload(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None

    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        return parsed
    return None
