---
sidebar_position: 2
---

# Runtime Quickstart

This quickstart is intentionally runtime-first. It shows the primary Algenta path as it exists today.

## What this proves

By the end of this guide you will have:

- installed the local-first package
- run the zero-friction demo
- connected local data
- resolved a deterministic plan
- queried that plan

## Step 1: Install the package

```bash
pip install algenta-core
```

## Step 2: Run the branded local demo

```bash
python -m algenta.demo
# or
algenta demo
```

The demo:

- runs locally
- requires no API key
- uses a bundled deterministic dataset
- prints the resolved plan and query result

## Step 3: Use the runtime in code

```python
from algenta import Runtime

rt = Runtime()
rt.connect(
    [
        {"product_line": "Electronics", "revenue": 42193221},
        {"product_line": "Apparel", "revenue": 28114992},
        {"product_line": "Home", "revenue": 19852111},
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

verified = rt.verify(plan)
if not verified.valid:
    raise RuntimeError(verified.errors)

result = rt.query(plan)
print(result.result)
```

## Step 4: Connect a real CSV file

If you want a branded terminal preflight before moving into code, run:

```bash
algenta import orders.csv --name orders
```

That validates local registration and schema discovery and prints a branded summary. It does not persist a session across separate CLI commands.

For related local exports, you can preview a bundle in one step:

```bash
algenta import orders.csv financial.csv ratings.csv
```

That prints a branded bundle summary with imported sources, explicit per-file failures, and deterministic shared-field overlap hints.

```python
from algenta import Runtime

rt = Runtime()
imported = rt.import_preview("orders.csv", name="orders")
print(imported.preview)

registration = imported.registration

plan = rt.resolve(
    {
        "source_name": registration.name,
        "metric": "revenue",
        "group_by": "product_line",
    }
)
result = rt.query(plan)
```

The same local runtime surface also accepts Parquet and Excel files directly:

```python
from algenta import Runtime

rt = Runtime()
orders = rt.connect("orders.parquet", name="orders_parquet")
price_book = rt.connect("price_book.xlsx", name="price_book")
```

You can also connect a local SQLite table on the same public runtime surface:

```python
from algenta import Runtime

rt = Runtime()
registration = rt.connect(
    {
        "provider": "sqlite",
        "path": "/data/orders.db",
        "table": "orders",
    },
    name="orders",
)

plan = rt.resolve(
    {
        "source_name": registration.name,
        "metric": "revenue",
        "group_by": "product_line",
    }
)
result = rt.query(plan)
```

Local Python runtime mode currently supports CSV, JSON, Parquet, Excel, SQLite descriptors, and in-memory records on the primary `resolve -> query` path.

## Step 5: Switch to API mode when needed

API mode is optional and explicit.

```bash
pip install "algenta-core[cloud]"
# or
pip install algenta-sdk
```

```python
from algenta import Runtime

rt = Runtime(mode="api", api_key="de_live_YOUR_KEY_HERE")

plan = rt.resolve(
    {
        "source_name": "orders",
        "metric": "revenue",
        "group_by": "product_line",
    }
)
result = rt.query(plan)
```

If you want to hit the hosted API directly, use the canonical Bearer contract:

```bash
curl https://api.algenta.ai/v1/resolve \
  -H "Authorization: Bearer de_live_YOUR_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "source_name": "orders",
    "metric": "revenue",
    "group_by": "product_line"
  }'
```

## Notes

- `verify()` is supported and recommended when you want explicit plan validation before execution.
- `Runtime()` defaults to local mode.
- `Runtime(api_key="de_live_...")` in Python, or `new Runtime({ apiKey: "de_live_..." })` in TypeScript, keeps execution local but can enforce a stored device license and local credits for offline hosted usage when the advanced runtime components are available.
- Simulation, MCP, and local helper APIs remain supported, but they are not the first path shown in the docs anymore.

## Next steps

- [Connect / Register Sources](/connect-register-sources)
- [Resolve](/resolve)
- [Query](/query)
- [Verify](/verify)
- [Trust Model](/trust-model)
