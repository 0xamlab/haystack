---
icon: python
---

# Python SDK

This page is the reference for the two Python packages Algenta ships: `algenta-sdk` (imported as `decision_engine`), a thin typed HTTP client for the Algenta API, and `algenta-core` (imported as `algenta`), a runtime-first package whose `Runtime` object runs locally, against the hosted API, or against a self-hosted engine. Use the client when you want direct, typed access to a single endpoint. Use the `Runtime` when you want one object that resolves and queries structured data the same way regardless of where execution happens.

## Install

The client and the runtime are separate distributions on PyPI.

```bash
# Typed HTTP client. Imported as `decision_engine`.
pip install algenta-sdk

# Runtime-first package. Imported as `algenta`. Adds the `algenta` CLI.
pip install algenta-core

# The runtime with the cloud client bundled (enables Runtime(mode="api")).
pip install "algenta-core[cloud]"
```

Both packages require Python 3.10 or newer. `algenta-sdk` depends only on `httpx>=0.28` and `pydantic>=2.7`.

{% hint style="info" %}
The import name is `decision_engine`, not `algenta_sdk`. This is the historical module name and is stable. The runtime package imports as `algenta`.
{% endhint %}

## Authentication and configuration

The client reads its API key, in order, from the `api_key=` argument, then `ALGENTA_API_KEY`, then the legacy `DE_API_KEY`. If none are set, the constructor raises `ValueError`.

```bash
export ALGENTA_API_KEY="de_live_..."        # production key
# or, for the sandbox:
export ALGENTA_API_KEY="de_test_..."
```

```python
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",   # default; override for self-hosted
)
```

The constructor accepts four arguments.

| Argument | Type | Default | Notes |
| --- | --- | --- | --- |
| `api_key` | `str \| None` | `None` | Falls back to `ALGENTA_API_KEY`, then `DE_API_KEY`. |
| `base_url` | `str \| None` | `https://api.algenta.ai` | Point at your self-hosted engine, e.g. `http://localhost:8000`. |
| `timeout` | `float` | `120.0` | Request timeout in seconds. |
| `max_retries` | `int` | `3` | Retries on `429` and `5xx`. |

`AlgentaClient` is the preferred name. `DecisionEngineClient` and `CodnaClient` are accepted aliases for backward compatibility; all three are the same class. The client is a context manager and holds a pooled `httpx.Client`:

```python
with AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"]) as client:
    print(client.get_contract().contract_version)
```

### Contract constants

The package re-exports the platform contract so you can read endpoint paths and defaults without hard-coding them.

```python
from decision_engine import (
    DEFAULT_BASE_URL,             # "https://api.algenta.ai"
    CONTRACT_VERSION,             # "v1.3"
    PRIMARY_DATA_QUERY_CONTRACT,  # dict: endpoints + query shape
    AUTH_SCHEME,                  # "bearer_api_key"
    API_KEY_PREFIX_LIVE,          # "de_live_"
    API_KEY_PREFIX_TEST,          # "de_test_"
)

print(PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"])  # /v1/meta/contract
```

## Datasets and the data contract

### list_datasets

```python
datasets = client.list_datasets(search="orders", compact=True)
for ds in datasets.datasets:
    print(ds.dataset_id, ds.name)
```

| Parameter | Type | Default | Notes |
| --- | --- | --- | --- |
| `page` | `int` | `1` | 1-based page index. |
| `limit` | `int` | `200` | Page size. |
| `search` | `str \| None` | `None` | Free-text match over dataset names. |
| `status` | `str \| None` | `None` | Filter by ingestion status. |
| `source_name` | `str \| None` | `None` | Filter by source. |
| `compact` | `bool` | `False` | Drop heavy fields for a lighter list. |

For large catalogs, `iter_datasets(...)` yields across pages and accepts a `max_items` cap.

### get_dataset_summary

```python
summary = client.get_dataset_summary(datasets.datasets[0].dataset_id)
print(summary.dataset_id, summary.row_count)
```

### get_contract

`get_contract()` returns the live platform contract. If the deployment predates the `/v1/meta/contract` endpoint, the client falls back to deriving the contract from the OpenAPI document.

```python
contract = client.get_contract()
print(contract.contract_version)
```

## Querying data

The query surface targets the `/v1/query` family. Requests are plain dicts; you can also pass keyword arguments, which are merged into the request body.

### query_with_metadata

Returns the query result plus execution metadata (request id, timing) and the raw response headers.

```python
result = client.query_with_metadata(
    {
        "dataset_id": summary.dataset_id,
        "metric": {"hint": "completed_order_count"},
        "aggregation": "sum",
    }
)
print(result.metadata.request_id)
print(result.data)
```

### query_batch

Send several queries in one round trip to `/v1/query/batch`.

```python
batch = client.query_batch(
    {
        "queries": [
            {"dataset_id": summary.dataset_id, "metric": {"hint": "revenue"}, "aggregation": "sum"},
            {"dataset_id": summary.dataset_id, "metric": {"hint": "orders"}, "aggregation": "count"},
        ]
    }
)
```

### query_sql_report

Run a structured SQL-style report against `/v1/query/sql-report`.

```python
report = client.query_sql_report(
    {
        "dataset_id": summary.dataset_id,
        "select": ["product_line", "sum(revenue) AS revenue"],
        "group_by": ["product_line"],
        "order_by": [{"field": "revenue", "direction": "desc"}],
        "limit": 10,
    }
)
```

### Typed query filters

`QueryFilterSpec` and `QueryFilterCondition` are exported for building filters with types rather than raw dicts.

```python
from decision_engine import QueryFilterSpec, QueryFilterCondition

filters = QueryFilterSpec(
    conditions=[
        QueryFilterCondition(field="status", operator="eq", value="completed"),
        QueryFilterCondition(field="region", operator="in", value=["EU", "UK"]),
    ]
)

result = client.query_with_metadata(
    {
        "dataset_id": summary.dataset_id,
        "metric": {"hint": "revenue"},
        "aggregation": "sum",
        "filters": filters.model_dump(exclude_none=True),
    }
)
```

The matching HTTP call is a plain POST:

```bash
curl -sS https://api.algenta.ai/v1/query \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "ds_orders",
    "metric": {"hint": "revenue"},
    "aggregation": "sum",
    "filters": {"conditions": [{"field": "status", "operator": "eq", "value": "completed"}]}
  }'
```

## Decisions and simulation

These methods target the decision and simulation endpoints. `simulate` and `recommend` take keyword arguments; `plan_decision` takes a request dict.

```python
# /v1/simulate — returns a DecisionEnvelope
envelope = client.simulate(
    mode="auto",
    scenario={
        "variables": {"revenue": {"low": 80000, "high": 200000}},
        "objective": "maximize_net_value",
    },
)
print(envelope.recommended_action, envelope.confidence)

# /v1/decisions/plan — returns a DecisionPlanResult
plan = client.plan_decision(
    {
        "goal": "Reduce checkout latency",
        "context": {"p95_ms": 820, "budget_usd": 5000},
    }
)

# /v1/recommend — ranks candidate actions
ranking = client.recommend(
    actions=[{"name": "scale_up"}, {"name": "add_cache"}],
    objective="maximize_net_value",
)
```

`verify` (POST `/v1/verify`) and `explain` (which runs a query and annotates it) complete the decision surface:

```python
verdict = client.verify({"dataset_id": summary.dataset_id, "claim": {"metric": "revenue", "op": "gt", "value": 0}})
trace = client.explain({"dataset_id": summary.dataset_id, "metric": {"hint": "revenue"}, "aggregation": "sum"})
```

## Capability plane

The capability plane lets an agent discover, route, and execute capabilities (tools, skills, MCP-backed providers).

```python
# List providers, then narrow to MCP-backed ones.
providers = client.list_capability_providers()
mcp = client.list_mcp_providers()      # providers whose provider_type == "mcp_provider"

# Catalog of capabilities; list_skills() is list_capabilities(kinds=["skill"]).
skills = client.list_skills()
cap = client.get_capability("cap.skill.summarize", include_instruction=True)

# Plan a route for a task, then execute the chosen capability.
route = client.route_capabilities({"task": "summarize the incident", "kinds": ["skill"]})
outcome = client.execute_capability(
    {
        "capability_id": cap.capability_id,
        "input": {"text": "..."},
    }
)
```

| Method | Endpoint | Returns |
| --- | --- | --- |
| `list_capability_providers()` | `GET /v1/capability-providers` | list of `CapabilityProviderResult` |
| `get_capability(capability_id, include_instruction=False)` | `GET /v1/capabilities/{id}` | `CapabilityCatalogEntryResult` |
| `list_capabilities(kinds=, provider_ids=, binding_ids=)` | `GET /v1/capabilities` | catalog list |
| `route_capabilities(request)` | `POST /v1/capabilities/route` | `CapabilityRoutePlanResult` |
| `execute_capability(request)` | `POST /v1/capabilities/execute` | `CapabilityExecutionResult` |
| `list_skills()` | `GET /v1/capabilities?kinds=skill` | skill catalog |
| `list_mcp_providers()` | filtered providers | MCP providers |

## Agent runs

Create a run, then poll its state and event log.

```python
run = client.create_agent_run(
    task="Triage the failing checkout test and propose a fix",
    context={"repository_id": "repo_42"},
    tools=["repository.triage", "repository.simulate"],
    max_steps=10,
    approval_mode="auto",     # or "manual"
    start_paused=False,
)

state = client.get_agent_run(run.run_id)
events = client.get_agent_run_events(run.run_id, limit=1000)
for event in events.events:
    print(event.type, event.created_at)
```

`create_agent_run` posts to `/v1/agent/runs`. `get_agent_run` reads `/v1/agent/runs/{run_id}`; `get_agent_run_events` reads `/v1/agent/runs/{run_id}/events`. For a live feed, `stream_agent_run_events(run_id)` returns an iterator over server-sent events. Lifecycle controls (`approve_agent_run`, `resume_agent_run`, `cancel_agent_run`, `fork_agent_run`, `replay_agent_run`) round out the surface.

## Repository intelligence

The repository methods take a `repository_id` and a request dict. `triage_repository` and `apply_repository` map to the same endpoints the agent uses internally.

```python
# Rank likely-broken files / propose where to act. POST /v1/repositories/{id}/triage
triage = client.triage_repository(
    "repo_42",
    {"goal": "checkout test is red", "max_candidates": 5},
)

# Simulate a proposed change. POST /v1/repositories/{id}/simulate -> DecisionEnvelope
sim = client.simulate_repository(
    "repo_42",
    {"decision_plan_id": triage.decision_plan_id},
)

# Apply the change. POST /v1/repositories/{id}/apply -> RepositoryApplyResult
applied = client.apply_repository(
    "repo_42",
    {"decision_plan_id": triage.decision_plan_id, "confirm": True},
)
print(applied.diff_uri)
```

{% hint style="warning" %}
`apply_repository` is a write. The platform contract is read-only by default and write operations require explicit confirmation, so pass the confirmation field your deployment expects rather than relying on defaults.
{% endhint %}

## Async client

Every method above has an async equivalent on `AsyncAlgentaClient`. The async client is an async context manager and exposes the same surface, split across the `async_client_*` modules internally.

```python
import asyncio
import os
from decision_engine import AsyncAlgentaClient

async def main() -> None:
    async with AsyncAlgentaClient(api_key=os.environ["ALGENTA_API_KEY"]) as client:
        datasets = await client.list_datasets(search="orders", compact=True)
        summary = await client.get_dataset_summary(datasets.datasets[0].dataset_id)
        result = await client.query_with_metadata(
            {"dataset_id": summary.dataset_id, "metric": {"hint": "revenue"}, "aggregation": "sum"}
        )
        print(result.metadata.request_id)

asyncio.run(main())
```

`AsyncDecisionEngineClient` and `AsyncCodnaClient` are aliases of `AsyncAlgentaClient`.

## The Runtime (`algenta-core`)

`Runtime` is the runtime-first object. It connects to sources, resolves a request into an executable plan, and runs the query. The same three calls work in every mode; only the constructor changes.

```python
from algenta import Runtime

# Local: execute against connected files / in-memory data. No network.
rt = Runtime()                          # mode="local" by default
rt.connect("orders.csv")
plan = rt.resolve({"metric": "revenue", "group_by": "product_line"})
result = rt.query(plan)
```

### Modes

```python
# Cloud Managed: delegate to the hosted Algenta API.
rt = Runtime(mode="api", api_key="de_live_...")

# Self-hosted: delegate to your own engine. base_url is REQUIRED here.
rt = Runtime(
    mode="self_hosted",
    api_key="de_live_...",
    base_url="http://localhost:8000",
)
```

| `mode` | Execution | `base_url` | `api_key` |
| --- | --- | --- | --- |
| `local` (default) | In-process, against connected sources | Unused | Optional |
| `api` | Hosted Algenta API | Defaults to `https://api.algenta.ai` | Required |
| `self_hosted` | Your engine | **Required** (e.g. `http://localhost:8000`) | Required |

| Constructor argument | Type | Default |
| --- | --- | --- |
| `mode` | `str` | `"local"` |
| `api_key` | `str \| None` | `None` (falls back to `ALGENTA_API_KEY` / `DE_API_KEY`) |
| `base_url` | `str \| None` | `None` |
| `enforce_limits` | `bool \| None` | `None` (auto) |

{% hint style="info" %}
Private profiles fail closed. `Runtime(mode="self_hosted")` raises `RuntimeConfigurationError` if `base_url` is missing, and never silently falls back to Algenta cloud.
{% endhint %}

Passing an invalid `mode` raises `ValueError`. `Runtime(mode="api")` requires the `algenta-sdk` client, which is installed by the `[cloud]` extra.

### connect, resolve, query

```python
rt = Runtime()

# Connect by file path (CSV, TSV, JSON, Excel, Parquet are recognized).
orders = rt.connect("orders.csv", name="orders")

# Resolve a request into a plan, then run it.
plan = rt.resolve({"source_name": "orders", "metric": "revenue", "group_by": "product_line"})
result = rt.query(plan)

# Or run a request directly without holding the plan.
result = rt.query({"source_name": "orders", "metric": "revenue", "group_by": "product_line"})

# Metadata-rich and batch variants mirror the client.
detailed = rt.query_with_metadata({"source_name": "orders", "metric": "revenue"})
batched = rt.query_batch({"queries": [{"source_name": "orders", "metric": "orders"}]})
```

`connect` is also available as `register_source`. It accepts a positional source plus keyword options:

| Argument | Notes |
| --- | --- |
| `source` | A file path, inline records, or a structured connector descriptor. |
| `name` | Logical source name used later as `source_name`. |
| `connector` | A structured connector descriptor (see below). |
| `selection` | Table / sheet / object selection within the connector. |
| `dataset_name` | Persisted dataset name (API and self-hosted modes). |
| `persist` | Persist the connection rather than treating it as ephemeral. |

### Structured connector descriptors

Local mode accepts local files and SQLite. The other SQL providers (Postgres, MySQL, and so on) require `mode="api"` or `mode="self_hosted"`. Descriptors use a canonical envelope with `type`, `location`, and `auth` sections.

SQLite, local:

```python
rt = Runtime()
rt.connect(
    connector={
        "type": "sqlite",
        "location": {"path": "/data/shop.db"},
    },
    selection={"table": "orders"},
    name="orders",
)
plan = rt.resolve({"source_name": "orders", "metric": "revenue", "group_by": "product_line"})
result = rt.query(plan)
```

Postgres, self-hosted engine:

```python
rt = Runtime(mode="self_hosted", api_key="de_live_...", base_url="http://localhost:8000")
rt.connect(
    connector={
        "type": "postgres",
        "location": {
            "host": "db.internal",
            "port": 5432,
            "database": "analytics",
        },
        "auth": {
            "username": "reader",
            "password": "...",
        },
    },
    selection={"schema": "public", "table": "orders"},
    dataset_name="orders",
    persist=True,
    name="orders",
)
result = rt.query({"source_name": "orders", "metric": "revenue", "group_by": "product_line"})
```

The engine builds the connection string from the structured `location` and `auth` fields. You may instead supply a ready `connection_string` inside the descriptor; for non-SQLite providers a structured `host`/`database` descriptor or an explicit `connection_string` is required.

{% hint style="info" %}
A descriptor is recognized as canonical when it carries any of `location`, `auth`, or `options`. The `type` is required and is lower-cased; `postgres` and `postgresql` are equivalent.
{% endhint %}

## CLI

`algenta-core` installs the `algenta` console command for quick checks without writing code.

```bash
algenta version
algenta query orders.csv --metric revenue --group-by product_line
algenta import ./data
algenta simulate            # quick built-in simulation
```

## Errors

The client raises typed exceptions, all subclasses of `DecisionEngineError`.

```python
from decision_engine import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
    DecisionEngineError,
)

try:
    client.get_dataset_summary("does-not-exist")
except NotFoundError:
    ...
except RateLimitError:
    ...   # the client already retried 429s up to max_retries
except DecisionEngineError as exc:
    print(exc)
```

The runtime raises `CodnaRuntimeError`, `RuntimeConfigurationError`, and `RuntimeValidationError` (all importable from `algenta`) for local-execution and descriptor problems.
