---
icon: filter
description: Reciprocal-rank fusion, hybrid blending, MMR reranking and rank-quality ratios over N ranked lists, plus the moving-average, EMA, IIR and spectral-adjacent filters that operate on one numeric series.
---

# Retrieval fusion and signal kernels

Four modules, two unrelated pairs. `retrieval.fuse` and `retrieval.score` are the composition
layer that turns per-lane scores into one ranking: given N ranked lists (or a dense/sparse pair,
or a candidate set with a similarity matrix), fold them into a single order and be able to say
which lane put each item where. `signal.dsp` and `signal.filter` are unrelated to fusion — they
operate on one `List[Float64]` series at a time and answer a different question: smoothed how,
trending how, correlated with itself at what lag, above what threshold. Both pairs are frozen
compositions over even-lower-level scalar kernels in `rag_retrieval.mojo`, and neither pair has
had a narrative page before now — grep across `gitbook/` turns up all four names in exactly one
place, the auto-generated function-count table in the
[runtime library catalog](runtime-library-catalog.md).

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# lane 0 ranks docs 10, 20, 30 (ranks 1, 2, 3); lane 1 ranks docs 30, 10, 40 (ranks 1, 2, 3)
doc_ids = [10, 20, 30, 30, 10, 40]
lane_lengths = [3, 3]

fused = runtime.execute("retrieval.fuse", "rrf_fuse_flat",
                        [doc_ids, lane_lengths, 2, 60.0, 0])["result"]
fused["doc_ids"]   # [10, 30, 20, 40]
fused["scores"][0] # 0.032522474881015336 -- 1/61 + 1/62, doc 10 ranked by both lanes
fused["lane_hits"] # [2, 2, 1, 1] -- 10 and 30 were ranked by both lanes, 20 and 40 by one
```

## The modules

| Module | What it does |
| --- | --- |
| `retrieval.fuse` | Reciprocal-rank fusion of N ranked lists into one ranking, with per-document and per-lane attribution. |
| `retrieval.score` | Dense/sparse hybrid ranking, greedy MMR reranking, and rank-quality ratios — each driven across a whole candidate list by a frozen scalar kernel, plus the package's shared ordering, truncation and finiteness rules. |
| `signal.dsp` | Moving average, EMA, first differences, cumulative sum, 1D convolution, autocorrelation, linear detrend, [-1,1] normalization, zero-crossing counting, and threshold peak detection. |
| `signal.filter` | EMA low/high/band-pass, median filter, a fixed Savitzky-Golay smoother, moving-average filter, first-order IIR, differentiation, trapezoidal integration, SNR, and RMS. |

## `retrieval.fuse` and `retrieval.score` are the arithmetic under `retrieval.md`'s `hybrid_search` and `rerank`

[Retrieval](retrieval.md) documents six Python-level verbs — `vector_search`, `sparse_search`,
`hybrid_search`, `rerank`, `filtered_search`, `provenance` — served by named backends, and its own
`## The modules` table lists exactly one dotted engine module: `vector_search`'s underlying
`vector_search` ANN kernels. It never names `retrieval.fuse` or `retrieval.score`, and that page's
own text is explicit about why: "Ranking, fusion and reranking are compiled kernels" the Python
layer marshals arguments for and decodes results from, without recomputing a score itself.
Reading `packages/algenta/algenta/retrieval_execution.py` shows exactly which kernels those are:

| `retrieval.md` verb | kernel called |
| --- | --- |
| `hybrid_search(fusion="rrf")` | `retrieval.fuse.rrf_fuse_flat` (and `rrf_provenance_flat` under `explain=True`) |
| `hybrid_search(fusion="linear")` | `retrieval.score.hybrid_rank_flat` |
| `rerank` (the diversity reranker) | `retrieval.score.mmr_select_flat` |

So this page and `retrieval.md` describe the same arithmetic at two altitudes: `retrieval.md`'s
"an empty lane and an absent lane are different" is `retrieval.fuse`'s `n_empty_lanes` counter and
its refusal to invent a rank for a lane that never ran; `retrieval.md`'s "shapes are checked before
anything is read" is `mmr_select_flat`'s `dims_fit(n, n, len(similarity))` guard below. One
function in `retrieval.score` is **not** wired to any Python verb: `retrieval_quality_flat`
(precision, citation coverage, context relevance, each with a `_known` flag) has no caller in
`retrieval.py` or `retrieval_execution.py` today. It is real, tested, and callable directly through
`runtime.execute("retrieval.score", "retrieval_quality_flat", [...])` — it is simply not yet behind
a verb.

## `signal.dsp` and `signal.filter` are a different, lower-level family from `signal_processing`

[Signal transforms and processing kernels](signal-transforms-and-processing-kernels.md) documents
six *bare*-named modules, one of which is `signal_processing` — a single file,
`mojo/engine/signal_processing.mojo`, with window functions, its own smaller spectral trio, and
peak/zero-crossing utilities keyed off a sample rate. `signal.dsp` and `signal.filter` are a
separate two-file package, `mojo/engine/signal/dsp.mojo` and `mojo/engine/signal/filter.mojo`,
under a shared `mojo/engine/signal/__init__.mojo` that never mentions `signal_processing.mojo` and
is never mentioned by it. Neither file imports the other's directory; the two families are
adjacent only in subject matter (both are "basic DSP for the decision engine," per their own
docstrings) and in the accident of dotted-vs-bare naming, not in code. `signal.dsp` and
`signal.filter` are documented here for the first time.

## `retrieval.fuse`: N lanes into a two-rank kernel, folded in pairs

| Function | What it does |
| --- | --- |
| `rrf_fuse_flat(doc_ids, lane_lengths, n_lanes, k, top_k)` | Fuses `n_lanes` ranked lists — `doc_ids` concatenated lane by lane, `lane_lengths[l]` sizing lane `l`'s slice — into one ranking via the frozen `rag_retrieval.rrf_score`. Returns a `Fusion`. |
| `rrf_provenance_flat(doc_ids, lane_lengths, n_lanes, k, top_k)` | Same arguments and the identical fold as `rrf_fuse_flat`; returns the row-per-`(document, lane)` `Provenance` table behind it, with a certificate that the rows reproduce the fused scores. |

The frozen `rrf_score(rank_dense, rank_sparse, k)` takes exactly two ranks — `1/(k+rank_dense) +
1/(k+rank_sparse)`. A retrieval contract fuses however many lanes it actually ran, so N lanes reach
that two-rank kernel as a **pair fold in ascending lane order**: lanes 0,1,2,3 fold as
`rrf_score(r0,r1,k) + rrf_score(r2,r3,k)`; an odd lane count closes with a tail term,
`rrf_score(r,r,k) / 2`, which is bit-identical to `1/(k+r)` because adding a float to itself only
increments its exponent and halving it is exact for the same reason. The fold order is part of the
contract, not an implementation detail — floating-point addition is not associative, so this is
what makes two runs over the same lanes produce the same bits.

Traced by hand on the two-lane example above (`k = 60`):

| doc | lane 0 rank | lane 1 rank | score |
| --- | --- | --- | --- |
| 10 | 1 | 2 | `1/61 + 1/62 = 0.032522474881015336` |
| 30 | 3 | 1 | `1/63 + 1/61 = 0.032266458495966693` |
| 20 | 2 | — | `1/62 = 0.016129032258064516` |
| 40 | — | 3 | `1/63 = 0.015873015873015872` |

— giving `doc_ids = [10, 30, 20, 40]`. A three-lane document ranked first by every lane folds as
pair-plus-tail, in that order: `rrf_score(1,1,60) + 1/61 = 2/61 + 1/61 = 0.04918032786885246`, not
`3 * (1/61)` computed directly, because the fold order is what the suite pins.

**An absent lane is never a rank.** A lane that ranked nothing contributes no term to any
document — not a rank of `n+1`, not `k` — so a short lane is never penalized for being short.
`n_empty_lanes` counts lanes that ranked nothing at all, and fusing an all-empty set of lanes is
`RETR_OK` with an empty ranking (`n_candidates == 0`), a real answer distinct from
`RETR_ERR_NO_LANES` (zero lanes altogether, `n_lanes == 0`). One lane ranking the same document
twice is `RETR_ERR_DUPLICATE_IN_LANE` — silently keeping the better of the two ranks would invent
an input the caller never sent.

`Provenance`'s certificate — `max_attribution_residual` — is the largest per-document
`|sum(row contributions) - fused_score| / sum(|row contributions|)`, checked against a tolerance of
`8 * hits * eps` for that document's own term count. A document ranked by one or two lanes matches
to exactly `0.0`, because the fused score and the row sum are the same two floating-point additions
in the same order; three or more lanes can differ in the last bits because the fused score folds in
pairs while the certificate sums left to right, and a residual that exceeds the tolerance is
`RETR_ERR_ATTRIBUTION` rather than a certificate that lies.

## `retrieval.score`: hybrid blend, greedy MMR, rank-quality ratios, and the package's shared rules

| Function | What it does |
| --- | --- |
| `hybrid_rank_flat(dense, sparse, n, alpha, top_k)` | Ranks `n` candidates by the frozen `hybrid_search_score(dense[d], sparse[d], alpha) = alpha*dense + (1-alpha)*sparse`, returning the blend decomposed into `dense_part`/`sparse_part` per item plus `dominant_lane`. |
| `mmr_select_flat(relevance, similarity, n, k, lambda_mmr)` | Greedy Maximal Marginal Relevance over `n` candidates via the frozen `mmr_diversity_score(relevance, max_sim, lambda) = lambda*relevance - (1-lambda)*max_sim`; `similarity` is the flat row-major `n x n` candidate-candidate matrix. |
| `retrieval_quality_flat(relevant_retrieved, cited_chunks, total_retrieved, query_terms_in_context, total_query_terms)` | Precision, citation coverage and context relevance from three frozen kernels, each paired with a `_known` flag. |
| `retrieval_rank_order(scores, ordinals)` | The one ordering for the whole package (`retrieval.fuse` included): score descending, ordinal ascending on a tie. |
| `retrieval_truncation(n_available, top_k)` | How many items a `top_k` request actually returns; `top_k == 0` means all, negative is an error. |
| `retrieval_finite(v)` | This package's single finiteness predicate — neither NaN nor `+-inf`. |
| `retrieval_status_name(code)` | The name behind a status code, e.g. `209` -> `"rrf_k_not_positive"`. |
| `retrieval_ceiling_report()` | `[MAX_RETRIEVAL_CELLS, MAX_RETRIEVAL_DIM, MAX_DOC_ORDINAL, MAX_CSR_DIM]` — the four ceilings this package enforces, read from the kernel rather than copied into a client. |

### Hybrid blending: exact at both endpoints

On `dense = [0.9, 0.1, 0.5]`, `sparse = [0.2, 0.8, 0.5]`:

```python
runtime.execute("retrieval.score", "hybrid_rank_flat",
                [[0.9, 0.1, 0.5], [0.2, 0.8, 0.5], 3, 0.5, 0])["result"]
```

| doc | dense_part (`alpha*d`) | sparse_part (`(1-alpha)*s`) | score | dominant |
| --- | --- | --- | --- | --- |
| 0 | 0.45 | 0.10 | 0.55 | dense |
| 2 | 0.25 | 0.25 | 0.50 | **tie** (`RETR_LANE_TIE = -1`, not lane 0) |
| 1 | 0.05 | 0.40 | 0.45 | sparse |

`alpha == 0.0` returns the sparse score bit-for-bit and `alpha == 1.0` the dense score bit-for-bit
— exact, because the frozen kernel computes `alpha*v + (1-alpha)*b`, and both `0.0*x` and `x+0.0`
are exact for finite `x`. `alpha` is validated against `[0, 1]`, never clamped:
`RETR_ERR_WEIGHT_RANGE` outside that range, since a blend past both lanes is an extrapolation, not
a weighting. `dense_ranks_nothing` / `sparse_ranks_nothing` flag a lane whose values are all
identical across at least two candidates — a lane that supplied no ordering at all, reported rather
than rejected, since a flat lane is only meaningful to the caller that knows whether it means
"unavailable" or a genuine tie.

### Greedy MMR, traced step by step

`relevance = [0.9, 0.8, 0.2]`, `similarity` (row-major 3x3):

```
1.00  0.95  0.10
0.95  1.00  0.10
0.10  0.10  1.00
```

At `lambda_mmr = 0.5`:

| step | scores considered | pick |
| --- | --- | --- |
| 0 | no redundancy term exists yet: `0.5*0.9=0.45`, `0.5*0.8=0.40`, `0.5*0.2=0.10` | doc 0 |
| 1 | doc 1: `0.5*0.8 - 0.5*0.95 = -0.075`; doc 2: `0.5*0.2 - 0.5*0.10 = 0.05` | doc 2 |
| 2 | doc 1 (only one left): `0.5*0.8 - 0.5*0.95 = -0.075` | doc 1 |

Result: `doc_ids = [0, 2, 1]`, `mmr_scores = [0.45, 0.05, -0.075]` — relevance alone would have
returned `[0, 1, 2]`; MMR demotes doc 1 for being 0.95-similar to the already-picked doc 0. The
first pick's redundancy term does not exist (nothing has been selected yet), so
`max_sim_known[0] == False` and `max_sim[0] == 0.0` is padding, not "measured, found zero" — it
cannot change the pick, since the term is identical for every candidate at step 0. A candidate's
running maximum similarity starts **absent**, never seeded at `0.0`: a negative similarity must
survive as the maximum, or a candidate only negatively similar to everything selected would have
its redundancy penalty understated. `lambda_mmr` is validated against `[0, 1]`, never clamped —
`lambda > 1` inverts the diversity term's sign and `lambda < 0` inverts relevance's.

`dims_fit(n, n, len(similarity))` guards the matrix shape rather than `n * n == len(similarity)`,
because that product is a wrapping 64-bit multiply — at `n = 6148914691236517206`, `n * n` wraps
to `2`, and an unguarded equality check would pass before an out-of-bounds read.

### Rank-quality ratios: absence is not zero

```python
runtime.execute("retrieval.score", "retrieval_quality_flat", [3, 2, 5, 4, 6])["result"]
# precision 0.6 (3/5), coverage 0.4 (2/5), relevance 0.6666... (4/6), all three *_known == True

runtime.execute("retrieval.score", "retrieval_quality_flat", [0, 0, 0, 0, 0])["result"]
# RETR_OK, but precision_known/coverage_known/relevance_known are all False --
# the frozen retrieval_precision/citation_coverage/context_relevance_score kernels all
# return 0.0 for a zero denominator, and 0.0 is a real precision (everything retrieved
# was irrelevant), so the driver's whole job is the flag that tells the two cases apart.
```

A count that is not a subset of its total is `RETR_ERR_QUALITY_COUNTS` rather than divided —
`retrieval_precision(7.0, 5.0)` is happily `1.4` in the frozen kernel, and a precision above 1 is
not a precision, so `retrieval_quality_flat(7, 2, 5, 4, 6)` (7 relevant of 5 retrieved) is refused.

## `signal.dsp` and `signal.filter`: two formula libraries with three overlapping pairs

| Function | What it does |
| --- | --- |
| `moving_average(data, window)` | Centered moving average; `window` clamped to `len(data)`, partial average (not padding) at the edges. |
| `exponential_moving_average(data, alpha)` | `EMA[0]=data[0]`, `EMA[i]=alpha*data[i]+(1-alpha)*EMA[i-1]`; **`alpha` is clamped to `[0,1]`.** |
| `diff(data)` | First differences, `result[i] = data[i+1]-data[i]`, length `n-1`. |
| `cumsum(data)` | Running sum, same length as `data`. |
| `convolve(signal_data, kernel)` | 1D full convolution, output length `n+m-1`. |
| `autocorrelation(data, max_lag)` | Normalized autocorrelation (lag-0 == 1.0) for lags `0..min(max_lag, n-1)`; a constant series returns all `1.0`. |
| `detrend_linear(data)` | Subtracts the OLS line `a+bx` fit to the series; falls back to subtracting the mean if the fit is degenerate. |
| `normalize_signal(data)` | Rescales to `[-1, 1]`; a constant series returns all `0.0`. |
| `zero_crossings(data)` | Sign changes, including a nonzero value landing exactly on `0.0`. |
| `peak_detect(data, threshold)` | Indices where `data[i]` is a strict local maximum and `data[i] >= threshold`. |

| Function | What it does |
| --- | --- |
| `lowpass_ema(data, alpha)` | EMA low-pass, same recurrence as `exponential_moving_average`. **`alpha` is NOT clamped.** |
| `highpass_ema(data, alpha)` | `data - lowpass_ema(data, alpha)`. |
| `bandpass(data, alpha_low, alpha_high)` | `lowpass_ema(data, alpha_low) - lowpass_ema(data, alpha_high)`. |
| `median_filter(data, window)` | Sliding-window median; an even `window` is bumped to the next odd size. |
| `savitzky_golay_3(data)` | Fixed window-5, polynomial-2 smoothing, coefficients `[-3, 12, 17, 12, -3] / 35`; the first and last two points are copied unchanged, and `n < 5` returns `data` unchanged. |
| `moving_average_filter(data, window)` | Centered moving average, partial average at the edges. |
| `iir_filter_1st(data, a, b)` | First-order IIR: `y[n] = b*x[n] + a*y[n-1]`. |
| `diff_filter(data)` | First differences, `result[i] = data[i]-data[i-1]`, length `n-1`. |
| `integrate_filter(data, dt=1.0)` | Cumulative trapezoidal integration; `result[0] = 0.0`. |
| `snr(signal, noise)` | `10*log10(Σsignal² / Σnoise²)` in dB; `1e30`/`-1e30` sentinels at a zero or non-positive-ratio denominator rather than `+-inf`. |
| `rms(data)` | `sqrt(mean(x^2))`. |

### Three formulas exist in both modules — one of the three diverges on invalid input

Reading both files directly turns up three near-identical pairs, one row from each table above:

* **`moving_average` and `moving_average_filter` are bit-identical.** Same clamp
  (`window = min(window, len(data))`), same centered half-width, same partial-average loop; the
  only textual difference is `moving_average` defensively checks `cnt > 0` before dividing (`cnt`
  is always `>= 1` whenever the function reaches that line, so the branch never fires). On
  `data = [1.0, 3.0, 5.0, 7.0, 9.0]`, `window = 3`, both return
  `[2.0, 3.0, 5.0, 7.0, 8.0]` — the pinned suite (`tests/mojo/test_wave10.mojo`,
  `tests/mojo/test_wave30.mojo`) checks the interior points of each (`ma[1]==3.0`, `ma[2]==5.0`;
  `filtered[2]==3.0` on a different fixture) but neither test file cross-checks the two against
  each other.
* **`diff` and `diff_filter` are bit-identical.** `diff` walks `data[i+1]-data[i]` forward,
  `diff_filter` walks `data[i]-data[i-1]` from `i=1`; both visit the same consecutive pairs in the
  same order and both return length `n-1` (`0` for `n <= 1`, since `diff_filter`'s
  `range(1, n)` is simply empty there too, matching `diff`'s explicit `n <= 1` guard).
  `diff_filter([1.0, 3.0, 6.0, 10.0])` and `diff([1.0, 3.0, 6.0, 10.0])` both give `[2.0, 3.0, 4.0]`.
* **`exponential_moving_average` and `lowpass_ema` share a recurrence but not a guard, and that
  is a real behavioral divergence, not a naming accident.** `exponential_moving_average` clamps
  `alpha` into `[0, 1]` before using it; `lowpass_ema` uses whatever `alpha` it is given. On the
  impulse `data = [1.0, 0.0, 0.0, 0.0]` with `alpha = 2.5` (outside the valid range):

  ```python
  runtime.execute("signal.dsp", "exponential_moving_average", [[1.0, 0.0, 0.0, 0.0], 2.5])["result"]
  # [1.0, 0.0, 0.0, 0.0] -- alpha clamped to 1.0, so EMA[i] = data[i] exactly
  ```

  ```python
  runtime.execute("signal.filter", "lowpass_ema", [[1.0, 0.0, 0.0, 0.0], 2.5])["result"]
  # [1.0, -1.5, 2.25, -3.375] -- alpha used as-is; (1-alpha) = -1.5, |pole| > 1,
  # so the "low-pass" filter diverges in a growing oscillation on a signal that
  # should just decay to 0.0
  ```

  A first-order EMA recurrence is stable only while `|1-alpha| <= 1`, i.e. `alpha in [0, 2]`; at
  `alpha = 2.5` the pole magnitude is `1.5` and every step multiplies the error by `-1.5`. Calling
  `lowpass_ema` with a caller-supplied `alpha` that is not validated upstream can silently hand back
  an unstable filter rather than a smoothed signal — `exponential_moving_average` cannot produce
  this output for any input, because its clamp forecloses `|1-alpha| > 1` entirely.

### Worked examples, hand-verified against the source formulas

`convolve([1.0, 2.0, 3.0], [1.0, 1.0])` gives `[1.0, 3.0, 5.0, 3.0]` (output length `3+2-1=4`,
pinned in `test_wave10.mojo`).

`autocorrelation([1.0, 3.0, 5.0, 7.0, 9.0], 3)` — only lag 0 is pinned in the suite
(`ac[0] == 1.0`); lags 1-3 below were hand-computed independently from the source formula (mean
`5.0`, `var0 = 40.0`) rather than read off any test:

| lag | `Σ(x[i]-mean)(x[i+lag]-mean)` | value |
| --- | --- | --- |
| 0 | 40.0 | 1.0 |
| 1 | 16.0 | 0.4 |
| 2 | -4.0 | -0.1 |
| 3 | -16.0 | -0.4 |

`median_filter([1.0, 1.0, 1.0, 100.0, 1.0, 1.0, 1.0], 3)` returns `[1.0]*7` — the spike at index 3
is removed at every position its window touches, not only at index 3 itself (pinned:
`filtered[3] == 1.0`; the full-array result above was hand-traced from the same formula).

`iir_filter_1st([1.0, 0.0, 0.0, 0.0, 0.0], a=0.5, b=0.5)` returns
`[0.5, 0.25, 0.125, 0.0625, 0.03125]` — geometric decay by the pole `a = 0.5` each step (pinned:
`filtered[0]==0.5`, `filtered[1]==0.25`, and `filtered[4] < filtered[0]`).

`rms([3.0, 4.0])` is `sqrt(12.5) = 3.5355339059327378` (pinned exactly in `test_wave30.mojo`).

`snr([10.0, 10.0, 10.0, 10.0], [0.1, -0.1, 0.1, -0.1])` is exactly `40.0` dB:
`sig_power = 4*100 = 400`, `noise_power = 4*0.01 = 0.04`, ratio `= 10000`,
`10*log10(10000) = 10*4 = 40.0` (the suite only pins `s > 30.0`; the exact value above is
hand-computed from the same formula).

## Verification

Every function in `retrieval.fuse` (`test_retrieval_fuse.mojo`), `signal.dsp`
(`test_signal_dsp.mojo`) and `signal.filter` (`test_signal_filter.mojo`) has an auto-generated
smoke test: each calls the function once on a fixed `[0.5, 0.6, 0.7, 0.4, 0.3]`-style fixture and
checks only that the result has non-negative length or is finite — none pin a specific numeric
output. `retrieval.score`'s own suite file, `mojo/tests/libs/test_retrieval_score.mojo`, is the
exception on this page: despite its name, it is a 900-line hand-written known-value suite that
covers **both** `retrieval.score` and `retrieval.fuse` — every worked number in the
`retrieval.fuse`/`retrieval.score` sections above (the two-lane RRF table, the three-lane odd tail,
the hybrid endpoints, the MMR trace, the quality-ratio absence check) is pinned there, computed on
paper first per the suite's own docstring, not read off a smoke-test pass. `signal.dsp` and
`signal.filter` have the equivalent real coverage one directory over: `tests/mojo/test_wave10.mojo`
and `tests/mojo/test_wave30.mojo` are hand-written suites (not `mojo/tests/libs/test_signal_*`, and
not machine-generated) that pin `moving_average`, `convolve`, `zero_crossings`, `peak_detect`,
`iir_filter_1st`, `rms`, and more against worked values — the autocorrelation lags, the full
`median_filter` output, and the `exponential_moving_average`/`lowpass_ema` divergence above are the
only numbers on this page that are not pinned anywhere and were verified independently by
re-running the source formulas by hand.

**Next:** [Retrieval](retrieval.md) for the Python-level verbs `retrieval.fuse` and
`retrieval.score` implement, [Signal transforms and processing kernels](signal-transforms-and-processing-kernels.md)
for the unrelated bare-named `signal_processing` module, or the
[runtime library catalog](runtime-library-catalog.md) for every module and function.
