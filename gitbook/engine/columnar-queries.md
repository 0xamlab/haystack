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
| `with_table(name, columns, rows=...)` | declare a named side table, once per request |
| `join(table, on=..., how=...)` | one equality key against a named side table |
| `window(fn, name=..., ...)` | append one window column, row order unchanged |

Aggregations: `sum`, `avg` (or `mean`), `min`, `max`, `count`, `var`, `std`.

Window functions have a method each — `row_number`, `rank`, `dense_rank`, `lag`, `lead`,
`running`, `rolling` and `partition_total` — and all of them are spellings of `window`.

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

## Joins

A join reads a **named side table**. Declare it once with `with_table` and name it from
the `join` op — the table is sent once per request, so joining it from three ops sends
it once, not three times:

```python
orders = [[1, 10, 100.0], [2, None, 50.0], [3, 99, 7.0]]
customers = [[10, 1.0], [10, 2.0], [99, 3.0]]

result = (
    Query(columns=["order_id", "customer_id", "amount"], rows=orders)
    .with_table("customers", ["id", "tier"], rows=customers)
    .join("customers", left_on="customer_id", right_on="id", how="left")
    .run(runtime, routing_module="stats")
)

result.columns
# ['order_id', 'customer_id', 'amount', 'customers.id', 'customers.tier']
```

Right columns arrive prefixed with the table's name, so a join cannot quietly shadow a
column you already had — pass `prefix="c_"` for a different one. Use `on="id"` when both
sides spell the key the same way, `left_on`/`right_on` when they do not. One equality key
per join; join again for a second key.

A side table can be a resident dataset instead of inline rows — `with_table("customers",
["id", "tier"], dataset=handle)` — which keeps the per-request payload constant however
many rows the table has. See [Large tables](#large-tables-send-once-query-many-times).

### how

| `how` | What comes back |
| --- | --- |
| `inner` | left rows that have a partner, once per partner |
| `left` | every left row, with nulls across the right columns where there was none |
| `semi` | left rows that have a partner — left columns only, one row per row in |
| `anti` | left rows known to have none — left columns only, one row per row in |

`right`, `outer`, `full` and `cross` are rejected by name rather than quietly treated as
`left`.

`semi` and `anti` cannot fan out: they answer a yes/no question about each left row, so
three partners still give you one row. They are SQL's `IN` and `NOT IN` — **not** `EXISTS`
and `NOT EXISTS`. The difference shows on a missing key: a left row whose key is `None` is
excluded from **both** results. It has no partner, and it is not *known* to have none
either, which is the same reason `NOT IN` with a missing value surprises people in SQL.

```python
def matched(how):
    return (
        Query(columns=["order_id", "customer_id", "amount"], rows=orders)
        .with_table("customers", ["id", "tier"], rows=customers)
        .join("customers", left_on="customer_id", right_on="id", how=how)
        .run(runtime, routing_module="stats")
    )

matched("semi").rows   # [[1.0, 10.0, 100.0], [3.0, 99.0, 7.0]]  — orders 1 and 3
matched("anti").rows   # []  — order 2's key is missing, so it is in neither
```

### A missing key matches nothing

A `None` key matches nothing — not even another `None` key. `null = null` is unknown and a
join is a sequence of equality tests, so:

* **`inner`** — the row disappears.
* **`left`** — the row survives once, with nulls across every right column.
* **`semi` / `anti`** — the row is in neither result.

That is deliberately the opposite of `distinct`, where two rows missing the same field
*are* the same row. An inner join that matched missing keys would pair unrelated rows that
happen to both be incomplete.

Write `None` for a key you do not have, rather than a stand-in value: `0` or `-1` is a key
like any other and will match every other row that also used it.

### Duplicate keys multiply

Three left rows and two right rows sharing a key produce **six** output rows. That is what
a join means, and it is the usual source of a surprise row count — above, customer `10`
appears twice, so order `1` comes back twice. Reach for `semi` when you meant "orders from
a customer in this list" rather than "one row per matching pair".

Because that product grows faster than the request does, the size of the output is checked
**before** it is built. A join may produce at most **1,000,000 rows** and **32,000,000
cells** (rows x columns); a plan that would exceed either is refused, and the error
reports the count it measured. It is never truncated — half a join is a wrong answer that
looks exactly like a right one.

The other limits on the same surface: a request may declare at most **8** side tables, all
of them together at most **32,000,000 cells** (the budget the join output draws on too),
and any header, left or right, at most **512 columns**.

### merge

`method="merge"` walks two already-sorted inputs and builds no hash table, which is the
cheaper choice when the left side is sorted on the key already. A plan cannot sort a side
table, so it applies only when the table you supply is itself ascending on its key with
missing values last — and that is verified rather than assumed, because an unsorted input
would silently drop matches, and a join that quietly drops matches is worse than one that
refuses. `method="merge"` is not defined for `semi` or `anti`.

## Window functions

A window function appends **one** column and leaves row order exactly as you gave it:

```python
result = (
    Query(columns=["region", "amount"], rows=[[1, 10], [1, 20], [2, 50]])
    .running("amount", name="running_total", partition_by="region", order_by="amount")
    .run(runtime, routing_module="stats")
)

result.columns   # ['region', 'amount', 'running_total']
result.rows      # [[1.0, 10.0, 10.0], [1.0, 20.0, 30.0], [2.0, 50.0, 50.0]]
```

| Method | What it appends |
| --- | --- |
| `row_number(name=..., order_by=...)` | 1-based position in the partition; never tied |
| `rank(name=..., order_by=...)` | competition rank: 10, 20, 20, 30 -> 1, 2, 2, **4** |
| `dense_rank(name=..., order_by=...)` | dense rank: 10, 20, 20, 30 -> 1, 2, 2, **3** |
| `lag(value, name=..., order_by=..., offset=1)` | the value `offset` rows earlier |
| `lead(value, name=..., order_by=..., offset=1)` | the value `offset` rows later |
| `running(value, name=..., order_by=..., agg=...)` | the aggregate of the partition so far |
| `rolling(value, name=..., order_by=..., preceding=..., agg=...)` | a trailing frame of `preceding + 1` rows |
| `partition_total(value, name=..., agg=...)` | the partition's aggregate, on every row of it |

Every one of them also takes `partition_by=...`, and all but `partition_total` take
`desc=...` — one boolean, or one per `order_by` column, since a short list would leave the
trailing keys ascending and quietly change the ranks.

`window(fn, name=..., ...)` is the general form; each method above is a spelling of it.
Frame aggregations are `sum`, `avg` (or `mean`), `min`, `max` and `count` — `var`, `std`
and `median` are not defined over a frame here and are rejected rather than answered with
a column of nulls.

`rank` and `dense_rank` differ only on ties, and only after one: both give the tied rows
the same number, then `rank` skips the numbers the tie consumed while `dense_rank` does
not. Use `rank` for "how many rows are ahead of me", `dense_rank` for "how many distinct
values are ahead of me".

The rules:

* **`name` is required.** Two frames over `amount` would both want to be called
  `sum_amount`, and a name that collides with an existing column would shadow it rather
  than replace it.
* **`order_by` is required for everything except `partition_total`.** A running total with
  no order is not a defined answer. `partition_total` is order-independent by definition,
  so it takes none.
* **`rank` and `dense_rank` take exactly one order column.** A tie is defined by that
  column; two keys would report ties that are not ties.
* **`partition_by` is optional.** Leave it out for one partition over the whole table,
  which is what `OVER (ORDER BY ...)` means. A missing partition key forms its **own**
  partition — unlike `group_by`, where a missing key belongs to no group.
* **Row order does not change.** Add a `sort` after the window op if you want the rows in
  window order; permuting them silently would change what a following `limit` or `top_k`
  means.
* **A window op takes at most 20,000 rows**, and its appended column counts against the
  512-column ceiling. Ordering the raw rows is the expensive part, so a larger batch is
  refused — with a message naming the operators that reduce rows — instead of taking
  minutes and looking like a stall. `filter`, `group_by`, `top_k` and `limit` all come
  first in a plan for that reason.

### At a partition edge the answer is missing, not zero

`lag` on the first row of a partition, and `lead` on the last, have nothing to point at.
They come back `None`:

```python
result = (
    Query(columns=["region", "amount"], rows=[[1, 10], [1, 20], [2, 50]])
    .lag("amount", name="previous", partition_by="region", order_by="amount")
    .lead("amount", name="next", partition_by="region", order_by="amount")
    .run(runtime, routing_module="stats")
)

result.rows
# [[1.0, 10.0, None, 20.0],
#  [1.0, 20.0, 10.0, None],
#  [2.0, 50.0, None, None]]   region 2 has one row: no previous, no next
```

`0` there would be a number nobody computed, and a difference against it — `amount - lag`
— would report a full-sized change where there is no comparison to make. An offset never
reaches into the neighbouring partition; `region=2` above is its own partition, so both
its answers are absent.

A frame behaves the same way at the start: `rolling(..., preceding=6, agg="avg")` on the
third row of a partition averages the three rows that exist rather than padding the frame
out with zeros.

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
