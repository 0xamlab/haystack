---
icon: heart-pulse
description: Kaplan-Meier and Cox proportional hazards, against lifelines 0.30.0 — zero losses across every cell measured, from 3.0x to 142.9x.
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
**Zero losses. Every one of the 10 gate-clean cells measured favors Algenta, from 3.0x
(Kaplan-Meier on a million synthetic event times) to 142.9x (Cox on a small synthetic
covariate set) — and the 5 cells that failed this run's own noise gate still show Algenta ahead
in their raw numbers, just not clean enough to publish a ratio for.**
{% endhint %}

## Results

| fit | data | n | p | lifelines | ours | speedup |
| --- | --- | --- | --- | --- | --- | --- |
| Kaplan-Meier | Rossi (real) | 432 | — | 2.01 ms | 0.029 ms | **69.4x** |
| Kaplan-Meier | synthetic | 10,000 | — | 5.64 ms | 0.995 ms | **5.7x** |
| Kaplan-Meier | synthetic | 100,000 | — | 34.91 ms | 10.69 ms | **3.3x** |
| Kaplan-Meier | synthetic | 1,000,000 | — | 324.35 ms | 107.43 ms | **3.0x** |
| Cox | Rossi (real) | 432 | 7 | 14.62 ms | 0.310 ms | **47.2x** |
| Cox | synthetic | 1,000 | 2 | 32.14 ms | 0.225 ms | **142.9x** |
| Cox | synthetic | 1,000 | 8 | 35.58 ms | 1.035 ms | **34.4x** |
| Cox | synthetic | 10,000 | 32 | 609.95 ms | 87.88 ms | **6.9x** |
| Cox | synthetic | 100,000 | 2 | 2,927.00 ms | 29.46 ms | **99.4x** |
| Cox | synthetic | 100,000 | 8 | 2,941.30 ms | 84.54 ms | **34.8x** |

Hot-tier wall time, gate-clean cells only. **10 of 15 measured cells passed this run's own
dispersion gate on both sides; every one is a win.** The remaining 5 (Kaplan-Meier at n=1,000, Cox
at n=1,000/p=32, n=10,000/p=2, n=10,000/p=8, n=100,000/p=32) failed the gate — usually on
`lifelines`' own dispersion under host load, not ours — and are excluded rather than published
with a ratio; their raw hot numbers still favor Algenta in every case (for example Cox at
n=100,000/p=32: 934 ms ours against 10,394 ms lifelines', gate-failed on lifelines' 2.15x spread).

### Correctness, checked before every timing

All 15 cells passed correctness before any timing was trusted. Kaplan-Meier: the survival curve
itself agreed with `lifelines.KaplanMeierFitter` to a relative difference of 4×10⁻¹⁵-3×10⁻¹³
across every size, real and synthetic, and the log-log confidence band agreed to ~10⁻⁹-10⁻¹⁰
absolute difference everywhere both sides define one (rows where survival collapses to exactly 0
or 1 are excluded from the band comparison, since the two libraries make a different, stated
choice about the degenerate band there — not a disagreement about the estimate). Cox: the fitted
coefficients agreed with `lifelines`' to 1.6×10⁻⁸-7×10⁻⁵ relative difference, standard errors to
1.2×10⁻¹⁰-3×10⁻⁸, and the log-likelihood to a magnitude-scaled tolerance mirroring the one the
kernel's own Newton loop already uses to decide convergence — across the real 432-subject, 7-covariate
Rossi dataset and a synthetic grid up to 100,000 subjects and 32 covariates with genuine dependence
between covariates and survival times (drawn from an actual proportional-hazards process, not
generated independently and coincidentally fit).

## Method

* **Baseline.** `lifelines` 0.30.0, Python. `KaplanMeierFitter` and `CoxPHFitter`, both defaults.
* **Real data.** `lifelines`' own bundled Rossi recidivism dataset (432 subjects, a real 1980
  study) — the exact dataset `lifelines`' own Kaplan-Meier and Cox tutorials use, loaded once and
  written to a file both implementations read identically, so there is no question of two loaders
  agreeing by luck.
* **Synthetic scaling data.** No real survival dataset exists at a million rows, so the scaling
  sweep above Rossi's size uses a closed-form generator with no library call on either side: the
  same formula, evaluated once in Mojo and once in Python, producing bit-identical IEEE-754
  doubles by construction rather than by two implementations happening to agree. Kaplan-Meier
  input carries a controlled ~25% censoring rate and a ~2.4% tie rate (ties matter to the
  algorithm, so they are present on purpose, not avoided); Cox input's survival times are drawn
  from a real proportional-hazards process driven by the same synthetic covariates, so the
  dependence a real dataset would have is present, not coincidental.
* **Two processes, not interleaved.** `lifelines` depends on `pandas`/`scipy`, which are not
  installed in the embedded Python this repo's Mojo runtime binds to, so — unlike [sort](sort.md)'s
  in-process comparison — this measurement writes each side's result to disk and compares out of
  process. Weaker evidence against contention than in-process interleaving, disclosed rather than
  presented as stronger than it is.
* **Cold / warm / hot.** Cold is the first call in-process, warm the second, hot the minimum of
  further repetitions, on both sides; a cell publishes a ratio only when both sides' hot readings
  are not slower than warm and stay within a bounded spread. This machine ran a 1-minute load
  average in the 12-36 range throughout (other work running concurrently on a shared host); 5 of
  15 cells did not clear that bar this run and are shown as excluded rather than fudged.
* **Hardware.** Apple M4 Max, 16 physical cores (12 performance + 4 efficiency). Both sides
  single-threaded for this comparison.

## What is not claimed

* **Not a claim about every survival method.** `survival_analysis` also has the Nelson-Aalen
  estimator, competing-risks cumulative incidence, and Weibull/lognormal parametric fits, none of
  which are measured on this page.
* **Not a claim at every size or shape.** Kaplan-Meier at n=1,000 and three points on the Cox
  (n, p) grid did not clear this run's noise gate and are not published with a ratio, even though
  their raw numbers also favor Algenta.
* **A real, narrow numerical edge case, disclosed rather than hidden.** Building this benchmark
  surfaced one case where `cox_fit` at a very tight tolerance (1e-9) failed to converge on a
  larger, well-conditioned synthetic dataset that a looser, still-tight tolerance (1e-7 — the
  value used throughout this page) converges on cleanly in 3 iterations, matching `lifelines` to
  ~10⁻⁶ relative on the fitted coefficients. Worth a look by whoever owns the convergence
  heuristic; out of scope for this benchmark, which uses 1e-7 throughout and states it.

## Related

* [Sort](sort.md) — a columnar kernel measured with a genuinely stronger, in-process interleaved
  methodology.
* [Graph betweenness centrality](graph-betweenness.md) — another zero-loss win, same
  correctness-first discipline.
* [Benchmarks](overview.md) — methodology and what is not published.

## Reproduce

```text title="benchmark"
python3 benchmarks/external_baselines/survival_lifelines/prep_rossi.py
python3 benchmarks/external_baselines/survival_lifelines/drive_survival.py
```

Builds the Mojo binary, dumps the real Rossi dataset once, generates the synthetic scaling data
deterministically, and runs both implementations through the correctness-then-timing procedure
described above. Requires `lifelines` in the Python environment driving the comparison (not in
the Mojo runtime's own embedded interpreter — see Method).
