from __future__ import annotations

from typing import Any

from .model_loader import validate_model


def _header_str(response: Any, name: str) -> str | None:
    value = response.headers.get(name)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _header_int(response: Any, name: str) -> int | None:
    value = _header_str(response, name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _header_float(response: Any, name: str) -> float | None:
    value = _header_str(response, name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _header_bool(response: Any, name: str) -> bool | None:
    value = _header_str(response, name)
    if value is None:
        return None
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def build_query_execution_metadata(body: dict[str, Any], response: Any) -> Any:
    return validate_model(
        "QueryExecutionMetadata",
        {
            "request_id": body.get("request_id") or _header_str(response, "X-Request-Id"),
            "latency_ms": body.get("latency_ms") or _header_float(response, "X-Execution-Ms"),
            "tokens_in": _header_int(response, "X-Input-Tokens"),
            "tokens_out": _header_int(response, "X-Output-Tokens"),
            "cost_usd": _header_float(response, "X-Cost-Usd"),
            "cache_hit": _header_bool(response, "X-Cache-Hit"),
        },
    )


def response_headers_dict(response: Any) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in response.headers.items()}


__all__ = [
    "build_query_execution_metadata",
    "response_headers_dict",
]
