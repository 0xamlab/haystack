---
sidebar_position: 1
---

# Python SDK

Algenta now has two Python surfaces:

1. **Primary surface**: `algenta.Runtime`
2. **Advanced direct API surface**: `decision_engine.DecisionEngineClient`

Use `Runtime` first unless you explicitly need the lower-level direct API client.

## Installation

### Local-first runtime package

```bash
pip install algenta-core
```

### Optional API mode support

```bash
pip install "algenta-core[cloud]"
# or
pip install algenta-sdk
```

## Primary path: `Runtime`

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

verified = rt.verify(plan)
if not verified.valid:
    raise RuntimeError(verified.errors)

result = rt.query(plan)
print(result.result)
```

## Local mode

Local mode is the default:

```python
from algenta import Runtime

rt = Runtime()
registration = rt.connect("orders.csv", name="orders")
parquet_registration = rt.connect("orders.parquet", name="orders_parquet")
excel_registration = rt.connect("price_book.xlsx", name="price_book")
plan = rt.resolve({"source_name": registration.name, "metric": "revenue"})
result = rt.query(plan)
```

What local mode proves:

- no API key required
- deterministic plan execution
- local data stays in your environment
- local file support includes CSV, JSON, Parquet, and Excel
- local descriptors include SQLite and in-memory records

Local mode on the public Python runtime also supports deterministic SQLite descriptors:

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
plan = rt.resolve({"source_name": registration.name, "metric": "revenue"})
result = rt.query(plan)
```

## API mode

API mode uses the direct Algenta API but keeps the same `Runtime` shape:

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

## Advanced surface: direct API client

Use the lower-level client when you want full direct access to the API surface, including simulation jobs and advanced request construction.

```python
from decision_engine import DecisionEngineClient

client = DecisionEngineClient(api_key="de_live_...")

plan = client.resolve(
    source_name="orders",
    metric="revenue",
    group_by="product_line",
)
verified = client.verify(plan.model_dump())
result = client.query(plan.model_dump())
```

## When to use which surface

### Use `Runtime` when:

- you want the primary documented path
- you want local-first behavior
- you want the same top-level shape in local and API mode

### Use `DecisionEngineClient` when:

- you need the full direct API surface
- you want to call simulation, jobs, or advanced endpoints directly
- you want lower-level control over request payloads
