---
sidebar_position: 5
---

# Query

`query()` executes a deterministic exact plan.

## Example

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
result = rt.query(plan)
print(result.result)
```

## Rules

- `query()` should receive an exact plan or a resolved plan
- it should not be used as a planning surface
- if the plan is stale or invalid, the runtime should reject it explicitly

## What this proves

The execution step is separate from planning. That separation is central to the runtime-first model.
