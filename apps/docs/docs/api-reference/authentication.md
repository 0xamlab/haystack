---
sidebar_position: 3
---

# Authentication

All API endpoints require an API key. The canonical `v1` auth format is `Authorization: Bearer <api_key>`.

## API key format

```
de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- Prefix `de_live_` for production keys
- Prefix `de_test_` for test keys (future — not rate limited)
- 32+ random URL-safe characters after the prefix
- Stored as SHA-256(raw_key) in the database — the raw key is shown only once on creation

## Sending your key

### Bearer header (recommended)

```bash
curl -H "Authorization: Bearer de_live_..." https://api.algenta.ai/v1/simulate
```

### Legacy header compatibility

```bash
curl -H "X-API-Key: de_live_..." https://api.algenta.ai/v1/simulate
```

## Getting an API key

### Via signup

```bash
curl -X POST https://api.algenta.ai/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword","name":"Your Name"}'
```

Returns `api_key.raw_key` — the only time the full key is shown.

### Via developer portal

Sign in at [https://app.algenta.ai](https://app.algenta.ai) → API Keys → Create Key.

### Via CLI

```bash
de-cli auth login --email you@example.com
de-cli keys create --label production
```

## Error responses

| Status | Code | Meaning |
|--------|------|---------|
| `401` | `authentication_required` | No API key provided |
| `401` | `invalid_api_key` | Key doesn't exist, revoked, or expired |
| `403` | `access_scope_denied` | Your key is valid, but it is not allowed to perform this action |
| `429` | `rate_limit_exceeded` | Too many requests/minute for your plan |
| `429` | `quota_exceeded` | Monthly simulation quota exhausted |

## Security model

- Keys are stored as SHA-256 hashes (bcrypt not needed — entropy is already 256 bits)
- Redis cache with 5-minute TTL for auth hot path (< 1ms avg latency)
- Keys can be revoked instantly — cache TTL is the max propagation delay
- All API communication over TLS 1.2+
- Rate limiting enforced per-org per-minute via Redis INCR
