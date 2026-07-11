---
icon: diagram-project
description: Frame a decision case, run the governed analysis, inspect the evidence, then propose, approve, and execute an action plan through the host-independent Decision API
---

# Drive a governed decision through the API

The Decision API turns a business question into an auditable, reproducible decision. You frame a case against a decision pack, run a governed analysis, read a host-independent recommendation, and — only after an explicit, credentialed approval — execute a plan and record what actually happened so the next run is better calibrated.

This walkthrough is transport-only: every step is a plain HTTP request you can issue with `curl`, the same requests the Excel add-in and other surfaces make under the hood. The analysis runs in your organization's decision runtime; the responses are structured JSON, not tied to any host.

## Before you start

You need two values throughout:

* `$GATEWAY_URL` — the base URL of your Decision API gateway (for example, `https://decisions.example.com`).
* `$ACCESS_TOKEN` — a bearer access token whose **audience** is the Decision API. Obtain it from your organization's identity provider the same way you would for any protected internal API; the token carries the caller's role, which the approval and execution steps enforce.

Every request sends `Authorization: Bearer $ACCESS_TOKEN`. Later steps reuse IDs returned by earlier ones — `$CASE_ID`, `$RUN_ID`, `$PLAN_ID`, `$PLAN_HASH`, and `$NONCE`.

{% hint style="info" %}
This walkthrough uses the **Renewal Capacity Allocation** pack (`renewal_capacity_allocation`), which answers "given upcoming renewals and limited customer-success capacity, where should we spend intervention time to maximize expected retained ARR?" The same request/response shapes apply to any pack — only the `pack_input` and the numbers inside `result` change.
{% endhint %}

## The nine calls

{% stepper %}
{% step %}
### Create a case

`POST /v1/decision-cases` frames the decision. The body names a `pack_id` and carries the pack's validated `pack_input` — the objective, horizon, levers (capacity), constraints, and assumptions. Creating a case writes an **immutable first revision**: the exact inputs are hashed so every later result can be traced back to what was framed.

```bash
curl -sS -X POST "$GATEWAY_URL/v1/decision-cases" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pack_id": "renewal_capacity_allocation",
    "title": "Q3 renewal capacity — enterprise segment",
    "owner": "renewals-team@example.com",
    "objective": "maximize_expected_retained_arr",
    "horizon_days": 90,
    "pack_input": {
      "accounts": [
        {"account_id": "A1", "name": "BigCo", "arr": 500000, "segment": "standard", "health_score": 42},
        {"account_id": "A3", "name": "SmallStrategic", "arr": 60000, "segment": "strategic", "health_score": 55},
        {"account_id": "A5", "name": "KeyStrategic", "arr": 90000, "segment": "strategic", "health_score": 70}
      ],
      "capacity": {"total_hours": 40},
      "constraints": {"strategic_min_hours": 4},
      "horizon_days": 90
    }
  }'
```

A `201 Created` returns the case id and the current revision:

```json
{
  "case_id": "8f2a1c7e-0b44-4d9a-9c31-0e5b2a6f1d20",
  "pack_id": "renewal_capacity_allocation",
  "title": "Q3 renewal capacity — enterprise segment",
  "owner": "renewals-team@example.com",
  "status": "analyzing",
  "current_revision_id": "1c9d3f6a-77e2-4a10-8f3b-2d6c9a4e5b71",
  "current_revision_number": 1,
  "inputs_hash": "b3c1e4d2f09a7c58"
}
```

Save `case_id` as `$CASE_ID`. If the pack input fails validation the API returns `422` with a `code` of `invalid_framing`.

{% hint style="info" %}
Re-framing a decision (`PUT /v1/decision-cases/$CASE_ID`) creates a **new** immutable revision when the change is material and invalidates any prior approvals — a plan approved against the old inputs can never be executed against new ones.
{% endhint %}
{% endstep %}

{% step %}
### Run the analysis

`POST /v1/decision-cases/{case_id}/analysis-runs` starts a governed run. It returns **`202 Accepted`** rather than the result, because an analysis can exceed a normal request timeout — the contract is asynchronous so heavier packs can move to a worker without changing your client.

The optional `retention_mode` controls what evidence is kept: `exploratory` (the default) retains references and hashes only; `governed` retains the exact inputs for later reproduction.

```bash
curl -sS -X POST "$GATEWAY_URL/v1/decision-cases/$CASE_ID/analysis-runs" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"retention_mode": "exploratory"}'
```

```json
{
  "run_id": "a17f9c3e-4d21-4b8e-9a6c-3f0e12d4c8b5",
  "case_id": "8f2a1c7e-0b44-4d9a-9c31-0e5b2a6f1d20",
  "status": "queued",
  "poll_url": "https://decisions.example.com/v1/analysis-runs/a17f9c3e-4d21-4b8e-9a6c-3f0e12d4c8b5",
  "result_url": "https://decisions.example.com/v1/analysis-runs/a17f9c3e-4d21-4b8e-9a6c-3f0e12d4c8b5/result"
}
```

Save `run_id` as `$RUN_ID`, then poll `poll_url` for the outcome.
{% endstep %}

{% step %}
### Poll the run

`GET /v1/analysis-runs/{run_id}` reports the run's lifecycle: `queued` → `running` → `completed`, or `failed`. Poll until it reads `completed` or `failed`.

```bash
curl -sS "$GATEWAY_URL/v1/analysis-runs/$RUN_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

```json
{
  "run_id": "a17f9c3e-4d21-4b8e-9a6c-3f0e12d4c8b5",
  "case_id": "8f2a1c7e-0b44-4d9a-9c31-0e5b2a6f1d20",
  "revision_id": "1c9d3f6a-77e2-4a10-8f3b-2d6c9a4e5b71",
  "status": "completed",
  "model_version": "renewal_capacity_allocation.outcome_model@v0.1.0",
  "reproducibility_id": "b3c1e4d2-a17f9c3e",
  "started_at": "2026-07-10T17:38:04Z",
  "finished_at": "2026-07-10T17:38:04Z",
  "error": null
}
```

The `reproducibility_id` pairs the inputs hash with the result hash — quote it in any audit. Because this pack is deterministic it usually completes within the request, so your first poll often already reads `completed`; always poll rather than assume, since the same client must work when a pack runs on a worker.
{% endstep %}

{% step %}
### Read the result

`GET /v1/analysis-runs/{run_id}/result` returns the host-independent recommendation: ranked options, the expected outcome, capacity and constraint status, rejected options with reasons, sensitivity thresholds, and the reproducibility id. Numbers are **model-estimated under the stated assumptions**, never guarantees — the `disclaimer` field says so explicitly.

```bash
curl -sS "$GATEWAY_URL/v1/analysis-runs/$RUN_ID/result" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Abbreviated (allocation and scenario lists are trimmed here):

```json
{
  "status": "completed",
  "reproducibility_id": "b3c1e4d2-a17f9c3e",
  "model_version": "renewal_capacity_allocation.outcome_model@v0.1.0",
  "result": {
    "feasible": true,
    "recommended_scenario_id": "recommended",
    "scenarios": [
      {
        "id": "recommended",
        "label": "Recommended — marginal-optimal allocation",
        "feasible": true,
        "rank": 1,
        "total_hours_used": 40.0,
        "capacity_utilization": 1.0,
        "baseline_retained_arr": 593449.22,
        "expected_retained_arr": 736164.37,
        "uplift_arr": 142715.16,
        "allocations": [
          {
            "account_id": "A1",
            "name": "BigCo",
            "hours": 16.0,
            "estimated_expected_retained_arr": 282926.55,
            "uplift_arr": 94202.16,
            "selected": true,
            "reason": "16h → +$94,202 expected retained ARR"
          }
        ]
      },
      {
        "id": "concentrate_top_arr",
        "label": "Concentrate on highest-ARR accounts",
        "feasible": false,
        "rank": null,
        "rejected_reason": "Strategic account 'SmallStrategic' receives 0h < 4h minimum guarantee",
        "expected_retained_arr": 732566.98,
        "uplift_arr": 139117.77
      }
    ],
    "constraints": [
      {"name": "total_capacity", "kind": "hard", "satisfied": true, "detail": "40h used of 40h available", "slack": 0.0},
      {"name": "strategic_min_hours", "kind": "hard", "satisfied": true, "detail": "2 strategic account(s) each guaranteed ≥ 4h", "slack": null}
    ],
    "sensitivity": [
      {
        "parameter": "intervention_effectiveness",
        "base_value": 0.35,
        "threshold_value": null,
        "direction": "below",
        "description": "Stable down to 0.05 — a uniform change scales retained-ARR magnitude, not where hours go."
      }
    ],
    "confidence": "low",
    "data_quality_score": 100,
    "disclaimer": "Model-estimated retained ARR under the stated intervention assumptions. Figures are simulated outcomes, not guaranteed results."
  }
}
```

Read `recommended_scenario_id` to find the chosen option; rejected options carry a `rejected_reason` so you can see *why* an alternative was dropped (here, a hard strategic-minimum constraint).

{% hint style="warning" %}
When the constraints cannot be met, the run still completes but the result is a **no-feasible-solution** answer: `feasible` is `false`, no scenario is recommended, and a `no_feasible_solution` block names the binding constraint and suggested relaxations. The pack never fabricates a recommendation it cannot support.
{% endhint %}
{% endstep %}

{% step %}
### Inspect the evidence

`GET /v1/analysis-runs/{run_id}/evidence` returns what the run accessed and under which retention mode, plus the provenance that keeps facts, customer assumptions, estimated parameters, and simulated outcomes explicitly separate.

```bash
curl -sS "$GATEWAY_URL/v1/analysis-runs/$RUN_ID/evidence" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

```json
{
  "evidence": {
    "retention_mode": "exploratory",
    "sources": {
      "pack_id": "renewal_capacity_allocation",
      "account_count": 3,
      "inputs_hash": "b3c1e4d2f09a7c58",
      "retention_mode": "exploratory"
    },
    "snapshot_ref": null,
    "content_hash": "b3c1e4d2f09a7c58",
    "data_quality_score": 100
  },
  "provenance": {
    "observed_facts": ["3 renewal accounts in scope with validated ARR.", "40h of customer-success capacity available."],
    "customer_assumptions": ["Intervention effectiveness = 0.35 (default_prior, uncalibrated).", "Strategic minimum = 4h (hard)."],
    "estimated_parameters": ["Baseline renewal probabilities derived from account health via the outcome-model curve."],
    "simulated_outcomes": ["Expected retained ARR under the recommendation: $736,164 (+$142,715 vs baseline)."]
  },
  "reproducibility_id": "b3c1e4d2-a17f9c3e"
}
```

In `exploratory` mode `snapshot_ref` is `null` — only references and hashes are kept. Run with `governed` retention when you need the exact inputs retained for reproduction; the evidence then carries a `snapshot_ref` to that revision.
{% endstep %}

{% step %}
### Propose a plan

`POST /v1/analysis-runs/{run_id}/action-plans` turns the recommendation into a safe, concrete execution plan and returns a **plan hash** plus a **single-use approval nonce**. The plan hash binds the exact actions to the run and revision; the nonce is the one-time challenge the approver must present.

```bash
curl -sS -X POST "$GATEWAY_URL/v1/analysis-runs/$RUN_ID/action-plans" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

```json
{
  "plan_id": "6d4b0a2f-1e88-49c3-b0a7-5c2f9e13d4a6",
  "case_id": "8f2a1c7e-0b44-4d9a-9c31-0e5b2a6f1d20",
  "run_id": "a17f9c3e-4d21-4b8e-9a6c-3f0e12d4c8b5",
  "lifecycle_state": "proposed",
  "plan_hash": "9f86d081884c7d659a2feaa0c55ad015",
  "nonce": "3b1f7c9d2e5a8046",
  "actions": {
    "actions": [
      {"type": "export_allocation_table", "title": "Recommended allocation"},
      {"type": "create_task_list", "title": "Customer-success intervention tasks"},
      {"type": "draft_approval_memo", "title": "Decision memo"}
    ]
  }
}
```

Save `plan_id`, `plan_hash`, and `nonce` as `$PLAN_ID`, `$PLAN_HASH`, and `$NONCE`. Proposing a plan requires a completed, **feasible** run — proposing against a no-feasible-solution result returns `409` with `code: no_feasible_solution`.
{% endstep %}

{% step %}
### Approve the plan

`POST /v1/decision-plans/{plan_id}/approve` is a **separate, credentialed call** — deliberately not an automated agent tool. It must carry the exact `plan_hash` and the single-use `nonce`, and the caller's token must hold an **approver role** (admin-or-owner). An optional `idempotency_key` makes a retried approval safe.

```bash
curl -sS -X POST "$GATEWAY_URL/v1/decision-plans/$PLAN_ID/approve" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan_hash": "'"$PLAN_HASH"'",
    "nonce": "'"$NONCE"'",
    "idempotency_key": "approve-2026-07-10-001"
  }'
```

```json
{
  "approval_id": "c02e7b41-9a63-4f0d-8e12-7b5a9d3c6f84",
  "case_id": "8f2a1c7e-0b44-4d9a-9c31-0e5b2a6f1d20",
  "plan_id": "6d4b0a2f-1e88-49c3-b0a7-5c2f9e13d4a6",
  "status": "approved",
  "approver_principal": "user:renewals-lead@example.com",
  "decided_at": "2026-07-10T17:40:12Z"
}
```

{% hint style="warning" %}
Approving is **not** executing. This call only records that a named principal endorsed this exact plan. The nonce is consumed on first use, the challenge expires, and a mismatched `plan_hash` or a below-role token is rejected (`403`) — a leaked propose-response cannot be approved later or by an unauthorized caller. If the decision was re-framed after the plan was proposed, approval fails with `stale_plan`; re-propose against the current revision.
{% endhint %}
{% endstep %}

{% step %}
### Execute the approved plan

`POST /v1/decision-plans/{plan_id}/execute` carries out an **approved** plan and returns a receipt. Execution also requires the approver role, and the plan's revision must still be the case's current revision.

```bash
curl -sS -X POST "$GATEWAY_URL/v1/decision-plans/$PLAN_ID/execute" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

```json
{
  "plan_id": "6d4b0a2f-1e88-49c3-b0a7-5c2f9e13d4a6",
  "case_id": "8f2a1c7e-0b44-4d9a-9c31-0e5b2a6f1d20",
  "run_id": "a17f9c3e-4d21-4b8e-9a6c-3f0e12d4c8b5",
  "lifecycle_state": "executed",
  "plan_hash": "9f86d081884c7d659a2feaa0c55ad015",
  "nonce": null,
  "actions": {"actions": [{"type": "export_allocation_table"}, {"type": "create_task_list"}, {"type": "draft_approval_memo"}]},
  "receipt": {
    "executed_at": "2026-07-10T17:41:03Z",
    "prepared_artifacts": ["export_allocation_table", "create_task_list", "draft_approval_memo"],
    "action_count": 3
  }
}
```

The `nonce` is never re-exposed after propose time. Execution is idempotent under concurrency — exactly one call transitions the plan to `executed`; a duplicate returns `409`.
{% endstep %}

{% step %}
### Record the outcome

`POST /v1/decision-cases/{case_id}/outcomes` closes the loop: report what actually happened so the pack's estimates can be calibrated against reality. Reference the `run_id` you acted on and the service computes the delta from the recommendation.

```bash
curl -sS -X POST "$GATEWAY_URL/v1/decision-cases/$CASE_ID/outcomes" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "'"$RUN_ID"'",
    "actual_metrics": {"retained_arr": 700000},
    "notes": "Two strategic renewals closed; one standard account churned mid-quarter."
  }'
```

```json
{
  "outcome_id": "e91a5d70-3c62-4b18-9f4a-6d2c0b7e1a83",
  "case_id": "8f2a1c7e-0b44-4d9a-9c31-0e5b2a6f1d20",
  "run_id": "a17f9c3e-4d21-4b8e-9a6c-3f0e12d4c8b5",
  "actual_metrics": {"retained_arr": 700000},
  "delta": {"retained_arr": -36164.37},
  "recorded_at": "2026-07-20T09:00:00Z"
}
```

The `delta` (actual minus the recommendation's model-estimated `expected_retained_arr`) is what feeds calibration — over time it moves the pack's assumptions from `uncalibrated` priors toward calibrated estimates.
{% endstep %}
{% endstepper %}

## Expected result

By the end of the walkthrough you have driven one decision through its full governed lifecycle:

* A **case** at revision 1 with a hashed, immutable framing.
* A **completed** analysis run carrying a `reproducibility_id` and a host-independent recommendation — a ranked, feasible allocation of 40 hours whose model-estimated expected retained ARR is about **$736K (+$142K vs baseline)**, with the higher-ARR alternative correctly rejected for breaching the strategic-minimum constraint.
* An **evidence** record that separates observed facts from assumptions, estimates, and simulated outcomes.
* A plan that went `proposed` → `approved` → `executed` — approval a distinct, role-gated, nonce-bound act — with an execution **receipt**.
* A recorded **outcome** whose delta (here, about **−$36K** versus the estimate) feeds the next run's calibration.

Every figure is model-estimated under the assumptions you framed, not a guaranteed result, and every step is traceable to the revision and reproducibility id it came from.

## Next steps

* [Renewal Capacity Allocation pack](renewal-capacity-allocation.md) — the objective, levers, constraints, and assumptions behind the numbers in this walkthrough.
* [The governed decision lifecycle](../concepts/decision-service.md) — why framing, evidence, approval, and calibration are separate, auditable stages.
* [Run decisions from Excel](../integrations/microsoft/excel.md) — drive these same calls from a spreadsheet instead of `curl`.