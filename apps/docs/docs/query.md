---
sidebar_position: 5
---

# Query

`query()` executes a deterministic exact plan.

## Discovery-first flow

For the first turn against hosted or self-hosted data, discover the dataset first:

1. `get_contract()` / `getContract()` / `GET /v1/meta/contract`
2. `list_datasets(search=..., compact=True)` / `listDatasets({ search, compact: true })`
3. `get_dataset_summary(dataset_id)` / `getDatasetSummary(datasetId)`
4. `resolve()`
5. optional `verify()`
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
result = rt.query(plan)
print(result.result)
```

## Rules

- `query()` should receive an exact plan or a resolved plan
- it should not be used as a planning surface
- if the plan is stale or invalid, the runtime should reject it explicitly
- the contract inspection step stays separate from discovery, planning, and execution

## What this proves

The execution step is separate from planning. That separation is central to the runtime-first model.

## Adjacent public surfaces

`query()` remains the one-exact-plan execution surface. Use the adjacent public methods when you need a different shape:

- `query_with_metadata()` / `queryWithMetadata()` for execution plus request/cost/latency metadata
- `query_batch()` / `queryBatch()` for several governed exact queries in one ordered response
- `query_sql_report()` / `querySqlReport()` for a wide read-only SQL rowset over authorized datasets

Do not use `query()` as a planning shortcut or as a generic SQL report surface.

For explicit bridge-table execution, see
[Multi-hop Joins](/api-reference/multi-hop-joins). That guide shows the
supported `join_path` contract, the `6`-hop (`7` table) ceiling, and the
separate `query_sql_report()` rowset surface.

## Deterministic filter contract

Exact governed queries now accept a small deterministic filter shape:

- `time_filter`
- `conditions[].op = eq`
- `conditions[].op = in`
- `conditions[].op = gt / gte / lt / lte`
- `conditions[].op = is_null / is_not_null`

The public filter contract is intentionally narrow. It is meant for common
cross-industry exact slices such as:

- `status = completed`
- `category in ["enterprise", "mid_market"]`
- `is_refunded = true`
- `amount >= 1000`
- `resolved_at is_not_null`

Treat this as a **record-filter contract** over normalized rows. It is **not**
SQL, and it stays valid for Redis, files, APIs, and other non-SQL sources as
long as the connector exposes deterministic records.

It is **not** a generic predicate tree. Avoid nested `OR`, arbitrary
expressions, or free-form SQL-like filters on the governed exact-query surface.
