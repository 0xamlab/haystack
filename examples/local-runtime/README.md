# Algenta — Local Runtime

Use Algenta locally in two distinct ways:

- pure local `algenta.Runtime` for local development and deterministic embedded execution
- hosted control plane plus local execution when you need the public API key, stored device license, and offline runtime history path

## 1. Primary local runtime

This is the simplest local path. It requires no API key and stays outside the
hosted device-license enforcement flow unless you opt into hosted local mode.

```python
from algenta import Runtime

rt = Runtime()
rt.connect("orders.csv", name="orders")
plan = rt.resolve({"source_name": "orders", "metric": "revenue"})
result = rt.query(plan)
print(result.result)
```

## 2. Hosted control plane with local execution

Use this path when you want the public Algenta API key contract plus local
runtime execution and offline task history.

Published package install:

```bash
pip install "algenta[cloud]"
```

`algenta` alone is the pure local runtime package and intentionally fails
closed for `Runtime(mode="api")` if `algenta-sdk` is missing. For local
artifact validation before publish, install the local `algenta-sdk` and
`algenta` artifacts together instead of relying on the `[cloud]` extra to
resolve an unpublished SDK.

### First proof

```bash
ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY> python3 scripts/verify_local_api_key_runtime.py
```

Canonical env vars on this hosted-local path are `ALGENTA_API_KEY` and
`ALGENTA_BASE_URL`. Legacy `DE_API_KEY`, `DE_BASE_URL`, and `ALGENTA_API_URL`
remain accepted for compatibility.

### Register and start

```bash
de login <YOUR_ALGENTA_API_KEY>
de runtime start
de runtime status
```

### Contract-first hosted data/query flow

Python:

```python
import os

from algenta import Runtime

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

rt = Runtime(api_key=api_key)

contract = rt.get_contract()
datasets = rt.list_datasets(search="orders", compact=True, limit=5)
summary = rt.get_dataset_summary(datasets.datasets[0].dataset_id)
query = rt.query_with_metadata(
    {
        "dataset_id": summary.dataset_id,
        "metric": {"role": "metric", "hint": "completed_order_count"},
        "aggregation": "sum",
        "group_by": ["order_month"],
        "limit": 12,
        "order": "desc",
    }
)
batch = rt.query_batch(
    {
        "defaults": {"dataset_id": summary.dataset_id},
        "queries": [
            {
                "key": "overall_completed_orders",
                "request": {
                    "metric": {"role": "metric", "hint": "completed_order_count"},
                    "aggregation": "sum",
                },
            },
            {
                "key": "monthly_completed_orders",
                "request": {
                    "metric": {"role": "metric", "hint": "completed_order_count"},
                    "aggregation": "sum",
                    "group_by": ["order_month"],
                    "limit": 12,
                    "order": "desc",
                },
            },
        ],
    }
)
report = rt.query_sql_report(
    {
        "sources": [{"dataset_id": summary.dataset_id, "alias": "orders"}],
        "sql": "select order_month, gross_revenue from orders order by order_month desc limit 12",
        "max_rows": 100,
    }
)
```

TypeScript:

```ts
import { Runtime } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const rt = new Runtime({ apiKey });

const contract = await rt.getContract();
const datasets = await rt.listDatasets({ search: "orders", compact: true, limit: 5 });
const summary = await rt.getDatasetSummary(datasets.datasets[0].dataset_id);
const query = await rt.queryWithMetadata({
  dataset_id: summary.dataset_id,
  metric: { role: "metric", hint: "completed_order_count" },
  aggregation: "sum",
  group_by: ["order_month"],
  limit: 12,
  order: "desc",
});
const batch = await rt.queryBatch({
  defaults: { dataset_id: summary.dataset_id },
  queries: [
    {
      key: "overall_completed_orders",
      request: {
        metric: { role: "metric", hint: "completed_order_count" },
        aggregation: "sum",
      },
    },
    {
      key: "monthly_completed_orders",
      request: {
        metric: { role: "metric", hint: "completed_order_count" },
        aggregation: "sum",
        group_by: ["order_month"],
        limit: 12,
        order: "desc",
      },
    },
  ],
});
const report = await rt.querySqlReport({
  sources: [{ dataset_id: summary.dataset_id, alias: "orders" }],
  sql: "select order_month, gross_revenue from orders order by order_month desc limit 12",
  max_rows: 100,
});
```

These hosted local-execution examples are the Cloud Managed path. In
`self_hosted` and `air_gapped`, pass an explicit self-hosted `base_url` /
`baseUrl` and fail closed instead of silently falling back to Algenta cloud.

That keeps the local runtime example aligned with the same public contract as
the API, direct SDKs, CLI, and MCP:

1. `GET /v1/meta/contract`
2. `GET /v1/data?search=...&compact=1`
3. `GET /v1/data/{dataset_id}/summary`
4. `POST /v1/query`, `POST /v1/query/batch`, or `POST /v1/query/sql-report`

`rt.get_contract()` / `rt.getContract()` already handles older self-hosted
nodes that still return `404` for `/v1/meta/contract` by falling back to
`/openapi.json` and reading `x-primary-data-query-contract`.

### Inspect persisted lineage and replay surfaces

The hosted local-runtime surface also exposes the same persisted operator
helpers as the direct clients.

Python:

```python
runs = rt.list_agent_runs(status="requires_approval", limit=10)
checkpoints = rt.query_agent_run_checkpoints(run_id="run_agent_123", limit=10)
mission_events = rt.query_agent_run_mission_events(run_id="run_agent_123", limit=25)
telemetry = rt.query_agent_run_telemetry(run_id="run_agent_123", limit=25)
replayed = rt.replay_agent_run("run_agent_123", checkpoint_id="cp_2")
forked = rt.fork_agent_run("run_agent_123", checkpoint_id="cp_1")
audit_artifacts = rt.get_audit_log_artifacts(limit=20)
policy_snapshots = rt.list_execution_policy_snapshots()
```

TypeScript:

```ts
const runs = await rt.listAgentRuns({ status: "requires_approval", limit: 10 });
const checkpoints = await rt.queryAgentRunCheckpoints({ run_id: "run_agent_123", limit: 10 });
const missionEvents = await rt.queryAgentRunMissionEvents({ run_id: "run_agent_123", limit: 25 });
const telemetry = await rt.queryAgentRunTelemetry({ run_id: "run_agent_123", limit: 25 });
const replayed = await rt.replayAgentRun("run_agent_123", { checkpoint_id: "cp_2" });
const forked = await rt.forkAgentRun("run_agent_123", { checkpoint_id: "cp_1" });
const auditArtifacts = await rt.getAuditLogArtifacts({ limit: 20 });
const policySnapshots = await rt.listExecutionPolicySnapshots();
```

### Inspect local history

```bash
de runtime history --limit 20
```

The append-only ledger lives at:

```text
~/.algenta/runtime/history.jsonl
```

### Stop or revoke

```bash
de runtime stop
de logout
```
