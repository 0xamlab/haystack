---
icon: puzzle-piece
description: Register capability providers, create and test bindings, discover and authorize capabilities, and enable skills — the setup layer behind the Algenta capability plane.
---

# Register capability providers and bindings

A **binding** is the connective tissue of the [capability plane](../concepts/capability-plane.md): it wires one *provider profile* (an MCP server, a skill pack, a data connector, a native tool pack, a runtime library) to your organization, holds the encrypted config, and produces the capabilities you can route and execute. This guide covers the setup layer — list providers, create a binding, test and discover its capabilities, authorize it, enable skills, and find external MCP providers. Once a binding is `ready`, use [Route and execute capabilities](capabilities.md) to run its capabilities.

You need an API key (see [Authentication](../authentication.md)) exported as `$ALGENTA_API_KEY`, and a running engine — the hosted API at `https://api.algenta.ai` or a self-hosted server at `http://localhost:8000`. Every route below lives under `/v1/capability-providers`, `/v1/capability-bindings`, and `/v1/capabilities`.

{% hint style="info" %}
Every binding carries a **status** (`unconfigured` → `authorizing` → `ready`, or `degraded` / `quarantined`) and an **execution owner** (`algenta_managed` — the engine runs it — or `client_managed` — your own adapter runs it). Discovery and execution fail closed when a binding is quarantined or ownership cannot be resolved. See [Execution ownership](../concepts/execution-ownership.md).
{% endhint %}

## Before you start

A **provider** groups one or more profiles by type. `provider_type` is one of:

| `provider_type` | What it is |
| --- | --- |
| `data_connector` | A connected data source (database, warehouse, REST API). |
| `mcp_provider` | An external Model Context Protocol server. |
| `skill_pack` | Prompt-skills enabled as first-class capabilities. |
| `native_tool_pack` | Built-in engine tools. |
| `runtime_library_pack` | Runtime-library operations. |

A binding is created at one **scope** — `user`, `workspace` (default), or `organization` — which controls who can see and route to its capabilities.

## The binding lifecycle

{% stepper %}
{% step %}
### List the providers available to your org

`GET /v1/capability-providers` returns every provider visible to your org, each with its `provider_type`, `active` flag, `supported_execution_owners`, and the `profiles` you can bind against. Note the `provider_id` and a `profile_id` you want to use.

{% tabs %}
{% tab title="cURL" %}
```bash title="list providers"
curl -sS "https://api.algenta.ai/v1/capability-providers" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Python" %}
```python title="list_providers.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

for provider in client.list_capability_providers():
    print(provider.provider_id, provider.provider_type, provider.active)
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="listProviders.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({ apiKey: process.env.ALGENTA_API_KEY });

const providers = await client.listCapabilityProviders();
for (const p of providers) {
  console.log(p.provider_id, p.provider_type, p.active);
}
```
{% endtab %}
{% endtabs %}
{% endstep %}

{% step %}
### Create a binding

`POST /v1/capability-bindings` binds a `provider_id` + `profile_id` pair to your org. `binding_name` is required; `scope` defaults to `workspace`; `execution_owner`, `scope_ref`, `config`, and `customer_metadata` are optional. Any credential in `config` is encrypted at rest and never returned. The example wires a generic external MCP server (see [Connect an external MCP server](external-mcp.md) for MCP-specific config).

{% tabs %}
{% tab title="cURL" %}
```bash title="create a binding"
curl -sS -X POST "https://api.algenta.ai/v1/capability-bindings" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "provider.mcp.generic",
    "profile_id": "profile.mcp.workspace",
    "binding_name": "Acme tools",
    "scope": "workspace",
    "execution_owner": "algenta_managed",
    "config": {
      "server_url": "https://mcp.acme.internal/mcp",
      "auth": {"type": "bearer", "token": "'"$ACME_MCP_TOKEN"'"}
    }
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="create_binding.py"
import os, requests

resp = requests.post(
    "https://api.algenta.ai/v1/capability-bindings",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "provider_id": "provider.mcp.generic",
        "profile_id": "profile.mcp.workspace",
        "binding_name": "Acme tools",
        "scope": "workspace",
        "execution_owner": "algenta_managed",
        "config": {
            "server_url": "https://mcp.acme.internal/mcp",
            "auth": {"type": "bearer", "token": os.environ["ACME_MCP_TOKEN"]},
        },
    },
)
binding = resp.json()
print(binding["binding_id"], binding["status"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="createBinding.ts"
const binding = await client.createCapabilityBinding({
  provider_id: "provider.mcp.generic",
  profile_id: "profile.mcp.workspace",
  binding_name: "Acme tools",
  scope: "workspace",
  execution_owner: "algenta_managed",
  config: {
    server_url: "https://mcp.acme.internal/mcp",
    auth: { type: "bearer", token: process.env.ACME_MCP_TOKEN },
  },
});
console.log(binding.binding_id, binding.status);
```
{% endtab %}
{% endtabs %}

The `201` response carries the `binding_id`, its `status`, `execution_owner`, and `scope_ref`. Export the id as `$BINDING_ID` for the next steps.
{% endstep %}

{% step %}
### Test the binding

`POST /v1/capability-bindings/{binding_id}/test` verifies connectivity for a saved binding. To validate config *before* saving, `POST /v1/capability-bindings/test` with the same body you would pass to create (a preview test).

{% tabs %}
{% tab title="cURL" %}
```bash title="test a saved binding"
curl -sS -X POST "https://api.algenta.ai/v1/capability-bindings/$BINDING_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Python" %}
```python title="test_binding.py"
import os, requests

resp = requests.post(
    f"https://api.algenta.ai/v1/capability-bindings/{os.environ['BINDING_ID']}/test",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
)
result = resp.json()
print(result["success"], result["binding_status"], result.get("latency_ms"))
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="testBinding.ts"
const result = await client.testCapabilityBinding(process.env.BINDING_ID!);
console.log(result.success, result.binding_status, result.latency_ms);
```
{% endtab %}
{% endtabs %}

The result reports `success`, the resulting `binding_status`, a `message`, an optional `latency_ms`, and a `details` object.
{% endstep %}

{% step %}
### Discover its capabilities

`POST /v1/capability-bindings/{binding_id}/discover` connects to the provider, enumerates what it offers, and writes each item into the unified catalog. A preview form (`POST /v1/capability-bindings/discover`) discovers against an unsaved binding config.

{% tabs %}
{% tab title="cURL" %}
```bash title="discover capabilities"
curl -sS -X POST "https://api.algenta.ai/v1/capability-bindings/$BINDING_ID/discover" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Python" %}
```python title="discover.py"
import os, requests

resp = requests.post(
    f"https://api.algenta.ai/v1/capability-bindings/{os.environ['BINDING_ID']}/discover",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
)
data = resp.json()
print(data["capability_count"], data["binding_status"])
for cap in data["capabilities"]:
    print(cap["capability_id"], cap["kind"], cap["name"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="discover.ts"
const data = await client.discoverCapabilityBinding(process.env.BINDING_ID!);
console.log(data.capability_count, data.binding_status);
for (const cap of data.capabilities) {
  console.log(cap.capability_id, cap.kind, cap.name);
}
```
{% endtab %}
{% endtabs %}

The response returns `capability_count`, a `manifest_hash`, `discovered_at`, and a `capabilities[]` array of catalog entries (`capability_id`, `kind`, `name`, `execution_owner`, `approval_required`, `binding_status`, …). Each `kind` is one of `dataset`, `mcp_tool`, `mcp_resource`, `mcp_prompt`, `skill`, `native_tool`, or `runtime_library`.
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — the binding reports `status: "ready"`, the test returns `success: true`, and discovery returns a non-zero `capability_count`. Confirm the new capabilities appear in `GET /v1/capabilities?binding_ids=$BINDING_ID`.
{% endhint %}

## Authorize an OAuth-style binding

Providers that require a delegated grant move to `status: "authorizing"` until you complete an authorization handshake. Start it, send the user to the returned `authorize_url`, then complete it with the callback.

{% code title="start then complete authorization" %}
```bash
# 1. Start — returns a session_id and an authorize_url to send the user to.
curl -sS -X POST "https://api.algenta.ai/v1/capability-bindings/$BINDING_ID/authorize/start" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"redirect_uri": "https://app.example.com/callback", "requested_scopes": ["read"]}'

# 2. Complete — pass the session_id plus the provider callback.
curl -sS -X POST "https://api.algenta.ai/v1/capability-bindings/$BINDING_ID/authorize/complete" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "'"$SESSION_ID"'", "authorization_code": "the-code", "state": "the-state"}'
```
{% endcode %}

The start response carries `session_id`, `authorize_url`, `expires_at`, and `requested_scopes`. The complete response returns the final `status` and, on success, `authorized_at`. In the SDK these are `startCapabilityAuthorization(bindingId, request)` and `completeCapabilityAuthorization(request)`.

## Manage bindings

`GET /v1/capability-bindings` lists your bindings and accepts optional `provider_id` and `scope` filters. `GET`, `PATCH`, and `DELETE` on `/{binding_id}` read, update, and remove one.

{% code title="list, update, delete a binding" %}
```bash
# List, filtered by provider and scope.
curl -sS "https://api.algenta.ai/v1/capability-bindings?provider_id=provider.mcp.generic&scope=workspace" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"

# Read one.
curl -sS "https://api.algenta.ai/v1/capability-bindings/$BINDING_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"

# Partial update — only supplied fields change.
curl -sS -X PATCH "https://api.algenta.ai/v1/capability-bindings/$BINDING_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"binding_name": "Acme tools (prod)", "status": "ready"}'

# Remove it — returns 204 No Content.
curl -sS -X DELETE "https://api.algenta.ai/v1/capability-bindings/$BINDING_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endcode %}

## Enable and disable skills

A **skill** is a prompt-instruction registered as a first-class capability. List the skills your org has with `GET /v1/capabilities?kinds=skill`. Enabling a skill creates a `skill_pack` binding and discovers it in one motion; disabling it deletes that binding.

{% tabs %}
{% tab title="cURL" %}
```bash title="enable then disable a skill"
# Enable: create a skill_pack binding whose config carries the instruction, then discover it.
BINDING_ID=$(curl -sS -X POST "https://api.algenta.ai/v1/capability-bindings" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "provider.skill_pack.algenta",
    "profile_id": "profile.skill_pack.user",
    "binding_name": "summarize-incident",
    "scope": "user",
    "execution_owner": "client_managed",
    "config": {"manifest": {"capabilities": [{
      "capability_id": "cap.skill.summarize_incident",
      "name": "summarize-incident",
      "kind": "skill",
      "implementation_kind": "instruction_only",
      "execution_owner": "client_managed",
      "instruction": "Summarize the incident report into five bullet points.",
      "replayability": "deterministic"
    }]}}
  }' | jq -r .binding_id)

curl -sS -X POST "https://api.algenta.ai/v1/capability-bindings/$BINDING_ID/discover" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"

# Disable: delete the skill binding.
curl -sS -X DELETE "https://api.algenta.ai/v1/capability-bindings/$BINDING_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Python" %}
```python title="list_skills.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

# List the skill capabilities your org can route to.
for skill in client.list_skills():
    print(skill.capability_id, skill.name)
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="skills.ts"
// The SDK wraps the create-binding + discover / delete flow in helpers.
const enabled = await client.enableSkill({
  skill_name: "summarize-incident",
  instruction: "Summarize the incident report into five bullet points.",
  execution_owner: "client_managed",
});

const skills = await client.listSkills();
console.log(skills.map((s) => s.capability_id));

await client.disableSkill(enabled.binding_id);
```
{% endtab %}
{% endtabs %}

## List external MCP providers

External MCP servers appear in the provider list with `provider_type: "mcp_provider"`. Fetch `GET /v1/capability-providers` and filter for that type; the TypeScript SDK exposes `listMcpProviders()` as a convenience.

{% tabs %}
{% tab title="cURL" %}
```bash title="filter MCP providers"
curl -sS "https://api.algenta.ai/v1/capability-providers" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  | jq '[.[] | select(.provider_type == "mcp_provider")]'
```
{% endtab %}

{% tab title="Python" %}
```python title="mcp_providers.py"
mcp = [p for p in client.list_capability_providers()
       if p.provider_type == "mcp_provider"]
print([p.provider_id for p in mcp])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="mcpProviders.ts"
const mcp = await client.listMcpProviders();
console.log(mcp.map((p) => p.provider_id));
```
{% endtab %}
{% endtabs %}

## Route and execute what you bound

Once a binding is `ready` and its capabilities are discovered, hand the engine an objective and let it pick and run one: `POST /v1/capabilities/route` returns a plan and `POST /v1/capabilities/execute` runs it. The full flow — with fallbacks, approval gates, and execution ownership — is covered in [Route and execute capabilities](capabilities.md).

## Troubleshooting

{% hint style="warning" %}
**Discovery returns `403` or the binding goes `quarantined`.** The provider host is not permitted by your egress policy, or credentials are stale. On a self-hosted or air-gapped deployment the host must be allowlisted; link-local / metadata addresses are always blocked. See [Run air-gapped](air-gapped.md) and [API errors](../api/errors.md).
{% endhint %}

{% hint style="info" %}
**A binding stays `authorizing`.** It needs the OAuth-style handshake completed. Run `authorize/start`, send the user to the `authorize_url`, then `authorize/complete` with the returned `session_id`.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Route and execute capabilities</strong></td><td>Turn an objective into one running capability, with fallbacks and ownership.</td><td><a href="capabilities.md">capabilities.md</a></td></tr>
<tr><td><strong>Connect an external MCP server</strong></td><td>Register an MCP server and proxy its tools through the plane.</td><td><a href="external-mcp.md">external-mcp.md</a></td></tr>
<tr><td><strong>The capability plane</strong></td><td>How providers, bindings, and capabilities fit together.</td><td><a href="../concepts/capability-plane.md">../concepts/capability-plane.md</a></td></tr>
</tbody></table>
