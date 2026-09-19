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
    json: dict[str, Any],
) -> Any:
    data = await client._request(method, path, json=json)
    return _validate_model(model_name, data)


async def product_decision(client: AsyncDecisionEngineClient, request: dict[str, Any]) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/decision",
        "ProductDecisionResult",
        json=request,
    )


async def product_agent_run(client: AsyncDecisionEngineClient, request: dict[str, Any]) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/agent/run",
        "ProductAgentRunResult",
        json=request,
    )


async def product_optimize(client: AsyncDecisionEngineClient, request: dict[str, Any]) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/optimize",
        "ProductOptimizeResult",
        json=request,
    )


async def product_retrieve(client: AsyncDecisionEngineClient, request: dict[str, Any]) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/retrieve",
        "ProductRetrieveResult",
        json=request,
    )


async def product_forecast(client: AsyncDecisionEngineClient, request: dict[str, Any]) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/forecast",
        "ProductForecastResult",
        json=request,
    )


__all__ = [
    "product_agent_run",
    "product_decision",
    "product_forecast",
    "product_optimize",
    "product_retrieve",
]
