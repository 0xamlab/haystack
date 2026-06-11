"""AR-OPT-9: one-call repository pipeline orchestration.

The `/repositories` flow is normally driven as four separate calls — snapshot,
triage, decision-plan, simulate — each of which re-resolves the connector and
reloads the snapshot manifest from disk. This module composes them behind a
single endpoint so a caller gets the whole chain (and the decision-gate
envelope) in one round-trip.

The stages are a strict dependency chain (each consumes the previous stage's
generated id), so there is no genuine step parallelism to exploit; the wins are:

  * one HTTP round-trip instead of four,
  * cross-stage manifest reuse via the AR-OPT-2 in-process triage LRU (the same
    snapshot_id is read once and reused by triage / plan / simulate),
  * per-stage timing surfaced in the response plus AR-OPT-0 telemetry spans.

Only the *plan* stage touches an LLM. *simulate* is the deterministic Mojo
engine (`run_simulation_fast`, compute-only) — running the pipeline through
simulate does not incur model cost.

Flag-gated: the endpoint is inert unless ``ALGENTA_REPOSITORIES_PIPELINE_ENABLED``
is truthy, so the surface is additive and default-off (zero regression).
"""
from __future__ import annotations

from copy import deepcopy
import os
import time

from apps.api_server.models.data_connector import DataConnector
from apps.api_server.schemas.repositories import (
    RepositoryDecisionPlanCreateRequest,
    RepositoryPipelineRequest,
    RepositoryPipelineResponse,
    RepositoryPipelineStageTiming,
    RepositorySimulationRequest,
    RepositorySnapshotCreateRequest,
    RepositoryTriageRequest,
)
from apps.api_server.services import repository_intelligence_core as _ri
from apps.api_server.services import repository_intelligence_telemetry as telemetry
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)

_PIPELINE_ENV = "ALGENTA_REPOSITORIES_PIPELINE_ENABLED"
_TRUTHY = {"1", "true", "yes", "on"}

# Stage ordering — used to decide whether `stop_after` includes a stage.
_STAGE_ORDER = ("snapshot", "triage", "plan", "simulate")


def pipeline_enabled() -> bool:
    """True when the one-call pipeline endpoint is enabled (default: off)."""
    return os.environ.get(_PIPELINE_ENV, "false").strip().lower() in _TRUTHY


def _should_run(stage: str, stop_after: str) -> bool:
    return _STAGE_ORDER.index(stage) <= _STAGE_ORDER.index(stop_after)


def _telemetry_snapshot(data: dict[str, object]) -> dict[str, object]:
    return {
        "spans_ms": deepcopy(data.get("spans_ms", {})),
        "counters": deepcopy(data.get("counters", {})),
        "events": deepcopy(data.get("events", [])),
    }


async def run_repository_pipeline(
    *,
    connector: DataConnector,
    request: RepositoryPipelineRequest,
) -> RepositoryPipelineResponse:
    """Run snapshot -> triage -> plan -> simulate up to ``request.stop_after``.

    Each stage reuses the public service function the standalone endpoints call,
    so behavior is identical to running the four endpoints in sequence.
    """
    if not pipeline_enabled():
        raise RepositoryIntelligenceError(
            code="pipeline_not_enabled",
            message=(
                "The one-call repository pipeline is not enabled. Set "
                f"{_PIPELINE_ENV}=true to enable it."
            ),
            status_code=404,
        )

    with telemetry.collect_or_current() as telemetry_data:
        timings: list[RepositoryPipelineStageTiming] = []
        stop_after = request.stop_after

        # --- Stage 1: snapshot (reuse by id, else create) -------------------
        start = time.perf_counter()
        with telemetry.span("pipeline_snapshot_ms"):
            if request.snapshot_id:
                snapshot = _ri.get_repository_snapshot(
                    connector=connector, snapshot_id=request.snapshot_id
                )
                snapshot_status = "reused"
            else:
                snapshot = _ri.create_repository_snapshot(
                    connector=connector,
                    request=request.snapshot or RepositorySnapshotCreateRequest(),
                )
                # An identical prior snapshot resolves to status "existing".
                snapshot_status = "reused" if snapshot.status == "existing" else "ok"
        timings.append(
            RepositoryPipelineStageTiming(
                stage="snapshot",
                status=snapshot_status,
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )
        )

        triage = None
        decision_plan = None
        simulation = None
        completed_stage = "snapshot"

        # --- Stage 2: triage ------------------------------------------------
        if _should_run("triage", stop_after):
            start = time.perf_counter()
            with telemetry.span("pipeline_triage_ms"):
                triage = _ri.triage_repository(
                    connector=connector,
                    request=RepositoryTriageRequest(
                        snapshot_id=snapshot.snapshot_id,
                        signals=request.signals,
                        max_evidence_items=request.max_evidence_items,
                        max_snippet_lines=request.max_snippet_lines,
                        token_budget=request.token_budget,
                    ),
                )
            timings.append(
                RepositoryPipelineStageTiming(
                    stage="triage",
                    status="ok",
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                )
            )
            completed_stage = "triage"

        # --- Stage 3: plan (LLM) --------------------------------------------
        if triage is not None and _should_run("plan", stop_after):
            start = time.perf_counter()
            with telemetry.span("pipeline_plan_ms"):
                decision_plan = await _ri.create_repository_decision_plan(
                    connector=connector,
                    request=RepositoryDecisionPlanCreateRequest(
                        snapshot_id=snapshot.snapshot_id,
                        workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
                        model=request.model,
                    ),
                )
            timings.append(
                RepositoryPipelineStageTiming(
                    stage="plan",
                    status="ok",
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                )
            )
            completed_stage = "plan"

        # --- Stage 4: simulate (deterministic Mojo engine) ------------------
        if decision_plan is not None and _should_run("simulate", stop_after):
            start = time.perf_counter()
            with telemetry.span("pipeline_simulate_ms"):
                simulation = await _ri.simulate_repository_decision(
                    connector=connector,
                    request=RepositorySimulationRequest(
                        snapshot_id=snapshot.snapshot_id,
                        decision_plan_id=decision_plan.decision_plan_id,
                        runs=request.runs,
                        seed=request.seed,
                    ),
                )
            timings.append(
                RepositoryPipelineStageTiming(
                    stage="simulate",
                    status="ok",
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                )
            )
            completed_stage = "simulate"

        return RepositoryPipelineResponse(
            repository_id=snapshot.repository_id,
            snapshot_id=snapshot.snapshot_id,
            stop_after=stop_after,
            completed_stage=completed_stage,
            snapshot=snapshot,
            triage=triage,
            decision_plan=decision_plan,
            simulation=simulation,
            stage_timings=timings,
            telemetry=_telemetry_snapshot(telemetry_data),
        )
