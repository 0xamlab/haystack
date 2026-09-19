# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .model_loader import validate_model as _validate_model

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient


async def _request_model(
    client: AsyncDecisionEngineClient,
    method: str,
    path: str,
    model_name: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> Any:
    request_kwargs = {"json": json_body} if json_body is not None else {}
    data = await client._request(method, path, **request_kwargs)
    return _validate_model(model_name, data)


__all__ = ["_request_model"]
