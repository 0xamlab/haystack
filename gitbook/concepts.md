---
icon: diagram-project
description: The core Algenta model — one integrated engine, governed data, deterministic decisions, capability routing, and explicit deployment boundaries.
---

# Core concepts

Algenta is a governed decision engine exposed through one versioned HTTP contract. The Python SDK, TypeScript SDK, CLI, and MCP server are clients of that contract. The deployment owns the compiled compute runtime; client users do not install or manage a separate engine component.

## Execution boundary

The public boundary is an Algenta base URL plus an API key:

| Target | Base URL | Who operates compute |
| --- | --- | --- |
| Algenta cloud | `https://api.algenta.ai` | Algenta |
| Self-hosted | your explicit deployment URL | your Algenta deployment |

Self-hosted clients must receive an explicit private base URL. A private deployment does not silently send work to Algenta cloud. The same `/v1` request and response schemas apply to both targets.

{% hint style="info" %}
The Python package is `algenta-sdk` and imports as `decision_engine`. The TypeScript package is `algenta-sdk`. Both call the integrated Algenta service; neither requires Mojo or worker setup.
{% endhint %}

## Governed data

Data moves through a deliberate lifecycle:

1. **Connect** a database, warehouse, object store, API, file, or repository.
2. **Verify** credentials once and persist the connector state.
3. **Onboard** a table, query, or object as a dataset.
4. **Resolve** structured intent against the known schema.
5. **Query** the validated plan and receive result metadata.

The engine does not guess missing identifiers or execute free-form SQL by default. A governed result carries evidence such as a schema revision, plan hash, validation state, and request id.

## Capability plane

The capability plane catalogs executable resources independently of the client using them.

| Kind | Meaning |
| --- | --- |
| `dataset` | A governed data source. |
| `skill` | A reusable instruction or callable behavior. |
| `mcp_tool` | A tool exposed by an MCP provider. |
| `runtime_library` | A compiled function owned by the Algenta deployment. |

The core operations are discover, route, and execute. Every capability declares an `execution_owner`:

| Owner | Contract |
| --- | --- |
| `algenta_managed` | Executes inside the selected Algenta deployment. |
| `client_managed` | Executes only through a customer-registered adapter or provider. |

If no valid owner or adapter exists, execution fails explicitly. Algenta does not invent an executor or report a silent success.

## Decisions and simulations

Simulations evaluate a typed scenario with an explicit run count and seed. Decision routes add options, constraints, confidence, risk, and a ranked recommendation. Agent runs add persisted steps, checkpoints, events, and approval gates around longer workflows.

These surfaces share the same controls:

* schema validation before execution;
* authorization and organization scope;
* deterministic compute for the same input, seed, and engine version;
* structured errors instead of hidden fallback;
* request and evidence identifiers for audit.

## Integrated runtime

The control plane handles validation, security, connectors, and persistence. The bundled compiled runtime handles numerical kernels. Algenta keeps workers warm inside the deployment and supervises their lifecycle. A missing or invalid runtime is a deployment failure, not a user setup step and not a reason to switch to Python compute.

Use `GET /v1/infrastructure` with an API key to execute the supported compute probe. A healthy primary node reports `status: "live"` and `engine_mode: "binary"`.

## Privacy profiles

`ALGENTA_DEPLOYMENT_MODE` selects the deployment privacy policy. `self_hosted` and `air_gapped` disable Algenta-cloud execution and apply fail-closed egress controls. Customer connectors and operator services must be explicitly configured and, under strict profiles, allowlisted.

Telemetry and metering modes are independent of compute. A private deployment can retain local audit records without sending them to a control plane.

## Where to go next

{% content-ref url="guides/connect-data.md" %}
[guides/connect-data.md](guides/connect-data.md)
{% endcontent-ref %}

{% content-ref url="guides/run-a-decision.md" %}
[guides/run-a-decision.md](guides/run-a-decision.md)
{% endcontent-ref %}

{% content-ref url="engine/bundled-runtime.md" %}
[engine/bundled-runtime.md](engine/bundled-runtime.md)
{% endcontent-ref %}

{% content-ref url="concepts/deployment-modes.md" %}
[concepts/deployment-modes.md](concepts/deployment-modes.md)
{% endcontent-ref %}
