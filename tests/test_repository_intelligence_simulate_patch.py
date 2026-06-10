"""In-flight working-tree patch simulation (the verified_agentic simulate_patch tool):
no stored decision plan needed — the sim request is built straight from the patch impact
and gated by the same calibrated-risk policy as the stored-plan path.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.api_server.schemas.repositories import RepositorySimulatePatchRequest
from apps.api_server.schemas.response import DecisionEnvelope, MetricsSummary
from apps.api_server.services import repository_intelligence_execution_workflow as ew


def test_patch_impact_request_uses_shared_builder() -> None:
    """The patch path must produce the SAME Monte Carlo request as the shared builder
    (so the in-flight sim is identical to the stored-plan sim for equal inputs)."""
    impact = {
        "blast_radius": "medium",
        "rollback_complexity": "low",
        "impacted_symbols": ["a", "b"],
        "likely_failing_tests": ["t1"],
    }
    from_patch = ew._simulation_request_from_patch_impact(impact, 0.7)
    direct = ew._simulation_request_payload(
        blast_radius="medium",
        rollback_complexity="low",
        impacted_symbol_count=2,
        likely_failing_test_count=1,
        confidence=0.7,
    )
    assert from_patch.model_dump() == direct.model_dump()
    # and it's a valid expert request with the risk variables wired
    names = {v.name for v in from_patch.simulation.variables}
    assert {"repair_value", "blast_radius_cost", "rollback_cost"} <= names


def test_adaptive_simulation_runs_scales_with_complexity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario count must scale with patch complexity + uncertainty (not be static),
    stay within [floor, ceiling], be deterministic, and honor the pin override."""
    monkeypatch.delenv("ALGENTA_REPOSITORY_SIMULATION_RUNS", raising=False)

    trivial = ew._adaptive_simulation_runs(
        blast_radius="low",
        rollback_complexity="low",
        impacted_symbol_count=0,
        likely_failing_test_count=0,
        confidence=0.95,
    )
    risky = ew._adaptive_simulation_runs(
        blast_radius="high",
        rollback_complexity="high",
        impacted_symbol_count=40,
        likely_failing_test_count=20,
        confidence=0.4,
    )

    # A trivial high-confidence patch costs fewer scenarios than the old static 5000;
    # a risky low-confidence one costs more — and both stay within bounds.
    assert ew._SIMULATION_RUNS_FLOOR <= trivial < 5_000
    assert 5_000 < risky <= ew._SIMULATION_RUNS_CEILING
    assert trivial < risky
    # Deterministic for fixed inputs (cold/hot snapshots must reproduce).
    assert trivial == ew._adaptive_simulation_runs(
        blast_radius="low",
        rollback_complexity="low",
        impacted_symbol_count=0,
        likely_failing_test_count=0,
        confidence=0.95,
    )

    # The env override pins a fixed count (kill-switch / golden fixtures).
    monkeypatch.setenv("ALGENTA_REPOSITORY_SIMULATION_RUNS", "5000")
    pinned = ew._adaptive_simulation_runs(
        blast_radius="high",
        rollback_complexity="high",
        impacted_symbol_count=40,
        likely_failing_test_count=20,
        confidence=0.4,
    )
    assert pinned == 5_000


def test_simulation_request_payload_uses_adaptive_runs() -> None:
    """The shared builder must wire the adaptive count into the MC request `runs`."""
    simple = ew._simulation_request_payload(
        blast_radius="low",
        rollback_complexity="low",
        impacted_symbol_count=0,
        likely_failing_test_count=0,
        confidence=0.95,
    )
    complex_ = ew._simulation_request_payload(
        blast_radius="high",
        rollback_complexity="high",
        impacted_symbol_count=40,
        likely_failing_test_count=20,
        confidence=0.4,
    )
    assert simple.runs < complex_.runs


async def test_simulate_repository_patch_applies_gate() -> None:
    impact = {
        "blast_radius": "low",
        "rollback_complexity": "low",
        "impacted_symbols": [],
        "likely_failing_tests": [],
    }

    def _make_envelope(confidence: float, var_95: float) -> DecisionEnvelope:
        return DecisionEnvelope.model_construct(
            recommended_action="pending",
            confidence=confidence,
            metrics=MetricsSummary.model_construct(var_95=var_95),
        )

    async def _run(_req, *, org_id, api_key_id):  # noqa: ANN001
        return _make_envelope(0.92, 5.0), {}

    connector = SimpleNamespace(
        org_id="11111111-1111-1111-1111-111111111111",
        id="22222222-2222-2222-2222-222222222222",
        owner_key_id=None,
    )
    req = RepositorySimulatePatchRequest(snapshot_id="snap-1", patch_diff="diff", confidence=0.9)

    async def call(min_confidence: float, risk_floor: float | None) -> str:
        env = await ew.simulate_repository_patch(
            connector=connector,
            request=req,
            require_repository_connector=lambda _c: None,
            get_policy=lambda _o: SimpleNamespace(min_confidence=min_confidence, risk_floor=risk_floor),
            load_snapshot_manifest=lambda **_k: {"snapshot_id": "snap-1", "files": []},
            validate_patch_against_snapshot=lambda **_k: None,
            patch_impact_summary=lambda _m, _d: impact,
            run_simulation_fast=_run,
        )
        return env.recommended_action

    # confidence 0.92 >= 0.8 and var_95 5.0 <= 20.0 -> apply
    assert await call(0.8, 20.0) == "apply_patch"
    # var_95 5.0 > floor 1.0 -> hold
    assert await call(0.8, 1.0) == "hold_patch"
    # confidence 0.92 < 0.95 -> hold
    assert await call(0.95, 20.0) == "hold_patch"
