---
icon: python
description: Use Algenta from Python — install algenta-sdk, authenticate, and call the engine with a typed client. Includes runnable examples.
---

# Python SDK

This page is the reference for the live Python package Algenta ships today: `algenta-sdk` (imported as `decision_engine`), a thin typed HTTP client for the Algenta API. The source tree also contains the local `algenta` runtime package, but that runtime distribution is not public on PyPI yet. Use the client when you want direct, typed access to a running hosted or self-hosted API.

{% hint style="info" %}
Public registry status: `algenta-sdk` is the live PyPI package. The local `algenta` runtime is source-build / rollout-only until the runtime package and native sidecar are published.
{% endhint %}

## Install

Install the published HTTP client from PyPI.

```bash title="install.sh"
# Typed HTTP client. Imported as `decision_engine`.
pip install algenta-sdk
```

The package requires Python 3.10 or newer. CI verifies fresh wheel installs on Python 3.10, 3.12, and 3.14. It depends on `httpx>=0.28` and `pydantic>=2.7`.

{% hint style="warning" %}
The import name is `decision_engine`, not `algenta_sdk`. This is the historical module name and is stable. The runtime package imports as `algenta`.
{% endhint %}

## Authentication and configuration

The client reads its API key, in order, from the `api_key=` argument, then `ALGENTA_API_KEY`, then the legacy `DE_API_KEY`. If none are set, the constructor raises `ValueError`.

{% stepper %}
{% step %}
### Set your API key

Export a live or sandbox key into the environment. Live keys carry the `de_live_` prefix; sandbox keys carry `de_test_`.

```bash title="env.sh"
export ALGENTA_API_KEY="de_live_..."        # production key
# or, for the sandbox:
export ALGENTA_API_KEY="de_test_..."
```
{% endstep %}

{% step %}
### Construct the client

Point `base_url` at the hosted API (the default) or at your own engine.

```python title="client.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",   # default; override for self-hosted
)
```
{% endstep %}

{% step %}
### Verify the connection

Read the live contract version as a cheap round-trip. The client is a context manager that holds a pooled `httpx.Client`.

```python title="verify.py"
with AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"]) as client:
    print(client.get_contract().contract_version)
```
{% endstep %}
{% endstepper %}

The constructor accepts four arguments.

| Argument | Type | Default | Notes |
| --- | --- | --- | --- |
| `api_key` | `str \| None` | `None` | Falls back to `ALGENTA_API_KEY`, then `DE_API_KEY`. |
| `base_url` | `str \| None` | `https://api.algenta.ai` | Point at your self-hosted engine, e.g. `http://localhost:8000`. |
| `timeout` | `float` | `120.0` | Request timeout in seconds. |
| `max_retries` | `int` | `3` | Retries on `429` and `5xx`. |

{% expandable title="Advanced: contract constants" %}
The package re-exports the platform contract so you can read endpoint paths and defaults without hard-coding them.

```python title="contract_constants.py"
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
{% endexpandable %}

## Datasets and the data contract

### list_datasets

```python title="list_datasets.py"
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

{% hint style="info" %}
For large catalogs, `iter_datasets(...)` yields across pages and accepts a `max_items` cap.
{% endhint %}

### get_dataset_summary

```python title="dataset_summary.py"
summary = client.get_dataset_summary(datasets.datasets[0].dataset_id)
print(summary.dataset_id, summary.row_count)
```

### get_contract

`get_contract()` returns the live platform contract. If the deployment predates the `/v1/meta/contract` endpoint, the client falls back to deriving the contract from the OpenAPI document.

```python title="get_contract.py"
contract = client.get_contract()
print(contract.contract_version)
```

## Querying data

The query surface targets the `/v1/query` family. Requests are plain dicts; you can also pass keyword arguments, which are merged into the request body.

### query_with_metadata

Returns the query result plus execution metadata (request id, timing) and the raw response headers.

{% tabs %}
{% tab title="Python" %}
```python title="query_with_metadata.py"
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
{% endtab %}

{% tab title="cURL" %}
```bash title="query.sh"
curl -sS https://api.algenta.ai/v1/query \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "ds_orders",
    "metric": {"hint": "completed_order_count"},
    "aggregation": "sum"
  }'
```
{% endtab %}
{% endtabs %}

### query_batch

Send several queries in one round trip to `/v1/query/batch`.

```python title="query_batch.py"
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

```python title="query_sql_report.py"
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

{% tabs %}
{% tab title="Python" %}
```python title="typed_filters.py"
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
{% endtab %}

{% tab title="cURL" %}
```bash title="filtered_query.sh"
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
{% endtab %}
{% endtabs %}

## Decisions and simulation

These methods target the decision and simulation endpoints. `simulate` and `recommend` take keyword arguments; `plan_decision` takes a request dict.

```python title="decisions.py"
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

```python title="verify_explain.py"
verdict = client.verify({"dataset_id": summary.dataset_id, "claim": {"metric": "revenue", "op": "gt", "value": 0}})
trace = client.explain({"dataset_id": summary.dataset_id, "metric": {"hint": "revenue"}, "aggregation": "sum"})
```

## Capability plane

The capability plane lets an agent discover, route, and execute capabilities (tools, skills, MCP-backed providers).

```python title="capability_plane.py"
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

{% expandable title="Capability plane method reference" %}
| Method | Endpoint | Returns |
| --- | --- | --- |
| `list_capability_providers()` | `GET /v1/capability-providers` | list of `CapabilityProviderResult` |
| `get_capability(capability_id, include_instruction=False)` | `GET /v1/capabilities/{id}` | `CapabilityCatalogEntryResult` |
| `list_capabilities(kinds=, provider_ids=, binding_ids=)` | `GET /v1/capabilities` | catalog list |
| `route_capabilities(request)` | `POST /v1/capabilities/route` | `CapabilityRoutePlanResult` |
| `execute_capability(request)` | `POST /v1/capabilities/execute` | `CapabilityExecutionResult` |
| `list_skills()` | `GET /v1/capabilities?kinds=skill` | skill catalog |
| `list_mcp_providers()` | filtered providers | MCP providers |
{% endexpandable %}

## Agent runs

Create a run, then poll its state and event log.

```python title="agent_runs.py"
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

`create_agent_run` posts to `/v1/agent/runs`. `get_agent_run` reads `/v1/agent/runs/{run_id}`; `get_agent_run_events` reads `/v1/agent/runs/{run_id}/events`. For a live feed, `stream_agent_run_events(run_id)` returns an iterator over server-sent events.

{% hint style="info" %}
Lifecycle controls — `approve_agent_run`, `resume_agent_run`, `cancel_agent_run`, `fork_agent_run`, and `replay_agent_run` — round out the surface for human-in-the-loop and reproducibility workflows.
{% endhint %}

## Repository intelligence

The repository methods take a `repository_id` and a request dict. `triage_repository` and `apply_repository` map to the same endpoints the agent uses internally.

```python title="repository_intelligence.py"
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

{% hint style="danger" %}
`apply_repository` is a write. The platform contract is read-only by default and write operations require explicit confirmation, so pass the confirmation field your deployment expects rather than relying on defaults.
{% endhint %}

## Async client

Every method above has an async equivalent on `AsyncAlgentaClient`. The async client is an async context manager and exposes the same surface, split across the `async_client_*` modules internally.

```python title="async_client.py"
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

## The source-built Runtime (`algenta`)

`Runtime` is the runtime-first object in the source package. It connects to sources, resolves a request into an executable plan, and runs the query. This section documents the implemented surface for source builds and future runtime releases; it is not a public PyPI install path today.

```python title="runtime_local.py"
from algenta import Runtime

# Local: execute against connected files / in-memory data. No network.
rt = Runtime()                          # mode="local" by default
rt.connect("orders.csv")
plan = rt.resolve({"metric": "revenue", "group_by": "product_line"})
result = rt.query(plan)
```

### Modes

{% tabs %}
{% tab title="Local" %}
```python title="mode_local.py"
# In-process, against connected sources. No network.
rt = Runtime()                          # mode="local" by default
```
{% endtab %}

{% tab title="Cloud Managed" %}
```python title="mode_api.py"
# Delegate to the hosted Algenta API.
rt = Runtime(mode="api", api_key="de_live_...")
```
{% endtab %}

{% tab title="Self-hosted" %}
```python title="mode_self_hosted.py"
# Delegate to your own engine. base_url is REQUIRED here.
rt = Runtime(
    mode="self_hosted",
    api_key="de_live_...",
    base_url="http://localhost:8000",
)
```
{% endtab %}
{% endtabs %}

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

{% hint style="warning" %}
Private profiles fail closed. `Runtime(mode="self_hosted")` raises `RuntimeConfigurationError` if `base_url` is missing, and never silently falls back to Algenta cloud.
{% endhint %}

{% hint style="info" %}
Passing an invalid `mode` raises `ValueError`. `Runtime(mode="api")` requires the `algenta-sdk` client.
{% endhint %}

### connect, resolve, query

```python title="connect_resolve_query.py"
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

{% tabs %}
{% tab title="SQLite (local)" %}
```python title="connector_sqlite.py"
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
{% endtab %}

{% tab title="Postgres (self-hosted)" %}
```python title="connector_postgres.py"
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
{% endtab %}
{% endtabs %}

The engine builds the connection string from the structured `location` and `auth` fields. You may instead supply a ready `connection_string` inside the descriptor; for non-SQLite providers a structured `host`/`database` descriptor or an explicit `connection_string` is required.

{% hint style="info" %}
A descriptor is recognized as canonical when it carries any of `location`, `auth`, or `options`. The `type` is required and is lower-cased; `postgres` and `postgresql` are equivalent.
{% endhint %}

## CLI

The source runtime package installs the `algenta` console command for quick checks without writing code.

```bash title="cli.sh"
algenta version
algenta query orders.csv --metric revenue --group-by product_line
algenta import ./data
algenta simulate            # quick built-in simulation
```

## Errors

The client raises typed exceptions, all subclasses of `DecisionEngineError`.

```python title="errors.py"
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

{% hint style="info" %}
The runtime raises `AlgentaRuntimeError`, `RuntimeConfigurationError`, and `RuntimeValidationError` (all importable from `algenta`) for local-execution and descriptor problems.
{% endhint %}

## Related pages

{% content-ref url="../authentication.md" %}
[authentication.md](../authentication.md)
{% endcontent-ref %}

{% content-ref url="../cli.md" %}
[cli.md](../cli.md)
{% endcontent-ref %}

{% content-ref url="../self-hosting.md" %}
[self-hosting.md](../self-hosting.md)
{% endcontent-ref %}

{% content-ref url="../api/reference.md" %}
[api/reference.md](../api/reference.md)
{% endcontent-ref %}
