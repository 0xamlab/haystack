from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.api_server.models.job import JobStatus
from apps.api_server.models.simulation_run import RunStatus
from apps.api_server.services import job_service


class _FakeResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeSession:
    def __init__(self, values: list[object | None]) -> None:
        self._values = list(values)
        self.flush_calls = 0
        self.commit_calls = 0
        self.refresh_calls: list[object] = []
        self.refresh_side_effect = None

    async def execute(self, _query: object) -> _FakeResult:
        if not self._values:
            raise AssertionError("No more fake query results configured.")
        return _FakeResult(self._values.pop(0))

    async def flush(self) -> None:
        self.flush_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1

    async def refresh(self, value: object) -> None:
        self.refresh_calls.append(value)
        if self.refresh_side_effect is not None:
            self.refresh_side_effect(value)


@pytest.mark.anyio
async def test_get_job_denies_cross_org_access_with_structured_error() -> None:
    job = SimpleNamespace(id=uuid.uuid4(), org_id=uuid.uuid4())
    db = _FakeSession([job])

    with pytest.raises(HTTPException) as exc_info:
        await job_service.get_job(uuid.uuid4(), uuid.uuid4(), db)  # type: ignore[arg-type]

    exc = exc_info.value
    assert exc.status_code == 403
    assert exc.detail == {
        "error": {
            "code": "job_access_denied",
            "message": "Access to this job is not allowed.",
        }
    }


@pytest.mark.anyio
async def test_get_job_denies_cross_workspace_access() -> None:
    """Same org, different workspace → 404 (not-found, no existence leak to a sibling ws)."""
    org_id = uuid.uuid4()
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()
    job = SimpleNamespace(id=uuid.uuid4(), org_id=org_id, workspace_id=ws_a)
    db = _FakeSession([job])

    with pytest.raises(HTTPException) as exc_info:
        await job_service.get_job(job.id, org_id, db, workspace_id=ws_b)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "job_not_found"


@pytest.mark.anyio
async def test_get_job_allows_same_workspace_and_org_wide() -> None:
    """Matching workspace returns the job; workspace_id=None (org-wide / internal) ignores ws."""
    org_id = uuid.uuid4()
    ws_a = uuid.uuid4()
    job = SimpleNamespace(id=uuid.uuid4(), org_id=org_id, workspace_id=ws_a)

    got = await job_service.get_job(job.id, org_id, _FakeSession([job]), workspace_id=ws_a)  # type: ignore[arg-type]
    assert got is job

    got_org_wide = await job_service.get_job(job.id, org_id, _FakeSession([job]))  # type: ignore[arg-type]
    assert got_org_wide is job


@pytest.mark.anyio
async def test_cancel_job_denies_cross_workspace_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """A sibling workspace cannot cancel another workspace's job (same org) → 404."""
    org_id = uuid.uuid4()
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(), org_id=org_id, workspace_id=ws_a, status=JobStatus.RUNNING
    )

    async def _fake_get_job_for_update(job_id: uuid.UUID, _db: object) -> object:
        return job

    monkeypatch.setattr(job_service, "_get_job_for_update", _fake_get_job_for_update)

    with pytest.raises(HTTPException) as exc_info:
        await job_service.cancel_job(job.id, org_id, _FakeSession([]), workspace_id=ws_b)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "job_not_found"


@pytest.mark.anyio
async def test_cancel_job_rejects_terminal_state_with_structured_error() -> None:
    org_id = uuid.uuid4()
    job = SimpleNamespace(id=uuid.uuid4(), org_id=org_id, status=JobStatus.COMPLETED)
    db = _FakeSession([job])

    with pytest.raises(HTTPException) as exc_info:
        await job_service.cancel_job(job.id, org_id, db)  # type: ignore[arg-type]

    exc = exc_info.value
    assert exc.status_code == 409
    assert exc.detail == {
        "error": {
            "code": "job_already_terminal",
            "message": "Job is already in terminal state: completed. Cannot cancel.",
        }
    }


@pytest.mark.anyio
async def test_execute_job_returns_fallback_payload_for_terminal_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = uuid.uuid4()
    run_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=org_id,
        run_id=run_id,
        status=JobStatus.COMPLETED,
    )
    run = SimpleNamespace(id=run_id, status=RunStatus.COMPLETED)
    db = _FakeSession([job, run])

    async def _fake_get_job_result(
        job_id: uuid.UUID,
        result_org_id: uuid.UUID,
        _db: object,
    ) -> None:
        assert job_id == job.id
        assert result_org_id == org_id
        return None

    monkeypatch.setattr(job_service, "get_job_result", _fake_get_job_result)

    result = await job_service.execute_job(job.id, {}, db)  # type: ignore[arg-type]

    assert result == {
        "status": "completed",
        "job_id": str(job.id),
        "run_id": str(run_id),
    }


@pytest.mark.anyio
async def test_get_job_result_returns_full_payload_from_object_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = uuid.uuid4()
    run_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=org_id,
        run_id=run_id,
        status=JobStatus.COMPLETED,
    )
    run = SimpleNamespace(
        id=run_id,
        org_id=org_id,
        result_url="https://storage.example/run.json",
        output_blob_ref="s3://decision-engine-results/org/run.json",
    )
    db = _FakeSession([job, run])

    async def _fake_get_result(
        result_url: str,
        *,
        org_id: uuid.UUID | None = None,
    ) -> dict[str, object]:
        assert result_url == "https://storage.example/run.json"
        assert org_id == run.org_id
        return {"recommended_action": "proceed", "confidence": 0.91}

    monkeypatch.setattr("apps.api_server.services.storage_service.get_result", _fake_get_result)

    result = await job_service.get_job_result(job.id, org_id, db)  # type: ignore[arg-type]

    assert result == {"recommended_action": "proceed", "confidence": 0.91}


@pytest.mark.anyio
async def test_get_job_result_falls_back_to_summary_when_blob_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = uuid.uuid4()
    run_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=org_id,
        run_id=run_id,
        status=JobStatus.COMPLETED,
    )
    run = SimpleNamespace(
        id=run_id,
        org_id=org_id,
        engine_version="0.1.0",
        scenarios_run=500,
        duration_ms=12,
        output_blob_ref="s3://decision-engine-results/org/run.json",
        result_url=None,
    )
    db = _FakeSession([job, run])

    monkeypatch.setattr(
        "apps.api_server.services.storage_service.generate_presigned_download_url",
        lambda org_id, run_id: "https://storage.example/run.json",
    )

    async def _fake_get_result(
        result_url: str,
        *,
        org_id: uuid.UUID | None = None,
    ) -> None:
        assert result_url == "https://storage.example/run.json"
        assert org_id == run.org_id
        return None

    monkeypatch.setattr("apps.api_server.services.storage_service.get_result", _fake_get_result)

    result = await job_service.get_job_result(job.id, org_id, db)  # type: ignore[arg-type]

    assert result == {
        "job_id": str(job.id),
        "run_id": str(run_id),
        "status": "completed",
        "engine_version": "0.1.0",
        "scenarios_run": 500,
        "duration_ms": 12,
        "output_blob_ref": "s3://decision-engine-results/org/run.json",
        "message": "Full result stored. Fetch via output_blob_ref if provided.",
    }


@pytest.mark.anyio
async def test_cancel_job_marks_associated_run_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = uuid.uuid4()
    run_id = uuid.uuid4()
    job = SimpleNamespace(id=uuid.uuid4(), org_id=org_id, run_id=run_id, status=JobStatus.RUNNING)
    run = SimpleNamespace(
        id=run_id,
        status=RunStatus.RUNNING,
        completed_at=None,
        error_message=None,
    )
    db = _FakeSession([])

    async def _fake_get_job_for_update(job_id: uuid.UUID, _db: object) -> object:
        assert job_id == job.id
        return job

    async def _fake_get_run_for_update(run_id: uuid.UUID, _db: object) -> object:
        assert run_id == run.id
        return run

    monkeypatch.setattr(job_service, "_get_job_for_update", _fake_get_job_for_update)
    monkeypatch.setattr(job_service, "_get_run_for_update", _fake_get_run_for_update)

    cancelled_job = await job_service.cancel_job(job.id, org_id, db)  # type: ignore[arg-type]

    assert cancelled_job.status == JobStatus.CANCELLED
    assert run.status == RunStatus.CANCELLED
    assert run.completed_at is not None
    assert run.error_message == "Job cancelled by user."
    assert db.flush_calls == 1
    assert db.commit_calls == 1


@pytest.mark.anyio
async def test_execute_job_honors_concurrent_cancellation_before_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = uuid.uuid4()
    run_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=org_id,
        run_id=run_id,
        status=JobStatus.RUNNING,
        callback_url=None,
        completed_at=None,
        error_message=None,
    )
    run = SimpleNamespace(
        id=run_id,
        api_key_id=None,
        status=RunStatus.RUNNING,
        started_at=None,
        completed_at=None,
        error_message=None,
    )
    db = _FakeSession([job, run])

    class _FakeEnvelope(SimpleNamespace):
        def model_dump(self, mode: str = "python") -> dict[str, object]:
            assert mode == "json"
            return {"status": "ok"}

    async def _fake_run_simulation_fast(
        request: object,
        org_id: uuid.UUID,
        api_key_id: uuid.UUID | None,
    ) -> tuple[SimpleNamespace, dict[str, object]]:
        assert org_id == job.org_id
        assert api_key_id is None
        return _FakeEnvelope(
            engine_version="0.1.0",
            scenarios_run=100,
            execution_ms=12,
            result_hash="abc123",
            recommended_action="hold",
            confidence=0.5,
            rationale="cancelled before completion",
            simulation_model="monte_carlo",
            metrics=SimpleNamespace(
                expected_value=1.0,
                probability_of_loss=0.1,
                std_deviation=0.2,
            ),
        ), {}

    monkeypatch.setattr(
        "apps.api_server.services.simulation_service.run_simulation_fast",
        _fake_run_simulation_fast,
    )

    lock_calls = {"job": 0}

    async def _fake_get_job_for_update(job_id: uuid.UUID, _db: object) -> object:
        assert job_id == job.id
        lock_calls["job"] += 1
        if lock_calls["job"] >= 2:
            job.status = JobStatus.CANCELLED
        return job

    async def _fake_get_run_for_update(run_id: uuid.UUID, _db: object) -> object:
        assert run_id == run.id
        return run

    monkeypatch.setattr(job_service, "_get_job_for_update", _fake_get_job_for_update)
    monkeypatch.setattr(job_service, "_get_run_for_update", _fake_get_run_for_update)

    result = await job_service.execute_job(
        job.id,
        {
            "mode": "auto",
            "scenario": {
                "variables": {"revenue": {"low": 1.0, "high": 2.0}},
                "objective": "maximize_net_value",
            },
            "runs": 100,
        },
        db,  # type: ignore[arg-type]
    )

    assert result == {
        "status": "cancelled",
        "job_id": str(job.id),
        "run_id": str(run_id),
    }
    assert run.status == RunStatus.CANCELLED
    assert run.completed_at is not None


@pytest.mark.anyio
async def test_execute_job_honors_cancellation_before_startup_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = uuid.uuid4()
    run_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=org_id,
        run_id=run_id,
        status=JobStatus.QUEUED,
        callback_url=None,
        completed_at=None,
        error_message=None,
    )
    run = SimpleNamespace(
        id=run_id,
        api_key_id=None,
        status=RunStatus.QUEUED,
        started_at=None,
        completed_at=None,
        error_message=None,
    )
    db = _FakeSession([job, run])

    async def _fake_get_job_for_update(job_id: uuid.UUID, _db: object) -> object:
        assert job_id == job.id
        job.status = JobStatus.CANCELLED
        return job

    async def _fake_get_run_for_update(run_id: uuid.UUID, _db: object) -> object:
        assert run_id == run.id
        return run

    async def _fake_get_job_result(
        job_id: uuid.UUID,
        result_org_id: uuid.UUID,
        _db: object,
    ) -> None:
        assert job_id == job.id
        assert result_org_id == org_id
        return None

    monkeypatch.setattr(job_service, "_get_job_for_update", _fake_get_job_for_update)
    monkeypatch.setattr(job_service, "_get_run_for_update", _fake_get_run_for_update)
    monkeypatch.setattr(job_service, "get_job_result", _fake_get_job_result)

    result = await job_service.execute_job(
        job.id,
        {
            "mode": "auto",
            "scenario": {
                "variables": {"revenue": {"low": 1.0, "high": 2.0}},
                "objective": "maximize_net_value",
            },
            "runs": 100,
        },
        db,  # type: ignore[arg-type]
    )

    assert result == {
        "status": "cancelled",
        "job_id": str(job.id),
        "run_id": str(run_id),
    }
    assert run.status == RunStatus.CANCELLED
    assert run.completed_at is not None
    assert db.commit_calls == 1
