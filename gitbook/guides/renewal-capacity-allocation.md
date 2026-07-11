---
icon: chart-line
description: Allocate limited customer-success hours across upcoming renewals to maximize model-estimated retained ARR, modeling intervention effects explicitly under hard constraints.
---

# Renewal Capacity Allocation pack

Renewal Capacity Allocation is an Algenta Decision Pack. It answers one recurring, high-stakes question for a customer-success organization:

> Given upcoming renewals, account health, ARR, renewal dates, and the customer-success (CSM) hours you actually have, **where should you spend intervention time to maximize expected retained ARR?**

The pack does not guess. It takes your renewal book and your capacity, models how additional CSM hours change each account's renewal probability, then runs a constrained optimizer that respects your hard rules. The result is a defensible allocation — hours per account and per CSM — plus the baseline it beats, the accounts it left out and why, and an honest account of every assumption behind the numbers.

Like every Decision Pack, it runs deterministically in your organization's decision runtime: the same inputs always produce the same output, and every figure is versioned for reproducibility. The language model may help you frame a request and explain a result, but it never invents the numbers — the outcome model and solver do.

## The decision it frames

| Element | Value |
| --- | --- |
| **Objective** | Maximize expected retained ARR across the horizon |
| **Lever** | Customer-success intervention hours per account |
| **Hard constraints** | Total hours ≤ available capacity; per-CSM hours ≤ per-CSM capacity (when supplied); every strategic account receives at least its minimum guaranteed hours |
| **Uncertainties** | Intervention effectiveness (confounded — an assumption unless calibrated); baseline renewal probability (derived from health) |
| **Outcome metrics** | Expected retained ARR; uplift vs. baseline; capacity utilization |

## What you provide

The pack takes one structured request. You can assemble it by hand, from a query, or start from a **governed Excel template** so business users fill a familiar sheet and the values flow into the same validated contract (see [Run decisions from Excel](../integrations/microsoft/excel.md)).

{% stepper %}
{% step %}
### Renewal accounts

Each renewing account carries the evidence the decision needs:

* `arr` — annual recurring revenue at risk, in your currency (must be greater than 0).
* `renewal_date` — the contract end date inside the horizon.
* `health_score` — a 0–100 account-health score, where higher means lower risk.
* `segment` — `strategic` or `standard`.
* `csm_id` — the owning CSM, used to enforce per-CSM capacity.
* `baseline_renewal_probability` *(optional)* — a pre-validated model output; if absent it is derived from health.

Accounts missing required evidence (ARR ≤ 0, or no renewal date) are **excluded** rather than guessed, and the data-quality score is downgraded. A missing health score falls back to the segment-median health and lowers confidence. A health score outside 0–100 is rejected outright — the model never silently extrapolates.
{% endstep %}

{% step %}
### Available capacity

* `total_hours` — the customer-success intervention hours available across the horizon.
* `per_csm_hours` *(optional)* — hard ceilings per CSM, keyed by `csm_id`.
{% endstep %}

{% step %}
### Strategic-account rules and horizon

* `strategic_min_hours` — the **hard** minimum every strategic account is guaranteed (default 4h).
* `max_hours_per_account` *(optional)* — a hard per-account ceiling (defaults to the model's max useful hours).
* `allocation_step_hours` — the granularity the optimizer allocates in (default 1h).
* `horizon_days` — the renewal window in scope (default 90 days).
{% endstep %}

{% step %}
### Intervention-effect assumptions (pack config)

This is the honest core of the pack, supplied as configuration so it is visible and auditable rather than hidden inside a model:

* `effectiveness` — the fraction of an account's renewal-probability gap that intervention can close at saturation (default 0.35).
* `saturation_hours` — hours at which roughly 63% of the achievable uplift is realized — the shape of diminishing returns (default 8h).
* `max_useful_hours_per_account` — the point beyond which more hours add essentially nothing (default 16h).
* `max_renewal_probability` — a cap on the estimated renewal probability (default 0.99).
* `segment_modifiers` — per-segment multipliers on achievable uplift.
* `source_of_estimate` and `calibration_status` — where the effectiveness figure came from (`default_prior`, `expert`, or `calibrated`) and whether it has been calibrated against realized renewals. Each assumption also carries a `confidence` level.
{% endstep %}
{% endstepper %}

## How the outcome is modeled — honestly

The tempting causal story is "more CSM hours → higher renewal probability." That relationship is **confounded**: at-risk accounts already receive more attention, so a naive correlation overstates how much intervention actually helps. The pack refuses to launder that confounding into a false promise. Instead it models intervention effectiveness explicitly, and every part of the model is a stated, sourced assumption:

* **Baseline renewal probability** — a fixed, documented curve maps a 0–100 health score into a probability (roughly 0.15 at health 0, 0.95 at health 100). This is an *estimated parameter*, not tenant-calibrated by default.
* **Intervention response curve** — a saturating curve where uplift grows with hours but with strictly **diminishing returns**, so each additional hour is worth less than the one before.
* **Max-useful-hours cap** — hours beyond `max_useful_hours_per_account` contribute nothing, and the estimated probability is capped at `max_renewal_probability`.
* **Segment modifiers** — per-segment priors on how much uplift is achievable.

Uplift is applied to the *gap* to certainty and scaled by effectiveness and the segment modifier, so intervention (or zero hours) can only hold or raise an account's renewal probability — never lower it.

{% hint style="warning" %}
Because effectiveness is an assumption by default (`calibration_status = "uncalibrated"`), the pack's language is deliberately careful. It reports **"model-estimated retained ARR under the stated intervention assumptions"** — never "Algenta will retain $640K." Figures are simulated outcomes, not guaranteed results. Calibrate effectiveness against your realized renewals to strengthen the claim.
{% endhint %}

## What the pack returns

The result object is host-independent — renderers turn it into Adaptive Cards, Excel sheets, or an API response. It contains:

* **Recommended hours by account and CSM** — with each account's baseline vs. model-estimated renewal probability, baseline vs. estimated expected retained ARR, the uplift, whether it was selected, and a plain-language reason.
* **Expected retained ARR** and the **uplift vs. baseline**.
* **A baseline comparison** — the explicit do-nothing scenario the recommendation is measured against.
* **Accounts not selected, and why** — typically "lower marginal retained-ARR gain than funded accounts."
* **Hard-constraint status** — total capacity and strategic minimums, each marked satisfied or not, with remaining slack.
* **Capacity utilization** — hours used over hours available.
* **Sensitivity to intervention effectiveness** — whether the allocation is stable, the threshold (if any) at which it flips, and the estimated uplift at half the assumed effectiveness.
* **Alternatives** — ranked feasible scenarios, including a "concentrate on highest-ARR accounts" strategy that is shown *and* checked against the strategic-minimum guarantee.
* **Provenance separation** — observed facts, customer assumptions, estimated parameters, and simulated outcomes kept explicitly apart so nothing blurs together.

### A representative recommendation

```json
{
  "pack_version": "renewal_capacity_allocation@v0.1.0",
  "model_version": "renewal_capacity_allocation.outcome_model@v0.1.0",
  "feasible": true,
  "recommended_scenario_id": "recommended",
  "scenarios": [
    {
      "id": "recommended",
      "label": "Recommended — marginal-optimal allocation",
      "feasible": true,
      "rank": 1,
      "total_hours_used": 40,
      "capacity_utilization": 1.0,
      "baseline_retained_arr": 1840000.0,
      "expected_retained_arr": 2158000.0,
      "uplift_arr": 318000.0,
      "allocations": [
        {
          "account_id": "acc_204",
          "name": "Northwind Traders",
          "segment": "strategic",
          "arr": 480000.0,
          "hours": 12,
          "baseline_renewal_probability": 0.41,
          "estimated_renewal_probability": 0.63,
          "baseline_expected_retained_arr": 196800.0,
          "estimated_expected_retained_arr": 302400.0,
          "uplift_arr": 105600.0,
          "selected": true,
          "reason": "12h → +$105,600 expected retained ARR"
        },
        {
          "account_id": "acc_311",
          "name": "Contoso Cloud",
          "segment": "standard",
          "arr": 90000.0,
          "hours": 0,
          "baseline_renewal_probability": 0.88,
          "estimated_renewal_probability": 0.88,
          "baseline_expected_retained_arr": 79200.0,
          "estimated_expected_retained_arr": 79200.0,
          "uplift_arr": 0.0,
          "selected": false,
          "reason": "Not prioritized — lower marginal retained-ARR gain than funded accounts"
        }
      ]
    }
  ],
  "constraints": [
    { "name": "total_capacity", "kind": "hard", "satisfied": true, "detail": "40h used of 40h available", "slack": 0.0 },
    { "name": "strategic_min_hours", "kind": "hard", "satisfied": true, "detail": "3 strategic account(s) each guaranteed ≥ 4h" }
  ],
  "sensitivity": [
    {
      "parameter": "intervention_effectiveness",
      "base_value": 0.35,
      "threshold_value": null,
      "direction": "below",
      "description": "The allocation is stable to intervention-effectiveness down to 0.05 — a uniform change scales retained-ARR magnitude, not where hours go. At half the assumed effectiveness (0.18), estimated uplift falls to ~$168,000 (from ~$318,000)."
    }
  ],
  "provenance": {
    "observed_facts": [
      "18 renewal accounts in scope with validated ARR and renewal date.",
      "40h of customer-success capacity available."
    ],
    "customer_assumptions": [
      "Intervention effectiveness = 0.35 (default_prior, uncalibrated).",
      "Saturation at 8h; max useful 16h/account.",
      "Strategic minimum = 4h (hard)."
    ],
    "estimated_parameters": [
      "Baseline renewal probabilities derived from account health via the outcome-model curve."
    ],
    "simulated_outcomes": [
      "Expected retained ARR under the recommendation: $2,158,000 (+$318,000 vs baseline)."
    ]
  },
  "data_quality_score": 100,
  "confidence": "low",
  "confidence_downgraded": false,
  "disclaimer": "Model-estimated retained ARR under the stated intervention assumptions. Figures are simulated outcomes, not guaranteed results."
}
```

## When there is no feasible solution

Hard constraints are genuinely enforced, so the pack will tell you when they cannot all be met rather than fabricating an answer. It returns a first-class `no_feasible_solution` result — with the binding constraint and concrete suggested relaxations — when, for example:

* the strategic minimums together exceed total capacity;
* a single CSM cannot cover the strategic minimums of the accounts they own;
* a strategic minimum is larger than the per-account ceiling, so no account could ever receive it; or
* required evidence (ARR, renewal date, or capacity) is missing.

```json
{
  "feasible": false,
  "no_feasible_solution": {
    "binding_constraint": "strategic_min_hours",
    "detail": "9 strategic accounts require 36h of guaranteed minimums but only 30h are available.",
    "suggested_relaxations": [
      "Lower strategic_min_hours (currently 4h).",
      "Increase available capacity above 36h.",
      "Reduce the number of strategic accounts in scope."
    ]
  }
}
```

## Assemble and run the decision

{% stepper %}
{% step %}
### Gather the inputs

Collect your renewing accounts, available CSM hours, strategic rules, and intervention assumptions. Start from the governed Excel template if business users own the data — the same validation applies whether values arrive from a sheet or an API call.
{% endstep %}

{% step %}
### Submit to the decision service

Send the request to the Renewal Capacity Allocation pack through the governed decision endpoint. The service validates the contract, runs the outcome model and solver deterministically, and records the model and pack versions with the result. See [Drive a governed decision through the API](governed-decisions.md) for the request mechanics.
{% endstep %}

{% step %}
### Read the recommendation

Review the recommended allocation, the baseline it beats, the accounts left out and why, the hard-constraint status, and the sensitivity to effectiveness. Treat every ARR figure as model-estimated under the stated assumptions.
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — a `feasible: true` result whose `recommended_scenario_id` points at the marginal-optimal allocation. You will see hours assigned per account and per CSM, an expected retained ARR with an explicit uplift over the do-nothing baseline, every hard constraint marked satisfied with its remaining slack, the capacity utilization, a sensitivity note on intervention effectiveness, and a provenance block that keeps observed facts, your assumptions, estimated parameters, and simulated outcomes apart. If your rules cannot be met, you instead get an honest `no_feasible_solution` naming the binding constraint and how to relax it.
{% endhint %}

## Next steps

* [Drive a governed decision through the API](governed-decisions.md)
* [Run decisions from Excel](../integrations/microsoft/excel.md)
* [The governed decision lifecycle](../concepts/decision-service.md)