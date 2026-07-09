---
icon: code-pull-request
description: Turn a triage evidence bundle into a verified code fix — generate a decision plan, simulate its risk gate, and apply it as a patch, a local branch, or a pull request.
---

# Fix a repository

Triage tells you where a problem lives. This guide takes the next step: it turns a triage evidence bundle into a concrete, risk-checked code change and lands it. The engine generates a candidate patch (a **decision plan**), runs a deterministic **simulation** that scores the patch against your calibrated apply gate, and only then lets you **apply** it — as a raw patch, a local branch, or a remote pull request.

The fix pipeline is a strict chain. Each stage consumes the previous stage's id:

`snapshot → triage → decision plan → simulate → apply`

You already produced the `snapshot` and `triage` stages in [Triage a repository](repository-intelligence.md). This guide starts from the evidence bundle they returned. All routes live under `/v1/repositories` and require `Authorization: Bearer $ALGENTA_API_KEY`.

{% hint style="info" %}
`apply` performs an external write (it can push a branch or open a PR), so it is deliberately not part of the read-only agent-callback set. It rejects service keys and requires an interactive key with `write_permission: true` for any mode that writes.
{% endhint %}

## Before you start

You need three things from the triage flow:

- `$REPOSITORY_ID` — the connector id for the repository (see [Connect data](connect-data.md)).
- `$SNAPSHOT_ID` — an immutable snapshot of the ref you are fixing.
- `$BUNDLE_REF` — the `workspace_evidence_bundle_ref` returned by [triage](repository-intelligence.md). It anchors the fix to a bounded slice of the repository.

Export the first two so the commands below run unchanged:

```bash title="env.sh"
export ALGENTA_API_KEY="de_live_..."
export REPOSITORY_ID="$REPOSITORY_ID"
export SNAPSHOT_ID="$SNAPSHOT_ID"
export BUNDLE_REF="$BUNDLE_REF"
```

## Generate and verify a fix

{% stepper %}
{% step %}
### Generate the fix (decision plan)

A decision plan is one immutable, stored fix revision. The engine reads the evidence bundle, drafts a change with the planner, validates the unified diff against the snapshot, and stores it. The response hands you both the `decision_plan_id` and the validated `patch_diff` inline.

`POST /v1/repositories/{repository_id}/decision-plans`

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "https://api.algenta.ai/v1/repositories/$REPOSITORY_ID/decision-plans" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_evidence_bundle_ref": "'"$BUNDLE_REF"'",
    "snapshot_id": "'"$SNAPSHOT_ID"'"
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="decision_plan.py"
import os
import httpx

repo_id = os.environ["REPOSITORY_ID"]
resp = httpx.post(
    f"https://api.algenta.ai/v1/repositories/{repo_id}/decision-plans",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "workspace_evidence_bundle_ref": os.environ["BUNDLE_REF"],
        "snapshot_id": os.environ["SNAPSHOT_ID"],
    },
    timeout=120.0,
)
plan = resp.json()
print(plan["decision_plan_id"])
print(plan["patch_diff"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="decision_plan.ts"
const repoId = process.env.REPOSITORY_ID!;
const resp = await fetch(
  `https://api.algenta.ai/v1/repositories/${repoId}/decision-plans`,
  {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      workspace_evidence_bundle_ref: process.env.BUNDLE_REF,
      snapshot_id: process.env.SNAPSHOT_ID,
    }),
  },
);
const plan = await resp.json();
console.log(plan.decision_plan_id, plan.patch_diff);
```
{% endtab %}
{% endtabs %}

The `200` `RepositoryDecisionPlanResponse` carries `decision_plan_id`, the `decision_plan` object, the validated `patch_diff`, and `planner_usage`. Save the id as `$DECISION_PLAN_ID`. Optional fields: pass `model` to pin the planner model, or add `?async_execution=true` to run the planner off the request path and get a `202` poll handle (see [Run asynchronous jobs](async-jobs.md)).
{% endstep %}

{% step %}
### Simulate the risk gate

Simulation is deterministic and runs on the Mojo engine — no LLM. It measures the patch's blast radius against the snapshot's dependency graph, runs the scenario set, and scores the result against your org's calibrated apply gate. The verdict lands in `recommended_action` (`apply_patch` or `hold_patch`).

`POST /v1/repositories/{repository_id}/simulate`

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "https://api.algenta.ai/v1/repositories/$REPOSITORY_ID/simulate" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "decision_plan_id": "'"$DECISION_PLAN_ID"'",
    "snapshot_id": "'"$SNAPSHOT_ID"'",
    "seed": 42
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="simulate.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

envelope = client.simulate_repository(
    os.environ["REPOSITORY_ID"],
    {
        "decision_plan_id": os.environ["DECISION_PLAN_ID"],
        "snapshot_id": os.environ["SNAPSHOT_ID"],
        "seed": 42,
    },
)
print(envelope.recommended_action)
simulation_id = envelope.validated_inputs["simulation_id"]
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="simulate.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY,
  baseUrl: "https://api.algenta.ai",
});

const envelope = await client.simulateRepository(process.env.REPOSITORY_ID!, {
  decision_plan_id: process.env.DECISION_PLAN_ID,
  snapshot_id: process.env.SNAPSHOT_ID,
  seed: 42,
});
console.log(envelope.recommended_action);
const simulationId = envelope.validated_inputs.simulation_id;
```
{% endtab %}
{% endtabs %}

The `200` response is a `DecisionEnvelope`. The two fields that gate `apply`:

```json title="simulate-response.json"
{
  "recommended_action": "apply_patch",
  "confidence": 0.91,
  "score_breakdown": {
    "apply_gate": { "passed": true, "min_confidence": 0.7, "risk_floor": null, "var_95": 0.0 }
  },
  "validated_inputs": {
    "simulation_id": "simulation_1a2b3c...",
    "decision_plan_id": "decision_plan_9f8e...",
    "snapshot_id": "snap_..."
  }
}
```

The `simulation_id` you pass to `apply` lives at `validated_inputs.simulation_id` — grab it now and export it as `$SIMULATION_ID`. `runs` defaults to a complexity-adaptive scenario count; pass an explicit integer (100–250000) to pin it, and keep `seed` fixed for a reproducible gate.
{% endstep %}

{% step %}
### Apply the fix

`apply` re-loads the stored decision plan and simulation, confirms they pin the same snapshot, and then acts according to `mode`. The three modes trade off how much the engine touches your repository.

`POST /v1/repositories/{repository_id}/apply`

{% tabs %}
{% tab title="Patch only" %}
Returns the unified diff and never writes. No `write_permission` and no passing gate required — use it to inspect or apply the change yourself.

```bash
curl -sS -X POST "https://api.algenta.ai/v1/repositories/$REPOSITORY_ID/apply" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "decision_plan_id": "'"$DECISION_PLAN_ID"'",
    "simulation_id": "'"$SIMULATION_ID"'",
    "mode": "patch_only"
  }'
```
{% endtab %}

{% tab title="Local branch" %}
Checks the code out, applies the patch, and commits it to a new branch. Requires `write_permission: true` and a passing apply gate.

```bash
curl -sS -X POST "https://api.algenta.ai/v1/repositories/$REPOSITORY_ID/apply" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "decision_plan_id": "'"$DECISION_PLAN_ID"'",
    "simulation_id": "'"$SIMULATION_ID"'",
    "mode": "local_branch",
    "write_permission": true,
    "branch_name": "algenta/fix-refund-retry",
    "commit_message": "Fix double-charge on refund retry"
  }'
```
{% endtab %}

{% tab title="Remote PR" %}
Pushes the branch to the connector's remote and opens a pull request. Requires `write_permission: true`, a passing apply gate, and a connector that supports remote PRs.

```bash
curl -sS -X POST "https://api.algenta.ai/v1/repositories/$REPOSITORY_ID/apply" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "decision_plan_id": "'"$DECISION_PLAN_ID"'",
    "simulation_id": "'"$SIMULATION_ID"'",
    "mode": "remote_pr",
    "write_permission": true,
    "base_branch": "main",
    "pull_request_title": "Fix double-charge on refund retry",
    "pull_request_body": "Generated and risk-checked by Algenta."
  }'
```
{% endtab %}
{% endtabs %}

The same call in code, opening a pull request:

{% tabs %}
{% tab title="Python" %}
```python title="apply.py"
applied = client.apply_repository(
    os.environ["REPOSITORY_ID"],
    {
        "decision_plan_id": os.environ["DECISION_PLAN_ID"],
        "simulation_id": simulation_id,
        "mode": "remote_pr",
        "write_permission": True,
        "pull_request_title": "Fix double-charge on refund retry",
    },
)
print(applied.applied, applied.pull_request_url)
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="apply.ts"
const applied = await client.applyRepository(process.env.REPOSITORY_ID!, {
  decision_plan_id: process.env.DECISION_PLAN_ID,
  simulation_id: simulationId,
  mode: "remote_pr",
  write_permission: true,
  pull_request_title: "Fix double-charge on refund retry",
});
console.log(applied.applied, applied.pull_request_url);
```
{% endtab %}
{% endtabs %}
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — `apply` returns a `RepositoryApplyResponse`. For a write mode, `applied` is `true` and you get `branch_name`, `commit_sha`, and (for `remote_pr`) a `pull_request_url`. Every response carries the `patch`, the `apply_gate`, and a `validation_summary` listing the changed files.
{% endhint %}

{% hint style="warning" %}
A write mode fails closed. If the simulation gate did not pass you get `409 repository_apply_gate_failed`; if you omit `write_permission: true` you get `409 repository_write_permission_required`. Re-run the simulation or switch to `patch_only` to inspect the diff.
{% endhint %}

## Verify an in-flight patch

If you already hold a working-tree patch — for example, an edit made mid-run by an agent — you can score it directly without creating a stored decision plan. `simulate-patch` runs the same calibrated risk gate against the snapshot and returns the `apply_patch` / `hold_patch` verdict. It is verify-only: it does not produce a `simulation_id` that `apply` can consume.

`POST /v1/repositories/{repository_id}/simulate-patch`

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "https://api.algenta.ai/v1/repositories/$REPOSITORY_ID/simulate-patch" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_id": "'"$SNAPSHOT_ID"'",
    "patch_diff": "diff --git a/src/payments/refund.py b/src/payments/refund.py\n...",
    "confidence": 0.6
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="simulate_patch.py"
import os
import httpx

repo_id = os.environ["REPOSITORY_ID"]
resp = httpx.post(
    f"https://api.algenta.ai/v1/repositories/{repo_id}/simulate-patch",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "snapshot_id": os.environ["SNAPSHOT_ID"],
        "patch_diff": open("fix.diff").read(),
        "confidence": 0.6,
    },
    timeout=120.0,
)
print(resp.json()["recommended_action"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="simulate_patch.ts"
import { readFileSync } from "node:fs";

const repoId = process.env.REPOSITORY_ID!;
const resp = await fetch(
  `https://api.algenta.ai/v1/repositories/${repoId}/simulate-patch`,
  {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      snapshot_id: process.env.SNAPSHOT_ID,
      patch_diff: readFileSync("fix.diff", "utf8"),
      confidence: 0.6,
    }),
  },
);
console.log((await resp.json()).recommended_action);
```
{% endtab %}
{% endtabs %}

{% hint style="success" %}
**Expected result** — a `DecisionEnvelope` whose `recommended_action` is `apply_patch` (the patch cleared the gate) or `hold_patch` (it did not). To land the change, promote it through the stored decision-plan → simulate → apply path above.
{% endhint %}

## Run the whole fix in one call

The `pipeline` endpoint runs `snapshot → triage → plan → simulate` in a single request, reusing cross-stage artifacts. Supply `signals` the same way you would for triage, and use `stop_after` to halt early — `triage` (before the planner) or `plan` (before simulation).

`POST /v1/repositories/{repository_id}/pipeline`

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "https://api.algenta.ai/v1/repositories/$REPOSITORY_ID/pipeline" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_id": "'"$SNAPSHOT_ID"'",
    "signals": {
      "issue_text": "Refund webhook double-charges on retry",
      "failing_tests": ["tests/test_refunds.py::test_idempotent_retry"]
    },
    "stop_after": "simulate",
    "seed": 42
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="pipeline.py"
import os
import httpx

repo_id = os.environ["REPOSITORY_ID"]
resp = httpx.post(
    f"https://api.algenta.ai/v1/repositories/{repo_id}/pipeline",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "snapshot_id": os.environ["SNAPSHOT_ID"],
        "signals": {"issue_text": "Refund webhook double-charges on retry"},
        "stop_after": "simulate",
        "seed": 42,
    },
    timeout=300.0,
)
result = resp.json()
plan_id = result["decision_plan"]["decision_plan_id"]
sim_id = result["simulation"]["validated_inputs"]["simulation_id"]
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="pipeline.ts"
const repoId = process.env.REPOSITORY_ID!;
const resp = await fetch(
  `https://api.algenta.ai/v1/repositories/${repoId}/pipeline`,
  {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      snapshot_id: process.env.SNAPSHOT_ID,
      signals: { issue_text: "Refund webhook double-charges on retry" },
      stop_after: "simulate",
      seed: 42,
    }),
  },
);
const result = await resp.json();
const planId = result.decision_plan.decision_plan_id;
const simId = result.simulation.validated_inputs.simulation_id;
```
{% endtab %}
{% endtabs %}

The `200` `RepositoryPipelineResponse` nests each stage (`snapshot`, `triage`, `decision_plan`, `simulation`) plus `stage_timings` and `completed_stage`. Read `decision_plan.decision_plan_id` and `simulation.validated_inputs.simulation_id` from it and pass them straight to `apply`. For a heavy pipeline, add `?async_execution=true` to get a `202` poll handle instead of an inline result.

{% hint style="success" %}
**Expected result** — one response containing every stage. When `stop_after` is `simulate`, `completed_stage` is `simulate` and `simulation.recommended_action` tells you whether the fix is ready to apply.
{% endhint %}

## Automate fixes with the GitHub App

Install the Algenta GitHub App to have the engine open fix pull requests on its own, driven by events in your repository.

{% stepper %}
{% step %}
### Start the install

Open the install endpoint in a browser while signed in with an owner or admin key. It redirects you to GitHub to choose which repositories the app can access. Only an org owner or admin can connect GitHub.

`GET /github/app/install/start`
{% endstep %}

{% step %}
### Approve on GitHub

Pick the repositories and approve. GitHub returns you to the app's callback (`/github/app/install/callback`), which verifies that you administer the installation before binding it to your org.
{% endstep %}

{% step %}
### Confirm the connection

You land on a short success page confirming the installation is connected. There is nothing else to configure.
{% endstep %}
{% endstepper %}

Once installed, GitHub delivers events to the app's inbound receiver, `POST /webhooks/github`. The receiver verifies GitHub's HMAC signature, dedupes the delivery, and returns `202` within seconds; the multi-step fix runs asynchronously in the background. Three events start a fix:

- **A labeled issue** — add the `codna-fix` label to a GitHub issue.
- **A failing CI check** — a completed `check_suite` whose conclusion is `failure`, `timed_out`, `startup_failure`, or `action_required`.
- **A submitted pull-request review** — a review left on an open PR.

{% hint style="success" %}
**Expected result** — after the install completes, labeling an issue `codna-fix` (or a CI check failing) opens a fix pull request in that repository without any further API calls.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Prove a security fix</strong></td><td>Re-prove that your patch closes a scanner finding.</td><td><a href="security-analysis.md">security-analysis.md</a></td></tr>
<tr><td><strong>Triage the next issue</strong></td><td>Build the evidence bundle this guide starts from.</td><td><a href="repository-intelligence.md">repository-intelligence.md</a></td></tr>
<tr><td><strong>Poll async jobs</strong></td><td>Handle the 202 handle from async pipeline runs.</td><td><a href="async-jobs.md">async-jobs.md</a></td></tr>
</tbody></table>
