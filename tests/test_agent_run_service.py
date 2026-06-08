from __future__ import annotations

import asyncio
import errno
from pathlib import Path

import pytest

from apps.api_server.schemas.agent_runs import AgentRunCreateRequest
from apps.api_server.services import agent_run_service
from apps.api_server.services.runtime_internal_contracts import (
    MissionEvent,
    TelemetryBatch,
    table_from_parquet_bytes,
    validate_table_schema,
)

pytest.importorskip("pyarrow")


def _fake_auth() -> dict[str, str]:
    return {
        "org_id": "org_agent_runs",
        "key_id": "key_agent_runs",
        "plan": "enterprise",
        "role": "owner",
        "email": "owner@algenta.test",
    }


def test_create_agent_run_persists_completed_run_and_events(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))

    run = asyncio.run(
        agent_run_service.create_agent_run(
            AgentRunCreateRequest(
                task="Search the knowledge base for airport disruptions",
                tools=["search", "calculate"],
                output_format="json",
            ),
            auth=_fake_auth(),
        )
    )

    assert run.status == "completed"
    assert run.pending_action is None
    assert run.selected_tool == "search"
    assert run.tools_used == ["search"]
    assert len(run.steps) == 4
    assert isinstance(run.result, dict)
    assert run.result["tool_used"] == "search"

    persisted = agent_run_service.get_agent_run(run_id=run.run_id, auth=_fake_auth())
    assert persisted.status == "completed"
    assert persisted.result == run.result

    events = agent_run_service.get_agent_run_events(run_id=run.run_id, auth=_fake_auth())
    assert [event.event_type for event in events] == [
        "run_created",
        "tool_selected",
        "tool_executed",
        "run_completed",
    ]
    checkpoints = agent_run_service.get_agent_run_checkpoints(run_id=run.run_id, auth=_fake_auth())
    assert checkpoints.total_checkpoints == 2
    assert checkpoints.data[-1].status == "completed"

    event_dir = Path(tmp_path / "runtime" / "agent_runs" / _fake_auth()["org_id"] / run.run_id / "events")
    event_parquet_files = sorted(event_dir.glob("*.parquet"))
    assert len(event_parquet_files) == 4
    event_rows: list[dict[str, object]] = []
    for path in event_parquet_files:
        table = table_from_parquet_bytes(path.read_bytes())
        validate_table_schema(table, MissionEvent)
        event_rows.extend(table.to_pylist())
    event_rows.sort(key=lambda row: int(row["event_index"]))
    first_event_row = event_rows[0]
    assert first_event_row["event_index"] == 0
    assert first_event_row["superstep"] == 1
    assert first_event_row["event_type"] == "run_created"
    assert first_event_row["event_message"] == "Agent run created."
    assert first_event_row["details_json"] == '{"approval_mode":"auto","start_paused":false}'
    assert first_event_row["request_hash"] == run.request_hash

    last_event_row = event_rows[-1]
    assert last_event_row["event_index"] == 3
    assert last_event_row["superstep"] == 2
    assert last_event_row["event_type"] == "run_completed"
    assert last_event_row["checkpoint_id"] == checkpoints.data[0].checkpoint_id

    telemetry_dir = Path(
        tmp_path / "runtime" / "agent_runs" / _fake_auth()["org_id"] / run.run_id / "telemetry"
    )
    telemetry_files = sorted(telemetry_dir.glob("*.parquet"))
    assert len(telemetry_files) == 1
    telemetry_table = table_from_parquet_bytes(telemetry_files[0].read_bytes())
    validate_table_schema(telemetry_table, TelemetryBatch)
    telemetry_row = telemetry_table.to_pylist()[0]
    assert telemetry_row["telemetry_kind"] == "agent_run_completion"
    assert telemetry_row["module_name"] == "agent_run_service"
    assert telemetry_row["request_hash"] == run.request_hash
    assert telemetry_row["success_count"] == 1
    assert telemetry_row["failure_count"] == 0

    mission_events = agent_run_service.get_agent_run_mission_events(run_id=run.run_id, auth=_fake_auth())
    assert mission_events.total_events == 4
    assert mission_events.data[0].event_type == "run_created"
    assert mission_events.data[-1].event_type == "run_completed"
    assert mission_events.data[-1].checkpoint_id == checkpoints.data[0].checkpoint_id

    telemetry = agent_run_service.get_agent_run_telemetry(run_id=run.run_id, auth=_fake_auth())
    assert telemetry.total_batches == 1
    assert telemetry.data[0].telemetry_kind == "agent_run_completion"
    assert telemetry.data[0].request_hash == run.request_hash

    replay = agent_run_service.replay_agent_run(
        run_id=run.run_id,
        auth=_fake_auth(),
        payload=agent_run_service.AgentRunReplayRequest(),
    )
    assert replay.replay_status == "matched"

    forked = agent_run_service.fork_agent_run(
        run_id=run.run_id,
        auth=_fake_auth(),
        payload=agent_run_service.AgentRunForkRequest(checkpoint_id=checkpoints.data[0].checkpoint_id),
    )
    assert forked.status == "paused"
    assert forked.pending_action == "resume"
    assert forked.source_run_id == run.run_id

    listed = agent_run_service.list_agent_runs(auth=_fake_auth(), page=1, limit=25)
    assert listed.total == 2
    assert listed.data[0].run_id == forked.run_id
    assert listed.data[1].run_id == run.run_id

    filtered = agent_run_service.list_agent_runs(
        auth=_fake_auth(),
        page=1,
        limit=25,
        status="paused",
        request_hash=run.request_hash,
        policy_snapshot_id=run.policy_snapshot_id,
        schema_snapshot_id=run.schema_snapshot_id,
    )
    assert filtered.total == 1
    assert filtered.data[0].run_id == forked.run_id


def test_create_manual_agent_run_requires_approval_then_completes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))

    run = asyncio.run(
        agent_run_service.create_agent_run(
            AgentRunCreateRequest(
                task="Find the most relevant market research documents",
                tools=["search"],
                approval_mode="manual",
            ),
            auth=_fake_auth(),
        )
    )

    assert run.status == "requires_approval"
    assert run.pending_action == "approve"
    assert run.result is None

    approved = asyncio.run(agent_run_service.approve_agent_run(run_id=run.run_id, auth=_fake_auth()))
    assert approved.status == "completed"
    assert approved.pending_action is None
    assert approved.tools_used == ["search"]
    assert isinstance(approved.result, str)

    events = agent_run_service.get_agent_run_events(run_id=run.run_id, auth=_fake_auth())
    assert [event.event_type for event in events] == [
        "run_created",
        "tool_selected",
        "approval_required",
        "run_approved",
        "tool_executed",
        "run_completed",
    ]
    checkpoints = agent_run_service.get_agent_run_checkpoints(run_id=run.run_id, auth=_fake_auth())
    assert checkpoints.total_checkpoints == 3
    assert checkpoints.data[0].status == "requires_approval"
    assert checkpoints.data[-1].status == "completed"

    event_dir = Path(tmp_path / "runtime" / "agent_runs" / _fake_auth()["org_id"] / run.run_id / "events")
    event_rows: list[dict[str, object]] = []
    for path in sorted(event_dir.glob("*.parquet")):
        table = table_from_parquet_bytes(path.read_bytes())
        validate_table_schema(table, MissionEvent)
        event_rows.extend(table.to_pylist())
    event_rows.sort(key=lambda row: int(row["event_index"]))
    assert [row["event_type"] for row in event_rows] == [
        "run_created",
        "tool_selected",
        "approval_required",
        "run_approved",
        "tool_executed",
        "run_completed",
    ]
    assert event_rows[2]["superstep"] == 1
    assert event_rows[3]["superstep"] == 2
    assert event_rows[4]["superstep"] == 3
    assert event_rows[4]["checkpoint_id"] == checkpoints.data[1].checkpoint_id


def test_create_agent_run_falls_back_when_default_runtime_dir_is_unwritable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ALGENTA_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(agent_run_service, "_IMPLICIT_FALLBACK_RUNTIME_DIR", tmp_path / "fallback-runtime")
    monkeypatch.setattr(agent_run_service.Path, "home", classmethod(lambda cls: tmp_path / "home"))
    agent_run_service._WRITABLE_RUNTIME_DIRS.clear()
    agent_run_service._UNWRITABLE_DEFAULT_RUNTIME_DIRS.clear()
    agent_run_service._WARNED_DEFAULT_RUNTIME_DIRS.clear()

    configured = tmp_path / "home" / ".algenta" / "runtime"
    real_runtime_dir_for_base = agent_run_service._runtime_dir_for_base

    def _fake_runtime_dir_for_base(runtime_dir: Path) -> Path:
        if runtime_dir == configured:
            raise PermissionError(errno.EPERM, "Operation not permitted", str(runtime_dir))
        return real_runtime_dir_for_base(runtime_dir)

    monkeypatch.setattr(agent_run_service, "_runtime_dir_for_base", _fake_runtime_dir_for_base)

    run = asyncio.run(
        agent_run_service.create_agent_run(
            AgentRunCreateRequest(task="Search fallback runtime path"),
            auth=_fake_auth(),
        )
    )

    persisted = (
        tmp_path
        / "fallback-runtime"
        / "agent_runs"
        / _fake_auth()["org_id"]
        / f"{run.run_id}.json"
    )
    assert persisted.exists()


def test_paused_agent_run_can_resume_or_cancel(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))

    paused = asyncio.run(
        agent_run_service.create_agent_run(
            AgentRunCreateRequest(
                task="Calculate the expected margin by region",
                start_paused=True,
            ),
            auth=_fake_auth(),
        )
    )
    assert paused.status == "paused"
    assert paused.pending_action == "resume"

    cancelled = agent_run_service.cancel_agent_run(run_id=paused.run_id, auth=_fake_auth())
    assert cancelled.status == "cancelled"

    resumable = asyncio.run(
        agent_run_service.create_agent_run(
            AgentRunCreateRequest(
                task="Calculate the expected margin by region",
                start_paused=True,
            ),
            auth=_fake_auth(),
        )
    )
    resumed = asyncio.run(agent_run_service.resume_agent_run(run_id=resumable.run_id, auth=_fake_auth()))
    assert resumed.status == "completed"
    assert resumed.pending_action is None
    assert resumed.tools_used == ["calculate"]
    checkpoints = agent_run_service.get_agent_run_checkpoints(
        run_id=resumable.run_id,
        auth=_fake_auth(),
    )
    assert checkpoints.total_checkpoints == 3


def test_query_agent_run_traces_filters_across_runs(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))

    completed = asyncio.run(
        agent_run_service.create_agent_run(
            AgentRunCreateRequest(
                task="Search the knowledge base for pricing exceptions",
                tools=["search"],
            ),
            auth=_fake_auth(),
        )
    )
    approval_required = asyncio.run(
        agent_run_service.create_agent_run(
            AgentRunCreateRequest(
                task="Review the export-control policy packet",
                tools=["search"],
                approval_mode="manual",
            ),
            auth=_fake_auth(),
        )
    )
    paused = asyncio.run(
        agent_run_service.create_agent_run(
            AgentRunCreateRequest(
                task="Calculate margin deltas for the weekly review",
                start_paused=True,
            ),
            auth=_fake_auth(),
        )
    )

    mission_events = agent_run_service.query_agent_run_mission_events(
        auth=_fake_auth(),
        page=1,
        limit=10,
        status="requires_approval",
        request_hash=approval_required.request_hash,
        policy_snapshot_id=approval_required.policy_snapshot_id,
        schema_snapshot_id=approval_required.schema_snapshot_id,
        run_id=approval_required.run_id,
        event_type="approval_required",
    )
    assert mission_events.total == 1
    assert mission_events.data[0].run_id == approval_required.run_id
    assert mission_events.data[0].run_status == "requires_approval"
    assert mission_events.data[0].event_type == "approval_required"

    telemetry = agent_run_service.query_agent_run_telemetry(
        auth=_fake_auth(),
        page=1,
        limit=10,
        status="completed",
        request_hash=completed.request_hash,
        policy_snapshot_id=completed.policy_snapshot_id,
        schema_snapshot_id=completed.schema_snapshot_id,
        run_id=completed.run_id,
        telemetry_kind="agent_run_completion",
        module_name="agent_run_service",
    )
    assert telemetry.total == 1
    assert telemetry.data[0].run_id == completed.run_id
    assert telemetry.data[0].run_status == "completed"
    assert telemetry.data[0].telemetry_kind == "agent_run_completion"
    assert telemetry.data[0].module_name == "agent_run_service"

    checkpoints = agent_run_service.query_agent_run_checkpoints(
        auth=_fake_auth(),
        page=1,
        limit=10,
        status="requires_approval",
        request_hash=approval_required.request_hash,
        policy_snapshot_id=approval_required.policy_snapshot_id,
        schema_snapshot_id=approval_required.schema_snapshot_id,
        run_id=approval_required.run_id,
        checkpoint_id=approval_required.latest_checkpoint_id,
    )
    assert checkpoints.total == 1
    assert checkpoints.data[0].run_id == approval_required.run_id
    assert checkpoints.data[0].run_status == "requires_approval"
    assert checkpoints.data[0].checkpoint_id == approval_required.latest_checkpoint_id

    all_events = agent_run_service.query_agent_run_mission_events(
        auth=_fake_auth(),
        page=1,
        limit=100,
    )
    assert all_events.total >= 6
    assert {item.run_id for item in all_events.data} >= {
        completed.run_id,
        approval_required.run_id,
        paused.run_id,
    }

    all_checkpoints = agent_run_service.query_agent_run_checkpoints(
        auth=_fake_auth(),
        page=1,
        limit=100,
    )
    assert all_checkpoints.total >= 4
    assert {item.run_id for item in all_checkpoints.data} >= {
        completed.run_id,
        approval_required.run_id,
        paused.run_id,
    }
