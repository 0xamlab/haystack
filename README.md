# Algenta

<p align="center">
  <strong>Deterministic execution for structured data.</strong><br>
  Today Algenta is a hybrid system with a proven deterministic core. The primary path is
  <code>Runtime.resolve() -&gt; Runtime.query()</code>, and the target model is a local-first runtime
  that executes where your data lives.
</p>

<p align="center">
  <a href="https://algenta.ai"><img src="https://img.shields.io/badge/website-algenta.ai-1d4ed8" alt="Website"></a>
  <a href="https://docs.algenta.ai"><img src="https://img.shields.io/badge/docs-docs.algenta.ai-0f172a" alt="Docs"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-ACL_1.0-green" alt="License"></a>
</p>

## What Algenta is

Algenta is **not**:

- an LLM-to-SQL generator
- a semantic-model-first BI layer
- an agent framework

Algenta **is**:

- a deterministic execution layer for structured data
- a runtime that resolves intent into exact plans and executes them
- a backend/runtime repo with simulation, MCP, and local helper surfaces that still exist today

## Current truth, primary path, target model

### Current truth

This repository currently supports multiple real usage modes:

- **Deterministic data runtime**: `connect/register -> resolve -> verify -> query`
- **Simulation workflows**: `simulate`, `recommend`, jobs, runtime/device flows
- **Local helper APIs**: `map_data`, `query_data`, `simulate`, `decision`, `optimize`
- **MCP/agent integration**: broad tool surface across data, query, simulation, memory, and triggers

### Primary path

The path Algenta now pushes in docs and SDKs is:

```python
from algenta import Runtime

rt = Runtime()
rt.connect(
    [
        {"product_line": "Electronics", "revenue": 42193221},
        {"product_line": "Apparel", "revenue": 28114992},
    ],
    name="orders",
)

plan = rt.resolve(
    {
        "source_name": "orders",
        "metric": "revenue",
        "group_by": "product_line",
    }
)

result = rt.query(plan)
print(result.result)
```

This path is fully supported and validated today.

### Target model

Algenta is converging toward a **local-first deterministic runtime**:

- local execution is the default
- cloud/API execution is optional
- `resolve -> query` is the canonical surface
- simulation remains supported, but no longer defines the top-level product story

## Quickstart

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

The demo is deterministic, local, and does not require credentials.

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
from algenta import Runtime

rt = Runtime(mode="api", api_key="de_live_...")

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
from algenta import Runtime

rt = Runtime(mode="api", api_key="de_live_...")
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
- **Local helper APIs** through `map_data`, `query_data`, `simulate`, `decision`, `optimize`, `forecast`
- **Direct API client** through `from decision_engine import DecisionEngineClient`
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
- **`algenta-sdk`**: lower-level Python API SDK, imported as `decision_engine`
- **`decision-engine-sdk`**: TypeScript SDK with a runtime-first facade plus direct API client

Primary docs examples use:

```python
from algenta import Runtime
```

TypeScript now supports the same published runtime-first path:

```typescript
import { Runtime } from "decision-engine-sdk";

const rt = new Runtime();
```

Advanced/direct API docs use:

```python
from decision_engine import DecisionEngineClient
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
