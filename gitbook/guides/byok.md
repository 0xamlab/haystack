---
icon: key
description: Supply your own LLM-provider or engine credential. Algenta stores it encrypted at rest, never returns the key material, and uses it only to serve your own org's calls.
---

# Bring Your Own Key (BYOK)

Bring Your Own Key (BYOK) lets your organization supply its own LLM-provider credential (or its own Algenta engine key) instead of relying on a platform-pooled key. You submit the secret once; Algenta stores it **encrypted at rest**, **never returns the key material** in any response, and uses it **only to serve your own org's calls**. Customer-supplied provider keys are billed by your provider directly and are not platform-metered.

Per-tenant keys are managed through the API at `/v1/provider-keys` (admin-only, authenticated with an Algenta API key) or by an org admin through the website's `/byok` front door (Supabase-authenticated). Both doors write to the same encrypted store; only the authentication and org-resolution differ.

{% hint style="info" %}
The key value is write-only by design. It is accepted on `POST`, encrypted, and is never read back, logged, or serialized into job payloads. The worker re-resolves your key from your `org_id` at run time. See [Deployment modes](../concepts/deployment-modes.md) for how per-tenant resolution fits self-hosted vs. hosted deployments.
{% endhint %}

## Prerequisites

{% stepper %}
{% step %}
### An admin API key

The `/v1/provider-keys` endpoints require the `admin` role. Authenticate with `Authorization: Bearer <key>`. See [Authentication](../authentication.md) for how to obtain a key.
{% endstep %}

{% step %}
### Config encryption enabled on the server

Setting or rotating a per-tenant key requires a config encryption key on the server. The deployment must have `ALGENTA_CONFIG_ENCRYPTION_KEY` set (a 64-character hex value, or any passphrase). Without it, the server refuses to store a plaintext key and returns `409 encryption_key_required`. See [Self-hosting](../self-hosting.md) for how to configure encryption.
{% endstep %}
{% endstepper %}

## Supported backends

The `backend` field accepts a supported LLM provider, or the literal `engine` for your organization's single Algenta engine key.

| Backend | Notes |
| --- | --- |
| `openai` | OpenAI |
| `openai_compatible` | Any OpenAI-compatible endpoint |
| `anthropic` | Anthropic (Claude) |
| `google_genai` | Google Generative AI |
| `mistral` | Mistral |
| `cohere` | Cohere |
| `groq` | Groq |
| `xai` | xAI |
| `ollama` | Ollama (local) |
| `router` | Multi-provider router |
| `engine` | The reserved per-org Algenta engine key |

## Set or rotate a key

Send a `POST` with the `backend` and the `api_key`. The same call sets a new key or rotates an existing one for that backend.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/provider-keys" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"backend\": \"anthropic\", \"api_key\": \"$ANTHROPIC_API_KEY\"}"
```
{% endtab %}

{% tab title="Python" %}
```python
import os

import httpx

base_url = os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai")

response = httpx.post(
    f"{base_url}/v1/provider-keys",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={"backend": "anthropic", "api_key": os.environ["MY_ANTHROPIC_KEY"]},
)
response.raise_for_status()
print(response.status_code)  # 204
```
{% endtab %}
{% endtabs %}

**Expected result:** the server responds `204 No Content` with no body. The key is now stored encrypted at rest, bound to your organization. The action is recorded in your audit log as `tenant_provider_key.set` (the metadata records the backend and whether it rotated an existing key, but never the key value). No key material is returned by this call or any later call.

{% hint style="warning" %}
If the server has no config encryption key configured, the request fails with `409` and an error body of the shape `{"error": {"code": "encryption_key_required", "message": "..."}}`. Algenta refuses to store a tenant key in plaintext. Set `ALGENTA_CONFIG_ENCRYPTION_KEY` on the deployment and retry.
{% endhint %}

## List configured backends

List which backends have a key configured. The response contains only the backend name and the time it was last set — never the key material.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS "$ALGENTA_API_URL/v1/provider-keys" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Python" %}
```python
import os

import httpx

base_url = os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai")

response = httpx.get(
    f"{base_url}/v1/provider-keys",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
)
response.raise_for_status()
print(response.json())
```
{% endtab %}
{% endtabs %}

The response lists the configured backends and when each was last updated:

```json
{
  "keys": [
    { "backend": "anthropic", "updated_at": "2026-06-21T09:30:00Z" }
  ]
}
```

## Delete a key

Remove a key by passing its backend in the path.

```bash
curl -sS -X DELETE "$ALGENTA_API_URL/v1/provider-keys/anthropic" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The server responds `204 No Content` on success. If no key exists for that backend, it returns `404` with `{"error": {"code": "provider_key_not_found", "message": "..."}}`.

## Set a key from the website

An org admin can also set a provider key from the website's `/byok` front door instead of the API. That page is authenticated by your Supabase (GitHub sign-in) session: it maps your GitHub identity to your Algenta org, confirms you are an org admin, and writes to the same encrypted tenant-key store. The site posts a payload of the shape `{"provider": "anthropic", "key": "<write-only provider key>"}`.

{% hint style="info" %}
The website front door manages your own LLM **provider** key only. The reserved `engine` key cannot be managed from the website; it can only be set through the admin-authenticated `/v1/provider-keys` API.
{% endhint %}

## Next steps

- [Self-hosting](../self-hosting.md) — run Algenta with no outbound network and configure `ALGENTA_CONFIG_ENCRYPTION_KEY`.
- [Deployment modes](../concepts/deployment-modes.md) — how per-tenant key resolution differs across single-tenant and multi-tenant deployments.
- [Authentication](../authentication.md) — obtain an admin API key and use `Authorization: Bearer`.
- [API reference](../api/reference.md) — full request and response schemas for the `/v1/provider-keys` endpoints.
