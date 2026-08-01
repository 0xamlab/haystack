---
icon: clipboard-check
description: Expectations that name the failing row and column, a profile that keeps null, NaN and zero apart, duplicates under a key and an equality you declare
---

# Data quality & feature hygiene

Five kernel families for the question "can I trust this table". They run as compiled kernels
inside the runtime that ships with the SDK — there is nothing to start and nothing to install
separately.

The point of this package is the address, not the count. "3 rows failed" tells you a table is
bad; it does not tell you what to fix. Every expectation comes back with the row, the column,
the bound and the observed value:

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Two columns (id, price), three rows, laid out row by row.
table   = [1.0, 5.0,
           2.0, -12.0,
           3.0, 7.0]
present = [True, True, True, True, True, True]

# Expect column 1 (price) to be greater than 0.0. Op 0 is ">".
report = runtime.execute(
    "data_quality.expect", "expect_column_flat",
    [table, 3, 2, present, 1, 0, 0.0, 0.0, 16],
)["result"]

report["n_violations"]     # 1
report["first_fail_row"]   # 1
report["fail_rows"]        # [1]
report["fail_columns"]     # [1]
report["fail_expected"]    # [0.0]
report["fail_observed"]    # [-12.0]
```

Row 1, column 1, expected `> 0.0`, observed `-12.0`. That is a work item. `n_violations = 1`
on its own is a status light.

## The modules

| Module | What it does |
| --- | --- |
| `data_quality.expect` | expectations over a column, over a suite of columns, or over a typed predicate you build yourself — each returning the failing rows, the columns they came from, the bound and the observed value, plus the rows it did not get to |
| `data_quality.profile` | a per-column census that counts nulls, NaNs, positive and negative infinities, zeros, negatives, positives and distinct finite values separately, with every statistic reported present or absent |
| `data_quality.duplicates` | grouping under a key you state and an equality you state, reporting group sizes, the first row of each group and how many rows are removable |
| `data_quality.leakage` | the ladder from "no signal" through "suspicious" to "proven", kept strictly apart, plus a timestamp check that is the only thing that can prove future information |
| `data_quality.contract` | the package's one status vocabulary, its finiteness test, its rounding-tolerance and decimal-grid builders, its non-wrapping work budget and its guarded column reader |

## Null, NaN and zero are three different facts

A column of nothing and a column of zeros are not the same column, and a profile that reports
`0.0` for both is wrong in the way that costs the most. Two calls, same values, different
presence:

```python
values = [0.0, 0.0, 0.0]

nothing = runtime.execute("data_quality.profile", "profile_column",
                          [values, [False, False, False], 3])["result"]

zeros   = runtime.execute("data_quality.profile", "profile_column",
                          [values, [True, True, True], 3])["result"]

nothing["n_null"], zeros["n_null"]                        # 3, 0
nothing["n_zero"], zeros["n_zero"]                        # 0, 3
nothing["n_distinct_finite"], zeros["n_distinct_finite"]  # 0, 1
nothing["null_fraction"], zeros["null_fraction"]          # 1.0, 0.0

nothing["has_mean"], zeros["has_mean"]                    # False, True
nothing["mean"],     zeros["mean"]                        # 0.0, 0.0
```

Look at the last two lines together. Both `mean` slots read `0.0`, and they mean completely
different things — which is exactly why `has_mean` is the answer and `mean` is only a number
you may read once the flag says you can. A mean of no data does not exist; a mean of three
zeros is zero. The same rule holds for the spread, the extremes and the median.

{% hint style="info" %}
**A NaN is not a null either.** A value that is present but not a number is counted in
`n_nan`, and the two infinities are counted separately in `n_pos_inf` and `n_neg_inf`. None of
them is allowed to become an average or an extreme, and none of them is silently dropped —
the counts are the report.
{% endhint %}

A whole table profiles column by column, and the columns worth looking at first come back
named:

```python
table   = [7.0, 1.0, 0.0,
           7.0, 2.0, 0.0,
           7.0, 3.0, 0.0]
present = [True, True, False, True, True, False, True, True, False]

t = runtime.execute("data_quality.profile", "profile_table",
                    [table, 3, 3, present])["result"]

t["null_counts"]           # [0, 0, 3]
t["distinct_counts"]       # [1, 3, 0]
t["all_absent_columns"]    # [2]  — column 2 has no data at all
t["constant_columns"]      # [0]  — column 0 never changes
```

Column 2 is empty and column 0 is constant. Neither is an error and both are usually a bug in
whatever produced the table.

### Ordering is a statistic too, so it is present-or-absent

A profile also reports whether a column's values are strictly increasing (`1`), strictly
decreasing (`-1`) or neither (`0`) — useful when a column is supposed to be a sorted key or a
timestamp. Nulls are skipped rather than treated as breaks, because a timestamp column with a
gap in it is still ordered.

Because an *order* is a relation between at least two values, this field is flag-paired like
every other statistic:

```python
def direction(values, present):
    p = runtime.execute("data_quality.profile", "profile_column",
                        [values, present, len(values)])["result"]
    return p["has_monotonic_direction"], p["monotonic_direction"]

direction([1.0, 2.0, 3.0], [True, True, True])     # (True,  1)
direction([3.0, 2.0, 1.0], [True, True, True])     # (True, -1)
direction([1.0, 3.0, 2.0], [True, True, True])     # (True,  0)  — out of order
direction([4.0, 4.0, 4.0], [True, True, True])     # (True,  0)  — constant
direction([5.0, 0.0, 0.0], [True, False, False])   # (False, 0)  — one value is not an order
direction([0.0, 0.0, 0.0], [False, False, False])  # (False, 0)  — nothing to order
```

Read the flag first. A column with one live value, or none, has no ordering to report, and
saying "strictly increasing" about a single point would be an answer about nothing. When the
flag is `True`, a `0` covers both "constant" and "genuinely out of order" — and
`n_distinct_finite` in the same report tells you which: `1` is constant, more is out of order.

## A duplicate needs a key and a notion of equality

Nothing is a duplicate in the abstract. It is a duplicate under a key, and under a rule for
when two numbers count as the same number. You state both, and changing either changes the
answer — visibly:

```python
table   = [1.001, 10.0,
           1.002, 20.0]
present = [True, True, True, True]

# decimals = -1: two rows are the same only if the key values are bit-identical.
exact = runtime.execute("data_quality.duplicates", "duplicate_scan_flat",
                        [table, 2, 2, present, [0], -1, 16])["result"]

exact["n_groups"]             # 2
exact["n_duplicate_rows"]     # 0
exact["first_duplicate_row"]  # -1  — there is no such row

# decimals = 2: round the key onto a two-place decimal grid first.
grid = runtime.execute("data_quality.duplicates", "duplicate_scan_flat",
                       [table, 2, 2, present, [0], 2, 16])["result"]

grid["n_groups"]                    # 1
grid["n_duplicate_rows"]            # 1  — one row is removable
grid["largest_group_size"]          # 2
grid["duplicate_group_first_rows"]  # [0]
grid["duplicate_group_sizes"]       # [2]
```

`1.001` and `1.002` are two customers or one, depending on a decision only you can make. The
package will not make it for you, and it records which one you made in `decimals`.

{% hint style="warning" %}
**There is no fuzzy default.** Equality is either the exact bit pattern of the key values —
with `-0.0` and `+0.0` treated as one key, and every NaN treated as one key — or that same
comparison after rounding onto a decimal grid you name. A tolerance of the "`|a - b|` is small
enough" kind is never used, because it is not transitive: it can call A the same as B and B the
same as C while A and C differ, so the groups it produces depend on the row order.
{% endhint %}

Rows whose key is missing are not duplicates of each other. They are counted in
`n_null_key_rows` and excluded from every group, because "both unknown" is not "both the same".

## Suspicious is not proven

This is the distinction the whole leakage module exists to hold. A feature that correlates
perfectly with the target is *suspicious*. A feature that was *recorded after the event you are
predicting* is proven leakage. From the values alone you can prove the first kind of thing but
never the second, and the report says which one it found.

```python
target = [1.0, 2.0, 3.0, 4.0]
mask   = [True, True, True, True]

def scan(feature):
    return runtime.execute("data_quality.leakage", "leakage_scan_flat",
                           [feature, mask, target, mask, 4, 0.95, 0.9])["result"]

# Almost perfectly correlated, but not a function of the target.
a = scan([1.0, 2.1, 2.9, 4.2])
a["verdict"]                  # 431 — suspicious_not_proven
a["abs_pearson"]              # 0.9961393366299974
a["suspicious_correlation"]   # True
a["proven_affine"]            # False
a["affine_worst_row"]         # 2 — where the straight line fits worst

# The feature IS the target, exactly.
b = scan([1.0, 2.0, 3.0, 4.0])
b["verdict"]                  # 432 — proven_feature_is_the_target
b["proven_target_copy"]       # True

# The feature is 3 * target + 5, exactly, on every compared row.
c = scan([8.0, 11.0, 14.0, 17.0])
c["verdict"]                  # 433 — proven_feature_is_an_affine_image_of_the_target
c["proven_affine"]            # True
c["affine_slope"]             # 3.0
c["affine_intercept"]         # 5.0
c["affine_max_residual"]      # 0.0
```

`a` and `c` both have a correlation of essentially 1. Only `c` is proven, because only `c` is a
*deterministic function* of the target that reproduces it on every row it was allowed to
compare. `a` is a lead to investigate — it could equally be a feature that is genuinely, and
legitimately, very predictive.

### What "proven" costs, so that it means something

A proof claim is only worth having if it is hard to get, so two things are required beyond a
small residual.

**The feature has to actually vary.** A column that never changes fits `0 * target + c`
perfectly on every row — and a constant column can be produced without ever looking at the
target, which is the opposite of leakage. An all-default or all-zero column is common in real
tables, so this matters in practice: it comes back as no signal, with `has_affine` false and
`feature_constant_on_compared` telling you why.

```python
const = scan([7.0, 7.0, 7.0, 7.0])
const["verdict"]                        # 430 — no_leakage_signal
const["proven_affine"]                  # False
const["has_affine"]                     # False — a flat line through one value is not a map
const["feature_constant_on_compared"]   # True — and this is the reason
```

**Each row is judged against its own magnitude.** The residual at a row is compared to a few
units in the last place of *that row's* observed value, and to nothing else — not to a total, a
maximum, or anything about the other rows. One consequence is worth knowing in advance: when a
target has a very large magnitude and a very narrow range (epoch timestamps are the everyday
example), the straight line through its two extreme rows is numerically fragile, and a
relationship that is exactly affine on paper can come back **not proven** with a large
`affine_max_residual`. That is deliberate. It means "this data cannot support the claim", not
"there is no relationship" — and such a feature still correlates at 1.0, so it is still
reported, as suspicious.

{% hint style="info" %}
**`proven_affine` false is not `has_affine` false.** `has_affine` true with `proven_affine`
false means a candidate line was fitted and `affine_max_residual` tells you how badly it
missed. `has_affine` false means no line was fitted at all, and the report says which
precondition was missing.
{% endhint %}

{% hint style="danger" %}
**`temporal_checked` is `False` in every one of those reports, including the clean one.** No
amount of correlation tells you whether a value was available at prediction time. If you want
that answered you have to supply the timestamps, and it is a separate call.
{% endhint %}

```python
# When the feature was observed, versus when the target event happened.
feature_time = [10.0, 20.0, 45.0]
target_time  = [15.0, 25.0, 30.0]
observed     = [True, True, True]

t = runtime.execute("data_quality.leakage", "leakage_timing_flat",
                    [feature_time, target_time, observed, 3])["result"]

t["verdict"]                    # 435 — proven_feature_observed_after_the_target_event
t["proven_future_information"]  # True
t["n_future_rows"]              # 1
t["first_future_row"]           # 2
t["max_future_lead"]            # 15.0  — observed 45, event at 30
```

Row 2's feature was recorded fifteen units *after* the thing it is supposed to predict. That is
not a correlation to argue about; it is a defect in how the dataset was built.

When nothing is late, the lead does not become zero:

```python
clean = runtime.execute("data_quality.leakage", "leakage_timing_flat",
                        [[10.0, 20.0, 25.0], target_time, observed, 3])["result"]

clean["n_future_rows"]                    # 0
clean["first_future_row"]                 # -1
clean["has_max_future_lead"]              # False
clean["max_future_lead"]                  # 0.0  — only readable because the flag is False
clean["n_unrepresentable_lead_rows"]      # 0
```

A lead of `0.0` would mean a feature observed at the *exact instant* of the event, which is a
real and different finding. Absent means there was no such row at all. Rows that share a
timestamp exactly are counted in `n_simultaneous_rows` and are never treated as proof.

There is a second way the largest lead can be absent, and it is distinguishable from the first.
If two timestamps are so far apart that their difference is larger than a 64-bit float can
hold, that row's lead has no numeric value — the *proof* still stands, the row is still counted
and still addressable, but the largest lead is no longer a number that exists:

```python
t["n_future_rows"]                  # > 0  — the lookahead is proven
t["n_unrepresentable_lead_rows"]    # > 0  — and at least one lead overflowed
t["has_max_future_lead"]            # False
t["max_future_lead"]                # 0.0
```

So `n_future_rows == 0` means "nothing was late" and `n_future_rows > 0` with
`n_unrepresentable_lead_rows > 0` means "something was late by an amount too large to state".
The largest *representable* lead is deliberately **not** reported in that case: telling you
"the worst skew is 10 seconds" while another row leads by an astronomical amount is the exact
mistake this field exists to prevent.

## A large table tells you what it did not check

An expectation suite over a big table has a work ceiling, and when a request runs into it the
report checks a prefix and says so. It does not quietly sample:

```python
report["n_rows"]              # every row in the table
report["n_rows_checked"]      # the rows actually examined
report["n_rows_not_checked"]  # the remainder — always accounted for
report["work_truncated"]      # True when the pass was partial
```

`n_rows_checked + n_rows_not_checked` always equals `n_rows`. This matters more than it looks:
a sampling pass that reports a clean table has given you a *wrong* answer, while a prefix pass
that reports 4,092 of 4,093 rows has given you a partial one you can act on. Narrow the table
or split the suite and run again.

`work_truncated` is `True` for exactly one reason — the request needed more work than the
ceiling allows — so that advice always applies when you see it. In particular a request that
contains **no expectations at all** is refused (status `422`) rather than answered: a suite of
nothing would otherwise report zero violations over zero rows, which reads as a clean table,
and would report a truncation it never hit.

The listed addresses are capped separately by the `max_reports` argument you pass, so a table
with a million bad rows returns a bounded report rather than a million-element list.
`n_violations` still counts all of them, and `reports_truncated` tells you the list was cut.

## Statuses

Every function returns a `status` of `0` on success, or one of these:

| Code | Meaning |
| --- | --- |
| `400` | a negative row or column count |
| `401` | the declared shape does not match the number of values given |
| `402` | too many rows |
| `403` | too many columns |
| `404` | the request exceeds the work budget |
| `405` | the presence mask does not describe exactly the declared number of rows |
| `406` | a column index outside the table |
| `407` | lists that should be parallel have different lengths |
| `408` | a decimal grid outside the supported range |
| `409` | a value that cannot be placed on the declared grid without changing it |
| `410` | a table with no columns to profile |
| `420` – `429` | an expectation or predicate the engine will not run: an unknown operator, a non-finite bound, a request containing nothing to check, a malformed predicate, or a suite past its ceiling |
| `430` – `436` | a leakage verdict, from no signal through suspicious to proven, or a threshold outside `[0, 1]` |
| `440` – `449` | a duplicate key that is empty, too wide, or names the same column twice |

The leakage codes in the `430` range are verdicts rather than errors: `430` no signal, `431`
suspicious, `432` the feature is the target, `433` the feature is an affine image of the target,
`434` too few comparable rows to decide, `435` the feature was observed after the event.

{% hint style="info" %}
**`434` is not `430`.** "Too few comparable rows to decide" and "no leakage found" are
different answers, and a pipeline that treats them the same will pass a dataset it never
actually examined. The same applies to a constant target: there is no learning problem to leak
into, so the verdict is `434`, not a clean bill of health.
{% endhint %}

## See also

* [Evaluation Calibration](evaluation-calibration.md) — scoring a model once its inputs pass these checks
* [Streaming Windows](streaming-windows.md) — windowed aggregates over the same columnar buffers
* [Runtime Library Catalog](runtime-library-catalog.md) — every module and function
