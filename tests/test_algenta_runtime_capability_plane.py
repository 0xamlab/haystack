from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

algenta = importlib.import_module("algenta")

Runtime = algenta.Runtime
RuntimeValidationError = algenta.RuntimeValidationError


def test_algenta_runtime_local_capability_plane_supports_skills_and_adapters() -> None:
    runtime = Runtime(mode="local")

    skill = runtime.enable_skill(
        skill_name="Escalation Skill",
        instruction="Escalate to the on-call incident commander.",
        artifact_affinities=["incident"],
        tags=["incident", "escalation"],
    )
    assert skill.capability_count == 1
    assert skill.capabilities[0].kind == "skill"

    route = runtime.route_capabilities(
        {
            "objective": "Escalate the production incident",
            "kinds": ["skill"],
            "artifact_affinities": ["incident"],
        }
    )
    assert route.selected_capability_id == skill.capabilities[0].capability_id

    execution = runtime.execute_capability({"capability_id": route.selected_capability_id})
    assert execution.status == "succeeded"
    assert execution.output["instruction_text"] == "Escalate to the on-call incident commander."

    runtime.register_capability_adapter(
        {
            "descriptor": {
                "capability_id": "cap.tool.dispatch",
                "provider_id": "provider.native_tool_pack.customer",
                "profile_id": "profile.native_tool_pack.workspace",
                "binding_id": "binding.local.cap.tool.dispatch",
                "binding_name": "Dispatch Tool",
                "name": "Dispatch Tool",
                "description": "Dispatches an incident to the owner.",
                "kind": "native_tool",
                "implementation_kind": "callable",
                "execution_owner": "client_managed",
                "artifact_affinities": ["incident"],
                "tags": ["dispatch"],
                "side_effect_class": "writes_external_state",
            },
            "execute": lambda payload: {"dispatched": payload.get("ticket_id"), "status": "ok"},
        }
    )

    capabilities = runtime.list_capabilities(kinds=["native_tool"])
    assert capabilities[0].capability_id == "cap.tool.dispatch"

    tool_execution = runtime.execute_capability(
        {
            "capability_id": "cap.tool.dispatch",
            "input": {"ticket_id": "INC-123"},
        }
    )
    assert tool_execution.output["dispatched"] == "INC-123"

    outcome = runtime.record_capability_outcome(
        {
            "capability_id": "cap.tool.dispatch",
            "provider_id": "provider.native_tool_pack.customer",
            "binding_id": "binding.local.cap.tool.dispatch",
            "success": True,
            "result_status": "completed",
        }
    )
    assert outcome.capability_id == "cap.tool.dispatch"
    assert outcome.success is True


def test_algenta_runtime_api_capability_plane_delegates_to_sdk_client() -> None:
    class FakeSdkClient:
        def list_capability_providers(self):
            return [
                {
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
                            "description": "User skills.",
                            "auth_kind": "none",
                            "default_execution_owner": "client_managed",
                            "binding_scope_default": "user",
                            "supported_binding_scopes": ["user"],
                        }
                    ],
                }
            ]

        def route_capabilities(self, request):
            assert request["objective"] == "Escalate incident"
            return {
                "selected_capability_id": "cap.skill.escalation",
                "selected_provider_id": "provider.skill_pack.algenta",
                "selected_binding_id": "binding-123",
                "kind": "skill",
                "execution_owner": "client_managed",
                "requires_approval": False,
                "confidence": 0.93,
                "reason": "Delegated route.",
                "fallbacks": [],
                "policy_snapshot_id": "capability-plane-policy-v1",
            }

        def execute_capability(self, request):
            assert request["capability_id"] == "cap.skill.escalation"
            return {
                "execution_session_id": "exec-123",
                "capability_id": "cap.skill.escalation",
                "provider_id": "provider.skill_pack.algenta",
                "binding_id": "binding-123",
                "execution_owner": "client_managed",
                "status": "succeeded",
                "output": {"instruction_text": "Escalate."},
                "error": None,
                "started_at": "2026-05-29T12:00:00Z",
                "completed_at": "2026-05-29T12:00:01Z",
            }

    runtime = Runtime(mode="api", api_key="de_test_runtime_capability", base_url="https://example.test")
    runtime._api_client = FakeSdkClient()

    providers = runtime.list_capability_providers()
    route = runtime.route_capabilities({"objective": "Escalate incident"})
    execution = runtime.execute_capability({"capability_id": "cap.skill.escalation"})

    assert providers[0].provider_id == "provider.skill_pack.algenta"
    assert route.selected_capability_id == "cap.skill.escalation"
    assert execution.status == "succeeded"


def test_algenta_runtime_local_capability_plane_rejects_algenta_managed_execution() -> None:
    runtime = Runtime(mode="local")
    skill = runtime.enable_skill(
        skill_name="Governed Skill",
        instruction="Run through Codna-managed execution.",
        execution_owner="algenta_managed",
    )

    with pytest.raises(RuntimeValidationError) as exc_info:
        runtime.execute_capability({"capability_id": skill.capabilities[0].capability_id})

    assert exc_info.value.code == "capability_execution_owner_unsupported"
    assert exc_info.value.details == {
        "capability_id": skill.capabilities[0].capability_id,
        "execution_owner": "algenta_managed",
    }


def test_algenta_runtime_local_capability_plane_requires_adapter_for_callable_capability() -> None:
    runtime = Runtime(mode="local")
    runtime.register_capability_adapter(
        {
            "descriptor": {
                "capability_id": "cap.tool.dispatch",
                "provider_id": "provider.native_tool_pack.customer",
                "profile_id": "profile.native_tool_pack.workspace",
                "binding_id": "binding.local.cap.tool.dispatch",
                "binding_name": "Dispatch Tool",
                "name": "Dispatch Tool",
                "description": "Dispatches an incident to the owner.",
                "kind": "native_tool",
                "implementation_kind": "callable",
                "execution_owner": "client_managed",
                "artifact_affinities": ["incident"],
                "tags": ["dispatch"],
                "side_effect_class": "writes_external_state",
            }
        }
    )

    with pytest.raises(RuntimeValidationError) as exc_info:
        runtime.execute_capability(
            {
                "capability_id": "cap.tool.dispatch",
                "input": {"ticket_id": "INC-123"},
            }
        )

    assert exc_info.value.code == "capability_adapter_missing"
    assert exc_info.value.details == {"capability_id": "cap.tool.dispatch"}
