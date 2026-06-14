"""
Decision endpoints:
  POST /v1/recommend — compare actions, return ranked recommendation
  POST /v1/score     — score simulation with custom weights
  POST /v1/batch     — run multiple simulations
  POST /v1/compare   — side-by-side scenario comparison
"""

import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request

from apps.api_server.middleware.auth import get_current_org, require_verified_email
from apps.api_server.schemas.recommend import (
    ActionResult,
    BatchItemResult,
    BatchRequest,
    BatchResponse,
    CompareRequest,
    CompareResponse,
    ComparisonDelta,
    RecommendRequest,
    RecommendResponse,
    ScenarioComparison,
    ScoreRequest,
    ScoreResponse,
)
from apps.api_server.schemas.response import (
    DecisionEnvelope,
    DecisionOption,
    RiskProfile,
    build_decision_plan,
)
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.simulation_service import run_simulation_fast

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Decision"], dependencies=[Depends(require_verified_email)])


@router.post(
    "/v1/recommend",
    response_model=RecommendResponse,
    summary="Compare actions and get a recommendation",
    description=(
        "Run simulations for 2–10 named actions and return them ranked by expected value. "
        "The top-ranked action is returned as `recommended_action`."
    ),
)
async def recommend(
    request: Request,
    payload: RecommendRequest,
    auth: AuthContext = Depends(get_current_org),
) -> RecommendResponse:
    # Run all actions in parallel via fast path — compute only, async persist
    async def _run_action(name: str, sim_req: Any) -> tuple[str, DecisionEnvelope]:
        envelope, _ = await run_simulation_fast(
            request=sim_req,
            org_id=auth["org_id"],
            api_key_id=auth["key_id"],
        )
        return (name, envelope)

    results: list[tuple[str, DecisionEnvelope]] = await asyncio.gather(
        *[_run_action(action.name, action.request) for action in payload.actions]
    )

    # Rank by expected value descending
    ranked = sorted(results, key=lambda x: x[1].metrics.expected_value, reverse=True)

    action_results = []
    for i, (name, envelope) in enumerate(ranked):
        # Simple score: weighted combo of EV normalization and 1-PoL
        ev = envelope.metrics.expected_value
        pol = envelope.metrics.probability_of_loss
        max_ev = max(abs(r[1].metrics.expected_value) for r in ranked) or 1.0
        ev_norm = max(0.0, min(1.0, (ev + max_ev) / (2 * max_ev)))
        score = round(0.6 * ev_norm + 0.4 * (1.0 - pol), 4)

        action_results.append(
            ActionResult(
                name=name,
                rank=i + 1,
                envelope=envelope,
                expected_value=ev,
                probability_of_loss=pol,
                score=score,
            )
        )

    best = action_results[0]
    prob_positive = round(1 - best.probability_of_loss, 4)

    # Build structured DecisionPlan with all ranked options
    plan_options = [
        DecisionOption(
            name=ar.name,
            rank=ar.rank,
            expected_value=ar.expected_value,
            risk=RiskProfile(
                p5=ar.envelope.percentiles.p5,
                p95=ar.envelope.percentiles.p95,
                probability_of_loss=ar.probability_of_loss,
                var_95=ar.envelope.metrics.var_95,
            ),
            score=ar.score,
        )
        for ar in action_results
    ]
    decision_plan = build_decision_plan(best.envelope, options=plan_options)

    # Apply historical calibration to confidence (raw stays in envelope.confidence)
    try:
        from apps.api_server.services.calibration_service import calibrate_confidence

        cal_conf, cal_stats = calibrate_confidence(
            decision_plan.confidence,
            str(auth["org_id"]),
            workspace_id=str(auth["workspace_id"]) if auth.get("workspace_id") else None,
        )
        decision_plan.confidence = cal_conf
        if cal_stats.is_reliable:
            decision_plan.calibration = cal_stats.summary()
    except Exception as exc:
        logger.debug("recommend_calibration_failed", error=str(exc))

    return RecommendResponse(
        recommended_action=best.name,
        confidence=round(best.score, 4),
        rationale=(
            f"'{best.name}' ranked #1 with expected value {best.expected_value:.6g} "
            f"and {prob_positive:.0%} probability of positive outcome."
        ),
        action_results=action_results,
        total_actions=len(action_results),
        decision_plan=decision_plan,
    )


@router.post(
    "/v1/score",
    response_model=ScoreResponse,
    summary="Score a simulation with custom weights",
)
async def score(
    request: Request,
    payload: ScoreRequest,
    auth: AuthContext = Depends(get_current_org),
) -> ScoreResponse:
    envelope, _ = await run_simulation_fast(
        request=payload.request,
        org_id=auth["org_id"],
        api_key_id=auth["key_id"],
    )

    weights = payload.scoring_weights or {"expected_value": 0.6, "downside_risk": 0.4}
    ev_w = float(weights.get("expected_value", 0.6))
    dr_w = float(weights.get("downside_risk", 0.4))

    ev = envelope.metrics.expected_value
    pol = envelope.metrics.probability_of_loss
    abs_ev = abs(ev) or 1.0
    ev_norm = max(0.0, min(1.0, (ev + abs_ev) / (2 * abs_ev)))
    final_score = round(ev_w * ev_norm + dr_w * (1.0 - pol), 4)

    return ScoreResponse(
        envelope=envelope,
        score=final_score,
        score_breakdown={
            "expected_value_component": round(ev_w * ev_norm, 4),
            "downside_risk_component": round(dr_w * (1.0 - pol), 4),
            "expected_value_weight": ev_w,
            "downside_risk_weight": dr_w,
        },
    )


@router.post(
    "/v1/batch",
    response_model=BatchResponse,
    summary="Run multiple simulations in one request",
    description=(
        "Submit 1–100 simulation requests. Partial failures are allowed; "
        "failed items include an error message."
    ),
)
async def batch(
    request: Request,
    payload: BatchRequest,
    auth: AuthContext = Depends(get_current_org),
) -> BatchResponse:
    results: list[BatchItemResult] = []
    succeeded = 0
    failed_count = 0

    async def _run_item(idx: int, item: Any) -> BatchItemResult:
        try:
            envelope, _ = await run_simulation_fast(
                request=item,
                org_id=auth["org_id"],
                api_key_id=auth["key_id"],
            )
            return BatchItemResult(index=idx, success=True, envelope=envelope)
        except Exception as exc:
            return BatchItemResult(index=idx, success=False, error=str(exc))

    # Run all simulations in parallel
    batch_results = await asyncio.gather(
        *[_run_item(i, item) for i, item in enumerate(payload.items)]
    )
    results = list(batch_results)
    succeeded = sum(1 for r in results if r.success)
    failed_count = sum(1 for r in results if not r.success)
    failed = failed_count  # noqa: F841

    return BatchResponse(
        total=len(payload.items),
        succeeded=succeeded,
        failed=failed_count,
        results=results,
    )


@router.post(
    "/v1/compare",
    response_model=CompareResponse,
    summary="Side-by-side scenario comparison",
    description=(
        "Run and compare 2–10 named scenarios. Returns full results with "
        "deltas versus the winning scenario."
    ),
)
async def compare(
    request: Request,
    payload: CompareRequest,
    auth: AuthContext = Depends(get_current_org),
) -> CompareResponse:
    # Run all scenarios in parallel — maximum throughput
    async def _run_scenario(name: str, sim_req: Any) -> tuple[str, DecisionEnvelope]:
        envelope, _ = await run_simulation_fast(
            request=sim_req,
            org_id=auth["org_id"],
            api_key_id=auth["key_id"],
        )
        return (name, envelope)

    scenario_results: list[tuple[str, DecisionEnvelope]] = list(
        await asyncio.gather(*[_run_scenario(s.name, s.request) for s in payload.scenarios])
    )

    # Find winner by expected value
    best_name, best_envelope = max(scenario_results, key=lambda x: x[1].metrics.expected_value)

    comparisons: list[ScenarioComparison] = []
    for name, envelope in scenario_results:
        delta = ComparisonDelta(
            expected_value_delta=(
                envelope.metrics.expected_value - best_envelope.metrics.expected_value
            ),
            probability_of_loss_delta=(
                envelope.metrics.probability_of_loss - best_envelope.metrics.probability_of_loss
            ),
            score_delta=0.0,
        )
        comparisons.append(ScenarioComparison(name=name, envelope=envelope, delta_vs_best=delta))

    winner_delta = ComparisonDelta(
        expected_value_delta=best_envelope.metrics.expected_value
        - min(e.metrics.expected_value for _, e in scenario_results),
        probability_of_loss_delta=best_envelope.metrics.probability_of_loss
        - max(e.metrics.probability_of_loss for _, e in scenario_results),
        score_delta=0.0,
    )

    return CompareResponse(
        winner=best_name,
        margin=winner_delta,
        scenarios=comparisons,
    )
