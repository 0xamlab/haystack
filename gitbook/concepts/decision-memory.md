---
icon: clock-rotate-left
description: Decision memory is the persisted log of decisions, the real-world outcomes recorded against them, and the review loop that lets the engine learn which decision types are over- or under-confident.
---

# Decision memory

Decision memory is the persisted record of decisions made through the engine, the real-world **outcomes** recorded against them later, and the review loop that closes the gap between the two. Each entry captures what was chosen, what the engine expected, and — once you report it — what actually happened, so accuracy can be measured rather than assumed. It is exposed under `/v1/decisions` and tagged **Decision Memory** in the API.

## Why it exists

A simulation tells you what the engine *expected*; it cannot tell you whether the world agreed. Decision memory is the bridge. By storing the expected value at decision time and the observed value afterward, the engine can compute a per-decision error and, over many decisions, learn which decision types are systematically over- or under-confident. That feedback is the foundation of the self-improving engine: every recorded outcome refreshes the org's confidence calibration. The loop is `log -> outcome -> review`.

It is not a plain audit log. A decision record is a structured, queryable object — `chosen_action`, `options_considered`, `expected_value`, `confidence`, a risk profile (`risk_p5`, `risk_p95`, `risk_pol`), and integrity hashes — that participates in computation. The immutable, append-only audit trail is written separately (`decision.log`, `decision.outcome`, `decision.execute`, `decision.delete` events); decision memory is the *learning* surface, the audit trail is the *forensic* one.

## The outcome lifecycle

A decision record moves through three phases. Only the first is required.

| Phase | Trigger | What gets set |
| --- | --- | --- |
| **Logged** | `POST /v1/decisions` | `chosen_action`, `expected_value`, `confidence`, risk, integrity hashes, `policy_snapshot_id`, `schema_snapshot_id`, `manifest_version`, `created_at` |
| **Outcome recorded** | `PATCH /v1/decisions/{id}/outcome` | `actual_outcome`, `outcome_delta` = `actual_outcome - expected_value`, `outcome_notes`, `outcome_recorded_at` |
| **Executed** (optional) | `POST /v1/decisions/{id}/execute` | `executed_at`, `execution_status`, `execution_webhook_url`, `execution_response_code` |

`outcome_delta` is only computed when an `expected_value` was logged; a negative delta means the result came in worse than predicted.

{% hint style="info" %}
Recording an outcome runs the auto-learning step synchronously: the engine re-reads every outcome for the org (and workspace, if scoped) and refreshes confidence calibration. The next `POST /v1/decisions/plan` you call returns a calibrated confidence, with calibration stats attached once enough outcomes make them reliable.
{% endhint %}

## Example

Log a decision, then close the loop once the real number is known.

```bash title="Log a decision, then record its outcome"
# 1. Log a decision (optionally linked to a simulation run_id)
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

# 2. Weeks later: record what actually happened (closes the loop)
curl -s -X PATCH "https://api.algenta.ai/v1/decisions/$DECISION_ID/outcome" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"actual_outcome": 131500, "outcome_notes": "Lower conversion than modeled."}'
```

The PATCH response includes the computed `outcome_delta` (here `131500 - 142000 = -10500`) and the `outcome_recorded_at` timestamp.

```json title="Outcome response (abridged)"
{
  "id": "…",
  "chosen_action": "raise_price_10pct",
  "expected_value": 142000,
  "actual_outcome": 131500,
  "outcome_delta": -10500,
  "outcome_recorded_at": "2026-06-21T13:30:00Z"
}
```

To review accuracy, list only the decisions that have a recorded outcome with `GET /v1/decisions?with_outcome_only=true`.

## Use this when

* **You want to measure decision accuracy** — store `expected_value` at decision time, report `actual_outcome` later, and read `outcome_delta` per record or in aggregate.
* **You need calibration to improve over time** — recording outcomes is what makes `POST /v1/decisions/plan` return calibrated confidence for your org.
* **You are reviewing which decision types miss** — filter with `with_outcome_only=true` and sort or scan `outcome_delta` to find systematically over- or under-confident actions.
* **You want a tamper-evident link back to compute** — every record carries `request_hash`, `result_hash`, and the `policy_snapshot_id` / `schema_snapshot_id` / `manifest_version` that were in force, plus a `run_id` linking to the originating simulation.
* **You want a logged decision to trigger an external action** — `POST /v1/decisions/{id}/execute` fires the full decision context to a webhook and persists the delivery status, behind per-org confidence and risk-floor gates.

Reach for the immutable audit trail instead when you need a forensic who-did-what record rather than a learning signal — decision memory entries can be soft-deleted (`DELETE /v1/decisions/{id}`) for data hygiene, while audit events cannot.

## Next

{% content-ref url="engine.md" %}
[engine.md](engine.md)
{% endcontent-ref %}

{% content-ref url="../concepts.md" %}
[concepts.md](../concepts.md)
{% endcontent-ref %}
