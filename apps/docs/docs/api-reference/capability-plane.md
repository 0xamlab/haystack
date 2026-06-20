---
sidebar_position: 6
---

# Capability Plane

Use the capability plane when you want one customer-agnostic control surface
across governed datasets, MCP providers, prompt-skills, native tools, and
runtime libraries.

- Cloud Managed: `https://api.algenta.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Algenta cloud.

The capability plane is the canonical route-selection layer above the existing
connector and governed data surfaces. It does not replace `/v1/data`,
`/v1/query`, or `/v1/query/sql-report`; it decides which governed or tool path
should own the request first.

## Primary endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/capability-providers` | List provider families across connectors, MCP, skills, native tools, and runtime libraries |
| `GET` | `/v1/capability-providers/{provider_id}` | Inspect one provider, profile, auth, and policy summary |
| `GET` | `/v1/capability-bindings` | List configured capability bindings |
| `POST` | `/v1/capability-bindings` | Create one provider binding |
| `POST` | `/v1/capability-bindings/discover` | Preview discovery without saving a binding |
| `POST` | `/v1/capability-bindings/{binding_id}/discover` | Persist one discovery snapshot |
| `GET` | `/v1/capabilities` | List discovered capabilities across all bound providers |
| `GET` | `/v1/capabilities/{capability_id}` | Inspect one capability, including instruction artifacts when requested |
| `POST` | `/v1/capabilities/route` | Select the governed capability that should own one objective |
| `POST` | `/v1/capabilities/execute` | Execute one Algenta-managed capability |
| `POST` | `/v1/capabilities/outcomes` | Record the observed outcome after execution or handoff |

## Route contract

`POST /v1/capabilities/route` returns the canonical route plan fields:

- `selected_capability_id`
- `selected_provider_id`
- `selected_binding_id`
- `kind`
- `execution_owner`
- `requires_approval`
- `confidence`
- `reason`
- `fallbacks[]`
- `policy_snapshot_id`
- `selected_tool_name` or `instruction_artifact_ref`

Use that response before generic tool planning or app-specific branching.

## Execution owner rules

- `algenta_managed` means Algenta owns the execution path and may return a
  direct execution response from `POST /v1/capabilities/execute`
- `client_managed` means the customer app must execute the selected capability
  through its own adapter or execution node
- execution ownership is authoritative and does not silently fall back across
  ownership modes

## Checked-in examples

Use the checked-in request artifacts in
[`examples/capability-plane/README.md`](/Users/angel/Developer/decision-engine/examples/capability-plane/README.md):

- `binding_create_request.json`
- `binding_discover_request.json`
- `capability_route_request.json`
- `capability_execute_request.json`
- `capability_outcome_request.json`

For a LangGraph router example that uses this contract before branching, see
[`examples/langgraph/capability_router.py`](/Users/angel/Developer/decision-engine/examples/langgraph/capability_router.py).

## SDK, CLI, and MCP surfaces

- Python SDK: `client.list_capability_providers()`, `client.route_capabilities(...)`, `client.execute_capability(...)`
- TypeScript SDK: `client.listCapabilityProviders()`, `client.routeCapabilities(...)`, `client.executeCapability(...)`
- CLI: `de capabilities providers`, `de capabilities route <request.json>`, `de capabilities execute <request.json>`
- MCP: `list_capability_providers`, `list_capabilities`, `route_capabilities`, `execute_capability`

For the focused repo-level verification bundle, run `make capability-plane-verify`.

For the machine-readable discovery contract, start with `GET /v1/meta/contract`.
