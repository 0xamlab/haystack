---
sidebar_position: 8
---

# Errors

All error responses use the same JSON structure:

```json
{
  "error": {
    "code": "quota_exceeded",
    "message": "Monthly simulation quota exhausted (500/500). Upgrade your plan.",
    "request_id": "req_abc123",
    "docs_url": "https://docs.codna.ai/errors/quota_exceeded"
  }
}
```

## Error codes reference

### Authentication errors

| Code | HTTP | Description |
|------|------|-------------|
| `authentication_required` | 401 | No API key provided |
| `invalid_api_key` | 401 | Key doesn't exist, revoked, or expired |
| `access_scope_denied` | 403 | Authenticated, but the key or role is not allowed to perform this action |

### Rate limit and quota errors

| Code | HTTP | Description |
|------|------|-------------|
| `rate_limit_exceeded` | 429 | Too many requests per minute for your plan |
| `quota_exceeded` | 429 | Monthly simulation quota exhausted |

For `rate_limit_exceeded`, a `Retry-After: 60` header is included.

### Validation errors

| Code | HTTP | Description |
|------|------|-------------|
| `validation_error` | 422 | Request body schema error |
| `invalid_plan` | 400 | Unknown billing plan |

### Resource errors

| Code | HTTP | Description |
|------|------|-------------|
| `user_not_found` | 404 | User lookup failed |
| `org_not_found` | 404 | Organization not found |
| `api_key_not_found` | 404 | API key ID doesn't exist |
| `job_not_found` | 404 | Async job ID doesn't exist |
| `cannot_revoke_last_key` | 400 | Would leave account with no keys |
| `resource_write_conflict` | 409 | Another write is already in progress for the same write scope |
| `idempotency_key_conflict` | 409 | The same idempotency key was reused with a different payload |

### Engine errors

| Code | HTTP | Description |
|------|------|-------------|
| `engine_error` | 500 | Monte Carlo engine encountered an error |

### Billing errors

| Code | HTTP | Description |
|------|------|-------------|
| `no_billing_account` | 400 | Stripe customer not found — complete checkout first |
| `stripe_error` | 502 | Stripe API call failed |

## Handling errors in code

### Python

```python
from decision_engine.exceptions import (
    AuthenticationError, RateLimitError, QuotaExceededError, APIError
)

try:
    result = client.simulate(...)
except QuotaExceededError:
    print("Upgrade your plan at codna.ai/pricing")
except RateLimitError as e:
    time.sleep(e.retry_after)
    result = client.simulate(...)
except AuthenticationError:
    print("Check your API key")
except APIError as e:
    print(f"Error {e.status}: {e.code} — {e.message}")
```

### TypeScript

```typescript
import { ApiError } from '@decision-engine/sdk'

try {
  const result = await client.simulate(payload)
} catch (e) {
  if (e instanceof ApiError) {
    if (e.status === 429) {
      console.log('Rate limited — wait', e.body?.error?.retry_after_seconds, 'seconds')
    }
  }
}
```
