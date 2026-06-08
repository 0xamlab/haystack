"""Public CRUD/lifecycle API: create_agent_run, get_agent_run, list_agent_runs, replay, fork, resume, cancel, approve.

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
from apps.api_server.services.agent_run_service._run_lifecycle import *  # noqa: F401, F403
from apps.api_server.services.agent_run_service._run_lifecycle import (
    _request_hash,
    _decision_hash_for_run,
    _runtime_manifest_metadata,
    _checkpoint_snapshot_payload,
    _persist_checkpoint_unlocked,
    _latest_checkpoint_for_run,
    _resolve_checkpoint_for_run,
    _select_tool,
    _initial_steps,
    _finalize_result,
    _run_sim,
    _execute_selected_tool,
    _record_ledger,
    _complete_run,
)



async def create_agent_run(
    payload: AgentRunCreateRequest,
    *,
    auth: AuthContext,
    request_state: Any | None = None,
) -> AgentRunResource:
    org_id = str(auth["org_id"])
    run_id = str(uuid.uuid4())
    available_tools = list(payload.tools or _DEFAULT_TOOLS)
    selected_tool = _select_tool(payload.task, available_tools)
    metadata = _runtime_manifest_metadata()
    policy = get_policy(org_id)
    now = _utc_now()
    status: AgentRunStatus = "running"
    pending_action: AgentRunPendingAction = None
    if payload.start_paused:
        status = "paused"
        pending_action = "resume"
    elif payload.approval_mode == "manual":
        status = "requires_approval"
        pending_action = "approve"
    run = _StoredAgentRun(
        run_id=run_id,
        org_id=org_id,
        status=status,
        task=payload.task,
        context=payload.context,
        output_format=payload.output_format,
        approval_mode=payload.approval_mode,
        pending_action=pending_action,
        max_steps=payload.max_steps,
        tools_available=available_tools,
        tools_used=[],
        selected_tool=selected_tool,
        result=None,
        steps=_initial_steps(payload.task, selected_tool),
        request_hash=_request_hash(payload, available_tools),
        decision_hash=None,
        policy_snapshot_id=policy.snapshot_id,
        schema_snapshot_id=metadata["schema_snapshot_id"],
        manifest_version=metadata["manifest_version"],
        replayable=True,
        artifact_refs=[],
        latest_checkpoint_id=None,
        checkpoint_count=0,
        source_run_id=None,
        source_checkpoint_id=None,
        created_at=now,
        updated_at=now,
        latency_ms=None,
    )
    with _LOCK:
        _write_run(run)
        _append_run_event(
            run=run,
            event_type="run_created",
            status=run.status,
            message="Agent run created.",
            details={"approval_mode": payload.approval_mode, "start_paused": payload.start_paused},
        )
        _append_run_event(
            run=run,
            event_type="tool_selected",
            status="completed",
            message=f"Selected {selected_tool} tool.",
            details={"tool": selected_tool},
        )
        if payload.start_paused:
            _append_run_event(
                run=run,
                event_type="run_paused",
                status="paused",
                message="Agent run paused before execution.",
                details={"pending_action": "resume"},
            )
        elif payload.approval_mode == "manual":
            _append_run_event(
                run=run,
                event_type="approval_required",
                status="requires_approval",
                message="Agent run is waiting for approval before tool execution.",
                details={"pending_action": "approve", "tool": selected_tool},
            )
        _persist_checkpoint_unlocked(run)
    _record_ledger(
        run=run,
        action="agent_run_create",
        status=run.status,
        details={"tool": selected_tool},
    )
    if run.status == "running":
        run = await _complete_run(run, auth=auth, request_state=request_state, resume_source="create")
    return AgentRunResource.model_validate(run.model_dump(mode="json"))


def get_agent_run(*, run_id: str, auth: AuthContext) -> AgentRunResource:
    run = _read_run(str(auth["org_id"]), run_id)
    return AgentRunResource.model_validate(run.model_dump(mode="json"))


def list_agent_runs(
    *,
    auth: AuthContext,
    page: int = 1,
    limit: int = 25,
    status: AgentRunStatus | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
) -> AgentRunListResponse:
    runs = _filter_runs(
        _list_runs(str(auth["org_id"])),
        status=status,
        request_hash=request_hash,
        policy_snapshot_id=policy_snapshot_id,
        schema_snapshot_id=schema_snapshot_id,
    )
    total = len(runs)
    start = (page - 1) * limit
    end = start + limit
    data = [
        AgentRunResource.model_validate(item.model_dump(mode="json"))
        for item in runs[start:end]
    ]
    pages = max(1, (total + limit - 1) // limit)
    return AgentRunListResponse(
        data=data,
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


def query_agent_run_mission_events(
    *,
    auth: AuthContext,
    page: int = 1,
    limit: int = 25,
    status: AgentRunStatus | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    run_id: str | None = None,
    event_type: str | None = None,
) -> AgentRunMissionEventListResponse:
    runs = _filter_runs(
        _list_runs(str(auth["org_id"])),
        status=status,
        request_hash=request_hash,
        policy_snapshot_id=policy_snapshot_id,
        schema_snapshot_id=schema_snapshot_id,
        run_id=run_id,
    )
    rows: list[AgentRunMissionEventListResource] = []
    for run in runs:
        for event in _read_mission_events(run.org_id, run.run_id):
            if event_type is not None and event.event_type != event_type:
                continue
            rows.append(
                AgentRunMissionEventListResource.model_validate(
                    {
                        **event.model_dump(mode="json"),
                        "run_id": run.run_id,
                        "run_status": run.status,
                    }
                )
            )
    rows.sort(key=lambda item: (item.event_ts, item.run_id, item.event_index), reverse=True)
    total = len(rows)
    start = (page - 1) * limit
    end = start + limit
    pages = max(1, (total + limit - 1) // limit)
    return AgentRunMissionEventListResponse(
        data=rows[start:end],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


def query_agent_run_telemetry(
    *,
    auth: AuthContext,
    page: int = 1,
    limit: int = 25,
    status: AgentRunStatus | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    run_id: str | None = None,
    telemetry_kind: str | None = None,
    module_name: str | None = None,
) -> AgentRunTelemetryListResponse:
    runs = _filter_runs(
        _list_runs(str(auth["org_id"])),
        status=status,
        request_hash=request_hash,
        policy_snapshot_id=policy_snapshot_id,
        schema_snapshot_id=schema_snapshot_id,
        run_id=run_id,
    )
    rows: list[AgentRunTelemetryBatchListResource] = []
    for run in runs:
        for batch in _read_telemetry_batches(run.org_id, run.run_id):
            if telemetry_kind is not None and batch.telemetry_kind != telemetry_kind:
                continue
            if module_name is not None and batch.module_name != module_name:
                continue
            rows.append(
                AgentRunTelemetryBatchListResource.model_validate(
                    {
                        **batch.model_dump(mode="json"),
                        "run_id": run.run_id,
                        "run_status": run.status,
                    }
                )
            )
    rows.sort(key=lambda item: (item.started_at, item.run_id, item.batch_id), reverse=True)
    total = len(rows)
    start = (page - 1) * limit
    end = start + limit
    pages = max(1, (total + limit - 1) // limit)
    return AgentRunTelemetryListResponse(
        data=rows[start:end],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


def get_agent_run_events(
    *,
    run_id: str,
    auth: AuthContext,
    limit: int = 1000,
) -> list[AgentRunEvent]:
    _read_run(str(auth["org_id"]), run_id)
    events = _read_events(str(auth["org_id"]), run_id)
    return events[-limit:]


def get_agent_run_mission_events(
    *,
    run_id: str,
    auth: AuthContext,
    limit: int = 1000,
) -> AgentRunMissionEventsResponse:
    org_id = str(auth["org_id"])
    _read_run(org_id, run_id)
    events = _read_mission_events(org_id, run_id)
    data = [
        AgentRunMissionEventResource.model_validate(item.model_dump(mode="json"))
        for item in events[-limit:]
    ]
    return AgentRunMissionEventsResponse(run_id=run_id, data=data, total_events=len(events))


def get_agent_run_checkpoints(
    *,
    run_id: str,
    auth: AuthContext,
) -> AgentRunCheckpointsResponse:
    org_id = str(auth["org_id"])
    _read_run(org_id, run_id)
    checkpoints = [_checkpoint_resource(item) for item in _read_checkpoints(org_id, run_id)]
    return AgentRunCheckpointsResponse(
        run_id=run_id,
        data=checkpoints,
        total_checkpoints=len(checkpoints),
    )


def query_agent_run_checkpoints(
    *,
    auth: AuthContext,
    page: int = 1,
    limit: int = 25,
    status: AgentRunStatus | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    run_id: str | None = None,
    checkpoint_id: str | None = None,
) -> AgentRunCheckpointListResponse:
    runs = _filter_runs(
        _list_runs(str(auth["org_id"])),
        status=status,
        request_hash=request_hash,
        policy_snapshot_id=policy_snapshot_id,
        schema_snapshot_id=schema_snapshot_id,
        run_id=run_id,
    )
    rows: list[AgentRunCheckpointListResource] = []
    for run in runs:
        for checkpoint in _read_checkpoints(run.org_id, run.run_id):
            if checkpoint_id is not None and checkpoint.checkpoint_id != checkpoint_id:
                continue
            rows.append(
                AgentRunCheckpointListResource.model_validate(
                    {
                        **checkpoint.model_dump(mode="json"),
                        "run_status": run.status,
                    }
                )
            )
    rows.sort(
        key=lambda item: (item.created_at, item.run_id, item.checkpoint_index),
        reverse=True,
    )
    total = len(rows)
    start = (page - 1) * limit
    end = start + limit
    pages = max(1, (total + limit - 1) // limit)
    return AgentRunCheckpointListResponse(
        data=rows[start:end],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


def get_agent_run_telemetry(
    *,
    run_id: str,
    auth: AuthContext,
    limit: int = 1000,
) -> AgentRunTelemetryResponse:
    org_id = str(auth["org_id"])
    _read_run(org_id, run_id)
    batches = _read_telemetry_batches(org_id, run_id)
    data = [
        AgentRunTelemetryBatchResource.model_validate(item.model_dump(mode="json"))
        for item in batches[-limit:]
    ]
    return AgentRunTelemetryResponse(run_id=run_id, data=data, total_batches=len(batches))


def replay_agent_run(
    *,
    run_id: str,
    auth: AuthContext,
    payload: AgentRunReplayRequest,
) -> AgentRunReplayResponse:
    run = _read_run(str(auth["org_id"]), run_id)
    checkpoint = _resolve_checkpoint_for_run(run, payload.checkpoint_id)
    snapshot_path = Path(checkpoint.snapshot_path)
    snapshot_text = snapshot_path.read_text(encoding="utf-8")
    snapshot_payload = json.loads(snapshot_text)
    snapshot_hash_payload = {
        "run": snapshot_payload["run"],
        "checkpoint": {
            **snapshot_payload["checkpoint"],
            "content_hash": "",
        },
    }
    compared_event_count = checkpoint.event_end_index - checkpoint.event_start_index + 1
    replay_status: Literal["matched", "mismatch"] = "matched"
    failure_code: str | None = None

    if _hash_payload(snapshot_hash_payload) != checkpoint.content_hash:
        replay_status = "mismatch"
        failure_code = "replay_mismatch"
    elif snapshot_payload["run"]["request_hash"] != checkpoint.request_hash:
        replay_status = "mismatch"
        failure_code = "replay_mismatch"
    elif snapshot_payload["run"]["decision_hash"] != checkpoint.decision_hash:
        replay_status = "mismatch"
        failure_code = "replay_mismatch"
    elif run.latest_checkpoint_id == checkpoint.checkpoint_id and run.decision_hash != checkpoint.decision_hash:
        replay_status = "mismatch"
        failure_code = "replay_mismatch"

    return AgentRunReplayResponse(
        run_id=run_id,
        checkpoint_id=checkpoint.checkpoint_id,
        replay_status=replay_status,
        compared_event_count=max(compared_event_count, 0),
        checkpoint_count=run.checkpoint_count,
        request_hash=checkpoint.request_hash,
        decision_hash=checkpoint.decision_hash,
        content_hash=checkpoint.content_hash,
        policy_snapshot_id=checkpoint.policy_snapshot_id,
        schema_snapshot_id=checkpoint.schema_snapshot_id,
        manifest_version=checkpoint.manifest_version,
        failure_code=failure_code,
        created_at=_utc_now(),
    )


def fork_agent_run(
    *,
    run_id: str,
    auth: AuthContext,
    payload: AgentRunForkRequest,
) -> AgentRunResource:
    org_id = str(auth["org_id"])
    source_run = _read_run(org_id, run_id)
    source_checkpoint = _resolve_checkpoint_for_run(source_run, payload.checkpoint_id)
    now = _utc_now()
    fork_run = _StoredAgentRun(
        run_id=str(uuid.uuid4()),
        org_id=org_id,
        status="paused",
        task=source_run.task,
        context=source_run.context,
        output_format=source_run.output_format,
        approval_mode=source_run.approval_mode,
        pending_action="resume",
        max_steps=source_run.max_steps,
        tools_available=list(source_run.tools_available),
        tools_used=[],
        selected_tool=source_run.selected_tool,
        result=None,
        steps=_initial_steps(source_run.task, source_run.selected_tool or "calculate"),
        request_hash=source_run.request_hash,
        decision_hash=None,
        policy_snapshot_id=source_checkpoint.policy_snapshot_id,
        schema_snapshot_id=source_checkpoint.schema_snapshot_id,
        manifest_version=source_checkpoint.manifest_version,
        replayable=source_run.replayable,
        artifact_refs=[],
        latest_checkpoint_id=None,
        checkpoint_count=0,
        source_run_id=source_run.run_id,
        source_checkpoint_id=source_checkpoint.checkpoint_id,
        created_at=now,
        updated_at=now,
        latency_ms=None,
    )
    with _LOCK:
        _write_run(fork_run)
        _append_run_event(
            run=fork_run,
            event_type="run_created",
            status="paused",
            message="Agent run forked from checkpoint.",
            details={
                "source_run_id": source_run.run_id,
                "source_checkpoint_id": source_checkpoint.checkpoint_id,
            },
        )
        _append_run_event(
            run=fork_run,
            event_type="tool_selected",
            status="completed",
            message=f"Selected {fork_run.selected_tool} tool.",
            details={"tool": fork_run.selected_tool},
        )
        _append_run_event(
            run=fork_run,
            event_type="run_paused",
            status="paused",
            message="Forked agent run paused before execution.",
            details={
                "pending_action": "resume",
                "source_run_id": source_run.run_id,
                "source_checkpoint_id": source_checkpoint.checkpoint_id,
            },
        )
        _persist_checkpoint_unlocked(fork_run)
    _record_ledger(
        run=fork_run,
        action="agent_run_fork",
        status="paused",
        details={
            "source_run_id": source_run.run_id,
            "source_checkpoint_id": source_checkpoint.checkpoint_id,
        },
    )
    return AgentRunResource.model_validate(fork_run.model_dump(mode="json"))


async def resume_agent_run(
    *,
    run_id: str,
    auth: AuthContext,
    request_state: Any | None = None,
) -> AgentRunResource:
    org_id = str(auth["org_id"])
    run = _read_run(org_id, run_id)
    if run.status != "paused":
        raise AgentRunServiceError(
            "agent_run_invalid_state",
            f"Agent run '{run_id}' is not paused.",
            {"run_id": run_id, "status": run.status, "expected_status": "paused"},
        )
    run.updated_at = _utc_now()
    if run.approval_mode == "manual":
        run.status = "requires_approval"
        run.pending_action = "approve"
        with _LOCK:
            _write_run(run)
            _append_run_event(
                run=run,
                event_type="run_resumed",
                status="requires_approval",
                message="Agent run resumed and is waiting for approval.",
                details={"pending_action": "approve"},
            )
            _persist_checkpoint_unlocked(run)
        _record_ledger(run=run, action="agent_run_resume", status="requires_approval")
        return AgentRunResource.model_validate(run.model_dump(mode="json"))
    with _LOCK:
        _append_run_event(
            run=run,
            event_type="run_resumed",
            status="running",
            message="Agent run resumed.",
        )
    run.status = "running"
    run.pending_action = None
    with _LOCK:
        _write_run(run)
        _persist_checkpoint_unlocked(run)
    return AgentRunResource.model_validate(
        (
            await _complete_run(
                run,
                auth=auth,
                request_state=request_state,
                resume_source="resume",
            )
        ).model_dump(mode="json")
    )


def cancel_agent_run(*, run_id: str, auth: AuthContext) -> AgentRunResource:
    org_id = str(auth["org_id"])
    run = _read_run(org_id, run_id)
    if run.status not in {"paused", "requires_approval"}:
        raise AgentRunServiceError(
            "agent_run_invalid_state",
            f"Agent run '{run_id}' cannot be cancelled from status '{run.status}'.",
            {"run_id": run_id, "status": run.status},
        )
    run.status = "cancelled"
    run.pending_action = None
    run.updated_at = _utc_now()
    with _LOCK:
        _write_run(run)
        _append_run_event(
            run=run,
            event_type="run_cancelled",
            status="cancelled",
            message="Agent run cancelled.",
        )
        _persist_checkpoint_unlocked(run)
    _record_ledger(run=run, action="agent_run_cancel", status="cancelled")
    return AgentRunResource.model_validate(run.model_dump(mode="json"))


async def approve_agent_run(
    *,
    run_id: str,
    auth: AuthContext,
    request_state: Any | None = None,
) -> AgentRunResource:
    org_id = str(auth["org_id"])
    run = _read_run(org_id, run_id)
    if run.status != "requires_approval":
        raise AgentRunServiceError(
            "agent_run_invalid_state",
            f"Agent run '{run_id}' is not waiting for approval.",
            {"run_id": run_id, "status": run.status, "expected_status": "requires_approval"},
        )
    run.updated_at = _utc_now()
    with _LOCK:
        _append_run_event(
            run=run,
            event_type="run_approved",
            status="approved",
            message="Agent run approved for execution.",
        )
    run.pending_action = None
    run.status = "running"
    with _LOCK:
        _write_run(run)
        _persist_checkpoint_unlocked(run)
    return AgentRunResource.model_validate(
        (
            await _complete_run(
                run,
                auth=auth,
                request_state=request_state,
                resume_source="approve",
            )
        ).model_dump(mode="json")
    )
