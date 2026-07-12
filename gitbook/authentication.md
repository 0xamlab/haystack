---
icon: key
description: Create and use Algenta API keys. Mint a key, send it as a Bearer token, and confirm an authenticated request succeeds.
---

# Authentication & API keys

This page is the complete reference for authenticating to Algenta. It covers the API key you send on every request, how to mint bounded keys and revoke them, how the CLI stores credentials, how device binding protects capped keys, the hosted sign-up and login endpoints, and how to bring your own provider keys (BYOK). Every command, header, environment variable, and endpoint below is copied from the running engine and SDKs, so you can paste it directly.

## How authentication works

Algenta authenticates every protected request with a single API key. The key identifies your organization, your plan, and (for capped keys) the device making the call. The engine resolves the key on each request and rejects anything that is missing, invalid, expired, or revoked.

There are two credential surfaces:

- **API keys** — long-lived secrets that authorize machine-to-machine calls (`Authorization: Bearer <key>`). This is what the SDKs, the CLI, and your services use.
- **Hosted session tokens** — short-lived JWTs returned by `POST /auth/login`, used by the dashboard and the sign-up flow. They are also accepted as `Authorization: Bearer <jwt>`.

The same Bearer header carries either credential. The engine figures out which one you sent.

{% hint style="info" %}
Self-hosted, air-gapped, and cloud deployments all use the same auth model. In private profiles the key is provisioned by your operator instead of the Algenta cloud; the request shape is identical.
{% endhint %}

## The API key

An Algenta key looks like `de_live_...` (or `de_test_...` for test keys). It is a bearer secret — anyone holding it can act as your organization, so treat it like a password.

### Sending the key

Send the key as a Bearer token. This is the canonical header and the one the SDKs use. For older clients the engine also accepts `X-API-Key`.

{% tabs %}
{% tab title="Bearer (canonical)" %}
```bash
curl https://api.algenta.ai/v1/me \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="X-API-Key (legacy)" %}
```bash
curl https://api.algenta.ai/v1/me \
  -H "X-API-Key: $ALGENTA_API_KEY"
```
{% endtab %}
{% endtabs %}

{% hint style="warning" %}
If neither header is present, the engine returns `401 authentication_required`. An invalid, expired, or revoked key returns `401 invalid_api_key`.
{% endhint %}

### Environment variables

The SDKs and CLI read the key and base URL from the environment.

| Variable | Purpose | Fallbacks |
| --- | --- | --- |
| `ALGENTA_API_KEY` | Your API key | `DE_API_KEY` (legacy) |
| `ALGENTA_BASE_URL` | API base URL (override for self-hosted) | `DE_BASE_URL`, `ALGENTA_API_URL` |

```bash title="set-env.sh"
export ALGENTA_API_KEY="de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export ALGENTA_BASE_URL="https://api.algenta.ai"
```

{% hint style="info" %}
`DE_API_KEY` is accepted everywhere `ALGENTA_API_KEY` is, but `ALGENTA_API_KEY` wins if both are set.
{% endhint %}

### Using the key from the SDKs

Both SDKs resolve the key from the constructor argument first, then `ALGENTA_API_KEY`, then `DE_API_KEY`. They attach `Authorization: Bearer <key>` to every request automatically. Install the TypeScript package from npm as `algenta-sdk`.

{% tabs %}
{% tab title="Python" %}
```python title="client.py"
import os
from decision_engine import AlgentaClient

# Resolves ALGENTA_API_KEY / DE_API_KEY from the environment if api_key is omitted.
client = AlgentaClient(
    api_key=os.environ.get("ALGENTA_API_KEY"),
    base_url=os.environ.get("ALGENTA_BASE_URL"),  # omit for the default cloud URL
)
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript title="client.ts"
import { AlgentaClient } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const client = new AlgentaClient({ apiKey });
```
{% endtab %}
{% endtabs %}

{% hint style="info" %}
`AlgentaClient` is the preferred name. `DecisionEngineClient` remains exported as an alias for backward compatibility — they are the same client.
{% endhint %}

## Managing API keys

Your first key is your **bootstrap key** — created with your account at sign-up and shown once. Use it to mint **bounded replacement keys**: scoped, labeled keys with an optional expiry and device cap. Rotate by creating a new key, moving your traffic to it, then revoking the old one.

### List keys

{% tabs %}
{% tab title="cURL" %}
```bash
curl https://api.algenta.ai/v1/api-keys \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="CLI" %}
```bash
de keys list
```
{% endtab %}
{% endtabs %}

The response lists active keys with their prefix, label, device limit, and timestamps. Key material is never returned — only `key_prefix` (the first 12 characters) so you can identify a key.

### Create a bounded key

`POST /v1/api-keys` accepts a label and, optionally, an expiry and a device limit. Creating a key requires at least the `member` role.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -X POST https://api.algenta.ai/v1/api-keys \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "CI runner",
    "expires_at": "2026-12-31T23:59:59Z",
    "device_limit": 3
  }'
```
{% endtab %}

{% tab title="CLI" %}
```bash
de keys create "CI runner" \
  --device-limit 3 \
  --expires-at 2026-12-31T23:59:59Z
```
{% endtab %}
{% endtabs %}

| Field | Type | Notes |
| --- | --- | --- |
| `label` | string | Human-readable name shown in lists and audit logs. |
| `expires_at` | RFC 3339 timestamp, optional | After this time the key returns `401 invalid_api_key`. |
| `device_limit` | integer, optional | Max distinct devices that may bind to this key. `0` = unlimited. Validated against your plan. |

The response includes `raw_key` — the full secret.

{% hint style="danger" %}
`raw_key` is returned **exactly once**. Store it immediately; you cannot retrieve it again. If you lose it, revoke the key and mint a new one.
{% endhint %}

{% expandable title="Example create response" %}
```json
{
  "id": "0f4c...",
  "label": "CI runner",
  "key_prefix": "de_live_8a2",
  "device_limit": 3,
  "raw_key": "de_live_8a2f...redacted...",
  "created_at": "2026-06-20T10:00:00Z",
  "expires_at": "2026-12-31T23:59:59Z"
}
```
{% endexpandable %}

{% hint style="info" %}
A `device_limit` greater than zero makes the key a **capped key**. Capped keys enforce device binding (see below). A bootstrap or broad key with `device_limit: 0` skips binding entirely.
{% endhint %}

### Revoke a key

{% tabs %}
{% tab title="cURL" %}
```bash
curl -X DELETE https://api.algenta.ai/v1/api-keys/0f4c... \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="CLI" %}
```bash
de keys revoke $KEY_ID
```
{% endtab %}
{% endtabs %}

Revocation is immediate and audited. Two guards apply:

- You **cannot revoke the last active key** (`400 cannot_revoke_last_key`). Create a replacement first.
- Revoking a key that does not belong to your org returns `404 api_key_not_found`.

### Rotate a key safely

{% stepper %}
{% step %}
### Mint the replacement
Create a new bounded key with the same scope. Capture its `raw_key` from the one-time response.

```bash
de keys create "prod-2026-q3" --device-limit 5
```
{% endstep %}

{% step %}
### Cut traffic over
Update `ALGENTA_API_KEY` (or your secret manager) in every service and CI runner to the new key, and roll your deployments.
{% endstep %}

{% step %}
### Verify the old key is idle
Confirm no traffic is still authenticating with the old key before removing it. Until then, leave both active.
{% endstep %}

{% step %}
### Revoke the old key
Once the new key carries all traffic, revoke the old one. Revocation is immediate.

```bash
de keys revoke $OLD_KEY_ID
```
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — during cutover, requests with the new key succeed; once you revoke the old key it returns `401 Unauthorized`. Traffic is never interrupted.
{% endhint %}

## CLI authentication

The self-hosted control-plane CLI is invoked as `de`. It reads `ALGENTA_API_KEY` first and otherwise uses the operating-system credential store. Non-secret settings remain in `~/.de/config.json`; API keys are never written there. The self-hosted installer creates the wrapper; `algenta-sdk` does not install it.

```bash
# The self-hosted installer creates $HOME/.local/bin/de.
curl -sSL https://algenta.ai/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
```

### Log in (register this machine)

`de login` registers the current machine under your API key, obtains a signed device license, and stores it locally.

```bash
de login                                 # prompts for the API key
de login $ALGENTA_API_KEY                # key as an argument (CI-safe)
ALGENTA_API_KEY=de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx de login
```

### Log out

```bash
de logout                                # removes the stored device license
```

### Save a key without registering a device

`de config set-key` writes the key to the operating-system credential store and writes only an optional base URL to the CLI config. If the host has no secure credential backend, the command fails closed; use `ALGENTA_API_KEY` in the process environment. Use this command for plain API access when you do not need a local device license.

```bash
de config set-key $ALGENTA_API_KEY
de config set-key $ALGENTA_API_KEY https://api.algenta.ai
```

### Manage keys from the CLI

```bash
de keys list                                       # list active API keys
de keys create "Mission Key"                       # mint a new key
de keys create "CI" --device-limit 3 --expires-at 2026-12-31T23:59:59Z
de keys revoke $KEY_ID                            # revoke a key
```

{% hint style="info" %}
Add `--format json` to any of these for machine-readable output.
{% endhint %}

## Device binding (capped keys)

When a key has a finite `device_limit`, the engine binds it to specific machines. Each machine must present a stable device identity; a different machine reusing the same device id is treated as a clone and rejected. This is what prevents one capped key from being shared across an unbounded fleet.

### From the SDKs and CLI

The SDKs and CLI handle binding for you. They derive a stable device id from the machine, send the device headers automatically, and store the binding token they receive so subsequent calls succeed. There is nothing to configure.

The headers they send:

| Header | Meaning |
| --- | --- |
| `X-Algenta-Device-Id` | Stable per-machine id (16–64 chars). |
| `X-Algenta-Platform` | OS family, e.g. `Darwin`, `Linux`. |
| `X-Algenta-Platform-Version` | OS release string. |
| `X-Algenta-Hostname-Hash` | Salted hash of the machine fingerprint. |
| `X-Algenta-SDK-Version` | SDK / client version. |

{% hint style="info" %}
You can pin the device id explicitly with `ALGENTA_DEVICE_ID` (or legacy `DE_DEVICE_ID`) — useful for ephemeral CI workers that need a deterministic identity.
{% endhint %}

### From raw HTTP

If you call the engine directly with a capped key, you must send the device headers yourself. On the **first** request that binds a device, the engine returns an `X-Algenta-Device-Binding-Token` response header. Replay that token on every subsequent request from the same device.

{% stepper %}
{% step %}
### First request (binds the device)
Send the device headers. The response carries `X-Algenta-Device-Binding-Token`.

```bash
curl -i -X POST https://api.algenta.ai/v1/simulate \
  -H "Authorization: Bearer de_live_CAPPED_KEY" \
  -H "X-Algenta-Device-Id: ci-runner-7f3a9b1c2d4e5f60" \
  -H "X-Algenta-Platform: Linux" \
  -H "X-Algenta-Hostname-Hash: 3b1c...e90" \
  -H "Content-Type: application/json" \
  -d '{ "...": "..." }'
# Response includes:  X-Algenta-Device-Binding-Token: <token>
```
{% endstep %}

{% step %}
### Subsequent requests (replay the token)
Add the binding token from step one to every later call from the same device.

```bash
curl -X POST https://api.algenta.ai/v1/simulate \
  -H "Authorization: Bearer de_live_CAPPED_KEY" \
  -H "X-Algenta-Device-Id: ci-runner-7f3a9b1c2d4e5f60" \
  -H "X-Algenta-Platform: Linux" \
  -H "X-Algenta-Hostname-Hash: 3b1c...e90" \
  -H "X-Algenta-Device-Binding-Token: <token>" \
  -H "Content-Type: application/json" \
  -d '{ "...": "..." }'
```
{% endstep %}
{% endstepper %}

{% expandable title="Device binding error reference" %}
Binding fails closed. The errors you may encounter:

- `403 device_identity_mismatch` — reusing a device id with a different fingerprint.
- `401 device_binding_required` — missing `X-Algenta-Device-Id`.
- `401 device_binding_token_required` — the device is already bound; replay the token.
- `403 invalid_device_binding_token` — the supplied token does not match.
- `402 device_limit_reached` — the key's device slots are full; revoke a device or create a broader key.
{% endexpandable %}

### Manage devices

{% tabs %}
{% tab title="CLI" %}
```bash
de devices list                          # list registered devices
de devices revoke $REGISTRATION_ID      # free up one device slot
```
{% endtab %}

{% tab title="cURL" %}
```bash
# List devices registered under this key's org
curl https://api.algenta.ai/v1/device/list \
  -H "Authorization: Bearer $ALGENTA_API_KEY"

# Revoke a device by its registration id (frees a slot)
curl -X DELETE https://api.algenta.ai/v1/device/$REGISTRATION_ID \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}
{% endtabs %}

{% hint style="info" %}
`de login` corresponds to `POST /v1/device/register`, which checks the plan's device limit and returns a signed license token.
{% endhint %}

## Hosted sign-up and login

The hosted control plane exposes a self-serve auth router under the `/auth` prefix. These endpoints issue and reset credentials; they do not require an existing API key.

### Sign up

Creates an organization, a user, and a first API key in one step. The raw API key is shown once in the response.

```bash
curl -X POST https://api.algenta.ai/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "password": "a-strong-password",
    "name": "Your Name"
  }'
```

### Log in

Returns a JWT bearer token. Use it as `Authorization: Bearer <token>`.

{% tabs %}
{% tab title="Request" %}
```bash
curl -X POST https://api.algenta.ai/auth/login \
  -H "Content-Type: application/json" \
  -d '{ "email": "you@example.com", "password": "a-strong-password" }'
```
{% endtab %}

{% tab title="Response" %}
```json
{ "access_token": "eyJ...", "token_type": "bearer", "expires_in": 604800 }
```
{% endtab %}
{% endtabs %}

### Verify email, forgot, and reset password

{% expandable title="Verify, forgot-password, and reset-password requests" %}
```bash
# Verify an email via the token from the verification link
curl "https://api.algenta.ai/auth/verify?token=$VERIFICATION_TOKEN"

# Request a reset email (always returns success; never reveals whether the email exists)
curl -X POST https://api.algenta.ai/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{ "email": "you@example.com" }'

# Complete the reset with the token from the email
curl -X POST https://api.algenta.ai/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{ "token": "$RESET_TOKEN", "new_password": "a-new-strong-password" }'
```
{% endexpandable %}

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/auth/signup` | POST | Create account + org + first API key. |
| `/auth/login` | POST | Exchange credentials for a session JWT. |
| `/auth/verify` | GET | Verify an email address from the link token. |
| `/auth/forgot-password` | POST | Send a password reset email. |
| `/auth/reset-password` | POST | Complete a password reset. |

## BYOK: provider keys

Bring-your-own-key lets your organization supply its own LLM provider credentials (and an optional Algenta engine key) instead of using managed billing. Keys are **write-only**: accepted on POST, stored encrypted at rest, and never returned by any endpoint. Managing provider keys requires the `admin` role.

{% hint style="warning" %}
Setting or rotating a provider key requires the engine to be configured with `ALGENTA_CONFIG_ENCRYPTION_KEY`. Without it, `POST /v1/provider-keys` refuses to store a plaintext key and returns `409 encryption_key_required`.
{% endhint %}

### Set or rotate a provider key

```bash
curl -X POST https://api.algenta.ai/v1/provider-keys \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"backend\": \"anthropic\",
    \"api_key\": \"$ANTHROPIC_API_KEY\"
  }"
```

| Field | Type | Notes |
| --- | --- | --- |
| `backend` | string | Provider backend, e.g. `anthropic`, `openai`, `google_genai`, or `engine` for the Algenta engine key. |
| `api_key` | string | The provider/engine secret. Stored encrypted; never returned. |

### List configured backends

Returns the configured backends and when each was last updated — no key material.

{% tabs %}
{% tab title="Request" %}
```bash
curl https://api.algenta.ai/v1/provider-keys \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Response" %}
```json
{ "keys": [ { "backend": "anthropic", "updated_at": "2026-06-20T10:00:00Z" } ] }
```
{% endtab %}
{% endtabs %}

### Delete a provider key

```bash
curl -X DELETE https://api.algenta.ai/v1/provider-keys/anthropic \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

{% hint style="info" %}
A backend with no configured key returns `404 provider_key_not_found`.
{% endhint %}

## Quick reference

| Action | How |
| --- | --- |
| Send a key | `Authorization: Bearer de_live_...` (or legacy `X-API-Key`) |
| Set the key for SDK/CLI | `export ALGENTA_API_KEY=...` (fallback `DE_API_KEY`) |
| Set a self-hosted base URL | `export ALGENTA_BASE_URL=...` (fallbacks `DE_BASE_URL`, `ALGENTA_API_URL`) |
| List / create / revoke keys | `GET /v1/api-keys`, `POST /v1/api-keys`, `DELETE /v1/api-keys/{key_id}`, or `de keys list\|create\|revoke` |
| Register / log out a machine | `de login` / `de logout` |
| Save a key without binding | `de config set-key <key> [base_url]` |
| List / revoke devices | `de devices list\|revoke`, or `/v1/device/list`, `DELETE /v1/device/{id}` |
| Hosted auth | `POST /auth/signup`, `/auth/login`, `GET /auth/verify`, `POST /auth/forgot-password`, `/auth/reset-password` |
| BYOK provider keys | `GET /v1/provider-keys`, `POST /v1/provider-keys`, `DELETE /v1/provider-keys/{backend}` (admin; needs `ALGENTA_CONFIG_ENCRYPTION_KEY`) |

## Related pages

{% content-ref url="quickstart.md" %}
[quickstart.md](quickstart.md)
{% endcontent-ref %}

{% content-ref url="cli.md" %}
[cli.md](cli.md)
{% endcontent-ref %}

{% content-ref url="api/reference.md" %}
[api/reference.md](api/reference.md)
{% endcontent-ref %}

{% content-ref url="licensing.md" %}
[licensing.md](licensing.md)
{% endcontent-ref %}
