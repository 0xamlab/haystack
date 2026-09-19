# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from .model_loader import validate_model as _validate_model
from .model_loader import validate_model_list as _validate_model_list


def _append_repeated_params(
    params: list[tuple[str, str]],
    key: str,
    values: list[str] | tuple[str, ...] | None,
) -> None:
    if not values:
        return
    for value in values:
        params.append((key, value))


async def list_capability_providers(client: Any):
    data = await client._request("GET", "/v1/capability-providers")
    return _validate_model_list("CapabilityProviderResult", data)


async def get_capability_provider(client: Any, provider_id: str):
    data = await client._request("GET", f"/v1/capability-providers/{provider_id}")
    return _validate_model("CapabilityProviderResult", data)


async def list_capability_bindings(
    client: Any,
    *,
    provider_id: str | None = None,
    scope: str | None = None,
):
    params: dict[str, str] = {}
    if provider_id:
        params["provider_id"] = provider_id
    if scope:
        params["scope"] = scope
    data = await client._request("GET", "/v1/capability-bindings", params=params or None)
    return _validate_model_list("CapabilityBindingResult", data)


async def create_capability_binding(client: Any, request: dict[str, Any]):
    data = await client._request("POST", "/v1/capability-bindings", json=request)
    return _validate_model("CapabilityBindingResult", data)


async def get_capability_binding(client: Any, binding_id: str):
    data = await client._request("GET", f"/v1/capability-bindings/{binding_id}")
    return _validate_model("CapabilityBindingResult", data)


async def update_capability_binding(client: Any, binding_id: str, request: dict[str, Any]):
    data = await client._request("PATCH", f"/v1/capability-bindings/{binding_id}", json=request)
    return _validate_model("CapabilityBindingResult", data)


async def delete_capability_binding(client: Any, binding_id: str) -> None:
    await client._request("DELETE", f"/v1/capability-bindings/{binding_id}")


async def preview_test_capability_binding(client: Any, request: dict[str, Any]):
    data = await client._request("POST", "/v1/capability-bindings/test", json=request)
    return _validate_model("CapabilityBindingTestResult", data)


async def test_capability_binding(client: Any, binding_id: str):
    data = await client._request("POST", f"/v1/capability-bindings/{binding_id}/test")
    return _validate_model("CapabilityBindingTestResult", data)


async def preview_discover_capability_binding(client: Any, request: dict[str, Any]):
    data = await client._request("POST", "/v1/capability-bindings/discover", json=request)
    return _validate_model("CapabilityDiscoverResult", data)


async def discover_capability_binding(client: Any, binding_id: str):
    data = await client._request("POST", f"/v1/capability-bindings/{binding_id}/discover")
    return _validate_model("CapabilityDiscoverResult", data)


async def start_capability_authorization(client: Any, binding_id: str, request: dict[str, Any]):
    data = await client._request(
        "POST",
        f"/v1/capability-bindings/{binding_id}/authorize/start",
        json=request,
    )
    return _validate_model("CapabilityAuthorizationStartResult", data)


async def complete_capability_authorization(client: Any, binding_id: str, request: dict[str, Any]):
    data = await client._request(
        "POST",
        f"/v1/capability-bindings/{binding_id}/authorize/complete",
        json=request,
    )
    return _validate_model("CapabilityAuthorizationCompleteResult", data)


async def list_capabilities(
    client: Any,
    *,
    kinds: list[str] | tuple[str, ...] | None = None,
    provider_ids: list[str] | tuple[str, ...] | None = None,
    binding_ids: list[str] | tuple[str, ...] | None = None,
):
    params: list[tuple[str, str]] = []
    _append_repeated_params(params, "kinds", kinds)
    _append_repeated_params(params, "provider_ids", provider_ids)
    _append_repeated_params(params, "binding_ids", binding_ids)
    data = await client._request("GET", "/v1/capabilities", params=params or None)
    return _validate_model_list("CapabilityCatalogEntryResult", data)


async def get_capability(
    client: Any,
    capability_id: str,
    *,
    include_instruction: bool = False,
):
    params = {"include_instruction": "1"} if include_instruction else None
    data = await client._request("GET", f"/v1/capabilities/{capability_id}", params=params)
    return _validate_model("CapabilityCatalogEntryResult", data)


async def route_capabilities(client: Any, request: dict[str, Any]):
    data = await client._request("POST", "/v1/capabilities/route", json=request)
    return _validate_model("CapabilityRoutePlanResult", data)


async def execute_capability(client: Any, request: dict[str, Any]):
    data = await client._request("POST", "/v1/capabilities/execute", json=request)
    return _validate_model("CapabilityExecutionResult", data)


async def record_capability_outcome(client: Any, request: dict[str, Any]):
    data = await client._request("POST", "/v1/capabilities/outcomes", json=request)
    return _validate_model("CapabilityOutcomeRecordResult", data)


async def list_skills(client: Any):
    return await list_capabilities(client, kinds=["skill"])


async def enable_skill(
    client: Any,
    *,
    skill_name: str,
    instruction: str,
    description: str | None = None,
    tags: list[str] | None = None,
    artifact_affinities: list[str] | None = None,
    execution_owner: str = "client_managed",
):
    binding = await create_capability_binding(
        client,
        {
            "provider_id": "provider.skill_pack.algenta",
            "profile_id": "profile.skill_pack.user",
            "binding_name": skill_name,
            "scope": "user",
            "execution_owner": execution_owner,
            "config": {
                "manifest": {
                    "capabilities": [
                        {
                            "capability_id": f"cap.skill.{skill_name.lower().replace(' ', '_')}",
                            "name": skill_name,
                            "description": description,
                            "kind": "skill",
                            "implementation_kind": "instruction_only",
                            "execution_owner": execution_owner,
                            "instruction": instruction,
                            "artifact_affinities": artifact_affinities or [],
                            "tags": tags or [],
                            "replayability": "deterministic",
                        }
                    ]
                }
            },
        },
    )
    return await discover_capability_binding(client, binding.binding_id)


async def disable_skill(client: Any, binding_id: str) -> None:
    await delete_capability_binding(client, binding_id)


async def list_mcp_providers(client: Any):
    return [
        provider
        for provider in await list_capability_providers(client)
        if provider.provider_type == "mcp_provider"
    ]


__all__ = [
    "list_capability_providers",
    "get_capability_provider",
    "list_capability_bindings",
    "create_capability_binding",
    "get_capability_binding",
    "update_capability_binding",
    "delete_capability_binding",
    "preview_test_capability_binding",
    "test_capability_binding",
    "preview_discover_capability_binding",
    "discover_capability_binding",
    "start_capability_authorization",
    "complete_capability_authorization",
    "list_capabilities",
    "get_capability",
    "route_capabilities",
    "execute_capability",
    "record_capability_outcome",
    "list_skills",
    "enable_skill",
    "disable_skill",
    "list_mcp_providers",
]
