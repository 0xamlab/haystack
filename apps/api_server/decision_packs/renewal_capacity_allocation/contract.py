"""Contract for the Renewal Capacity Allocation Decision Pack.

*Contracts first* (the mandated Phase-1 build order): lock the input/output schema,
the objective, hard/soft constraints, the intervention-response assumptions, validity
ranges, and the unsupported-input / no-feasible-solution behavior — before any DB or UI.

Decision framed by the pack:

    "Given upcoming renewals, account health, ARR, and available customer-success
     capacity, where should we allocate intervention time to maximize expected
     retained ARR?"

Everything here is host-independent structured data (the Decision API contract). The LM
may *frame* a request into this shape and *explain* the result; it never produces the
numbers — the outcome model + solver do (see :mod:`outcome_model`, :mod:`solver`).
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "PACK_ID",
    "PACK_VERSION",
    "Segment",
    "RenewalAccount",
    "CapacityInput",
    "InterventionAssumptions",
    "RenewalConstraints",
    "RenewalAllocationInput",
    "ConfidenceLevel",
    "ClaimClass",
    "AccountAllocation",
    "ConstraintStatus",
    "ScenarioResult",
    "SensitivityResult",
    "NoFeasibleSolution",
    "ProvenanceSeparation",
    "RenewalAllocationResult",
    "DEFAULT_ASSUMPTIONS",
    "DEFAULT_CONSTRAINTS",
]

PACK_ID = "renewal_capacity_allocation"
PACK_VERSION = "renewal_capacity_allocation@v0.1.0"


class Segment(StrEnum):
    strategic = "strategic"
    standard = "standard"


class ConfidenceLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class ClaimClass(StrEnum):
    """How a reported figure was produced — never blur these together in the UI."""

    observed_fact = "observed_fact"
    customer_assumption = "customer_assumption"
    estimated_parameter = "estimated_parameter"
    simulated_outcome = "simulated_outcome"


# ── inputs ──────────────────────────────────────────────────────────────────────────


class RenewalAccount(BaseModel):
    """One renewing account. See the Evidence Contract for canonical field semantics."""

    account_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=160)
    arr: float = Field(..., ge=0.0, description="Annual recurring revenue at risk (USD)")
    renewal_date: date | None = Field(None, description="Contract end date within the horizon")
    health_score: float | None = Field(
        None, ge=0.0, le=100.0, description="0–100 account-health score (higher = lower risk)"
    )
    segment: Segment = Field(Segment.standard)
    csm_id: str | None = Field(None, max_length=64, description="Owning CSM, for per-CSM capacity")
    # Optional: a pre-validated baseline renewal probability. If absent it is derived
    # from health_score by the outcome model. Must be a model output, never a guess.
    baseline_renewal_probability: float | None = Field(None, ge=0.0, le=1.0)


class CapacityInput(BaseModel):
    """Available customer-success intervention hours across the horizon."""

    total_hours: float = Field(..., ge=0.0)
    per_csm_hours: dict[str, float] = Field(
        default_factory=dict, description="Optional hard per-CSM ceilings, keyed by csm_id"
    )


class InterventionAssumptions(BaseModel):
    """The lever→outcome response assumptions — the confounded, net-new core.

    The causal relationship "+hours → renewal probability" is confounded (at-risk
    accounts already receive more attention), so effectiveness is an *explicit assumption*
    unless calibrated against realized renewals. Output language reflects this:
    "model-estimated retained ARR under the stated intervention assumptions."
    """

    effectiveness: float = Field(
        0.35,
        ge=0.0,
        le=1.0,
        description="Fraction of the renewal-probability gap intervention can close at saturation",
    )
    saturation_hours: float = Field(
        8.0,
        gt=0.0,
        description="Hours at which ~63% of the achievable uplift is realized (curve tau)",
    )
    max_useful_hours_per_account: float = Field(
        16.0, gt=0.0, description="Hours beyond which additional intervention adds ~nothing"
    )
    max_renewal_probability: float = Field(
        0.99, gt=0.0, le=1.0, description="Cap on estimated renewal probability"
    )
    segment_modifiers: dict[Segment, float] = Field(
        default_factory=lambda: {Segment.strategic: 1.0, Segment.standard: 1.0},
        description="Per-segment multiplier on achievable uplift",
    )
    source_of_estimate: str = Field(
        "default_prior",
        description="Where effectiveness came from: default_prior | expert | calibrated",
    )
    calibration_status: str = Field(
        "uncalibrated",
        description="uncalibrated | calibrated — governs the honesty of the output claim",
    )
    confidence: ConfidenceLevel = Field(ConfidenceLevel.low)

    @model_validator(mode="after")
    def _check_modifiers(self) -> InterventionAssumptions:
        for seg, mod in self.segment_modifiers.items():
            if mod < 0:
                raise ValueError(f"segment_modifier for {seg} must be >= 0 (got {mod})")
        return self


class RenewalConstraints(BaseModel):
    """Hard and soft constraints. Hard constraints are genuinely enforced by the solver."""

    strategic_min_hours: float = Field(
        4.0, ge=0.0, description="HARD: minimum hours every strategic account must receive"
    )
    max_hours_per_account: float | None = Field(
        None,
        ge=0.0,
        description="HARD: optional per-account ceiling (defaults to max useful hours)",
    )
    allocation_step_hours: float = Field(
        1.0, gt=0.0, le=8.0, description="Granularity of allocation (marginal-greedy step)"
    )

    @model_validator(mode="after")
    def _check(self) -> RenewalConstraints:
        if (
            self.max_hours_per_account is not None
            and self.max_hours_per_account < self.strategic_min_hours
        ):
            raise ValueError("max_hours_per_account cannot be below strategic_min_hours")
        return self


class RenewalAllocationInput(BaseModel):
    """The full, host-independent request for one renewal-allocation analysis."""

    accounts: list[RenewalAccount] = Field(..., min_length=1, max_length=5000)
    capacity: CapacityInput
    assumptions: InterventionAssumptions = Field(default_factory=InterventionAssumptions)
    constraints: RenewalConstraints = Field(default_factory=RenewalConstraints)
    horizon_days: int = Field(90, ge=1, le=730)
    objective: str = Field(
        "maximize_expected_retained_arr",
        description="Fixed for this pack; present for contract clarity",
    )


# ── outputs ─────────────────────────────────────────────────────────────────────────


class AccountAllocation(BaseModel):
    account_id: str
    name: str
    segment: Segment
    arr: float
    hours: float
    baseline_renewal_probability: float
    estimated_renewal_probability: float
    baseline_expected_retained_arr: float
    estimated_expected_retained_arr: float
    uplift_arr: float = Field(..., description="estimated − baseline expected retained ARR")
    selected: bool = Field(..., description="Received > 0 discretionary hours")
    reason: str = Field(..., description="Why this account was (or was not) prioritized")


class ConstraintStatus(BaseModel):
    name: str
    kind: str = Field(..., description="'hard' | 'soft'")
    satisfied: bool
    detail: str
    slack: float | None = Field(None, description="Remaining headroom, when meaningful")


class ScenarioResult(BaseModel):
    id: str
    label: str
    feasible: bool
    rejected_reason: str | None = None
    rank: int | None = None
    total_hours_used: float
    capacity_utilization: float = Field(..., description="hours used / total hours, 0–1")
    baseline_retained_arr: float
    expected_retained_arr: float
    uplift_arr: float
    allocations: list[AccountAllocation] = Field(default_factory=list)


class SensitivityResult(BaseModel):
    parameter: str
    base_value: float
    threshold_value: float | None = Field(
        None, description="Value at which the recommendation materially changes; None if stable"
    )
    direction: str = Field(..., description="'below' | 'above'")
    description: str


class NoFeasibleSolution(BaseModel):
    binding_constraint: str
    detail: str
    suggested_relaxations: list[str] = Field(default_factory=list)


class ProvenanceSeparation(BaseModel):
    """Keeps facts, assumptions, estimates, and simulated outcomes explicitly distinct."""

    observed_facts: list[str] = Field(default_factory=list)
    customer_assumptions: list[str] = Field(default_factory=list)
    estimated_parameters: list[str] = Field(default_factory=list)
    simulated_outcomes: list[str] = Field(default_factory=list)


class RenewalAllocationResult(BaseModel):
    """Host-independent result object. Renderers turn this into Adaptive Cards / Excel sheets."""

    model_config = ConfigDict(protected_namespaces=())

    pack_version: str = PACK_VERSION
    model_version: str
    feasible: bool
    no_feasible_solution: NoFeasibleSolution | None = None
    recommended_scenario_id: str | None = None
    scenarios: list[ScenarioResult] = Field(default_factory=list)
    constraints: list[ConstraintStatus] = Field(default_factory=list)
    sensitivity: list[SensitivityResult] = Field(default_factory=list)
    provenance: ProvenanceSeparation = Field(default_factory=ProvenanceSeparation)
    data_quality_score: int = Field(100, ge=0, le=100)
    confidence: ConfidenceLevel = ConfidenceLevel.low
    confidence_downgraded: bool = False
    evidence_notes: list[str] = Field(default_factory=list)
    disclaimer: str = Field(
        "Model-estimated retained ARR under the stated intervention assumptions. "
        "Figures are simulated outcomes, not guaranteed results."
    )


DEFAULT_ASSUMPTIONS = InterventionAssumptions()
DEFAULT_CONSTRAINTS = RenewalConstraints()
