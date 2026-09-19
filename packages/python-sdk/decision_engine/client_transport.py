# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from .exceptions import (
    AuthenticationError,
    DecisionEngineError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .transport_retry_policy import (
    rate_limit_backoff_seconds,
    server_error_backoff_seconds,
    should_retry_rate_limit,
)

if TYPE_CHECKING:
    from .client_facade import DecisionEngineClient


def request_with_retries(
    client: DecisionEngineClient,
    method: str,
    path: str,
    *,
    return_response: bool = False,
    **kwargs: Any,
) -> dict[str, Any] | tuple[dict[str, Any], Any]:
    httpx = client._get_httpx_module()
    store_device_binding_token = getattr(client, "_store_device_binding_token", None)
    last_exc: Exception | None = None
    for attempt in range(client._max_retries + 1):
        try:
            response = client._client.request(method, path, **kwargs)
            if callable(store_device_binding_token):
                store_device_binding_token(response)
            body = client._handle_response(response)
            if return_response:
                return body, response
            return body
        except (AuthenticationError, ValidationError, NotFoundError):
            raise
        except RateLimitError as exc:
            if not should_retry_rate_limit(exc.error_code):
                raise
            if attempt >= client._max_retries:
                raise
            time.sleep(rate_limit_backoff_seconds(exc.retry_after, attempt=attempt))
            last_exc = exc
        except (ServerError, httpx.HTTPError) as exc:
            if attempt >= client._max_retries:
                raise
            time.sleep(server_error_backoff_seconds(attempt=attempt))
            last_exc = exc
    raise last_exc or DecisionEngineError("Request failed after retries")


def request_with_retries_and_response(
    client: DecisionEngineClient,
    method: str,
    path: str,
    **kwargs: Any,
) -> tuple[dict[str, Any], Any]:
    response = request_with_retries(
        client,
        method,
        path,
        return_response=True,
        **kwargs,
    )
    assert isinstance(response, tuple)
    return response


__all__ = ["request_with_retries", "request_with_retries_and_response"]
