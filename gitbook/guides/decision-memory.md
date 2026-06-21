---
icon: clock-rotate-left
description: Log a decision through the engine, record its real-world outcome later, and review the closed loop so the engine learns which decision types are over or under confident.
---

# Log decisions and record outcomes

By the end of this guide you will have logged a decision to decision memory, recorded the real number once you knew it, and read back the engine-computed `outcome_delta` that closes the loop. You need an Algenta API key (see [Authentication](../authentication.md)) exported as `$ALGENTA_API_KEY`, and either `curl`, the `de` CLI, or the Python SDK (`pip install algenta-sdk`). The loop is `log -> outcome -> review`; only the first step is required, and the outcome can be recorded minutes or weeks later.

{% stepper %}
{% step %}
### Log the decision

Send the action you chose to `POST /v1/decisions`. Only `chosen_action` is required; logging `expected_value` is what makes the engine able to compute a delta later, and an optional `run_id` binds the record to the simulation that produced it. The call returns `201 Created` with the new decision `id` — capture it.

{% tabs %}
{% tab title="HTTP" %}
```bash title="POST /v1/decisions"
DECISION_ID=$(curl -s -X POST https://api.algenta.ai/v1/decisions \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "context": "Q3 pricing change for the Pro tier",
        "chosen_action": "raise_price_10pct",
        "options_considered": ["hold", "raise_price_10pct", "raise_price_20pct"],
        "expected_value": 142000,
        "confidence": 0.78,
        "risk_p5": -8000,
        "risk_p95": 210000,
        "risk_pol": 0.12
      }' | jq -r .id)
echo "$DECISION_ID"
```
{% endtab %}

{% tab title="CLI" %}
```bash title="de decisions log"
# Put the request body in a JSON file, then log it.
de decisions log decision.json
```
{% endtab %}

{% tab title="Python" %}
```python title="log_decision.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

decision = client.log_decision(
    {
        "context": "Q3 pricing change for the Pro tier",
        "chosen_action": "raise_price_10pct",
        "options_considered": ["hold", "raise_price_10pct", "raise_price_20pct"],
        "expected_value": 142000,
        "confidence": 0.78,
        "risk_p5": -8000,
        "risk_p95": 210000,
        "risk_pol": 0.12,
    }
)
print(decision.id)
```
{% endtab %}
{% endtabs %}

Verify by confirming the response carried a non-empty `id` and a `created_at` timestamp. The record also pins `policy_snapshot_id`, `schema_snapshot_id`, and `manifest_version`, which is what makes the decision auditable later.
{% endstep %}

{% step %}
### Record the actual outcome

Once the real number is known, close the loop with `PATCH /v1/decisions/{id}/outcome`. The body requires `actual_outcome` (a float) and accepts optional `outcome_notes`. The engine sets `outcome_recorded_at` and computes `outcome_delta = actual_outcome - expected_value` whenever an `expected_value` was logged. This call also refreshes your org's confidence calibration.

{% tabs %}
{% tab title="HTTP" %}
```bash title="PATCH /v1/decisions/{id}/outcome"
curl -s -X PATCH "https://api.algenta.ai/v1/decisions/$DECISION_ID/outcome" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"actual_outcome": 131500, "outcome_notes": "Lower conversion than modeled."}'
```
{% endtab %}

{% tab title="CLI" %}
```bash title="de decisions outcome"
# outcome.json holds {"actual_outcome": 131500, "outcome_notes": "..."}
de decisions outcome "$DECISION_ID" outcome.json
```
{% endtab %}

{% tab title="Python" %}
```python title="record_outcome.py"
updated = client.record_outcome(
    decision.id,
    actual_outcome=131500,
    outcome_notes="Lower conversion than modeled.",
)
print(updated.outcome_delta)  # -10500
```
{% endtab %}
{% endtabs %}

Verify by checking the `200 OK` response carries `outcome_delta` (here `131500 - 142000 = -10500`) and a populated `outcome_recorded_at`. A negative delta means the result came in worse than the engine expected.
{% endstep %}

{% step %}
### Review the closed loop

Re-read the persisted record to confirm the loop is closed, and list decisions to compare expected against actual across the org. `GET /v1/decisions/{id}` returns the single record; `GET /v1/decisions?with_outcome_only=true` returns only decisions that already have a recorded outcome, most recent first.

{% tabs %}
{% tab title="HTTP" %}
```bash title="GET a record and list with outcomes"
# Re-read the single decision
curl -s "https://api.algenta.ai/v1/decisions/$DECISION_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" | jq '{id, expected_value, actual_outcome, outcome_delta}'

# List only decisions that have an outcome recorded
curl -s "https://api.algenta.ai/v1/decisions?with_outcome_only=true&limit=20" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" | jq '.total'
```
{% endtab %}

{% tab title="CLI" %}
```bash title="de decisions get / list"
de decisions get "$DECISION_ID"
de decisions list --with-outcome-only --limit 20
```
{% endtab %}

{% tab title="Python" %}
```python title="review.py"
record = client.get_decision(decision.id)
print(record.expected_value, record.actual_outcome, record.outcome_delta)

reviewed = client.list_decisions(with_outcome_only=True, limit=20)
print(reviewed.total)
```
{% endtab %}
{% endtabs %}

Verify by confirming the single record shows your `actual_outcome` and `outcome_delta`, and that the filtered list `total` includes the decision you just closed.
{% endstep %}
{% endstepper %}

## Expected result

You logged one decision (HTTP `201`), recorded its outcome (HTTP `200`), and read back a closed-loop record. The single decision now carries `expected_value: 142000`, `actual_outcome: 131500`, and an engine-computed `outcome_delta: -10500`, alongside `outcome_recorded_at` and the integrity snapshot fields.

```json title="Closed-loop record (abridged)"
{
  "id": "…",
  "chosen_action": "raise_price_10pct",
  "expected_value": 142000,
  "actual_outcome": 131500,
  "outcome_delta": -10500,
  "outcome_recorded_at": "2026-06-21T13:30:00Z",
  "policy_snapshot_id": "…",
  "schema_snapshot_id": "…",
  "manifest_version": "…"
}
```

## Troubleshooting

{% hint style="warning" %}
**`outcome_delta` is `null` after recording an outcome.** The delta is only computed when an `expected_value` was present on the original log. Log the decision with `expected_value`, or read the raw `actual_outcome` instead.
{% endhint %}

{% hint style="info" %}
**`404 Decision not found` on the PATCH or GET.** Decision memory is scoped to your org and workspace. Confirm the `id` came from a `POST /v1/decisions` made with the same API key, and that the record was not soft-deleted with `DELETE /v1/decisions/{id}`. See [API errors](../api/errors.md).
{% endhint %}

## Next

{% content-ref url="../concepts/decision-memory.md" %}
[decision-memory.md](../concepts/decision-memory.md)
{% endcontent-ref %}

{% content-ref url="../api/reference.md" %}
[reference.md](../api/reference.md)
{% endcontent-ref %}
