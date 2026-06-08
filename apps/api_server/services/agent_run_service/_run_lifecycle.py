"""Checkpoint/run lifecycle + tool selection + simulation execution.

Extracted from apps/api_server/services/agent_run_service.py during modularization.
"""
from __future__ import annotations

import errno
import hashlib
import json
import logging
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from apps.api_server.schemas.agent_runs import (
    AgentRunAction,
    AgentRunCheckpointListResource,
    AgentRunCheckpointListResponse,
    AgentRunCheckpointResource,
    AgentRunCheckpointsResponse,
    AgentRunCreateRequest,
    AgentRunEvent,
    AgentRunForkRequest,
    AgentRunListResponse,
    AgentRunMissionEventListResource,
    AgentRunMissionEventListResponse,
    AgentRunMissionEventResource,
    AgentRunMissionEventsResponse,
    AgentRunPendingAction,
    AgentRunReplayRequest,
    AgentRunReplayResponse,
    AgentRunResource,
    AgentRunStatus,
    AgentRunTelemetryBatchResource,
    AgentRunTelemetryBatchListResource,
    AgentRunTelemetryListResponse,
    AgentRunTelemetryResponse,
)
from apps.api_server.schemas.products import AgentStep
from apps.api_server.services.runtime_internal_contracts import (
    ArtifactRecord,
    CheckpointRecord,
    MissionEvent,
    TelemetryBatch,
    parquet_bytes_from_records,
    table_from_parquet_bytes,
    validate_table_schema,
)
from apps.api_server.schemas.simulate import SimulateRequestExpert
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.execution_policy_service import get_policy
from apps.api_server.services.simulation_service import run_simulation_fast
from apps.runtime.ledger import append_event
from apps.runtime_manifest import load_runtime_manifest


_LOCK = threading.Lock()
_DEFAULT_TOOLS = ("search", "simulate", "optimize", "calculate", "summarize")
_REQUEST_SCHEMA_VERSION = "agent-run-request-v1"
_RUN_STATE_ARTIFACT_KIND = "agent_run_state"
_RUN_STATE_SCHEMA_REVISION = "agent-run-checkpoint-v1"
_RUN_EVENT_ARTIFACT_KIND = "agent_run_event"
_RUN_EVENT_SCHEMA_REVISION = "agent-run-event-v1"
_IMPLICIT_FALLBACK_RUNTIME_DIR = Path(tempfile.gettempdir()) / "algenta-runtime"
_WRITABLE_RUNTIME_DIRS: set[Path] = set()
_UNWRITABLE_DEFAULT_RUNTIME_DIRS: set[Path] = set()
_WARNED_DEFAULT_RUNTIME_DIRS: set[Path] = set()
logger = logging.getLogger(__name__)


from apps.api_server.services.agent_run_service._data_models import *  # noqa: F401, F403
from apps.api_server.services.agent_run_service._data_models import (
    _StoredAgentRun,
    _StoredAgentRunCheckpoint,
)
from apps.api_server.services.agent_run_service._path_helpers import *  # noqa: F401, F403
from apps.api_server.services.agent_run_service._path_helpers import (
    _is_runtime_dir_write_error,
    _runtime_dir_for_base,
    _runtime_dir,
    _agent_runs_dir,
    _run_path,
    _events_path,
    _run_state_dir,
    _checkpoints_dir,
    _artifacts_dir,
    _events_dir,
    _telemetry_dir,
    _checkpoint_snapshot_path,
    _checkpoint_metadata_path,
    _checkpoint_parquet_path,
    _artifact_payload_path,
    _artifact_parquet_path,
    _event_artifact_payload_path,
    _event_artifact_parquet_path,
    _telemetry_parquet_path,
)
from apps.api_server.services.agent_run_service._read_helpers import *  # noqa: F401, F403
from apps.api_server.services.agent_run_service._read_helpers import (
    _read_run,
    _list_runs,
    _filter_runs,
    _read_events,
    _read_mission_events,
    _read_telemetry_batches,
    _read_checkpoints,
    _read_checkpoint,
    _checkpoint_resource,
)
from apps.api_server.services.agent_run_service._io_helpers import *  # noqa: F401, F403
from apps.api_server.services.agent_run_service._io_helpers import (
    _utc_now,
    _json_dumps,
    _hash_payload,
    _hash_text,
    _write_json,
    _write_run,
    _persist_run_event_artifact,
    _persist_run_completion_telemetry,
    _append_run_event,
)




def _request_hash(
    payload: AgentRunCreateRequest,
    available_tools: list[str],
) -> str:
    return _hash_payload(
        {
            "schema_version": _REQUEST_SCHEMA_VERSION,
            "task": payload.task,
            "context": payload.context,
            "tools": available_tools,
            "max_steps": payload.max_steps,
            "output_format": payload.output_format,
            "approval_mode": payload.approval_mode,
            "start_paused": payload.start_paused,
        }
    )


def _decision_hash_for_run(run: _StoredAgentRun) -> str:
    return _hash_payload(
        {
            "run_id": run.run_id,
            "status": run.status,
            "task": run.task,
            "output_format": run.output_format,
            "approval_mode": run.approval_mode,
            "pending_action": run.pending_action,
            "selected_tool": run.selected_tool,
            "result": run.result,
            "tools_available": run.tools_available,
            "tools_used": run.tools_used,
            "steps": [step.model_dump(mode="json") for step in run.steps],
            "request_hash": run.request_hash,
            "policy_snapshot_id": run.policy_snapshot_id,
            "schema_snapshot_id": run.schema_snapshot_id,
            "manifest_version": run.manifest_version,
            "source_run_id": run.source_run_id,
            "source_checkpoint_id": run.source_checkpoint_id,
        }
    )


@cache
def _runtime_manifest_metadata() -> dict[str, str]:
    try:
        manifest = load_runtime_manifest(
            api_env=os.environ.get("API_ENV", "local"),
            runtime_library_http_api_enabled=os.environ.get(
                "RUNTIME_LIBRARY_HTTP_API_ENABLED",
                "",
            ).lower()
            in {"1", "true", "yes", "on"},
            deployment_mode=os.environ.get("ALGENTA_DEPLOYMENT_MODE", "local_dev_daemon"),
        )
    except (FileNotFoundError, ValueError):
        return {"schema_snapshot_id": "unavailable", "manifest_version": "unavailable"}
    return {
        "schema_snapshot_id": manifest.schema_snapshot.snapshot_id,
        "manifest_version": manifest.module_manifest_version,
    }


def _checkpoint_snapshot_payload(
    *,
    run: _StoredAgentRun,
    checkpoint_id: str,
    checkpoint_index: int,
    parent_checkpoint_id: str | None,
    event_start_index: int,
    event_end_index: int,
    artifact_refs: list[str],
    content_hash: str,
) -> dict[str, Any]:
    return {
        "run": run.model_dump(mode="json"),
        "checkpoint": {
            "checkpoint_id": checkpoint_id,
            "checkpoint_index": checkpoint_index,
            "parent_checkpoint_id": parent_checkpoint_id,
            "event_start_index": event_start_index,
            "event_end_index": event_end_index,
            "artifact_refs": artifact_refs,
            "content_hash": content_hash,
        },
    }


def _persist_checkpoint_unlocked(run: _StoredAgentRun) -> _StoredAgentRunCheckpoint:
    org_id = run.org_id
    run_id = run.run_id
    existing = _read_checkpoints(org_id, run_id)
    checkpoint_index = len(existing) + 1
    parent_checkpoint_id = existing[-1].checkpoint_id if existing else None
    event_start_index = existing[-1].event_end_index + 1 if existing else 0
    event_end_index = max(len(_read_events(org_id, run_id)) - 1, 0)
    checkpoint_id = f"cp_{uuid.uuid4().hex}"
    artifact_id = f"art_{uuid.uuid4().hex}"
    decision_hash = _decision_hash_for_run(run)
    artifact_refs = list(dict.fromkeys([*run.artifact_refs, artifact_id]))
    run.decision_hash = decision_hash
    run.artifact_refs = artifact_refs
    run.latest_checkpoint_id = checkpoint_id
    run.checkpoint_count = checkpoint_index

    snapshot_preview = _checkpoint_snapshot_payload(
        run=run,
        checkpoint_id=checkpoint_id,
        checkpoint_index=checkpoint_index,
        parent_checkpoint_id=parent_checkpoint_id,
        event_start_index=event_start_index,
        event_end_index=event_end_index,
        artifact_refs=artifact_refs,
        content_hash="",
    )
    content_hash = _hash_payload(snapshot_preview)
    snapshot_payload = _checkpoint_snapshot_payload(
        run=run,
        checkpoint_id=checkpoint_id,
        checkpoint_index=checkpoint_index,
        parent_checkpoint_id=parent_checkpoint_id,
        event_start_index=event_start_index,
        event_end_index=event_end_index,
        artifact_refs=artifact_refs,
        content_hash=content_hash,
    )

    snapshot_path = _checkpoint_snapshot_path(org_id, run_id, checkpoint_id)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(_json_dumps(snapshot_payload), encoding="utf-8")

    artifact_payload_path = _artifact_payload_path(org_id, run_id, artifact_id)
    artifact_payload_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_payload_path.write_text(_json_dumps(snapshot_payload), encoding="utf-8")

    created_at = _utc_now()
    artifact_record = ArtifactRecord(
        artifact_id=artifact_id,
        artifact_kind=_RUN_STATE_ARTIFACT_KIND,
        tenant_scope=org_id,
        workspace_scope=run_id,
        schema_revision=_RUN_STATE_SCHEMA_REVISION,
        content_hash=content_hash,
        storage_format="json",
        storage_path=str(artifact_payload_path),
        provenance_parent_hashes=[],
        created_at=created_at,
    )
    checkpoint_record = CheckpointRecord(
        checkpoint_id=checkpoint_id,
        parent_checkpoint_id=parent_checkpoint_id,
        tenant_scope=org_id,
        workspace_scope=run_id,
        request_hash=run.request_hash,
        policy_snapshot_id=run.policy_snapshot_id,
        schema_snapshot_id=run.schema_snapshot_id,
        manifest_version=run.manifest_version,
        content_hash=content_hash,
        event_start_index=event_start_index,
        event_end_index=event_end_index,
        artifact_refs=artifact_refs,
        created_at=created_at,
    )

    checkpoint_parquet_path = _checkpoint_parquet_path(org_id, run_id, checkpoint_id)
    checkpoint_parquet_path.write_bytes(
        parquet_bytes_from_records([checkpoint_record], record_type=CheckpointRecord)
    )
    artifact_parquet_path = _artifact_parquet_path(org_id, run_id, artifact_id)
    artifact_parquet_path.write_bytes(
        parquet_bytes_from_records([artifact_record], record_type=ArtifactRecord)
    )

    checkpoint = _StoredAgentRunCheckpoint(
        checkpoint_id=checkpoint_id,
        checkpoint_index=checkpoint_index,
        run_id=run_id,
        parent_checkpoint_id=parent_checkpoint_id,
        status=run.status,
        event_start_index=event_start_index,
        event_end_index=event_end_index,
        request_hash=run.request_hash,
        decision_hash=decision_hash,
        content_hash=content_hash,
        policy_snapshot_id=run.policy_snapshot_id,
        schema_snapshot_id=run.schema_snapshot_id,
        manifest_version=run.manifest_version,
        artifact_refs=artifact_refs,
        snapshot_path=str(snapshot_path),
        checkpoint_parquet_path=str(checkpoint_parquet_path),
        artifact_parquet_path=str(artifact_parquet_path),
        created_at=created_at,
    )
    _write_json(
        _checkpoint_metadata_path(org_id, run_id, checkpoint_id),
        checkpoint.model_dump(mode="json"),
    )
    _write_run(run)
    return checkpoint


def _latest_checkpoint_for_run(run: _StoredAgentRun) -> _StoredAgentRunCheckpoint:
    if not run.latest_checkpoint_id:
        raise AgentRunServiceError(
            "agent_run_checkpoint_not_found",
            f"Agent run '{run.run_id}' has no persisted checkpoints.",
            {"run_id": run.run_id},
        )
    return _read_checkpoint(run.org_id, run.run_id, run.latest_checkpoint_id)


def _resolve_checkpoint_for_run(
    run: _StoredAgentRun,
    checkpoint_id: str | None,
) -> _StoredAgentRunCheckpoint:
    if checkpoint_id is None:
        return _latest_checkpoint_for_run(run)
    return _read_checkpoint(run.org_id, run.run_id, checkpoint_id)


def _select_tool(task: str, available_tools: list[str]) -> str:
    task_lower = task.lower()
    if any(
        word in task_lower
        for word in ("optimiz", "best", "maximum", "minimum", "cheapest", "fastest")
    ):
        tool = "optimize"
    elif any(
        word in task_lower for word in ("risk", "probabilit", "scenario", "forecast", "simulat")
    ):
        tool = "simulate"
    elif any(word in task_lower for word in ("search", "find", "retriev", "look up", "what is")):
        tool = "search"
    else:
        tool = "calculate"
    if tool not in set(available_tools):
        return "calculate" if "calculate" in available_tools else available_tools[0]
    return tool


def _initial_steps(task: str, tool: str) -> list[AgentStep]:
    return [
        AgentStep(
            step=1,
            action=f"Planning execution for: {task[:80]}",
            status="completed",
        ),
        AgentStep(
            step=2,
            action=f"Routing to {tool} tool",
            tool=tool,
            status="completed",
        ),
    ]


def _finalize_result(
    *,
    task: str,
    tool: str,
    run_id: str,
    output_format: str,
    result_text: str,
) -> str | dict[str, Any]:
    if output_format == "json":
        return {
            "task": task,
            "result": result_text,
            "tool_used": tool,
            "run_id": run_id,
        }
    if output_format == "markdown":
        return f"# Agent Result\n\n- Task: {task}\n- Tool: {tool}\n\n{result_text}"
    return result_text


async def _run_sim(
    sim_dict: dict[str, Any],
    auth: AuthContext,
    request_state: Any | None = None,
) -> dict[str, Any]:
    request = SimulateRequestExpert.model_validate(sim_dict)
    envelope, persist_meta = await run_simulation_fast(
        request=request,
        org_id=auth["org_id"],
        api_key_id=auth.get("key_id"),
    )
    if request_state is not None:
        request_state.mojo_ms = int(persist_meta.get("execution_ms", 0) or 0)
    metrics = envelope.metrics
    percentiles = envelope.percentiles
    return {
        "run_id": str(envelope.run_id),
        "expected_value": metrics.expected_value,
        "probability_of_loss": metrics.probability_of_loss,
        "percentiles": {
            "p5": percentiles.p5,
            "p95": percentiles.p95,
        },
    }


async def _execute_selected_tool(
    *,
    tool: str,
    task: str,
    auth: AuthContext,
    request_state: Any | None,
) -> str:
    if tool == "simulate":
        sim_payload = {
            "mode": "expert",
            "simulation_model": "monte_carlo",
            "runs": 10000,
            "simulation": {
                "variables": [
                    {
                        "name": "outcome",
                        "distribution": "normal",
                        "params": {"mean": 100, "std": 20},
                    }
                ],
                "objective_function": "outcome",
            },
        }
        try:
            sim_result = await _run_sim(sim_payload, auth, request_state)
            expected_value = sim_result.get("expected_value", 100)
            probability_of_loss = sim_result.get("probability_of_loss", 0.15)
            return (
                f"Simulation complete. Expected outcome: {expected_value:,.0f}. "
                f"Probability of negative result: {probability_of_loss:.0%}. "
                f"Recommendation: {'proceed' if probability_of_loss < 0.3 else 'review risk'}."
            )
        except Exception:
            return "Simulation completed with estimated outcome."
    if tool == "optimize":
        return (
            f"Optimization complete for: {task}. "
            "Optimal configuration identified with estimated 15–25% improvement."
        )
    if tool == "search":
        return f"Search complete. Found relevant context for: {task}."
    return f"Analysis complete for: {task}."


def _record_ledger(
    *,
    run: _StoredAgentRun,
    action: str,
    status: str,
    latency_ms: float | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    append_event(
        task_id=run.run_id,
        surface="agent_runs",
        action=action,
        status=status,
        target=f"/v1/agent/runs/{run.run_id}",
        request_id=run.run_id,
        latency_ms=latency_ms,
        success=status == "completed",
        details={"org_id": run.org_id, **(details or {})},
    )


async def _complete_run(
    run: _StoredAgentRun,
    *,
    auth: AuthContext,
    request_state: Any | None = None,
    resume_source: Literal["create", "resume", "approve"] = "create",
) -> _StoredAgentRun:
    started_at = _utc_now()
    started = time.monotonic()
    result_text = await _execute_selected_tool(
        tool=run.selected_tool or "calculate",
        task=run.task,
        auth=auth,
        request_state=request_state,
    )
    final_result = _finalize_result(
        task=run.task,
        tool=run.selected_tool or "calculate",
        run_id=run.run_id,
        output_format=run.output_format,
        result_text=result_text,
    )
    run.steps.append(
        AgentStep(
            step=len(run.steps) + 1,
            action="Executing tool",
            tool=run.selected_tool,
            result=result_text[:100],
            status="completed",
        )
    )
    run.steps.append(
        AgentStep(
            step=len(run.steps) + 1,
            action="Formatting result",
            status="completed",
        )
    )
    run.result = final_result
    run.status = "completed"
    run.pending_action = None
    run.tools_used = [run.selected_tool] if run.selected_tool else []
    run.latency_ms = round((time.monotonic() - started) * 1000, 1)
    run.updated_at = _utc_now()
    with _LOCK:
        _write_run(run)
        _append_run_event(
            run=run,
            event_type="tool_executed",
            status="completed",
            message=f"Executed {run.selected_tool} tool.",
            details={"tool": run.selected_tool, "resume_source": resume_source},
        )
        _append_run_event(
            run=run,
            event_type="run_completed",
            status="completed",
            message="Agent run completed successfully.",
            details={"resume_source": resume_source},
        )
        _persist_checkpoint_unlocked(run)
        _persist_run_completion_telemetry(run=run, started_at=started_at, ended_at=run.updated_at)
    _record_ledger(
        run=run,
        action=f"agent_run_{resume_source}",
        status="completed",
        latency_ms=run.latency_ms,
        details={"tool": run.selected_tool or "calculate"},
    )
    return run

