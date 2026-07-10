"""Evidence Contract for the Renewal Capacity Allocation pack.

An input schema alone is insufficient: customers define ARR, "renewal", account
health, capacity, and "strategic" differently, so the *same* pack would otherwise
produce incomparable outputs across tenants. The Evidence Contract pins the
canonical meaning of every business concept the pack consumes — definition, unit +
valid range, authoritative source, freshness requirement, null handling,
transformation rules, quality threshold, sensitivity classification, and permitted
fallback.

The analysis **blocks or downgrades confidence** when required evidence is stale,
incomplete, or semantically incompatible (see :func:`assess_evidence`). This is a
governance boundary, not a convenience check.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

__all__ = [
    "SensitivityClass",
    "EvidenceConcept",
    "EVIDENCE_CONTRACT",
    "EVIDENCE_CONTRACT_VERSION",
    "EvidenceIssue",
    "EvidenceQuality",
    "assess_evidence",
]

EVIDENCE_CONTRACT_VERSION = "renewal_capacity_allocation.evidence@v0.1.0"


class SensitivityClass(StrEnum):
    """Data-sensitivity classification — drives what may leave the Decision Service."""

    public = "public"
    internal = "internal"
    confidential = "confidential"
    restricted = "restricted"


class EvidenceConcept(BaseModel):
    """Canonical definition of one business concept the pack depends on."""

    name: str = Field(..., description="Concept key, e.g. 'renewal_probability'")
    definition: str = Field(..., description="Precise, tenant-independent meaning")
    unit: str = Field(..., description="Canonical unit, e.g. 'USD', 'probability', 'hours'")
    valid_min: float | None = Field(None, description="Inclusive lower bound (if numeric)")
    valid_max: float | None = Field(None, description="Inclusive upper bound (if numeric)")
    authoritative_source: str = Field(..., description="System of record the value must come from")
    freshness_max_age_days: int | None = Field(
        None, description="Max acceptable age of the value; None = not time-sensitive"
    )
    required: bool = Field(True, description="Whether the analysis can proceed without it")
    null_handling: str = Field(..., description="What a missing/null value means and does")
    transformation_rules: str = Field("", description="Normalization applied before use")
    quality_threshold: str = Field("", description="Minimum quality bar for use")
    sensitivity: SensitivityClass = Field(
        SensitivityClass.confidential, description="Data-sensitivity classification"
    )
    permitted_fallback: str = Field(
        "none", description="The only fallback allowed when the value is missing"
    )


# The canonical contract. Extend deliberately — every field consumed by the outcome
# model or solver must have an entry, or coverage checks will flag it.
EVIDENCE_CONTRACT: tuple[EvidenceConcept, ...] = (
    EvidenceConcept(
        name="arr",
        definition=(
            "Annual recurring revenue attributable to the renewing contract, net of "
            "one-off and services revenue, in the reporting currency."
        ),
        unit="USD",
        valid_min=0.0,
        valid_max=1_000_000_000.0,
        authoritative_source="billing_system",
        freshness_max_age_days=31,
        null_handling="Account is excluded from the analysis; recorded as unavailable.",
        transformation_rules="Convert to reporting currency at the run-time FX snapshot.",
        quality_threshold="Must reconcile to the billing ledger within 1%.",
        sensitivity=SensitivityClass.confidential,
        permitted_fallback="none",
    ),
    EvidenceConcept(
        name="renewal_date",
        definition="Contract end date at which the renewal decision takes effect.",
        unit="date",
        authoritative_source="crm",
        freshness_max_age_days=31,
        null_handling="Account is excluded; a renewal with no date cannot be scheduled.",
        transformation_rules="Normalize to the tenant's fiscal calendar / UTC date.",
        quality_threshold="Must fall within the decision horizon.",
        sensitivity=SensitivityClass.confidential,
        permitted_fallback="none",
    ),
    EvidenceConcept(
        name="account_health",
        definition=(
            "A 0–100 account-health score where higher means lower churn risk, from the "
            "tenant's health model (support, usage, sentiment, NPS)."
        ),
        unit="score_0_100",
        valid_min=0.0,
        valid_max=100.0,
        authoritative_source="customer_success_platform",
        freshness_max_age_days=14,
        null_handling=(
            "Baseline renewal probability falls back to the segment median; confidence downgraded."
        ),
        transformation_rules="Rescale any native range to 0–100.",
        quality_threshold="Health model refreshed within 14 days.",
        sensitivity=SensitivityClass.confidential,
        permitted_fallback="segment_median_health",
    ),
    EvidenceConcept(
        name="available_capacity",
        definition="Customer-success intervention hours available across the horizon.",
        unit="hours",
        valid_min=0.0,
        valid_max=1_000_000.0,
        authoritative_source="capacity_plan",
        freshness_max_age_days=14,
        null_handling="No capacity means no allocation is possible; analysis blocks.",
        transformation_rules="Sum per-CSM available hours net of committed time.",
        quality_threshold="Reconciled to the staffing plan.",
        sensitivity=SensitivityClass.internal,
        permitted_fallback="none",
    ),
    EvidenceConcept(
        name="strategic_account",
        definition=(
            "Boolean flag marking an account as strategic per the tenant's account-tiering "
            "policy; strategic accounts carry a hard minimum-hours guarantee."
        ),
        unit="boolean",
        authoritative_source="account_tiering_policy",
        freshness_max_age_days=90,
        null_handling="Treated as non-strategic; no minimum-hours guarantee applied.",
        transformation_rules="Map tenant tier labels to the strategic flag.",
        quality_threshold="Tiering reviewed within the quarter.",
        sensitivity=SensitivityClass.internal,
        permitted_fallback="not_strategic",
    ),
    EvidenceConcept(
        name="renewal_probability",
        definition=(
            "Baseline probability the account renews with NO additional intervention, in "
            "[0,1]. Derived from account_health via the outcome model's baseline curve."
        ),
        unit="probability",
        valid_min=0.0,
        valid_max=1.0,
        authoritative_source="derived:outcome_model",
        freshness_max_age_days=14,
        required=False,
        null_handling="Derived from account_health at run time when not supplied.",
        transformation_rules="If supplied directly, must be a validated model output, not a guess.",
        quality_threshold="Calibrated against realized renewals where history exists.",
        sensitivity=SensitivityClass.confidential,
        permitted_fallback="derive_from_health",
    ),
)


class EvidenceIssue(BaseModel):
    """One problem found while assessing an input against the Evidence Contract."""

    concept: str
    severity: str = Field(..., description="'blocking' | 'degrading'")
    detail: str


class EvidenceQuality(BaseModel):
    """Outcome of assessing an input dataset against the Evidence Contract."""

    ok: bool = Field(..., description="False when any blocking issue is present")
    data_quality_score: int = Field(..., ge=0, le=100)
    confidence_downgraded: bool = False
    issues: list[EvidenceIssue] = Field(default_factory=list)

    @property
    def blocking(self) -> list[EvidenceIssue]:
        return [i for i in self.issues if i.severity == "blocking"]


def _concept(name: str) -> EvidenceConcept | None:
    return next((c for c in EVIDENCE_CONTRACT if c.name == name), None)


def assess_evidence(
    *,
    account_count: int,
    excluded_account_count: int,
    health_fallback_count: int,
    max_health_age_days: int | None,
    max_arr_age_days: int | None,
    available_hours: float,
) -> EvidenceQuality:
    """Assess dataset-level evidence quality; block or downgrade confidence per contract.

    This is intentionally coarse and deterministic — a governance gate, not a model.
    Blocking issues stop the run (``ok=False``); degrading issues lower the data-quality
    score and flag ``confidence_downgraded`` so the recommendation carries the caveat.
    """

    issues: list[EvidenceIssue] = []
    score = 100

    if account_count <= 0:
        issues.append(
            EvidenceIssue(
                concept="arr",
                severity="blocking",
                detail="No renewal accounts with usable ARR/renewal_date remain after validation.",
            )
        )
    if available_hours <= 0:
        cap = _concept("available_capacity")
        issues.append(
            EvidenceIssue(
                concept="available_capacity",
                severity="blocking",
                detail=(cap.null_handling if cap else "No available capacity.")
                + " No allocation is possible.",
            )
        )

    if excluded_account_count > 0:
        score -= min(30, excluded_account_count * 5)
        issues.append(
            EvidenceIssue(
                concept="arr",
                severity="degrading",
                detail=(
                    f"{excluded_account_count} account(s) excluded for missing ARR/renewal_date."
                ),
            )
        )

    if health_fallback_count > 0:
        score -= min(25, health_fallback_count * 5)
        issues.append(
            EvidenceIssue(
                concept="account_health",
                severity="degrading",
                detail=(
                    f"{health_fallback_count} account(s) used the segment-median health fallback; "
                    "baseline renewal probability is less reliable for them."
                ),
            )
        )

    health = _concept("account_health")
    if (
        health is not None
        and health.freshness_max_age_days is not None
        and max_health_age_days is not None
        and max_health_age_days > health.freshness_max_age_days
    ):
        score -= 15
        issues.append(
            EvidenceIssue(
                concept="account_health",
                severity="degrading",
                detail=(
                    f"Health data {max_health_age_days}d (max {health.freshness_max_age_days}d); "
                    "confidence downgraded."
                ),
            )
        )

    arr = _concept("arr")
    if (
        arr is not None
        and arr.freshness_max_age_days is not None
        and max_arr_age_days is not None
        and max_arr_age_days > arr.freshness_max_age_days
    ):
        score -= 15
        issues.append(
            EvidenceIssue(
                concept="arr",
                severity="degrading",
                detail=(
                    f"ARR data is {max_arr_age_days}d (max {arr.freshness_max_age_days}d); "
                    "confidence downgraded."
                ),
            )
        )

    score = max(0, min(100, score))
    blocking = [i for i in issues if i.severity == "blocking"]
    degrading = [i for i in issues if i.severity == "degrading"]
    return EvidenceQuality(
        ok=not blocking,
        data_quality_score=score,
        confidence_downgraded=bool(degrading),
        issues=issues,
    )
