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
    json: dict[str, Any] | None = None,
) -> Any:
    data = await client._request(method, path, json=json)
    return _validate_model(model_name, data)


async def list_deployment_regions(client: AsyncDecisionEngineClient) -> Any:
    return await _request_model(client, "GET", "/v1/deployments/regions", "DeploymentRegionsResult")


async def get_deployment(client: AsyncDecisionEngineClient) -> Any:
    data = await client._request("GET", "/v1/deployments")
    if data is None:
        return None
    return _validate_model("DeploymentResult", data)


async def create_deployment(
    client: AsyncDecisionEngineClient,
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
    return await _request_model(
        client,
        "POST",
        "/v1/deployments",
        "DeploymentResult",
        json=payload,
    )


async def delete_deployment(client: AsyncDecisionEngineClient, deployment_id: str) -> Any:
    if not isinstance(deployment_id, str) or not deployment_id.strip():
        raise ValueError("deployment_id must be a non-empty string.")
    return await _request_model(
        client,
        "DELETE",
        f"/v1/deployments/{deployment_id}",
        "DeploymentDeleteResult",
    )


async def get_deployment_cost(client: AsyncDecisionEngineClient, deployment_id: str) -> Any:
    if not isinstance(deployment_id, str) or not deployment_id.strip():
        raise ValueError("deployment_id must be a non-empty string.")
    return await _request_model(
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
