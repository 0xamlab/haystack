"""agent_run_service — public facade.

The implementation is split into _<name>.py submodules of this package
for maintainability (each well under 1000 lines). This __init__.py
re-exports the complete public API so existing
`from apps.api_server.services.agent_run_service import X` imports
continue to work unchanged.
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


from apps.api_server.services.agent_run_service._data_models import *  # noqa: E402, F401, F403
from apps.api_server.services.agent_run_service._data_models import (  # noqa: E402, F401
    _StoredAgentRun,
    _StoredAgentRunCheckpoint,
)
from apps.api_server.services.agent_run_service._path_helpers import *  # noqa: E402, F401, F403
from apps.api_server.services.agent_run_service._path_helpers import (  # noqa: E402, F401
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
from apps.api_server.services.agent_run_service._read_helpers import *  # noqa: E402, F401, F403
from apps.api_server.services.agent_run_service._read_helpers import (  # noqa: E402, F401
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
from apps.api_server.services.agent_run_service._io_helpers import *  # noqa: E402, F401, F403
from apps.api_server.services.agent_run_service._io_helpers import (  # noqa: E402, F401
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
from apps.api_server.services.agent_run_service._run_lifecycle import *  # noqa: E402, F401, F403
from apps.api_server.services.agent_run_service._run_lifecycle import (  # noqa: E402, F401
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
from apps.api_server.services.agent_run_service._public_api import *  # noqa: E402, F401, F403
