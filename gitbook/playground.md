---
icon: flask
description: Try the Algenta engine with a single POST /v1/playground call — no sign-up and no API key. Run a decision, optimization, simulation, or forecast in one request.
---

# Try Algenta without an API key

The fastest way to feel what Algenta does is the **playground**: one HTTP call, no account, no key. `POST /v1/playground` runs a decision analysis, optimization, simulation, or forecast against the engine and returns a recommended action, a value, a confidence, and a plain-language "why". It is rate limited to **10 requests per minute per IP** — enough to explore, not to build on. When you are ready for real work, mint a key ([Authentication & API keys](authentication.md)) and move to `/v1/simulate` and the rest of the API.

## Before you start

Nothing to install and nothing to authenticate. You only need a base URL:

- **Hosted:** `https://api.algenta.ai`
- **Self-hosted:** `http://localhost:8000`

## Make your first playground call

{% stepper %}
{% step %}
### Ask a decision question

Send a `decision` request — "given these inputs, what should I do?". No statistics knowledge required.

{% tabs %}
{% tab title="cURL" %}
```bash title="playground-decision.sh"
curl -sS -X POST https://api.algenta.ai/v1/playground \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "decision",
    "inputs": { "revenue": 120000, "cost": 70000 },
    "runs": 1000
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="playground_decision.py"
import httpx

resp = httpx.post(
    "https://api.algenta.ai/v1/playground",
    json={"mode": "decision", "inputs": {"revenue": 120000, "cost": 70000}, "runs": 1000},
)
print(resp.json())
```
{% endtab %}
{% endtabs %}
{% endstep %}

{% step %}
### Read the response

The engine returns a compact result you can act on directly:

```json title="playground-response.json"
{
  "playground_id": "b8f1c0de-1234-4abc-9def-0123456789ab",
  "mode": "decision",
  "action": "proceed",
  "value": 50000.0,
  "confidence": 0.87,
  "why": [
    "Expected net value is positive across the modeled range.",
    "Downside stays bounded at the 5th percentile."
  ],
  "details": { "scenarios_evaluated": 1000 },
  "latency_ms": 4.2,
  "upgrade_hint": "Playground cap: 1,000 scenarios. Upgrade for 1,000,000+."
}
```
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — a `200` response whose `action` is one of `proceed` / `pause` / `reject` (for `decision`), with a `value`, a `confidence` between 0 and 1, a `why` list, and a sub-5ms `latency_ms`. No key was required.
{% endhint %}

## The four modes

`mode` selects what the engine runs. All modes take `inputs` as `name → value` (or `name → {value, low, high}` for a range).

| `mode` | Question it answers | Key inputs |
| --- | --- | --- |
| `decision` | What should I do? | `inputs` (values or ranges) |
| `optimize` | What is the best configuration? | `inputs` as `[min, max]` or `{min, max}` ranges, plus `objective` |
| `simulate` | What is the range of outcomes? | `inputs` |
| `forecast` | What happens next? | `history` (a numeric series, most recent last, at least 3 values) |

{% tabs %}
{% tab title="optimize" %}
```bash title="playground-optimize.sh"
curl -sS -X POST https://api.algenta.ai/v1/playground \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "optimize",
    "objective": "maximize profit",
    "inputs": { "price": [10, 200], "quantity": [100, 5000] },
    "runs": 1000
  }'
```
{% endtab %}

{% tab title="simulate" %}
```bash title="playground-simulate.sh"
curl -sS -X POST https://api.algenta.ai/v1/playground \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "simulate",
    "inputs": { "revenue": 120000, "cost": 70000 },
    "runs": 5000
  }'
```
{% endtab %}

{% tab title="forecast" %}
```bash title="playground-forecast.sh"
curl -sS -X POST https://api.algenta.ai/v1/playground \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "forecast",
    "history": [80000, 85000, 90000, 95000, 100000]
  }'
```
{% endtab %}
{% endtabs %}

## Request fields

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `mode` | string | `decision` | One of `decision`, `optimize`, `simulate`, `forecast`. |
| `inputs` | object | `{}` | Your variables as `name → value` or `name → {value, low, high}`. |
| `objective` | string | `maximize_value` | Used by `optimize`, e.g. `maximize profit`, `minimize cost`. |
| `runs` | integer | `1000` | Scenarios to evaluate. Range `100`–`5000` (playground cap). |
| `history` | array of numbers | — | Required for `forecast`; at least 3 values, most recent last. |

{% hint style="warning" %}
The playground caps `runs` at 5,000 and allows 10 requests per minute per IP. Over the limit returns `429` with `error.code = "playground_rate_limit"`. For 1,000,000+ scenarios per request and no rate cap, get an API key and call `/v1/simulate`.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Run the engine for real</strong></td><td>Install, mint a key, and call /v1/simulate.</td><td><a href="quickstart.md">quickstart.md</a></td></tr>
<tr><td><strong>Get an API key</strong></td><td>Authenticate and lift the playground caps.</td><td><a href="authentication.md">authentication.md</a></td></tr>
<tr><td><strong>See the full API</strong></td><td>Every endpoint, schema, and error shape.</td><td><a href="api/reference.md">api/reference.md</a></td></tr>
</tbody></table>
