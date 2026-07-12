---
icon: user-gear
description: MCP reference for account, identity, API keys, usage and runtime discovery — the get_contract, get_me, key-management, run-history and analytics tools.
---

# Account & meta MCP tools

These tools cover **discovery** (what this Algenta instance is and can execute), **identity and account** (who you are, your limits, your keys), and **history** (simulation runs, analytics, usage). They are read-mostly and the natural first calls an assistant makes before doing real work — `get_contract` tells it what the instance supports, and `get_me` / `get_limits` tell it what the current key is allowed to do.

## Discovery & runtime tools

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `get_contract` | Get the machine-readable platform contract: discovery, query, batch, SQL-report, governed-filter rules, and CLI/MCP entrypoints. | none |
| `get_runtime_manifest` | Get the signed runtime manifest: runtime-core inventory, maturity states, proof matrix, and failure contract. | none |
| `get_runtime_modules` | Get the runtime module proof catalog: shipping modules, proof-matrix entries, maturity counts. | none |
| `get_runtime_benchmarks` | Get the runtime benchmark catalog: benchmark classes, SLO budgets, evaluation quality gates. | none |
| `get_runtime_release_validation` | Get the current runtime release-validation verdict and fail-closed proof status. | none |

## Identity & key tools

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `get_me` | Get the current user and organization identity for the active key. | none |
| `update_me` | Update the current user name and/or organization name. | `name`, `org_name` |
| `get_limits` | Get current plan quotas and limits. | none |
| `list_distributions` | List supported distribution types. | none |
| `list_templates` | List built-in simulation templates. | none |
| `list_api_keys` | List active API keys (never returns raw secrets). | none |
| `create_api_key` | Create a new key and return its one-time `raw_key`. | `label` (required), `expires_at` (date-time), `device_limit` (≥0) |
| `revoke_api_key` | Revoke one key by id. | `key_id` (required) |

## History & usage tools

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `list_runs` | List recent simulation runs. | `limit` (default `20`, 1–100), `mode` (`auto`/`expert`), `status` (`completed`/`failed`/`running`) |
| `get_run` | Fetch one simulation run by id. | `run_id` (required) |
| `get_analytics` | Get usage analytics: volume, latency p95, outcome distributions. | `days` (default `30`) |
| `get_usage` | Get current billing-period usage vs quota for this key. | none |

{% hint style="warning" %}
`create_api_key` returns the secret `raw_key` exactly once, in the create response — it is never retrievable again. Store it immediately in a secrets manager. `list_api_keys` returns metadata only.
{% endhint %}

## HTTP mapping

| Tool | Method | Endpoint |
| --- | --- | --- |
| `get_contract` | `GET` | `/v1/meta/contract` |
| `get_runtime_manifest` | `GET` | `/v1/runtime/manifest` |
| `get_runtime_modules` | `GET` | `/v1/admin/runtime/modules` |
| `get_runtime_benchmarks` | `GET` | `/v1/admin/runtime/benchmarks` |
| `get_runtime_release_validation` | `GET` | `/v1/admin/runtime/validation` |
| `get_me` | `GET` | `/v1/me` |
| `update_me` | `PATCH` | `/v1/me` |
| `get_limits` | `GET` | `/v1/limits` |
| `list_distributions` | `GET` | `/v1/distributions` |
| `list_templates` | `GET` | `/v1/templates` |
| `list_api_keys` | `GET` | `/v1/api-keys` |
| `create_api_key` | `POST` | `/v1/api-keys` |
| `revoke_api_key` | `DELETE` | `/v1/api-keys/{key_id}` |
| `list_runs` | `GET` | `/v1/runs` |
| `get_run` | `GET` | `/v1/runs/{run_id}` |
| `get_analytics` | `GET` | `/v1/runs/analytics` |
| `get_usage` | `GET` | `/v1/usage` |

## Worked examples

### Discover the instance with get_contract

The contract is the first call an assistant should make: it returns the endpoints, tool entrypoints, and governed-filter rules the instance actually supports.

{% tabs %}
{% tab title="MCP tool call" %}
`get_contract` takes no arguments. It returns a normalized object:

```json title="get_contract — result (abridged)"
{
  "contract_version": "1.0",
  "brand": "Algenta",
  "api_base_url": "https://api.algenta.ai",
  "mcp_endpoint": "/mcp",
  "mcp_transport": "streamable_http",
  "mcp_protocol_version": "2025-11-25",
  "mcp_tools_endpoint": "/mcp/tools",
  "auth_scheme": "Authorization: Bearer",
  "primary_data_query_contract": { "governed_filter_contract": { "...": "..." } },
  "capability_plane": { "...": "..." },
  "integrations": { "...": "..." }
}
```
{% endtab %}

{% tab title="HTTP" %}
```bash title="contract.sh"
curl -sS "$ALGENTA_BASE_URL/v1/meta/contract" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}
{% endtabs %}

### Check identity and remaining quota

{% tabs %}
{% tab title="MCP tool call" %}
`get_me` and `get_usage` take no arguments. `get_usage` reports the current billing period against quota:

```json title="get_usage — result"
{
  "simulations_used": 4210,
  "simulations_limit": 100000,
  "billing_period": "2026-07",
  "plan": "developer",
  "api_calls": 5623,
  "pct_used": 4.21
}
```
{% endtab %}

{% tab title="HTTP" %}
```bash title="me_usage.sh"
curl -sS "$ALGENTA_BASE_URL/v1/me" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
curl -sS "$ALGENTA_BASE_URL/v1/usage" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}
{% endtabs %}

### Create a scoped API key

{% tabs %}
{% tab title="MCP tool call" %}
```json title="create_api_key — arguments"
{ "label": "ci-pipeline", "device_limit": 2 }
```

```json title="create_api_key — result (raw_key shown once)"
{ "id": "$KEY_ID", "label": "ci-pipeline", "raw_key": "de_live_...", "device_limit": 2 }
```

Revoke it later with `revoke_api_key`:

```json title="revoke_api_key — result"
{ "key_id": "$KEY_ID", "revoked": true }
```
{% endtab %}

{% tab title="HTTP" %}
```bash title="keys.sh"
curl -sS "$ALGENTA_BASE_URL/v1/api-keys" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "label": "ci-pipeline", "device_limit": 2 }'

curl -sS -X DELETE "$ALGENTA_BASE_URL/v1/api-keys/$KEY_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}
{% endtabs %}

## Related references

{% content-ref url="../authentication.md" %}
[authentication.md](../authentication.md)
{% endcontent-ref %}

{% content-ref url="../api/overview.md" %}
[overview.md](../api/overview.md)
{% endcontent-ref %}

{% content-ref url="control-plane.md" %}
[control-plane.md](control-plane.md)
{% endcontent-ref %}
