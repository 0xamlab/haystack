---
icon: chart-line-up
description: Rolling minimum, maximum, range, mean and standard deviation over a sliding window, plus exponentially weighted mean and variance — with the real cost of each one charged before it runs.
---

# Windowed aggregates

One kernel module for the aggregates a monitor actually asks for: over the last `w`
observations, what was the minimum, the maximum, the spread, the average and the variability.
It runs as a compiled kernel inside the runtime that ships with the SDK — there is nothing to
start and nothing to install separately.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

v = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]

runtime.execute("streaming.windows", "window_min", [v, 3])["result"]["values"]
# [1.0, 1.0, 1.0, 1.0, 2.0, 2.0]

runtime.execute("streaming.windows", "window_max", [v, 3])["result"]["values"]
# [4.0, 4.0, 5.0, 9.0, 9.0, 9.0]

runtime.execute("streaming.windows", "window_range", [v, 3])["result"]["values"]
# [3.0, 3.0, 4.0, 8.0, 7.0, 7.0]
```

Eight observations at window 3 give **six** positions, not eight: `8 - 3 + 1`. The result
reports `n_positions` so you never have to derive that, and a `present` flag per position beside
the values.

## The two costs are different, and both are charged

This is the part worth reading before you size a request.

| Function | Cost |
| --- | --- |
| `window_min`, `window_max`, `window_range` | **O(n)** — a monotonic deque, so each observation is examined a constant number of times whatever the window is |
| `window_mean` | **O(n)** — a sliding sum |
| `window_std` | **O(n × window)** — each window's mean and sum of squared deviations are recomputed exactly |
| `ewma_series`, `ewmvar_series` | **O(n)** |

`window_std` is genuinely the expensive one, and its cost is charged as that product before the
request runs. So a shape that a cheaper aggregate accepts is refused here:

```python
wide = [float(i % 97) for i in range(40000)]

runtime.execute("streaming.windows", "window_mean", [wide, 20000])["result"]["n_positions"]
# 20001 — computed

std = runtime.execute("streaming.windows", "window_std", [wide, 20000])["result"]
std["valid"]    # False
std["status"]   # 369 — work_budget_exceeded
```

That is 800,000,000 element visits behind a request whose payload is 40,000 numbers. Charging
`n + window` for it would let it through and then run for minutes, which is exactly the
situation the refusal exists to prevent. If you want a cheap variability signal over a wide
window, `ewmvar_series` is O(n) and is the right tool; if you want the exact per-window figure,
narrow the window or split the request.

**Why the expensive version is the one on offer.** A sliding-window variance can be computed
cheaply by removing the departing observation from a running accumulator, and that method has no
numerically sound inverse: on a window whose values are large and close together it produces a
*negative* variance, whose square root is a NaN. Cheap-and-wrong was available and was not
taken.

## The exact per-window figures

```python
runtime.execute("streaming.windows", "window_mean", [v, 3])["result"]["values"]
# [2.666..., 2.0, 3.333..., 5.0, 5.333..., 5.666...]
#   8/3       6/3   10/3      15/3  16/3      17/3
```

`window_std` is the population standard deviation of each window — divided by `w`, not `w - 1`.

## One summary of the most recent window

Usually a monitor wants a single scalar summary of the latest window rather than a value per
position. `window_summary_prefix` gives all four at once, over the last `window` observations
inside the first `n`:

```python
s = runtime.execute("streaming.windows", "window_summary_prefix", [v, 8, 3])["result"]

s["present"]    # True
s["count"]      # 3 — the window [9.0, 2.0, 6.0]
s["mean"]       # 5.666666666666667
s["variance"]   # 8.222222222222223
s["minimum"]    # 2.0
s["maximum"]    # 9.0

runtime.execute("streaming.windows", "window_summary_std", [s])["result"]
# 2.8674417556808756
```

The variance is accumulated forward with a numerically stable update rather than as the
difference of two large sums, so it does not lose precision on values that are large and close
together.

`window_summary_std` returns **-1.0** when there is no summary to take a standard deviation of.
Not `0.0`: a one-observation window has a standard deviation of exactly `0.0`, and so does a
constant window, so `0.0` is the commonest real answer there is and cannot double as "there was
nothing here". A standard deviation is never negative, so `-1.0` cannot be mistaken for one.

## Exponentially weighted mean and variance

```python
runtime.execute("streaming.windows", "ewma_series", [v, 0.5])["result"]["values"]
# [3.0, 2.0, 3.0, 2.0, 3.5, 6.25, 4.125, 5.0625]

runtime.execute("streaming.windows", "ewmvar_series", [v, 0.5])["result"]["values"]
# [0.0, 1.0, 1.5, 1.75, 3.125, 9.125, 9.078125, 5.41796875]
```

One value per input, with no warm-up gap. The series is seeded with `values[0]` rather than
`0.0`, because seeding at zero makes the first several outputs an artefact of the seed rather
than of the data and you cannot tell by looking at them.

`window` is reported as `0` for both, which this module defines as "no finite window" — an
exponentially weighted average's memory is unbounded and decaying, so quoting a window length
for it would be a fiction.

`alpha` must be strictly inside `(0, 1)`. `alpha = 0` never moves off the seed and `alpha = 1`
is the identity, so both are degenerate rather than useful and are refused:

```python
runtime.execute("streaming.windows", "ewma_series", [v, 1.0])["result"]["status"]
# 377 — parameter_out_of_range
```

The first entry of `ewmvar_series` is `0.0` and **present**: with one observation the
exponentially weighted variance is genuinely zero, not unknown.

## A window that does not fit is not an error

`window > n` has no windows in it, so the result is valid with zero positions and empty lists —
not a single window over the short data, and not a refusal:

```python
r = runtime.execute("streaming.windows", "window_mean", [v, 9])["result"]

r["valid"]         # True — the request was fine
r["n_positions"]   # 0 — and there are no windows in the data
r["status"]        # 360 — ok
```

`window_positions(n, window)` computes that count for you and returns `0` rather than a negative
number when the window does not fit, so it is always safe to loop over.

## Non-finite inputs are refused at the door

A NaN inside a rolling minimum is the silent case: every comparison against it is false, so it
is never discarded and never wins, and the reported minimum simply skips a position with no
error anywhere. So a non-finite anywhere in the input is refused before anything is computed:

```python
runtime.execute("streaming.windows", "window_min",
                [[1.0, float("nan"), 3.0], 2])["result"]["status"]
# 362 — non_finite_input
```

| Situation | Status |
| --- | --- |
| a non-finite value in the input | `362` |
| an element count that does not match the data | `363` |
| a window outside `[1, 65536]` | `375` |
| the work this request would do exceeds the ceiling | `369` |
| `alpha` outside `(0, 1)` | `377` |
| a summary of no observations | `361` |

## See also

* [Streaming Sketches](streaming-sketches.md) — mergeable quantile, distinct-count and frequency sketches
* [Evaluation Calibration](evaluation-calibration.md) — drift and regression gates over windowed metrics
* [Runtime Library Catalog](runtime-library-catalog.md) — every module and function
