---
icon: chart-line
description: Forecast accuracy on the M4 competition, all 100,000 series — five benchmark rows reproduced at OWA ratio 1.000, and the fitted Holt family below the official Holt, Damped and Comb rows.
---

# M4 forecasting accuracy

The M4 competition (Makridakis, Spiliotis and Assimakopoulos, 2018) is the standard public accuracy benchmark for univariate forecasting: 100,000 real time series across six observation frequencies, each with a held-out test horizon, scored by OWA — the overall weighted average of relative sMAPE and relative MASE against the Naive2 benchmark. Lower is better, and Naive2 is 1.000 by construction.

This page scores Algenta's forecasting kernels on all 100,000 series. The reference is the official competition results workbook, and the scoring harness is validated against it directly: its OWA algebra reproduces all 413 numeric cells of the workbook, and five benchmark rows computed end to end through Algenta's own kernels land on the official values at ratio 1.000. Those five rows are what make the other four checkable.

{% hint style="info" %}
**The headline claim on this page is about accuracy, not speed.** No timing appears here, and the results do not depend on the host: independent reruns produce bit-identical forecasts. The comparison set is the competition's statistical benchmarks — the top machine-learning entrants remain ahead, and [Scope](#scope) says by how much.
{% endhint %}

## Results

Total OWA over all 100,000 series. Ratio is Algenta over official; below 1.000 means the Algenta row scores better than the official row of the same name.

| Row | Algenta OWA | Official OWA | Ratio | Verdict |
| --- | --- | --- | --- | --- |
| Naive | 1.058 | 1.058 | 1.000 | reproduces |
| sNaive | 1.078 | 1.078 | 1.000 | reproduces |
| Naive2 | 1.000 | 1.000 | 1.000 | reproduces — the OWA denominator |
| SES | 0.975 | 0.975 | 1.000 | reproduces |
| Theta | 0.898 | 0.897 | 1.000 | reproduces |
| Holt, fitted initial state | 0.893 | 0.971 | 0.920 | 8.0% below the official row |
| Damped, fitted initial state | 0.879 | 0.907 | 0.969 | 3.1% below the official row |
| Comb | 0.876 | 0.898 | 0.976 | 2.4% below the official row |
| SelectBest | 0.874 | 0.897 † | 0.974 | below every official statistical row |

† There is no official SelectBest row; the value shown is the best official statistical benchmark row (Theta, 0.897). SelectBest scores below all eight of the competition's statistical benchmarks.

Per frequency, OWA of the Algenta rows:

| Row | Yearly | Quarterly | Monthly | Weekly | Daily | Hourly | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Series | 23,000 | 24,000 | 48,000 | 359 | 4,227 | 414 | 100,000 |
| Naive | 1.000 | 1.066 | 1.095 | 1.000 | 1.000 | 3.593 | 1.058 |
| sNaive | 1.000 | 1.153 | 1.146 | 1.000 | 1.000 | 0.628 | 1.078 |
| Naive2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| SES | 1.002 | 0.970 | 0.951 | 0.974 | 1.001 | 0.990 | 0.975 |
| Theta | 0.872 | 0.918 | 0.907 | 0.969 | 0.999 | 1.005 | 0.898 |
| Holt, fitted | 0.826 | 0.910 | 0.942 | 0.959 | 0.992 | 1.045 | 0.893 |
| Damped, fitted | 0.816 | 0.895 | 0.925 | 0.928 | 0.990 | 0.989 | 0.879 |
| Comb | 0.822 | 0.896 | 0.913 | 0.935 | 0.977 | 1.005 | 0.876 |
| SelectBest | 0.812 | 0.889 | 0.918 | 0.928 | 0.987 | 0.992 | 0.874 |

### Cross-check against statsforecast on the same series

The fitted rows are also compared against statsforecast 2.1.1 running its equivalent models on identical inputs — the same 100,000 deseasonalised series, scored by the same harness:

| Arm | Total sMAPE | Total OWA |
| --- | --- | --- |
| Algenta Holt, fitted | 12.789 | 0.893 |
| statsforecast `AutoETS(model="AAN", damped=False)` | 12.789 | 0.893 |
| Algenta Damped, fitted | 12.398 | 0.879 |
| statsforecast `AutoETS(model="AAN", damped=True)` | 12.423 | 0.880 |

The Holt totals agree to the third decimal and the damped totals differ by 0.024 sMAPE. Two independent implementations landing on the same value, both well below the official 0.971 and 0.907 rows, means the margin over the official rows comes from the quality of the fitted initial state, not from scorer drift.

## Method

### Dataset

The public M4 dataset, complete — no sampling, no exclusions. Every row in the tables above returned a success status on all of its series; a failed fit is reported through a status code, never silently replaced with a fallback value.

| Frequency | Series | Horizon | Seasonal period |
| --- | --- | --- | --- |
| Yearly | 23,000 | 6 | 1 |
| Quarterly | 24,000 | 8 | 4 |
| Monthly | 48,000 | 18 | 12 |
| Weekly | 359 | 13 | 1 |
| Daily | 4,227 | 14 | 1 |
| Hourly | 414 | 48 | 24 |

### Metrics, exactly as the competition defines them

* **sMAPE**, 200-form: the mean over the horizon of `200 * |y - f| / (|y| + |f|)`.
* **MASE**: the mean over the horizon of `|y - f|`, divided by the in-sample mean absolute seasonal difference `mean(|y[t] - y[t-m]|)` of the training series, where `m` is the seasonal period.
* **OWA**: `0.5 * (sMAPE / sMAPE_Naive2 + MASE / MASE_Naive2)`, taken on the per-frequency aggregate means. The Total row aggregates sMAPE and MASE weighted by series count across frequencies, then takes OWA against Naive2's Total aggregates — the official workbook's own convention.
* **Naive2**: multiplicative classical-decomposition seasonal adjustment, applied when the competition's autocorrelation seasonality test at the seasonal lag fires; the forecast is the last deseasonalised value carried forward and reseasonalised.

The harness's algebra is validated by exact reproduction, not by inspection: it reproduces all 413 numeric cells of the official results workbook, and the five anchor rows — Naive, sNaive, Naive2, SES, Theta — computed end to end through Algenta's kernels, match the official values at every frequency with a worst per-frequency deviation of 0.027 sMAPE, 0.002 MASE and 0.002 OWA (Theta, Weekly).

### Pipeline

The pipeline mirrors the official benchmark code: Naive and sNaive run on the raw series; SES, Holt, Damped and Theta run on the seasonally adjusted series and are reseasonalised; Comb is the arithmetic mean of the SES, Holt and Damped forecasts. Every forecast comes out of an engine kernel — the harness moves bytes and applies the scoring algebra above, nothing else.

The rows that beat their official counterparts differ from the official method in exactly one respect. The official Holt and Damped benchmarks initialise the level and trend states from the first two observations, unfitted; Algenta's `holt_fitted` and `damped_fitted` drivers fit the smoothing parameters and the initial state jointly, matching the statsforecast 2.1.1 formulation, with `fitted_init_solve` providing the closed-form least-squares initial state at fixed parameters. `select_best_fitted` chooses per series among SES, fitted Damped and Theta by in-sample one-step mean absolute error.

### Hardware independence

These are accuracy results: they contain no timings, and the values do not depend on the machine. Reruns of the full 100,000-series pass produce bit-identical forecasts, and the tables above were regenerated from a clean checkout of the shipping source before publication.

## Scope

* **The comparison set is the competition's statistical benchmarks.** SelectBest at 0.874 is below all eight official statistical benchmark rows and above the competition's top entrants — the winner, a hybrid method, scored 0.821 Total OWA and the runner-up, a combination method, 0.838. This page claims the statistical-benchmark result and nothing further.
* **The official Hourly Holt, Damped and Comb values are not reproducible from the published method.** The workbook lists Hourly OWA 2.749 (Holt), 1.141 (Damped) and 1.556 (Comb); this pipeline obtains 1.045, 0.989 and 1.005, and statsforecast 2.1.1 on the same series agrees with this pipeline (1.045 and 0.989), not with the workbook — a known discrepancy of the official benchmark code on the Hourly subset. The anchor rows, including their Hourly cells, do reproduce. The headline margins do not depend on this: excluding Hourly entirely, Holt is 7.2%, Damped 3.1% and Comb 2.1% below the official rows.
* **The seasonal fitted variant, ETS(A,A,A), is currently behind statsforecast.** On Quarterly it trails statsforecast `AutoETS(model="AAA")` by 0.397 sMAPE (10.873 against 10.476), and on Monthly by 0.024 MASE (0.974 against 0.950, with a Monthly sMAPE 0.056 lower). Its seasonal initial states come from the decomposition rather than a joint fit. It is not a row in the tables above.
* **One competition, one metric family.** These results are M4 under sMAPE, MASE and OWA. They say nothing about other datasets, other horizons, probabilistic accuracy, or speed.

## Reproduce

The entry points behind every fitted row are `holt_fitted`, `damped_fitted` and `fitted_init_solve` in `forecasting.fitted`, and `select_best_fitted` in `forecasting.select`, over the baseline, SES, Theta and deseasonalisation kernels in `forecasting.point`. Their unit suites are `mojo/tests/libs/test_forecasting_fitted.mojo` and `mojo/tests/libs/test_forecasting_select.mojo`, and the package's scaling gate runs from the repository:

```text title="benchmark"
mojo run benchmarks/mojo_benchmarks/bench_forecasting.mojo
```

The gate checks scaling properties — including that the closed-form initial-state solve is one linear pass and that a fitted driver's total cost stays linear per evaluation — rather than absolute times, which vary by machine.

The M4 dataset and the official results workbook are public, published by the M4 organisers in the `Mcompetitions/M4-methods` repository. The [Method](#method) section defines the complete scoring algebra; any M4 scorer that reproduces the official anchor rows will reproduce the tables above from the entry points named here. Accuracy carries no timing component, so no particular hardware is required.

## See also

* [Benchmarks](overview.md) — methodology and what is not published.
* [Code retrieval quality](code-retrieval.md) — nDCG@10 on CoIR against reproduced BM25 baselines.
* [Compute kernels](compute-kernels.md) — the matrix kernel results.
* [Runtime library catalog](../engine/runtime-library-catalog.md) — every module and function the runtime exposes.
