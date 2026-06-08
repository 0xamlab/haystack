"""AgentRunServiceError + _StoredAgentRun + _StoredAgentRunCheckpoint.

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

