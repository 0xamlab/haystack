---
icon: robot
description: gpt-5-mini answering 16 real questions against a 33,125-row CSV, with and without Algenta's tool-calling access to its own compiled engine — 15 of 16 correct with tools, 1 of 16 without.
---

# LLM tool-calling uplift

A language model asked a numeric question about a dataset it has never seen has exactly one
option: guess from whatever it has memorized about datasets that look like this one. Algenta's
tool-calling surface gives it a second option — call a real, compiled kernel over the real data
and report what it returns. This page measures the gap between those two options on the same
questions, the same model, and the same data.

{% hint style="success" %}
**With tool access to Algenta's engine, gpt-5-mini answers 15 of 16 questions correctly. Without
it, working from the schema alone, it answers 1 of 16.**
{% endhint %}

## Results

16 objective, numerically-scored questions against a real 33,125-row CSV of purchase-quote line
items, asked twice each: once "bare" (schema visible, no data, no tools) and once with Algenta's
tool-calling surface available. Every question has a fixed ground-truth value and a tolerance,
computed independently of Algenta before either arm ran (see [Method](#method)).

| | bare | tools |
| --- | --- | --- |
| Correct | 1 / 16 | **15 / 16** |
| Real API cost | $0.0131 | $0.2662 |
| API calls | 16 | 126 |
| Prompt / completion tokens | 6,245 / 5,781 | 822,383 / 30,300 |

Total real, usage-priced cost for both arms across all 16 questions: **$0.279319**.

| id | question | ground truth | bare | tools |
| --- | --- | --- | --- | --- |
| q01 | 90th percentile of UNIT_PRICE | 1905.48 | 1200 ✗ | 1905.48 ✓ |
| q02 | 25th percentile of EXT_PRICE | 1275.25 | 150 ✗ | 1275.25 ✓ |
| q03 | median EXT_PRICE | 6052.1 | 250 ✗ | 6052.1 ✓ |
| q04 | mean UNIT_PRICE | 779.182035 | 285.0 ✗ | 779.1820350636932 ✓ |
| q05 | sample std dev (ddof=1) of UNIT_PRICE | 2331.963152 | 2100.0 ✗ | 2332.0030828729 ✗ |
| q06 | min/max UNIT_PRICE | 0.0 / 215000.0 | 0.0 / 1000000.0 ✗ | 0.0 / 215000.0 ✓ |
| q07 | count of STATUS == 'LOST' | 14673 | 1800 ✗ | 14673 ✓ |
| q08 | sum EXT_PRICE where CUST_TYPE == 'OEM' | 169562999.02 | 6250000 ✗ | 169562999.02 ✓ |
| q09 | average QUANTITY where STATUS == 'ORDER' | 261.723926 | 4.2 ✗ | 261.7239263803681 ✓ |
| q10 | sum of QUANTITY | 3436556.0 | 120000 ✗ | 3436556 ✓ |
| q11 | distinct CUSTOMER_NO values | 2008 | 3500 ✗ | 2008 ✓ |
| q12 | distinct non-null STATUS values | 12 | 12 ✓ | 12 ✓ |
| q13 | fraction with AUTO_QUOTED == 'Y' | 0.03963 | 0.6 ✗ | 0.0396304578949 ✓ |
| q14 | CUST_TYPE with highest average UNIT_PRICE | MILITARY, 12515.95 | MILITARY, 4500.0 ✗ | MILITARY, 12515.949999999999 ✓ |
| q15 | STATUS with highest average EXT_PRICE | QTE, 60485.014002 | ORDER, 11250.0 ✗ | QTE, 60485.01400237531 ✓ |
| q16 | Pearson r(UNIT_PRICE, QUANTITY) | -0.071331 | -0.12 ✗ | -0.07133063138937178 ✓ |

Every value the tools arm gets right, it gets right to six or more significant digits — these
are real kernel outputs, not values rounded to look plausible. The bare arm's only correct
answer, q12, is a low-cardinality count a model can plausibly guess without seeing the data;
every arithmetic, percentile, sum, group-by and correlation question misses, several by more
than an order of magnitude.

## Method

* **Dataset.** `test_files/Processed_Quotes.csv`, 33,125 real purchase-quote line items, loaded
  through Algenta's own local file connector — `Runtime(mode="local").connect(csv_path)` — the
  same production CSV parser and connector path any `pip install algenta` caller uses. No cloud
  call and no sidecar process are involved; the connector and the kernels both run in-process.
* **Model.** `gpt-5-mini`, called live via the OpenAI API, both arms, all 16 questions, real
  usage-based cost taken from each response's own token counts.
* **Bare arm.** The question plus the dataset's schema (column names and types, no row data, no
  computed statistics) in the prompt. No tools. One API call per question.
* **Tools arm.** The same question, with six tools exposed via OpenAI function calling, every one
  of them dispatching into the real compiled Mojo engine or a plain read of the real CSV — there
  is no Python-side statistics computation standing in for the engine on this path:
  * `list_capabilities` — search the capability catalog for a candidate kernel.
  * `explain` — get a kernel's exact signature and declared properties.
  * `get_column` / `get_columns` — read one or more real columns from the connected dataset,
    data access only.
  * `execute` — dispatch a named kernel (for example `stats.compute_mean`,
    `stats.quantile`, `stat_tests.pearson_r_strict`) against real, connected data and return
    its real output.
  * `group_by_aggregate` — group real rows by a column and aggregate another, in one kernel
    dispatch.
* **Scoring.** Every ground-truth value was computed independently with pandas directly against
  the CSV before either arm ran, and cross-checked for several questions with a second, unrelated
  CSV parser (Python's `csv.DictReader`) to rule out a shared parsing bug. Each question carries
  a fixed tolerance (exact match for counts and category labels, absolute tolerance for
  floating-point statistics) applied identically to both arms.

## Scope

* **One dataset, one model, one 16-question set.** This page is not a claim about every dataset,
  every model, or every kind of question — it is this CSV, `gpt-5-mini`, and these 16 numeric
  questions, run live.
* **Numeric, single-answer questions only.** All 16 questions score a single number, pair of
  numbers, or category label against a fixed ground truth. Open-ended or multi-step reasoning
  questions are out of scope for this page.
* **Cost reflects this workload, not a ceiling.** $0.27 for 16 questions across both arms on this
  model's pricing; heavier questions (multi-category group-bys) cost more in tool calls than
  simple lookups, which is visible in the per-question API-call counts in the source results.

## Reproduce

The benchmark's own harness doubles as usage documentation for the same six tools:

```text title="run the full benchmark"
python3 -m benchmarks.algenta_llm_tools.eval.run_benchmark
```

The question set, fixed ground truth and scoring rules are in
`benchmarks/algenta_llm_tools/eval/quotes_question_set.json`; how each ground-truth value was
derived (including the independent cross-check) is in
`benchmarks/algenta_llm_tools/eval/README.md`. The tool implementations themselves —
`list_capabilities`, `execute`, `explain`, `get_column`, `get_columns`, `group_by_aggregate` — are
in `benchmarks/algenta_llm_tools/tools.py`, built entirely on the public Algenta Python SDK
(`algenta.MojoRuntime`, `algenta.Runtime`), the same surface any caller has access to.

## See also

* [Benchmarks](overview.md) — methodology and what is not published.
* [Dataframe group-by](dataframe-groupby.md) — Algenta's own group-by engine measured directly, without an LLM in the loop.
* [Declared capabilities](../engine/capabilities.md) — the catalog `list_capabilities` and `explain` search.
* [Route & execute capabilities](../guides/capabilities.md) — calling the same kernels directly, without a model choosing the calls.
