---
sidebar_position: 3
---

# LangGraph

Add Algenta as a tool node in your LangGraph AI agent.

- Cloud Managed: `https://api.algenta.ai`
- `self_hosted` and `air_gapped`: pass an explicit self-hosted `base_url`

Private profiles do not silently fall back to Algenta cloud.

## Installation

```bash
pip install algenta-sdk langgraph langchain-openai
```

## Usage

```python
import os

from langchain_core.tools import tool
from decision_engine import AlgentaClient

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

client = AlgentaClient(api_key=api_key)

@tool
def inspect_algenta_contract() -> dict:
    """Fetch the live machine-readable Algenta contract before discovery."""
    contract = client.get_contract()
    return {
        "api_base_url": contract.api_base_url,
        "contract_endpoint": contract.primary_data_query_contract.api.contract_endpoint,
        "discovery_endpoint": contract.primary_data_query_contract.api.discovery_endpoint,
        "summary_endpoint": contract.primary_data_query_contract.api.summary_endpoint,
        "query_batch_endpoint": contract.primary_data_query_contract.api.query_batch_endpoint,
        "query_sql_report_endpoint": contract.primary_data_query_contract.api.query_sql_report_endpoint,
    }


@tool
def query_monthly_completed_orders(dataset_search: str = "orders") -> dict:
    """Inspect the contract, discover a dataset, then run an exact governed query."""
    contract = client.get_contract()
    datasets = client.list_datasets(search=dataset_search, compact=True, limit=5)
    if not datasets.datasets:
        return {"error": {"code": "dataset_not_found", "message": "No matching dataset found."}}

    dataset_id = datasets.datasets[0].dataset_id
    summary = client.get_dataset_summary(dataset_id)
    result = client.query_with_metadata(
        {
            "dataset_id": dataset_id,
            "metric": {"role": "derived_measure", "hint": "completed_order_count"},
            "aggregation": "sum",
            "group_by": ["order_month"],
            "limit": 12,
            "order": "desc",
        }
    )
    return {
        "dataset_id": dataset_id,
        "dataset_name": summary.name,
        "contract_endpoint": contract.primary_data_query_contract.api.contract_endpoint,
        "request_id": result.metadata.request_id,
        "latency_ms": result.metadata.latency_ms,
        "rows": result.data.result,
    }


@tool
def compare_kpis(dataset_id: str) -> dict:
    """Run multiple governed exact queries in one batch call."""
    result = client.query_batch(
        {
            "defaults": {"dataset_id": dataset_id},
            "queries": [
                {
                    "key": "overall_completed_orders",
                    "request": {
                        "metric": {"role": "derived_measure", "hint": "completed_order_count"},
                        "aggregation": "sum",
                    },
                },
                {
                    "key": "average_order_value",
                    "request": {
                        "metric": {"role": "base_measure", "hint": "gross_revenue"},
                        "aggregation": "avg",
                    },
                },
            ],
        }
    )
    return {
        "request_id": result.request_id,
        "results": [item.model_dump() for item in result.results],
    }


@tool
def route_capability_for_incident(objective: str) -> dict:
    """Use the unified capability plane before choosing a specialist tool node."""
    route = client.route_capabilities(
        {
            "objective": objective,
            "kinds": ["dataset", "skill", "mcp_tool", "native_tool"],
            "artifact_affinities": ["incident"],
            "tags": ["incident"],
        }
    )
    capability = client.get_capability(route.selected_capability_id)
    return {
        "selected_capability_id": route.selected_capability_id,
        "selected_provider_id": route.selected_provider_id,
        "kind": route.kind,
        "execution_owner": route.execution_owner,
        "requires_approval": route.requires_approval,
        "required_policy": capability.required_policy,
    }
```

The direct-client snippet above is the Cloud Managed path. In `self_hosted`
and `air_gapped`, construct `AlgentaClient(api_key=..., base_url="http://localhost:8000")`
or your own self-hosted origin instead.

For wide read-only reports that should return raw columns and rows, use
`client.query_sql_report(...)`. Keep that separate from the governed exact-query
path.

The same direct client also exposes persisted runtime and control-plane helpers
that fit naturally into LangGraph approval or follow-up nodes:

- `client.list_capability_providers(...)`, `client.list_capability_bindings(...)`, and `client.list_capabilities(...)` for customer-agnostic capability discovery
- `client.route_capabilities(...)`, `client.get_capability(...)`, and `client.execute_capability(...)` for unified tool and skill routing before the main graph branches
- `client.list_agent_runs(...)`
- `client.query_agent_run_checkpoints(...)`
- `client.query_agent_run_mission_events(...)`
- `client.query_agent_run_telemetry(...)`
- `client.replay_agent_run(run_id, checkpoint_id=...)`
- `client.fork_agent_run(run_id, checkpoint_id=...)`
- `client.get_audit_log_artifacts(...)`
- `client.list_execution_policy_snapshots()`

## When to use which surface

- `get_contract()` for the live machine-readable API, SDK, CLI, and MCP contract before the first tool run
- `route_capabilities(...)` plus `get_capability(...)` when the graph needs to choose between data, MCP, native-tool, or skill paths without app-specific routing headers
- `list_datasets(search=..., compact=True)` plus `get_dataset_summary(...)` for low-token dataset discovery
- `query_with_metadata(...)` for one exact metric query with stable request/cost/latency metadata
- `query_batch(...)` for multi-metric governed exact queries in one API call
- `query_sql_report(...)` for constrained read-only rowset reports over authorized datasets
- `list_agent_runs(...)`, checkpoint and mission-event queries, and `query_agent_run_telemetry(...)` for persisted runtime follow-up inspection
- `replay_agent_run(...)` and `fork_agent_run(...)` for deterministic branch-from-checkpoint or replay workflows
- `get_audit_log_artifacts(...)` and `list_execution_policy_snapshots()` for immutable audit and policy review inside governed approval flows

## Simulation example

```python
import os

from langchain_core.tools import tool
from decision_engine import AlgentaClient

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

client = AlgentaClient(api_key=api_key)

@tool
def run_decision_simulation(
    variables: dict,
    objective: str = "maximize_net_value"
) -> dict:
    """Run a Monte Carlo simulation to evaluate a decision scenario."""
    result = client.simulate(
        mode="auto",
        scenario={"variables": variables, "objective": objective}
    )
    return {
        "recommended_action": result.recommended_action,
        "confidence": result.confidence,
        "rationale": result.rationale,
        "expected_value": result.metrics.expected_value,
        "probability_of_loss": result.metrics.probability_of_loss,
    }
```

Full example: [`examples/langgraph/decision_tool.py`](https://github.com/decisionengine/decision-engine/tree/main/examples/langgraph/decision_tool.py)

Capability-plane router example: [`examples/langgraph/capability_router.py`](https://github.com/decisionengine/decision-engine/tree/main/examples/langgraph/capability_router.py)
