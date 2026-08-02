# Heston-QE + Longstaff-Schwartz against QuantLib — an honest, mixed result

Updated: 2026-08-01

## Read this first

This is a narrower, separate comparison from `STAC_A2_WORKLOAD.md`. That page compares our
Mojo implementation against **published, audited STAC-A2 hardware results** and states plainly
that we lose there, by a lot, for structural reasons (scalar fp64, CPU-only, a loaded shared
machine, no vendor-tuned Pack). This page compares the same underlying kernels
(`mojo/engine/quantfin/heston.mojo`) against a **real, installed, measured opponent** —
[QuantLib](https://github.com/lballabio/QuantLib) 1.43, the open-source pricing library real
quant desks use — on a single-asset contract, with QuantLib actually installed and run here, not
read from a paper.

**Verdict: no outright win survives scrutiny.** On accuracy, the two independent semi-analytic
Heston prices agree to 0.00000% — a strong correctness cross-check, not a competitive win. On
Monte Carlo accuracy at equal path count, QuantLib is *more* accurate than us in most cells. On
speed at matched thread count, our margin is real but small (1.1x-2.4x) and does not clearly clear
the round-to-round noise floor measured on this shared, persistently loaded machine. Per this
repository's benchmark-publication rule — a page ships only on an outright win over the
strongest installed opponent, not a proximity claim — **no GitBook page ships from this
comparison.** This file is the honest internal record instead.

## What QuantLib exposes, and what it does not

`ql.HestonProcess`'s own DEFAULT discretisation is `QuadraticExponentialMartingale` — Andersen's
QE, the same scheme `heston.mojo` runs by default. That makes QuantLib a genuine like-for-like
opponent for the European leg. For the American leg it is not: `ql.MCAmericanEngine` and
`ql.BinomialVanillaEngine` (QuantLib's public Longstaff-Schwartz and binomial engines) are wired
to a `GeneralizedBlackScholesProcess`, not a `HestonProcess`. There is no single public QuantLib
call that prices "Heston + Longstaff-Schwartz American" the way `heston_basket_price` does.

So the American leg runs on the Black-Scholes-**degenerate** corner of our own Heston model
(`xi = 0, rho = 0, v0 = theta = sigma^2`), which collapses Heston to Black-Scholes exactly and
lets QuantLib's BS-only American engines price the identical contract. `ql.FdHestonVanillaEngine`
— a PDE solver, not Monte Carlo, and genuinely Heston-native — is measured separately and never
averaged into the LSM-vs-LSM numbers: a race between a finite-difference grid and a Monte Carlo
estimator is not a race between two estimators of the same kind.

## The contract

S0=100, K=100, r=3%, q=0 (no dividends), T=1y. European leg: v0=theta=0.04, kappa=2.0, xi=0.5,
rho=-0.7 — Feller ratio 0.64, the same branch-coverage configuration `STAC_A2_WORKLOAD.md`
section 4b uses, so the QE exponential branch is genuinely exercised, not only the quadratic one.
American leg: the BS-degenerate corner of the same spot/rate/tenor, sigma = sqrt(0.04) = 0.2.

## 1. Ground truth cross-check: two independent semi-analytic Heston prices agree exactly

| Side | Method | Price |
| --- | --- | --- |
| Ours | Fourier inversion, "Little Heston Trap" (Albrecher, Mayer, Schoutens & Tistaert 2007) | 8.92941 |
| QuantLib 1.43 | `ql.AnalyticHestonEngine` | 8.92941 |

Relative difference: **0.00000%**. Two independently-implemented semi-analytic Heston pricers,
built from different code, agreeing to displayed precision is a genuine correctness result —
the same kind of thing NIST StRD's certified values gave us for least-squares, without needing an
opponent to be "beaten." It is reported here as validation, not as a win.

## 2. Monte Carlo accuracy at equal path count

Both sides price the SAME contract, SAME path counts, SAME step count (252), against their own
respective closed form above.

### European leg

| n_paths | ours price | ours rel err% | QuantLib price | QuantLib rel err% |
| --- | --- | --- | --- | --- |
| 10,000 | 9.06003 | 1.4629 | 8.89214 | 0.4174 |
| 40,000 | 8.96385 | 0.3857 | 8.92290 | 0.0730 |
| 160,000 | 8.89379 | 0.3990 | 8.94399 | 0.1633 |

QuantLib is more accurate than us at every one of these three path counts, by a factor of
2.4x-5.3x. This held whether QuantLib's engine used `"lowdiscrepancy"` or `"pseudorandom"`
sequences (both tested; both cluster in the same range), so the gap is not explained by QuantLib
using a lower-discrepancy generator than our pseudorandom Philox4x64-10 — it is more likely a
property of QuantLib's specific antithetic/path-construction details, not investigated further
here. **This is an honest loss on accuracy-per-path for the European leg.**

### American leg (BS-degenerate corner)

`rel_err%` is against each side's own CRR binomial reference (ours: European CRR, 2048 steps,
valid here only because q=0; QuantLib: `ql.BinomialVanillaEngine`, American CRR, 2000 steps).

| n_paths | ours price | ours rel err% | QuantLib price | QuantLib rel err% |
| --- | --- | --- | --- | --- |
| 10,000 | 9.58027 | 1.7831 | 9.33740 | 0.7968 |
| 40,000 | 9.21003 | 2.1504 | 9.31744 | 1.0090 |
| 160,000 | 9.26439 | 1.5728 | 9.30117 | 1.1817 |

Same pattern: QuantLib is closer to its own binomial reference than we are to ours, at every
path count.

### The negative early-exercise premium is expected, on both engines, and is not a bug

An American call on a non-dividend-paying asset is never optimally exercised early — a
model-free theorem (the discounted underlying is a martingale and the payoff is convex, so
holding to maturity dominates exercising early at every date, for ANY diffusion model, Heston
included). So the *true* American value in this corner equals the European value exactly, and
any measured "early-exercise premium" is pure finite-sample bias from the in-sample
degree-2-polynomial Longstaff-Schwartz regression. That bias runs NEGATIVE — i.e. the LSM
estimator underprices its own European anchor — for both engines:

Measured directly on `ql.MCAmericanEngine` (`polynomOrder=2`, `timeSteps=100`,
`antitheticVariate=True`) against `ql.AnalyticEuropeanEngine` on the identical contract, three
seeds, three sample sizes (9 runs, all of them negative):

| Seed | 10,000 | 40,000 | 160,000 |
| --- | --- | --- | --- |
| 42 | -0.07600 | -0.09597 | -0.11223 |
| 7 | -0.08971 | -0.10752 | -0.11707 |
| 123 | -0.25129 | -0.17837 | -0.13032 |

Our own `heston_basket_price` shows the same sign and a comparable magnitude
(-0.038 to -0.175 across the path counts measured above). This is reported as a shared,
known property of the standard degree-2 in-sample LSM algorithm — corroborated on the industry
reference implementation, not a defect unique to either side.

## 3. Speed, matched thread count — the confound that was caught and fixed

**QuantLib's Python MC engines here run on ONE thread.** Confirmed by CPU-percentage sampling
during a call (~97%, one core) and by inspection: neither `MCEuropeanHestonEngine` nor
`MCAmericanEngine` takes a thread-count argument in the public SWIG/Python bindings. An earlier
pass of this measurement ran our Mojo arm at `workers=8` against QuantLib's single thread and
found a 3-6x apparent speed advantage — which was a thread-count confound, not an algorithmic
one, and is DISCARDED here rather than reported. The number below is `workers=1` on both sides,
the only like-for-like comparison.

Interleaved rounds (Mojo run, then QuantLib run, alternating — never one arm run to completion
before the other, so both see the same load distribution), 5 rounds, minimum wall time per cell
reported, `git rev-parse HEAD` and `ql.__version__` asserted at run time. Host load average
(1-minute) ranged from 62 to 98 across the whole run — this machine runs multiple concurrent
agent workloads and was never quiet; every figure below is an upper bound on the true time.

### European leg, workers=1

| n_paths | ours hot_ms | ours spread | QuantLib hot_ms | QuantLib spread | speed (QL/ours) |
| --- | --- | --- | --- | --- | --- |
| 10,000 | 299.3 | 1.39x | 329.7 | 2.09x | 1.10x |
| 40,000 | 1232.9 | 1.87x | 1344.7 | 1.20x | 1.09x |
| 160,000 | 4868.9 | 1.70x | 5410.1 | 1.19x | 1.11x |

### American leg, workers=1

| n_paths | ours hot_ms | ours spread | QuantLib hot_ms | QuantLib spread | speed (QL/ours) |
| --- | --- | --- | --- | --- | --- |
| 10,000 | 109.1 | 2.98x | 266.6 | 1.22x | 2.44x |
| 40,000 | 442.7 | 1.72x | 898.6 | 1.99x | 2.03x |
| 160,000 | 1918.8 | 1.66x | 3251.9 | 1.51x | 1.69x |

"spread" is max/min wall time for that arm across the 5 rounds — the honesty check on the
minimum: contention can only make a reading slower, never faster, so a spread comparable in size
to the measured speed ratio means the ratio is not resolved from noise on this machine. On the
European leg, the 1.09x-1.11x margin is smaller than either arm's own round-to-round spread
(1.19x-2.09x) — **this is a tie within measurement noise, not a win, on a machine this loaded.**
On the American leg the 1.69x-2.44x margin is larger than most of the observed spreads, which is
suggestive but, on a single 5-round sample on a machine whose load swung from 62 to 98 during the
run, is not the "outright, adversarially-robust win" this repository's publication rule requires.

## 4. Heston-native PDE opponent — a different method, not raced

`ql.FdHestonVanillaEngine` (grid 100 x 100 x 50) is a finite-difference PDE solver operating
directly on the Heston process — the closest public QuantLib approximation to "Heston American,"
and NOT Monte Carlo. Measured once (not interleaved — a single deterministic PDE solve has no
"hot" tier to speak of):

| Quantity | Value |
| --- | --- |
| American price (PDE) | 8.93093 |
| European price, same engine | 8.93076 |
| Wall time | 71.4 ms |

American ≈ European here too (difference 0.00017, consistent with the no-dividend theorem and the
PDE grid's own discretisation error) — a second, differently-implemented confirmation of the
same degenerate-corner fact section 2 discusses. Not compared to our LSM number: a PDE grid and a
Monte Carlo estimator are different tools and a speed ratio between them would not mean what a
reader would assume it means.

## What this comparison is worth, stated plainly

- A genuine, useful correctness cross-check: our closed-form Heston price and QuantLib's agree
  to displayed precision, from independently-written code.
- An honest loss on Monte Carlo accuracy-per-path, on both legs, not investigated further here
  (a candidate explanation — QuantLib's specific antithetic-variate/path-construction choices —
  is stated but not confirmed).
- A shared, known LSM finite-sample property (negative premium in the theoretically-zero-premium
  degenerate corner), corroborated on QuantLib's own reference implementation across 9
  seed/sample combinations — useful context for anyone reading a `heston_basket_price` premium
  near this corner, not a defect report.
- A speed measurement that, corrected for a real thread-count confound this build caught and
  discarded, shows a small-to-moderate margin in our favor that this repository's own
  publication bar does not consider settled on a persistently loaded shared machine.

## Files

| Path | What it is |
| --- | --- |
| `mojo/engine/quantfin/heston.mojo` | the kernel under comparison — unchanged for this comparison |
| `benchmarks/mojo_benchmarks/bench_vs_quantlib_heston.mojo` | our arm: prices the fixed contract at workers=1 (like-for-like) and workers=8 (labelled, informational), both legs, three path counts each |
| `benchmarks/mojo_benchmarks/bench_vs_quantlib_heston.py` | the QuantLib arm — run under an interpreter with QuantLib importable, e.g. `/tmp/bb/bin/python -P benchmarks/mojo_benchmarks/bench_vs_quantlib_heston.py` |
| `benchmarks/mojo_benchmarks/bench_vs_quantlib_heston_driver.py` | interleaves the two arms, reports load average and round-to-round spread, decides nothing on its own — the numbers above are transcribed from a run of it |

## Reproducing

```
cd mojo_env && pixi run mojo build -I../mojo/engine -O3 \
    ../benchmarks/mojo_benchmarks/bench_vs_quantlib_heston.mojo \
    -o /tmp/qlbench/bench_vs_quantlib_heston

/tmp/bb/bin/python -P ../benchmarks/mojo_benchmarks/bench_vs_quantlib_heston_driver.py \
    --rounds 5 --binary /tmp/qlbench/bench_vs_quantlib_heston
```

QuantLib must be installed into the SAME interpreter the driver runs under
(`/tmp/bb/bin/python -m pip install QuantLib`) — this repo's own `mojo_env` Python does not have
it, and QuantLib's public wheel installs in seconds with no build step.

## Sources

- QuantLib — <https://github.com/lballabio/QuantLib>. Version installed and measured here: 1.43,
  asserted at run time via `ql.__version__`.
- Andersen, L. (2008). Simple and Efficient Simulation of the Heston Stochastic Volatility Model.
  *Journal of Computational Finance* 11(3).
- Longstaff, F. & Schwartz, E. (2001). Valuing American Options by Simulation: A Simple
  Least-Squares Approach. *Review of Financial Studies* 14(1).
- Merton, R. (1973). Theory of Rational Option Pricing. *Bell Journal of Economics and Management
  Science* 4(1) — the never-exercise-early-on-a-non-dividend-call argument used in section 2.
- `benchmarks/STAC_A2_WORKLOAD.md` — the STAC-A2-shaped workload built alongside this comparison,
  which compares against published audited hardware results instead of an installed opponent.
