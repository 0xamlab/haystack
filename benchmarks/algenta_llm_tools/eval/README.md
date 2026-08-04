# quotes_question_set.json

16 objective, numerically-scoreable questions against the real
`test_files/Processed_Quotes.csv` corpus (33,125 parsed rows), for benchmarking
an LLM+tool-calling system's numeric answers against fixed ground truth.

## How ground truth was derived

Every `ground_truth` value in `quotes_question_set.json` was computed directly
with pandas on `test_files/Processed_Quotes.csv` -- never via the Algenta SDK or
its Mojo kernels, so a bug shared between "ground truth" and "system under test"
can't make a wrong answer look right. Example (values reproduce exactly):

```python
import pandas as pd
df = pd.read_csv("test_files/Processed_Quotes.csv", low_memory=False)

df["UNIT_PRICE"].dropna().quantile(0.9)                       # q01 -> 1905.48
df["EXT_PRICE"].dropna().quantile(0.25)                        # q02 -> 1275.25
df["EXT_PRICE"].dropna().quantile(0.5)                         # q03 -> 6052.1
df["UNIT_PRICE"].mean()                                        # q04 -> 779.182035...
df["UNIT_PRICE"].std(ddof=1)                                    # q05 -> 2331.963152...
df["UNIT_PRICE"].min(), df["UNIT_PRICE"].max()                 # q06 -> 0.0, 215000.0
(df["STATUS"] == "LOST").sum()                                  # q07 -> 14673
df.loc[df["CUST_TYPE"] == "OEM", "EXT_PRICE"].sum()             # q08 -> 169562999.02
df.loc[df["STATUS"] == "ORDER", "QUANTITY"].mean()              # q09 -> 261.723926...
df["QUANTITY"].sum()                                            # q10 -> 3436556.0
df["CUSTOMER_NO"].nunique()                                     # q11 -> 2008
df["STATUS"].dropna().nunique()                                 # q12 -> 12
(df["AUTO_QUOTED"] == "Y").sum() / df["AUTO_QUOTED"].notna().sum()  # q13 -> 0.03963...
df.groupby("CUST_TYPE")["UNIT_PRICE"].mean().sort_values(ascending=False)  # q14 -> MILITARY, 12515.95
df.groupby("STATUS")["EXT_PRICE"].mean().sort_values(ascending=False)     # q15 -> QTE, 60485.014002
df.dropna(subset=["UNIT_PRICE", "QUANTITY"])[["UNIT_PRICE", "QUANTITY"]].corr().iloc[0, 1]  # q16 -> -0.071331...
```

## Independent cross-check (second parser, not pandas)

Four of the values (q06 min/max, q07 count, q10 sum, q11 nunique) were
additionally recomputed using Python's stdlib `csv.DictReader` -- a completely
separate CSV parser implementation from pandas's C parser -- and matched
exactly:

```python
import csv
rows = list(csv.DictReader(open("test_files/Processed_Quotes.csv", newline="", encoding="utf-8", errors="replace")))
len(rows)                                                           # 33125 (matches pandas row count)
sum(1 for r in rows if r["STATUS"] == "LOST")                       # 14673 (matches q07)
prices = [float(r["UNIT_PRICE"]) for r in rows if r["UNIT_PRICE"]]
min(prices), max(prices)                                            # 0.0, 215000.0 (matches q06)
qtys = [float(r["QUANTITY"]) for r in rows if r["QUANTITY"]]
sum(qtys)                                                            # 3436556.0 (matches q10)
len({r["CUSTOMER_NO"] for r in rows if r["CUSTOMER_NO"]})            # 2008 (matches q11)
```

This also confirms the earlier phase's note about `wc -l` (46,573) vs. the
parsed row count (33,125): both parsers independently land on 33,125 rows, so
the difference is embedded newlines inside quoted CSV fields, not a parsing
bug in either tool.

## Hand spot-checks

- q06 max ($215,000.00): row `PART_NUMBER=902-00001-05`, `STATUS=LOST`,
  `EXT_PRICE=$430,000.00` -- exactly 2x UNIT_PRICE, consistent with a real
  quantity-2 quote even though that row's `QUANTITY` cell itself is null.
- q06 min ($0.00): real rows with an unpriced/zero-priced quote line (e.g.
  `PART_NUMBER=SL-2221M2C8`, `STATUS=QTE`); no negative values exist anywhere
  in `UNIT_PRICE`, `EXT_PRICE`, or `QUANTITY` (checked with
  `(df[col] < 0).sum() == 0` for all three).
- q16: deliberately paired `UNIT_PRICE` with `QUANTITY`, not `EXT_PRICE`,
  because `EXT_PRICE ~= UNIT_PRICE * QUANTITY` holds for ~80% of rows
  (18,738 / 23,269 within 1 cent), which would make a UNIT_PRICE-vs-EXT_PRICE
  correlation trivially/tautologically high rather than a genuine test.

## Scoring

See each question's `scoring` block in `quotes_question_set.json` for the
exact rule (`exact_int`, `exact_string`, `tolerance_abs`, or
`tolerance_abs_multi` for questions with more than one required field, e.g.
q06's min+max or q14/q15's category label + its average). All ground truth
values and tolerances were fixed before any LLM/tool-calling answer existed.

## Closed gaps: q05, q16 (root cause + fix + live re-verification)

The original `run_benchmark.py` run (`benchmark_results.json`) missed both of
these under the TOOLS condition. Both are now closed; the tool-calling model
answers correctly, unprompted, in a real run.

### q05 -- sample std dev of UNIT_PRICE

- **Miss:** `benchmark_results.json` recorded `value=2332.0030805` vs
  `ground_truth=2331.963152` (tol 0.01). Root cause: `mojo/engine/stats.mojo`
  had `compute_mean` and `compute_variance` but no direct standard-deviation
  kernel, so the model had to chain `execute(compute_mean)` ->
  `execute(compute_variance)` and take a manual square root itself in its own
  (lower-precision) arithmetic -- that manual step is where the error came
  from, not the kernels.
- **Fix:** added `stats.compute_std(v, n, mean) -> Float64` (additive,
  `sqrt(compute_variance(...))` in one kernel call; `compute_variance`/
  `compute_mean` untouched), wired into the runtime contract, capability
  manifest, dispatch table, and golden-vector test suite. See
  `probe_compute_std_kernel.py` for a standalone, non-LLM proof against the
  real compiled kernel.
- **Live re-verification (2026-08-04, gpt-5-mini, TOOLS condition only, real
  API run via `rerun_final_two_gaps.py`, unmodified system prompt -- the model
  was never told the new kernel's name):** the model called
  `list_capabilities(query='std')`, found `stats.compute_std` on its own in
  the search results (alongside five unrelated `*_std*` kernels from other
  modules), called `explain('stats', 'compute_std')`, fetched `UNIT_PRICE` via
  `get_column`, computed the mean via `execute(stats.compute_mean)`, then
  called `execute(stats.compute_std, ...)` with that mean. Final answer
  `2331.9631517502244` vs ground truth `2331.963152` (tol 0.01) -- **correct**.
  Total cost for this question: $0.0136.

### q16 -- Pearson correlation of UNIT_PRICE vs QUANTITY

- **Miss:** `benchmark_results.json` recorded `value=-0.0016079675984121261`
  vs `ground_truth=-0.071331` (tol 0.001) -- not just outside tolerance but the
  wrong sign region entirely. Root cause: the only column-reading tool at the
  time, `get_column`, reads one column and drops **its own** nulls
  independently of any other column. The model called `get_column('UNIT_PRICE',
  dropna=True)` (29,204 values) and `get_column('QUANTITY', dropna=True)`
  (27,066 values) separately, then fed both into
  `stat_tests.pearson_r_strict`, which silently zipped/truncated two
  differently-null-filtered, no-longer-row-aligned lists -- a confidently
  wrong correlation over mismatched pairs, not a kernel bug.
- **Fix:** added `get_columns(columns, filter_column=None, filter_value=None,
  dropna=True)` in `tools.py` -- takes two-plus column names up front, drops a
  row if **any** requested column is null there (matching
  `df.dropna(subset=[...])`'s own semantics), and returns every column's
  values in that same jointly-filtered row order, each backed by its own
  `result_id`. Its schema description explicitly steers a model toward it for
  any multi-column statistic. `get_column` is unchanged. See
  `probe_get_columns_correlation.py` for a standalone, non-LLM proof that
  reproduces the real 29,204-vs-27,066 length mismatch and shows the aligned
  path lands on q16's own recorded `n=23269`.
- **Live re-verification (2026-08-04, gpt-5-mini, TOOLS condition only, real
  API run via `rerun_final_two_gaps.py`, unmodified system prompt -- the model
  was never told the new tool's name):** the model called
  `list_capabilities(query='pearson')`, `explain('stat_tests',
  'pearson_r_strict')`, then went straight to `get_columns(['UNIT_PRICE',
  'QUANTITY'])` (picked over two separate `get_column` calls purely from the
  tool's own schema description, which was visible to it side by side with
  every other tool) and fed both result_ids into
  `execute(stat_tests.pearson_r_strict, ...)`. Final answer
  `-0.07133063138937178` vs ground truth `-0.071331` (tol 0.001) --
  **correct**. Total cost for this question: $0.0174.

Combined live re-verification cost for both questions: $0.017395 (13 API
calls, well under the $3 budget cap). Full transcript in
`benchmarks/algenta_llm_tools/eval/final_two_gaps_rerun_results.json` and
`rerun_final_two_gaps.py`.
