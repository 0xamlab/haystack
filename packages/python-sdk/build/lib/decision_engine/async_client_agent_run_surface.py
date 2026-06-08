from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from .async_client_model_surface_common import _request_model
from .async_client_stream_surface_common import _stream_model

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient


async def create_agent_run(
    client: AsyncDecisionEngineClient,
    *,
    task: str,
    context: dict[str, Any] | None = None,
    tools: list[str] | None = None,
    max_steps: int = 10,
    output_format: str = "text",
    approval_mode: str = "auto",
    start_paused: bool = False,
) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/agent/runs",
        "AgentRunResult",
        json_body={
            "task": task,
            "context": context,
            "tools": tools,
            "max_steps": max_steps,
            "output_format": output_format,
            "approval_mode": approval_mode,
            "start_paused": start_paused,
        },
    )


async def list_agent_runs(
    client: AsyncDecisionEngineClient,
    *,
    page: int = 1,
    limit: int = 25,
    status: str | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
) -> Any:
    query = urlencode(
        {
            "page": page,
            "limit": limit,
            "status": status,
            "request_hash": request_hash,
            "policy_snapshot_id": policy_snapshot_id,
            "schema_snapshot_id": schema_snapshot_id,
        }
    )
    return await _request_model(
        client,
        "GET",
        f"/v1/agent/runs?{query}",
        "AgentRunListResult",
    )


async def get_agent_run(client: AsyncDecisionEngineClient, run_id: str) -> Any:
    return await _request_model(client, "GET", f"/v1/agent/runs/{run_id}", "AgentRunResult")


async def get_agent_run_events(
    client: AsyncDecisionEngineClient,
    run_id: str,
    *,
    limit: int = 1000,
) -> Any:
    return await _request_model(
        client,
        "GET",
        f"/v1/agent/runs/{run_id}/events?limit={limit}",
        "AgentRunEventsResult",
    )


def stream_agent_run_events(
    client: AsyncDecisionEngineClient,
    run_id: str,
    *,
    limit: int = 1000,
) -> AsyncIterator[Any]:
    return _stream_model(
        client,
        "GET",
        f"/v1/agent/runs/{run_id}/events?limit={limit}&stream=true",
        "AgentRunStreamEventResult",
    )


async def list_agent_run_checkpoints(client: AsyncDecisionEngineClient, run_id: str) -> Any:
    return await _request_model(
        client,
        "GET",
        f"/v1/agent/runs/{run_id}/checkpoints",
        "AgentRunCheckpointsResult",
    )


async def query_agent_run_checkpoints(
    client: AsyncDecisionEngineClient,
    *,
    page: int = 1,
    limit: int = 25,
    status: str | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    run_id: str | None = None,
    checkpoint_id: str | None = None,
) -> Any:
    query = urlencode(
        {
            "page": page,
            "limit": limit,
            "status": status,
            "request_hash": request_hash,
            "policy_snapshot_id": policy_snapshot_id,
            "schema_snapshot_id": schema_snapshot_id,
            "run_id": run_id,
            "checkpoint_id": checkpoint_id,
        }
    )
    return await _request_model(
        client,
        "GET",
        f"/v1/agent/runs/checkpoints?{query}",
        "AgentRunCheckpointListResponseResult",
    )


async def list_agent_run_mission_events(
    client: AsyncDecisionEngineClient,
    run_id: str,
    *,
    limit: int = 1000,
) -> Any:
    return await _request_model(
        client,
        "GET",
        f"/v1/agent/runs/{run_id}/mission-events?limit={limit}",
        "AgentRunMissionEventsResult",
    )


async def query_agent_run_mission_events(
    client: AsyncDecisionEngineClient,
    *,
    page: int = 1,
    limit: int = 25,
    status: str | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    run_id: str | None = None,
    event_type: str | None = None,
) -> Any:
    query = urlencode(
        {
            "page": page,
            "limit": limit,
            "status": status,
            "request_hash": request_hash,
            "policy_snapshot_id": policy_snapshot_id,
            "schema_snapshot_id": schema_snapshot_id,
            "run_id": run_id,
            "event_type": event_type,
        }
    )
    return await _request_model(
        client,
        "GET",
        f"/v1/agent/runs/mission-events?{query}",
        "AgentRunMissionEventListResponseResult",
    )


async def list_agent_run_telemetry(
    client: AsyncDecisionEngineClient,
    run_id: str,
    *,
    limit: int = 1000,
) -> Any:
    return await _request_model(
        client,
        "GET",
        f"/v1/agent/runs/{run_id}/telemetry?limit={limit}",
        "AgentRunTelemetryResult",
    )


async def query_agent_run_telemetry(
    client: AsyncDecisionEngineClient,
    *,
    page: int = 1,
    limit: int = 25,
    status: str | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    run_id: str | None = None,
    telemetry_kind: str | None = None,
    module_name: str | None = None,
) -> Any:
    query = urlencode(
        {
            "page": page,
            "limit": limit,
            "status": status,
            "request_hash": request_hash,
            "policy_snapshot_id": policy_snapshot_id,
            "schema_snapshot_id": schema_snapshot_id,
            "run_id": run_id,
            "telemetry_kind": telemetry_kind,
            "module_name": module_name,
        }
    )
    return await _request_model(
        client,
        "GET",
        f"/v1/agent/runs/telemetry?{query}",
        "AgentRunTelemetryListResult",
    )


async def replay_agent_run(
    client: AsyncDecisionEngineClient,
    run_id: str,
    *,
    checkpoint_id: str | None = None,
) -> Any:
    return await _request_model(
        client,
        "POST",
        f"/v1/agent/runs/{run_id}/replay",
        "AgentRunReplayResult",
        json_body={"checkpoint_id": checkpoint_id},
    )


async def fork_agent_run(
    client: AsyncDecisionEngineClient,
    run_id: str,
    *,
    checkpoint_id: str | None = None,
) -> Any:
    return await _request_model(
        client,
        "POST",
        f"/v1/agent/runs/{run_id}/fork",
        "AgentRunResult",
        json_body={"checkpoint_id": checkpoint_id},
    )


async def resume_agent_run(client: AsyncDecisionEngineClient, run_id: str) -> Any:
    return await _request_model(
        client,
        "POST",
        f"/v1/agent/runs/{run_id}/resume",
        "AgentRunResult",
        json_body={},
    )


async def cancel_agent_run(client: AsyncDecisionEngineClient, run_id: str) -> Any:
    return await _request_model(
        client,
        "POST",
        f"/v1/agent/runs/{run_id}/cancel",
        "AgentRunResult",
        json_body={},
    )


async def approve_agent_run(client: AsyncDecisionEngineClient, run_id: str) -> Any:
    return await _request_model(
        client,
        "POST",
        f"/v1/agent/runs/{run_id}/approve",
        "AgentRunResult",
        json_body={},
    )


__all__ = [
    "approve_agent_run",
    "cancel_agent_run",
    "create_agent_run",
    "fork_agent_run",
    "get_agent_run",
    "get_agent_run_events",
    "list_agent_runs",
    "list_agent_run_checkpoints",
    "list_agent_run_mission_events",
    "list_agent_run_telemetry",
    "query_agent_run_mission_events",
    "query_agent_run_telemetry",
    "replay_agent_run",
    "resume_agent_run",
    "stream_agent_run_events",
]
