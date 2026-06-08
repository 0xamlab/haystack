---
sidebar_position: 1
---

# API Reference

Start with [Quickstart](/quickstart) if you are bringing up a self-hosted service for the first time.

**Base URL:** `https://api.algenta.ai`

- Cloud Managed: `https://api.algenta.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Algenta cloud.

**Authentication:** API requests require an API key via:

- `Authorization: Bearer <YOUR_ALGENTA_API_KEY>`
- `X-API-Key: <YOUR_ALGENTA_API_KEY>` for legacy `v1` compatibility only

The bearer examples above are Cloud Managed examples. In `self_hosted` and
`air_gapped`, use the API key provisioned by your self-hosted operator
deployment instead.

## First-run decision endpoints

These are the endpoints most users touch first after the service is running:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | [`/v1/simulate`](/api-reference/simulate) | Run a simulation |
| `POST` | `/v1/recommend` | Compare actions |
| `POST` | `/v1/score` | Score a scenario |
| `POST` | `/v1/batch` | Run multiple simulations |
| `POST` | `/v1/compare` | Compare named scenarios |
| `POST` | `/v1/jobs` | Submit async simulation job |
| `GET` | `/v1/jobs/{id}` | Poll job status |
| `GET` | `/v1/jobs/{id}/result` | Retrieve completed job result |

## Structured data runtime endpoints

These endpoints back the deterministic data/runtime surface after service install:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/sources/register` | Register a source in the Decision Intelligence Layer |
| `GET` | `/v1/meta/contract` | Fetch the machine-readable Algenta contract |
| `GET` | `/v1/data` | Discover authorized datasets with deterministic filters |
| `GET` | `/v1/data/{dataset_id}/summary` | Fetch a low-token dataset selection summary |
| `POST` | `/v1/resolve` | Resolve structured intent into an exact plan |
| `POST` | `/v1/verify` | Validate an exact plan before execution |
| `POST` | `/v1/query` | Execute a deterministic query |
| `POST` | `/v1/query/batch` | Execute multiple governed exact queries in one call |
| `POST` | `/v1/query/sql-report` | Execute a constrained read-only SQL report |

## Unified capability-plane endpoints

These endpoints sit above the governed data and tool surfaces and decide where
an objective should route first:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | [`/v1/capability-providers`](/api-reference/capability-plane) | List customer-agnostic provider families |
| `GET` | [`/v1/capabilities`](/api-reference/capability-plane) | List discovered capabilities across providers |
| `POST` | [`/v1/capabilities/route`](/api-reference/capability-plane) | Route one objective to the selected capability |
| `POST` | [`/v1/capabilities/execute`](/api-reference/capability-plane) | Execute one Algenta-managed capability |
| `POST` | [`/v1/capabilities/outcomes`](/api-reference/capability-plane) | Record the observed execution outcome |

## Runtime contract notes

- `/v1/resolve` is the planning boundary.
- `/v1/query` is execution-only and should be given an exact plan or a resolved plan.
- `/v1/verify` is the trust/introspection surface for plan validation.
- `/v1/data` plus `/v1/data/{dataset_id}/summary` is the low-token discovery path.
- `/v1/query/batch` keeps governed exact queries in one ordered response.
- `/v1/query/sql-report` is a separate read-only rowset surface, not metric inference.
- `/v1/capabilities/route` is the customer-agnostic route-selection surface above governed data, MCP, skills, native tools, and runtime libraries.
- `/v1/capabilities/execute` only runs `algenta_managed` capabilities and fails closed for `client_managed` paths.
- `/v1/query` and `/v1/query/batch` share the same deterministic filter contract:
  `time_filter` plus `conditions[]` with `eq`, `in`, `gt`, `gte`, `lt`, `lte`,
  `is_null`, and `is_not_null`.
- Those filters are **record predicates**, not SQL clauses. SQL backends may
  push them down, while Redis and other non-SQL sources may apply them after
  materializing normalized records. The public behavior stays the same.
- `/v1/meta/contract` is the live machine-readable contract endpoint for API, SDK, CLI, and MCP discovery.
- `primary_data_query_contract.governed_filter_contract` declares the selector fields, operator families, type behavior, and validation rules for that same database-agnostic filter model.
- The canonical OpenAPI document also publishes `x-canonical-mcp-endpoint` and `x-primary-data-query-contract` for machine-readable integration discovery.
- Official SDKs, the CLI, and MCP tooling automatically fall back to `x-primary-data-query-contract` from `/openapi.json` when an older self-hosted node still returns `404` for `/v1/meta/contract`. Raw HTTP integrations should do the same.
- That contract now includes the preferred direct-client imports (`decision_engine.AlgentaClient`, `decision_engine.AsyncAlgentaClient`) and runtime entrypoints (`algenta.Runtime`, `algenta.libraries`, `algenta-sdk` `Runtime`).

For explicit bridge-table execution, see
[Multi-hop Joins](/api-reference/multi-hop-joins). That guide covers exact
`join_path` requests for `POST /v1/query`, file-based CLI execution through
`de data query-batch`, and the separate `POST /v1/query/sql-report` rowset
surface.

For unified provider, skill, MCP, and runtime-library routing, see
[Capability Plane](/api-reference/capability-plane).
For the focused repo proof bundle, run `make capability-plane-verify`.

## Headers

| Header | Description |
|--------|-------------|
| `X-Request-Id` | Request identifier for tracing |
| `X-Decision-Hash` | Decision integrity hash when available |
| `X-Execution-Ms` | Canonical server execution time |
| `X-RateLimit-Limit` | Plan-based rate limit |
| `X-RateLimit-Remaining` | Remaining requests in the current window |
