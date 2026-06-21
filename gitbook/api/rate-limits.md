---
icon: gauge-high
description: Algenta rate limits and plan quotas — generated from the server settings so the numbers are authoritative and current, with how to handle 429 and quota errors.
---

# Rate limits & quotas

Algenta enforces per-plan **quotas** (monthly usage) and per-endpoint **rate limits** (abuse protection). The values below are generated from the server settings (`apps/api_server/config.py`), so they match what the engine actually enforces. Plan tiers are on [Plans, billing & credits](../billing.md).

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

## Handling limits

{% hint style="info" %}
A quota or rate-limit rejection returns the standard error envelope (for example `quota_exceeded` or a `429`). Back off and retry with jitter on `429`; for `quota_exceeded`, upgrade the plan or wait for the monthly reset. See [Error codes](errors.md).
{% endhint %}

## Related

{% content-ref url="../billing.md" %}
[billing.md](../billing.md)
{% endcontent-ref %}
