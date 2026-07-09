---
icon: diagram-project
description: MCP reference for Algenta's capability plane — list providers and bindings, discover and test them, route an objective, execute a capability, and manage skills.
---

# Capability plane MCP tools

The capability plane is Algenta's unified surface over every kind of capability — datasets, MCP tools and resources, prompt-skills, native tools, and runtime libraries — regardless of who provides them. These tools let an MCP client enumerate providers, create and test bindings, route an objective to the best capability with fallbacks, execute a capability, and manage skills. Each tool wraps a single authenticated `/v1/capabilit*` endpoint.

Configure `algenta-mcp` first — see [MCP server](../sdk/mcp.md). For the concepts behind providers, bindings, and execution ownership, see [The capability plane](../concepts/capability-plane.md).

{% hint style="info" %}
The core loop is **route → execute**: `route_capabilities` returns the best capability and its authoritative `execution_owner`, and `execute_capability` runs it. Only `algenta_managed` routes execute server-side; `client_managed` routes must run in your own app or adapter.
{% endhint %}

## Providers and bindings

| Tool | What it does | Key inputs |
|------|--------------|------------|
| `list_capability_providers` | List unified providers across data, MCP, skills, native tools, and runtime libraries. | _(none)_ |
| `list_capability_bindings` | List bindings for the current organization. | `provider_id`, `scope` (`user`\|`workspace`\|`organization`) |
| `create_capability_binding` | Create one binding for a provider/profile pair. | `provider_id`, `profile_id`, `binding_name` (required); `scope`, `scope_ref`, `execution_owner` (`algenta_managed`\|`client_managed`), `config`, `customer_metadata` |
| `test_capability_binding` | Test a saved binding, or preview-test an unsaved one. | `binding_id` (saved) **or** `provider_id`+`profile_id`+`config` (preview); `scope`, `scope_ref`, `execution_owner`, `customer_metadata` |
| `discover_capability_binding` | Discover the capabilities a binding exposes, or preview-discover an unsaved one. | `binding_id` (saved) **or** `provider_id`+`profile_id`+`config` (preview); `scope`, `scope_ref`, `execution_owner`, `customer_metadata` |

## Capabilities

| Tool | What it does | Key inputs |
|------|--------------|------------|
| `list_capabilities` | List unified capabilities, filtered by kind, provider, or binding. | `kinds` (`dataset`, `mcp_tool`, `mcp_resource`, `mcp_prompt`, `skill`, `native_tool`, `runtime_library`), `provider_ids`, `binding_ids` |
| `get_capability` | Get one capability by id. | `capability_id` (required); `include_instruction` |
| `route_capabilities` | Route an objective to the best capability with fallbacks and an authoritative `execution_owner`. | `objective` (required); `binding_ids`, `provider_ids`, `kinds`, `execution_owners`, `artifact_affinities`, `tags`, `max_fallbacks` (0–10) |
| `execute_capability` | Execute one routed or known `algenta_managed` capability by id. | `capability_id` (required); `binding_id`, `input`, `request_id` |

## Skills

| Tool | What it does | Key inputs |
|------|--------------|------------|
| `list_skills` | List skill capabilities from the plane. | _(none)_ |
| `enable_skill` | Enable one prompt-skill as a first-class capability binding. | `skill_name`, `instruction` (required); `description`, `tags`, `artifact_affinities`, `execution_owner` |
| `disable_skill` | Disable one skill binding by id. | `binding_id` (required) |

## Endpoint mapping

| Tool | Method | Endpoint |
|------|--------|----------|
| `list_capability_providers` | `GET` | `/v1/capability-providers` |
| `list_capability_bindings` | `GET` | `/v1/capability-bindings` |
| `create_capability_binding` | `POST` | `/v1/capability-bindings` |
| `test_capability_binding` | `POST` | `/v1/capability-bindings/{binding_id}/test` or `/v1/capability-bindings/test` |
| `discover_capability_binding` | `POST` | `/v1/capability-bindings/{binding_id}/discover` or `/v1/capability-bindings/discover` |
| `list_capabilities` | `GET` | `/v1/capabilities` |
| `get_capability` | `GET` | `/v1/capabilities/{capability_id}` |
| `route_capabilities` | `POST` | `/v1/capabilities/route` |
| `execute_capability` | `POST` | `/v1/capabilities/execute` |
| `list_skills` | `GET` | `/v1/capabilities?kinds=skill` |
| `enable_skill` | `POST` | `/v1/capability-bindings` (then discover) |
| `disable_skill` | `DELETE` | `/v1/capability-bindings/{binding_id}` |

## Worked examples

### Enumerate what is available

Start with the providers on the instance, then narrow to concrete capabilities by kind.

{% code title="list_capability_providers (tool call)" %}
```json
{ "name": "list_capability_providers", "arguments": {} }
```
{% endcode %}

{% code title="list_capabilities (tool call)" %}
```json
{
  "name": "list_capabilities",
  "arguments": {
    "kinds": ["mcp_tool", "dataset"]
  }
}
```
{% endcode %}

```bash
curl -sS "$ALGENTA_BASE_URL/v1/capabilities?kinds=mcp_tool&kinds=dataset" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" | jq '.capabilities[].capability_id'
```

### Route an objective, then execute it

`route_capabilities` returns a ranked capability plus fallbacks and the authoritative `execution_owner`. If that owner is `algenta_managed`, run it with `execute_capability`.

{% code title="route_capabilities (tool call)" %}
```json
{
  "name": "route_capabilities",
  "arguments": {
    "objective": "summarize the latest churn report",
    "kinds": ["skill", "mcp_tool"],
    "max_fallbacks": 2
  }
}
```
{% endcode %}

{% code title="execute_capability (tool call)" %}
```json
{
  "name": "execute_capability",
  "arguments": {
    "capability_id": "$CAPABILITY_ID",
    "input": { "period": "2026-Q2" }
  }
}
```
{% endcode %}

```bash
curl -sS "$ALGENTA_BASE_URL/v1/capabilities/execute" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "capability_id": "$CAPABILITY_ID", "input": { "period": "2026-Q2" } }'
```

{% hint style="warning" %}
`execute_capability` runs only `algenta_managed` routes server-side. A `client_managed` route is returned by `route_capabilities` for you to execute in your own app or adapter path — the engine will not run it on your behalf.
{% endhint %}

### Enable a prompt-skill

Register an instruction-only skill as a first-class capability binding, then let routing pick it up.

{% code title="enable_skill (tool call)" %}
```json
{
  "name": "enable_skill",
  "arguments": {
    "skill_name": "Executive summary",
    "instruction": "Summarize the input into five crisp bullet points for an executive audience.",
    "tags": ["summarization", "reporting"]
  }
}
```
{% endcode %}

Disable it later with `disable_skill` and the returned `$BINDING_ID`.

## Related pages

{% content-ref url="../concepts/capability-plane.md" %}
[capability-plane.md](../concepts/capability-plane.md)
{% endcontent-ref %}

{% content-ref url="../guides/capabilities.md" %}
[capabilities.md](../guides/capabilities.md)
{% endcontent-ref %}

{% content-ref url="../api/reference.md" %}
[reference.md](../api/reference.md)
{% endcontent-ref %}
