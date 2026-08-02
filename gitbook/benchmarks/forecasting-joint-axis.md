---
icon: stopwatch
description: Forecast accuracy and latency measured together on all 100,000 M4 series against statsforecast 2.1.1 — equal or better accuracy at 2.42x-3.99x the speed, with the accuracy leaders that remain ahead named.
---

# Forecasting on the joint axis

A forecast that arrives after the decision has been taken is worth nothing, whatever its error
metric says. Accuracy and latency are therefore not two benchmarks — they are one, and a method
only wins if it is at least as accurate **and** at least as fast as the alternative.

This is not a framing invented here. Forecasting research already asks for it. Petropoulos and
Spiliotis, writing in *Foresight* 77 (2025), put it directly:

> Forecast evaluation should include assessment of the computational costs of producing it.
> ... Based on this evidence, it is time to stop evaluating forecasts purely on statistical error
> measures.

Their companion study on the M, M3 and M4 monthly series defines the cost side precisely —
"the time (in seconds) needed to fit all relevant models and estimate the prediction intervals of
the best one, averaged across time series" — and reports error and seconds in the same table
(*Wielding Occam's razor: Fast and frugal retail forecasting*, Journal of the Operational Research
Society, 2024). This page follows that shape.

**The corpus is M4** — all 100,000 competition series across six frequencies. **The reference is
statsforecast 2.1.1**, which describes itself as "Lightning fast forecasting with statistical and
econometric models" and is the most widely used implementation of exactly these models. Both arms
fit the same three models to the same series over the same horizons and are scored by the same
independent scorer.

{% hint style="success" %}
**At accuracy equal or better, Algenta is strictly faster than statsforecast 2.1.1 on every
frequency, every model and every thread setting measured — 45 of 45 rows.**

Whole-corpus wall clock at matched parallelism: **2.42x** at one thread — the conservative figure,
and the one the claim uses — rising to 3.99x at twelve workers and 3.41x at sixteen. On the same
series, Algenta's ETS(A,A,A) agrees with statsforecast to within 2.0e-8 on all 72,414 seasonal
series, its damped-trend row is more accurate on all six frequencies, and its Holt row is level.

This is Pareto dominance, not a trade. It is also a narrow claim: **on accuracy alone the top M4
entrants are still ahead of Algenta**, and that is stated below with their numbers.
{% endhint %}

## The accuracy half

Both arms' forecasts come out of the very processes that were timed, so there is no possibility of
timing one code path and scoring another. Scoring is the official M4 algebra — sMAPE, MASE against
the in-sample seasonal-naive mean absolute error, OWA against Naive2 — implemented independently in
NumPy, with the Naive2 anchors re-derived and checked against the official competition workbook.

**OWA, lower is better.** A negative delta is an Algenta win.

| Model | Series | Algenta OWA | statsforecast OWA | Delta | Series agreeing to 1e-6 | Largest relative disagreement |
|---|---|---|---|---|---|---|
| ETS(A,A,A) | 72,414 | 0.933238 | 0.933238 | +0.000000 | 72,414 / 72,414 | 2.0e-8 |
| Holt | 100,000 | 0.893182 | 0.893171 | +0.000010 | 99,936 / 100,000 | 3.4e-2 |
| Damped trend | 100,000 | 0.878523 | 0.879521 | **-0.000999** | 3,849 / 100,000 | 2.9e+1 |

Three different situations, and they are not interchangeable:

* **ETS(A,A,A) is the same answer.** Every one of the 72,414 seasonal series agrees to within
  2.0e-8 relative; the corpus OWA is identical to six decimals. What differs is floating-point
  association, not the fit.
* **Holt is level.** Both arms score sMAPE 12.789 and MASE 1.613, and 99,936 of 100,000 series
  agree to within one part in a million. The residual is a 1.0e-5 OWA deficit for Algenta — one
  part in ninety thousand, from 64 series where the two optimisers settled on different local
  optima. It rounds away at every precision the competition reports, and it is printed here rather
  than rounded away.
* **Damped trend is a genuine accuracy win, not a tie.** The two implementations fit the same model
  class with different optimisers and they do diverge — hence the large maximum disagreement — and
  Algenta is the more accurate of the two on **all six frequencies** independently, not just in
  aggregate.

The Naive2 anchors reproduce the official M4 workbook on every frequency:

| Anchor ratio, this session vs official workbook | Yearly | Quarterly | Monthly | Weekly | Daily | Hourly |
|---|---|---|---|---|---|---|
| Naive2 sMAPE | 1.00001 | 0.99996 | 0.99999 | 1.00003 | 1.00008 | 0.99999 |
| Naive2 MASE | 1.00009 | 1.00028 | 1.00034 | 1.00011 | 1.00013 | 1.00002 |

If those anchors did not land at 1.000 the scorer would be wrong and nothing else on this page
would be worth reading.

## The compute half

The claim uses **whole-corpus wall clock**: the time to fit and forecast every series the model
applies to, which is an exact measurement over the corpus rather than a sample extrapolated to it.
Per-series figures appear below for scale, but they are derived from these passes, not the claim.

Both arms are run at the same thread count, and then each at its own best setting, because
publishing only the favourable configuration would be scope-narrowing. Each figure is the minimum
across interleaved launch pairs — K=4 at one thread and at twelve workers, K=2 at sixteen — with one
full pass per launch, because a full pass over the corpus **is** the cold pass. There is no
in-process repetition anywhere in this table.

| Matched threads | Model | Series | Algenta | statsforecast 2.1.1 | Ratio | Load median |
|---|---|---|---|---|---|---|
| 1 | Holt | 100,000 | 26.61 s | 78.02 s | 2.93x | 66-127 |
| 1 | Damped trend | 100,000 | 44.73 s | 209.94 s | 4.69x | 66-127 |
| 1 | ETS(A,A,A) | 72,414 | 222.24 s | 422.61 s | 1.90x | 66-127 |
| 1 | **all three** | 272,414 fits | **293.58 s** | **710.58 s** | **2.42x** | 66-127 |
| 12 | Holt | 100,000 | 6.83 s | 55.83 s | 8.18x | 231-244 |
| 12 | Damped trend | 100,000 | 11.44 s | 84.49 s | 7.38x | 231-244 |
| 12 | ETS(A,A,A) | 72,414 | 43.35 s | 105.57 s | 2.44x | 231-244 |
| 12 | **all three** | 272,414 fits | **61.62 s** | **245.89 s** | **3.99x** | 231-244 |
| 16 | Holt | 100,000 | 7.30 s | 55.51 s | 7.60x | 160 |
| 16 | Damped trend | 100,000 | 11.20 s | 81.35 s | 7.26x | 160 |
| 16 | ETS(A,A,A) | 72,414 | 50.96 s | 99.81 s | 1.96x | 160 |
| 16 | **all three** | 272,414 fits | **69.47 s** | **236.67 s** | **3.41x** | 160 |

**The one-thread row is the one to lean on**, and it is the one measured hardest — four launch pairs
across two sessions whose load medians were 127 and 66. Both arms are single-threaded there, so
contention on a shared machine hits them alike. The parallel rows were taken at load medians of 231
and above, where a process pool has more to lose to a busy machine than a single in-process loop
does. Two independent twelve-worker sessions land at 3.98x and 3.99x, which is a reproduction rather
than a lucky window, but they were both taken on a loaded box and the conservative headline is
therefore **2.42x**, not 3.99x. Both are reported, because running only one parallelism setting
would be scope-narrowing in the other direction.

**Each side at its own best setting.** Algenta is fastest at twelve workers (61.62 s) — twelve is
exactly the performance-core count on this chip, and adding the four efficiency cores makes it
slower. statsforecast is nominally fastest at sixteen jobs (236.67 s); its sixteen-versus-twelve gap
is 3.6% across runs whose load medians differed by 71, so that is a tie and the faster of the two is
credited to it. **Own best against own best: 3.84x, with Algenta using twelve of sixteen cores
against statsforecast's sixteen.**

Per frequency, at one thread — the setting where both arms use their cheapest dispatch and no pool
overhead exists on either side:

| Frequency | Series | Holt | Damped trend | ETS(A,A,A) |
|---|---|---|---|---|
| Yearly | 23,000 | 1.94x | 1.97x | — |
| Quarterly | 24,000 | 2.45x | 3.24x | 2.06x |
| Monthly | 48,000 | 2.87x | 4.60x | 1.85x |
| Weekly | 359 | 3.46x | 6.18x | — |
| Daily | 4,227 | 3.50x | 6.67x | — |
| Hourly | 414 | 3.45x | 5.96x | 3.65x |

ETS(A,A,A) has no entry on Yearly, Weekly and Daily because those series are non-seasonal and the
model does not apply to them — which is why its corpus is 72,414 rather than 100,000.

Derived per-series hot cost at one thread, from those same whole-corpus passes rather than from a
sample: Holt 0.266 ms against 0.780 ms, damped trend 0.447 ms against 2.099 ms, ETS(A,A,A) 3.069 ms
against 5.836 ms.

## The joint result

Placing both arms on the two axes at once, which is the only placement a live decision cares about:

| Comparison | Accuracy | Compute | Verdict |
|---|---|---|---|
| ETS(A,A,A), 72,414 series | equal — OWA 0.933238 both, every series within 2.0e-8 | Algenta 1.90x-2.44x faster | **Algenta dominates** |
| Holt, 100,000 series | level — 12.789 sMAPE and 1.613 MASE on both arms; Algenta +1.0e-5 OWA | Algenta 2.93x-8.18x faster | **Algenta dominates** |
| Damped trend, 100,000 series | Algenta better, on all six frequencies — OWA 0.878523 against 0.879521 | Algenta 4.69x-7.38x faster | **Algenta dominates, on both axes** |
| FFORMA, M4 rank 2 | FFORMA better — 0.8377 against 0.8428 | not published in any primary source | **no dominance either way** |
| ES-RNN, M4 rank 1 | ES-RNN better — 0.8209 against 0.8428 | not published in any primary source | **no dominance either way** |

The first three rows are dominance in the strict sense: at accuracy equal or better, strictly faster.
None of them is a trade. The last two are not dominance in either direction and are not presented as
one — Algenta is behind on accuracy there, and their compute is not available to compare.

## Cold decision latency

Every number above starts its clock after both stacks are loaded. A live decision does not get that
courtesy: it pays whatever the stack costs before it can compute anything. Measured from **outside**
both processes — exec to answer, both arms doing the identical job of opening the frequency's
blocks, fitting one series and forecasting it — minimum over fourteen interleaved launches
across two sessions:

| Frequency, model | Algenta | statsforecast 2.1.1 | Ratio |
|---|---|---|---|
| Monthly, Holt | 73.9 ms | 1,866.6 ms | 25.3x |
| Monthly, damped | 66.0 ms | 1,760.0 ms | 26.7x |
| Monthly, ETS(A,A,A) | 67.9 ms | 1,858.2 ms | 27.4x |
| Quarterly, damped | 27.4 ms | 2,004.4 ms | 73.2x |
| Quarterly, ETS(A,A,A) | 22.6 ms | 2,073.3 ms | 91.6x |
| Quarterly, Holt | 23.6 ms | 2,244.8 ms | 95.3x |
| Hourly, ETS(A,A,A) | 22.7 ms | 1,841.7 ms | 81.3x |
| Hourly, damped | 14.4 ms | 1,870.6 ms | 129.5x |
| Hourly, Holt | 13.5 ms | 1,902.6 ms | 140.4x |

**The number to take from this table is the smallest one, 25.3x.** The rest of the spread is not a
property of the models but of how much data each frequency has to open before it can fit: the
reference arm pays an almost constant 1.8-2.2 s of interpreter startup and import on every row,
while Algenta's cost tracks the file it reads. An earlier single session put the Quarterly rows near
186x purely because its launches happened to sit at a higher load average, and importing a Python
library is exactly what a loaded machine slows down; taking the minimum over both sessions pulls
those rows down to 73x-95x, which is what the table now carries.

**Where that cost is, exactly.** It is not the models. In a fresh process, `import statsforecast`
costs 1,915 ms at its fastest and 2,226 ms at its slowest over five launches, with NumPy already
imported; constructing the model costs 0.006 ms. Algenta's symmetric cost is the launch of an
ahead-of-time compiled binary, which is included in the 13-74 ms above.

{% hint style="info" %}
**There is no JIT cost to separate out here, and that is worth stating because a reader will look
for one.** statsforecast 2.1.1 does not use Numba. Three independent checks: `numba` is not
installed or importable in the measurement environment, and every reference launch asserts and
records that; a search of the installed package for `numba` or `njit` returns nothing, because the
package ships ahead-of-time compiled C++ extensions instead; and behaviourally, in a fresh process
the first, second and third `AutoETS` calls cost 5.363, 5.150 and 5.014 ms at their minimum, so
there is no first-call penalty to find. The cold cost above is interpreter startup plus import, and
it is confined to the cold table — every warm and hot reading is taken inside an already-imported
process with the timer started after the import and after the data load.
{% endhint %}

## How each side was run

| | Algenta | statsforecast 2.1.1 |
|---|---|---|
| One thread | one in-process loop over series, zero dispatches | per-call `model.forecast(y, h)`, its cheapest path |
| Twelve and sixteen workers | `parallelize` over contiguous series chunks, one process | `StatsForecast(n_jobs=W).forecast(df, h)`, its own documented parallel path |
| Timed region | fit, forecast, store into a preallocated buffer | fit, forecast, store into a preallocated buffer |
| Outside the timed region | file reads, slicing, output writes | file reads, frame construction, output writes |

Both arms store into a preallocated buffer inside the timed region, so the comparison is symmetric.
Thread pinning for the reference arm — `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`,
`VECLIB_MAXIMUM_THREADS`, `NUMEXPR_NUM_THREADS` all set to one — is applied by the driver on every
launch and echoed back by the process, so the pinning is in the artifact rather than assumed.

Algenta's twelve-worker forecasts are **bit-identical** to its serial forecasts and to the artifacts
the accuracy table was scored from. Parallelism buys speed here at no numerical cost, which is why
the same accuracy column stands at every thread setting.

## Where Algenta is not ahead

{% hint style="warning" %}
**On accuracy alone, the top M4 entrants are still ahead, and this page does not dispute that.**
Official competition workbook, Total OWA, lower is better: **Smyl 0.8209** (rank 1), **FFORMA
0.8377** (rank 2), Algenta's most accurate configuration **0.8428**. That is a loss on the accuracy
axis and it is not reframed here.
{% endhint %}

Nor can it be turned into a joint-axis comparison, because the compute half of their coordinates is
not published:

* **FFORMA** reports no training time, no hardware, no core count and no memory in the paper, in the
  official M4 submission document, or in the authors' own reproduction guide. The strongest
  published statements are qualitative — replicating the training is "a very computationaly
  expensive process, so a pretrained model is provided", and computing the nine-method pool over
  the 100,000 series is "a very time consuming process (hours)".
* **The winning ES-RNN** likewise reports no training time. On hardware its author is explicit, and
  the frequently repeated claim that it was trained on GPUs is wrong: the programs "are using CPU,
  not GPU, and are meant to be run in parallel".

The official M4 evaluation workbook carries sMAPE, MASE and OWA and no timing column for any
method, so no entrant's compute can be recovered from the competition record either. **An
accuracy-per-unit-compute ratio against either leader would have to be invented, so none is printed
here.**

Algenta's own 0.8428 configuration is a different kind of object from the three models measured
above, and the difference matters. Holt, damped trend and ETS(A,A,A) are per-series fits with
nothing learned across series — the whole cost is the wall clock in the tables above. The 0.8428
configuration adds a learned stage on top of a candidate pool, so it has two costs, both measured
here rather than asserted: about **80 minutes** of one-time single-core training over the corpus to
produce its weights, then about **8.4 ms per series** to answer once they exist. The largest
component of that 80 minutes is a bracket between the first and last artifact written rather than an
internal timer, so it is an upper bound rather than a precise figure.

## What this page does not claim

* **The parallel Weekly and Hourly rows are excluded from every ratio quoted above.** At twelve and
  sixteen workers those two frequencies show 70x-155x, which is not kernel throughput: it is
  statsforecast's `n_jobs` process pool paying a fixed spawn cost of roughly 4.4 s per call that
  a few hundred series cannot amortise. That is a real property of its batch API, and it is a
  reason to quote Weekly and Hourly from the one-thread arm instead, which is what the table does.
* **The margin is not uniform, and the narrowest row is the honest bound.** Across the four
  one-thread launch pairs the smallest ratio is Monthly ETS(A,A,A) at 1.85x — the single largest
  block of work in the corpus, 48,000 series, and the row that dominates the ETS(A,A,A) total. Every
  other row is wider. An earlier pass on a heavily contended machine put Yearly Holt at 1.12x; with
  four launches the floor for that row settles at 1.94x, which is what the table now carries. The
  contended reading is mentioned because it is the kind of number a single unlucky pass produces,
  and a minimum over more launches is the correction for it.
* **Three models, not a forecasting suite.** Holt, damped trend and ETS(A,A,A). Nothing here says
  anything about ARIMA, TBATS, neural methods, or statsforecast's automatic model selection.
* **This is single-machine measurement.** Nothing about clusters, GPUs or distributed scheduling is
  implied.

## Reproducing these numbers

Build the Algenta arm ahead of time — `mojo run` recompiles the source on every launch, which would
have put a development-mode cost into the cold table:

```text title="build"
mojo build -I mojo/engine benchmarks/external_baselines/forecasting_m4_h2h.mojo -o build/joint/forecasting_m4_h2h
```

Whole-corpus wall clock, interleaved, at matched thread counts:

```text title="whole corpus"
./scripts/run_repo_python.sh benchmarks/external_baselines/drive_forecasting_m4.py -K 2 --mode full --reps 1 --a-workers 1 --b-workers 1 --b-dispatch percall --out build/joint/corpus_1t.json
./scripts/run_repo_python.sh benchmarks/external_baselines/drive_forecasting_m4.py -K 2 --mode full --reps 1 --a-workers 12 --b-workers 12 --b-dispatch batch --out build/joint/corpus_12w.json
```

Cold, warm and hot per-series tiers, and cold exec-to-answer measured from outside both processes:

```text title="tiers and cold start"
./scripts/run_repo_python.sh benchmarks/external_baselines/drive_forecasting_m4.py -K 6 --reps 4 --out build/joint/tiers.json
./scripts/run_repo_python.sh benchmarks/external_baselines/forecasting_m4_coldwall.py -K 7 --freq Monthly --method ETSAAA --out build/joint/coldwall.json
./scripts/run_repo_python.sh benchmarks/external_baselines/forecasting_m4_coldstart.py --out build/joint/coldstart.json
```

The accuracy half, scored from the forecasts those timed processes emitted:

```text title="accuracy"
./scripts/run_repo_python.sh benchmarks/external_baselines/forecasting_m4_equal_accuracy.py
```

The driver alternates the two arms launch by launch within every frequency, samples the one-minute
load average before every launch, and records the versions each reference process actually imported.
Set `M4_REF_PYTHON` to the interpreter that has statsforecast installed; every reference launch
echoes back the versions and the thread-pinning environment it actually ran under, so both end up in
the artifact rather than in a claim.

## Reading these results honestly

* Hardware: Apple M4 Max, 16 cores (12 performance + 4 efficiency), 128 GiB.
* This machine was shared during the measurement session and the one-minute load ranged from 26 to
  259. Absolute times are therefore upper bounds. The ratios are the result, and they reproduce at
  load 243 and at load 78 alike. Two things keep contention out of the comparison: both arms are
  interleaved inside every frequency, so a load spike cannot land on one side only; and every figure
  is a minimum across launches, and contention can only ever make a reading slower than the work
  takes, never faster, so a minimum is a floor on the true cost rather than a lucky sample.
* Versions asserted at runtime by every launch, not remembered: CPython 3.14.6, NumPy 2.5.1,
  statsforecast 2.1.1, coreforecast 0.0.18.
* OWA is a competition metric averaged over a corpus. A 0.001 OWA advantage on 100,000 series says
  nothing about any individual series.

## Related

* [Benchmarks](overview.md) — the rules every published number here follows.
* [Least-squares accuracy](least-squares-accuracy.md) — correct digits on the NIST StRD suite.
* [Dataframe group-by](dataframe-groupby.md) — group-by throughput against an established baseline.
* [Runtime library catalog](../engine/runtime-library-catalog.md) — every module and function the runtime exposes.
