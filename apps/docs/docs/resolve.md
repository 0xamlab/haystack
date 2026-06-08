---
sidebar_position: 4
---

# Resolve

`resolve()` converts structured intent into an exact plan.

## Discovery-first flow

For the first turn against hosted or self-hosted data, select the dataset before you resolve:

This API-mode snippet is the Cloud Managed path. In `self_hosted` and
`air_gapped`, use an explicit self-hosted `base_url` for API mode; private
profiles fail closed instead of silently falling back to Algenta cloud.

```python
import os

from algenta import Runtime

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

rt = Runtime(mode="api", api_key=api_key)
datasets = rt.list_datasets(search="orders", compact=True)
summary = rt.get_dataset_summary(datasets.datasets[0].dataset_id)
```

That keeps dataset selection low-token before you ask the runtime to resolve an exact plan.

If you are integrating against a hosted or self-hosted service for the first
time, inspect the live contract first with `get_contract()` / `getContract()` or
`GET /v1/meta/contract`.

SDK clients already handle older self-hosted nodes that still return `404`
there by falling back to `/openapi.json` and reading
`x-primary-data-query-contract`. Raw HTTP callers should do the same.

## Local example

```python
from algenta import Runtime

rt = Runtime()
rt.connect("orders.csv", name="orders")

plan = rt.resolve(
    {
        "source_name": "orders",
        "metric": "revenue",
        "group_by": "product_line",
    }
)
```

## What a resolved plan contains

A resolved plan identifies:

- source
- metric column
- aggregation
- optional group column
- schema revision
- plan hash

## What this proves

`resolve()` is the deterministic planning boundary. It does not execute the query. You can verify the plan, inspect it, and then pass it to `query()`.

`resolve()` is still separate from:

- `query_with_metadata()` / `queryWithMetadata()` for execution plus usage metadata
- `query_batch()` / `queryBatch()` for several governed exact queries
- `query_sql_report()` / `querySqlReport()` for wide read-only rowsets
