---
icon: gauge-high
description: Inspect your plan's limits and observe usage for governance and audit. Algenta is licensed per device — see Licensing for editions and terms.
---

# Usage & limits

Algenta is **licensed per device** — a flat license with unlimited decisions and **no usage-based billing**. There is no per-simulation metering, no compute overage, and no surprise invoice. For the editions (Community, Pro, Team, Enterprise), what a license grants, and how to install and verify one offline, see [Licensing & editions](licensing.md).

This page covers the runtime's **governance and observability** endpoints: how to read your plan's configured limits and observe usage for audit. Metering, quotas, and per-key limits are **governance primitives you configure** to bound keys and AI agents — not a bill. Every command and endpoint below is real and runs against a hosted or self-hosted deployment.

{% hint style="info" %}
Looking for pricing, editions, or how to license a commercial deployment? That lives in [Licensing & editions](licensing.md). This page is purely operational — inspecting limits and usage.
{% endhint %}

## Inspect your plan's limits

`GET /v1/limits` returns the capabilities and governance caps configured for your plan (device count, rate limit, concurrency, and optional per-key quotas you can set to bound agents).

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
  "plan": "team",
  "max_runs_per_simulation": 1000000,
  "max_batch_items": 100,
  "rate_limit_per_minute": 1000,
  "async_jobs_enabled": true,
  "webhooks_enabled": true,
  "concurrent_jobs": 8,
  "storage_gb": 10
}
```
{% endtab %}
{% endtabs %}

## Observe your usage

`GET /v1/usage` reports your current activity for the period — counts, any configured governance limit, and (when you use managed keys) provider spend. It is **observability for audit and capacity planning**, not a usage bill: on the per-device license, decisions are unlimited and nothing here is invoiced.

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

Keys, quotas, metering, and audit are **runtime primitives** — the same controls apply to humans, SDKs, and AI agents because every call crosses one governed boundary. You set them to keep autonomy inside the lines you draw, and they are decoupled from how you pay (a flat per-device license):

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
