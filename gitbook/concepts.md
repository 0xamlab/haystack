---
icon: diagram-project
---

# Core concepts

This page builds the mental model you need to use Algenta well. It explains the three runtime modes, the capability plane that routes work to datasets, skills, MCP tools, and runtime libraries, the governed data and query flow, the decision and agent primitives, and the determinism and privacy guarantees that hold across all of them. Read it once. After that the SDK, CLI, and API pages are mostly syntax.

The engine is the same whether you run it locally, call a hosted control plane, or point at your own deployment. What changes is where execution happens and what leaves your process. Algenta makes that boundary explicit and enforces it.

## The Runtime

Everything starts with a `Runtime`. It is the single entry point in both SDKs.

{% tabs %}
{% tab title="Python" %}
```python
from algenta import Runtime

rt = Runtime()  # mode="local" by default
```
{% endtab %}

{% tab title="TypeScript" %}
```ts
import { Runtime } from "algenta-sdk";

const rt = new Runtime(); // mode "local" by default
```
{% endtab %}
{% endtabs %}

The Python package is `algenta-core` (import `algenta`); the TypeScript package is `algenta-sdk`. Both expose the same `Runtime` surface and the same three modes.

## Runtime modes

A `Runtime` runs in exactly one of three modes. The mode decides where execution happens and whether anything crosses the network.

| Mode | How you construct it | Where work runs | API key |
| --- | --- | --- | --- |
| `local` | `Runtime()` (default) | In your process, against connected sources | Not required |
| `api` | `Runtime(mode="api", api_key=...)` | Hosted control plane | Required |
| `self_hosted` | `Runtime(mode="self_hosted", base_url=...)` | Your own engine deployment | Required |

### Local mode

`local` is the default and needs no API key. It executes deterministically in-process against sources you connect. Local mode reads CSV, JSON, Parquet, Excel, in-memory rows, and local SQLite — no cloud, no egress.

```python
from algenta import Runtime

rt = Runtime()
reg = rt.connect("orders.csv", name="orders")
plan = rt.resolve({"metric": "revenue", "group_by": "product_line"})
result = rt.query(plan)
```

You can also connect in-memory rows directly:

```python
rt.connect(
    [{"product_line": "pro", "revenue": 120000}, {"product_line": "free", "revenue": 0}],
    name="orders",
)
```

Methods that require a server — billing, agent runs, the full control plane — are not available in `local` mode. Calling them raises a typed error pointing you at `api` or `self_hosted`:

```text
local_mode_not_supported: <method>() is not supported for Runtime({ mode: 'local' }).
Use Runtime({ mode: 'api', apiKey: '...' }) or Runtime({ mode: 'self_hosted', baseUrl: '...' }).
```

### API mode

`api` mode delegates to the Algenta hosted control plane. Set a key once and Algenta resolves the base URL for you.

```bash
export ALGENTA_API_KEY="sk_live_..."   # or DE_API_KEY
```

```python
from algenta import Runtime

rt = Runtime(mode="api")  # api_key read from ALGENTA_API_KEY / DE_API_KEY
```

### Self-hosted mode

`self_hosted` targets an engine you operate. It requires an explicit `base_url` and **never falls back to Algenta cloud**. If the base URL is missing, the constructor fails closed.

{% tabs %}
{% tab title="Python" %}
```python
import os
from algenta import Runtime

rt = Runtime(
    mode="self_hosted",
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="http://localhost:8000",
)
```
{% endtab %}

{% tab title="TypeScript" %}
```ts
import { Runtime } from "algenta-sdk";

const rt = new Runtime({
  mode: "self_hosted",
  apiKey: process.env.ALGENTA_API_KEY,
  baseUrl: "http://localhost:8000",
});
```
{% endtab %}
{% endtabs %}

{% hint style="warning" %}
`self_hosted` will not silently reach the public cloud. Constructing `Runtime(mode="self_hosted")` without a `base_url` raises `self_hosted_base_url_required`. When a private deployment profile is active, pointing any base URL at an Algenta-owned host is rejected. The self-hosted boundary is the privacy boundary.
{% endhint %}

`api` and `self_hosted` both require a key. You can supply it as the `api_key` argument or via `ALGENTA_API_KEY` / `DE_API_KEY`. The base URL for either mode also honors `ALGENTA_BASE_URL`, `DE_BASE_URL`, or `ALGENTA_API_URL`.

## The capability plane

Algenta does not hard-code which tool answers a request. Instead it exposes a **capability plane**: a catalog of capabilities you can discover, route over, and execute. Each capability has a `kind`:

| Kind | What it is |
| --- | --- |
| `dataset` | A governed data source you query |
| `skill` | A reusable instruction or callable behavior |
| `mcp_tool` | A tool exposed over the Model Context Protocol |
| `runtime_library` | A compiled engine library (for example, Mojo kernels) |

The plane has three core verbs. Discover with `list_capabilities` / `get_capability`, plan with `route_capabilities`, and run with `execute_capability`.

```python
# Discover
caps = rt.list_capabilities(kinds=["skill", "mcp_tool"])
detail = rt.get_capability(caps[0].capability_id, include_instruction=True)

# Route: pick the best capability for an objective
plan = rt.route_capabilities({
    "objective": "summarize the latest orders",
    "kinds": ["skill"],
})

# Execute the selected capability
result = rt.execute_capability({
    "capability_id": plan.selected_capability_id,
    "input": {"window": "last_7d"},
})
```

### Execution ownership: the fail-closed rule

Every capability carries an `execution_owner`, either `algenta_managed` or `client_managed`. This is the rule that governs where a capability is allowed to run.

| Execution owner | Where it may execute |
| --- | --- |
| `algenta_managed` | Server-side only — `Runtime(mode="api")` or `Runtime(mode="self_hosted")` |
| `client_managed` | Either server-side, or locally via a registered adapter |

In `local` mode the runtime **only** executes `client_managed` capabilities, and it fails closed otherwise:

```text
capability_execution_owner_unsupported:
Local runtime execution only supports client_managed capabilities.
```

`algenta_managed` capabilities remain discoverable and routable from `local` mode — `route_capabilities` will still return them — but executing one must go through `api` or `self_hosted`. To run a `client_managed` capability locally, register a customer-owned handler first:

```python
rt.register_capability_adapter(adapter)  # provides the local `execute` for the capability
```

If a `client_managed` capability is selected for local execution and no adapter is registered, you get `capability_adapter_missing` rather than a silent no-op.

{% hint style="info" %}
Read the rule as a one-liner: **managed runs on the server; local adapters run only what you own.** This is why the same code can move from `local` to `self_hosted` without changing behavior — only the set of executable capabilities widens.
{% endhint %}

## The governed data and query flow

Querying is a deliberate four-step flow: **connect → dataset_id → resolve → query**. You never query a raw table; you query a resolved plan against a governed dataset.

```python
from algenta import Runtime

rt = Runtime()
reg = rt.connect("orders.csv", name="orders")   # 1. connect -> dataset_id
dataset_id = reg.dataset_id

plan = rt.resolve({                              # 2. resolve an intent into a plan
    "dataset_id": dataset_id,
    "metric": "revenue",
    "group_by": "product_line",
})

result = rt.query(plan)                          # 3. execute the plan
```

### Filtering with QueryFilterSpec

Filters are typed, not free-form strings. Build them with `QueryFilterSpec` and `QueryFilterCondition`.

```python
from algenta import QueryFilterCondition, QueryFilterSpec

completed_orders = QueryFilterSpec(
    time_filter="last_year",
    conditions=(
        QueryFilterCondition(dimension_hint="status", op="eq", value="completed"),
    ),
)

query = rt.query_with_metadata({
    "dataset_id": dataset_id,
    "filter": completed_orders.to_dict(),
    "metric": {"hint": "gross_revenue"},
    "aggregation": "sum",
})
```

A `QueryFilterCondition` targets a `column` or a `dimension_hint` and uses one of the supported operators: `eq`, `in`, `gt`, `gte`, `lt`, `lte`, `is_null`, `is_not_null`. Conditions are validated on construction — `op="in"` requires `values`; `is_null` / `is_not_null` accept neither `value` nor `values`.

### Batch and SQL-report queries

When you need many related results in one round trip, use `query_batch`. Shared keys go in `defaults`; each entry overrides as needed.

```python
batch = rt.query_batch({
    "defaults": {
        "dataset_id": dataset_id,
        "filter": completed_orders.to_dict(),
    },
    "queries": [
        {
            "key": "completed_orders",
            "request": {"metric": {"hint": "order_count"}, "aggregation": "sum"},
        },
        {
            "key": "monthly_completed_orders",
            "request": {
                "metric": {"hint": "order_count"},
                "aggregation": "sum",
                "group_by": ["order_month"],
                "limit": 12,
                "order": "desc",
            },
        },
    ],
})
```

For a formatted, multi-section analytical output, use `query_sql_report`. Both `query_batch` and `query_sql_report` follow the same governed contract as a single `query`.

## Decision, simulation, and agent primitives

On top of the data flow, Algenta exposes higher-order primitives. They share the same runtime, modes, and determinism guarantees.

### plan_decision

Turn a structured decision request into a ranked plan with options and risk profile.

```python
plan = rt.plan_decision({
    "objective": "choose a fulfillment region",
    "options": ["us-east", "eu-west"],
    "constraints": {"max_latency_ms": 200},
})
```

### simulate and recommend

`simulate` runs Monte Carlo scenarios; `recommend` scores candidate actions and returns the best one.

```python
from algenta import simulate

outcome = simulate(revenue=120000, cost=70000, runs=50000)
```

```python
recommendation = rt.recommend([
    {"name": "expand", "request": {...}},
    {"name": "hold", "request": {...}},
])
```

### Decision memory

Decisions can be logged, listed, and reconciled against real outcomes — a durable record of what was decided and how it turned out.

```python
logged = rt.log_decision({"objective": "choose a fulfillment region", "selected": "us-east"})
rt.record_outcome(logged.decision_id, actual_outcome=142000.0, outcome_notes="Q3 actuals")
history = rt.list_decisions(with_outcome_only=True)
```

### Agent runs

Agent runs are long-lived, governed executions with checkpoints, events, and approval gates. They require `api` or `self_hosted` mode.

```python
run = rt.create_agent_run(
    task="triage the failing orders pipeline",
    tools=["dataset.orders", "skill.diagnose"],
    max_steps=10,
    approval_mode="auto",
)
status = rt.get_agent_run(run.run_id)
events = rt.get_agent_run_events(run.run_id)
```

Runs support `resume_agent_run`, `cancel_agent_run`, `approve_agent_run`, checkpoints, telemetry, and `replay_agent_run` for deterministic re-execution.

## Determinism and the runtime contract

Algenta is built to be replayable. Given the same inputs, the same plan, and the same engine version, you get the same result. Two endpoints make the engine's behavior machine-readable so you can pin and verify it.

```bash
# The machine-readable platform contract: endpoints, enums, query/filter rules
curl http://localhost:8000/v1/meta/contract

# The signed runtime manifest: modules, versions, determinism guarantees
curl http://localhost:8000/v1/runtime/manifest
```

From the SDK these are `rt.get_contract()` and `rt.get_runtime_manifest()`:

```python
contract = rt.get_contract()
manifest = rt.get_runtime_manifest()
```

The contract is also available as a static export, so you can assert against it in tests without a network call:

```python
from algenta import PRIMARY_DATA_QUERY_CONTRACT, CAPABILITY_PLANE_CONTRACT

print(PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"]["operators"]["scalar"])
print(CAPABILITY_PLANE_CONTRACT["enums"]["capability_kinds"])
# ['dataset', 'mcp_tool', 'mcp_resource', 'mcp_prompt', 'skill', 'native_tool', 'runtime_library']
print(CAPABILITY_PLANE_CONTRACT["enums"]["execution_owners"])
# ['algenta_managed', 'client_managed']
```

## Privacy and governance defaults

Algenta defaults to keeping data and audit local unless you opt into cloud sync.

`ALGENTA_DEPLOYMENT_MODE` selects the profile. The default is `saas`; setting it to `self_hosted` or `air_gapped` activates a **private profile** that disables cloud egress and forbids targeting Algenta-owned hosts.

```bash
export ALGENTA_DEPLOYMENT_MODE=self_hosted   # or: air_gapped
```

Telemetry and metering follow the profile. Each has three modes — `disabled`, `local_audit`, `control_plane_sync` — controlled by `ALGENTA_TELEMETRY_MODE` and `ALGENTA_METERING_MODE`. Under a private profile they default to `local_audit`: usage is recorded locally and nothing is shipped to a control plane.

```bash
export ALGENTA_TELEMETRY_MODE=local_audit
export ALGENTA_METERING_MODE=local_audit
```

{% hint style="info" %}
`air_gapped` is the strictest profile: `control_plane_sync` for telemetry or metering is rejected outright (`air_gapped_control_plane_sync_forbidden`). To force cloud off regardless of profile, set `ALGENTA_DISABLE_CLOUD=1`.
{% endhint %}

These defaults compose with the mode rules above. A `self_hosted` runtime under a `self_hosted` deployment profile with `local_audit` telemetry is a fully governed, no-egress configuration where the only network calls are to the engine you operate.

## Where to go next

This page is intentionally conceptual. For exact signatures, parameters, and return types, follow the reference pages:

- **SDK reference** — every `Runtime` method, the model types (`QueryFilterSpec`, `ResolvedPlan`, `QueryOutput`, capability and agent-run models), and async variants.
- **CLI reference** — the `algenta` command (`algenta import`, `algenta map`, `algenta query`) for local previews and queries straight from the shell.
- **API reference** — the HTTP surface behind `api` and `self_hosted` modes, including `/v1/meta/contract`, `/v1/runtime/manifest`, the query endpoints, and the capability plane routes.
