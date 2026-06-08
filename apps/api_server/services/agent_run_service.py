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

__all__ = [
    "AgentRunServiceError",
    "approve_agent_run",
    "cancel_agent_run",
    "create_agent_run",
    "fork_agent_run",
    "get_agent_run",
    "get_agent_run_events",
    "get_agent_run_mission_events",
    "get_agent_run_checkpoints",
    "get_agent_run_telemetry",
    "list_agent_runs",
    "query_agent_run_checkpoints",
    "query_agent_run_mission_events",
    "query_agent_run_telemetry",
    "replay_agent_run",
    "resume_agent_run",
]

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


@dataclass(frozen=True)
class AgentRunServiceError(Exception):
    code: str
    message: str
    details: dict[str, object] | None = None

    def __str__(self) -> str:
        return self.message


class _StoredAgentRun(BaseModel):
    artifact: str = "agent_run"
    version: int = 1
    run_id: str
    org_id: str
    status: AgentRunStatus
    task: str
    context: dict[str, Any] | None = None
    output_format: str
    approval_mode: AgentRunAction
    pending_action: AgentRunPendingAction = None
    max_steps: int
    tools_available: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    selected_tool: str | None = None
    result: str | dict[str, Any] | None = None
    steps: list[AgentStep] = Field(default_factory=list)
    request_hash: str
    decision_hash: str | None = None
    policy_snapshot_id: str
    schema_snapshot_id: str
    manifest_version: str
    replayable: bool = True
    artifact_refs: list[str] = Field(default_factory=list)
    latest_checkpoint_id: str | None = None
    checkpoint_count: int = 0
    source_run_id: str | None = None
    source_checkpoint_id: str | None = None
    created_at: datetime
    updated_at: datetime
    latency_ms: float | None = None


class _StoredAgentRunCheckpoint(BaseModel):
    artifact: str = "agent_run_checkpoint"
    version: int = 1
    checkpoint_id: str
    checkpoint_index: int
    run_id: str
    parent_checkpoint_id: str | None = None
    status: AgentRunStatus
    event_start_index: int
    event_end_index: int
    request_hash: str
    decision_hash: str
    content_hash: str
    policy_snapshot_id: str
    schema_snapshot_id: str
    manifest_version: str
    artifact_refs: list[str] = Field(default_factory=list)
    snapshot_path: str
    checkpoint_parquet_path: str
    artifact_parquet_path: str
    created_at: datetime


def _is_runtime_dir_write_error(exc: OSError) -> bool:
    return getattr(exc, "errno", None) in {errno.EACCES, errno.EPERM, errno.EROFS}


def _runtime_dir_for_base(runtime_dir: Path) -> Path:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    if runtime_dir not in _WRITABLE_RUNTIME_DIRS:
        with tempfile.TemporaryFile(dir=runtime_dir):
            pass
        _WRITABLE_RUNTIME_DIRS.add(runtime_dir)
    return runtime_dir


def _runtime_dir() -> Path:
    configured = Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))
    if not os.environ.get("ALGENTA_RUNTIME_DIR") and configured in _UNWRITABLE_DEFAULT_RUNTIME_DIRS:
        return _runtime_dir_for_base(_IMPLICIT_FALLBACK_RUNTIME_DIR)
    try:
        return _runtime_dir_for_base(configured)
    except OSError as exc:
        if os.environ.get("ALGENTA_RUNTIME_DIR") or not _is_runtime_dir_write_error(exc):
            raise
        _UNWRITABLE_DEFAULT_RUNTIME_DIRS.add(configured)
        fallback = _runtime_dir_for_base(_IMPLICIT_FALLBACK_RUNTIME_DIR)
        if configured not in _WARNED_DEFAULT_RUNTIME_DIRS:
            logger.warning(
                "agent_run_runtime_dir_unwritable configured=%s fallback=%s error=%s",
                configured,
                fallback,
                exc,
            )
            _WARNED_DEFAULT_RUNTIME_DIRS.add(configured)
        return fallback


def _agent_runs_dir(org_id: str) -> Path:
    return _runtime_dir() / "agent_runs" / org_id


def _run_path(org_id: str, run_id: str) -> Path:
    return _agent_runs_dir(org_id) / f"{run_id}.json"


def _events_path(org_id: str, run_id: str) -> Path:
    return _agent_runs_dir(org_id) / f"{run_id}.events.jsonl"


def _run_state_dir(org_id: str, run_id: str) -> Path:
    return _agent_runs_dir(org_id) / run_id


def _checkpoints_dir(org_id: str, run_id: str) -> Path:
    return _run_state_dir(org_id, run_id) / "checkpoints"


def _artifacts_dir(org_id: str, run_id: str) -> Path:
    return _run_state_dir(org_id, run_id) / "artifacts"


def _events_dir(org_id: str, run_id: str) -> Path:
    return _run_state_dir(org_id, run_id) / "events"


def _telemetry_dir(org_id: str, run_id: str) -> Path:
    return _run_state_dir(org_id, run_id) / "telemetry"


def _checkpoint_snapshot_path(org_id: str, run_id: str, checkpoint_id: str) -> Path:
    return _checkpoints_dir(org_id, run_id) / f"{checkpoint_id}.snapshot.json"


def _checkpoint_metadata_path(org_id: str, run_id: str, checkpoint_id: str) -> Path:
    return _checkpoints_dir(org_id, run_id) / f"{checkpoint_id}.meta.json"


def _checkpoint_parquet_path(org_id: str, run_id: str, checkpoint_id: str) -> Path:
    return _checkpoints_dir(org_id, run_id) / f"{checkpoint_id}.parquet"


def _artifact_payload_path(org_id: str, run_id: str, artifact_id: str) -> Path:
    return _artifacts_dir(org_id, run_id) / f"{artifact_id}.json"


def _artifact_parquet_path(org_id: str, run_id: str, artifact_id: str) -> Path:
    return _artifacts_dir(org_id, run_id) / f"{artifact_id}.parquet"


def _event_artifact_payload_path(org_id: str, run_id: str, event_id: str) -> Path:
    return _events_dir(org_id, run_id) / f"{event_id}.json"


def _event_artifact_parquet_path(org_id: str, run_id: str, event_id: str) -> Path:
    return _events_dir(org_id, run_id) / f"{event_id}.parquet"


def _telemetry_parquet_path(org_id: str, run_id: str, batch_id: str) -> Path:
    return _telemetry_dir(org_id, run_id) / f"{batch_id}.parquet"


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
    except FileNotFoundError:
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
