---
sidebar_position: 6
---

# Verify

`verify()` is the optional trust and introspection step between planning and execution.

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

verification = rt.verify(plan)
if not verification.valid:
    raise RuntimeError(verification.errors)

result = rt.query(plan)
```

## When to use it

Use `verify()` when you want:

- explicit plan validation
- trust/audit checkpoints
- a clean preflight before execution
