"""
What-if parametric sweep — vary one variable across a range, holding all others fixed.

POST /v1/runs/{run_id}/what-if
GET  /v1/simulate/what-if  (inline — no stored run needed)

Use cases:
  - "What happens to my NPV as discount rate moves from 5% to 15%?"
  - "How does revenue sensitivity affect my probability of loss?"
  - "Show me the tornado chart for this simulation"

The endpoint returns a sweep: one simulation result per step, all computed
in parallel via asyncio.gather using the Mojo worker pool.
"""

import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.schemas.simulate import SimulateRequest, SimulateRequestExpert
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.simulation_service import run_simulation_fast

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["What-If Analysis"])


class WhatIfStep(BaseModel):
    """A single point in the what-if sweep."""

    model_config = ConfigDict(strict=False)
    step: int
    value: float
    label: str
    mean: float
    std: float
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float
    probability_of_loss: float
    score: float | None = None


class WhatIfResponse(BaseModel):
    """Full what-if sweep result."""

    model_config = ConfigDict(strict=False)
    variable: str
    n_steps: int
    range_low: float
    range_high: float
    param_changed: str
    steps: list[WhatIfStep]
    # Summary: which direction helps/hurts
    increasing_direction: str  # "better", "worse", "mixed"
    sensitivity_label: str  # "High sensitivity", "Low sensitivity", etc.
    elasticity: float  # Δ(EV%) / Δ(variable%)


class WhatIfRequest(BaseModel):
    """Inline what-if request (no stored run needed)."""

    model_config = ConfigDict(strict=False)
    request: SimulateRequest = Field(..., description="Base simulation request")
    variable: str = Field(..., description="Variable name to sweep")
    param: str = Field(
        default="mean", description="Which parameter to vary: mean, std, low, high, mode, value"
    )
    range_pct: float = Field(
        default=0.30, description="Sweep range as fraction of base value (e.g. 0.30 = ±30%)"
    )
    n_steps: int = Field(
        default=11,
        ge=3,
        le=51,
        description="Number of steps (odd number recommended for symmetric sweep)",
    )
    runs_per_step: int = Field(
        default=5000,
        ge=100,
        le=100_000,
        description="Monte Carlo runs per step. Lower for faster response.",
    )


def _make_step_request(
    base_request: SimulateRequest,
    variable_name: str,
    param: str,
    new_value: float,
    runs: int,
) -> SimulateRequest:
    """Clone the base request with one variable parameter modified."""
    if not isinstance(base_request, SimulateRequestExpert):
        raise HTTPException(400, "What-if only supported for expert-mode requests")

    # Deep-copy simulation dict and modify the target variable
    sim_data = base_request.simulation.model_dump()
    modified = False
    for var in sim_data.get("variables", []):
        if var["name"] == variable_name:
            if param in var.get("params", {}):
                var["params"] = dict(var["params"])
                var["params"][param] = new_value
                modified = True
            break

    if not modified:
        raise HTTPException(
            400,
            f"Variable '{variable_name}' or param '{param}' not found in request",
        )

    # Rebuild the request with modified variable
    payload = base_request.model_dump()
    payload["simulation"] = sim_data
    payload["runs"] = runs
    return SimulateRequestExpert(**payload)


@router.post(
    "/v1/simulate/what-if",
    response_model=WhatIfResponse,
    summary="What-if parametric sweep",
    description=(
        "Vary one variable parameter across a range and see how outcomes change. "
        "All steps run in parallel via Mojo worker pool. "
        "Returns a sweep with mean, percentiles, and probability of loss at each step. "
        "Automatically computes sensitivity direction and elasticity."
    ),
)
async def what_if_inline(
    request: Request,
    payload: WhatIfRequest,
    auth: AuthContext = Depends(get_current_org),
) -> WhatIfResponse:
    """Inline what-if — no stored run needed."""
    return await _run_what_if(
        base_request=payload.request,
        variable=payload.variable,
        param=payload.param,
        range_pct=payload.range_pct,
        n_steps=payload.n_steps,
        runs_per_step=payload.runs_per_step,
        auth=auth,
    )


async def _run_what_if(
    base_request: SimulateRequest,
    variable: str,
    param: str,
    range_pct: float,
    n_steps: int,
    runs_per_step: int,
    auth: AuthContext,
) -> WhatIfResponse:
    if not isinstance(base_request, SimulateRequestExpert):
        raise HTTPException(400, "What-if only supported for expert-mode requests")

    # Find base value of the variable/param
    base_value: float | None = None
    for var in base_request.simulation.variables:
        if var.name == variable:
            params_dict = var.params.model_dump(exclude_none=True)
            base_value = params_dict.get(param)
            break

    if base_value is None:
        raise HTTPException(400, f"Variable '{variable}' param '{param}' not found or is None")
    if base_value == 0.0:
        # Use absolute range when base is 0
        sweep_range = max(1.0, range_pct)
    else:
        sweep_range = abs(base_value) * range_pct

    # Build step values
    step_values: list[float] = []
    for i in range(n_steps):
        fraction = (i / (n_steps - 1)) * 2.0 - 1.0  # -1 to +1
        step_values.append(base_value + fraction * sweep_range)

    # Run all steps in parallel
    async def _run_step(step_idx: int, val: float) -> tuple[int, float, dict[str, Any]]:
        step_req = _make_step_request(base_request, variable, param, val, runs_per_step)
        envelope, _ = await run_simulation_fast(
            request=step_req,
            org_id=auth["org_id"],
            api_key_id=auth.get("key_id"),
        )
        return (
            step_idx,
            val,
            {
                "mean": envelope.metrics.expected_value,
                "std": envelope.metrics.std_deviation,
                "p5": envelope.percentiles.p5,
                "p25": envelope.percentiles.p25,
                "p50": envelope.percentiles.p50,
                "p75": envelope.percentiles.p75,
                "p95": envelope.percentiles.p95,
                "pol": envelope.metrics.probability_of_loss,
                "score": envelope.score,
            },
        )

    step_results = await asyncio.gather(*[_run_step(i, v) for i, v in enumerate(step_values)])
    step_results = sorted(step_results, key=lambda x: x[0])

    # Build WhatIfStep list
    steps: list[WhatIfStep] = []
    for i, val, stats in step_results:
        pct_label = (
            f"{((val - base_value) / (abs(base_value) or 1.0) * 100):+.1f}%"
            if base_value != 0
            else f"{val:+.3g}"
        )
        steps.append(
            WhatIfStep(
                step=i,
                value=val,
                label=f"{variable}={val:.4g} ({pct_label})",
                mean=stats["mean"],
                std=stats["std"],
                p5=stats["p5"],
                p25=stats["p25"],
                p50=stats["p50"],
                p75=stats["p75"],
                p95=stats["p95"],
                probability_of_loss=stats["pol"],
                score=stats["score"],
            )
        )

    # Compute sensitivity metrics
    ev_values = [s.mean for s in steps]
    base_ev = steps[len(steps) // 2].mean if steps else 0.0

    # Elasticity: (% change in EV) / (% change in variable)
    if base_value != 0.0 and base_ev != 0.0 and len(steps) >= 2:
        delta_ev_pct = (ev_values[-1] - ev_values[0]) / abs(base_ev) * 100.0
        delta_var_pct = (step_values[-1] - step_values[0]) / abs(base_value) * 100.0
        elasticity = delta_ev_pct / delta_var_pct if delta_var_pct != 0 else 0.0
    else:
        elasticity = 0.0

    # Direction: does increasing the variable help or hurt?
    if len(ev_values) >= 2:
        delta = ev_values[-1] - ev_values[0]
        if abs(delta) < abs(base_ev) * 0.01:
            direction = "insensitive"
        elif delta > 0:
            direction = "better"
        else:
            direction = "worse"
    else:
        direction = "mixed"

    # Sensitivity label based on elasticity magnitude
    abs_e = abs(elasticity)
    if abs_e >= 2.0:
        sens_label = "Very high sensitivity"
    elif abs_e >= 1.0:
        sens_label = "High sensitivity"
    elif abs_e >= 0.5:
        sens_label = "Moderate sensitivity"
    elif abs_e >= 0.1:
        sens_label = "Low sensitivity"
    else:
        sens_label = "Insensitive"

    return WhatIfResponse(
        variable=variable,
        n_steps=len(steps),
        range_low=step_values[0],
        range_high=step_values[-1],
        param_changed=param,
        steps=steps,
        increasing_direction=direction,
        sensitivity_label=sens_label,
        elasticity=round(elasticity, 3),
    )
