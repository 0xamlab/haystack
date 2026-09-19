# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from .model_loader import validate_model as _validate_model


async def get_repository_intelligence_capabilities(client: Any):
    data = await client._request("GET", "/v1/repositories/capabilities")
    return _validate_model("RepositoryIntelligenceCapabilitiesResult", data)


async def create_repository_snapshot(
    client: Any,
    repository_id: str,
    request: dict[str, Any],
):
    data = await client._request(
        "POST", f"/v1/repositories/{repository_id}/snapshots", json=request
    )
    return _validate_model("RepositorySnapshotResult", data)


async def get_repository_snapshot(
    client: Any,
    repository_id: str,
    snapshot_id: str,
):
    data = await client._request("GET", f"/v1/repositories/{repository_id}/snapshots/{snapshot_id}")
    return _validate_model("RepositorySnapshotResult", data)


async def triage_repository(
    client: Any,
    repository_id: str,
    request: dict[str, Any],
):
    data = await client._request("POST", f"/v1/repositories/{repository_id}/triage", json=request)
    return _validate_model("RepositoryTriageResult", data)


async def create_repository_decision_plan(
    client: Any,
    repository_id: str,
    request: dict[str, Any],
):
    data = await client._request(
        "POST", f"/v1/repositories/{repository_id}/decision-plans", json=request
    )
    return _validate_model("RepositoryDecisionPlanRevisionResult", data)


async def query_repository_graph(
    client: Any,
    repository_id: str,
    request: dict[str, Any],
):
    data = await client._request(
        "POST",
        f"/v1/repositories/{repository_id}/graph-query",
        json=request,
    )
    return _validate_model("RepositoryGraphQueryResult", data)


async def simulate_repository(
    client: Any,
    repository_id: str,
    request: dict[str, Any],
):
    data = await client._request("POST", f"/v1/repositories/{repository_id}/simulate", json=request)
    return _validate_model("DecisionEnvelope", data)


async def apply_repository(
    client: Any,
    repository_id: str,
    request: dict[str, Any],
):
    data = await client._request("POST", f"/v1/repositories/{repository_id}/apply", json=request)
    return _validate_model("RepositoryApplyResult", data)
