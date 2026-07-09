---
icon: credit-card
description: Algenta plans, usage metering, and limits — what each tier includes, how usage is counted, and how to manage your subscription.
---

# Plans, billing & credits

This page is the commercial surface for the Algenta hosted control plane. It covers the pricing tiers, how an organization subscribes through Stripe, how to inspect plan, usage, and limits, and how the execution credit bucket works for the local runtime. Every command, endpoint, and SDK call below is real. You can copy and run them against a hosted control plane or your own self-hosted deployment.

{% hint style="info" %}
Billing and credit enforcement apply to the **hosted control plane** path. A purely local runtime that never authenticates against a control plane stays outside device-license and credit-bucket enforcement. You opt into hosted enforcement by attaching an API key (`ALGENTA_API_KEY`) and a control-plane `base_url` — see [Local mode and hosted enforcement](#local-mode-and-hosted-enforcement).
{% endhint %}

## Plan tiers

Algenta plans are per-organization. Each tier maps to an enforced set of capabilities and quotas.

| Tier | Monthly simulations | Rate limit | Engines | Notable |
| --- | --- | --- | --- | --- |
| Free | 500 / month | 60 req/min | Core Decision Engine only | No async jobs, no webhooks, community support |
| Developer | 10,000 / month | 300 req/min | All 6 Core engines | Async jobs + webhook callbacks, up to 100,000 Monte Carlo runs per request, email support |
| Pro | 100,000 / month | 1,000 req/min | All 10 Core + Advanced engines | Data connectors, up to 1,000,000 runs per request, priority support + SLA |
| Enterprise | Unlimited | 10,000 req/min | All 12 engines incl. Security & Governance + Hybrid Intelligence | Dedicated deployment, SSO/SAML, audit exports, custom SLA |

Read your organization's live plan and remaining quota any time with `GET /v1/limits` and `GET /v1/usage`. For current plans and how to subscribe, see [algenta.ai](https://algenta.ai). Enterprise is a sales-assisted contract.

{% hint style="info" %}
Usage is metered per billing period and surfaced through `GET /v1/usage` — your subscription plus any compute overage above the monthly simulation quota.
{% endhint %}

## Inspect your account

Start by confirming who you are, what plan you are on, your usage this period, and your hard limits.

{% stepper %}
{% step %}
### Confirm the current account

`GET /v1/me` returns the current user and organization, including the active plan.

{% tabs %}
{% tab title="CLI" %}
```bash
algenta account me
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -s https://api.algenta.ai/v1/me \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Response" %}
```json
{
  "user": { "id": "...", "email": "you@example.com", "role": "owner" },
  "org":  { "id": "...", "name": "Acme", "slug": "acme", "plan": "developer", "status": "active" }
}
```
{% endtab %}
{% endtabs %}
{% endstep %}

{% step %}
### Read usage this billing period

`GET /v1/usage` returns the simulation count, quota, and percent used for the current `YYYY-MM` period, plus managed-LLM spend and storage footprint.

{% tabs %}
{% tab title="CLI" %}
```bash
algenta account usage
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -s https://api.algenta.ai/v1/usage \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Response" %}
```json
{
  "billing_period": "2026-06",
  "simulations_run": 4210,
  "api_calls": 4210,
  "quota_limit": 10000,
  "quota_used_pct": 42.1,
  "managed_llm_spend_usd_month": 0.0,
  "managed_llm_cap_usd_month": 50,
  "storage_bytes_used": 0,
  "storage_gb_limit": 10
}
```
{% endtab %}
{% endtabs %}
{% endstep %}

{% step %}
### Check your plan limits

`GET /v1/limits` returns the enforced caps for your plan.

{% tabs %}
{% tab title="CLI" %}
```bash
algenta account limits
```
{% endtab %}

{% tab title="Response" %}
```json
{
  "plan": "developer",
  "max_simulations_per_month": 10000,
  "max_runs_per_simulation": 100000,
  "max_batch_items": 10,
  "rate_limit_per_minute": 300,
  "async_jobs_enabled": true,
  "webhooks_enabled": true,
  "concurrent_jobs": 5,
  "storage_gb": 10,
  "llm_spend_cap_usd_month": 50
}
```
{% endtab %}
{% endtabs %}
{% endstep %}
{% endstepper %}

{% hint style="success" %}
Add `--format json` to any `account` command for raw output suitable for scripting.
{% endhint %}

## Subscriptions and Stripe

Subscriptions are created and managed through Stripe. The control plane exposes three billing endpoints. Checkout and Portal require the `owner` role.

| Endpoint | Method | Role | Purpose |
| --- | --- | --- | --- |
| `/v1/billing/info` | GET | any member | Current plan + Stripe customer id |
| `/v1/billing/checkout` | POST | owner | Create a Stripe Checkout session to subscribe or upgrade |
| `/v1/billing/portal` | POST | owner | Open the Stripe Customer Portal to manage an existing subscription |

### View current billing state

{% tabs %}
{% tab title="CLI" %}
```bash
algenta billing info
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -s https://api.algenta.ai/v1/billing/info \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Response" %}
```json
{
  "plan": "developer",
  "stripe_customer_id": "cus_...",
  "subscription_status": null,
  "current_period_end": null
}
```
{% endtab %}
{% endtabs %}

### Start a checkout (subscribe or upgrade)

The plan argument must be `developer` or `pro`. The command returns a Stripe Checkout URL; open it to complete payment.

{% tabs %}
{% tab title="CLI" %}
```bash
algenta billing checkout developer
# or
algenta billing checkout pro
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -s -X POST https://api.algenta.ai/v1/billing/checkout \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"plan": "pro"}'
```
{% endtab %}

{% tab title="Response" %}
```json
{ "url": "https://checkout.stripe.com/c/pay/cs_..." }
```
{% endtab %}
{% endtabs %}

{% hint style="warning" %}
An invalid plan returns `400 invalid_plan`. Only `developer` and `pro` are accepted; Enterprise is provisioned through a sales contract, not Checkout.
{% endhint %}

### Manage an existing subscription

Once an org has a Stripe customer (after a first checkout), open the Billing Portal to change card, view invoices, or cancel.

{% tabs %}
{% tab title="CLI" %}
```bash
algenta billing portal
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -s -X POST https://api.algenta.ai/v1/billing/portal \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -d '{}'
```
{% endtab %}

{% tab title="Response" %}
```json
{ "url": "https://billing.stripe.com/p/session/..." }
```
{% endtab %}
{% endtabs %}

{% hint style="warning" %}
If the org has never completed a checkout, this returns `400 no_billing_account` — run a checkout first.
{% endhint %}

{% expandable title="How plan transitions are applied (Stripe webhook)" %}
Plan transitions are applied by a signed Stripe webhook (`POST /v1/billing/webhook`), processed exactly once. On `checkout.session.completed` or `customer.subscription.updated` the org plan is upgraded and its entitlement recomputed. On `customer.subscription.deleted` the org is downgraded to Free and its local-runtime devices are revoked. You do not call the webhook yourself; Stripe does.
{% endexpandable %}

### From the SDK

The SDK exposes the same operations on the client. In Python, `AlgentaClient` is the preferred alias; `DecisionEngineClient` remains for compatibility.

{% tabs %}
{% tab title="Python" %}
```python title="billing_example.py"
from decision_engine import AlgentaClient

# api_key falls back to ALGENTA_API_KEY; base_url to ALGENTA_BASE_URL.
client = AlgentaClient(
    api_key="ak_live_...",
    base_url="https://api.algenta.ai",
)

print(client.get_billing_info())
session = client.create_billing_checkout(plan="pro")
print(session.url)

portal = client.create_billing_portal()
print(portal.url)
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript title="billing_example.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY,
  baseUrl: "https://api.algenta.ai",
});

await client.getBillingInfo();
const session = await client.createBillingCheckout({ plan: "pro" });
console.log(session.url);
```
{% endtab %}
{% endtabs %}

## Credits (execution credit bucket)

The local runtime daemon does not phone home on every execution. Instead it draws from a **credit bucket** issued by the control plane. When the local pool drops below 10%, the daemon calls `POST /v1/credits/refresh` and receives a new batch sized to your plan. This bounds the maximum overage to a single batch.

| Plan | Credit batch size per refresh |
| --- | --- |
| Free | 1,000 |
| Developer | 10,000 |
| Pro | 10,000 |
| Enterprise | 100,000 (unlimited monthly quota) |

A refresh grants `min(batch_size, monthly_remaining)` credits. When the monthly quota is exhausted, the endpoint returns `429 quota_exhausted`.

The daemon issues refreshes automatically. You can also drive a refresh manually for testing or scripted provisioning.

{% tabs %}
{% tab title="CLI" %}
```bash
algenta credits refresh refresh-request.json
```

```json title="refresh-request.json"
{
  "device_id": "dev-7f3c9a21",
  "billing_period": "2026-06",
  "credits_used": 0
}
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -s -X POST https://api.algenta.ai/v1/credits/refresh \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"device_id": "dev-7f3c9a21", "billing_period": "2026-06", "credits_used": 0}'
```
{% endtab %}

{% tab title="Python" %}
```python
result = client.refresh_credits(
    device_id="dev-7f3c9a21",
    billing_period="2026-06",
)
print(result.credits_granted, result.monthly_remaining)
```
{% endtab %}

{% tab title="Response" %}
```json
{
  "credits_granted": 10000,
  "credits_issued_this_month": 10000,
  "monthly_limit": 100000,
  "monthly_remaining": 90000,
  "billing_period": "2026-06",
  "expires_at": 1750531200.0,
  "refresh_after": 1750521600.0,
  "server_time": 1750444800.0
}
```
{% endtab %}
{% endtabs %}

{% expandable title="What a quota-exhausted refresh returns" %}
When the monthly quota is gone, the refresh fails closed with `429 quota_exhausted`:

```json
{
  "error": "quota_exhausted",
  "message": "Monthly execution quota exhausted for plan 'pro' (100,000 executions/mo). Upgrade your plan or wait for the next billing period.",
  "monthly_limit": 100000,
  "issued_this_month": 100000,
  "billing_period": "2026-06",
  "upgrade_url": "https://algenta.io/pricing"
}
```
{% endexpandable %}

{% hint style="info" %}
`billing_period` must be a `YYYY-MM` string (the CLI validates the format before sending). Credits expire 24 hours after issue (`expires_at`), and the daemon refreshes again after `refresh_after`. Enterprise plans have an unlimited monthly quota and always receive a full batch.
{% endhint %}

## Metering (execution analytics)

Separate from credit enforcement, the daemon flushes a batch of execution events to `POST /v1/metering` roughly every 60 seconds. This endpoint is **analytics-only** — it powers usage dashboards and does not enforce quota (that is the credit bucket's job), so it never double-counts against cloud-API usage.

{% tabs %}
{% tab title="CLI" %}
```bash
algenta metering ingest metering-batch.json
```

```json title="metering-batch.json"
{
  "device_id": "dev-7f3c9a21",
  "events": [
    {
      "event_type": "execute",
      "module": "decision",
      "function": "simulate",
      "engine_used": "mojo",
      "latency_ms": 8.4,
      "success": true,
      "timestamp": 1750444800.0,
      "request_id": "req-001"
    }
  ]
}
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -s -X POST https://api.algenta.ai/v1/metering \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @metering-batch.json
```
{% endtab %}

{% tab title="Python" %}
```python
client.ingest_metering_events(
    device_id="dev-7f3c9a21",
    events=[{
        "event_type": "execute",
        "module": "decision",
        "function": "simulate",
        "engine_used": "mojo",
        "latency_ms": 8.4,
        "success": True,
        "timestamp": 1750444800.0,
        "request_id": "req-001",
    }],
)
```
{% endtab %}

{% tab title="Response" %}
```json
{ "accepted": 1, "billing_period": "2026-06" }
```
{% endtab %}
{% endtabs %}

{% hint style="warning" %}
The events list cannot be empty (`400 empty_events`). Each event accepts only the fields shown above; the billing period is derived per-event from the `timestamp`.
{% endhint %}

## Local mode and hosted enforcement

A local runtime that runs purely embedded — no control-plane `base_url`, no API key — is not subject to device licensing or the credit bucket. You opt **into** hosted enforcement explicitly by configuring credentials.

{% stepper %}
{% step %}
### Set the credentials

```bash
export ALGENTA_API_KEY="ak_live_..."
export ALGENTA_BASE_URL="https://api.algenta.ai"
```

| Variable | Meaning |
| --- | --- |
| `ALGENTA_API_KEY` | API key used as the `Bearer` token (legacy `DE_API_KEY` still accepted) |
| `ALGENTA_BASE_URL` | Control-plane base URL (legacy `DE_BASE_URL` / `ALGENTA_API_URL` still accepted) |
{% endstep %}

{% step %}
### Hosted enforcement activates

With these set, the daemon registers a device, refreshes credits, and flushes metering against the hosted control plane — and the plan limits and overage rules on this page apply. Without them, the local runtime stays offline and outside hosted billing.
{% endstep %}
{% endstepper %}

{% hint style="info" %}
Managed LLM pass-through (where Algenta provides the model key and meters spend) is an optional capability you can enable for your organization. When enabled, spend is metered and surfaced under `managed_llm_spend_usd_month` in `GET /v1/usage` and capped per plan (`llm_spend_cap_usd_month`). Self-hosted and BYOK keys record $0 pass-through cost.
{% endhint %}

## Quick reference

| Action | CLI | Endpoint | SDK (Python) |
| --- | --- | --- | --- |
| Show account + plan | `algenta account me` | `GET /v1/me` | `client.me()` |
| Show usage | `algenta account usage` | `GET /v1/usage` | `client.usage()` |
| Show limits | `algenta account limits` | `GET /v1/limits` | `client.limits()` |
| Billing info | `algenta billing info` | `GET /v1/billing/info` | `client.get_billing_info()` |
| Subscribe / upgrade | `algenta billing checkout <plan>` | `POST /v1/billing/checkout` | `client.create_billing_checkout(plan=...)` |
| Manage subscription | `algenta billing portal` | `POST /v1/billing/portal` | `client.create_billing_portal()` |
| Refresh credits | `algenta credits refresh <file>` | `POST /v1/credits/refresh` | `client.refresh_credits(...)` |
| Ingest metering | `algenta metering ingest <file>` | `POST /v1/metering` | `client.ingest_metering_events(...)` |

## Related pages

{% content-ref url="licensing.md" %}
[licensing.md](licensing.md)
{% endcontent-ref %}

{% content-ref url="authentication.md" %}
[authentication.md](authentication.md)
{% endcontent-ref %}

{% content-ref url="self-hosting.md" %}
[self-hosting.md](self-hosting.md)
{% endcontent-ref %}

{% content-ref url="api/reference.md" %}
[api/reference.md](api/reference.md)
{% endcontent-ref %}
