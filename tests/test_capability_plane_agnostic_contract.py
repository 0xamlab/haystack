from __future__ import annotations

import json

from apps.platform_contract import load_platform_contract


def test_capability_plane_contract_is_customer_agnostic_and_canonical() -> None:
    contract = load_platform_contract()
    capability_plane = contract.capability_plane

    assert capability_plane is not None
    assert capability_plane["api"]["list_providers_endpoint"] == "/v1/capability-providers"
    assert capability_plane["api"]["route_capabilities_endpoint"] == "/v1/capabilities/route"
    assert capability_plane["direct_sdk"]["typescript"]["list_providers_method"] == (
        "listCapabilityProviders"
    )
    assert capability_plane["runtime_sdk"]["typescript"]["register_adapter_method"] == (
        "registerCapabilityAdapter"
    )
    assert capability_plane["mcp"]["list_providers_tool"] == "list_capability_providers"
    assert capability_plane["enums"]["provider_types"] == [
        "data_connector",
        "mcp_provider",
        "skill_pack",
        "native_tool_pack",
        "runtime_library_pack",
    ]
    assert capability_plane["enums"]["capability_kinds"] == [
        "dataset",
        "mcp_tool",
        "mcp_resource",
        "mcp_prompt",
        "skill",
        "native_tool",
        "runtime_library",
    ]
    assert capability_plane["enums"]["execution_owners"] == [
        "algenta_managed",
        "client_managed",
    ]

    serialized = json.dumps(capability_plane, sort_keys=True).lower()
    assert "mission" not in serialized
    assert "x-active-mcps" not in serialized
    assert "x-active-skills" not in serialized
