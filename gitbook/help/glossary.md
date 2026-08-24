---
icon: book-bookmark
description: Every Algenta term in one place — the engine, the surfaces, decisioning, governed data, agentic runs, deployment, and licensing vocabulary, each defined once.
---

# Glossary

The canonical vocabulary for Algenta. Each term is defined once here; the rest of the docs use these words exactly. If a page and this glossary ever disagree, the glossary wins.

## The engine

| Term | Meaning |
| --- | --- |
| **Engine** | The Algenta core — a deterministic computational-intelligence runtime (math/operational libraries, simulation, decision planning, governed query, agent runtime). You deploy it; you don't adopt it as a finished app. |
| **Runtime** | The compiled compute capability integrated into an Algenta deployment. |
| **Mojo engine** | Algenta's compiled, high-performance numerical runtime. |
| **Bundled runtime** | The signed compiled compute component included with Algenta and supervised as part of the service. Users do not install or manage it separately. |
| **Decision envelope** | The structured result of a simulation or decision — expected value, confidence, percentiles, and a recommended action. |
| **Determinism** | The same inputs + `seed` always produce the same result. Algenta computation is reproducible by design. |

## Surfaces — how you reach the engine

| Term | Meaning |
| --- | --- |
| **HTTP API** | The versioned REST surface under `/v1`. The default integration path; no SDK required. See [API overview](../api/overview.md). |
| **SDK** (`algenta-sdk`) | The published Python HTTP client (`decision_engine.AlgentaClient`) and TypeScript/JavaScript client (`AlgentaClient`) for the API. See [Python SDK](../sdk/python.md) and [TypeScript SDK](../sdk/typescript.md). |
| **MCP server** (`algenta-mcp`) | A Model Context Protocol bridge that exposes the engine as tools for Cursor, Claude Desktop, and other AI clients. See [MCP server](../sdk/mcp.md). |
| **CLI** | The `de` terminal client for the Algenta HTTP API. See [CLI reference](../cli.md). |

## Decisioning

| Term | Meaning |
| --- | --- |
| **Simulation** | A Monte Carlo run over a scenario that returns a decision envelope (`POST /v1/simulate`). |
| **Distribution** | The probabilistic shape of an input variable (for example normal, lognormal, triangular, beta, poisson). |
| **Decision** | A single recommended action plus its expected value and confidence. |
| **Recommendation / Score / Compare** | Decision primitives: rank actions, score one scenario, or compare alternatives. |
| **Decision plan** | A structured, multi-stage decision the engine produces and can later execute. |
| **Decision memory** | The persisted log of decisions and their later real-world **outcomes**, so models can learn from results. |
| **What-if** | Sensitivity analysis that varies inputs to see how the decision changes (`POST /v1/simulate/what-if`). |

## Governed data

| Term | Meaning |
| --- | --- |
| **Governed data** | Data the engine queries under a typed, validated contract — schema-checked, with explicit field hints and operators — so results are deterministic and auditable. |
| **Source** | A registered, queryable data origin (schema-inferred and tracked in the source registry). |
| **Dataset** | An onboarded, engine-managed table you can summarize and query. |
| **Connector** | A configured connection to an external system (SQL, warehouse, REST, file) that backs a source or dataset. |
| **Query / Resolve** | A deterministic exact query (`POST /v1/query`) and the plan-resolution step that precedes it. |
| **Capability plane** | The unified router that turns an objective into the right provider/skill and executes it. |
| **Capability / Skill** | A discrete operation the capability plane can route to and execute (an LLM call, an optimizer, a data operation). |

## Agentic

| Term | Meaning |
| --- | --- |
| **Agent run** | A persisted, observable agent execution with events, checkpoints, telemetry, approval gates, and lifecycle control. |
| **Checkpoint** | Saved agent state you can pause at, resume from, or replay. |
| **Repository intelligence** | The code-aware workflow: snapshot a repo, triage an issue, plan, simulate a patch, and apply a fix/PR. |
| **Blast radius** | The set of files and symbols transitively affected by a change — what depends on it. Drives graph queries, patch-apply gating, and adaptive CI scan scoping. |
| **Adaptive security scanning** | CI security analysis scoped by blast radius: skip, differential (scoped to the change's closure), or full. See [Adaptive security scanning](../guides/adaptive-security-scanning.md). |
| **Async job** | A long-running execution submitted to `/v1/jobs`, polled for status, and fetched on completion. |
| **Trigger** | A registered condition that fires an action (a webhook-driven automation). |

## Deploy & operate

| Term | Meaning |
| --- | --- |
| **Deployment mode** | The privacy/egress profile: `saas`, `vpc`, `self_hosted`, `air_gapped`, or `hybrid_provider`. Set with `ALGENTA_DEPLOYMENT_MODE`. |
| **Self-hosted** | You run the full stack (API + worker + engine + Postgres + Redis + object storage) on your own infrastructure. See [Self-hosting](../self-hosting.md). |
| **Air-gapped** | A self-hosted profile with zero outbound network — licensing and execution are fully local. |
| **Control plane** | The hosted, engine-free surface (auth, accounts, teams, billing, licensing). A deployment runs `full` or `control_plane` via `ALGENTA_SERVICE_ROLE`. |
| **Edition** | A licensed product surface over the engine, selected with `ALGENTA_PRODUCT`. |
| **Metering / Credits / Quota** | Generic managed-runtime compatibility controls. Algenta editions do not use them for billing or execution caps; local activity records remain customer-owned. See [Usage & execution policy](../billing.md). |
| **Egress / Privacy report** | Outbound-network policy and the operator proof (`GET /v1/admin/privacy-report`) that a deployment is cloud-free. |

## Security & licensing

| Term | Meaning |
| --- | --- |
| **API key** | The bearer credential (`Authorization: Bearer …`) that authenticates requests. See [Authentication](../authentication.md). |
| **Device binding** | Binding a capped key to a specific device identity, enforced by fingerprint headers + a replay token. |
| **License** | A signed, offline-verifiable JWT (RS256) that grants product entitlements and capacity. Always v2. See [Licensing](../licensing.md). |
| **Entitlement** | What a license grants — products, features, and capacity caps (seats, nodes, workers). |
| **BYOK** | Bring Your Own Keys — your own provider credentials for LLM/AI capabilities, encrypted per tenant. |
| **Execution ownership** | Who runs a capability: `algenta_managed` (the engine) vs `client_managed` (your adapter). Fail-closed when unresolved. |

## Related

{% content-ref url="../concepts.md" %}
[concepts.md](../concepts.md)
{% endcontent-ref %}

{% content-ref url="../overview.md" %}
[overview.md](../overview.md)
{% endcontent-ref %}
