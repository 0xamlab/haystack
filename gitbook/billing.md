---
icon: gauge-high
description: Inspect unlimited execution policy and local governance records. Algenta is licensed per device, never per decision.
---

# Usage & execution policy

Algenta is **licensed per device** — a flat license with unlimited decisions and **no usage-based billing**. There is no per-simulation metering, no compute overage, and no surprise invoice. For the editions (Community, Pro, Team, Enterprise), what a license grants, and how to install and verify one offline, see [Licensing & editions](licensing.md).

This page covers the runtime's **governance and observability** endpoints: how to inspect the unlimited execution policy and query customer-owned activity records for audit. These records stay inside a self-hosted deployment; Algenta execution counts are not sent to Algenta or Stripe. Every command and endpoint below is real and runs against a hosted or self-hosted deployment.

{% hint style="info" %}
Looking for pricing, editions, or how to license a commercial deployment? That lives in [Licensing & editions](licensing.md). This page is purely operational — inspecting limits and usage.
{% endhint %}

## Inspect the effective policy

`GET /v1/limits` returns execution policy and request-shape safety bounds. `0` means unlimited for monthly execution, plan request rate, and concurrent async jobs.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -s https://api.algenta.ai/v1/limits \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="CLI" %}
```bash
de account limits
```
{% endtab %}

{% tab title="Response" %}
```json
{
  "plan": "algenta_team",
  "max_simulations_per_month": 0,
  "max_runs_per_simulation": 1000000,
  "max_batch_items": 100,
  "rate_limit_per_minute": 0,
  "async_jobs_enabled": true,
  "webhooks_enabled": true,
  "concurrent_jobs": 0,
  "storage_gb": 0,
  "llm_spend_cap_usd_month": 0
}
```
{% endtab %}
{% endtabs %}

## Observe your usage

`GET /v1/usage` reports local activity for audit and capacity planning. On a self-hosted deployment these records remain in your database. They are not an Algenta usage bill or vendor telemetry: decisions are unlimited and nothing here is invoiced per call.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -s https://api.algenta.ai/v1/usage \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="CLI" %}
```bash
de account usage
```
{% endtab %}

{% tab title="Response" %}
```json
{
  "billing_period": "2026-07",
  "simulations_run": 4210,
  "api_calls": 4210,
  "storage_bytes_used": 0,
  "storage_gb_limit": 10
}
```
{% endtab %}
{% endtabs %}

{% hint style="success" %}
Add `--format json` to any `de account` command for raw output suitable for scripting.
{% endhint %}

## Governance, not billing

Keys, local activity records, and audit are **runtime primitives** — the same controls apply to humans, SDKs, and AI agents because every call crosses one governed boundary. They are decoupled from how you pay: one flat license per device, with unlimited decisions.

* **Per-tenant provider keys (BYOK)** — bring your own model keys, encrypted at rest. See [Bring your own key](guides/byok.md).
* **Teams, roles & audit** — scope who can do what and keep an append-only trail. See [Teams, roles & audit logs](operate/teams-rbac.md).
* **Egress & privacy** — inspect and tighten what a self-hosted engine sends outbound. See [Egress policy & privacy reports](operate/privacy-egress.md).

<table data-view="cards">
<thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Licensing &amp; editions</strong></td><td>How Algenta is licensed per device, the editions, and offline verification.</td><td><a href="licensing.md">licensing.md</a></td></tr>
<tr><td><strong>Self-host the engine</strong></td><td>Run Algenta on your own infrastructure.</td><td><a href="self-hosting.md">self-hosting.md</a></td></tr>
<tr><td><strong>Teams, roles &amp; audit</strong></td><td>Govern access with roles and an audit trail.</td><td><a href="operate/teams-rbac.md">operate/teams-rbac.md</a></td></tr>
</tbody>
</table>
