---
sidebar_position: 3
---

# Connect / Register Sources

This page covers the first step in the primary runtime path.

## Local mode

Use `Runtime.connect()` to attach data to a local runtime:

```python
from algenta import Runtime

rt = Runtime()
registration = rt.connect("orders.csv", name="orders")
parquet_registration = rt.connect("orders.parquet", name="orders_parquet")
excel_registration = rt.connect("price_book.xlsx", name="price_book")
print(registration.name, registration.row_count)
```

You can also connect records directly:

```python
registration = rt.connect(
    [
        {"product_line": "Electronics", "revenue": 42193221},
        {"product_line": "Apparel", "revenue": 28114992},
    ],
    name="orders",
)
```

And you can attach a local SQLite table without leaving the public runtime surface:

```python
registration = rt.connect(
    {
        "provider": "sqlite",
        "path": "/data/orders.db",
        "table": "orders",
    },
    name="orders",
)
```

Local Python runtime mode supports:
- CSV
- JSON
- Parquet
- Excel
- SQLite descriptors
- in-memory records

If you prefer an explicit read-only query, use a `connection_string` plus `query`:

```python
registration = rt.connect(
    {
        "type": "sqlite",
        "connection_string": "sqlite+pysqlite:////data/orders.db",
        "query": "SELECT product_line, revenue FROM orders",
    },
    name="orders_projection",
)
```

If you want an operator-facing import preview from the terminal first, use:

```bash
algenta import orders.csv --name orders
```

That branded CLI path validates local registration and schema discovery, then prints the source metadata and a copy-pasteable `Runtime()` snippet. It does not persist a local session across separate CLI runs.

You can also preview a related bundle:

```bash
algenta import orders.csv financial.csv ratings.csv
```

That bundle path keeps going even if one file is an explicit empty export or local validation error, and it reports those failures in the output instead of hiding them.

If you want the same bundled import behavior in code, you can mix local files and local SQLite descriptors:

```python
bundle = rt.import_bundle_preview(
    [
        "orders.csv",
        {
            "provider": "sqlite",
            "path": "/data/orders.db",
            "table": "orders",
        },
    ]
)
print(bundle.preview)
```

## API mode

In API mode, registration delegates to the direct API client and expects a structured source descriptor:

```python
from algenta import Runtime

rt = Runtime(mode="api", api_key="de_live_...")
registration = rt.connect(
    {
        "type": "csv",
        "name": "orders",
        "path": "/data/orders.csv",
    }
)
```

The same path is what you use for broader hosted connectors such as databases:

```python
from algenta import Runtime

rt = Runtime(mode="api", api_key="de_live_...")
registration = rt.connect(
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

This API-mode descriptor path is also where object-storage and REST-backed connectors fit. The runtime-first contract stays the same:

- pass a structured descriptor to `Runtime.connect(...)`
- let the hosted connector layer validate and register it
- continue with `resolve -> verify -> query`

## What this proves

- local mode can connect file-backed, SQLite-backed, or in-memory sources without credentials
- API mode can register files, hosted database descriptors, object-storage descriptors, and REST descriptors through the service
- the same runtime surface supports both modes
