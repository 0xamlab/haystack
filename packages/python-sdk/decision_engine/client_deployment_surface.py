# SPDX-License-Identifier: Apache-2.0

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
    json: dict[str, Any] | None = None,
) -> Any:
    data = client._request(method, path, json=json)
    return _validate_model(model_name, data)


def list_deployment_regions(client: DecisionEngineClient) -> Any:
    return _request_model(client, "GET", "/v1/deployments/regions", "DeploymentRegionsResult")


def get_deployment(client: DecisionEngineClient) -> Any:
    data = client._request("GET", "/v1/deployments")
    if data is None:
        return None
    return _validate_model("DeploymentResult", data)


def create_deployment(
    client: DecisionEngineClient,
    *,
    provider: str = "algenta_shared",
    region: str = "algenta-shared",
    config: dict[str, Any] | None = None,
    billing_markup_pct: float = 20.0,
) -> Any:
    if not isinstance(provider, str) or not provider.strip():
        raise ValueError("provider must be a non-empty string.")
    if not isinstance(region, str) or not region.strip():
        raise ValueError("region must be a non-empty string.")
    if config is not None and not isinstance(config, dict):
        raise TypeError("config must be a mapping or None.")
    if isinstance(billing_markup_pct, bool) or not isinstance(billing_markup_pct, (int, float)):
        raise TypeError("billing_markup_pct must be a number.")
    payload = {
        "provider": provider,
        "region": region,
        "config": config,
        "billing_markup_pct": float(billing_markup_pct),
    }
    return _request_model(
        client,
        "POST",
        "/v1/deployments",
        "DeploymentResult",
        json=payload,
    )


def delete_deployment(client: DecisionEngineClient, deployment_id: str) -> Any:
    if not isinstance(deployment_id, str) or not deployment_id.strip():
        raise ValueError("deployment_id must be a non-empty string.")
    return _request_model(
        client,
        "DELETE",
        f"/v1/deployments/{deployment_id}",
        "DeploymentDeleteResult",
    )


def get_deployment_cost(client: DecisionEngineClient, deployment_id: str) -> Any:
    if not isinstance(deployment_id, str) or not deployment_id.strip():
        raise ValueError("deployment_id must be a non-empty string.")
    return _request_model(
        client,
        "GET",
        f"/v1/deployments/{deployment_id}/cost",
        "DeploymentCostResult",
    )


__all__ = [
    "create_deployment",
    "delete_deployment",
    "get_deployment",
    "get_deployment_cost",
    "list_deployment_regions",
]
