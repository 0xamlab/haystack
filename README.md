# Algenta

<p align="center">
  <strong>Algenta is the engine — one self-hosted, deterministic computational runtime + SDK that specialized products build on.</strong><br>
  Deploy on your own infrastructure and integrate over HTTP API or SDK; the local runtime is a development/embedded surface.
</p>

<p align="center">
  <a href="https://algenta.ai"><img src="https://img.shields.io/badge/website-algenta.ai-1d4ed8" alt="Website"></a>
  <a href="https://docs.algenta.ai"><img src="https://img.shields.io/badge/docs-docs.algenta.ai-0f172a" alt="Docs"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-ACL_1.0-green" alt="License"></a>
</p>

## What Algenta is

Algenta is the **engine**, not a vertical application. It is a local-first deterministic
**computational intelligence runtime** — a large library of mathematical/operational functions and
high-performance libraries, plus simulation, decision planning, an agent runtime, decision memory,
and governed execution — exposed through one universal **API / SDK / MCP** surface, with metering,
auth, BYOK, and enterprise controls.

### Algenta and its products

Specialized products **consume the Algenta SDK** — they are surfaces on top of the one engine, not
the engine itself:

| Product | Domain |
| --- | --- |
| **Codna** | coding — repository intelligence: triage, fix / PR-repair, blast-radius, simulate |
| **Mission** | API-first local integration (`:8000` API + MCP stack) |
| **Cohenta** | marketing intelligence |
| **Decimas** | trading / market simulation |
| **Escrypto** | crypto governance |

This repository is **Algenta** (the engine + its API/worker/SDK/MCP/local-runtime surfaces). Each
product lives in its own repo and talks to Algenta over the API/SDK.

Algenta is **not**:

- an LLM-to-SQL generator
- a semantic-model-first BI layer
- an agent framework
- a `pip install` product pretending to be a platform

Official position:

> Algenta is a self-hosted decision engine you deploy on your infrastructure.
> Integrate via API or SDK. Run locally for development if needed.

Enterprise deployment defaults are now explicit:

- self-hosted by default
- cloud optional
- strict privacy profile available with `ALGENTA_DEPLOYMENT_MODE=air_gapped`
- `ALGENTA_DISABLE_TELEMETRY=1` disables outbound/vendor telemetry but keeps local audit
- `ALGENTA_API_PUBLIC_BASE_URL` and optional `ALGENTA_APP_BASE_URL` control user-facing self-hosted links without cloud fallback
- `GET /v1/admin/privacy-report` is the operator proof endpoint

## Self-hosted service

If you want to deploy Algenta on your own infrastructure, start with the self-hosted service path:

- `api + worker + postgres + redis + object storage`
- deployed with Docker Compose
- integrate over HTTP API or SDK after the service is running
- no SDK or Python install required for first use

Start with [Quickstart](./apps/docs/docs/quickstart.md), then use [Setup & Configuration](./apps/docs/docs/self-hosting.md) for production settings.

### First 2-minute success path

```bash
curl -sSL https://algenta.ai/install.sh | bash
curl http://localhost:8000/v1/health
```

The installer prints:

- the API URL
- a bootstrap API key
- a concrete `POST /v1/simulate` example

If you are evaluating the product, start there.

For recurring workloads, use the bootstrap key only to create a bounded-lifetime
replacement key:

```bash
curl -X POST http://localhost:8000/v1/api-keys \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"label":"mission-runtime","expires_at":"2028-05-19T00:00:00Z","device_limit":3}'
```

The returned `raw_key` value is shown only once. Store it, along with the
returned `id`, `key_prefix`, `device_limit`, and `expires_at`, before revoking
the bootstrap key, then replace `ALGENTA_API_KEY` with that replacement key for
steady-state service access. Use that replacement key for steady-state service
access instead of the bootstrap credential.

An explicit `device_limit` also binds ordinary hosted API traffic for that key,
not just local runtime/device registration. The SDKs send the stable device
headers automatically. Raw HTTP callers using capped keys must send
`X-Algenta-Device-Id`, `X-Algenta-Platform`, and
`X-Algenta-Hostname-Hash` on authenticated requests. The first successful
hosted request for a new capped device also returns
`X-Algenta-Device-Binding-Token`; store and replay that token on later
requests from the same device. Reusing the same device ID with different non-empty machine fingerprint
metadata fails closed with `device_identity_mismatch`.

## Current truth, primary path, target model

### Current truth

This repository currently supports multiple real usage modes:

- **Self-hosted service deployment**: `api + worker + postgres + redis + object storage`
- **Deterministic data runtime**: `discover -> summarize -> resolve -> verify -> query`
- **Simulation workflows**: `simulate`, `recommend`, jobs, runtime/device flows
- **MCP/agent integration**: broad tool surface across data, query, simulation, memory, and triggers

### Primary path

The primary published product path is:

1. deploy the self-hosted service with `curl -sSL https://algenta.ai/install.sh | bash`
2. verify the API with `GET /v1/health`
3. run the first decision through `POST /v1/simulate`, or run the first governed dataset query through `GET /v1/data?search=...&compact=1` -> `GET /v1/data/{dataset_id}/summary` -> `POST /v1/query`
4. integrate over HTTP or SDK against the running service

If the workflow needs customer-agnostic routing across governed data, MCP,
skills, native tools, or runtime libraries, start with
`POST /v1/capabilities/route` and the checked-in examples in
[`examples/capability-plane/README.md`](./examples/capability-plane/README.md).
`algenta_managed` routes can execute through Algenta; `client_managed` routes
must execute in the customer app or adapter path and fail closed otherwise.
For the focused repo proof bundle, run `make capability-plane-verify`.

The local `Runtime()` path remains fully supported, but it is the development/runtime surface rather than the product install path.

### Target model

Algenta is converging toward a **service-first deterministic execution system**:

- self-hosted deployment is the primary product contract
- HTTP API is the default integration surface
- SDKs and local runtime remain supported secondary interfaces
- governed discovery/query and simulation workflows share the same backend/runtime core

## Development quickstart

This section is the **development** surface. If you are deploying the product, start with [Quickstart](./apps/docs/docs/quickstart.md).

### Mission local API + MCP stack

If you are bringing up the local `:8000` API + MCP stack for Mission or another
API-first local integration, use the repo launcher:

```bash
ALGENTA_ENV_FILE=/absolute/path/to/.env.local ./scripts/start-local.sh
```

If port `8000` is already occupied locally, override the API port instead of
reusing or killing the conflicting service:

```bash
ALGENTA_ENV_FILE=/absolute/path/to/.env.local ALGENTA_API_PORT=8010 ALGENTA_MCP_PORT=8011 ./scripts/start-local.sh
```

When you are done with local stacks, stop all launcher-managed pairs cleanly:

```bash
./scripts/stop-local.sh
```

Or stop a specific pair only:

```bash
ALGENTA_API_PORT=8060 ALGENTA_MCP_PORT=8061 ./scripts/stop-local.sh
```

To inspect the current launcher-managed stacks and see whether each API or MCP
entry is active, stale, missing a lease, or missing a listener:

```bash
./scripts/status-local.sh
```

For automation, you can request structured JSON instead:

```bash
./scripts/status-local.sh --format json
```

`scripts/start-local.sh` loads `ALGENTA_ENV_FILE` (or `DE_ENV_FILE`) before
falling back to `decision-engine/.env`. When
`ALGENTA_LLM_PROVIDER_MODELS_JSON` is unset, the script auto-derives a local
provider registry from available provider credentials such as
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`,
`COHERE_API_KEY`, `GROQ_API_KEY`, and `XAI_API_KEY`, then exposes
`provider.router` on `/v1/models`. The launcher now fail-closes if
`ALGENTA_LLM_PROVIDER_MODELS_JSON` is malformed, and it only reports
`provider.router enabled` when the effective registry actually contains that
router entry. Explicit startup env overrides such as `ALGENTA_API_PORT=...`,
`ALGENTA_MCP_PORT=...`, and `ALGENTA_LLM_PROVIDER_MODELS_JSON=...` win over
values inside the loaded env file. It launches the API and MCP processes through
`scripts/detach_process.py` so they survive the startup shell itself. It resolves the standalone MCP HTTP/SSE dependencies from
`requirements-mcp.txt` via isolated `uv run` before launching `/mcp/sse`. The
launcher also fails closed if either the API `/v1/health` endpoint or the
standalone MCP `/mcp/tools` endpoint never becomes ready. If port `8000` or the
chosen MCP port is already occupied by an unrelated process, the launcher now
refuses to clobber it and only stops prior launcher-managed processes recorded
in `build/start-local/*.pid`. Same-port reruns retire the previous API and MCP
pair via per-port lease files under `build/start-local/*.lease`, so restart does
not rely only on cross-session `kill`. The launcher also prunes orphaned
`build/start-local/*.pid` files when the matching lease is gone and the recorded
process is no longer alive. If no provider credentials are present, it falls
back to a local Ollama-backed chat route when available.

### Repository Intelligence channel parity proof

To run the focused live Repository Intelligence parity proof across the CLI,
Python SDK, MCP server, Algenta client/runtime, and TypeScript client/runtime
surfaces, use the repo-owned target:

```bash
make repository-intelligence-channel-parity
```

The run writes the consolidated parity artifact to
`build/repository_intelligence_channel_parity_summary.json` and per-channel logs
to `build/repository_intelligence_channel_parity_logs/`.

If you need to override the default repository-only filter, output path, log
directory, or requested job count, use the Make variables:

```bash
make repository-intelligence-channel-parity \
  RI_CHANNEL_PARITY_FILTER=repository \
  RI_CHANNEL_PARITY_OUTPUT=build/repository_intelligence_channel_parity_summary.json \
  RI_CHANNEL_PARITY_LOGS_DIR=build/repository_intelligence_channel_parity_logs \
  RI_CHANNEL_PARITY_JOBS=1
```

### 1. Install the local runtime package

```bash
pip install algenta-core
```

### 2. Run the zero-friction demo

```bash
python -m algenta.demo
# or
algenta demo
```

In a real terminal, `algenta demo` now opens an interactive scenario picker and walks
through registration, resolve, verify, query, and guardrail behavior step by step.
The demo is deterministic, local, and does not require credentials.

Useful shortcuts:

```bash
algenta demo --list
algenta demo --all --no-interactive
algenta demo --scenario region --no-interactive
algenta demo --scenario canada_filter --no-interactive
algenta demo --scenario guardrail --no-interactive
```

Inside the interactive menu, use the explicit actions `all`, `recipes`, and `quit`.
You can also chain them, for example `1,recipes` or `all,quit`.

### 3. Use the primary path in code

```python
from algenta import Runtime

rt = Runtime()
rt.connect("orders.csv", name="orders")
rt.connect("orders.parquet", name="orders_parquet")
rt.connect("price_book.xlsx", name="price_book")

plan = rt.resolve(
    {
        "source_name": "orders",
        "metric": "revenue",
        "group_by": "product_line",
    }
)

verified = rt.verify(plan)
if not verified.valid:
    raise RuntimeError(verified.errors)

result = rt.query(plan)
print(result.result)
```

If you want a branded terminal-side import preflight first:

```bash
algenta import orders.csv --name orders
```

That validates local registration and schema discovery and prints the source metadata plus a copy-pasteable `Runtime()` snippet. It does not persist a local runtime session across separate CLI commands.

You can also preview a related local bundle:

```bash
algenta import orders.csv financial.csv ratings.csv
```

That prints a branded multi-source summary with imported sources, explicit per-file failures, and deterministic shared-field overlap hints.

For the hosted Algenta data/query path from the terminal:

```bash
de contract
de data list --search orders --compact --limit 5
de data summary orders_facts
de data query-batch batch_request.json
de data sql-report sql_report_request.json
```

For the same branded onboarding step in Python:

```python
from algenta import Runtime

rt = Runtime()
imported = rt.import_preview("orders.csv", name="orders")
print(imported.preview)
```

## Local vs API mode

### Local mode

Local mode is the default:

```python
from algenta import Runtime

rt = Runtime()
rt.connect("orders.csv", name="orders")
plan = rt.resolve({"source_name": "orders", "metric": "revenue"})
result = rt.query(plan)
```

Local mode can also read local SQLite tables, Parquet files, and Excel workbooks deterministically:

```python
from algenta import Runtime

rt = Runtime()
rt.connect(
    {
        "provider": "sqlite",
        "path": "/data/orders.db",
        "table": "orders",
    },
    name="orders",
)
plan = rt.resolve({"source_name": "orders", "metric": "revenue"})
result = rt.query(plan)
```

Local mode:

- runs against connected local data
- requires no API key
- is deterministic and self-contained
- supports local CSV, JSON, Parquet, Excel, in-memory records, and local SQLite descriptors on the public Python runtime path
- stays outside hosted device-license and credit-bucket enforcement unless you explicitly opt into hosted local mode with an API key

### API mode

API mode uses the direct Algenta API through the lower-level SDK:

```bash
pip install "algenta-core[cloud]"
# or
pip install algenta-sdk
```

```python
import os

from algenta import Runtime

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

rt = Runtime(mode="api", api_key=api_key)

plan = rt.resolve(
    {
        "source_name": "orders",
        "metric": "revenue",
        "group_by": "product_line",
    }
)
result = rt.query(plan)
```

API mode is the right choice when you want:

- the hosted control plane
- registered source management through the API
- the full direct API surface

That includes broader structured source descriptors such as hosted databases, object storage, and REST-backed sources:

```python
import os

from algenta import Runtime

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

rt = Runtime(mode="api", api_key=api_key)
rt.connect(
    {
        "type": "postgres",
        "location": {
            "host": "db.example.com",
            "port": 5432,
            "database": "orders",
            "schema": "public",
            "table": "orders",
        },
        "auth": {
            "credentials": {
                "user": "analytics",
                "password": "secret",
            }
        },
    },
    name="orders_pg",
)
```

The same runtime-first `connect(...)` surface is what you use for descriptors like:

- PostgreSQL / MySQL tables
- warehouse-style structured connectors
- S3 / object-storage file descriptors
- REST resources exposed through hosted connector adapters

### Self-hosted mode

Use `self_hosted` when you want the same governed SDK contract against your own Algenta deployment:

```python
import os

from algenta import Runtime

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

rt = Runtime(mode="self_hosted", api_key=api_key, base_url="http://localhost:8000")
```

`self_hosted` never falls back to the hosted control plane. You must provide an explicit
`base_url` and the SDK will use that service directly.

## Connector onboarding and dataset operations

Saved connectors are the production path:

```python
import os

from algenta import Runtime

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

rt = Runtime(mode="self_hosted", api_key=api_key, base_url="http://localhost:8000")

connector = rt.create_connector(
    name="Warehouse Postgres",
    connector_type="postgres",
    config={
        "host": "db.internal",
        "port": 5432,
        "database": "analytics",
        "user": "readonly",
        "password": "secret",
    },
)

connector = rt.update_connector(
    connector.id,
    description="analytics warehouse",
    visibility="workspace",
)
rt.test_connector(connector.id)
preview = rt.browse_connector(connector.id)
dataset = rt.connect(
    connector_id=connector.id,
    dataset_name="warehouse_orders",
    selection={"schema": "public", "table": "orders"},
)

datasets = rt.list_datasets()
refreshed = rt.refresh_dataset(dataset.dataset_id)
dataset_detail = rt.get_dataset(dataset.dataset_id)
dataset_summary = rt.get_dataset_summary(dataset.dataset_id)
connector_detail = rt.get_connector(connector.id)
rt.delete_dataset(dataset.dataset_id)
rt.delete_connector(connector.id)
```

TypeScript uses the same governed self-hosted runtime contract:

```typescript
import { Runtime } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const rt = new Runtime({
  mode: "self_hosted",
  apiKey,
  baseUrl: "http://localhost:8000",
});

const connector = await rt.createConnector({
  name: "Warehouse Postgres",
  connectorType: "postgres",
  config: {
    host: "db.internal",
    database: "analytics",
  },
});

await rt.testConnector(connector.id);
await rt.browseConnector(connector.id);
const dataset = await rt.connect(null, {
  connectorId: connector.id,
  name: "warehouse_orders",
  selection: { schema: "public", table: "orders" },
});
await rt.listDatasets();
await rt.refreshDataset(dataset.dataset_id!);
await rt.getDatasetSummary(dataset.dataset_id!);
```

Repository intelligence follows the same governed connector path:

```typescript
const snapshot = await rt.createRepositorySnapshot("repo_123", {
  ref: "main",
  include_patterns: ["apps/**", "packages/**", "tests/**"],
  exclude_patterns: ["**/node_modules/**", "**/dist/**"],
});

const triage = await rt.triageRepository("repo_123", {
  snapshot_id: snapshot.snapshot_id,
  signals: {
    issue_text: "Production regression after the latest deploy",
    failing_tests: ["tests/test_repository_intelligence_service.py::test_simulate_requires_patch_impact"],
    changed_files: ["apps/api_server/services/repository_intelligence.py"],
  },
});

const planRevision = await rt.createRepositoryDecisionPlan("repo_123", {
  snapshot_id: snapshot.snapshot_id,
  workspace_evidence_bundle_ref: triage.workspace_evidence_bundle_ref,
});

const simulation = await rt.simulateRepository("repo_123", {
  snapshot_id: snapshot.snapshot_id,
  decision_plan_id: planRevision.decision_plan_id,
  runs: 5000,
  seed: 42,
});

const patchOnly = await rt.applyRepository("repo_123", {
  snapshot_id: snapshot.snapshot_id,
  decision_plan_id: planRevision.decision_plan_id,
  simulation_id: String(simulation.validated_inputs?.simulation_id),
  mode: "patch_only",
});
```

The repository flow stays artifact-first and governed:
`RepositorySnapshot -> WorkspaceEvidenceBundle -> DecisionPlan -> PatchImpactReport -> DecisionEnvelope -> Apply gate`.

For large inventories, use the paginated iterators or opt into automatic multi-page fetches:

```python
all_connectors = rt.list_connectors(all_pages=True)
first_five_datasets = rt.list_datasets(all_pages=True, max_items=5)

for connector in rt.iter_connectors(limit=100):
    print(connector.id, connector.connector_type)
```

Filtered discovery and low-token dataset selection are also first-class:

```python
datasets = rt.list_datasets(search="orders", status="ready", source_name="warehouse_postgres", compact=True)
summary = rt.get_dataset_summary(datasets.datasets[0].dataset_id)
```

```typescript
const datasets = await rt.listDatasets({
  search: "orders",
  status: "ready",
  sourceName: "warehouse_postgres",
  compact: true,
});
const summary = await rt.getDatasetSummary(datasets.datasets[0].dataset_id);
```

For governed query execution, the public clients now expose exact-query metadata,
batch exact queries, and constrained SQL reports:

```python
contract = client.get_contract()
query = client.query_with_metadata({
    "dataset_id": "orders_facts",
    "filter": {
        "time_filter": "last_year",
        "conditions": [{"dimension_hint": "status", "op": "eq", "value": "completed"}],
    },
    "metric": {"role": "metric", "hint": "gross_revenue"},
    "aggregation": "sum",
})
batch = client.query_batch(
    {
        "defaults": {
            "dataset_id": "orders_facts",
            "filter": {
                "time_filter": "last_year",
                "conditions": [{"dimension_hint": "status", "op": "eq", "value": "completed"}],
            },
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
```

```typescript
const contract = await client.getContract();
const query = await client.queryWithMetadata({
  dataset_id: "orders_facts",
  filter: {
    time_filter: "last_year",
    conditions: [{ dimension_hint: "status", op: "eq", value: "completed" }],
  },
  metric: { role: "metric", hint: "gross_revenue" },
  aggregation: "sum",
});
const batch = await client.queryBatch({
  defaults: {
    dataset_id: "orders_facts",
    filter: {
      time_filter: "last_year",
      conditions: [{ dimension_hint: "status", op: "eq", value: "completed" }],
    },
  },
  queries: [
    { key: "completed_orders", request: { metric: { role: "metric", hint: "order_count" }, aggregation: "sum" } },
    { key: "gross_revenue", request: { metric: { role: "metric", hint: "gross_revenue" }, aggregation: "sum" } },
  ],
});
const report = await client.querySqlReport({
  sources: [{ dataset_id: "orders_facts", alias: "orders" }],
  sql: "select order_month, gross_revenue from orders",
  max_rows: 100,
});
```

`get_contract()` / `getContract()` now also handles older self-hosted nodes
that still return `404` for `/v1/meta/contract` by falling back to
`/openapi.json` and reading `x-primary-data-query-contract`.

For explicit multihop and bridge-table execution, see
[Multi-hop Joins](./apps/docs/docs/api-reference/multi-hop-joins.md) and the
checked-in request files under
[examples/multi-hop](./examples/multi-hop/README.md). Those examples show the
exact `join_path` contract, the `6`-hop (`7` table) ceiling, the current
`de data query-batch` CLI entrypoint, and when to move to
`query_sql_report()` instead of forcing everything through `query()`.

The governed filter shape is a **record-filter contract** over normalized rows,
not a SQL predicate tree. That keeps `time_filter` plus `conditions[]`
portable across SQL databases, Redis snapshots, files, and API-backed datasets.
The same operator families and validation rules are also published through
`PRIMARY_DATA_QUERY_CONTRACT.governed_filter_contract` and `/v1/meta/contract`
for raw consumers that need machine-readable filter introspection.

Why this is the production path:

- durable audit and lineage
- stable refresh/reload behavior
- explicit support/debugging handle (`connector_id`)
- clean attribution and governance boundaries

Inline connector descriptors are onboarding and preview only:

```python
import os

from algenta import Runtime

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

rt = Runtime(mode="api", api_key=api_key)
preview = rt.browse_connector(
    connector={
        "type": "redis",
        "url": "redis://localhost:6379",
    }
)
```

Rules:

- `test_connector(connector=...)` is allowed for preview
- `browse_connector(connector=...)` is allowed for preview
- `connect(connector=...)` requires `persist=True`
- repeated inline previews are rate limited

The SDK uses direct non-persistent preview endpoints when the backend supports them.
If an older backend does not expose that contract yet, the SDK falls back to the
temporary connector flow and then cleans it up immediately. The runtime also
caches preview-route capability for a short window, so older backends do not
pay the same failed preview probe on every distinct inline preview.
On the API side, successful inline preview tests and browse results are also
cached briefly per org and connector config to avoid re-running the same
connectivity or discovery work during short onboarding bursts. Concurrent
identical inline preview requests are also coalesced so the backend does the
real connector work once per key while other callers await the same result.
When multiple API workers share Redis, successful preview results are reused
across workers and the same key is coordinated through a short Redis lock, so
duplicate onboarding work stays bounded beyond a single process.
Saved connector `test` and `browse` requests also coalesce duplicate in-flight
work and use a short cross-worker handoff window, so the governed production
path avoids repeated backend connector work during UI or agent bursts without
turning those routes into long-lived caches.

That keeps saved connectors as the production path while avoiding unnecessary
create/test/browse/delete churn for preview-capable backends.

Saved connector and dataset reads also use a short-lived SDK cache for repeated
reads in the same runtime session. The TTL is `5s`, and writes invalidate the
affected cache entries immediately, so repeated UI or agent reads stay fast
without holding stale state for long-lived workflows.

## Runtime-backed Mojo libraries

The public package also exposes the executable Mojo library surface without shipping source:

```python
from algenta import libraries

catalog = libraries(mode="local", auto_start_daemon=False)
modules = catalog.list_modules()
functions = catalog.list_functions("ab_testing")
module = catalog.module("ab_testing")
sample = catalog.ab_testing.sample_size_proportion(
    p1=0.10,
    p2=0.12,
    alpha=0.05,
    power=0.8,
)
```

Important boundaries:

- the library catalog is backed by the executable runtime inventory
- Python `from algenta import libraries` stays local/runtime-backed
- Python `libraries()` and `MojoRuntime` stay local/runtime-backed, accept local `api_key` and `base_url` for licensed local execution, and still reject non-local modes
- TypeScript `libraries()` and `MojoRuntime` stay local/runtime-backed in this rollout
- start the local runtime daemon before using the TypeScript library surface
- hosted or self-hosted generic Mojo dispatch is not part of this surface
- missing runtime or missing library dispatch fails closed

TypeScript clients can use the same local/runtime-backed surface without importing or exposing Mojo source:

```typescript
import { libraries } from "algenta-sdk";

const catalog = await libraries({
  mode: "local",
  tcpAddress: process.env.ALGENTA_DAEMON_TCP ?? "127.0.0.1:50099",
});

const modules = catalog.listModules();
const sample = await catalog.ab_testing.sample_size_proportion({
  p1: 0.10,
  p2: 0.12,
  alpha: 0.05,
  power: 0.8,
});
```

The same local/runtime-backed library surface is also available through the CLI
and MCP layer:

```bash
de runtime modules --format json
de runtime functions text.tokenizer --format json
de runtime execute rerank_eval hit_rate_at_k --args-json '[[1,0,1,1,0],5]' --format json
de llm chat chat_request.json --stream --format json
de llm responses responses_request.json --stream
de agent-runs events <run_id> --stream --format json
```

- MCP `list_runtime_libraries`
- MCP `execute_runtime_library`

You can benchmark the public catalog path directly:

```bash
make bench-algenta-mojo-catalog
```

And benchmark the inline connector preview fast path directly:

```bash
make bench-algenta-connector-preview
```

You can also benchmark repeated saved connector and dataset reads:

```bash
make bench-algenta-runtime-read-cache
```

And you can benchmark the local exact `connect -> resolve -> query -> verify`
path directly:

```bash
make bench-algenta-local-runtime-exact
```

And you can benchmark the local registration path directly:

```bash
make bench-algenta-local-connect
```

And you can benchmark the API exact resolve fast path directly:

```bash
make bench-algenta-api-exact-resolve
```

And you can benchmark the public API payload coercion helpers directly:

```bash
make bench-algenta-api-payload
```

The benchmarks write JSON artifacts under `build/`, including:

- `build/algenta_mojo_catalog_benchmark.json`
- `build/algenta_runtime_read_cache_benchmark.json`
- `build/algenta_local_runtime_exact_benchmark.json`
- `build/algenta_local_connect_benchmark.json`
- `build/algenta_api_exact_resolve_benchmark.json`
- `build/algenta_api_payload_benchmark.json`

You can also benchmark the cold public package import path:

```bash
make bench-algenta-import
```

That writes `build/algenta_import_benchmark.json`, including:

- cold `import algenta`
- cold lightweight export resolution such as `algenta.QueryOutput`
- cold lightweight onboarding export resolution such as `algenta.ConnectorMetadata`
- cold heavy runtime export resolution such as `algenta.Runtime`

And you can benchmark the cold public `decision_engine` package import path too:

```bash
make bench-decision-engine-import
```

That writes `build/decision_engine_import_benchmark.json`, including:

- cold `import decision_engine`
- cold lightweight model resolution such as `decision_engine.QueryResult`
- cold lightweight onboarding model resolution such as `decision_engine.ConnectorInfo`
- cold async client resolution without loading the sync client or model families
- cold sync client resolution without loading the async client or model families

And you can benchmark client construction itself without issuing a request:

```bash
make bench-decision-engine-client-init
```

That writes `build/decision_engine_client_init_benchmark.json`, including:

- cold `AlgentaClient(api_key=...)` construction
- cold `AsyncAlgentaClient(api_key=...)` construction
- whether constructor-only startup still loads `httpx`
- whether the lazy transport wrapper loads without forcing the real HTTP client

## MCP integration

Algenta already exposes a strong MCP surface for agent workflows. Today it includes tools across:

- data onboarding and registration
- deterministic query and verification
- simulation and decision workflows
- memory and trigger operations

MCP is a supported surface, but it is not the top-level product narrative. The primary runtime story remains
`resolve -> query`.

See:

- [MCP docs](apps/docs/docs/mcp.md)
- [Claude/Codex example](examples/claude-desktop/README.md)

## Supported secondary modes

The following surfaces remain supported and tested:

- **Simulation workflows** through `/v1/simulate`, `/v1/recommend`, `/v1/jobs`
- **Local helper APIs** through `map_data`, `list_datasets`, `get_dataset_summary`, `query_data`, `query_with_metadata`, `query_batch`, `query_sql_report`, `simulate`, `decision`, `optimize`, `forecast`
- **Direct API client** through `from decision_engine import AlgentaClient`
- **Runtime daemon/device flows** through `apps/runtime` and the local runtime verifier scripts

These are real surfaces. They are not removed. They are just no longer the primary path we recommend first.

## Self-host and local runtime

This repository includes the backend/runtime code needed for:

- API server
- worker
- local runtime
- source registry and deterministic query surfaces
- docs and examples

The web interface is maintained outside this repository.

If you want hosted control plane plus local execution, see:

- [Local Runtime docs](apps/docs/docs/integrations/local-runtime.md)
- [`scripts/verify_local_api_key_runtime.py`](scripts/verify_local_api_key_runtime.py)

## Package and import truth

Current package story:

- **`algenta-core`**: local-first package that owns the `algenta` import namespace
- **`algenta-sdk` (PyPI)**: lower-level Python API SDK, imported as `decision_engine`
- **`algenta-sdk` (npm)**: TypeScript SDK with a runtime-first facade plus direct API client

Primary docs examples use:

```python
from algenta import Runtime
```

TypeScript now supports the same published runtime-first path:

```typescript
import { Runtime } from "algenta-sdk";

const rt = new Runtime();
```

That constructor is the local/runtime-first surface. For Cloud Managed API usage,
use `AlgentaClient` / `DecisionEngineClient`. For `self_hosted` and `air_gapped`,
pass an explicit self-hosted `baseUrl`; private profiles fail closed and do not
silently fall back to Algenta cloud.

Repo-root JavaScript package commands are now valid for the shipped JS surfaces
in this checkout:

```bash
pnpm install
pnpm lint
pnpm test
pnpm build
```

Those commands bootstrap and validate `packages/ts-sdk` and `apps/gateway`.
Use Node.js 22+ from the repo root so both packages share one operator path.

Advanced/direct API docs use:

```python
from decision_engine import AlgentaClient
```

## Competitor fit

Algenta aims to be:

- as easy to start in Python as Vanna
- as disciplined to integrate as Cube
- as MCP/tool-friendly as LlamaIndex

without becoming:

- an LLM-to-SQL generator
- a semantic-model-first BI layer
- an agent framework

See the full compatibility breakdown in [Competitor Compatibility](apps/docs/docs/competitor-compatibility.md).

## Validation snapshot

The backend/runtime repo is validated with:

- focused unit tests on the `algenta.Runtime` facade and demo
- repo-wide pytest coverage
- the strongest repo-native integration gate:

```bash
python3 -u tests/integration/test_go_live_full_real.py --parallel-tasks 4 --mojo-workers 4 --mojo-timeout 30
```

- source-matrix runtime benchmark
- uploaded CSV exact/spec/warm benchmarks
- column-rank boundary benchmark
- Mojo libraries A-Z suite

## Development

```bash
git clone https://github.com/algenta/decision-engine
cd decision-engine

python3 -m pytest tests -q
python3 -u tests/integration/test_go_live_full_real.py --parallel-tasks 4 --mojo-workers 4 --mojo-timeout 30
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for repository contribution guidance.
