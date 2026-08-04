# quotes_question_set.json

16 objective, numerically-scoreable questions against the real
`test_files/Processed_Quotes.csv` corpus (33,125 parsed rows), for benchmarking
an LLM+tool-calling system's numeric answers against fixed ground truth.

## Dataset provenance and anonymization (2026-08-04)

`test_files/Processed_Quotes.csv` originates from a real business's real quote
line-item export. The original export carried customer names, sales-rep names,
free-text notes embedding rep names and timestamps (`PRICING_METHOD`), part
numbers/descriptions, and other identifying/quasi-identifying columns -- none
of which this benchmark's schema, tools, or question set ever reads (see
`DATASET_DESCRIPTION`/`TOOLS_SUFFIX` in `run_benchmark.py`, and `KEEP` below).
The file was reduced to exactly the 7 columns actually used --
`UNIT_PRICE, EXT_PRICE, QUANTITY, STATUS, CUST_TYPE, CUSTOMER_NO, AUTO_QUOTED`
-- with every other column dropped, and `CUSTOMER_NO` remapped through a
deterministic bijection to a synthetic sequential id (preserving `nunique()`
and grouping structure exactly, breaking traceability to any real customer).
Row order and every numeric/categorical value in the 7 kept columns are
untouched, so every ground-truth value below, and every kernel result in
`benchmark_results.json`, is unchanged by this. If this dataset is ever
swapped or extended, apply the same reduction before it can be read by
anything that surfaces results externally (a GitBook page, a shared report,
etc.) -- never re-add or re-derive from the dropped columns for that purpose.

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

## Token/cost investigation (2026-08-04): the previews were the real bloat, and caching was already working

A prior full-16-question run's TOOLS condition measured 822,383 prompt tokens
across 126 API calls -- disproportionate for 16 questions, and it looked like
OpenAI's automatic prompt caching (a >=1024-token matching prefix reused at a
discount, server-side, no code required beyond a stable/growing message
history -- which `run_with_tools` already has) might not be firing. It was:
`_cost_usd` priced 100% of every prompt token at the full $0.25/1M input rate
and never read `usage.prompt_tokens_details.cached_tokens`, so the real cost
and the real cache-hit rate were both invisible, not necessarily zero.

Three real, additive fixes, one live 16-question rerun to verify:

1. **`truncate.py`'s array-preview budget was the dominant real bloat.**
   `get_column`/`get_columns` previewed up to 500 elements / 32KB per call --
   but every tool schema already steers the model to pipe a column's
   `result_id` straight into `execute()` for any real computation (see
   `GET_COLUMN_SCHEMA`/`EXECUTE_SCHEMA`), so the model never needs to read
   hundreds of raw values back. That oversized, mostly-unread preview stayed
   in the growing `messages` history for the rest of that question's turn
   loop, compounding on every subsequent call. Cut to 20 elements / 3KB
   (`MAX_ELEMENTS_TO_MODEL`, `MAX_ELEMENT_BYTES_TO_MODEL`); row-shaped
   (tabular) results keep their original, already-tight 25-row/250-cell
   budget since a model plausibly does read a few real rows to sanity-check
   shape before aggregating.
2. **Added `usage.prompt_tokens_details.cached_tokens` tracking** to
   `CostTracker`, pricing the cached and uncached portions of every call's
   prompt tokens separately at their real, live-checked rates (gpt-5-mini:
   $0.25/1M input, $0.025/1M cached input -- a 90% discount, confirmed at
   developers.openai.com/api/docs/pricing 2026-08-04). This is the only way
   to answer "is caching firing" honestly instead of assuming either "it's
   fine" or "it's broken."
3. **Added an in-process dedup cache** at the `TOOL_FUNCTIONS` dispatch layer
   (`tools.py`), mirroring mission's own real, tested
   `registerSqlSourceWithCache` fingerprint-cache pattern
   (`agent-algenta-tool-helpers.ts`): a repeated tool call with byte-identical
   arguments returns the same already-real result instead of re-dispatching
   the kernel/data-access. Every dataset+kernel is immutable for the life of
   one process, so this is memoization of dispatch, not Python-side
   recomputation. It mainly saves real compute/latency for a model that
   re-explores the same capability query or category more than once -- it
   does not by itself shrink any individual tool-response message, since the
   API still requires one tool-role message per tool_call_id the model
   issued.

**Live 16-question rerun, same model, same questions, TOOLS condition
before vs. after (bare condition unaffected -- it never touches tools.py):**

| | before | after |
|---|---|---|
| tools_pass | 15/16 | **16/16** |
| prompt tokens | 822,383 | 471,584 (-43%) |
| cached prompt tokens (now visible) | not tracked | 384,896 (**81.6%** of prompt tokens) |
| completion tokens | 30,300 | 16,364 (-46%) |
| API calls | 126 | 103 |
| real tools-condition cost | $0.2662 | $0.0640 (**-76%**) |
| tool_dedup_hits | n/a (didn't exist) | 15 |

**The honest conclusion: OpenAI's prompt caching was already firing --
81.6% of this run's prompt tokens were served from cache -- the previous
version of this script simply had no instrumentation to see that, so an
already-large true cost looked even larger than it was. The bigger, more
addressable problem was the raw preview size itself**, which both inflates
the *uncached* token count directly and (by growing the conversation faster)
increases how much total content needs caching in the first place. Fixing
the preview budget was the higher-leverage change; the cache-visibility fix
mainly exists so this conclusion could be reached honestly instead of
guessed at.

The 16/16 in this same rerun (vs. the 15/16 the last full clean run measured,
with q05 failing) is a second independent post-#538-fix data point in q05's
favor, but is not by itself a resolution of the "does q05 fail sometimes"
question above -- see whatever live-repetition investigation is recorded
after this section (if any) for the authoritative read on that, since one
run either way is not enough reps to characterize a possibly-nondeterministic
miss.

## q05 follow-up: a second, deeper miss found by repeated live reruns (2026-08-04)

The single re-verification run above (one rep) passed, but one rep cannot
distinguish "fixed" from "got lucky" against real model sampling variance. A
follow-up diagnosis pass re-read every existing q05 transcript on `main` and
every sibling `fix/uplift-*` branch looking for a specific, more insidious
failure mode: a run that calls `stats.compute_std`, gets back the exact
correct value, and then *overrides it anyway* with a manually-recomputed,
wrong number in its final JSON answer. That exact sequence did not appear in
any existing transcript on disk -- but static transcripts are not the same
as a controlled repeated experiment, so this was tested live instead of
being assumed absent.

**Live baseline (2026-08-04, gpt-5-mini, TOOLS condition, real API calls, 5
independent fresh-conversation reps of q05 alone, unmodified `run_benchmark.py`
system prompt and `tools.py` -- run against a separate, unmodified checkout of
this same commit, i.e. with `compute_std` already available but none of the
prompt/schema changes below):** **4/5 passed, 1/5 failed** this exact way. Rep
5's tool-call log shows `execute(stats.compute_std, ...)` returning the correct
`2331.9631517502244` -- but the model's final JSON answer was
`{"value": 2332.0030818899}`, a manually-recomputed number matching the
historical "manual `sqrt(compute_variance(...))`" error signature, discarding
the correct tool result it had just received. This is the real, live-reproduced
failure mode the task set out to close -- a ~20% per-question rate in this
5-rep sample, not a hypothetical. Full transcript in
`q05_baseline_5x_before_fix_results.json`.

**Fix:** two additive changes, neither touching scoring, ground truth, or any
other tool's behavior:
1. One added sentence in `run_benchmark.py`'s `TOOLS_SUFFIX` system prompt:
   "Once a tool call's result already, directly, and completely answers the
   question, use that exact returned value in your final answer -- do not
   recompute it yourself by hand, and do not call a second kernel to derive
   the same statistic a different way ... unless the question genuinely
   requires combining multiple distinct statistics."
2. A scoped, `(module, function)`-keyed note (`_FINAL_ANSWER_NOTES` in
   `tools.py`) that appends one extra sentence to `explain()`'s and
   `execute()`'s output *only* for `("stats", "compute_std")`:  "This IS the
   final sample standard deviation ... do not also call compute_variance and
   take its square root yourself." Every other kernel's `explain()`/`execute()`
   output is byte-for-byte unchanged -- this closes the real gap found during
   diagnosis, that the manifest's generic `docs` field is `"none"` for every
   kernel in the library today (a separate, repo-wide gap in the manifest
   generator, out of scope here), so nothing previously told a caller
   `compute_std`'s result was final rather than intermediate.

**Live re-verification of the fix (2026-08-04, gpt-5-mini, TOOLS condition,
real API calls, 5 independent fresh-conversation reps of q05 alone, WITH both
changes above):** **5/5 passed.** `compute_std` was called and its value used
directly in all 5 reps; `compute_variance` was never called in any rep. Total
cost: $0.0727 (47 API calls). Full transcript in
`q05_prompt_trust_fix_rerun_results.json`.

**Full 16-question regression check (2026-08-04, gpt-5-mini, same run, both
conditions, WITH the fix applied):** **16/16 tools-condition correct** (up
from 14/16 in the original `benchmark_results.json`, which predates the
`compute_std`/`get_columns` fixes entirely), **1/16 bare-condition correct**
(unchanged -- the bare/no-tools condition never sees any tool-facing text, so
it cannot be affected by this change). No regression on any of the other 15
questions; total run cost $0.2133 (118 tools-condition API calls, well under
the historical run's $0.33). Full transcript in
`full16_with_q05_trust_fix_rerun_results.json`;
`rerun_full16_with_q05_trust_fix.py` reruns it.

**Honest framing:** the diagnosis phase that preceded this fix found *zero*
occurrences of the failure mode in every static transcript already on disk --
it was only surfaced by deliberately running the exact same (then-unmodified)
prompt+tools 5 times live and observing 1 real failure. A 5-rep sample cannot
establish a precise failure rate (nor can 5/5 on the fix prove the rate is
now exactly zero) -- but a real, reproducible miss was captured going in, and
it did not recur once across 5 fix reps plus a full 16-question rerun (21
tools-condition questions total, post-fix, all correct). That is a genuine,
measured improvement, not an assumed one.
