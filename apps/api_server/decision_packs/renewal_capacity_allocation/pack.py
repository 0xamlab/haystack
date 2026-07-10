"""Pack entrypoint + descriptor for Renewal Capacity Allocation.

``run()`` is the single deterministic entrypoint the Decision Service calls. ``DESCRIPTOR``
is the governed metadata (objective, levers, constraints, uncertainties, outcome metrics,
model + evidence versions) that the model registry and Decision Pack catalog record.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .contract import PACK_ID, PACK_VERSION, RenewalAllocationInput, RenewalAllocationResult
from .evidence_contract import EVIDENCE_CONTRACT_VERSION
from .outcome_model import MODEL_LIMITATIONS, MODEL_VERSION
from .solver import solve

__all__ = ["run", "DESCRIPTOR", "PackDescriptor"]


class PackDescriptor(BaseModel):
    """Governed, registry-facing description of the pack (no free-form model-version strings)."""

    model_config = ConfigDict(protected_namespaces=())

    pack_id: str = PACK_ID
    pack_version: str = PACK_VERSION
    model_version: str = MODEL_VERSION
    evidence_contract_version: str = EVIDENCE_CONTRACT_VERSION
    title: str = "Renewal Capacity Allocation"
    question: str = (
        "Given upcoming renewals, account health, ARR, and available customer-success "
        "capacity, where should we allocate intervention time to maximize expected retained ARR?"
    )
    objective: str = "Maximize expected retained ARR across the horizon"
    levers: list[str] = Field(
        default_factory=lambda: ["customer_success_hours_per_account"]
    )
    hard_constraints: list[str] = Field(
        default_factory=lambda: [
            "total customer-success hours <= available capacity",
            "per-CSM hours <= per-CSM capacity (when supplied)",
            "each strategic account receives >= strategic_min_hours",
        ]
    )
    uncertainties: list[str] = Field(
        default_factory=lambda: [
            "intervention effectiveness (confounded — assumption unless calibrated)",
            "baseline renewal probability (derived from health)",
        ]
    )
    outcome_metrics: list[str] = Field(
        default_factory=lambda: [
            "expected_retained_arr",
            "uplift_arr_vs_baseline",
            "capacity_utilization",
        ]
    )
    limitations: list[str] = Field(default_factory=lambda: list(MODEL_LIMITATIONS))


DESCRIPTOR = PackDescriptor()


def run(inp: RenewalAllocationInput) -> RenewalAllocationResult:
    """Execute the pack. Pure/deterministic: same input → identical output."""

    return solve(inp)
