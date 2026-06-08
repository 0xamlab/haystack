from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api_server.routers import decisions as decisions_router


def _decision_response_dict() -> dict:
    now = "2026-04-18T00:00:00Z"
    org_id = uuid.uuid4()
    decision_id = uuid.uuid4()
    return {
        "id": decision_id,
        "org_id": org_id,
        "run_id": None,
        "context": "ctx",
        "chosen_action": "proceed",
        "options_considered": ["proceed", "pause"],
        "expected_value": 100.0,
        "confidence": 0.9,
        "rationale": "good",
        "risk_p5": 10.0,
        "risk_p95": 200.0,
        "risk_pol": 0.1,
        "request_hash": None,
        "result_hash": None,
        "policy_snapshot_id": "policy-v1",
        "schema_snapshot_id": "schema-v1",
        "manifest_version": "runtime-manifest-v1",
        "actual_outcome": None,
        "outcome_delta": None,
        "outcome_notes": None,
        "outcome_recorded_at": None,
        "executed_at": None,
        "execution_status": None,
        "execution_webhook_url": None,
        "execution_response_code": None,
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.anyio
async def test_list_decisions_returns_limit_and_pages(monkeypatch) -> None:
    row_result = MagicMock()
    row_result.scalars.return_value.all.return_value = [SimpleNamespace()]
    count_result = MagicMock()
    count_result.scalar_one.return_value = 45
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[row_result, count_result])

    monkeypatch.setattr(
        decisions_router.DecisionLogResponse,
        "from_model",
        classmethod(lambda cls, row: _decision_response_dict()),
    )

    response = await decisions_router.list_decisions(
        auth={"org_id": uuid.uuid4()},
        db=db,
        page=2,
        limit=25,
        page_size=None,
        with_outcome_only=False,
    )

    assert response.page == 2
    assert response.limit == 25
    assert response.page_size == 25
    assert response.pages == 2
    assert response.total == 45


@pytest.mark.anyio
async def test_list_decisions_limit_overrides_legacy_page_size(monkeypatch) -> None:
    row_result = MagicMock()
    row_result.scalars.return_value.all.return_value = []
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[row_result, count_result])

    monkeypatch.setattr(
        decisions_router.DecisionLogResponse,
        "from_model",
        classmethod(lambda cls, row: _decision_response_dict()),
    )

    response = await decisions_router.list_decisions(
        auth={"org_id": uuid.uuid4()},
        db=db,
        page=1,
        limit=50,
        page_size=10,
        with_outcome_only=False,
    )

    assert response.limit == 50
    assert response.page_size == 50
    assert response.pages == 1


def test_decision_log_response_from_model_preserves_runtime_lineage() -> None:
    entry = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        run_id=None,
        context="ctx",
        chosen_action="proceed",
        options_considered='["proceed","pause"]',
        expected_value=100.0,
        confidence=0.9,
        rationale="good",
        risk_p5=10.0,
        risk_p95=200.0,
        risk_pol=0.1,
        request_hash="a" * 64,
        result_hash="b" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        manifest_version="runtime-manifest-v1",
        actual_outcome=None,
        outcome_delta=None,
        outcome_notes=None,
        outcome_recorded_at=None,
        executed_at=None,
        execution_status=None,
        execution_webhook_url=None,
        execution_response_code=None,
        created_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )

    response = decisions_router.DecisionLogResponse.from_model(entry)

    assert response.options_considered == ["proceed", "pause"]
    assert response.policy_snapshot_id == "policy-v1"
    assert response.schema_snapshot_id == "schema-v1"
    assert response.manifest_version == "runtime-manifest-v1"


@pytest.mark.anyio
async def test_log_decision_persists_runtime_lineage(monkeypatch) -> None:
    created_entries: list[object] = []
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    db = MagicMock()

    def _capture_entry(entry: object) -> None:
        created_entries.append(entry)
        setattr(entry, "id", uuid.uuid4())
        setattr(entry, "created_at", now)
        setattr(entry, "updated_at", now)

    db.add.side_effect = _capture_entry
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    monkeypatch.setattr(
        decisions_router,
        "_runtime_manifest_metadata",
        lambda: {
            "schema_snapshot_id": "schema-v1",
            "manifest_version": "runtime-manifest-v1",
        },
    )
    monkeypatch.setattr(
        decisions_router,
        "_current_policy_snapshot_id",
        lambda org_id: "policy-v1",
    )
    audit_writer = AsyncMock()
    monkeypatch.setattr(decisions_router, "write_audit_event", audit_writer)
    monkeypatch.setattr(decisions_router, "get_client_ip", lambda request: "203.0.113.10")

    response = await decisions_router.log_decision(
        payload=decisions_router.LogDecisionRequest(
            chosen_action="proceed",
            options_considered=["proceed", "pause"],
            expected_value=100.0,
        ),
        request=SimpleNamespace(headers={}, client=None),
        auth={"org_id": uuid.uuid4()},
        db=db,
    )

    assert len(created_entries) == 1
    entry = created_entries[0]
    assert entry.policy_snapshot_id == "policy-v1"
    assert entry.schema_snapshot_id == "schema-v1"
    assert entry.manifest_version == "runtime-manifest-v1"
    assert response.policy_snapshot_id == "policy-v1"
    assert response.schema_snapshot_id == "schema-v1"
    assert response.manifest_version == "runtime-manifest-v1"
    audit_writer.assert_awaited_once()
    metadata = audit_writer.await_args.kwargs["metadata"]
    assert metadata["policy_snapshot_id"] == "policy-v1"
    assert metadata["schema_snapshot_id"] == "schema-v1"
    assert metadata["manifest_version"] == "runtime-manifest-v1"


@pytest.mark.anyio
async def test_execute_decision_backfills_missing_runtime_lineage(monkeypatch) -> None:
    entry = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        run_id=None,
        context="ctx",
        chosen_action="proceed",
        options_considered='["proceed","pause"]',
        expected_value=100.0,
        confidence=0.9,
        rationale="good",
        risk_p5=10.0,
        risk_p95=200.0,
        risk_pol=0.1,
        request_hash="a" * 64,
        result_hash="b" * 64,
        policy_snapshot_id=None,
        schema_snapshot_id=None,
        manifest_version=None,
        execution_status=None,
        execution_webhook_url=None,
        execution_response_code=None,
        execution_receipt=None,
        executed_at=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = entry
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    monkeypatch.setattr(
        decisions_router,
        "_runtime_manifest_metadata",
        lambda: {
            "schema_snapshot_id": "schema-v1",
            "manifest_version": "runtime-manifest-v1",
        },
    )
    monkeypatch.setattr(
        "apps.api_server.services.execution_policy_service.get_policy",
        lambda org_id: SimpleNamespace(
            snapshot_id="policy-v2",
            min_confidence=0.5,
            risk_floor=None,
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.execution_policy_service.check_execution_gates",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        decisions_router,
        "async_http_request",
        AsyncMock(return_value=SimpleNamespace(status_code=202, is_success=True)),
    )
    audit_writer = AsyncMock()
    monkeypatch.setattr(decisions_router, "write_audit_event", audit_writer)
    monkeypatch.setattr(decisions_router, "get_client_ip", lambda request: "203.0.113.10")

    receipt = await decisions_router.execute_decision(
        decision_id=entry.id,
        payload=decisions_router.ExecuteDecisionRequest(
            webhook_url="https://hooks.example.test/decision"
        ),
        request=SimpleNamespace(state=SimpleNamespace(request_id="req_123"), headers={}, client=None),
        auth={"org_id": entry.org_id, "email": "owner@example.com"},
        db=db,
    )

    persisted_receipt = json.loads(entry.execution_receipt)
    assert entry.policy_snapshot_id == "policy-v2"
    assert entry.schema_snapshot_id == "schema-v1"
    assert entry.manifest_version == "runtime-manifest-v1"
    assert persisted_receipt["policy_snapshot_id"] == "policy-v2"
    assert persisted_receipt["schema_snapshot_id"] == "schema-v1"
    assert persisted_receipt["manifest_version"] == "runtime-manifest-v1"
    assert receipt.policy_snapshot_id == "policy-v2"
    assert receipt.schema_snapshot_id == "schema-v1"
    assert receipt.manifest_version == "runtime-manifest-v1"
    audit_writer.assert_awaited_once()
    metadata = audit_writer.await_args.kwargs["metadata"]
    assert metadata["execution_status"] == "delivered"
    assert metadata["policy_snapshot_id"] == "policy-v2"
    assert metadata["schema_snapshot_id"] == "schema-v1"


@pytest.mark.anyio
async def test_record_outcome_emits_audit_lineage(monkeypatch) -> None:
    entry = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        context="ctx",
        chosen_action="proceed",
        options_considered='["proceed","pause"]',
        confidence=0.9,
        rationale="good",
        risk_p5=10.0,
        risk_p95=200.0,
        risk_pol=0.1,
        run_id=None,
        request_hash="a" * 64,
        result_hash="b" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        manifest_version="runtime-manifest-v1",
        expected_value=100.0,
        actual_outcome=None,
        outcome_delta=None,
        outcome_notes=None,
        outcome_recorded_at=None,
        executed_at=None,
        execution_status=None,
        execution_webhook_url=None,
        execution_response_code=None,
        created_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = entry
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    audit_writer = AsyncMock()
    monkeypatch.setattr(decisions_router, "write_audit_event", audit_writer)
    monkeypatch.setattr(decisions_router, "get_client_ip", lambda request: "203.0.113.10")
    monkeypatch.setattr(
        "apps.api_server.services.calibration_service.refresh_calibration_from_db",
        AsyncMock(),
    )

    response = await decisions_router.record_outcome(
        decision_id=entry.id,
        payload=decisions_router.RecordOutcomeRequest(
            actual_outcome=80.0,
            outcome_notes="Observed lower conversion",
        ),
        request=SimpleNamespace(headers={}, client=None),
        auth={"org_id": entry.org_id, "email": "owner@example.com"},
        db=db,
    )

    assert response.outcome_delta == -20.0
    audit_writer.assert_awaited_once()
    metadata = audit_writer.await_args.kwargs["metadata"]
    assert metadata["actual_outcome"] == 80.0
    assert metadata["outcome_delta"] == -20.0
    assert metadata["manifest_version"] == "runtime-manifest-v1"


@pytest.mark.anyio
async def test_delete_decision_emits_audit_lineage(monkeypatch) -> None:
    entry = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        chosen_action="proceed",
        run_id=None,
        request_hash="a" * 64,
        result_hash="b" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        manifest_version="runtime-manifest-v1",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = entry
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[result, None])
    db.commit = AsyncMock()
    audit_writer = AsyncMock()
    monkeypatch.setattr(decisions_router, "write_audit_event", audit_writer)
    monkeypatch.setattr(decisions_router, "get_client_ip", lambda request: "203.0.113.10")

    await decisions_router.delete_decision(
        decision_id=entry.id,
        request=SimpleNamespace(headers={}, client=None),
        auth={"org_id": entry.org_id, "email": "owner@example.com"},
        db=db,
    )

    audit_writer.assert_awaited_once()
    metadata = audit_writer.await_args.kwargs["metadata"]
    assert metadata["decision_id"] == str(entry.id)
    assert metadata["policy_snapshot_id"] == "policy-v1"
    assert metadata["schema_snapshot_id"] == "schema-v1"
