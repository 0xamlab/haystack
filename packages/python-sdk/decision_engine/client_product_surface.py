from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .model_loader import validate_model as _validate_model

if TYPE_CHECKING:
    from .client_facade import DecisionEngineClient


def _request_model(
    client: DecisionEngineClient,
    method: str,
    path: str,
    model_name: str,
    *,
    json: dict[str, Any],
) -> Any:
    data = client._request(method, path, json=json)
    return _validate_model(model_name, data)


def product_decision(client: DecisionEngineClient, request: dict[str, Any]) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/decision",
        "ProductDecisionResult",
        json=request,
    )


def product_agent_run(client: DecisionEngineClient, request: dict[str, Any]) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/agent/run",
        "ProductAgentRunResult",
        json=request,
    )


def product_optimize(client: DecisionEngineClient, request: dict[str, Any]) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/optimize",
        "ProductOptimizeResult",
        json=request,
    )


def product_retrieve(client: DecisionEngineClient, request: dict[str, Any]) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/retrieve",
        "ProductRetrieveResult",
        json=request,
    )


def product_forecast(client: DecisionEngineClient, request: dict[str, Any]) -> Any:
    return _request_model(
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
