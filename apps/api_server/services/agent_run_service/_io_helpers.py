"""Hash/JSON write helpers + _persist_run_event_artifact + _persist_run_completion_telemetry + _append_run_event.

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


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=True)


def _hash_payload(payload: Any) -> str:
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _write_run(run: _StoredAgentRun) -> None:
    _write_json(_run_path(run.org_id, run.run_id), run.model_dump(mode="json"))


def _persist_run_event_artifact(
    *,
    run: _StoredAgentRun,
    event: AgentRunEvent,
    event_index: int,
) -> None:
    event_payload = event.model_dump(mode="json")
    event_payload_path = _event_artifact_payload_path(run.org_id, run.run_id, event.event_id)
    _write_json(event_payload_path, event_payload)
    mission_event = MissionEvent(
        mission_id=run.run_id,
        thread_id=run.run_id,
        tenant_scope=run.org_id,
        workspace_scope=run.run_id,
        event_index=event_index,
        superstep=run.checkpoint_count + 1,
        node_name="agent_run_service",
        event_type=event.event_type,
        event_message=event.message,
        details_json=_json_dumps(event.details) if event.details else None,
        event_ts=event.created_at,
        request_hash=run.request_hash,
        policy_snapshot_id=run.policy_snapshot_id,
        schema_snapshot_id=run.schema_snapshot_id,
        manifest_version=run.manifest_version,
        checkpoint_id=run.latest_checkpoint_id,
        artifact_refs=[event.event_id],
        latency_ms=None,
        cost_usd_micros=None,
    )
    event_parquet_path = _event_artifact_parquet_path(run.org_id, run.run_id, event.event_id)
    event_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    event_parquet_path.write_bytes(
        parquet_bytes_from_records([mission_event], record_type=MissionEvent)
    )
    artifact_record = ArtifactRecord(
        artifact_id=event.event_id,
        artifact_kind=_RUN_EVENT_ARTIFACT_KIND,
        tenant_scope=run.org_id,
        workspace_scope=run.run_id,
        schema_revision=_RUN_EVENT_SCHEMA_REVISION,
        content_hash=_hash_payload(event_payload),
        storage_format="json",
        storage_path=str(event_payload_path),
        provenance_parent_hashes=[run.request_hash],
        created_at=event.created_at,
    )
    artifact_parquet_path = _artifact_parquet_path(run.org_id, run.run_id, event.event_id)
    artifact_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_parquet_path.write_bytes(
        parquet_bytes_from_records([artifact_record], record_type=ArtifactRecord)
    )


def _persist_run_completion_telemetry(
    *,
    run: _StoredAgentRun,
    started_at: datetime,
    ended_at: datetime,
) -> None:
    batch_id = f"telemetry_{uuid.uuid4().hex}"
    telemetry = TelemetryBatch(
        batch_id=batch_id,
        telemetry_kind="agent_run_completion",
        module_name="agent_run_service",
        tenant_scope=run.org_id,
        request_hash=run.request_hash,
        started_at=started_at,
        ended_at=ended_at,
        success_count=1,
        failure_count=0,
        latency_ms_p95=float(run.latency_ms or 0.0),
        cost_usd_micros=0,
    )
    path = _telemetry_parquet_path(run.org_id, run.run_id, batch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(parquet_bytes_from_records([telemetry], record_type=TelemetryBatch))


def _append_run_event(
    *,
    run: _StoredAgentRun,
    event_type: str,
    status: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> AgentRunEvent:
    event_index = len(_read_events(run.org_id, run.run_id))
    event = AgentRunEvent(
        event_id=f"evt_{uuid.uuid4().hex}",
        event_type=event_type,
        status=status,
        message=message,
        created_at=_utc_now(),
        details=details or {},
    )
    path = _events_path(run.org_id, run.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.model_dump(mode="json"), sort_keys=True) + "\n")
    _persist_run_event_artifact(run=run, event=event, event_index=event_index)
    return event

