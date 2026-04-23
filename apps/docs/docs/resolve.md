---
sidebar_position: 4
---

# Resolve

`resolve()` converts structured intent into an exact plan.

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
