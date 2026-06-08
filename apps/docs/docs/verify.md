---
sidebar_position: 6
---

# Verify

`verify()` is the optional trust and introspection step between planning and execution.

## Discovery-first flow

For the first turn against hosted or self-hosted data, the full governed path is:

1. `get_contract()` / `getContract()` / `GET /v1/meta/contract`
2. `list_datasets(search=..., compact=True)` / `listDatasets({ search, compact: true })`
3. `get_dataset_summary(dataset_id)` / `getDatasetSummary(datasetId)`
4. `resolve()`
5. `verify()`
6. `query()`

SDK clients already fall back automatically when an older self-hosted node
still returns `404` for `/v1/meta/contract`. Raw HTTP callers should use
`/openapi.json` and read `x-primary-data-query-contract` in that case.

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

If you only need execution metadata from the final run, keep `query()` unchanged and use the adjacent `query_with_metadata()` / `queryWithMetadata()` surface instead of parsing headers manually.
