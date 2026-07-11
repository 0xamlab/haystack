"""The Foundry decision-evaluation pack (Workstream K-eval).

Proves the harness passes a real (golden) decision and *catches* a seeded-violation decision —
so the evaluators demonstrably flag an indefensible recommendation rather than shipping it.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from apps.api_server.services.decision_service.evaluators import EvalContext, evaluate_decision

FOUNDRY = Path(__file__).resolve().parents[1] / "infra" / "azure" / "foundry"
SAMPLES = FOUNDRY / "sample-data"


def _load(name: str) -> dict:
    return json.loads((SAMPLES / name).read_text())


def test_clean_decision_passes_all_evaluators() -> None:
    report = evaluate_decision(EvalContext(
        result=_load("renewal_clean.result.json"),
        recommendation=_load("renewal_clean.recommendation.json"),
    ))
    assert report.passed, [o.detail for o in report.failed]
    # numerical_grounding must actually have run (recommendation supplied), not skipped
    grounding = next(o for o in report.outcomes if o.name == "numerical_grounding")
    assert grounding.status == "passed"


def test_seeded_violation_is_caught() -> None:
    report = evaluate_decision(EvalContext(result=_load("renewal_violation.result.json")))
    assert not report.passed
    failed = {o.name for o in report.failed}
    assert "constraint_compliance" in failed  # a hard constraint is unsatisfied
    assert "unit_consistency" in failed        # probability 1.2 / utilization 1.5 out of range


def test_recommendation_numbers_trace_to_engine_output() -> None:
    # every >=100 figure in the shipped clean recommendation exists in the golden result
    reco = _load("renewal_clean.recommendation.json")
    report = evaluate_decision(EvalContext(
        result=_load("renewal_clean.result.json"), recommendation=reco,
    ))
    assert next(o for o in report.outcomes if o.name == "numerical_grounding").status == "passed"


def test_runner_exits_zero_on_shipped_cases() -> None:
    spec = importlib.util.spec_from_file_location(
        "_run_evals", FOUNDRY / "evaluations" / "run_evals.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    # clean -> pass (expect pass), violation -> fail (expect fail): both match => exit 0
    assert mod.main([str(FOUNDRY / "evaluations" / "run_evals.py")]) == 0
