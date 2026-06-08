"""
LangGraph capability-router example for the unified Algenta capability plane.

Setup:
    pip install algenta-sdk langgraph langchain-openai
    export ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY>  # Cloud Managed example

In `self_hosted` and `air_gapped`, keep `ALGENTA_API_KEY` pointed at the API
key provisioned by your self-hosted operator deployment and configure the
example to use your self-hosted base URL. Private profiles fail closed and do
not silently fall back to Algenta cloud.
"""

from __future__ import annotations

import json
import os

from decision_engine import AlgentaClient
from examples.shared.privacy_profile import resolve_example_api_base_url


def _resolve_api_key() -> str:
    api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY", "")
    if not api_key:
        raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
    return api_key


def _client() -> AlgentaClient:
    return AlgentaClient(
        api_key=_resolve_api_key(),
        base_url=resolve_example_api_base_url(
            component="LangGraph capability router example",
            default_base_url="http://localhost:8000",
        ),
    )


def route_and_execute_capability(objective: str) -> dict[str, object]:
    """
    Route one objective through the capability plane, fetch the selected
    capability record, and execute it when the selected path is Algenta-managed.
    """
    client = _client()
    route = client.route_capabilities(
        {
            "objective": objective,
            "kinds": ["dataset", "skill", "mcp_tool", "native_tool", "runtime_library"],
            "artifact_affinities": ["incident"],
            "tags": ["incident", "triage"],
        }
    )
    capability = client.get_capability(route.selected_capability_id, include_instruction=True)

    payload: dict[str, object] = {
        "selected_capability_id": route.selected_capability_id,
        "selected_provider_id": route.selected_provider_id,
        "selected_binding_id": route.selected_binding_id,
        "kind": route.kind,
        "execution_owner": route.execution_owner,
        "requires_approval": route.requires_approval,
        "required_policy": capability.required_policy,
    }

    if route.execution_owner != "algenta_managed":
        payload["execution_skipped"] = True
        payload["reason"] = "client_managed_capability_requires_customer_adapter"
        return payload

    execution = client.execute_capability(
        {
            "capability_id": route.selected_capability_id,
            "binding_id": route.selected_binding_id,
            "input": {
                "objective": objective,
                "requested_output": "instruction_bundle",
            },
        }
    )
    payload["execution"] = execution.model_dump()
    return payload


if __name__ == "__main__":
    example_objective = (
        "Investigate the latest checkout incident and route me to the correct "
        "governed specialist path."
    )
    print(json.dumps(route_and_execute_capability(example_objective), indent=2))
