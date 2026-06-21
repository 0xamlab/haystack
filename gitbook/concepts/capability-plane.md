---
icon: diagram-project
description: The unified router that turns an objective into the right provider and skill, then executes it — discovery, routing, execution, adapters, and fail-closed execution ownership.
---

# The capability plane

The capability plane is the unified router that turns an **objective** into one concrete **capability** — a discrete operation backed by a provider and a binding — and then executes it. It is the single seam over governed data, MCP tools and prompts, skills, native tools, and Algenta runtime libraries: instead of integrating each provider by hand, you register a binding, let the plane discover what it exposes, ask it to route an objective to the best capability, and execute through one contract. Every operation is org-scoped and authenticated.

## Why it exists

Without a router, every caller has to know which provider does what, how each one authenticates, and who actually runs the work. The capability plane collapses that into four stages with one vocabulary:

1. **Discovery** — a binding (a configured connection to a provider) is probed, and the tools, prompts, resources, datasets, or library functions it exposes are persisted into a unified catalog as `CapabilityCatalogEntry` records.
2. **Routing** — `POST /v1/capabilities/route` scores catalog entries against an `objective` (token overlap, binding readiness, requested tags, artifact affinities, and historical outcomes) and returns one selected capability plus ranked fallbacks. Quarantined bindings are excluded.
3. **Execution** — `POST /v1/capabilities/execute` runs the selected capability and returns an execution session with `status`, `output` or `error`, and timing.
4. **Adapters** — capabilities the engine cannot run server-side are handed back to a caller-provided adapter rather than run on a wrong path.

The result is that a planner can express intent ("summarize this dataset", "call this tool") and let the plane resolve the provider, the credentials, and the executor.

## Execution ownership

Every capability carries an **execution owner** that decides who actually runs it:

| Owner | Meaning | What execute does |
| --- | --- | --- |
| `algenta_managed` | The engine runs it server-side (governed datasets, Algenta runtime libraries, and instruction-only skill/prompt/resource records). | Executes and returns `status: succeeded` with `output`. |
| `client_managed` | Your own adapter runs it (typically MCP tools and native tools that call out to your systems). | Records a **failed** session with error code `client_managed_capability_requires_adapter` — the plane will not run it for you. |

This split is **fail-closed**. If a capability is `client_managed`, `execute` does not attempt a best-effort call; it returns a failed execution session telling you to run it through your adapter (use the route plan plus your execution node). If a capability is `algenta_managed` but its kind has no server-side path yet, `execute` fails with `algenta_managed_capability_not_executable` instead of guessing. Ownership is never silently inferred at run time — it comes from the capability's stored `execution_owner`, defaulting to `client_managed` when a provider does not declare a managed path.

{% hint style="warning" %}
Fail-closed is the point: an unresolved or unsupported execution path surfaces as an explicit error, not a silent fallback. A planner can react to the error code, not discover later that work ran somewhere unexpected.
{% endhint %}

## Providers

A **provider** is a class of capability source. The plane ships with a fixed set of provider types, each declaring which execution owners it supports:

| Provider type | Capability kinds | Supported owners |
| --- | --- | --- |
| `data_connector` | `dataset` | `algenta_managed` |
| `runtime_library_pack` | `runtime_library` | `algenta_managed` |
| `mcp_provider` | `mcp_tool`, `mcp_resource`, `mcp_prompt` | `algenta_managed`, `client_managed` |
| `skill_pack` | `skill` | `algenta_managed`, `client_managed` |
| `native_tool_pack` | `native_tool` | `algenta_managed`, `client_managed` |

`GET /v1/capability-providers` lists them; `GET /v1/capabilities` lists the discovered capabilities and accepts `kinds`, `provider_ids`, and `binding_ids` filters.

## BYOK and provider keys

Customer-registered providers (MCP, native tools) authenticate through their **binding** configuration. When a binding config carries credentials — fields such as `api_key`, `access_token`, `client_secret`, `refresh_token`, `bearer_token`, or `password` — those values are encrypted at rest and redacted from responses, never returned in plaintext. This is the capability plane's expression of **BYOK** (Bring Your Own Keys): the provider credentials your bindings use are your own, scoped to your org, and held encrypted per tenant. Managed providers (governed data, runtime libraries) use `"type": "managed"` auth and need no caller-supplied key.

## A routing example

Route an objective, then execute the selected capability.

```bash title="Route, then execute"
# 1. Route an objective to one capability (plus ranked fallbacks)
curl -sS -X POST https://api.algenta.example/v1/capabilities/route \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"objective": "summarize the orders dataset", "max_fallbacks": 3}'

# 2. Execute the selected capability_id from the route plan
curl -sS -X POST https://api.algenta.example/v1/capabilities/execute \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"capability_id": "cap_orders_summary", "input": {"operation": "summary"}}'
```

A route plan names the choice and its alternatives:

```json title="CapabilityRoutePlan (shape)"
{
  "selected_capability_id": "cap_orders_summary",
  "selected_provider_id": "provider.data_connector_pack.algenta",
  "selected_binding_id": "bnd_workspace_governed_data",
  "kind": "dataset",
  "execution_owner": "algenta_managed",
  "requires_approval": false,
  "confidence": 0.41,
  "reason": "token overlap: dataset, orders, summarize; binding ready",
  "policy_snapshot_id": "capability-plane-policy-v1",
  "fallbacks": []
}
```

An execution returns a session you can record an outcome against (via `POST /v1/capabilities/outcomes`), which feeds the historical signal back into future routing scores.

## Use this when

* **You have intent, not an integration.** You know the objective but not which provider or tool should serve it — let `route` pick and rank.
* **You are building a planner or agent head.** Route to a capability, then either execute `algenta_managed` work in the engine or hand `client_managed` work to your adapter using the returned `execution_owner`.
* **You need an auditable choice.** The route plan records the selected capability, its confidence, a human-readable reason, and the `policy_snapshot_id` used.
* **You want one credential surface.** Register provider credentials once on a binding (encrypted, per tenant) instead of wiring secrets into each caller.
* **You must fail safe.** You want unresolved or unsupported execution to error explicitly rather than fall back to an unintended path.

{% hint style="info" %}
Governed datasets reached through the plane are the same governed data the engine queries elsewhere — the plane routes to them, it does not replace the typed query contract.
{% endhint %}

## Next

{% content-ref url="governed-data.md" %}
[governed-data.md](governed-data.md)
{% endcontent-ref %}

{% content-ref url="decision-memory.md" %}
[decision-memory.md](decision-memory.md)
{% endcontent-ref %}
