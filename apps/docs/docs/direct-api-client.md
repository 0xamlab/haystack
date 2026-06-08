---
sidebar_position: 10
---

# Direct API Client

Use the direct API client when you want lower-level access to a running Algenta
service.

This is an advanced integration surface for a running Algenta service. It is **not** the product installation path.

Start with [Quickstart](/quickstart), then use [API Authentication](/api-reference/authentication). The direct client is what you use after the service is already running.

Use this surface when you want raw API control instead of the higher-level SDK helpers or local runtime surfaces.

- Cloud Managed: `https://api.algenta.ai`
- `self_hosted` and `air_gapped`: pass an explicit self-hosted `base_url` / `baseUrl`

Private profiles fail closed and do not silently fall back to Algenta cloud.
Use the API key provisioned by your self-hosted operator deployment in private
profiles instead of Cloud Managed dashboard-issued keys.

## Python

```bash
pip install algenta-sdk
```

```python
import os

from decision_engine import AlgentaClient, QueryFilterCondition, QueryFilterSpec

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

client = AlgentaClient(api_key=api_key)
created = client.create_api_key(
    label="mission-runtime",
    expires_at="2028-05-19T00:00:00Z",
    device_limit=3,
)

datasets = client.list_datasets(search="orders", compact=True)
contract = client.get_contract()
plan = client.resolve(
    source_name="orders",
    metric="revenue",
    group_by="product_line",
)
verified = client.verify(plan.model_dump())
result = client.query(plan.model_dump())
result_with_metadata = client.query_with_metadata(plan.model_dump())
completed_orders = QueryFilterSpec(
    time_filter="last_year",
    conditions=[QueryFilterCondition(dimension_hint="status", op="eq", value="completed")],
)
summary = client.get_dataset_summary("orders_facts")
batch = client.query_batch(
    {
        "defaults": {
            "dataset_id": "orders_facts",
            "filter": completed_orders.model_dump(exclude_none=True),
        },
        "queries": [
            {"key": "completed_orders", "request": {"metric": {"role": "metric", "hint": "order_count"}, "aggregation": "sum"}},
            {"key": "gross_revenue", "request": {"metric": {"role": "metric", "hint": "gross_revenue"}, "aggregation": "sum"}},
        ],
    }
)
report = client.query_sql_report(
    {
        "sources": [{"dataset_id": "orders_facts", "alias": "orders"}],
        "sql": "select order_month, gross_revenue from orders",
        "max_rows": 100,
    }
)

from decision_engine import DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT

print(DEFAULT_BASE_URL)
print(PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"])
print(PRIMARY_DATA_QUERY_CONTRACT["api"]["query_batch_endpoint"])
print(PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"]["operators"]["scalar"])
```

The Python example above is the Cloud Managed path. In `self_hosted` and
`air_gapped`, construct `AlgentaClient(api_key=..., base_url="http://localhost:8000")`
or your own self-hosted origin instead.

## TypeScript

```bash
npm install algenta-sdk
```

```typescript
import { AlgentaClient, type QueryFilterSpec } from 'algenta-sdk'

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY
if (!apiKey) {
  throw new Error('Set ALGENTA_API_KEY or DE_API_KEY before running this example.')
}

const client = new AlgentaClient({
  apiKey,
})

const created = await client.createApiKey({
  label: 'mission-runtime',
  expires_at: '2028-05-19T00:00:00Z',
  device_limit: 3,
})

const datasets = await client.listDatasets({ search: 'orders', compact: true })
const contract = await client.getContract()
const plan = await client.resolve({
  source_name: 'orders',
  metric: 'revenue',
  group_by: 'product_line',
})
const result = await client.query(plan)
const resultWithMetadata = await client.queryWithMetadata(plan)
const completedOrders: QueryFilterSpec = {
  time_filter: 'last_year',
  conditions: [{ dimension_hint: 'status', op: 'eq', value: 'completed' }],
}
const summary = await client.getDatasetSummary('orders_facts')
const batch = await client.queryBatch({
  defaults: { dataset_id: 'orders_facts', filter: completedOrders },
  queries: [
    { key: 'completed_orders', request: { metric: { role: 'metric', hint: 'order_count' }, aggregation: 'sum' } },
    { key: 'gross_revenue', request: { metric: { role: 'metric', hint: 'gross_revenue' }, aggregation: 'sum' } },
  ],
})
const report = await client.querySqlReport({
  sources: [{ dataset_id: 'orders_facts', alias: 'orders' }],
  sql: 'select order_month, gross_revenue from orders',
  max_rows: 100,
})

import { DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT } from 'algenta-sdk'

console.log(DEFAULT_BASE_URL)
console.log(PRIMARY_DATA_QUERY_CONTRACT.api.contract_endpoint)
console.log(PRIMARY_DATA_QUERY_CONTRACT.api.query_sql_report_endpoint)
console.log(PRIMARY_DATA_QUERY_CONTRACT.governed_filter_contract.operators.scalar)
```

The TypeScript example above is also the Cloud Managed path. In `self_hosted`
and `air_gapped`, construct `new AlgentaClient({ apiKey: ..., baseUrl:
"http://localhost:8000" })` or your own self-hosted origin instead.

## Unified capability-plane helpers

Use the capability-plane methods when you want one customer-agnostic routing
surface above governed data, MCP providers, skills, native tools, and runtime
libraries.

- Python: `client.list_capability_providers()`
- Python: `client.list_capability_bindings(...)`
- Python: `client.list_capabilities(...)`
- Python: `client.route_capabilities(...)`
- Python: `client.get_capability(...)`
- Python: `client.execute_capability(...)`
- TypeScript: `client.listCapabilityProviders()`
- TypeScript: `client.listCapabilityBindings({ ... })`
- TypeScript: `client.listCapabilities({ ... })`
- TypeScript: `client.routeCapabilities({ ... })`
- TypeScript: `client.getCapability(capabilityId, { includeInstruction: true })`
- TypeScript: `client.executeCapability({ ... })`

Checked-in request artifacts live in `examples/capability-plane/`, and the
LangGraph reference router lives in `examples/langgraph/capability_router.py`.

The governed filter surface is a **record-filter contract**, not a SQL
predicate language. Use `QueryFilterCondition` / `QueryFilterSpec` for
deterministic exact slices that also work for Redis and other non-SQL sources
after normalization. The live operator families and validation rules are also
published under `PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"]` /
`PRIMARY_DATA_QUERY_CONTRACT.governed_filter_contract`. Use
`query_sql_report()` / `querySqlReport()` only when you truly need a wide
read-only SQL rowset.

The `raw_key` value from `create_api_key()` / `createApiKey()` is returned only
once on creation. Store it, along with `id`, `key_prefix`, `device_limit`, and
`expires_at`, before rotating or revoking the previous key.

An explicit `device_limit` also binds ordinary hosted API traffic for that key.
The SDK helpers send the stable device headers automatically. If you are making
raw HTTP requests with a capped key, send `X-Algenta-Device-Id`,
`X-Algenta-Platform`, and `X-Algenta-Hostname-Hash` on authenticated
requests. The first successful hosted request for a new capped device also returns
`X-Algenta-Device-Binding-Token`; store and replay that token on later
requests from the same device.

## Persisted runtime and control-plane helpers

The direct clients also expose the newer manifest-first runtime surfaces without
requiring the higher-level local runtime facade.

- Python: `client.list_agent_runs(...)`
- Python: `client.list_agent_run_checkpoints(run_id)`
- Python: `client.query_agent_run_checkpoints(...)`
- Python: `client.list_agent_run_mission_events(run_id, limit=...)`
- Python: `client.query_agent_run_mission_events(...)`
- Python: `client.list_agent_run_telemetry(run_id, limit=...)`
- Python: `client.query_agent_run_telemetry(...)`
- Python: `client.replay_agent_run(run_id, checkpoint_id=...)`
- Python: `client.fork_agent_run(run_id, checkpoint_id=...)`
- Python: `client.get_audit_logs(...)`
- Python: `client.get_audit_log_artifacts(...)`
- Python: `client.list_execution_policy_snapshots()`
- TypeScript: `client.listAgentRuns({ ... })`
- TypeScript: `client.listAgentRunCheckpoints(runId)`
- TypeScript: `client.queryAgentRunCheckpoints({ ... })`
- TypeScript: `client.listAgentRunMissionEvents(runId, { limit })`
- TypeScript: `client.queryAgentRunMissionEvents({ ... })`
- TypeScript: `client.listAgentRunTelemetry(runId, { limit })`
- TypeScript: `client.queryAgentRunTelemetry({ ... })`
- TypeScript: `client.replayAgentRun(runId, { checkpoint_id })`
- TypeScript: `client.forkAgentRun(runId, { checkpoint_id })`
- TypeScript: `client.getAuditLogs({ ... })`
- TypeScript: `client.getAuditLogArtifacts({ ... })`
- TypeScript: `client.listExecutionPolicySnapshots()`

Use those methods when you need persisted agent-run inventory, immutable
checkpoint and mission-trace queries, deterministic replay or fork workflows,
immutable audit-log artifacts, or stored execution-policy snapshot review from
the lower-level hosted client.

## When to use this surface

Use the direct API client when:

- you want the full API surface
- you need lower-level control than the higher-level SDK helpers
- you are integrating directly against hosted API behavior
- in private profiles, you want the same direct-client surface against an explicitly configured self-hosted origin
- you want the live machine-readable contract plus typed discovery, deterministic filter types, per-request metadata, governed batch execution, or constrained SQL reports without hand-parsing raw headers
