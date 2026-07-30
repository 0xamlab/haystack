---
icon: table-columns
description: Filter, group, sort and rank tabular data with compiled kernels on your own machine.
---

# Columnar queries

`execute_batch` and `pipeline` remove the cost of *calling* many kernels. A query is
different: filtering, grouping and sorting a table is one job made of several steps,
and each step's output is the next step's whole input. `runtime.query` sends the
whole plan in one call and runs every operator as a compiled kernel on your device.

```python
from algenta import MojoRuntime, Query, col

runtime = MojoRuntime(mode="local")

result = (
    Query(
        columns=["region", "amount"],
        rows=[[1, 10.5], [2, 50], [1, 30], [3, None]],
    )
    .filter(col("amount") > 20)
    .group_by("region", "amount", agg="sum")
    .sort("sum_amount", desc=True)
    .run(runtime, routing_module="stats")
)

result.columns    # ['region', 'sum_amount']
result.rows       # [[2.0, 50.0], [1.0, 30.0]]
result.plan_hash  # identifies the computation, not the data
```

Nothing leaves the machine. There is no server to start and no sidecar to install —
the kernels are inside the wheel.

## Operators

| Method | What it does |
| --- | --- |
| `filter(expr)` | keep rows where `expr` is true |
| `project(name=expr, ...)` | compute new columns |
| `select(*names)` | keep these columns, in this order |
| `group_by(by, value, agg=...)` | one aggregate per group, in one pass |
| `sort(by, desc=..., nulls_last=...)` | stable sort, one key or several |
| `top_k(by, k, desc=...)` | the k best rows without sorting the rest |
| `distinct(*names)` | first row of each distinct combination |
| `limit(count, offset=...)` | a row window |

Aggregations: `sum`, `avg` (or `mean`), `min`, `max`, `count`, `var`, `std`.

## Expressions

Build a predicate with `col`, and Python's operators do what they look like:

```python
from algenta import col, lit

col("amount") > 20
col("amount").between = (col("amount") >= 10) & (col("amount") <= 100)
col("region").eq(2) | col("region").eq(3)
~(col("amount") < 5)
(col("price") * col("units")).is_not_null()
```

Use `.eq(...)` and `.ne(...)` rather than `==` and `!=`. Python reserves those for
value equality, and expressions stay comparable and hashable so you can put a plan in
a dict or compare two of them.

Arithmetic, comparison, `and`/`or`/`not`, `is_null`, `is_not_null` and `coalesce` are
all available. Column references are by **name**, resolved against your header, so
reordering `columns` cannot silently point a plan at a different column.

## Missing values are missing, not zero

Write `None` for a value you do not have. It stays absent the whole way through and
comes back as `None`.

That distinction changes answers:

```python
result = (
    Query(columns=["region", "amount"], rows=[[1, 10], [1, None], [2, 5]])
    .group_by("region", "amount", agg="avg")
    .run(runtime, routing_module="stats")
)
result.rows   # [[1.0, 10.0], [2.0, 5.0]]  — region 1 averages 10, not 5
```

Region 1 has one known amount, so its average is 10. Had the missing value been read
as `0`, the average would be `5` — a plausible number, and wrong.

The rules, in full:

* **A predicate over a missing value is unknown**, and unknown does not pass a filter.
  A row with no `amount` is neither kept by `amount > 20` nor by `amount <= 20`. Use
  `col("amount").is_null()` to select it deliberately.
* **Arithmetic propagates**: `None + 5` is `None`. The sum of a number and something
  unknown is unknown.
* **A missing group key belongs to no group.** It is not folded into a category and
  it does not invent one.
* **`count` and `sum` of nothing are `0`** — real answers. **`avg`, `min`, `max`,
  `var` and `std` of nothing are `None`** — those do not exist.
* **`distinct` treats two missing values as the same row**, because it asks whether
  two rows are the same row. This is deliberately different from `.eq()`.

## Sorting

Sorts are stable: rows with equal keys keep the order you gave them. So `top_k` and a
full `sort` agree on which row is first, and two runs over the same data produce the
same output in the same order.

Missing values go to the **same end in both directions**:

```python
Query(...).sort("amount", desc=True)                    # nulls last
Query(...).sort("amount", desc=True, nulls_last=False)  # nulls first
```

A missing value is not a large one, so `desc=True` gives you the biggest known
amounts — not the rows that have no amount. Set `nulls_last=False` when you want the
incomplete rows surfaced.

Sort by several keys, most significant first:

```python
Query(...).sort(["region", "amount"], desc=[False, True])
```

## top-k

`top_k` keeps only k rows as it scans, so asking for the top 10 of a million rows
costs ten comparisons per row and ten slots of memory — not a full sort.

```python
Query(columns=[...], rows=[...]).top_k("amount", 10, desc=True)
```

## Grouping by several columns

```python
result = (
    Query(columns=["region", "channel", "amount"], rows=[...])
    .group_by(["region", "channel"], "amount", agg="sum")
    .run(runtime, routing_module="stats")
)
result.columns   # ['region', 'channel', 'sum_amount']
```

A row is excluded if **any** key column is missing. `(region=2, channel=None)` is a
row whose group is unknown, so putting it under region 2 would report a total that
includes rows nobody can attribute.

## Large tables: send once, query many times

Open the table as a resident dataset and reference it by handle. Per-query payload
then stays constant no matter how many rows the table has:

```python
handle = runtime.open_dataset(
    [[1, 10.5], [2, 50], [1, 30]],
    name="sales",
    routing_module="stats",
)

for threshold in (10, 20, 30):
    result = (
        Query(columns=["region", "amount"], dataset=handle)
        .filter(col("amount") > threshold)
        .group_by("region", "amount", agg="sum")
        .run(runtime, routing_module="stats")
    )
    print(threshold, result.rows)

runtime.close_dataset(handle, routing_module="stats")
```

Handles live as long as the worker connection. A closed or unknown handle raises
`unknown_dataset` rather than returning an empty result — an empty answer to a query
over data that is not there looks exactly like a real answer.

## Reading the result

```python
result.columns          # output column names
result.rows             # list of rows; None for missing
result.column("amount") # one column by name
result.to_dicts()       # rows as dicts
len(result)             # row count
result.lineage          # what each operator did, and the shape it produced
result.plan_hash        # a stable identity for the plan
result.latency_ms
```

`lineage` reports one entry per operator, with the shape it produced:

```python
[{'index': 0, 'op': 'filter',    'shape': '2 rows x 2 cols'},
 {'index': 1, 'op': 'aggregate', 'shape': '2 rows x 2 cols'}]
```

That is how you see a filter removed more than you expected, without adding a
`limit` and re-running.

## plan_hash

`plan_hash` is a SHA-256 over the plan's **values**, not its text. Reformatting the
plan or reordering keys gives the same hash; changing a threshold gives a different
one. It identifies the computation, so you can cache on it, compare two runs, or
record which query produced a number.

```python
a = Query(columns=["v"], rows=[[1]]).top_k("v", 10)
b = Query(columns=["v"], rows=[[1], [2]]).top_k("v", 10)
# same plan, different data -> same plan_hash
```

## When a plan is wrong

A rejected plan raises `QueryError` and returns **no rows**. There is no partial
result, because a correct answer to the first half of your plan is impossible to tell
apart from a complete one.

```python
from algenta import QueryError

try:
    Query(columns=["region", "amount"], rows=[[1, 10]]) \
        .sort("revenue") \
        .run(runtime, routing_module="stats")
except QueryError as error:
    error.code      # 'query_op_failed'
    error.op_index  # 0 — which operator failed
    str(error)      # names 'revenue' and lists the columns that do exist
```

Column names, expressions and aggregation names are all checked before the first row
is touched. A misspelled aggregation lists what is accepted rather than quietly
falling back to a sum.

## routing_module

`routing_module` names which installed shard serves the request. The runtime ships as
filtered shards — you install the kernels you need, not all of them — so the call has
to say where it belongs. Any module in the shard you have works; `"stats"` is a safe
default for a query that names no kernel of its own.

## What runs where

Every operator is a compiled Mojo kernel. Python builds the plan and decodes the
result; it does no filtering, grouping or sorting. The grouping path reuses the same
streaming update kernels the rest of the engine uses, so a group's mean is computed
the same way whether you reach it through a query or call the kernel directly.

The engine holds one accumulator per group rather than every value in each group, so
memory scales with the number of groups, not the number of rows.

## See also

* [Batched and chained execution](coarse-execution.md) — many kernel calls in one frame
* [Runtime libraries](runtime-libraries.md) — calling a kernel directly
* [Verify the bundled engine](bundled-runtime.md) — confirming what is installed
