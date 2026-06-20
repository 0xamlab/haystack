"""
LangGraph integration — Algenta tool wrapper.

This module provides @tool decorated functions that wrap the public Algenta SDK
for use in LangGraph agent workflows across both simulation and governed
data/query tasks.

Setup:
    pip install algenta-sdk langgraph langchain-openai
    export ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY>  # Cloud Managed example

In `self_hosted` and `air_gapped`, keep `ALGENTA_API_KEY` pointed at the API
key provisioned by your self-hosted operator deployment and configure the
example to use your self-hosted base URL. Private profiles fail closed and do
not silently fall back to Algenta cloud.

Usage:
    from examples.langgraph.decision_tool import (
        inspect_algenta_contract,
        inspect_runtime_lineage,
        query_dataset_batch,
        query_dataset_metric,
        query_dataset_sql_report,
        recommend_action,
        simulate_decision,
    )

    tools = [
        inspect_algenta_contract,
        inspect_runtime_lineage,
        query_dataset_metric,
        query_dataset_batch,
        query_dataset_sql_report,
        simulate_decision,
        recommend_action,
    ]
"""

from __future__ import annotations

import json
import os
from typing import Any

from decision_engine import AlgentaClient
from examples.shared.privacy_profile import resolve_example_api_base_url


def _resolve_api_key() -> str:
    api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY", "")
    if not api_key:
        raise ValueError(
            "Algenta API key required. Set ALGENTA_API_KEY or DE_API_KEY before using this example."
        )
    return api_key


def _resolve_base_url() -> str:
    return resolve_example_api_base_url(
        component="LangGraph Algenta example",
        default_base_url="http://localhost:8000",
    )


def _client() -> AlgentaClient:
    return AlgentaClient(
        api_key=_resolve_api_key(),
        base_url=_resolve_base_url(),
    )


def _dataset_not_found_payload(dataset_search: str) -> str:
    return json.dumps(
        {
            "error": {
                "code": "dataset_not_found",
                "message": f"No dataset matched search {dataset_search!r}.",
            }
        },
        indent=2,
    )


def _contract_payload(client: AlgentaClient) -> dict[str, Any]:
    contract = client.get_contract()
    primary = contract.primary_data_query_contract
    return {
        "api_base_url": contract.api_base_url,
        "contract_endpoint": primary.api.contract_endpoint,
        "discovery_endpoint": primary.api.discovery_endpoint,
        "summary_endpoint": primary.api.summary_endpoint,
        "query_endpoint": primary.api.query_endpoint,
        "query_batch_endpoint": primary.api.query_batch_endpoint,
        "query_sql_report_endpoint": primary.api.query_sql_report_endpoint,
        "python_contract_method": primary.direct_sdk.python.contract_method,
        "typescript_contract_method": primary.direct_sdk.typescript.contract_method,
        "cli_contract_command": primary.cli.contract_command,
        "mcp_contract_tool": primary.mcp.contract_tool,
    }


def _discover_dataset(
    *,
    dataset_search: str,
    limit: int,
    status: str | None = "ready",
    source_name: str | None = None,
) -> tuple[Any, Any, Any] | None:
    client = _client()
    datasets = client.list_datasets(
        search=dataset_search,
        status=status,
        source_name=source_name,
        compact=True,
        limit=limit,
    )
    if not datasets.datasets:
        return None

    dataset = datasets.datasets[0]
    summary = client.get_dataset_summary(dataset.dataset_id)
    return client, datasets, summary


# ── Try to import LangChain tool decorator ────────────────────────────────────
try:
    from langchain_core.tools import tool as _tool

    _HAS_LANGCHAIN = True
except ImportError:

    def _tool(fn):  # type: ignore[misc]
        return fn

    _HAS_LANGCHAIN = False


@_tool
def inspect_algenta_contract() -> str:
    """
    Inspect the live machine-readable Algenta contract before discovery or querying.

    Use this tool first when the agent needs the exact discovery, summary, batch,
    SQL-report, CLI, or MCP contract exposed by the running service.
    """
    client = _client()
    return json.dumps(_contract_payload(client), indent=2)


@_tool
def inspect_runtime_lineage(
    status: str = "requires_approval",
    run_limit: int = 10,
    query_limit: int = 25,
) -> str:
    """
    Inspect persisted agent-run lineage, replay points, and control-plane artifacts.

    Use this tool when the agent needs the latest persisted run inventory plus
    matching checkpoints, mission events, telemetry, audit artifacts, and
    execution-policy snapshots before taking a follow-up action.
    """
    client = _client()
    runs = client.list_agent_runs(status=status, limit=run_limit)
    run_items = list(runs.runs)
    selected_run_id = run_items[0].run_id if run_items else None
    checkpoints = (
        client.query_agent_run_checkpoints(run_id=selected_run_id, limit=query_limit)
        if selected_run_id
        else None
    )
    mission_events = (
        client.query_agent_run_mission_events(run_id=selected_run_id, limit=query_limit)
        if selected_run_id
        else None
    )
    telemetry = (
        client.query_agent_run_telemetry(run_id=selected_run_id, limit=query_limit)
        if selected_run_id
        else None
    )
    audit_artifacts = client.get_audit_log_artifacts(limit=query_limit)
    policy_snapshots = client.list_execution_policy_snapshots()
    return json.dumps(
        {
            "runs": [item.model_dump() for item in run_items],
            "selected_run_id": selected_run_id,
            "checkpoints": [] if checkpoints is None else [item.model_dump() for item in checkpoints.checkpoints],
            "mission_events": [] if mission_events is None else [item.model_dump() for item in mission_events.events],
            "telemetry": [] if telemetry is None else [item.model_dump() for item in telemetry.entries],
            "audit_artifacts": [item.model_dump() for item in audit_artifacts.items],
            "policy_snapshots": [item.model_dump() for item in policy_snapshots.snapshots],
        },
        indent=2,
    )


@_tool
def query_dataset_metric(
    dataset_search: str,
    metric_hint: str,
    aggregation: str = "avg",
    group_by: list[str] | None = None,
    limit: int = 12,
    discovery_limit: int = 5,
    metric_role: str = "derived_measure",
    status: str | None = "ready",
    source_name: str | None = None,
) -> str:
    """
    Discover a dataset, inspect its summary, and run one governed exact query.

    Use this tool when you need:
    - the live Algenta contract first, then low-token dataset discovery
    - low-token dataset discovery before querying
    - exact governed metric queries with request metadata
    - a deterministic query path rather than open-ended SQL
    """
    discovered = _discover_dataset(
        dataset_search=dataset_search,
        limit=discovery_limit,
        status=status,
        source_name=source_name,
    )
    if discovered is None:
        return _dataset_not_found_payload(dataset_search)

    client, datasets, summary = discovered
    contract_payload = _contract_payload(client)
    result = client.query_with_metadata(
        {
            "dataset_id": summary.dataset_id,
            "metric": {"role": metric_role, "hint": metric_hint},
            "aggregation": aggregation,
            "group_by": group_by or [],
            "limit": limit,
            "order": "desc",
        }
    )
    return json.dumps(
        {
            "dataset_id": summary.dataset_id,
            "dataset_name": summary.name,
            "matched_total": datasets.matched_total,
            "contract": contract_payload,
            "query_hints": summary.query_hints,
            "metadata": {
                "request_id": result.metadata.request_id,
                "latency_ms": result.metadata.latency_ms,
                "tokens_in": result.metadata.tokens_in,
                "tokens_out": result.metadata.tokens_out,
                "cost_usd": result.metadata.cost_usd,
                "cache_hit": result.metadata.cache_hit,
            },
            "result": result.data.result,
        },
        indent=2,
    )


@_tool
def query_dataset_batch(
    dataset_search: str,
    queries: list[dict[str, Any]],
    *,
    discovery_limit: int = 5,
    status: str | None = "ready",
    source_name: str | None = None,
) -> str:
    """
    Discover a dataset, inspect its summary, and run several governed exact queries.

    Use this tool when one user prompt needs multiple exact metrics in one ordered
    response instead of several sequential calls.
    """
    discovered = _discover_dataset(
        dataset_search=dataset_search,
        limit=discovery_limit,
        status=status,
        source_name=source_name,
    )
    if discovered is None:
        return _dataset_not_found_payload(dataset_search)

    client, datasets, summary = discovered
    result = client.query_batch(
        {
            "defaults": {"dataset_id": summary.dataset_id},
            "queries": queries,
        }
    )
    return json.dumps(
        {
            "dataset_id": summary.dataset_id,
            "dataset_name": summary.name,
            "matched_total": datasets.matched_total,
            "request_id": result.request_id,
            "results": [item.model_dump() for item in result.results],
        },
        indent=2,
    )


@_tool
def query_dataset_sql_report(
    dataset_search: str,
    sql: str,
    *,
    alias: str = "dataset",
    max_rows: int = 100,
    discovery_limit: int = 5,
    status: str | None = "ready",
    source_name: str | None = None,
) -> str:
    """
    Discover a dataset, inspect its summary, and run a constrained read-only SQL report.

    Use this only when the result needs a wide rowset instead of the governed
    exact-query surface.
    """
    discovered = _discover_dataset(
        dataset_search=dataset_search,
        limit=discovery_limit,
        status=status,
        source_name=source_name,
    )
    if discovered is None:
        return _dataset_not_found_payload(dataset_search)

    client, datasets, summary = discovered
    result = client.query_sql_report(
        {
            "sources": [{"dataset_id": summary.dataset_id, "alias": alias}],
            "sql": sql,
            "max_rows": max_rows,
        }
    )
    return json.dumps(
        {
            "dataset_id": summary.dataset_id,
            "dataset_name": summary.name,
            "matched_total": datasets.matched_total,
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count,
            "truncated": result.truncated,
            "request_id": result.request_id,
            "latency_ms": result.latency_ms,
        },
        indent=2,
    )


@_tool
def simulate_decision(
    variables: dict[str, dict[str, float]],
    objective: str = "maximize_net_value",
    runs: int = 10000,
) -> str:
    """
    Simulate a decision scenario using Monte Carlo analysis.

    Use this tool when you need to:
    - Evaluate the expected outcome of a business decision
    - Quantify risk and uncertainty in a scenario
    - Get a probability-weighted recommendation
    """
    client = _client()
    result = client.simulate(
        mode="auto",
        scenario={
            "variables": variables,
            "objective": objective,
        },
        runs=runs,
    )
    return json.dumps(
        {
            "recommended_action": result.recommended_action,
            "confidence": result.confidence,
            "rationale": result.rationale,
            "expected_value": result.metrics.expected_value,
            "probability_of_loss": result.metrics.probability_of_loss,
            "p5_downside": result.percentiles.p5,
            "p95_upside": result.percentiles.p95,
            "scenarios_run": result.scenarios_run,
            "request_id": result.request_id,
        },
        indent=2,
    )


@_tool
def recommend_action(
    actions: list[dict[str, Any]],
    runs: int = 10000,
) -> str:
    """
    Compare multiple named actions and get a ranked recommendation.

    Use this tool when you need to:
    - Choose between two or more options with uncertainty
    - Rank alternatives by expected value and risk
    """
    client = _client()
    formatted_actions = []
    for action in actions:
        formatted_actions.append(
            {
                "name": action["name"],
                "request": {
                    "mode": "auto",
                    "scenario": {
                        "variables": action.get("variables", {}),
                        "objective": action.get("objective", "maximize_net_value"),
                    },
                    "runs": runs,
                },
            }
        )

    result = client.recommend(actions=formatted_actions)
    return json.dumps(
        {
            "recommended_action": result.recommended_action,
            "confidence": result.confidence,
            "rationale": result.rationale,
            "ranking": [
                {
                    "rank": item.get("rank"),
                    "name": item.get("name"),
                    "expected_value": item.get("expected_value"),
                    "score": item.get("score"),
                }
                for item in result.action_results or []
            ],
            "request_id": result.request_id,
        },
        indent=2,
    )


EXAMPLE_AGENT_CODE = '''
"""Example LangGraph agent using Algenta tools."""
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from examples.langgraph.decision_tool import (
    inspect_algenta_contract,
    inspect_runtime_lineage,
    query_dataset_batch,
    query_dataset_metric,
    query_dataset_sql_report,
    recommend_action,
    simulate_decision,
)

llm = ChatOpenAI(model="gpt-4o")
tools = [
    inspect_algenta_contract,
    inspect_runtime_lineage,
    query_dataset_metric,
    query_dataset_batch,
    query_dataset_sql_report,
    simulate_decision,
    recommend_action,
]
agent = create_react_agent(llm, tools)

result = agent.invoke({
    "messages": [
        {"role": "user", "content": (
            "Inspect the live contract, then find the orders dataset and "
            "return monthly completed orders and average order value. "
            "If I ask about paused or approval-gated runs, inspect runtime lineage first. "
            "If I ask for a wide table, use the SQL report tool. "
            "If I ask for scenario analysis after that, use the decision simulation tools."
        )}
    ]
})
print(result["messages"][-1].content)
'''


if __name__ == "__main__":
    import sys

    def _emit(message: str = "") -> None:
        sys.stdout.write(f"{message}\n")

    _emit("Testing Algenta LangGraph tools directly...\n")
    contract_result = inspect_algenta_contract()  # type: ignore[call-arg]
    _emit("inspect_algenta_contract result:")
    _emit(contract_result)
    _emit("")

    metric_result = query_dataset_metric(  # type: ignore[call-arg]
        dataset_search="orders",
        metric_hint="completed_order_count",
        aggregation="sum",
        group_by=["order_month"],
        limit=12,
    )
    _emit("query_dataset_metric result:")
    _emit(metric_result)
    _emit("")

    simulate_result = simulate_decision(  # type: ignore[call-arg]
        variables={
            "revenue": {"low": 80000, "high": 200000},
            "cost": {"low": 40000, "high": 90000},
        },
        objective="maximize_net_value",
        runs=5000,
    )
    _emit("simulate_decision result:")
    _emit(simulate_result)
    _emit("\nAgent usage example:")
    _emit(EXAMPLE_AGENT_CODE)
