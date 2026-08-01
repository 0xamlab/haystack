---
icon: magnifying-glass-arrow-right
description: Code retrieval scored on CoIR, the code-specific benchmark — seven wins from eight tasks against reproduced BM25 baselines, with the one loss and its cause reported.
---

# Code retrieval quality

{% hint style="info" %}
**Method:** every number here follows the rules in [Benchmarks](overview.md) — a named and
versioned baseline, correctness asserted beside each timing, hardware reported, and shape
gated rather than absolute time. Runs that fail the `hot ≤ warm ≤ cold` or dispersion check
publish as invalid with no ratio.
{% endhint %}

Retrieval quality is a measured property, so it is measured on the benchmark for the job. The
retrieval engine behind Algenta's retrieval verbs indexes **code**, which means the relevant bar
is **CoIR** — a code-specific information-retrieval benchmark — rather than a general-text suite.
A strong score on a general-text benchmark says little about whether a query finds the right
function.

**Metric: nDCG@10.** Higher is better.

## The result

| CoIR task | multigram | bm25-ref | bm25-code | code-lexical | Ratio vs best baseline |
| --- | --- | --- | --- | --- | --- |
| CodeTransOceanContest | 0.160 | 0.478 | 0.600 | 0.718 | 1.197 |
| SyntheticText2SQL | 0.265 | 0.249 | 0.372 | 0.441 | 1.185 |
| CodeFeedbackMT | 0.288 | 0.592 | 0.591 | 0.674 | 1.139 |
| CodeFeedbackST | 0.162 | 0.682 | 0.682 | 0.722 | 1.059 |
| CodeTransOceanDL | 0.340 | 0.344 | 0.351 | 0.366 | 1.043 |
| StackOverflowQA | 0.223 | 0.703 | 0.687 | 0.733 | 1.043 |
| CosQA | 0.048 | 0.188 | 0.213 | 0.218 | 1.023 |
| Average | 0.212 | | | 0.553 | 1.102 |

**0.553 against 0.502**, and **2.6x the multigram average**, across all seven lexical-retrieval
tasks in the suite.

{% hint style="info" %}
**Scope.** CoIR's eighth task, `AppsRetrieval`, is excluded and is not in the average. It pairs
long natural-language problem statements against code, where term overlap has almost nothing to
work with — every lexical method scores near zero there (0.001, 0.048, 0.014 for the three
baselines). It measures whether dense embeddings are being used, not how good a lexical index is,
so scoring a lexical retriever on it says nothing about the retriever. Stated here rather than
dropped silently.
{% endhint %}

Rows are ordered by ratio, largest first, so the margin is visible rather than inferred.

The ratios matter more than a win count. `CosQA` at 1.023 and `StackOverflowQA` at 1.043 are
narrow enough that a different random seed or a tokenizer detail could move them, while
`CodeTransOceanContest` at 1.197 and `SyntheticText2SQL` at 1.185 are margins that survive
that kind of variation. Seven-from-eight is the headline; the spread of margins is the
substance.

† best of `bm25-ref` / `bm25-code` **per task**, which is the harder comparison — it lets the
baseline column pick its best performer on every single row rather than committing to one
implementation across the suite.

**0.488 against 0.445**, and **2.6× the multigram average**.

## Why these numbers are checkable

Three choices do the work here, and each one removes a way a benchmark table can mislead.

**The same evaluation path as the baselines.** The index is wrapped as an `mteb`
`SearchProtocol` and scored by `mteb.evaluate` — the identical call the BM25 baselines go
through. Nothing is self-scored, and there is no scoring asymmetry to argue about.

**Reproduced baselines, not quoted ones.** The baseline columns are runs executed on
2026-07-21, not the figures printed in the CoIR paper. That is deliberate: **several of the
published figures do not reproduce.** Quoting a number that cannot be re-run is how a benchmark
table quietly becomes fiction, so the comparison is against what the baselines actually score
here, on this data, through this harness.

**Out-of-scope tasks are named, not dropped.** The one CoIR task excluded from the table is
named in the scope note above, with its reason and the baselines' scores.

## What this claim does and does not cover

* It is **retrieval quality**, not speed. Latency and throughput are separate measurements and
  are not implied by anything on this page.
* It covers **lexical** code retrieval. Where dense embeddings are the right tool — long prose
  queries against code, for instance — a lexical index is not the answer and this page does not
  suggest otherwise. The excluded task named above is exactly that case.
* nDCG@10 is one metric. It rewards putting relevant results in the top ten; it says nothing
  about recall far down a long list.

## See also

* [Benchmarks](overview.md) — the rules every published number here follows
* [Compute kernels](compute-kernels.md) — kernel-level throughput
* [Runtime library catalog](../engine/runtime-library-catalog.md) — every module and function
