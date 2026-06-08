from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .async_client_model_surface_common import _request_model
from .request_simulation_helpers import (
    _normalize_compare_request,
    _normalize_recommend_request,
    _normalize_simulation_request,
)

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient


async def simulate(client: AsyncDecisionEngineClient, **kwargs: Any) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/simulate",
        "DecisionEnvelope",
        json_body=_normalize_simulation_request(kwargs),
    )


async def recommend(
    client: AsyncDecisionEngineClient,
    actions: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    return await client._request(
        "POST",
        "/v1/recommend",
        json=_normalize_recommend_request(actions, **kwargs),
    )


async def score(
    client: AsyncDecisionEngineClient,
    request: dict[str, Any],
    scoring_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"request": request}
    if scoring_weights:
        body["scoring_weights"] = scoring_weights
    return await client._request("POST", "/v1/score", json=body)


async def batch(
    client: AsyncDecisionEngineClient,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    data = await client._request(
        "POST",
        "/v1/batch",
        json={"items": [_normalize_simulation_request(item) for item in items]},
    )
    return data.get("results", [])


async def compare(
    client: AsyncDecisionEngineClient,
    scenarios: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    return await client._request(
        "POST",
        "/v1/compare",
        json=_normalize_compare_request(scenarios, **kwargs),
    )


__all__ = ["batch", "compare", "recommend", "score", "simulate"]
