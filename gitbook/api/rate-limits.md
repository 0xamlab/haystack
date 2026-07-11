---
icon: gauge-high
description: Algenta rate limits and plan quotas — the authoritative numbers the engine enforces, with how to handle 429 and quota errors.
---

# Rate limits & quotas

Algenta enforces three things: per-plan **quotas** (monthly usage), per-endpoint **rate limits** (abuse protection), and a **per-device worker concurrency cap** (how many jobs one machine runs in parallel). The values below are the authoritative numbers the engine enforces. Plan tiers are on [Plans, billing & credits](../billing.md).

| Setting | Default | What it limits |
| --- | --- | --- |
| `API_KEY_CREATE_RATE_LIMIT_PER_MINUTE` | `10` | API-key creations per minute. |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `10` | Login attempts per minute. |
| `MAX_BATCH_ITEMS_FREE` | `10` | Maximum batch items on the Free plan. |
| `MAX_BATCH_ITEMS_PRO` | `100` | Maximum batch items on the Pro plan. |
| `MAX_PAYLOAD_SIZE_BYTES` | `1048576` | Maximum request body size. |
| `MAX_SYNC_RUNS` | `100000` | Maximum simulation runs in a synchronous request. |
| `MOJO_MAX_CONCURRENT` | `4` | — |
| `QUOTA_DEVELOPER_SIMULATIONS_MONTH` | `10000` | Monthly simulations on the Developer plan. |
| `QUOTA_FREE_SIMULATIONS_MONTH` | `500` | Monthly simulations on the Free plan. |
| `QUOTA_PRO_SIMULATIONS_MONTH` | `100000` | Monthly simulations on the Pro plan. |
| `SIGNUP_MAX_PER_DAY_PER_EMAIL` | `2` | Sign-ups per day per email. |
| `SIGNUP_RATE_LIMIT_PER_MINUTE` | `3` | Sign-up attempts per minute (abuse protection). |
| `WEBHOOK_MAX_RETRIES` | `3` | — |

## Per-device worker concurrency

The self-hosted engine caps **concurrent workers per device** — how many simulations/analyses a single machine runs in parallel. This is enforced locally by the runtime worker broker (offline-capable, no network call), and the cap comes from your license tier:

| Tier | Workers per device |
| --- | --- |
| Community (free) | 1 |
| Pro | 5 |
| Team | 20 |
| Enterprise | Unlimited (negotiated) |

Work beyond the cap queues until a slot frees (or is rejected immediately on a non-blocking request). Upgrading your plan raises the cap on the **next license renewal** — no redeploy needed.

## Handling limits

{% hint style="info" %}
A quota or rate-limit rejection returns the standard error envelope (for example `quota_exceeded` or a `429`). Back off and retry with jitter on `429`; for `quota_exceeded`, upgrade the plan or wait for the monthly reset. See [Error codes](errors.md).
{% endhint %}

## Related

{% content-ref url="../billing.md" %}
[billing.md](../billing.md)
{% endcontent-ref %}
