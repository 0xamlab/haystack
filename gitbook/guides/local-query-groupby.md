---
icon: table-cells
description: Build a columnar query with algenta.Query and group your own data locally with group_by() — the same composed engine the dataframe group-by benchmark measures.
---

# Group data locally with Query.group_by()

By the end of this guide you will have built a query plan with `algenta.Query`, aggregated a column with `group_by()`, run it in one dispatch on your own machine, and read back the grouped result. Everything runs inside the runtime that ships with the `algenta` package — there is nothing separate to start, connect to, or manage.

`Query(...).group_by(...)` is the same public entry point [Dataframe group-by](../benchmarks/dataframe-groupby.md) measures: the "aggregate" operator resolves to the composed dense/packed/fused-radix engine that page benchmarks against DuckDB and Polars, not a separate, slower path.

## Requirements

* **Python 3.14** — `pip install algenta` requires it.
* Data as columns of numbers. Cells are floats or `None`; booleans are accepted and coerced to `1.0`/`0.0`. Non-numeric data (strings, dates) needs to be encoded to a numeric column before it reaches `Query` — the same convention [Dataframe group-by](../benchmarks/dataframe-groupby.md) uses for its own categorical columns.

## Install Algenta

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install algenta
```

## Run a group-by

{% stepper %}
{% step %}
### Build the query

`Query` takes a `columns` header and either `rows` (inline data) or a `dataset` handle (see [Reusing one table across several queries](#reusing-one-table-across-several-queries)). `group_by(by, value, agg=...)` appends one aggregate operator; `by` is a single column name or a list of them for a multi-key group.

```python title="build_query.py"
from algenta import Query, col

query = (
    Query(
        columns=["region", "amount"],
        rows=[[1, 10.5], [2, 50.0], [1, 30.0], [2, 5.0]],
    )
    .filter(col("amount") > 0)
    .group_by("region", "amount", agg="sum")
    .sort("sum_amount", desc=True)
)
```

Chaining `filter`, `sort`, `top_k`, `project`, `join` and `group_by` costs nothing extra in round trips — the whole plan crosses into the runtime once, not once per operator.
{% endstep %}

{% step %}
### Run it

```python title="run_query.py"
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")
result = query.run(runtime, routing_module="stats")
```

`routing_module` names the installed shard to dispatch through. `"stats"` is a safe default for a query that names no kernel directly — pick a shard you know is installed if you have filtered the runtime down (see [Route & execute capabilities](capabilities.md)).
{% endstep %}

{% step %}
### Read the result

```python title="read_result.py"
print(result.columns)   # ['region', 'sum_amount']
print(result.rows)      # [[2.0, 55.0], [1.0, 40.0]]
print(result.plan_hash) # identifies the computation, not the data
print(result.latency_ms)
```
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — `result.rows` has one row per distinct group in `by`, in first-appearance order (before the `sort` reordered them), with one aggregate column per `value`/`agg` pair named `<agg>_<value>`. A raised `algenta.QueryError` — not an empty or partial result — means the plan was rejected or an operator failed.
{% endhint %}

## Group-by semantics

* **Accepted `agg` tokens:** `sum`, `avg` (alias `mean`), `min`, `max`, `count`, `var`, `std`. Any other value raises `ValueError` before the plan is sent.
* **A row whose group key is absent joins no group** — it is counted separately rather than folded into an existing one, so a missing category never silently merges with a real one.
* **A group with nothing to average has no mean** (`None`), while its `count` and `sum` are a real `0`.
* **`min`/`max` never come from a `NaN` row.** A `NaN` value is counted in its group but never becomes that group's extremum.

## Reusing one table across several queries

Sending a large table again for every query re-sends the same bytes each time. `open_dataset` makes a value resident once and returns a handle you reference from `Query`'s `dataset` argument instead of `rows`:

```python title="reuse_table.py"
handle = runtime.open_dataset(
    [[1, 10.5], [2, 50.0], [1, 30.0], [2, 5.0]],
    name="orders",
    routing_module="stats",
)

totals = Query(columns=["region", "amount"], dataset=handle).group_by(
    "region", "amount", agg="sum"
).run(runtime, routing_module="stats")

counts = Query(columns=["region", "amount"], dataset=handle).group_by(
    "region", "amount", agg="count"
).run(runtime, routing_module="stats")

runtime.close_dataset(handle, routing_module="stats")
```

Handles are scoped to one worker connection and are never reissued after `close_dataset` — a stale handle fails with `dataset_not_found` rather than reading whatever took its place.

## See also

* [Dataframe group-by](../benchmarks/dataframe-groupby.md) — the benchmark measuring this same composed engine against DuckDB and Polars.
* [Make your first query](first-query.md) — the governed, hosted `/v1/query` surface (a different feature: server-scoped, resolver-driven, not this local plan builder).
* [Route & execute capabilities](capabilities.md) — choosing and installing runtime shards.
