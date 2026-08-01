---
icon: magnifying-glass-arrow-right
description: Code retrieval quality on CoIR, measured with nDCG@10 against BM25 baselines evaluated on the same harness.
---

# Code retrieval quality

The retrieval engine indexes code, so quality is measured on CoIR, a code-specific
information-retrieval benchmark. All systems on this page are evaluated by `mteb.evaluate`
through the `mteb` `SearchProtocol` interface, on the same data and the same scoring path.

**Metric:** nDCG@10. Higher is better.

## Results

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

The ratio column compares against the higher of `bm25-ref` and `bm25-code` on each task.
Average nDCG@10 is 0.553, versus 0.502 for the per-task best baseline. Rows are ordered by
ratio, descending.

## Method

* All systems are scored by `mteb.evaluate` through the same `SearchProtocol` interface.
* Baseline figures are runs executed on 2026-07-21 on this harness.

## Scope

* `AppsRetrieval`, CoIR's eighth task, pairs long natural-language problem statements with
  code. Lexical methods score near zero on it (baselines: 0.001, 0.048, 0.014), so it is out
  of scope for this lexical-retrieval comparison.
* This page measures retrieval quality. Latency and throughput are measured separately.
* nDCG@10 measures ranking quality within the top ten results.

## See also

* [Benchmarks](overview.md)
* [Compute kernels](compute-kernels.md)
* [Runtime library catalog](../engine/runtime-library-catalog.md)
