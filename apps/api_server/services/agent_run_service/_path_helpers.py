"""Runtime directory layout + per-run/checkpoint/artifact path helpers.

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
    # Test code monkey-patches _IMPLICIT_FALLBACK_RUNTIME_DIR and
    # _runtime_dir_for_base on the facade — look up via facade so the patches
    # propagate into this submodule.
    from apps.api_server.services import agent_run_service as _facade
    fallback_dir = _facade._IMPLICIT_FALLBACK_RUNTIME_DIR
    runtime_dir_for_base = _facade._runtime_dir_for_base
    configured = Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))
    if not os.environ.get("ALGENTA_RUNTIME_DIR") and configured in _UNWRITABLE_DEFAULT_RUNTIME_DIRS:
        return runtime_dir_for_base(fallback_dir)
    try:
        return runtime_dir_for_base(configured)
    except OSError as exc:
        if os.environ.get("ALGENTA_RUNTIME_DIR") or not _is_runtime_dir_write_error(exc):
            raise
        _UNWRITABLE_DEFAULT_RUNTIME_DIRS.add(configured)
        fallback = runtime_dir_for_base(fallback_dir)
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

