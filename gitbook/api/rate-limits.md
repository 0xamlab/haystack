---
icon: gauge-high
description: The Algenta request-rate, execution-governance, batch, and worker limits enforced for each edition.
---

# Rate limits & governance limits

Algenta uses four separate controls. They are not interchangeable:

1. **Request rate** bounds selected compute and mutation routes per organization and UTC minute.
2. **Monthly execution governance** bounds hosted control-plane execution. It is a safety limit, not usage-based billing.
3. **Request shape limits** bound runs per call and batch size.
4. **Worker concurrency** bounds simultaneous bundled-runtime work per licensed device.

`GET /v1/limits` is the authoritative response for the authenticated organization. It is generated from the same plan table used by enforcement.

```bash
curl -sS "$ALGENTA_API_URL/v1/limits" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

## Algenta edition defaults

| Edition | Requests/minute | Monthly execution governance | Runs/call | Batch items | Async jobs | Concurrent jobs | Workers/device |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| Community | 60 | 10,000 | 10,000 | 10 | no | 1 | 1 |
| Pro | 300 | 500,000 | 1,000,000 | 100 | yes | 4 | 5 |
| Team | 1,000 | 500,000 | 1,000,000 | 100 | yes | 8 | 20 |
| Enterprise | 10,000 | unlimited | 1,000,000 | 100 | yes | unlimited | negotiated |

The monthly value applies to centrally governed execution. A licensed local runtime does not create a usage invoice; see [Usage & limits](../billing.md). Worker concurrency is enforced by the bundled runtime from the signed license and changes on license renewal.

## Which requests use the plan rate

The plan request rate is applied to compute-bearing route families, including simulations, decision generation, agent execution, repository analysis, LLM operations, and runtime-library execution. Read-only account and discovery routes are not automatically charged against this counter merely because they use the API.

Separate abuse controls protect authentication and key-management routes. Their deployment defaults are:

| Operation | Scope | Default |
| --- | --- | ---: |
| Create an API key | organization | 10/minute |
| Login | email + client IP | 10/minute |
| Signup | client IP | 3/minute |
| Create organizations by signup | email | 2/day |

Self-hosted operators can lower or raise these abuse-control defaults in deployment configuration. The authenticated `GET /v1/limits` response remains the source for plan execution limits.

## Window and headers

Plan request limits use a Redis counter for the current UTC minute. On applicable successful responses, Algenta returns:

```text
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 299
```

When the counter is exceeded, the response is HTTP `429` with error code `rate_limit_exceeded` and:

```text
Retry-After: 60
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 0
```

The `Retry-After` value is a conservative upper bound. Retry only idempotent operations automatically, use jitter, and honor the header rather than hard-coding a shorter delay.

If the rate-limit backend is unavailable under the production fail-closed policy, Algenta returns HTTP `503` with `rate_limit_backend_unavailable` and `Retry-After: 30`. It does not silently pretend the limiter succeeded.

## Monthly governance rejection

When centrally governed execution reaches its monthly ceiling, Algenta returns HTTP `429` with error code `quota_exceeded`, plus `used`, `limit`, and `billing_period`. This is not a short rate window: retrying seconds later will not help. Wait for the next period or change the organization policy or edition.

## Related

{% content-ref url="../billing.md" %}
[billing.md](../billing.md)
{% endcontent-ref %}

{% content-ref url="errors.md" %}
[errors.md](errors.md)
{% endcontent-ref %}
