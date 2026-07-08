from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

pytestmark = pytest.mark.anyio

decision_engine = importlib.import_module("decision_engine")
algenta = importlib.import_module("algenta")

AsyncDecisionEngineClient = decision_engine.AsyncDecisionEngineClient
CapabilityAuthorizationCompleteResult = decision_engine.CapabilityAuthorizationCompleteResult
CapabilityAuthorizationStartResult = decision_engine.CapabilityAuthorizationStartResult
CapabilityBindingResult = decision_engine.CapabilityBindingResult
CapabilityBindingTestResult = decision_engine.CapabilityBindingTestResult
CapabilityCatalogEntryResult = decision_engine.CapabilityCatalogEntryResult
CapabilityDiscoverResult = decision_engine.CapabilityDiscoverResult
CapabilityExecutionResult = decision_engine.CapabilityExecutionResult
CapabilityOutcomeRecordResult = decision_engine.CapabilityOutcomeRecordResult
CapabilityProviderResult = decision_engine.CapabilityProviderResult
CapabilityRoutePlanResult = decision_engine.CapabilityRoutePlanResult
DecisionEngineClient = decision_engine.DecisionEngineClient

AlgentaClient = algenta.AlgentaClient


def _provider_payload() -> dict[str, Any]:
    return {
        "provider_id": "provider.skill_pack.algenta",
        "provider_type": "skill_pack",
        "name": "Skill Pack",
        "description": "Prompt skills.",
        "supported_execution_owners": ["algenta_managed", "client_managed"],
        "active": True,
        "profiles": [
            {
                "profile_id": "profile.skill_pack.user",
                "provider_id": "provider.skill_pack.algenta",
                "name": "User Skills",
                "description": "User-scoped instruction skills.",
                "auth_kind": "none",
                "default_execution_owner": "client_managed",
                "binding_scope_default": "user",
                "supported_binding_scopes": ["user"],
            }
        ],
    }


def _binding_payload() -> dict[str, Any]:
    return {
        "binding_id": "binding-123",
        "provider_id": "provider.skill_pack.algenta",
        "profile_id": "profile.skill_pack.user",
        "binding_name": "Escalation Skill",
        "scope": "user",
        "scope_ref": "user-123",
        "status": "ready",
        "execution_owner": "client_managed",
        "config": {"manifest": {"capabilities": []}},
        "customer_metadata": {"tier": "test"},
        "system_managed": False,
        "last_tested_at": "2026-05-29T12:00:00Z",
        "last_discovered_at": "2026-05-29T12:05:00Z",
        "authorized_at": None,
        "quarantine_reason": None,
        "discovery_error_message": None,
        "test_error_message": None,
        "created_at": "2026-05-29T11:00:00Z",
        "updated_at": "2026-05-29T12:05:00Z",
    }


def _catalog_entry_payload() -> dict[str, Any]:
    return {
        "capability_id": "cap.skill.escalation",
        "provider_id": "provider.skill_pack.algenta",
        "profile_id": "profile.skill_pack.user",
        "binding_id": "binding-123",
        "kind": "skill",
        "name": "Escalation Skill",
        "description": "Escalates incidents.",
        "implementation_kind": "instruction_only",
        "execution_owner": "client_managed",
        "input_schema_ref": "capability.input.none",
        "output_schema_ref": "capability.output.skill_instruction",
        "side_effect_class": "read_only",
        "risk_level": "low",
        "required_policy": "capability_plane.default",
        "replayability": "deterministic",
        "approval_required": False,
        "trust_tier": "workspace",
        "manifest_hash": "hash-123",
        "artifact_affinities": ["incident"],
        "tags": ["skill", "incident"],
        "required_binding_ids": ["binding-123"],
        "selected_tool_name": None,
        "instruction_artifact_ref": "artifact://skills/escalation",
        "binding_status": "ready",
        "discovered_at": "2026-05-29T12:05:00Z",
        "customer_metadata": None,
        "instruction_text": "Escalate to the on-call incident commander.",
    }


def _discover_payload() -> dict[str, Any]:
    return {
        "binding_id": "binding-123",
        "provider_id": "provider.skill_pack.algenta",
        "profile_id": "profile.skill_pack.user",
        "snapshot_id": "snapshot-123",
        "binding_status": "ready",
        "manifest_hash": "hash-123",
        "capability_count": 1,
        "discovered_at": "2026-05-29T12:05:00Z",
        "message": "Discovered 1 capability.",
        "capabilities": [_catalog_entry_payload()],
    }


def _route_plan_payload() -> dict[str, Any]:
    return {
        "selected_capability_id": "cap.skill.escalation",
        "selected_provider_id": "provider.skill_pack.algenta",
        "selected_binding_id": "binding-123",
        "kind": "skill",
        "execution_owner": "client_managed",
        "requires_approval": False,
        "confidence": 0.94,
        "reason": "Exact skill match for escalation objective.",
        "fallbacks": [],
        "policy_snapshot_id": "capability-plane-policy-v1",
        "instruction_artifact_ref": "artifact://skills/escalation",
    }


def _execution_payload() -> dict[str, Any]:
    return {
        "execution_session_id": "exec-123",
        "capability_id": "cap.skill.escalation",
        "provider_id": "provider.skill_pack.algenta",
        "binding_id": "binding-123",
        "execution_owner": "client_managed",
        "status": "succeeded",
        "output": {"instruction_text": "Escalate to the on-call incident commander."},
        "error": None,
        "started_at": "2026-05-29T12:06:00Z",
        "completed_at": "2026-05-29T12:06:01Z",
    }


def _outcome_payload() -> dict[str, Any]:
    return {
        "outcome_id": "outcome-123",
        "capability_id": "cap.skill.escalation",
        "provider_id": "provider.skill_pack.algenta",
        "binding_id": "binding-123",
        "success": True,
        "result_status": "completed",
        "confidence": 0.91,
        "latency_ms": 125,
        "error_code": None,
        "details": {"source": "test"},
        "created_at": "2026-05-29T12:06:02Z",
    }


def _binding_test_payload() -> dict[str, Any]:
    return {
        "success": True,
        "binding_status": "ready",
        "message": "Binding is healthy.",
        "latency_ms": 12,
        "details": {"mode": "preview"},
    }


def _authorization_start_payload() -> dict[str, Any]:
    return {
        "session_id": "auth-session-123",
        "binding_id": "binding-123",
        "provider_id": "provider.skill_pack.algenta",
        "authorize_url": "https://customer.example.com/oauth/start",
        "expires_at": "2026-05-29T13:00:00Z",
        "requested_scopes": ["skills.read"],
    }


def _authorization_complete_payload() -> dict[str, Any]:
    return {
        "session_id": "auth-session-123",
        "binding_id": "binding-123",
        "provider_id": "provider.skill_pack.algenta",
        "status": "completed",
        "authorized_at": "2026-05-29T12:15:00Z",
    }


def test_sync_client_capability_plane_methods_return_typed_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = DecisionEngineClient(api_key="de_test_capability", base_url="https://example.test")
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        calls.append((method, path, kwargs))
        if (method, path) == ("GET", "/v1/capability-providers"):
            return [_provider_payload()]
        if (method, path) == ("GET", "/v1/capability-providers/provider.skill_pack.algenta"):
            return _provider_payload()
        if (method, path) == ("GET", "/v1/capability-bindings"):
            return [_binding_payload()]
        if (method, path) == ("POST", "/v1/capability-bindings"):
            return _binding_payload()
        if (method, path) == ("GET", "/v1/capability-bindings/binding-123"):
            return _binding_payload()
        if (method, path) == ("PATCH", "/v1/capability-bindings/binding-123"):
            return {**_binding_payload(), "binding_name": kwargs["json"]["binding_name"]}
        if (method, path) == ("POST", "/v1/capability-bindings/test"):
            return _binding_test_payload()
        if (method, path) == ("POST", "/v1/capability-bindings/binding-123/test"):
            return _binding_test_payload()
        if (method, path) == ("POST", "/v1/capability-bindings/discover"):
            return _discover_payload()
        if (method, path) == ("POST", "/v1/capability-bindings/binding-123/discover"):
            return _discover_payload()
        if (method, path) == ("POST", "/v1/capability-bindings/binding-123/authorize/start"):
            return _authorization_start_payload()
        if (method, path) == ("POST", "/v1/capability-bindings/binding-123/authorize/complete"):
            return _authorization_complete_payload()
        if (method, path) == ("GET", "/v1/capabilities"):
            return [_catalog_entry_payload()]
        if (method, path) == ("GET", "/v1/capabilities/cap.skill.escalation"):
            return _catalog_entry_payload()
        if (method, path) == ("POST", "/v1/capabilities/route"):
            return _route_plan_payload()
        if (method, path) == ("POST", "/v1/capabilities/execute"):
            return _execution_payload()
        if (method, path) == ("POST", "/v1/capabilities/outcomes"):
            return _outcome_payload()
        if (method, path) == ("DELETE", "/v1/capability-bindings/binding-123"):
            return {}
        raise AssertionError((method, path, kwargs))

    monkeypatch.setattr(client, "_request", fake_request)

    providers = client.list_capability_providers()
    provider = client.get_capability_provider("provider.skill_pack.algenta")
    bindings = client.list_capability_bindings(provider_id="provider.skill_pack.algenta", scope="user")
    created = client.create_capability_binding({"binding_name": "Escalation Skill"})
    fetched = client.get_capability_binding("binding-123")
    updated = client.update_capability_binding("binding-123", {"binding_name": "Escalation v2"})
    preview_test = client.preview_test_capability_binding({"provider_id": "provider.skill_pack.algenta"})
    saved_test = client.test_capability_binding("binding-123")
    preview_discover = client.preview_discover_capability_binding({"provider_id": "provider.skill_pack.algenta"})
    discovered = client.discover_capability_binding("binding-123")
    auth_started = client.start_capability_authorization("binding-123", {"requested_scopes": ["skills.read"]})
    auth_completed = client.complete_capability_authorization("binding-123", {"session_id": "auth-session-123"})
    capabilities = client.list_capabilities(kinds=["skill"], provider_ids=["provider.skill_pack.algenta"], binding_ids=["binding-123"])
    capability = client.get_capability("cap.skill.escalation", include_instruction=True)
    route = client.route_capabilities({"objective": "Escalate incident", "kinds": ["skill"]})
    execution = client.execute_capability({"capability_id": "cap.skill.escalation"})
    outcome = client.record_capability_outcome({"capability_id": "cap.skill.escalation", "provider_id": "provider.skill_pack.algenta"})
    skills = client.list_skills()
    mcp_providers = client.list_mcp_providers()
    client.disable_skill("binding-123")

    assert isinstance(providers[0], CapabilityProviderResult)
    assert isinstance(provider, CapabilityProviderResult)
    assert isinstance(bindings[0], CapabilityBindingResult)
    assert isinstance(created, CapabilityBindingResult)
    assert isinstance(fetched, CapabilityBindingResult)
    assert updated.binding_name == "Escalation v2"
    assert isinstance(preview_test, CapabilityBindingTestResult)
    assert isinstance(saved_test, CapabilityBindingTestResult)
    assert isinstance(preview_discover, CapabilityDiscoverResult)
    assert isinstance(discovered, CapabilityDiscoverResult)
    assert isinstance(auth_started, CapabilityAuthorizationStartResult)
    assert isinstance(auth_completed, CapabilityAuthorizationCompleteResult)
    assert isinstance(capabilities[0], CapabilityCatalogEntryResult)
    assert isinstance(capability, CapabilityCatalogEntryResult)
    assert isinstance(route, CapabilityRoutePlanResult)
    assert isinstance(execution, CapabilityExecutionResult)
    assert isinstance(outcome, CapabilityOutcomeRecordResult)
    assert skills[0].kind == "skill"
    assert mcp_providers == []

    list_bindings_call = next(call for call in calls if call[0:2] == ("GET", "/v1/capability-bindings"))
    assert list_bindings_call[2]["params"] == {"provider_id": "provider.skill_pack.algenta", "scope": "user"}

    list_capabilities_call = next(call for call in calls if call[0:2] == ("GET", "/v1/capabilities"))
    assert list_capabilities_call[2]["params"] == [
        ("kinds", "skill"),
        ("provider_ids", "provider.skill_pack.algenta"),
        ("binding_ids", "binding-123"),
    ]

    get_capability_call = next(
        call for call in calls if call[0:2] == ("GET", "/v1/capabilities/cap.skill.escalation")
    )
    assert get_capability_call[2]["params"] == {"include_instruction": "1"}


async def test_async_client_capability_plane_methods_return_typed_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncDecisionEngineClient(
        api_key="de_test_capability_async",
        base_url="https://example.test",
    )

    async def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        if (method, path) == ("GET", "/v1/capability-providers"):
            return [_provider_payload()]
        if (method, path) == ("POST", "/v1/capability-bindings"):
            return _binding_payload()
        if (method, path) == ("POST", "/v1/capability-bindings/binding-123/discover"):
            return _discover_payload()
        if (method, path) == ("POST", "/v1/capabilities/route"):
            return _route_plan_payload()
        if (method, path) == ("POST", "/v1/capabilities/execute"):
            return _execution_payload()
        if (method, path) == ("POST", "/v1/capabilities/outcomes"):
            return _outcome_payload()
        raise AssertionError((method, path, kwargs))

    monkeypatch.setattr(client, "_request", fake_request)

    providers = await client.list_capability_providers()
    created = await client.create_capability_binding({"binding_name": "Escalation Skill"})
    discovered = await client.discover_capability_binding("binding-123")
    route = await client.route_capabilities({"objective": "Escalate incident"})
    execution = await client.execute_capability({"capability_id": "cap.skill.escalation"})
    outcome = await client.record_capability_outcome(
        {"capability_id": "cap.skill.escalation", "provider_id": "provider.skill_pack.algenta"}
    )

    assert isinstance(providers[0], CapabilityProviderResult)
    assert isinstance(created, CapabilityBindingResult)
    assert isinstance(discovered, CapabilityDiscoverResult)
    assert isinstance(route, CapabilityRoutePlanResult)
    assert isinstance(execution, CapabilityExecutionResult)
    assert isinstance(outcome, CapabilityOutcomeRecordResult)


def test_algenta_client_capability_plane_methods_proxy_to_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSdkClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

        def _record(self, name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
            self.calls.append((name, args, kwargs))
            return {"name": name, "args": list(args), "kwargs": kwargs}

        def list_capability_providers(self) -> dict[str, Any]:
            return self._record("list_capability_providers")

        def route_capabilities(self, request: dict[str, Any]) -> dict[str, Any]:
            return self._record("route_capabilities", request)

        def execute_capability(self, request: dict[str, Any]) -> dict[str, Any]:
            return self._record("execute_capability", request)

        def enable_skill(self, **kwargs: Any) -> dict[str, Any]:
            return self._record("enable_skill", **kwargs)

    client = AlgentaClient(api_key="de_test_algenta_capability", base_url="https://example.test")
    fake_sdk = FakeSdkClient()
    monkeypatch.setattr(client, "_sdk_client", lambda: fake_sdk)

    providers = client.list_capability_providers()
    route = client.route_capabilities({"objective": "Escalate incident"})
    execution = client.execute_capability({"capability_id": "cap.skill.escalation"})
    enabled = client.enable_skill(
        skill_name="Escalation Skill",
        instruction="Escalate immediately.",
        tags=["incident"],
    )

    assert providers["name"] == "list_capability_providers"
    assert route["name"] == "route_capabilities"
    assert execution["name"] == "execute_capability"
    assert enabled["name"] == "enable_skill"
