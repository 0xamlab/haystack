"""Wave B1: repository decision-plan/pipeline runs execute off the request path via the
generic Job lifecycle. Fake-session unit tests of the dispatch, idempotency on a
terminal job (no re-run / re-bill of the LLM agent), connector-not-found failure, and
the create_job / get_job_result generalization for repository kinds."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from apps.api_server.models.job import JobKind, JobStatus
from apps.api_server.services import job_service, repository_job_service


async def _aret(value: object) -> object:
    return value


class _FakeResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeSession:
    """Returns pre-seeded query results in order; records adds. No real DB."""

    def __init__(self, values: list[object | None]) -> None:
        self._values = list(values)
        self.added: list[object] = []
        self.commits = 0

    async def execute(self, _query: object) -> _FakeResult:
        return _FakeResult(self._values.pop(0) if self._values else None)

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _obj: object) -> None:
        pass


def _repo_job(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = dict(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        workspace_id=None,
        run_id=None,
        job_kind=JobKind.REPOSITORY_DECISION_PLAN.value,
        status=JobStatus.QUEUED,
        request_payload={"repository_id": str(uuid.uuid4()), "request": {}},
        result_payload=None,
        callback_url=None,
        started_at=None,
        completed_at=None,
        error_message=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.anyio
async def test_execute_repository_job_completes_and_stores_result(monkeypatch):
    job = _repo_job()
    connector = SimpleNamespace(id=uuid.uuid4())
    db = _FakeSession([job, connector])  # 1) load job, 2) load connector
    monkeypatch.setattr(
        repository_job_service, "_run_repository_kind", lambda j, c: _aret({"plan": "ok"})
    )
    result = await repository_job_service.execute_repository_job(job.id, db)  # type: ignore[arg-type]
    assert result == {"plan": "ok"}
    assert job.status == JobStatus.COMPLETED
    assert job.result_payload == {"plan": "ok"}
    assert job.error_message is None


@pytest.mark.anyio
async def test_execute_repository_job_idempotent_on_terminal(monkeypatch):
    """A terminal job returns its stored result without re-running (re-billing) the agent."""
    job = _repo_job(status=JobStatus.COMPLETED, result_payload={"plan": "done"})
    db = _FakeSession([job])

    def _must_not_run(*_args: object) -> object:
        raise AssertionError("a terminal job must not re-run the agent")

    monkeypatch.setattr(repository_job_service, "_run_repository_kind", _must_not_run)
    result = await repository_job_service.execute_repository_job(job.id, db)  # type: ignore[arg-type]
    assert result == {"plan": "done"}


@pytest.mark.anyio
async def test_execute_repository_job_fails_when_connector_missing():
    job = _repo_job()
    db = _FakeSession([job, None])  # connector not found for org
    with pytest.raises(ValueError):
        await repository_job_service.execute_repository_job(job.id, db)  # type: ignore[arg-type]
    assert job.status == JobStatus.FAILED
    assert "not found" in (job.error_message or "")


@pytest.mark.anyio
async def test_create_job_repository_kind_has_no_run_id():
    db = _FakeSession([])
    job = await job_service.create_job(
        None,
        uuid.uuid4(),
        db,  # type: ignore[arg-type]
        queue_name="repository",
        job_kind=JobKind.REPOSITORY_PIPELINE,
        request_payload={"repository_id": "r", "request": {"x": 1}},
    )
    assert job.run_id is None
    assert job.job_kind == JobKind.REPOSITORY_PIPELINE.value
    assert job.request_payload == {"repository_id": "r", "request": {"x": 1}}
    assert job.status == JobStatus.QUEUED


@pytest.mark.anyio
async def test_get_job_result_returns_repository_result_payload():
    org = uuid.uuid4()
    job = _repo_job(org_id=org, status=JobStatus.COMPLETED, result_payload={"plan": "r"})
    db = _FakeSession([job])
    out = await job_service.get_job_result(job.id, org, db)  # type: ignore[arg-type]
    assert out == {"plan": "r"}
