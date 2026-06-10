"""AR-OPT-9: one-call pipeline orchestration (snapshot->triage->plan->simulate).

Hermetic: the four composable service functions are stubbed, so this asserts the
*orchestration* — flag gate, stage chaining (each stage receives the prior
stage's generated id), `stop_after` truncation, reuse-by-id, per-stage timings,
and AR-OPT-0 telemetry spans — without running real parsing/LLM/simulation.
"""
from __future__ import annotations

import uuid

import pytest

from apps.api_server.schemas.repositories import (
    RepositoryDecisionPlanResponse,
    RepositoryPipelineRequest,
    RepositorySnapshotResponse,
    RepositoryTriageResponse,
)
from apps.api_server.schemas.response import DecisionEnvelope
from apps.api_server.services import repository_intelligence_pipeline as pipeline
from apps.api_server.services import repository_intelligence_telemetry as telemetry
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)

_ENV = "ALGENTA_REPOSITORIES_PIPELINE_ENABLED"


def _snapshot(*, snapshot_id: str = "snap-new", status: str = "created"):
    return RepositorySnapshotResponse.model_construct(
        repository_id="repo-1", snapshot_id=snapshot_id, status=status
    )


def _triage(*, bundle_ref: str = "bundle-1"):
    return RepositoryTriageResponse.model_construct(
        repository_id="repo-1",
        snapshot_id="snap-new",
        workspace_evidence_bundle_ref=bundle_ref,
    )


def _plan(*, plan_id: str = "plan-1"):
    return RepositoryDecisionPlanResponse.model_construct(
        repository_id="repo-1", snapshot_id="snap-new", decision_plan_id=plan_id
    )


@pytest.fixture
def stubbed(monkeypatch):
    """Stub the composable service fns; return a dict capturing each stage's request."""
    calls: dict = {}

    def fake_create_snapshot(*, connector, request):
        calls["snapshot_request"] = request
        return _snapshot(snapshot_id="snap-new", status="created")

    def fake_get_snapshot(*, connector, snapshot_id):
        calls["get_snapshot_id"] = snapshot_id
        return _snapshot(snapshot_id=snapshot_id, status="existing")

    def fake_triage(*, connector, request):
        calls["triage_request"] = request
        return _triage(bundle_ref="bundle-1")

    async def fake_plan(*, connector, request):
        calls["plan_request"] = request
        return _plan(plan_id="plan-1")

    async def fake_simulate(*, connector, request):
        calls["simulate_request"] = request
        return DecisionEnvelope.model_construct(run_id=uuid.uuid4())

    monkeypatch.setattr(pipeline._ri, "create_repository_snapshot", fake_create_snapshot)
    monkeypatch.setattr(pipeline._ri, "get_repository_snapshot", fake_get_snapshot)
    monkeypatch.setattr(pipeline._ri, "triage_repository", fake_triage)
    monkeypatch.setattr(pipeline._ri, "create_repository_decision_plan", fake_plan)
    monkeypatch.setattr(pipeline._ri, "simulate_repository_decision", fake_simulate)
    monkeypatch.setenv(_ENV, "true")
    return calls


async def test_pipeline_disabled_by_default(monkeypatch):
    monkeypatch.delenv(_ENV, raising=False)
    assert pipeline.pipeline_enabled() is False
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        await pipeline.run_repository_pipeline(
            connector=object(), request=RepositoryPipelineRequest()
        )
    assert excinfo.value.code == "pipeline_not_enabled"
    assert excinfo.value.status_code == 404


async def test_full_chain_threads_ids_between_stages(stubbed):
    response = await pipeline.run_repository_pipeline(
        connector=object(),
        request=RepositoryPipelineRequest(runs=1234, seed=7, model="m-x"),
    )
    # Each stage received the prior stage's generated id.
    assert stubbed["triage_request"].snapshot_id == "snap-new"
    assert stubbed["plan_request"].snapshot_id == "snap-new"
    assert stubbed["plan_request"].workspace_evidence_bundle_ref == "bundle-1"
    assert stubbed["plan_request"].model == "m-x"
    assert stubbed["simulate_request"].decision_plan_id == "plan-1"
    assert stubbed["simulate_request"].runs == 1234
    assert stubbed["simulate_request"].seed == 7
    # Response is fully populated through simulate.
    assert response.completed_stage == "simulate"
    assert response.snapshot_id == "snap-new"
    assert response.triage is not None
    assert response.decision_plan is not None
    assert response.simulation is not None
    assert [t.stage for t in response.stage_timings] == [
        "snapshot",
        "triage",
        "plan",
        "simulate",
    ]
    assert response.stage_timings[0].status == "ok"  # freshly created


async def test_stop_after_triage_skips_plan_and_simulate(stubbed):
    response = await pipeline.run_repository_pipeline(
        connector=object(),
        request=RepositoryPipelineRequest(stop_after="triage"),
    )
    assert "plan_request" not in stubbed
    assert "simulate_request" not in stubbed
    assert response.completed_stage == "triage"
    assert response.decision_plan is None
    assert response.simulation is None
    assert [t.stage for t in response.stage_timings] == ["snapshot", "triage"]


async def test_reuse_snapshot_by_id_skips_create(stubbed):
    response = await pipeline.run_repository_pipeline(
        connector=object(),
        request=RepositoryPipelineRequest(
            snapshot_id="snap-existing", stop_after="snapshot"
        ),
    )
    assert stubbed["get_snapshot_id"] == "snap-existing"
    assert "snapshot_request" not in stubbed  # create not called
    assert response.snapshot_id == "snap-existing"
    assert response.completed_stage == "snapshot"
    assert response.stage_timings[0].status == "reused"
    assert response.triage is None


async def test_pipeline_records_telemetry_spans(stubbed):
    with telemetry.collect() as data:
        await pipeline.run_repository_pipeline(
            connector=object(), request=RepositoryPipelineRequest()
        )
    for span in (
        "pipeline_snapshot_ms",
        "pipeline_triage_ms",
        "pipeline_plan_ms",
        "pipeline_simulate_ms",
    ):
        assert span in data["spans_ms"], f"missing span {span}"
