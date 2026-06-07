from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("pyarrow")

from apps.api_server.services import audit_service
from apps.api_server.services.runtime_internal_contracts import (
    AuditEventRecord,
    table_from_parquet_bytes,
    validate_table_schema,
)


@pytest.mark.anyio
async def test_write_audit_event_persists_parquet_artifact(monkeypatch, tmp_path) -> None:
    captured_events: list[object] = []
    db = MagicMock()

    def _capture_event(event: object) -> None:
        captured_events.append(event)
        event.id = uuid.uuid4()
        event.created_at = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)

    db.add.side_effect = _capture_event
    db.flush = AsyncMock()
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))

    await audit_service.write_audit_event(
        db,
        org_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        action="decision.execute",
        actor_email="owner@example.com",
        actor_user_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        resource_type="decision_log",
        resource_id="decision_123",
        ip_address="203.0.113.10",
        metadata={
            "policy_snapshot_id": "policy-v1",
            "schema_snapshot_id": "schema-v1",
            "manifest_version": "runtime-manifest-v1",
            "request_hash": "req-hash-1",
        },
    )

    assert len(captured_events) == 1
    event = captured_events[0]
    path = (
        tmp_path
        / "runtime"
        / "audit_events"
        / "11111111-1111-1111-1111-111111111111"
        / f"{event.id}.parquet"
    )
    assert path.exists()

    table = table_from_parquet_bytes(path.read_bytes())
    validate_table_schema(table, AuditEventRecord)
    assert table.num_rows == 1
    row = table.to_pylist()[0]
    assert row["action"] == "decision.execute"
    assert row["policy_snapshot_id"] == "policy-v1"
    assert row["schema_snapshot_id"] == "schema-v1"
    assert row["manifest_version"] == "runtime-manifest-v1"
    assert row["request_hash"] == "req-hash-1"


@pytest.mark.anyio
async def test_query_audit_event_artifacts_filters_immutable_records(monkeypatch, tmp_path) -> None:
    captured_events: list[object] = []
    db = MagicMock()

    def _capture_event(event: object) -> None:
        captured_events.append(event)
        event.id = uuid.uuid4()
        event.created_at = datetime(2026, 5, 24, 12, len(captured_events), tzinfo=UTC)

    db.add.side_effect = _capture_event
    db.flush = AsyncMock()
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    org_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

    await audit_service.write_audit_event(
        db,
        org_id=org_id,
        action="decision.execute",
        actor_email="owner@example.com",
        resource_type="decision_log",
        resource_id="decision_123",
        result="success",
        metadata={
            "policy_snapshot_id": "policy-v1",
            "schema_snapshot_id": "schema-v1",
            "manifest_version": "runtime-manifest-v1",
            "request_hash": "req-hash-1",
        },
    )
    await audit_service.write_audit_event(
        db,
        org_id=org_id,
        action="invite_member",
        actor_email="admin@example.com",
        resource_type="team_member",
        resource_id="user_456",
        result="success",
        metadata={
            "policy_snapshot_id": "policy-v2",
            "schema_snapshot_id": "schema-v2",
            "manifest_version": "runtime-manifest-v2",
            "request_hash": "req-hash-2",
        },
    )

    directory = tmp_path / "runtime" / "audit_events" / str(org_id)
    content_hash = None
    for path in sorted(directory.glob("*.parquet")):
        row = table_from_parquet_bytes(path.read_bytes()).to_pylist()[0]
        if row["action"] == "decision.execute":
            content_hash = row["content_hash"]
            break
    assert content_hash is not None

    records = audit_service.query_audit_event_artifacts(
        org_id=str(org_id),
        actor_email="owner@example.com",
        action="decision.execute",
        resource_type="decision_log",
        result="success",
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        manifest_version="runtime-manifest-v1",
        request_hash="req-hash-1",
        content_hash=content_hash,
    )

    assert len(records) == 1
    assert records[0].resource_id == "decision_123"
    assert records[0].content_hash == content_hash


@pytest.mark.anyio
async def test_audit_artifacts_workspace_isolation(monkeypatch, tmp_path) -> None:
    """#7 full fix: artifacts carry workspace_id; a scoped query returns only that workspace's
    records, while an org-wide query (workspace_id=None) returns all — including legacy
    (workspace_id=None) records, which are invisible to a scoped caller."""
    db = MagicMock()

    def _capture_event(event: object) -> None:
        event.id = uuid.uuid4()
        event.created_at = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)

    db.add.side_effect = _capture_event
    db.flush = AsyncMock()
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    org_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()

    await audit_service.write_audit_event(
        db, org_id=org_id, action="a.event", actor_email="a@x", workspace_id=ws_a
    )
    await audit_service.write_audit_event(
        db, org_id=org_id, action="b.event", actor_email="b@x", workspace_id=ws_b
    )
    await audit_service.write_audit_event(
        db, org_id=org_id, action="legacy.event", actor_email="l@x", workspace_id=None
    )

    def _actions(workspace_id: str | None) -> set[str]:
        recs = audit_service.query_audit_event_artifacts(
            org_id=str(org_id), workspace_id=workspace_id
        )
        return {r.action for r in recs}

    assert _actions(str(ws_a)) == {"a.event"}  # workspace A sees only its own
    assert _actions(str(ws_b)) == {"b.event"}  # workspace B sees only its own
    # Org-wide (unscoped platform call) sees everything, including the legacy record.
    assert _actions(None) == {"a.event", "b.event", "legacy.event"}


@pytest.mark.anyio
async def test_audit_artifact_reader_tolerates_legacy_without_workspace_id() -> None:
    """A pre-#7 artifact (no workspace_id column) must still parse, with workspace_id=None."""
    from datetime import datetime as _dt

    import pyarrow as pa

    from apps.api_server.services.runtime_internal_contracts import (
        _load_pyarrow,
        table_from_parquet_bytes_tolerant,
        validate_table_schema,
    )

    # Build a LEGACY table: the audit schema MINUS the workspace_id column.
    legacy_fields = [
        ("event_id", "e1"), ("org_id", "o1"), ("actor_user_id", None), ("actor_email", "a@x"),
        ("action", "act"), ("resource_type", None), ("resource_id", None), ("ip_address", None),
        ("result", "success"), ("metadata_json", None), ("policy_snapshot_id", None),
        ("schema_snapshot_id", None), ("manifest_version", None), ("request_hash", None),
        ("content_hash", "h1"),
    ]
    _, pq = _load_pyarrow()
    import io as _io

    arrays = {k: pa.array([v], type=pa.string()) for k, v in legacy_fields}
    arrays["created_at"] = pa.array([_dt(2026, 5, 24, 12, 0)], type=pa.timestamp("us", tz="UTC"))
    legacy_table = pa.table(arrays)
    buf = _io.BytesIO()
    pq.write_table(legacy_table, buf)

    from apps.api_server.services.runtime_internal_contracts import AuditEventRecord

    table = table_from_parquet_bytes_tolerant(buf.getvalue(), AuditEventRecord)
    validate_table_schema(table, AuditEventRecord)  # must NOT raise — tolerant reader normalized it
    rec = AuditEventRecord.model_validate(table.to_pylist()[0])
    assert rec.workspace_id is None and rec.action == "act"


@pytest.mark.anyio
async def test_write_audit_event_nested_failure_does_not_raise(monkeypatch, tmp_path) -> None:
    class DummyNestedTransaction:
        def __init__(self) -> None:
            self.exit_exc_type: object | None = None

        async def __aenter__(self) -> DummyNestedTransaction:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            self.exit_exc_type = exc_type
            return False

    class DummyAsyncSession:
        def __init__(self) -> None:
            self.nested = DummyNestedTransaction()
            self.added_events: list[object] = []
            self.flush_calls = 0

        def begin_nested(self) -> DummyNestedTransaction:
            return self.nested

        def add(self, event: object) -> None:
            self.added_events.append(event)

        async def flush(self) -> None:
            self.flush_calls += 1
            raise RuntimeError("simulated audit write failure")

    monkeypatch.setattr(audit_service, "AsyncSession", DummyAsyncSession)
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    db = DummyAsyncSession()

    await audit_service.write_audit_event(
        db,
        org_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        action="decision.execute",
        actor_email="owner@example.com",
        resource_type="decision_log",
        resource_id="decision_123",
    )

    assert db.flush_calls == 1
    assert len(db.added_events) == 1
    assert db.nested.exit_exc_type is RuntimeError
    artifact_dir = tmp_path / "runtime" / "audit_events" / "11111111-1111-1111-1111-111111111111"
    assert not artifact_dir.exists()
