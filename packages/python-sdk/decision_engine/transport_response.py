# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from .exceptions import (
    AuthenticationError,
    DecisionEngineError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .transport_retry_policy import parse_retry_after_header


def parse_response_body(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        return {}


def _response_request_id(response: Any, error_body: dict[str, Any]) -> str | None:
    """Matches query_metadata_helpers._header_str's body-then-header precedence, so a
    request_id is available on the error path the same way it already is on the success path."""
    value = error_body.get("request_id") or response.headers.get("X-Request-Id")
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def handle_response(response: Any, *, auth_message: str) -> Any:
    body = parse_response_body(response)
    error_body = body if isinstance(body, dict) else {}

    if response.status_code in (200, 201, 202, 204):
        return body
    request_id = _response_request_id(response, error_body)
    if response.status_code == 401:
        raise AuthenticationError(
            error_body.get("error", {}).get("message", auth_message),
            status_code=401,
            response_body=body,
            request_id=request_id,
        )
    if response.status_code == 404:
        raise NotFoundError(
            error_body.get("error", {}).get("message", "Not found"),
            status_code=404,
            response_body=body,
            request_id=request_id,
        )
    if response.status_code == 422:
        raise ValidationError(
            error_body.get("error", {}).get("message", "Validation error"),
            status_code=422,
            response_body=body,
            request_id=request_id,
        )
    if response.status_code == 429:
        retry_after = parse_retry_after_header(response.headers.get("Retry-After"))
        raise RateLimitError(
            error_body.get("error", {}).get("message", "Rate limit exceeded"),
            retry_after=retry_after,
            status_code=429,
            response_body=body,
            request_id=request_id,
        )
    if response.status_code >= 500:
        raise ServerError(
            error_body.get("error", {}).get("message", "Server error"),
            status_code=response.status_code,
            response_body=body,
            request_id=request_id,
        )
    raise DecisionEngineError(
        f"Unexpected status {response.status_code}",
        status_code=response.status_code,
        response_body=body,
        request_id=request_id,
    )


__all__ = ["handle_response", "parse_response_body"]
