from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from apps.api_server.schemas.products import AgentStep

__all__ = [
    "AgentRunAction",
    "AgentRunCheckpointResource",
    "AgentRunCheckpointListResource",
    "AgentRunCheckpointsResponse",
    "AgentRunCheckpointListResponse",
    "AgentRunCreateRequest",
    "AgentRunEvent",
    "AgentRunEventsResponse",
    "AgentRunMissionEventResource",
    "AgentRunMissionEventsResponse",
    "AgentRunPendingAction",
    "AgentRunForkRequest",
    "AgentRunListResponse",
    "AgentRunReplayRequest",
    "AgentRunReplayResponse",
    "AgentRunReplayStatus",
    "AgentRunResource",
    "AgentRunStatus",
    "AgentRunTelemetryBatchListResource",
    "AgentRunTelemetryListResponse",
    "AgentRunTelemetryBatchResource",
    "AgentRunTelemetryResponse",
    "AgentRunMissionEventListResource",
    "AgentRunMissionEventListResponse",
]

AgentRunStatus = Literal["running", "paused", "requires_approval", "completed", "cancelled"]
AgentRunAction = Literal["auto", "manual"]
AgentRunPendingAction = Literal["resume", "approve"] | None
AgentRunReplayStatus = Literal["matched", "mismatch"]


class AgentRunCreateRequest(BaseModel):
    """Create a persisted agent run lifecycle resource."""

    task: str = Field(..., description="What should the agent do?", min_length=5)
    context: dict[str, Any] | None = Field(None, description="Additional context or data")
    tools: list[str] | None = Field(
        None,
        description="Tools to make available: search, simulate, optimize, calculate, summarize",
    )
    max_steps: int = Field(10, ge=1, le=50, description="Maximum execution steps")
    output_format: str = Field("text", description="Output format: text, json, markdown")
    approval_mode: AgentRunAction = Field(
        "auto",
        description="Execution mode: auto executes immediately, manual waits for approval.",
    )
    start_paused: bool = Field(
        False,
        description="If true, persist the run in paused state until /resume is called.",
    )


class AgentRunResource(BaseModel):
    run_id: str
    status: AgentRunStatus
    task: str
    output_format: str
    approval_mode: AgentRunAction
    pending_action: AgentRunPendingAction = None
    selected_tool: str | None = None
    result: str | dict[str, Any] | None = None
    tools_available: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    steps: list[AgentStep] = Field(default_factory=list)
    request_hash: str | None = None
    decision_hash: str | None = None
    policy_snapshot_id: str | None = None
    schema_snapshot_id: str | None = None
    manifest_version: str | None = None
    replayable: bool = False
    artifact_refs: list[str] = Field(default_factory=list)
    latest_checkpoint_id: str | None = None
    checkpoint_count: int = Field(default=0, ge=0)
    source_run_id: str | None = None
    source_checkpoint_id: str | None = None
    created_at: datetime
    updated_at: datetime
    latency_ms: float | None = None


class AgentRunListResponse(BaseModel):
    object: str = "list"
    data: list[AgentRunResource]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)
    pages: int = Field(ge=1)


class AgentRunCheckpointResource(BaseModel):
    checkpoint_id: str
    checkpoint_index: int = Field(ge=1)
    run_id: str
    parent_checkpoint_id: str | None = None
    status: AgentRunStatus
    event_start_index: int = Field(ge=0)
    event_end_index: int = Field(ge=0)
    request_hash: str
    decision_hash: str
    content_hash: str
    policy_snapshot_id: str
    schema_snapshot_id: str
    manifest_version: str
    artifact_refs: list[str] = Field(default_factory=list)
    created_at: datetime


class AgentRunCheckpointsResponse(BaseModel):
    object: str = "list"
    run_id: str
    data: list[AgentRunCheckpointResource]
    total_checkpoints: int = Field(ge=0)


class AgentRunCheckpointListResource(AgentRunCheckpointResource):
    run_status: AgentRunStatus


class AgentRunCheckpointListResponse(BaseModel):
    object: str = "list"
    data: list[AgentRunCheckpointListResource]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)
    pages: int = Field(ge=1)


class AgentRunReplayRequest(BaseModel):
    checkpoint_id: str | None = Field(
        default=None,
        description="Optional checkpoint to replay from. Defaults to the latest checkpoint.",
    )


class AgentRunReplayResponse(BaseModel):
    object: str = "agent_run_replay"
    run_id: str
    checkpoint_id: str
    replay_status: AgentRunReplayStatus
    compared_event_count: int = Field(ge=0)
    checkpoint_count: int = Field(ge=0)
    request_hash: str
    decision_hash: str
    content_hash: str
    policy_snapshot_id: str
    schema_snapshot_id: str
    manifest_version: str
    failure_code: str | None = None
    created_at: datetime


class AgentRunForkRequest(BaseModel):
    checkpoint_id: str | None = Field(
        default=None,
        description="Optional checkpoint to fork from. Defaults to the latest checkpoint.",
    )


class AgentRunEvent(BaseModel):
    event_id: str
    event_type: str
    status: str
    message: str
    created_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class AgentRunEventsResponse(BaseModel):
    object: str = "list"
    run_id: str
    data: list[AgentRunEvent]
    total_events: int = Field(ge=0)


class AgentRunMissionEventResource(BaseModel):
    mission_id: str
    thread_id: str
    tenant_scope: str
    workspace_scope: str
    event_index: int = Field(ge=0)
    superstep: int = Field(ge=0)
    node_name: str
    event_type: str
    event_message: str | None = None
    details_json: str | None = None
    event_ts: datetime
    request_hash: str
    policy_snapshot_id: str
    schema_snapshot_id: str
    manifest_version: str
    checkpoint_id: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    failure_code: str | None = None
    latency_ms: int | None = None
    cost_usd_micros: int | None = None


class AgentRunMissionEventsResponse(BaseModel):
    object: str = "list"
    run_id: str
    data: list[AgentRunMissionEventResource]
    total_events: int = Field(ge=0)


class AgentRunMissionEventListResource(AgentRunMissionEventResource):
    run_id: str
    run_status: AgentRunStatus


class AgentRunMissionEventListResponse(BaseModel):
    object: str = "list"
    data: list[AgentRunMissionEventListResource]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)
    pages: int = Field(ge=1)


class AgentRunTelemetryBatchResource(BaseModel):
    batch_id: str
    telemetry_kind: str
    module_name: str
    tenant_scope: str
    request_hash: str
    started_at: datetime
    ended_at: datetime
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    latency_ms_p95: float = Field(ge=0)
    cost_usd_micros: int = Field(ge=0)


class AgentRunTelemetryResponse(BaseModel):
    object: str = "list"
    run_id: str
    data: list[AgentRunTelemetryBatchResource]
    total_batches: int = Field(ge=0)


class AgentRunTelemetryBatchListResource(AgentRunTelemetryBatchResource):
    run_id: str
    run_status: AgentRunStatus


class AgentRunTelemetryListResponse(BaseModel):
    object: str = "list"
    data: list[AgentRunTelemetryBatchListResource]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)
    pages: int = Field(ge=1)
