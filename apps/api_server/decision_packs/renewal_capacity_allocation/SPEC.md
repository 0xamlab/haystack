# Renewal Capacity Allocation — Decision Pack contract (v0.1.0)

The first Algenta Decision Pack. Built **contracts-first**: this document + the code in
this package lock the schema, semantics, constraints, intervention-response assumptions,
validity ranges, and the unsupported-input / no-feasible-solution behavior **before** any
DB, API surface, or client UI.

## Decision framed
> Given upcoming renewals, account health, ARR, and available customer-success capacity,
> where should we allocate intervention time to maximize expected retained ARR?

- **Objective:** maximize expected retained ARR across the horizon.
- **Lever:** customer-success intervention hours per account.
- **Hard constraints (genuinely enforced):** total hours ≤ available capacity; per-CSM hours
  ≤ per-CSM capacity (when supplied); every strategic account receives ≥ `strategic_min_hours`.
- **Uncertainties:** intervention effectiveness (confounded — an assumption unless calibrated);
  baseline renewal probability (derived from health).
- **Outcome metrics:** expected retained ARR; uplift vs baseline; capacity utilization.

## Files
| File | Role |
|---|---|
| `contract.py` | Host-independent request/result schemas (the Decision API shape). |
| `evidence_contract.py` | Canonical concept semantics + the evidence-quality gate. |
| `outcome_model.py` | The confounded lever→outcome response model (versioned, deterministic). |
| `solver.py` | Constrained allocation + scenarios + sensitivity + no-feasible-solution. |
| `pack.py` | `run()` entrypoint + governed `DESCRIPTOR`. |
| `golden/` | Frozen reproducible outputs for the golden tests. |

## Honesty rules baked in
- The lever→outcome link is **confounded**; effectiveness is an explicit assumption
  (`calibration_status = "uncalibrated"` by default). Output reads *"model-estimated retained
  ARR under the stated intervention assumptions,"* never *"we will retain \$X."*
- Every figure is one of **observed fact / customer assumption / estimated parameter /
  simulated outcome** — kept separate in `ProvenanceSeparation`.
- The LM never generates numbers; the outcome model + solver do. Results carry
  `model_version` and `pack_version` for reproducibility.
- "N in the tested scenario set," not "N% probability," unless distributions are justified.

## Validity & failure behavior
- `health_score` valid range **[0, 100]**; out-of-range → `DomainValidityError` (no silent
  extrapolation). Pydantic also bounds inputs at the contract edge.
- Accounts missing required evidence (ARR ≤ 0 or no `renewal_date`) are **excluded** and the
  data-quality score is downgraded.
- Missing `health_score` falls back to the **segment-median** health and downgrades confidence.
- **No feasible solution** is a first-class result (not a fabricated answer) when:
  strategic minimums exceed total capacity; a CSM cannot cover its strategic minimums; or
  required evidence (ARR/renewal-date/capacity) is absent.

## Solver
Each account's expected-retained-ARR value function is **concave** in hours (the uplift curve
saturates), and there is a single shared budget plus per-account/per-CSM ceilings — so
**greedy marginal allocation is optimal**: seed hard strategic minimums, then repeatedly give
the next hour to the account with the highest marginal expected-ARR gain.

## Model version
`renewal_capacity_allocation.outcome_model@v0.1.0` · evidence
`renewal_capacity_allocation.evidence@v0.1.0` · pack `renewal_capacity_allocation@v0.1.0`.
Changing any of these is a governed model-behavior change and must update the golden fixture.
