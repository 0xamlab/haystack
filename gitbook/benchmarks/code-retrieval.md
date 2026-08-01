---
icon: magnifying-glass-arrow-right
description: Code retrieval scored on CoIR, the code-specific benchmark — seven wins from eight tasks against reproduced BM25 baselines, with the one loss and its cause reported.
---

# Code retrieval quality

Retrieval quality is a measured property, so it is measured on the benchmark for the job. The
retrieval engine behind Algenta's retrieval verbs indexes **code**, which means the relevant bar
is **CoIR** — a code-specific information-retrieval benchmark — rather than a general-text suite.
A strong score on a general-text benchmark says little about whether a query finds the right
function.

**Metric: nDCG@10.** Higher is better.

## The result

| CoIR task | multigram | bm25-ref | bm25-code | **shipped** | vs best baseline |
|---|---|---|---|---|---|
| CodeTransOceanContest | 0.160 | 0.478 | 0.600 | **0.718** | ✅ |
| CodeTransOceanDL | 0.340 | 0.344 | 0.351 | **0.366** | ✅ |
| CosQA | 0.048 | 0.188 | 0.213 | **0.218** | ✅ |
| SyntheticText2SQL | 0.265 | 0.249 | 0.372 | **0.441** | ✅ |
| CodeFeedbackMT | 0.288 | 0.592 | 0.591 | **0.674** | ✅ |
| CodeFeedbackST | 0.162 | 0.682 | 0.682 | **0.722** | ✅ |
| StackOverflowQA | 0.223 | 0.703 | 0.687 | **0.733** | ✅ |
| AppsRetrieval | 0.001 | 0.048 | 0.014 | 0.034 | ❌ |
| **Average** | 0.186 | 0.445 † | | **0.488** | **7 / 8** |

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

**The loss is reported with its cause.** AppsRetrieval is a real loss and it is in the table.

## The loss, and what it tells you

On AppsRetrieval every lexical method collapses — 0.001, 0.048, 0.014 and 0.034 are all
effectively noise. That is not a close contest that went the wrong way; it is a task where
lexical matching is the wrong tool.

The reason is structural. AppsRetrieval pairs long natural-language problem statements against
code, and a long prose statement shares few literal tokens with the function that solves it.
Term overlap has almost nothing to work with. **That is embedding territory**, and no amount of
lexical tuning changes the category.

Reporting it matters more than winning it would have. A method that claims eight wins from eight
tasks on a suite this varied is either overfitted to the suite or not telling you everything, and
knowing where a technique stops working is what makes the other seven results usable.

## What this claim does and does not cover

* It is **retrieval quality**, not speed. Latency and throughput are separate measurements and
  are not implied by anything on this page.
* It covers **lexical** code retrieval. On tasks where dense embeddings are the right tool —
  AppsRetrieval being the clear example here — a lexical index is not the answer and this page
  does not suggest otherwise.
* nDCG@10 is one metric. It rewards putting relevant results in the top ten; it says nothing
  about recall far down a long list.

## See also

* [Benchmarks](overview.md) — the rules every published number here follows
* [Compute kernels](compute-kernels.md) — kernel-level throughput
* [Runtime library catalog](../engine/runtime-library-catalog.md) — every module and function
