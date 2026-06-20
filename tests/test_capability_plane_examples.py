from __future__ import annotations

import json
from pathlib import Path

from apps.api_server.services.capability_plane import (
    CapabilityBindingCreateRequest,
    CapabilityBindingPreviewRequest,
    CapabilityExecutionRequest,
    CapabilityOutcomeRecordRequest,
    CapabilityRouteRequest,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_json(relative_path: str) -> dict[str, object]:
    payload = json.loads((ROOT / relative_path).read_text())
    assert isinstance(payload, dict)
    return payload


def test_capability_plane_example_requests_validate_against_real_models() -> None:
    CapabilityBindingCreateRequest.model_validate(
        _load_json("examples/capability-plane/binding_create_request.json")
    )
    CapabilityBindingPreviewRequest.model_validate(
        _load_json("examples/capability-plane/binding_discover_request.json")
    )
    CapabilityRouteRequest.model_validate(
        _load_json("examples/capability-plane/capability_route_request.json")
    )
    CapabilityExecutionRequest.model_validate(
        _load_json("examples/capability-plane/capability_execute_request.json")
    )
    CapabilityOutcomeRecordRequest.model_validate(
        _load_json("examples/capability-plane/capability_outcome_request.json")
    )


def test_capability_plane_examples_use_customer_agnostic_placeholders() -> None:
    readme = (ROOT / "examples/capability-plane/README.md").read_text()
    binding_create = _load_json("examples/capability-plane/binding_create_request.json")
    binding_discover = _load_json("examples/capability-plane/binding_discover_request.json")
    route = _load_json("examples/capability-plane/capability_route_request.json")
    execute = _load_json("examples/capability-plane/capability_execute_request.json")
    outcome = _load_json("examples/capability-plane/capability_outcome_request.json")

    assert "https://api.algenta.ai" in readme
    assert "Private profiles do not silently fall back to Algenta cloud." in readme
    assert "examples/capability-plane/capability_route_request.json" in readme
    assert "examples/capability-plane/capability_execute_request.json" in readme
    assert "Mission-specific" not in readme

    for payload in (binding_create, binding_discover, route, execute, outcome):
        serialized = json.dumps(payload, sort_keys=True).lower()
        assert "x-active-mcps" not in serialized
        assert "x-active-skills" not in serialized
        assert "mission-specific" not in serialized

    assert binding_create["provider_id"] == "provider.skill_pack.algenta"
    assert binding_discover["provider_id"] == "provider.skill_pack.algenta"
    assert route["provider_ids"] == [
        "provider.data_connector.algenta",
        "provider.mcp.generic",
        "provider.skill_pack.algenta",
        "provider.runtime_library_pack.algenta",
    ]
    assert execute["binding_id"] == "00000000-0000-0000-0000-000000000123"
    assert outcome["provider_id"] == "provider.skill_pack.algenta"


def test_langgraph_capability_router_example_uses_unified_capability_plane() -> None:
    text = (ROOT / "examples/langgraph/capability_router.py").read_text()
    normalized = " ".join(text.split())

    assert "client.route_capabilities(" in text
    assert "client.get_capability(" in text
    assert "client.execute_capability(" in text
    assert "Private profiles fail closed and do not silently fall back to Algenta cloud." in normalized
