---
icon: heart-pulse
description: Kaplan-Meier and Cox proportional hazards, against lifelines 0.30.0, on two current real-world datasets plus synthetic scaling — wins from 3.0x to 142.9x, one loss disclosed.
---

# Survival analysis

Kaplan-Meier estimates the survival curve itself — the probability of surviving past each
observed time, given who was still at risk. Cox proportional hazards fits a regression on top of
it: which covariates raise or lower risk, and by how much. `survival_analysis.km_fit` and
`survival_analysis.cox_fit` are additive drivers over the frozen product-limit arithmetic
(`survival_analysis.km` calls into the older, frozen `survival.mojo` for the core computation
rather than restating it), with Greenwood standard errors, a log-log confidence band, and — for
Cox — Efron partial-likelihood Newton-Raphson with mean-centered covariates and refusals for
singular information, separation, and a flat likelihood.

{% hint style="success" %}
**Measured against two current, independent real-world datasets — a large production
hard-drive fleet (Q4 2025) and a professional motor-racing retirement corpus spanning 2019
through the current season — plus a synthetic scaling sweep. 10 of the 11 cells measured
win, from 3.0x to 142.9x. The one loss is Kaplan-Meier on the largest, most heavily-censored
real dataset (341,664 drives, a 0.3% failure rate this quarter) — reported plainly below,
not folded into an aggregate.**
{% endhint %}

## Results

| fit | data | n | p | lifelines | ours | speedup |
| --- | --- | --- | --- | --- | --- | --- |
| Kaplan-Meier | hard-drive fleet (real) | 341,664 | — | 12.337 ms | 20.668 ms | 0.60x |
| Kaplan-Meier | car-racing corpus (real) | 2,596 | — | 1.909 ms | 0.180 ms | **10.6x** |
| Kaplan-Meier | synthetic | 10,000 | — | 5.64 ms | 0.995 ms | **5.7x** |
| Kaplan-Meier | synthetic | 100,000 | — | 34.91 ms | 10.69 ms | **3.3x** |
| Kaplan-Meier | synthetic | 1,000,000 | — | 324.35 ms | 107.43 ms | **3.0x** |
| Cox | car-racing corpus (real) | 2,596 | 2 | 10.557 ms | 0.533 ms | **19.8x** |
| Cox | synthetic | 1,000 | 2 | 32.14 ms | 0.225 ms | **142.9x** |
| Cox | synthetic | 1,000 | 8 | 35.58 ms | 1.035 ms | **34.4x** |
| Cox | synthetic | 10,000 | 32 | 609.95 ms | 87.88 ms | **6.9x** |
| Cox | synthetic | 100,000 | 2 | 2,927.00 ms | 29.46 ms | **99.4x** |
| Cox | synthetic | 100,000 | 8 | 2,941.30 ms | 84.54 ms | **34.8x** |

Hot-tier wall time per call, both arms run as separate process invocations (see
[Method](#method) for what that costs the evidence). **11 cells measured, all gate-clean.
10 wins; 1 loss, reported first rather than last.**

### Why the one loss happens

The hard-drive fleet is the largest dataset on this page by row count (341,664) and the
most lopsided by censoring: 945 failures against 340,719 still-running drives, which
collapses to only 89 distinct event times. `km_fit` still pays the cost of the full input
— sorting and scanning all 341,664 observations to build the risk set — while `lifelines`'
pandas-vectorized grouping has very little relative overhead left to pay once the data
collapses to that few distinct times. The margin is not large (0.60x, the same performance
class rather than a different one), and it does not repeat on the smaller real dataset: at
n=2,596 with a much higher 10.25% event rate and 60 distinct event times, the same kernel
is a 10.6x win.

### Correctness, checked before every timing

Every cell's `km_fit`/`cox_fit` output is compared against the matching `lifelines` fit on
the **identical input bytes** (see [Method](#method) for why identical bytes, not
independently-generated data). Kaplan-Meier: survival values agree to a relative difference
of 1.6×10⁻¹⁴ to 2.1×10⁻¹⁵ across the two real datasets, and the confidence band agrees to an
absolute difference under 4×10⁻¹¹. Cox: coefficients agree to a relative difference under
1.6×10⁻⁶, standard errors under 1.5×10⁻⁷, and the log-likelihood agrees within the same
magnitude-scaled tolerance `cox_fit`'s own convergence test uses internally. All 11 cells
passed before any cell's timing was trusted.

## Method

* **Baseline.** `lifelines` 0.30.0, Python. `KaplanMeierFitter` and `CoxPHFitter`, both
  defaults.
* **What is timed.** `survival_analysis.km_fit` and `survival_analysis.cox_fit`, called
  directly.
* **Real data: two current, independent sources, not one decades-old dataset.**
  * **Hard-drive fleet.** Backblaze's own Drive Stats dataset — daily SMART-attribute
    snapshots of every hard drive in Backblaze's production data centers, published
    quarterly and continuously updated. This page uses the Q4 2025 release (2025-10-01
    through 2025-12-31), the most recent full quarter published as of this writing:
    341,664 drives, observed from first appearance in the quarter to either failure (an
    event) or the quarter's end with the drive still running (censored) — genuinely
    survival-shaped, nothing bent to fit. 945 failures, a 0.28% event rate.
  * **Car-racing retirement corpus.** 132 real race sessions from a professional
    motor-racing series, spanning 2019 through the current season, held locally as
    decoded per-session timing records. Duration is laps completed; the event is
    retirement, determined by motor racing's own standard classification rule — a car
    that completes fewer than 90% of the race winner's laps is unclassified, one that
    reaches 90% is classified even if lapped — rather than an unpopulated raw status
    field this corpus's own decoder does not fill in (checked directly: that field reads
    zero everywhere in the corpus against a known multi-retirement session, so the
    external classification rule is what actually determines the label here, not this
    benchmark's invention). 2,596 car-race entries, 266 retirements, a 10.25% event
    rate. Cox covariates are two directly-observed quantities: starting grid position,
    and a walk-forward count of that car's prior races in the corpus.
  * A third, smaller real dataset — the 432-subject criminology study `lifelines` itself
    bundles (Rossi, Bock and Berk, 1980) — is still exercised by this benchmark's own
    test suite as a cross-check at a very different n and p, but is not part of this
    page's claims: a 46-year-old dataset does not meet the bar the rest of this page
    holds itself to.
* **Cox on the hard-drive fleet was attempted and is not reported.** At this event
  rarity (408 failures among 114,453 drives with complete covariates), `lifelines`'
  unregularized Newton-Raphson does not converge reliably on the natural covariate set —
  checked directly, not assumed: two of the five SMART attributes Backblaze's own
  reliability team has publicly identified as the strongest failure predictors read
  identically on this fleet (correlation 1.000), which makes the design matrix exactly
  singular, and `lifelines` raises `ConvergenceError: ... Matrix is singular`. Dropping
  the duplicate and log1p-transforming the remaining heavy-tailed counts lets `cox_fit`
  converge cleanly (6 Newton iterations) — but `lifelines` still fails, now with an
  overflow in its own likelihood computation. A cell with no working reference arm is
  not a comparison, so this page does not manufacture one by relaxing the correctness
  bar.
* **Synthetic scaling data.** No real survival dataset exists at a million rows, so the
  scaling sweep above uses a closed-form generator with no library call on either side:
  the same formula, evaluated once in Mojo and once in Python, producing bit-identical
  IEEE-754 doubles by construction rather than by two implementations happening to agree.
  Kaplan-Meier input carries a controlled ~25% censoring rate and a ~2.4% tie rate; Cox
  input's survival times are drawn from a real proportional-hazards process driven by the
  same synthetic covariates, so the dependence a real dataset would have is present, not
  coincidental.
* **Two processes, not interleaved.** Same reason and same disclosure as
  [top-k selection](top-k.md) and [graph betweenness](graph-betweenness.md): `lifelines`
  depends on `pandas`/`scipy`, not installed in the embedded interpreter the Mojo runtime
  binds to, so each arm runs as its own process. Both arms read the **same bytes** off
  disk — raw little-endian float64 dumps, one write, two identical reads — so this is not
  two independently-derived inputs hoping to agree.
* **Cold / warm / hot.** Rep 0 is cold (first call in that process), rep 1 is warm, the
  minimum of the remaining reps is hot — the same convention
  [sort](sort.md)/[top-k](top-k.md)/[graph betweenness](graph-betweenness.md) use. A cell
  is reported only if hot ≤ warm and the hot-repetition spread stays bounded on both arms
  independently.
* **Hardware.** Apple M4 Max, 16 physical cores (12 performance + 4 efficiency). Both
  implementations single-threaded for this comparison.

## What is not claimed

* **Not a claim about every real dataset, or every covariate set.** Two real sources are
  measured, both disclosed with their actual event rates and sizes; a third, smaller and
  much older real dataset is deliberately excluded from the claims above.
* **Not a claim that Cox converges on every real covariate set.** The hard-drive fleet's
  natural SMART covariates are a genuine counter-example, stated above rather than
  concealed by dropping the cell silently.
* **Not a claim about every survival method.** `survival_analysis` also has the
  Nelson-Aalen estimator, competing-risks cumulative incidence, and Weibull/lognormal
  parametric fits, none of which are measured on this page.
* **Not a claim about competing risks, time-varying covariates, or stratified models.**
  `cox_fit` fits a single-stratum proportional-hazards model with time-fixed covariates;
  none of this page's cells need more than that, but a dataset that does is out of scope
  here.
* **The `tol=1e-9` convergence edge case is unrelated to any cell on this page.**
  `cox_fit`'s own docstring notes `SA_ERR_SEPARATION` can trip at a tolerance this tight
  on well-conditioned synthetic data that a looser, still-tight tolerance (1e-7 — the
  value used throughout this page) converges on cleanly. Worth a look by whoever owns the
  convergence heuristic; out of scope for this benchmark.

## Related

* [Sort](sort.md) — a columnar kernel measured with a genuinely stronger, in-process
  interleaved methodology.
* [Top-k selection](top-k.md) — a bounded-heap kernel with one honest loss disclosed up
  front.
* [Graph betweenness centrality](graph-betweenness.md) — a zero-loss win against
  networkx, same two-process disclosure.
* [Benchmarks](overview.md) — methodology and what is not published.

## Reproduce

```text title="hard-drive fleet"
curl -o data_Q4_2025.zip https://f001.backblazeb2.com/file/Backblaze-Hard-Drive-Data/data_Q4_2025.zip
python3 benchmarks/external_baselines/survival_lifelines/build_drivestats_summary.py data_Q4_2025.zip drivestats_summary.csv
python3 benchmarks/external_baselines/survival_lifelines/prep_drivestats.py drivestats_summary.csv
```

```text title="car-racing corpus"
python3 scripts/timing/fetch_corpus.py --session-types Race
python3 scripts/timing/batch_replay.py --session-types Race
python3 benchmarks/external_baselines/survival_lifelines/build_motorsport_survival.py
python3 benchmarks/external_baselines/survival_lifelines/prep_motorsport.py
```

```text title="benchmark"
python3 benchmarks/external_baselines/survival_lifelines/drive_survival.py
```

`drive_survival.py` builds the Mojo binary, prepares any real dataset not yet dumped, runs
every cell above plus the legacy Rossi cross-check, and prints a
`BENCH_GATE survival_lifelines PASS|FAIL <n>` line. The car-racing corpus fetch is a real,
rate-limited download of a multi-gigabyte archive and takes substantially longer than the
benchmark itself; the dataset does not change once fetched, so this is a one-time cost.
