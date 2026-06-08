"""_read_run / _list_runs / _filter_runs / _read_events / _read_mission_events / _read_telemetry_batches / _read_checkpoints / _read_checkpoint.

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


def _read_run(org_id: str, run_id: str) -> _StoredAgentRun:
    path = _run_path(org_id, run_id)
    if not path.exists():
        raise AgentRunServiceError(
            "agent_run_not_found",
            f"Agent run '{run_id}' was not found.",
            {"run_id": run_id},
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _StoredAgentRun.model_validate(payload)


def _list_runs(org_id: str) -> list[_StoredAgentRun]:
    directory = _agent_runs_dir(org_id)
    if not directory.exists():
        return []
    runs: list[_StoredAgentRun] = []
    for path in sorted(directory.glob("*.json")):
        if path.name.endswith(".events.jsonl"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        runs.append(_StoredAgentRun.model_validate(payload))
    runs.sort(key=lambda item: (item.created_at, item.run_id), reverse=True)
    return runs


def _filter_runs(
    runs: list[_StoredAgentRun],
    *,
    status: AgentRunStatus | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    run_id: str | None = None,
) -> list[_StoredAgentRun]:
    filtered = runs
    if status is not None:
        filtered = [item for item in filtered if item.status == status]
    if request_hash is not None:
        filtered = [item for item in filtered if item.request_hash == request_hash]
    if policy_snapshot_id is not None:
        filtered = [item for item in filtered if item.policy_snapshot_id == policy_snapshot_id]
    if schema_snapshot_id is not None:
        filtered = [item for item in filtered if item.schema_snapshot_id == schema_snapshot_id]
    if run_id is not None:
        filtered = [item for item in filtered if item.run_id == run_id]
    return filtered


def _read_events(org_id: str, run_id: str) -> list[AgentRunEvent]:
    path = _events_path(org_id, run_id)
    if not path.exists():
        return []
    events: list[AgentRunEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(AgentRunEvent.model_validate_json(line))
    return events


def _read_mission_events(org_id: str, run_id: str) -> list[MissionEvent]:
    directory = _events_dir(org_id, run_id)
    if not directory.exists():
        return []
    events: list[MissionEvent] = []
    for path in sorted(directory.glob("*.parquet")):
        table = table_from_parquet_bytes(path.read_bytes())
        validate_table_schema(table, MissionEvent)
        for row in table.to_pylist():
            events.append(MissionEvent.model_validate(row))
    events.sort(key=lambda item: item.event_index)
    return events


def _read_telemetry_batches(org_id: str, run_id: str) -> list[TelemetryBatch]:
    directory = _telemetry_dir(org_id, run_id)
    if not directory.exists():
        return []
    batches: list[TelemetryBatch] = []
    for path in sorted(directory.glob("*.parquet")):
        table = table_from_parquet_bytes(path.read_bytes())
        validate_table_schema(table, TelemetryBatch)
        for row in table.to_pylist():
            batches.append(TelemetryBatch.model_validate(row))
    batches.sort(key=lambda item: item.started_at)
    return batches


def _read_checkpoints(org_id: str, run_id: str) -> list[_StoredAgentRunCheckpoint]:
    directory = _checkpoints_dir(org_id, run_id)
    if not directory.exists():
        return []
    checkpoints: list[_StoredAgentRunCheckpoint] = []
    for path in sorted(directory.glob("*.meta.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        checkpoints.append(_StoredAgentRunCheckpoint.model_validate(payload))
    checkpoints.sort(key=lambda item: item.checkpoint_index)
    return checkpoints


def _read_checkpoint(org_id: str, run_id: str, checkpoint_id: str) -> _StoredAgentRunCheckpoint:
    path = _checkpoint_metadata_path(org_id, run_id, checkpoint_id)
    if not path.exists():
        raise AgentRunServiceError(
            "agent_run_checkpoint_not_found",
            f"Checkpoint '{checkpoint_id}' was not found for run '{run_id}'.",
            {"run_id": run_id, "checkpoint_id": checkpoint_id},
        )
    return _StoredAgentRunCheckpoint.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )


def _checkpoint_resource(checkpoint: _StoredAgentRunCheckpoint) -> AgentRunCheckpointResource:
    return AgentRunCheckpointResource.model_validate(checkpoint.model_dump(mode="json"))
