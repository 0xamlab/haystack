# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .client_model_surface_common import _request_model
from .request_simulation_helpers import (
    _normalize_compare_request,
    _normalize_recommend_request,
    _normalize_simulation_request,
)

if TYPE_CHECKING:
    from .client_facade import DecisionEngineClient


def simulate(client: DecisionEngineClient, **kwargs: Any) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/simulate",
        "DecisionEnvelope",
        json_body=_normalize_simulation_request(kwargs),
    )


def recommend(client: DecisionEngineClient, actions: Any, **kwargs: Any) -> dict[str, Any]:
    return client._request(
        "POST",
        "/v1/recommend",
        json=_normalize_recommend_request(actions, **kwargs),
    )


def score(
    client: DecisionEngineClient,
    request: dict[str, Any],
    scoring_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"request": request}
    if scoring_weights:
        body["scoring_weights"] = scoring_weights
    return client._request("POST", "/v1/score", json=body)


def batch(client: DecisionEngineClient, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    data = client._request(
        "POST",
        "/v1/batch",
        json={"items": [_normalize_simulation_request(item) for item in items]},
    )
    return data.get("results", [])


def compare(client: DecisionEngineClient, scenarios: Any, **kwargs: Any) -> dict[str, Any]:
    return client._request(
        "POST",
        "/v1/compare",
        json=_normalize_compare_request(scenarios, **kwargs),
    )


__all__ = ["batch", "compare", "recommend", "score", "simulate"]
