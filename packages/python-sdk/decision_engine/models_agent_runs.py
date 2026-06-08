from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


AgentRunStatus = Literal["running", "paused", "requires_approval", "completed", "cancelled"]
AgentRunAction = Literal["auto", "manual"]
AgentRunPendingAction = Literal["resume", "approve"] | None
AgentRunReplayStatus = Literal["matched", "mismatch"]


class AgentStepResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    step_number: int = Field(validation_alias=AliasChoices("step_number", "step"))
    tool_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("tool_name", "tool"),
    )
    action: str | None = None
    result: str | None = None
    status: str | None = None
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    rationale: str | None = None


class AgentRunResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

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
    steps: list[AgentStepResult] = Field(default_factory=list)
    request_hash: str | None = None
    decision_hash: str | None = None
    policy_snapshot_id: str | None = None
    schema_snapshot_id: str | None = None
    manifest_version: str | None = None
    replayable: bool = False
    artifact_refs: list[str] = Field(default_factory=list)
    latest_checkpoint_id: str | None = None
    checkpoint_count: int = 0
    source_run_id: str | None = None
    source_checkpoint_id: str | None = None
    created_at: datetime
    updated_at: datetime
    latency_ms: float | None = None


class AgentRunListResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: str = "list"
    data: list[AgentRunResult] = Field(default_factory=list)
    total: int
    page: int
    limit: int
    pages: int


class AgentRunEventResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    event_id: str
    event_type: str
    status: str
    message: str
    created_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class AgentRunEventsResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: str = "list"
    run_id: str
    data: list[AgentRunEventResult] = Field(default_factory=list)
    total_events: int


class AgentRunMissionEventResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    mission_id: str
    thread_id: str
    tenant_scope: str
    workspace_scope: str
    event_index: int
    superstep: int
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


class AgentRunMissionEventListResult(AgentRunMissionEventResult):
    model_config = ConfigDict(extra="allow", defer_build=True)

    run_id: str
    run_status: AgentRunStatus


class AgentRunMissionEventsResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: str = "list"
    run_id: str
    data: list[AgentRunMissionEventResult] = Field(default_factory=list)
    total_events: int


class AgentRunMissionEventListResponseResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: str = "list"
    data: list[AgentRunMissionEventListResult] = Field(default_factory=list)
    total: int
    page: int
    limit: int
    pages: int


class AgentRunStreamEventResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    type: Literal["agent.run.event", "agent.run.completed"]
    run_id: str
    event: AgentRunEventResult | None = None
    status: AgentRunStatus | None = None
    total_events: int | None = None


class AgentRunCheckpointResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

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
    created_at: datetime


class AgentRunCheckpointListResult(AgentRunCheckpointResult):
    model_config = ConfigDict(extra="allow", defer_build=True)

    run_status: AgentRunStatus


class AgentRunCheckpointsResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: str = "list"
    run_id: str
    data: list[AgentRunCheckpointResult] = Field(default_factory=list)
    total_checkpoints: int


class AgentRunCheckpointListResponseResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: str = "list"
    data: list[AgentRunCheckpointListResult] = Field(default_factory=list)
    total: int
    page: int
    limit: int
    pages: int


class AgentRunReplayResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: str = "agent_run_replay"
    run_id: str
    checkpoint_id: str
    replay_status: AgentRunReplayStatus
    compared_event_count: int
    checkpoint_count: int
    request_hash: str
    decision_hash: str
    content_hash: str
    policy_snapshot_id: str
    schema_snapshot_id: str
    manifest_version: str
    failure_code: str | None = None
    created_at: datetime


class AgentRunTelemetryBatchResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    batch_id: str
    telemetry_kind: str
    module_name: str
    tenant_scope: str
    request_hash: str
    started_at: datetime
    ended_at: datetime
    success_count: int
    failure_count: int
    latency_ms_p95: float
    cost_usd_micros: int


class AgentRunTelemetryBatchListResult(AgentRunTelemetryBatchResult):
    model_config = ConfigDict(extra="allow", defer_build=True)

    run_id: str
    run_status: AgentRunStatus


class AgentRunTelemetryResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: str = "list"
    run_id: str
    data: list[AgentRunTelemetryBatchResult] = Field(default_factory=list)
    total_batches: int


class AgentRunTelemetryListResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: str = "list"
    data: list[AgentRunTelemetryBatchListResult] = Field(default_factory=list)
    total: int
    page: int
    limit: int
    pages: int
