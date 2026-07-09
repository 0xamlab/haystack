---
icon: shield-halved
description: Read and update the Algenta execution policy — the confidence, risk, calibration, and idempotency gates that guard autonomous decision execution — and inspect calibration.
---

# Configure the execution policy

The **execution policy** is the set of safety gates the engine applies to every `POST /v1/decisions/{id}/execute` call and to trigger-driven `auto_execute`. It decides whether a logged decision is confident enough, safe enough, and calibrated enough to fire. By the end of this guide you will have read your org's current policy, tightened its thresholds, reviewed the versioned snapshots, and inspected the calibration that backs the `require_calibration` gate.

You need an API key (see [Authentication](../authentication.md)) exported as `$ALGENTA_API_KEY`, and a running engine — the hosted API at `https://api.algenta.ai` or a self-hosted server at `http://localhost:8000`.

{% hint style="info" %}
Policy changes take effect immediately for all subsequent executions and are recorded in the audit log. Individual executions can still bypass gates on purpose: `force: true` overrides the idempotency gate, and `override_safety: true` bypasses the confidence and risk gates for one call. See [Drive decisions through the API](decision-memory-api.md).
{% endhint %}

## The four gates

| Field | What it does | Default |
| --- | --- | --- |
| `min_confidence` | Decisions below this confidence (0–1) are blocked. | `0.5` |
| `risk_floor` | Maximum tolerable downside loss (absolute). If `p5 < -risk_floor`, execution is blocked. `null` disables the check. | unset |
| `require_calibration` | When true, `auto_execute` waits until the org has 5+ recorded outcomes. Manual execution is always allowed. | `false` |
| `allow_reexecution` | When true, already-executed decisions can fire again without `force: true`. | `false` |

## Read, update, and inspect the policy

{% stepper %}
{% step %}
### Read the current policy

`GET /v1/execution/policy` returns the org's active policy, including the four gates plus the version fields (`snapshot_id`, `content_hash`, `revision`, `previous_snapshot_id`).

{% tabs %}
{% tab title="cURL" %}
```bash title="GET /v1/execution/policy"
curl -sS "https://api.algenta.ai/v1/execution/policy" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Python" %}
```python title="get_policy.py"
import os, requests

resp = requests.get(
    "https://api.algenta.ai/v1/execution/policy",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
)
policy = resp.json()
print(policy["min_confidence"], policy["risk_floor"], policy["revision"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="getPolicy.ts"
const resp = await fetch("https://api.algenta.ai/v1/execution/policy", {
  headers: { Authorization: `Bearer ${process.env.ALGENTA_API_KEY}` },
});
const policy = await resp.json();
console.log(policy.min_confidence, policy.risk_floor, policy.revision);
```
{% endtab %}
{% endtabs %}
{% endstep %}

{% step %}
### Update the thresholds

`PATCH /v1/execution/policy` is a partial update — only the fields you send change. This example raises the confidence bar and sets a downside floor so any decision whose worst case (`p5`) drops below `-25000` is blocked.

{% tabs %}
{% tab title="cURL" %}
```bash title="PATCH /v1/execution/policy"
curl -sS -X PATCH "https://api.algenta.ai/v1/execution/policy" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "min_confidence": 0.7,
    "risk_floor": 25000,
    "require_calibration": true
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="update_policy.py"
resp = requests.patch(
    "https://api.algenta.ai/v1/execution/policy",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={"min_confidence": 0.7, "risk_floor": 25000, "require_calibration": True},
)
policy = resp.json()
print(policy["revision"], policy["snapshot_id"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="updatePolicy.ts"
const resp = await fetch("https://api.algenta.ai/v1/execution/policy", {
  method: "PATCH",
  headers: {
    Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    min_confidence: 0.7,
    risk_floor: 25000,
    require_calibration: true,
  }),
});
const policy = await resp.json();
console.log(policy.revision, policy.snapshot_id);
```
{% endtab %}
{% endtabs %}

The response is the new policy with an incremented `revision` and a fresh `snapshot_id`; the prior one is preserved as `previous_snapshot_id`. To disable the risk gate again, send `"risk_floor": null`.
{% endstep %}

{% step %}
### Review the snapshot history

`GET /v1/execution/policy/snapshots` returns every persisted policy revision in order, so you can trace who changed what and replay a decision against the policy that was live when it fired.

```bash title="GET /v1/execution/policy/snapshots"
curl -sS "https://api.algenta.ai/v1/execution/policy/snapshots" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The response carries `data[]` (each an execution-policy record with its `snapshot_id` and `revision`) and a `total_snapshots` count.
{% endstep %}

{% step %}
### Check calibration

`GET /v1/calibration` reports how accurate your org's past predictions have been. This is what backs `require_calibration`: the `confidence_multiplier` is applied automatically to every simulation once `n_samples >= 5`.

{% tabs %}
{% tab title="cURL" %}
```bash title="GET /v1/calibration"
curl -sS "https://api.algenta.ai/v1/calibration" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Python" %}
```python title="get_calibration.py"
resp = requests.get(
    "https://api.algenta.ai/v1/calibration",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
)
cal = resp.json()
print(cal["is_reliable"], cal["n_samples"], cal["confidence_multiplier"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="getCalibration.ts"
const resp = await fetch("https://api.algenta.ai/v1/calibration", {
  headers: { Authorization: `Bearer ${process.env.ALGENTA_API_KEY}` },
});
const cal = await resp.json();
console.log(cal.is_reliable, cal.n_samples, cal.confidence_multiplier);
```
{% endtab %}
{% endtabs %}

The response includes `is_reliable`, `n_samples`, `confidence_multiplier`, `direction`, and a plain-English `summary`. Until 5 outcomes are recorded, `is_reliable` is `false` and the numeric metrics (`bias`, `rmse_pct`, `hit_rate`) are `null`. Feed the loop by recording outcomes with `PATCH /v1/decisions/{id}/outcome` — see [Log decisions and record outcomes](decision-memory.md).
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — `GET /v1/execution/policy` reflects your new `min_confidence` and `risk_floor` with a bumped `revision`, the snapshots list shows the prior revision retained, and `GET /v1/calibration` reports the org's current `confidence_multiplier`.
{% endhint %}

## Troubleshooting

{% hint style="warning" %}
**A decision I expect to fire is blocked with `409`.** The execution policy rejected it. Read the `error.gate` on the `execution_blocked_*` response, then either lower the threshold here or pass `override_safety: true` (confidence + risk) or `force: true` (idempotency) on the execute call. See [API errors](../api/errors.md).
{% endhint %}

{% hint style="info" %}
**`confidence_multiplier` stays at 1.0 and `is_reliable` is false.** The org has fewer than 5 recorded outcomes. Calibration only engages once enough decisions have been closed with `PATCH /v1/decisions/{id}/outcome`.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Drive decisions through the API</strong></td><td>Plan, log, execute, and delete decisions — the calls these gates guard.</td><td><a href="decision-memory-api.md">decision-memory-api.md</a></td></tr>
<tr><td><strong>Log decisions and record outcomes</strong></td><td>Feed the calibration loop that powers require_calibration.</td><td><a href="decision-memory.md">decision-memory.md</a></td></tr>
<tr><td><strong>Execution ownership &#38; fail-closed</strong></td><td>How the engine decides who may run a decision, and when it refuses.</td><td><a href="../concepts/execution-ownership.md">../concepts/execution-ownership.md</a></td></tr>
</tbody></table>
