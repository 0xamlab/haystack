---
sidebar_position: 3
slug: /api-reference/authentication
---

# API Authentication

All API requests use `Authorization: Bearer <api_key>`.

## Bootstrap key behavior

The self-hosted installer creates a bootstrap key with the `de_test_` prefix and prints it once:

```text
API Key: <SELF_HOST_BOOTSTRAP_KEY>
```

Use that key for the first authenticated requests against the running service.

> **Critical**
> The installer prints the bootstrap API key only once. Store it before closing the terminal.

## Bearer header

```bash
curl http://localhost:8000/v1/simulate \
  -H "Authorization: Bearer <SELF_HOST_BOOTSTRAP_KEY>"
```

## Legacy header compatibility

```bash
curl http://localhost:8000/v1/simulate \
  -H "X-API-Key: <SELF_HOST_BOOTSTRAP_KEY>"
```

## Key rotation

Create a replacement key first:

```bash
curl -X POST http://localhost:8000/v1/api-keys \
  -H "Authorization: Bearer <SELF_HOST_BOOTSTRAP_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"label":"replacement-key","expires_at":"2028-05-19T00:00:00Z","device_limit":3}'
```

`expires_at` is optional, must be an ISO-8601 timestamp, and must be in the future.
`device_limit` is optional, must be a non-negative integer, and sets the max
registered machines for that key. `0` means unlimited only on plans that allow
unlimited devices.

An explicit `device_limit` now binds both local runtime/device registration and
ordinary hosted API traffic for that key. Once the cap is reached, a new
machine gets `device_limit_reached` until you revoke an existing device or use
a broader key.

The Python and TypeScript SDKs send the required stable device headers
automatically. Raw HTTP clients using capped keys must send both
`X-Algenta-Device-Id`, `X-Algenta-Platform`, and
`X-Algenta-Hostname-Hash` on authenticated requests. On the first successful
hosted request for a new capped device, the API also returns
`X-Algenta-Device-Binding-Token`. Store that token and replay it on later
requests from the same device. If you omit it later, the request fails closed
with `device_binding_token_required`; if you send the wrong value, it fails
closed with `invalid_device_binding_token`.
Reusing the same device ID with different non-empty machine fingerprint metadata
fails closed with `device_identity_mismatch`; keep device identity stable per
machine.

List active keys:

```bash
curl http://localhost:8000/v1/api-keys \
  -H "Authorization: Bearer <SELF_HOST_BOOTSTRAP_KEY>"
```

`GET /v1/api-keys` returns non-secret metadata such as `id`, `label`,
`key_prefix`, `device_limit`, `created_at`, and `expires_at`. It never returns `raw_key` again.

Revoke the old key:

```bash
curl -X DELETE http://localhost:8000/v1/api-keys/<key_id> \
  -H "Authorization: Bearer <SELF_HOST_BOOTSTRAP_KEY>"
```

The replacement `raw_key` is shown only once. Store it, along with the returned
`id`, `key_prefix`, `device_limit`, and `expires_at`, before revoking the
previous key.

## Error responses

| Status | Code | Meaning |
| --- | --- | --- |
| `401` | `authentication_required` | No API key provided |
| `401` | `invalid_api_key` | Key does not exist, is revoked, or is expired |
| `403` | `access_scope_denied` | The key is valid but not allowed to perform this action |
| `429` | `rate_limit_exceeded` | Endpoint abuse control, upstream provider limit, or operator policy |
| `429` | `quota_exceeded` | Custom non-Algenta governance policy; Algenta editions have no execution quota |

## Related pages

- [Quickstart](/quickstart)
- [Python SDK](/sdks/python)
- [TypeScript SDK](/sdks/typescript)
