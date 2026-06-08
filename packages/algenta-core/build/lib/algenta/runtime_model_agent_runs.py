from __future__ import annotations

from datetime import datetime
from dataclasses import asdict, dataclass, field
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping, jsonable


def _require_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _optional_string(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _optional_mapping(data: dict[str, Any], key: str, context: str) -> dict[str, Any] | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError(f"{context}.{key} must be a mapping.")
    return value


def _require_integer(data: dict[str, Any], key: str, context: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer.")
    return value


def _optional_number(data: dict[str, Any], key: str, context: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context}.{key} must be a number.")
    return float(value)


def _optional_integer(data: dict[str, Any], key: str, context: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer.")
    return value


def _require_string_list(data: dict[str, Any], key: str, context: str) -> list[str]:
    raw = data.get(key) or []
    if not isinstance(raw, list):
        raise TypeError(f"{context}.{key} must be a list.")
    result: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item:
            raise TypeError(f"{context}.{key}.{index} must be a non-empty string.")
        result.append(item)
    return result


def _require_datetime_text(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


@dataclass(frozen=True)
class AgentStepOutput:
    step_number: int
    tool_name: str | None = None
    action: str | None = None
    status: str | None = None
    result: str | None = None
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    rationale: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> AgentStepOutput:
        context = "agent_run.steps.item"
        data = coerce_payload_mapping(payload)
        step_number = _optional_integer(data, "step_number", context)
        if step_number is None:
            step_number = _require_integer(data, "step", context)
        return cls(
            step_number=step_number,
            tool_name=_optional_string(data, "tool_name", context)
            or _optional_string(data, "tool", context),
            action=_optional_string(data, "action", context),
            status=_optional_string(data, "status", context),
            result=_optional_string(data, "result", context),
            input=_optional_mapping(data, "input", context),
            output=_optional_mapping(data, "output", context),
            rationale=_optional_string(data, "rationale", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunOutput:
    run_id: str
    status: str
    task: str
    output_format: str
    approval_mode: str
    pending_action: str | None = None
    selected_tool: str | None = None
    result: str | dict[str, Any] | None = None
    tools_available: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    steps: list[AgentStepOutput] = field(default_factory=list)
    request_hash: str | None = None
    decision_hash: str | None = None
    policy_snapshot_id: str | None = None
    schema_snapshot_id: str | None = None
    manifest_version: str | None = None
    replayable: bool = False
    artifact_refs: list[str] = field(default_factory=list)
    latest_checkpoint_id: str | None = None
    checkpoint_count: int = 0
    source_run_id: str | None = None
    source_checkpoint_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    latency_ms: float | None = None

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunOutput:
        context = "agent_run"
        data = coerce_payload_mapping(payload)
        raw_steps = data.get("steps") or []
        if not isinstance(raw_steps, list):
            raise TypeError(f"{context}.steps must be a list.")
        result = data.get("result")
        if result is not None and not isinstance(result, (str, dict)):
            raise TypeError(f"{context}.result must be a string or mapping.")
        return cls(
            run_id=_require_string(data, "run_id", context),
            status=_require_string(data, "status", context),
            task=_require_string(data, "task", context),
            output_format=_require_string(data, "output_format", context),
            approval_mode=_require_string(data, "approval_mode", context),
            pending_action=_optional_string(data, "pending_action", context),
            selected_tool=_optional_string(data, "selected_tool", context),
            result=result,
            tools_available=_require_string_list(data, "tools_available", context),
            tools_used=_require_string_list(data, "tools_used", context),
            steps=[AgentStepOutput.from_api(item) for item in raw_steps],
            request_hash=_optional_string(data, "request_hash", context),
            decision_hash=_optional_string(data, "decision_hash", context),
            policy_snapshot_id=_optional_string(data, "policy_snapshot_id", context),
            schema_snapshot_id=_optional_string(data, "schema_snapshot_id", context),
            manifest_version=_optional_string(data, "manifest_version", context),
            replayable=bool(data.get("replayable", False)),
            artifact_refs=_require_string_list(data, "artifact_refs", context),
            latest_checkpoint_id=_optional_string(data, "latest_checkpoint_id", context),
            checkpoint_count=_optional_integer(data, "checkpoint_count", context) or 0,
            source_run_id=_optional_string(data, "source_run_id", context),
            source_checkpoint_id=_optional_string(data, "source_checkpoint_id", context),
            created_at=_require_datetime_text(data, "created_at", context),
            updated_at=_require_datetime_text(data, "updated_at", context),
            latency_ms=_optional_number(data, "latency_ms", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunListOutput:
    object: str
    data: list[AgentRunOutput] = field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 25
    pages: int = 1

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunListOutput:
        context = "agent_runs"
        data = coerce_payload_mapping(payload)
        raw_items = data.get("data") or []
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.data must be a list.")
        return cls(
            object=_require_string(data, "object", context),
            data=[AgentRunOutput.from_api(item) for item in raw_items],
            total=_require_integer(data, "total", context),
            page=_require_integer(data, "page", context),
            limit=_require_integer(data, "limit", context),
            pages=_require_integer(data, "pages", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunEventOutput:
    event_id: str
    event_type: str
    status: str
    message: str
    created_at: str
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunEventOutput:
        context = "agent_run_events.data.item"
        data = coerce_payload_mapping(payload)
        details = data.get("details") or {}
        if not isinstance(details, dict):
            raise TypeError(f"{context}.details must be a mapping.")
        return cls(
            event_id=_require_string(data, "event_id", context),
            event_type=_require_string(data, "event_type", context),
            status=_require_string(data, "status", context),
            message=_require_string(data, "message", context),
            created_at=_require_datetime_text(data, "created_at", context),
            details=details,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunEventsOutput:
    object: str
    run_id: str
    data: list[AgentRunEventOutput] = field(default_factory=list)
    total_events: int = 0

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunEventsOutput:
        context = "agent_run_events"
        data = coerce_payload_mapping(payload)
        raw_events = data.get("data") or []
        if not isinstance(raw_events, list):
            raise TypeError(f"{context}.data must be a list.")
        return cls(
            object=_require_string(data, "object", context),
            run_id=_require_string(data, "run_id", context),
            data=[AgentRunEventOutput.from_api(item) for item in raw_events],
            total_events=_require_integer(data, "total_events", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunMissionEventOutput:
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
    event_ts: str = ""
    request_hash: str = ""
    policy_snapshot_id: str = ""
    schema_snapshot_id: str = ""
    manifest_version: str = ""
    checkpoint_id: str | None = None
    artifact_refs: list[str] = field(default_factory=list)
    failure_code: str | None = None
    latency_ms: int | None = None
    cost_usd_micros: int | None = None

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunMissionEventOutput:
        context = "agent_run_mission_events.data.item"
        data = coerce_payload_mapping(payload)
        return cls(
            mission_id=_require_string(data, "mission_id", context),
            thread_id=_require_string(data, "thread_id", context),
            tenant_scope=_require_string(data, "tenant_scope", context),
            workspace_scope=_require_string(data, "workspace_scope", context),
            event_index=_require_integer(data, "event_index", context),
            superstep=_require_integer(data, "superstep", context),
            node_name=_require_string(data, "node_name", context),
            event_type=_require_string(data, "event_type", context),
            event_message=_optional_string(data, "event_message", context),
            details_json=_optional_string(data, "details_json", context),
            event_ts=_require_datetime_text(data, "event_ts", context),
            request_hash=_require_string(data, "request_hash", context),
            policy_snapshot_id=_require_string(data, "policy_snapshot_id", context),
            schema_snapshot_id=_require_string(data, "schema_snapshot_id", context),
            manifest_version=_require_string(data, "manifest_version", context),
            checkpoint_id=_optional_string(data, "checkpoint_id", context),
            artifact_refs=_require_string_list(data, "artifact_refs", context),
            failure_code=_optional_string(data, "failure_code", context),
            latency_ms=_optional_integer(data, "latency_ms", context),
            cost_usd_micros=_optional_integer(data, "cost_usd_micros", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunMissionEventListOutput(AgentRunMissionEventOutput):
    run_id: str = ""
    run_status: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunMissionEventListOutput:
        context = "agent_run_mission_event_list.data.item"
        data = coerce_payload_mapping(payload)
        return cls(
            mission_id=_require_string(data, "mission_id", context),
            thread_id=_require_string(data, "thread_id", context),
            tenant_scope=_require_string(data, "tenant_scope", context),
            workspace_scope=_require_string(data, "workspace_scope", context),
            event_index=_require_integer(data, "event_index", context),
            superstep=_require_integer(data, "superstep", context),
            node_name=_require_string(data, "node_name", context),
            event_type=_require_string(data, "event_type", context),
            event_message=_optional_string(data, "event_message", context),
            details_json=_optional_string(data, "details_json", context),
            event_ts=_require_datetime_text(data, "event_ts", context),
            request_hash=_require_string(data, "request_hash", context),
            policy_snapshot_id=_require_string(data, "policy_snapshot_id", context),
            schema_snapshot_id=_require_string(data, "schema_snapshot_id", context),
            manifest_version=_require_string(data, "manifest_version", context),
            checkpoint_id=_optional_string(data, "checkpoint_id", context),
            artifact_refs=_require_string_list(data, "artifact_refs", context),
            failure_code=_optional_string(data, "failure_code", context),
            latency_ms=_optional_integer(data, "latency_ms", context),
            cost_usd_micros=_optional_integer(data, "cost_usd_micros", context),
            run_id=_require_string(data, "run_id", context),
            run_status=_require_string(data, "run_status", context),
        )


@dataclass(frozen=True)
class AgentRunMissionEventsOutput:
    object: str
    run_id: str
    data: list[AgentRunMissionEventOutput] = field(default_factory=list)
    total_events: int = 0

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunMissionEventsOutput:
        context = "agent_run_mission_events"
        data = coerce_payload_mapping(payload)
        raw_items = data.get("data") or []
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.data must be a list.")
        return cls(
            object=_require_string(data, "object", context),
            run_id=_require_string(data, "run_id", context),
            data=[AgentRunMissionEventOutput.from_api(item) for item in raw_items],
            total_events=_require_integer(data, "total_events", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunMissionEventListResponseOutput:
    object: str
    data: list[AgentRunMissionEventListOutput] = field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 25
    pages: int = 1

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunMissionEventListResponseOutput:
        context = "agent_run_mission_event_list"
        data = coerce_payload_mapping(payload)
        raw_items = data.get("data") or []
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.data must be a list.")
        return cls(
            object=_require_string(data, "object", context),
            data=[AgentRunMissionEventListOutput.from_api(item) for item in raw_items],
            total=_require_integer(data, "total", context),
            page=_require_integer(data, "page", context),
            limit=_require_integer(data, "limit", context),
            pages=_require_integer(data, "pages", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunStreamEventOutput:
    type: str
    run_id: str
    event: AgentRunEventOutput | None = None
    status: str | None = None
    total_events: int | None = None

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunStreamEventOutput:
        context = "agent_run_event_stream"
        data = coerce_payload_mapping(payload)
        event_payload = data.get("event")
        status = data.get("status")
        if status is not None and (not isinstance(status, str) or not status):
            raise TypeError(f"{context}.status must be a non-empty string.")
        total_events = data.get("total_events")
        if total_events is not None and (isinstance(total_events, bool) or not isinstance(total_events, int)):
            raise TypeError(f"{context}.total_events must be an integer.")
        return cls(
            type=_require_string(data, "type", context),
            run_id=_require_string(data, "run_id", context),
            event=AgentRunEventOutput.from_api(event_payload) if event_payload is not None else None,
            status=status,
            total_events=total_events,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunCheckpointOutput:
    checkpoint_id: str
    checkpoint_index: int
    run_id: str
    parent_checkpoint_id: str | None = None
    status: str = ""
    event_start_index: int = 0
    event_end_index: int = 0
    request_hash: str = ""
    decision_hash: str = ""
    content_hash: str = ""
    policy_snapshot_id: str = ""
    schema_snapshot_id: str = ""
    manifest_version: str = ""
    artifact_refs: list[str] = field(default_factory=list)
    created_at: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunCheckpointOutput:
        context = "agent_run_checkpoints.data.item"
        data = coerce_payload_mapping(payload)
        return cls(
            checkpoint_id=_require_string(data, "checkpoint_id", context),
            checkpoint_index=_require_integer(data, "checkpoint_index", context),
            run_id=_require_string(data, "run_id", context),
            parent_checkpoint_id=_optional_string(data, "parent_checkpoint_id", context),
            status=_require_string(data, "status", context),
            event_start_index=_require_integer(data, "event_start_index", context),
            event_end_index=_require_integer(data, "event_end_index", context),
            request_hash=_require_string(data, "request_hash", context),
            decision_hash=_require_string(data, "decision_hash", context),
            content_hash=_require_string(data, "content_hash", context),
            policy_snapshot_id=_require_string(data, "policy_snapshot_id", context),
            schema_snapshot_id=_require_string(data, "schema_snapshot_id", context),
            manifest_version=_require_string(data, "manifest_version", context),
            artifact_refs=_require_string_list(data, "artifact_refs", context),
            created_at=_require_datetime_text(data, "created_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunCheckpointListOutput(AgentRunCheckpointOutput):
    run_status: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunCheckpointListOutput:
        context = "agent_run_checkpoint_list.data.item"
        data = coerce_payload_mapping(payload)
        return cls(
            checkpoint_id=_require_string(data, "checkpoint_id", context),
            checkpoint_index=_require_integer(data, "checkpoint_index", context),
            run_id=_require_string(data, "run_id", context),
            parent_checkpoint_id=_optional_string(data, "parent_checkpoint_id", context),
            status=_require_string(data, "status", context),
            event_start_index=_require_integer(data, "event_start_index", context),
            event_end_index=_require_integer(data, "event_end_index", context),
            request_hash=_require_string(data, "request_hash", context),
            decision_hash=_require_string(data, "decision_hash", context),
            content_hash=_require_string(data, "content_hash", context),
            policy_snapshot_id=_require_string(data, "policy_snapshot_id", context),
            schema_snapshot_id=_require_string(data, "schema_snapshot_id", context),
            manifest_version=_require_string(data, "manifest_version", context),
            artifact_refs=_require_string_list(data, "artifact_refs", context),
            created_at=_require_datetime_text(data, "created_at", context),
            run_status=_require_string(data, "run_status", context),
        )


@dataclass(frozen=True)
class AgentRunCheckpointsOutput:
    object: str
    run_id: str
    data: list[AgentRunCheckpointOutput] = field(default_factory=list)
    total_checkpoints: int = 0

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunCheckpointsOutput:
        context = "agent_run_checkpoints"
        data = coerce_payload_mapping(payload)
        raw_items = data.get("data") or []
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.data must be a list.")
        return cls(
            object=_require_string(data, "object", context),
            run_id=_require_string(data, "run_id", context),
            data=[AgentRunCheckpointOutput.from_api(item) for item in raw_items],
            total_checkpoints=_require_integer(data, "total_checkpoints", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunCheckpointListResponseOutput:
    object: str
    data: list[AgentRunCheckpointListOutput] = field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 25
    pages: int = 1

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunCheckpointListResponseOutput:
        context = "agent_run_checkpoint_list"
        data = coerce_payload_mapping(payload)
        raw_items = data.get("data") or []
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.data must be a list.")
        return cls(
            object=_require_string(data, "object", context),
            data=[AgentRunCheckpointListOutput.from_api(item) for item in raw_items],
            total=_require_integer(data, "total", context),
            page=_require_integer(data, "page", context),
            limit=_require_integer(data, "limit", context),
            pages=_require_integer(data, "pages", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunReplayOutput:
    object: str
    run_id: str
    checkpoint_id: str
    replay_status: str
    compared_event_count: int
    checkpoint_count: int
    request_hash: str
    decision_hash: str
    content_hash: str
    policy_snapshot_id: str
    schema_snapshot_id: str
    manifest_version: str
    failure_code: str | None = None
    created_at: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunReplayOutput:
        context = "agent_run_replay"
        data = coerce_payload_mapping(payload)
        return cls(
            object=_require_string(data, "object", context),
            run_id=_require_string(data, "run_id", context),
            checkpoint_id=_require_string(data, "checkpoint_id", context),
            replay_status=_require_string(data, "replay_status", context),
            compared_event_count=_require_integer(data, "compared_event_count", context),
            checkpoint_count=_require_integer(data, "checkpoint_count", context),
            request_hash=_require_string(data, "request_hash", context),
            decision_hash=_require_string(data, "decision_hash", context),
            content_hash=_require_string(data, "content_hash", context),
            policy_snapshot_id=_require_string(data, "policy_snapshot_id", context),
            schema_snapshot_id=_require_string(data, "schema_snapshot_id", context),
            manifest_version=_require_string(data, "manifest_version", context),
            failure_code=_optional_string(data, "failure_code", context),
            created_at=_require_datetime_text(data, "created_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunTelemetryBatchOutput:
    batch_id: str
    telemetry_kind: str
    module_name: str
    tenant_scope: str
    request_hash: str
    started_at: str
    ended_at: str
    success_count: int
    failure_count: int
    latency_ms_p95: float
    cost_usd_micros: int

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunTelemetryBatchOutput:
        context = "agent_run_telemetry.data.item"
        data = coerce_payload_mapping(payload)
        return cls(
            batch_id=_require_string(data, "batch_id", context),
            telemetry_kind=_require_string(data, "telemetry_kind", context),
            module_name=_require_string(data, "module_name", context),
            tenant_scope=_require_string(data, "tenant_scope", context),
            request_hash=_require_string(data, "request_hash", context),
            started_at=_require_datetime_text(data, "started_at", context),
            ended_at=_require_datetime_text(data, "ended_at", context),
            success_count=_require_integer(data, "success_count", context),
            failure_count=_require_integer(data, "failure_count", context),
            latency_ms_p95=float(_require_integer(data, "latency_ms_p95", context))
            if isinstance(data.get("latency_ms_p95"), int)
            else _optional_number(data, "latency_ms_p95", context) or 0.0,
            cost_usd_micros=_require_integer(data, "cost_usd_micros", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunTelemetryBatchListOutput(AgentRunTelemetryBatchOutput):
    run_id: str = ""
    run_status: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunTelemetryBatchListOutput:
        context = "agent_run_telemetry_list.data.item"
        data = coerce_payload_mapping(payload)
        return cls(
            batch_id=_require_string(data, "batch_id", context),
            telemetry_kind=_require_string(data, "telemetry_kind", context),
            module_name=_require_string(data, "module_name", context),
            tenant_scope=_require_string(data, "tenant_scope", context),
            request_hash=_require_string(data, "request_hash", context),
            started_at=_require_datetime_text(data, "started_at", context),
            ended_at=_require_datetime_text(data, "ended_at", context),
            success_count=_require_integer(data, "success_count", context),
            failure_count=_require_integer(data, "failure_count", context),
            latency_ms_p95=float(_require_integer(data, "latency_ms_p95", context))
            if isinstance(data.get("latency_ms_p95"), int)
            else _optional_number(data, "latency_ms_p95", context) or 0.0,
            cost_usd_micros=_require_integer(data, "cost_usd_micros", context),
            run_id=_require_string(data, "run_id", context),
            run_status=_require_string(data, "run_status", context),
        )


@dataclass(frozen=True)
class AgentRunTelemetryOutput:
    object: str
    run_id: str
    data: list[AgentRunTelemetryBatchOutput] = field(default_factory=list)
    total_batches: int = 0

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunTelemetryOutput:
        context = "agent_run_telemetry"
        data = coerce_payload_mapping(payload)
        raw_items = data.get("data") or []
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.data must be a list.")
        return cls(
            object=_require_string(data, "object", context),
            run_id=_require_string(data, "run_id", context),
            data=[AgentRunTelemetryBatchOutput.from_api(item) for item in raw_items],
            total_batches=_require_integer(data, "total_batches", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AgentRunTelemetryListOutput:
    object: str
    data: list[AgentRunTelemetryBatchListOutput] = field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 25
    pages: int = 1

    @classmethod
    def from_api(cls, payload: Any) -> AgentRunTelemetryListOutput:
        context = "agent_run_telemetry_list"
        data = coerce_payload_mapping(payload)
        raw_items = data.get("data") or []
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.data must be a list.")
        return cls(
            object=_require_string(data, "object", context),
            data=[AgentRunTelemetryBatchListOutput.from_api(item) for item in raw_items],
            total=_require_integer(data, "total", context),
            page=_require_integer(data, "page", context),
            limit=_require_integer(data, "limit", context),
            pages=_require_integer(data, "pages", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
