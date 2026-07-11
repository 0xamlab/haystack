---
icon: gauge-high
description: Unlimited Algenta execution, request safety bounds, licensed worker capacity, and configurable abuse controls.
---

# Execution policy & safety limits

Algenta is licensed per device at a flat price. **Decisions and executions are unlimited on every edition**: there is no monthly quota, per-decision charge, overage rate, or edition-specific request meter. The self-hosted engine does not send execution counts to Algenta or Stripe.

The runtime still records customer-owned audit events inside the deployment. Those local records are governance data, not vendor telemetry or a billing meter.

`GET /v1/limits` reports the effective execution policy. A value of `0` for monthly execution, plan request rate, or concurrent jobs means unlimited.

```bash
curl -sS "$ALGENTA_API_URL/v1/limits" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

## Edition contract

All editions have unlimited decisions, no edition request meter, async execution, and no plan-level concurrent-job quota. The only tiered execution capacity is workers per licensed device:

| Edition | Decisions | Workers/device |
| --- | --- | ---: |
| Community | unlimited | 1 |
| Pro | unlimited | 5 |
| Team | unlimited | 20 |
| Enterprise | unlimited | negotiated |

## Request-shape validation

The current API schema accepts up to 1,000,000 simulation runs in one request and up to 100 items in one batch. These uniform per-payload validation bounds prevent a single request from monopolizing memory; they do not cap total calls, decisions, or monthly execution. Split larger work across calls or async jobs.

Workers/device is licensed capacity, not a rate limit. The bundled runtime enforces the signed-license value locally. See [Licensing & editions](../licensing.md).

## Security abuse controls

Authentication and key-management endpoints retain narrow security controls. These are not decision or execution quotas, and self-hosted operators can configure them:

| Operation | Scope | Default |
| --- | --- | ---: |
| Create an API key | organization | 10/minute |
| Login | email + client IP | 10/minute |
| Signup | client IP | 3/minute |
| Create organizations by signup | email | 2/day |

When one of these security controls is exceeded, the response is HTTP `429` with its operation-specific error code and a `Retry-After` header. This does not consume or reduce an edition execution allowance; no such allowance exists.

Provider APIs and customer infrastructure can still apply their own capacity or rate controls. Algenta surfaces those external errors explicitly rather than relabeling them as an Algenta plan quota.

## Related

{% content-ref url="../billing.md" %}
[billing.md](../billing.md)
{% endcontent-ref %}

{% content-ref url="errors.md" %}
[errors.md](errors.md)
{% endcontent-ref %}
