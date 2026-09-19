# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from collections.abc import AsyncIterable, AsyncIterator
from typing import TYPE_CHECKING, Any

from .exceptions import DecisionEngineError
from .model_loader import validate_model as _validate_model

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient


def _invalid_stream_error(
    *, code: str, message: str, details: dict[str, Any]
) -> DecisionEngineError:
    return DecisionEngineError(
        message,
        response_body={"error": {"code": code, "message": message, "details": details}},
    )


async def _iter_sse_payloads(lines: AsyncIterable[str]) -> AsyncIterator[Any]:
    buffered_data: list[str] = []
    async for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if not line:
            if not buffered_data:
                continue
            payload_text = "\n".join(buffered_data)
            buffered_data.clear()
            if payload_text == "[DONE]":
                return
            try:
                yield json.loads(payload_text)
            except json.JSONDecodeError as exc:
                raise _invalid_stream_error(
                    code="invalid_sse_event",
                    message="Received invalid JSON in Server-Sent Events payload.",
                    details={"payload": payload_text},
                ) from exc
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            buffered_data.append(line[5:].lstrip())
    if buffered_data:
        payload_text = "\n".join(buffered_data)
        if payload_text == "[DONE]":
            return
        try:
            yield json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise _invalid_stream_error(
                code="invalid_sse_event",
                message="Received invalid JSON in trailing Server-Sent Events payload.",
                details={"payload": payload_text},
            ) from exc


async def _stream_model(
    client: AsyncDecisionEngineClient,
    method: str,
    path: str,
    model_name: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> AsyncIterator[Any]:
    request_kwargs: dict[str, Any] = {
        "headers": {"Accept": "text/event-stream"},
    }
    if json_body is not None:
        request_kwargs["json"] = json_body
    async with client._client.stream(method, path, **request_kwargs) as response:
        client._store_device_binding_token(response)
        if not 200 <= response.status_code < 300:
            client._handle_response(response)
            raise _invalid_stream_error(
                code="stream_request_failed",
                message="Streaming request failed without a structured API error.",
                details={"status_code": response.status_code},
            )
        content_type = str(response.headers.get("content-type", ""))
        if "text/event-stream" not in content_type:
            raise _invalid_stream_error(
                code="invalid_stream_content_type",
                message="Expected text/event-stream response for streaming request.",
                details={"content_type": content_type},
            )
        async for payload in _iter_sse_payloads(response.aiter_lines()):
            yield _validate_model(model_name, payload)


__all__ = ["_stream_model"]
