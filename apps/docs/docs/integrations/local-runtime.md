---
sidebar_position: 6
---

# Local Runtime

There are two related but different local-runtime stories in this repository.

## 1. Primary local runtime: `algenta.Runtime`

This is the primary local-runtime path when you intentionally want local development, testing, or embedded execution.

```python
from algenta import Runtime

rt = Runtime()
rt.connect("orders.csv", name="orders")
plan = rt.resolve({"source_name": "orders", "metric": "revenue"})
result = rt.query(plan)
```

This path:

- runs locally
- requires no API key
- is the primary local-runtime docs and SDK path
- supports local CSV, JSON, in-memory records, and deterministic SQLite descriptors on Python today
- remains outside the hosted device-license and credit-bucket enforcement path unless you explicitly opt into hosted local mode
- also remains outside the hosted commercial plane in the default `self_hosted` enterprise profile

## 2. Hosted control plane with local execution

This repo also supports a more advanced runtime/device flow where the hosted control plane verifies the machine and a local daemon performs execution.

Use this when you need:

- hosted API-key verification
- local device licensing
- daemon-managed local execution
- local task history

Install shape for this hosted-runtime path:

```bash
pip install "algenta[cloud]"
```

`algenta` alone is the pure local runtime package and intentionally fails
closed for `Runtime(mode="api")` or `Runtime(mode="self_hosted")` if
`algenta-sdk` is absent. For local artifact validation before publish, install
the local `algenta-sdk` and `algenta` artifacts together instead of
assuming the `[cloud]` extra can resolve an unpublished SDK from a package
index.

### Verify the machine

Use a bounded-lifetime replacement key for this hosted path, not the one-time
self-host bootstrap key.

```bash
ALGENTA_API_KEY=de_live_...
ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY> python3 scripts/verify_local_api_key_runtime.py
```

Canonical env vars on this hosted-local path are `ALGENTA_API_KEY` and
`ALGENTA_BASE_URL`. Legacy `DE_API_KEY`, `DE_BASE_URL`, and `ALGENTA_API_URL`
remain accepted for compatibility.

If you already have a stored device license from that advanced path, the public runtimes can also execute locally with hosted enforcement enabled.

Python:

```python
import os

from algenta import Runtime

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

rt = Runtime(api_key=api_key)
rt.connect("orders.csv", name="orders")
plan = rt.resolve({"source_name": "orders", "metric": "revenue"})
result = rt.query(plan)
```

This hosted local-execution example is the Cloud Managed path. In `self_hosted`
and `air_gapped`, pass an explicit self-hosted `base_url` and fail closed
instead of silently falling back to Algenta cloud.

The same licensed local path also works for the Python Mojo package surface:

```python
import os

from algenta import MojoRuntime, libraries

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

runtime = MojoRuntime(mode="local", api_key=api_key, base_url="http://localhost:8000")
catalog = libraries(mode="local", api_key=api_key, base_url="http://localhost:8000")
sample = catalog.ab_testing.sample_size_proportion(
    p1=0.10,
    p2=0.12,
    alpha=0.05,
    power=0.8,
)
```

TypeScript:

```typescript
import { Runtime } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const rt = new Runtime({ apiKey });
await rt.connect("orders.csv", { name: "orders" });
const plan = await rt.resolve({ source_name: "orders", metric: "revenue" });
const result = await rt.query(plan);
```

This TypeScript snippet is also the Cloud Managed path. In `self_hosted` and
`air_gapped`, pass an explicit self-hosted `baseUrl` and fail closed instead
of silently falling back to Algenta cloud.

For local database-backed development, the public runtimes now diverge slightly:

- Python local mode supports deterministic SQLite descriptors directly
- TypeScript local mode also supports SQLite descriptors when the active Node runtime exposes `node:sqlite`

That keeps execution local while enforcing the stored local device license and local credit bucket offline.

## Strict privacy profile

Use `ALGENTA_DEPLOYMENT_MODE=air_gapped` when the local runtime must fail
closed without hosted registration, credit refresh, heartbeat, or metering
flush. In that profile:

- a valid local signed license file is required
- `ALGENTA_DISABLE_TELEMETRY=1` keeps local audit records but sends no usage telemetry
- `ALGENTA_ALLOW_OUTBOUND_NETWORK=0` blocks Algenta-owned and undeclared public egress
- `ALGENTA_EGRESS_ALLOWLIST` is the only way to permit explicit connector/operator egress

### Hosted data/query contract on the runtime surface

When the runtime is using API transport with a hosted key, it also exposes the
same public data/query contract as the direct API clients:

- `get_contract()` / `getContract()`
- `list_connectors(page=..., limit=...)` / `listConnectors({ page, limit })`
- `create_connector(...)`, `get_connector(...)`, `update_connector(...)`, `test_connector(...)`, `browse_connector(...)`, and `delete_connector(...)`
- `createConnector(...)`, `getConnector(...)`, `updateConnector(...)`, `testConnector(...)`, `browseConnector(...)`, and `deleteConnector(...)`
- `connect_data(...)` / `connect(source?, { name?, description?, connectorId?, connector?, selection?, datasetName?, persist?, visibility?, connectionName? })`
- `list_datasets(search=..., compact=True)` / `listDatasets({ search, compact: true })`
- `get_dataset(dataset_id)` / `getDataset(datasetId)`
- `get_dataset_summary(dataset_id)` / `getDatasetSummary(datasetId)`
- `refresh_dataset(dataset_id)` / `refreshDataset(datasetId)`
- `delete_dataset(dataset_id)` / `deleteDataset(datasetId)`
- `create_repository_snapshot(repository_id, request)`, `get_repository_snapshot(repository_id, snapshot_id)`, `triage_repository(repository_id, request)`, `create_repository_decision_plan(repository_id, request)`, `simulate_repository(repository_id, request)`, and `apply_repository(repository_id, request)`
- `createRepositorySnapshot(repositoryId, request)`, `getRepositorySnapshot(repositoryId, snapshotId)`, `triageRepository(repositoryId, request)`, `createRepositoryDecisionPlan(repositoryId, request)`, `simulateRepository(repositoryId, request)`, and `applyRepository(repositoryId, request)`
- `query_with_metadata()` / `queryWithMetadata()`
- `query_batch()` / `queryBatch()`
- `query_sql_report()` / `querySqlReport()`

That means the hosted local-runtime path can stay on the same contract-first
flow as the rest of Algenta:

1. `GET /v1/meta/contract`
2. `GET /v1/connectors`, `POST /v1/connectors`, `POST /v1/connectors/{connector_id}/test`, or `GET /v1/connectors/{connector_id}/browse`
3. `POST /v1/data/connect`, `GET /v1/data?search=...&compact=1`, `GET /v1/data/{dataset_id}`, `POST /v1/data/{dataset_id}/refresh`, or `DELETE /v1/data/{dataset_id}`
4. `GET /v1/data/{dataset_id}/summary`
5. `POST /v1/repositories/{repository_id}/snapshots`, `GET /v1/repositories/{repository_id}/snapshots/{snapshot_id}`, `POST /v1/repositories/{repository_id}/triage`, `POST /v1/repositories/{repository_id}/decision-plans`, `POST /v1/repositories/{repository_id}/simulate`, or `POST /v1/repositories/{repository_id}/apply`
6. `POST /v1/query`, `POST /v1/query/batch`, or `POST /v1/query/sql-report`

For explicit self-hosted Repository Intelligence planning without a
provider-backed chat model, set
`ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1`.
That bounded local planner is intentionally narrow: today it supports the
deterministic Python return-literal mismatch workflow used by the live
repository proof lane, and it fails closed with
`repository_local_planner_unsupported` outside that contract.

For local SDK or daemon-backed repository intelligence without a hosted API
hop, configure a repository backend on the unified runtime surface instead of
branching per channel. The generic environment contract is
`ALGENTA_RUNTIME_REPOSITORY_INTELLIGENCE_BACKEND=package.module:attribute`.
The attribute can be either:

- a backend instance exposing the full repository runtime contract
- a zero-argument factory or class returning that backend

Python callers can also pass the same spec directly when constructing the
runtime:

```python
from algenta import Runtime

rt = Runtime(
    mode="local",
    repository_intelligence_backend="my_repo_backend.module:build_backend",
)
```

or register an already-instantiated backend explicitly:

```python
rt.register_repository_intelligence_backend(build_backend())
```

If neither a backend object nor a valid import spec is configured, repository
methods fail closed with `local_repository_intelligence_backend_required`.

Stored repository `DecisionPlan` revisions expose
`repository_analysis.planner_model_id`,
`repository_analysis.planner_execution_mode`, and
`repository_analysis.planner_provider_backend` so operators can audit whether a
patch plan came from the bounded deterministic local planner or a
provider-backed chat planner.

SDK clients on this hosted-runtime path already fall back automatically when an
older self-hosted node still returns `404` for `/v1/meta/contract`. Raw HTTP
callers should use `/openapi.json` and read `x-primary-data-query-contract` in
that case.

The same hosted runtime path also exposes the current lineage-aware control-plane
and persisted agent-run helpers through the runtime facade:

- `rt.get_audit_logs(...)` / `await rt.getAuditLogs({ ... })`
- `rt.get_audit_log_artifacts(...)` / `await rt.getAuditLogArtifacts({ ... })`
- `rt.list_execution_policy_snapshots()` / `await rt.listExecutionPolicySnapshots()`
- `rt.list_agent_runs(...)` / `await rt.listAgentRuns({ ... })`
- `rt.list_agent_run_checkpoints(run_id)` / `await rt.listAgentRunCheckpoints(runId)`
- `rt.query_agent_run_checkpoints(...)` / `await rt.queryAgentRunCheckpoints({ ... })`
- `rt.list_agent_run_mission_events(run_id, limit=...)` / `await rt.listAgentRunMissionEvents(runId, { limit })`
- `rt.query_agent_run_mission_events(...)` / `await rt.queryAgentRunMissionEvents({ ... })`
- `rt.list_agent_run_telemetry(run_id, limit=...)` / `await rt.listAgentRunTelemetry(runId, { limit })`
- `rt.query_agent_run_telemetry(...)` / `await rt.queryAgentRunTelemetry({ ... })`
- `rt.replay_agent_run(run_id, checkpoint_id=...)` / `await rt.replayAgentRun(runId, { checkpoint_id })`
- `rt.fork_agent_run(run_id, checkpoint_id=...)` / `await rt.forkAgentRun(runId, { checkpoint_id })`

That keeps the hosted local-runtime path aligned with the same manifest-first
operator and replay surfaces documented for the public SDKs instead of forcing
users back onto raw HTTP calls for lineage inspection or replay operations.

### Start the daemon runtime

```bash
de runtime start
de runtime status
de runtime manifest --format json
de runtime validate --format json
de runtime admin-modules --format json
de runtime admin-benchmarks --format json
de runtime modules --format json
de runtime functions text.tokenizer --format json
de runtime execute rerank_eval hit_rate_at_k --args-json '[[1,0,1,1,0],5]' --format json
```

## Mission local library tool mapping

If you are porting a Mission flow that uses the local Algenta library tools,
map those calls onto the public local/runtime-backed surfaces below.

| Mission functionality | Python local runtime | TypeScript local runtime | CLI | MCP |
| --- | --- | --- | --- | --- |
| `get_algenta_library_health` | `MojoRuntime(mode="local").health()` | `await new MojoRuntime({ mode: "local" }).health()` | `de runtime status` | No one-to-one MCP tool today |
| `get_algenta_runtime_proof` | `rt.get_runtime_manifest()`, `rt.get_runtime_modules()`, `rt.get_runtime_benchmarks()`, `rt.get_runtime_release_validation()` | `await runtime.getRuntimeManifest()`, `await runtime.getRuntimeModules()`, `await runtime.getRuntimeBenchmarks()`, `await runtime.getRuntimeReleaseValidation()` | `de runtime manifest`, `de runtime validate`, `de runtime admin-modules`, `de runtime admin-benchmarks` | `get_runtime_manifest`, `get_runtime_modules`, `get_runtime_benchmarks`, `get_runtime_release_validation` |
| `list_algenta_libraries` | `libraries(mode="local").names()` or `runtime.list_modules()` | `(await libraries({ mode: "local" })).names()` or `await runtime.listModules()` | `de runtime modules --format json` | `list_runtime_libraries(search=...)` |
| `inspect_algenta_library` | `runtime.list_functions("text.tokenizer")` | `await runtime.listFunctions("text.tokenizer")` | `de runtime functions text.tokenizer --format json` | `list_runtime_libraries(search="text.tokenizer")` |
| `get_algenta_library_module` | `catalog.module("text.tokenizer")` | `catalog.module("text.tokenizer")` | `de runtime functions <module> --format json` | `list_runtime_libraries(search="text.tokenizer")` |
| `execute_algenta_library` | `runtime.execute("rerank_eval", "precision_at_k", {"relevance": [1, 0, 1, 1], "k": 3})` or `catalog.module("text.tokenizer").word_tokenize("alpha beta")` | `await runtime.execute("rerank_eval", "precision_at_k", { relevance: [1, 0, 1, 1], k: 3 })` or `await catalog.module("text.tokenizer").word_tokenize("alpha beta")` | `de runtime execute rerank_eval precision_at_k --args-json '{"relevance":[1,0,1,1],"k":3}' --format json` | `execute_runtime_library(module="rerank_eval", function="precision_at_k", args={...})` |

Keep canonical module names when you inspect or execute the runtime surface.
Mission may expose attribute aliases such as `text_tokenizer`, but the runtime
inventory and CLI stay canonical: `text.tokenizer`, `vector_kernels.table`,
`vector_kernels.ranker`, `rerank_eval`, `kv_cache`, and the rest of the local
Mojo catalog.

`de runtime admin-benchmarks --format json` and `get_runtime_benchmarks()`
include benchmark-class `evidence_paths`, so the runtime proof surface carries
concrete artifact linkage for shipped benchmark claims instead of only code and
description labels.
That same proof surface currently publishes quality-gate benchmark classes `B6`
checkpoint and replay overhead, `B7` MCP tool latency, `B9` RAG retrieval
quality and latency, and `B10` decision workflow completion latency, plus
quality-gate SLO budgets `mcp_call_first_party`, `decision_plan_creation`, and
`replay`.
`B10` is currently backed by the Repository Intelligence workflow artifact at
`build/repository_intelligence_benchmark.json`.

Use the checked-in SDK examples when you want the Mission local-library
replacements in runnable code:

- [`python_runtime_library_flow.py`](/Users/angel/Developer/decision-engine/examples/multi-hop/python_runtime_library_flow.py)
- [`typescript_runtime_library_flow.ts`](/Users/angel/Developer/decision-engine/examples/multi-hop/typescript_runtime_library_flow.ts)
- [`mcp_runtime_library_sequence.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/mcp_runtime_library_sequence.json)
- [`mission_functionality_surface_map.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/mission_functionality_surface_map.json)

Use the local runtime library lane for direct deterministic compute only. For
governed multihop analytics and bridge-table SQL analysis, stay on the governed
`query`, `query-batch`, and `sql-report` surfaces documented in
[`multi-hop-joins.md`](/Users/angel/Developer/decision-engine/apps/docs/docs/api-reference/multi-hop-joins.md).

### Inspect local runtime history

```bash
de runtime history --limit 20
```

## What this page proves

- The simple primary local runtime exists in `algenta`
- The more advanced hosted-control-plane local runtime also exists in this repo
- These are both real, but they are not the same surface

The docs now lead with the simpler `Runtime.resolve() -> Runtime.query()` story and keep the daemon/device path as an advanced operating mode.
