# The STAC-A2 market-risk workload on Algenta — unaudited

Updated: 2026-08-01

## Read this first

**This is not a STAC-A2 result.** An official STAC-A2 result requires an audit by the STAC
Benchmark Council. We have not had one. The STAC-A2 specification documents, the R reference
implementation and the STAC Test Harness are restricted to qualified Council members and we do
not have them.

What follows is **the market-risk workload STAC-A2 describes**, reconstructed from publicly
posted STAC Reports and from the cited academic literature, implemented independently and
measured here. Every figure on this page is **unaudited and independently implemented from the
public specification**.

STAC-A2 metric names (`GREEKS.TIME.WARM`, `PATHGEN.PVSTDERR`, `OPTIONPV.ERR`, `CORRAND.CORR`,
`EARLYEX.ERR`) appear below only to identify *which published definition* each of our checks was
modelled on. They do not assert certification, and no number here may be quoted under one of
them as though it were.

---

## What the workload is

Monte Carlo estimation of Heston-based Greeks for a path-dependent, multi-asset option with early
exercise.

| Element | This implementation | Source for the choice |
| --- | --- | --- |
| Instrument | best-of-5 call, holder may pay a fixed price at any date before expiry for the best of N assets | public STAC Report wording |
| Model | Heston: CIR variance, GBM price, correlation `rho` between the driving Brownians, one configuration per asset | public STAC Report |
| Path generation | **Andersen Quadratic Exponential**, `psi_c = 1.5`, central `gamma1 = gamma2 = 0.5`, martingale correction ON | Andersen (2008), *J. Computational Finance* 11(3); STAC names QE |
| Cross-check scheme | **full-truncation Euler**, same Philox coordinates | Lord, Koekkoek & van Dijk (2010), *Quantitative Finance* 10(2) |
| Early exercise | Longstaff-Schwartz LSMC, degree-2 basis, daily exercise dates | Longstaff & Schwartz (2001), *RFS* 14(1); STAC names LSMC |
| Cross-asset correlation | price Brownians mapped through the lower Cholesky factor of the input matrix | public STAC Report |
| Greeks | THETA, RHO, DELTA, GAMMA, CROSS-GAMMA, MODEL VEGA (KAPPA / MV_THETA / KHI / V0), CORRELATION VEGA | public STAC Report "Operations" list |
| Greeks method | finite differences on **common random numbers** | our design; see the CRN section |
| Baseline problem | 5 assets, 25,000 paths, 252 timesteps | public STAC Report |

### The discretization, named — because it is the first thing a reviewer asks

Naive Euler on the CIR variance produces **negative variance**, at which point `sqrt(V)` is not a
real number. That is the single most common Heston implementation error. This implementation
**never runs naive Euler**. It ships two schemes and every number states which one produced it:

- **Andersen QE** (default). The variance is sampled from a moment-matched quadratic `a(b+Z)^2`
  when `psi = s2/m^2 <= psi_c`, and from a moment-matched exponential-with-an-atom-at-zero above
  it. Non-negative **by construction** — a square on one branch, support `[0, inf)` on the other.
  No truncation applied and none needed.
- **Full-truncation Euler** (cross-check only). `max(V, 0)` substituted in drift, diffusion and
  the carried state.

Measured, at 100,000 paths x 252 steps x 5 single-asset configurations, fp64, 16 threads,
M4 Max arm64:

| Scheme | Negative variances produced | Zero-variance visits |
| --- | --- | --- |
| Andersen QE | **0** | 0 |
| full-truncation Euler | **381,483** | 0 |

The QE zero is a hard gate in `bench_stac_a2_workload.mojo` section 4. The full-truncation column
is the point: the raw Euler variance goes negative hundreds of thousands of times per run and the
scheme survives only by truncating at use. A naive Euler with no truncation takes `sqrt` of those
and returns nan — which is exactly what the injected-defect run below produces.

### Which QE branch actually runs, and a bound worth knowing

Building this surfaced a result that is not obvious from Andersen's paper and that we did not
find stated anywhere. On the five baseline assets, the QE **exponential** branch is never taken —
zero visits — and the reason is analytic, not a sampling accident.

Andersen switches to the exponential branch when `psi = s2/m^2` exceeds `psi_c = 1.5`. For a
variance started at its own long-run level (`v0 = theta`), `m = theta` exactly at every step, and
as `dt` grows `s2 -> theta·xi²/(2·kappa)`. So

```
psi  ->  xi² / (2·kappa·theta)  =  1 / Feller
```

`psi` is bounded above by `1/Feller` **however coarse the timestep**, and the exponential branch
is therefore *unreachable* unless `Feller < 1/psi_c = 0.667`.

Measured, 20,000 paths x 5 assets, Feller 0.80-1.20:

| Timesteps per year | Asset-steps | QE exponential-branch visits |
| --- | --- | --- |
| 1 | 100,000 | 0 |
| 2 | 200,000 | 0 |
| 4 | 400,000 | 0 |
| 12 | 1,200,000 | 0 |
| 52 | 5,200,000 | 0 |
| 126 | 12,600,000 | 0 |
| 252 | 25,200,000 | 0 |

A scheme half of which never executes is a scheme half tested, so the benchmark carries a
dedicated **branch-coverage** configuration chosen so `Feller < 0.667` — `v0 = theta = 0.04`,
`kappa = 2.0`, `xi = 0.5`, `rho = -0.7`, Feller 0.64 — and gates that the exponential branch is
genuinely taken, that it produces no negative variance, and that it still agrees with the closed
form. Measured at 100,000 paths x 252 steps, fp64, 16 threads, M4 Max arm64:

| Quantity | Value |
| --- | --- |
| Feller ratio | 0.64 |
| exponential-branch visits | **336,604** |
| zero-variance visits | 72,566 |
| negative variances | **0** |
| martingale-correction fallbacks | 0 |
| Monte Carlo price | 5.81073 |
| Heston closed form | 5.81803 |
| relative error | **0.1255%** |
| Z | **0.28** |

The zero-variance count is not an error: at Feller 0.64 the CIR variance genuinely reaches the
boundary, and the exponential branch has an atom there. `negV = 0` is the gate, and it holds
because the exponential branch's support is `[0, inf)`.

**This corrects a claim it would have been easy to make.** The branch-divergence hazard that a
counter-based generator protects against is real, but it does not arise on the STAC baseline
configuration at 252 daily steps, because only the quadratic branch ever runs there. The 55x
variance reduction measured below comes from **sharing draws**, not from surviving a branch flip.
The fixed-slot design covers the flip; this configuration does not exercise it, and the
branch-coverage row is what does.

---

## Correctness, before any timing

Every row below is a hard gate in `benchmarks/mojo_benchmarks/bench_stac_a2_workload.mojo`. The
benchmark runs all of them before it times anything, and exits non-zero if any fails.

| # | Check | Result | Gate |
| --- | --- | --- | --- |
| 1 | Fast Philox path vs frozen `counter_rng`, exact fp64 equality | 0 mismatches in 100,000 draws | must be 0 |
| 2 | LSM in-place normal equations vs frozen `regression.ols_multiple` | worst coefficient diff 2.05e-7 (degree 3) | < 1e-6 |
| 3 | **Black-Scholes degeneracy** (`xi = 0`, `rho = 0`) | see below | every Z <= 4.0 |
| 4 | **Heston closed form** (Fourier, "Little Heston Trap") | worst rel. error 1.26%, worst Z 1.64 | Z <= 4.0 |
| 4b | QE **exponential-branch coverage** at Feller 0.64 | 336,604 branch visits, 0 negative variances, Z = 0.28 | branch > 0, negV = 0, Z <= 4.0 |
| 5 | Realised cross-asset correlation (STAC's `CORRAND.CORR`) | 0.72-0.85x the 1/sqrt(n) sampling floor | <= 3x floor |
| 6 | LSM vs binomial American (STAC's `EARLYEX.ERR`) | 1.19% at 160,000 paths | < 2% |
| 7 | Worker invariance, 1 vs 2/5/8/11/14 threads | **bit-identical** price, s.e., exercise count | exact |
| 8 | Greeks convergence with path count | final successive change 0.0137 in delta_0 | < 0.10 |
| 9 | CRN pairing reduces variance | 55.5x | must be true |

### 3. Black-Scholes degeneracy — the strongest available check

At `xi = 0` and `rho = 0` with `v0 = theta = sigma^2`, the Heston variance is constant and the
price is exactly Black-Scholes. Asserted against the frozen `option_pricing.black_scholes_call`.
Reported as a **Z score** — the number of Monte Carlo standard errors — because an absolute error
of 0.01 is a pass at 1,000 paths and a hard failure at 10 million, and only the Z score knows the
difference. fp64, 16 threads, M4 Max arm64, 64 timesteps.

| Paths | MC price | Black-Scholes closed form | Abs error | Rel error | Std error | Z |
| --- | --- | --- | --- | --- | --- | --- |
| 1,000 | 9.9815 | 9.4134 | 0.56806 | 6.03% | 0.47210 | 1.20 |
| 4,000 | 9.2902 | 9.4134 | 0.12321 | 1.31% | 0.22081 | 0.56 |
| 16,000 | 9.4539 | 9.4134 | 0.04052 | 0.43% | 0.11110 | 0.36 |
| 64,000 | 9.4224 | 9.4134 | 0.00899 | 0.10% | 0.05577 | 0.16 |
| 256,000 | 9.3903 | 9.4134 | 0.02306 | 0.25% | 0.02784 | 0.83 |

The standard error shrank **16.96x** over a 256x path increase; `sqrt(256) = 16.00`. Both the Z
bound and the `1/sqrt(n)` trend are gated, because a systematic scheme error shows up as a Z that
*grows* with the path count while the standard error shrinks.

**What this check does not test.** With `xi = 0` the QE `psi` is identically 0, so only the
degenerate branch runs; with `rho = 0` the `K1`/`K2` correlation terms vanish. A mis-signed `rho`
passes this check. That is why check 4 exists.

### 4. The full model against the Heston closed form

The closed form is the branch-safe "Little Heston Trap" Fourier inversion (Albrecher, Mayer,
Schoutens & Tistaert 2007), integrated with the frozen `integrate.simpson`. This is the anchor
STAC's `OPTIONPV.ERR` uses. It tests the full model at non-zero vol-of-vol and non-zero
correlation, where the degeneracy check is blind. 100,000 paths, 252 steps, fp64, 16 threads,
M4 Max arm64.

| Asset | Feller ratio | Scheme | MC price | Closed form | Rel error | Z |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.98 | Andersen QE | 6.0855 | 6.0637 | 0.361% | 0.78 |
| 0 | 0.98 | full-trunc Euler | 6.0837 | 6.0637 | 0.331% | 0.72 |
| 1 | 0.99 | Andersen QE | 4.5080 | 4.5057 | 0.051% | 0.09 |
| 1 | 0.99 | full-trunc Euler | 4.5081 | 4.5057 | 0.053% | 0.09 |
| 2 | 0.80 | Andersen QE | 8.0142 | 8.0356 | 0.266% | 0.66 |
| 2 | 0.80 | full-trunc Euler | 8.0159 | 8.0356 | 0.245% | 0.61 |
| 3 | 1.20 | Andersen QE | 14.0250 | 13.9931 | 0.228% | 0.65 |
| 3 | 1.20 | full-trunc Euler | 14.0218 | 13.9931 | 0.205% | 0.58 |
| 4 | 1.01 | Andersen QE | 2.3033 | 2.2761 | 1.194% | 1.56 |
| 4 | 1.01 | full-trunc Euler | 2.3048 | 2.2761 | 1.262% | 1.64 |

Every discrepancy is within 1.64 Monte Carlo standard errors of the closed form. The sanity
reference for the `EARLYEX.ERR` scale is the 2013 STAC Report for SUT NVDA131118, which records
`EARLYEX.ERR` 0.007 on an **audited** run; ours is 0.0119, unaudited and on a different
configuration, so it is a scale check and not a comparison.

---

## Common random numbers — the headline result

Finite-difference Greeks need the base and bumped runs to share randomness, or the sensitivity is
buried in Monte Carlo noise.

Algenta's `determinism/counter_rng` is Philox4x64-10 with every draw addressed by
`(replication, step, asset, stream, slot)` at a fixed slot budget. Two properties follow, and it
is worth separating them because only the first is what produces the number below:

1. **Draws are shared exactly** between the base and bumped runs. This is what buys the variance
   reduction measured here.
2. **A variable-consumption branch cannot desynchronise the two runs.** Andersen QE consumes a
   normal on the quadratic branch and a uniform on the exponential branch, and which one it takes
   depends on the state, which depends on the bump; a stateful stream generator would shift every
   subsequent draw at the first divergence. The fixed slot budget means the exponential branch
   simply leaves a slot unread. As measured above, this hazard does **not** arise on the STAC
   baseline configuration, where only the quadratic branch runs — so it is insurance here, not
   the mechanism.

Measured: asset-0 Delta, 24 replications x 1,000 paths x 252 steps, 5 assets, fp64, 16 threads,
M4 Max arm64, target interval **+/-0.010 at 95%**.

| Arm | Mean delta_0 | Variance | Std dev | Replications needed | Ratio |
| --- | --- | --- | --- | --- | --- |
| Paired (CRN) | 0.16051 | 2.664e-3 | 0.05162 | **103** | 1.0x |
| Unpaired | 0.15126 | 1.480e-1 | 0.38467 | **5,685** | **55.2x** |

Variance ratio 55.5x, replication ratio 55.2x. A re-run at identical coordinates reproduced the
base price exactly on 24 of 24 replications, which is the check that the pairing is real rather
than asserted.

Read the replication column as the cost. The unpaired design needs **5,685** replications to pin
asset-0 Delta to +/-0.010 where the paired design needs **103**. A central-difference replication
is two prices, and a 1,000-path price costs 68.6 ms at the measured baseline rate below, so the
same interval is **14 seconds of work paired against 13 minutes unpaired** — 206 prices against
11,370, for an answer of identical precision.

The measurement design is copied from `strategy/crn.mojo`'s `crn_pairing_audit`, which runs the
same comparison for the policy domain. That function could not be called here — its tape is
policy-shaped, not Heston-shaped — so the discipline is reproduced rather than the code reused.

---

## Timing

### Batching and dispatch count

**Total runtime dispatches for the entire workload: 0.**

Everything runs in-process. Verify with:

```
grep -nE '(dispatch_runtime_library|library_execute|json_parse)[[:space:]]*\(' \
    benchmarks/mojo_benchmarks/bench_stac_a2_workload.mojo \
    benchmarks/mojo_benchmarks/bench_stac_a2_baseline.mojo \
    mojo/engine/quantfin/heston.mojo
```

which returns nothing. The `\(` matters — a bare token grep also matches the paragraphs in those
files that *claim* zero dispatch, which is the sort of self-defeating check that gets pasted into
a report and believed.

The natural batch here is the whole Greeks set: 94 prices x 5 assets x 25,000 paths x 252
timesteps = **2,961 M asset-steps in one call**, with no argument boundary crossed at any point
inside it. The runtime's dispatched path costs ~168 ns/cell against 4.8 ns/cell batched; at this
size a dispatched design would measure the boundary and not the model.

No SDK arm was built. `option_pricing`, `determinism.counter_rng`, `regression` and
`matrix_decomp` are not on the SDK dispatch surface (`runtime_capability_manifest.json` exposes 69
modules / 445 functions and none of those four are among them), so a Heston SDK arm would need a
new dispatch entry. That is reported rather than substituted with a weaker proxy.

### STAC baseline problem size — 5 assets, 25,000 paths, 252 timesteps

STAC's own protocol: five executions, one cold and four warm. **STAC's published WARM metric is
the *mean* of the four warm runs, not the fastest** — STAC Report NVDA131118 §9 states it plainly:
"Table 3 contains three results for each operation: the mean of all five runs, the result for the
first (cold) run, and the mean of results for the subsequent four runs." An earlier revision of
this page reported our *fastest* warm run against STAC's *mean* warm run, which flattered us by
1.15x. That is corrected below: the WARM row is now a mean of four, matching STAC's definition.

**K = 1** — one cold reading, one process. Five Greeks sets at this size is already a long run and
cannot be repeated across K processes in reasonable time; the K-process tier statistics are at a
reduced size in the next section and are labelled as such.

94 prices per Greeks set. 2,961 M asset-steps per Greeks set. 0 dispatches.

Two independent executions of the identical binary are reported, because the difference between
them is a result in its own right. Both returned a **bit-identical** price of 20.0492 +/- 0.0880.

Quieter execution — load average **20.51 before, 37.89 after**, peaking 112 mid-run (16 physical
cores):

| Tier | Seconds | Paths/sec (set) | Asset-steps/sec | dtype | Threads | Device |
| --- | --- | --- | --- | --- | --- | --- |
| COLD (1st in process) | 95.241 | 24,674 | 31.09 M | fp64 | 16 | M4 Max arm64 |
| MEAN (all five) | 98.531 | 23,850 | 30.05 M | fp64 | 16 | M4 Max arm64 |
| WARM (mean of 4, STAC definition) | 99.353 | 23,652 | 29.80 M | fp64 | 16 | M4 Max arm64 |
| WARM (fastest warm, NOT STAC's definition) | 90.507 | 25,965 | 32.72 M | fp64 | 16 | M4 Max arm64 |

Warm dispersion max/min 1.26. A single price at this size is **906.3 ms**.

Busier execution — load average **36.84 before, 53.72 after**:

| Tier | Seconds | Paths/sec (set) | Asset-steps/sec | dtype | Threads | Device |
| --- | --- | --- | --- | --- | --- | --- |
| COLD (1st in process) | 146.828 | 16,005 | 20.17 M | fp64 | 16 | M4 Max arm64 |
| MEAN (all five) | 150.733 | 15,591 | 19.64 M | fp64 | 16 | M4 Max arm64 |
| WARM (mean of 4, STAC definition) | 151.709 | 15,491 | 19.52 M | fp64 | 16 | M4 Max arm64 |
| WARM (fastest warm, NOT STAC's definition) | 131.509 | 17,870 | 22.52 M | fp64 | 16 | M4 Max arm64 |

Warm dispersion max/min 1.23. A single price at this size is 1,715.7 ms.

**Same binary, same work, same answer to the last bit — 1.54x apart on cold, 1.53x on mean-warm,
1.89x on a single price.** Neither machine state was quiet in the sense the word usually implies.
Every figure here is an upper bound on the time, and no figure on this page should be read to
three significant figures.

The answer the timing is attached to, so the number is not free-floating:

| Quantity | Value |
| --- | --- |
| best-of-5 Bermudan price | 20.0492 +/- 0.0880 (1 s.e., empirical) |
| European value, same paths | 20.0090 |
| early-exercise premium | 0.0402, on 52,066 exercise decisions |
| QE negative variances | 0 |
| martingale-correction fallbacks | 0 |
| delta_0 / gamma_0 | 0.16950 / -0.000442 |

### Reduced size, K = 5 processes — 5 assets, 2,000 paths, 252 timesteps

`benchmarks/cold_start_harness.py -K 5 --mode build`. A cold reading can only be taken once per
process, so **K cold readings need K launches, and K here is 5**. Runs are strictly sequential;
K in parallel would measure the contention between them.

Load: **24 at start, 61 at end** (1-min, 16 cores), peaking at **122** mid-run. Total wall
2,138.7 s. All 5 processes exited 0: **BENCH_GATE 5 PASS / 0 FAIL**.

Per-process wall time, same binary, same work, and this is the load discipline made concrete:

| Process | Wall (s) | 1-min load at that moment | Ratio vs the quietest |
| --- | --- | --- | --- |
| 1 | 244.9 | 50 | 1.00x |
| 2 | 463.4 | 112 | 1.89x |
| 3 | 443.1 | 122 | 1.81x |
| 4 | 521.5 | 102 | 2.13x |
| 5 | 464.6 | 61 | 1.90x |

Identical work took **2.1x** longer at load 102 than at load 50. Any figure quoted from this
machine without its load average is not a figure.

Tier statistics across the 5 processes, ms per full Greeks set (94 prices, 2,000 paths, 252
steps), fp64, 16 threads, M4 Max arm64:

| Tier | Min (floor) | Median | Max | Spread |
| --- | --- | --- | --- | --- |
| cold | 7,220.5 | 13,593.2 | 16,843.8 | 2.33x |
| warm | 6,446.7 | 9,834.0 | 16,288.2 | 2.53x |
| hot | 5,929.7 | 14,058.0 | 14,759.2 | 2.49x |

**cold/hot: floor 1.22x, median 0.97x.** The floor is the statistic to quote — contention can
only make a reading slower than the work takes, never faster. The median 0.97x is hot coming out
*slower* than cold, which is not a property of the code; it is the machine going from load 24 to
load 122 during the run. Spread is under the harness's 3.0x noise threshold on every row, so the
cold tier is stable enough for a median to mean something, but only just.

At the floor reading, 2,000 paths x 94 prices in 5,929.7 ms is **31,705 paths/sec** and
**39.9 M asset-steps/sec** — slightly better than the baseline-size figure, as expected, since
the 2,000-path working set fits in cache where the 25,000-path one does not.

**The INVALID path fires on real runs, not only on injected defects.** A final single-process
verification of the shipped binary at load 35 -> 55 returned cold/warm/hot
13,561.3 / 11,895.6 / 12,578.2 ms — hot slower than warm — and printed:

```
   INVALID — hot (12578.2 ms) is SLOWER than warm (11895.6 ms). No cold/hot ratio is
   printed, because on a contended machine the ratio would be a number about the machine
   and a reader would quote it as a number about the code.

   1 ADVISORY tier breach(es). NOT gate failures.
...
BENCH_GATE stac_a2_workload PASS            (exit code 0)
```

All ten sections passed their correctness gates in that same run. That is the split working as
intended: no ratio was emitted for a reader to quote, and no correct build was branded a failure
because a sibling process was using the machine.

---

## We lose, and by a lot

Two audited STAC-A2 results publish absolute seconds at this problem size. Ours is unaudited and
is far slower than both, including one taken on 2013 GPU hardware. Stating it plainly:

Ours is the quieter execution (load 20.5 -> 37.9); warm is mean-of-four on both sides, which is
STAC's definition. Every row states the opposing hardware.

| Comparison | Ours (s) | Theirs (s) | Ratio (ours/theirs) |
| --- | --- | --- | --- |
| COLD vs SUT NVDA131118 SUT-scale-1 (1x K20Xm + 1 CPU thread, audited) | 95.241 | 1.528 | **62.3x slower** |
| COLD vs SUT NVDA131118 full SUT (2x K20Xm + 2x 8-core Xeon E5-2660 @ 2.20 GHz, audited) | 95.241 | 1.258 | **75.7x slower** |
| WARM vs SUT NVDA131118 SUT-scale-1 (1x K20Xm + 1 CPU thread, audited) | 99.353 | 1.276 | **77.9x slower** |
| MEAN-of-5 vs SUT NVDA131118 full SUT (audited) | 98.531 | 0.770 | **128.0x slower** |
| WARM vs SUT NVDA131118 full SUT (audited) | 99.353 | 0.648 | **153.3x slower** |
| COLD vs SUT INTC260430 (2x Xeon 6980P, 256 cores, audited) | 95.241 | 0.033 | **2,886.1x slower** |
| WARM vs SUT INTC260430 | 99.353 | **not public** | **no ratio computed** |

Two things this table is careful about. First, the SUT-scale-1 rows are the *smallest* audited
configuration NVIDIA published (Table 6 of the report: one GPU driven by one CPU thread) and are
the closest thing to a like-for-like small-machine anchor; we are still 62-78x slower than a
single 2013 GPU on one thread. Second, **the core count does not explain the Intel gap**: 256
P-cores against our 16 is a 16.0x ratio, so of the 2,886x, a factor of **180x is per-core
efficiency that core count does not account for.**

An earlier revision of this table read 202.9x / 116.7x / 4,449.3x. Those figures compared our
*fastest* warm run against STAC's *mean* warm run, and were taken on a busier machine. Both
errors have been corrected here; the warm ratio got **worse** (202.9x -> 153.3x is an improvement
only because the machine was quieter — on identical load the definition fix alone moves 202.9x to
234.1x).

### The published figures, with their caveats

| SUT | Hardware | COLD | WARM | Source, and what it does not say |
| --- | --- | --- | --- | --- |
| NVDA131118 | IBM System X iDataPlex dx360 M4, 2x NVIDIA Tesla K20Xm, **2x 8-core Intel Xeon E5-2660 (Sandy Bridge) @ 2.20 GHz** — the host CPU **is** stated, on the report cover. | 1.258 s | 0.648 s (mean of 4) | STAC Report, test date 2013-11-18, draft v1.01 2013-12-03, hosted at nvidia.com. STAC-A2 Pack for CUDA 5.5 (Rev A). Spec: beta 2 on the cover, Rev P in the references. MEAN-of-5 0.770 s. Problem size stated as 5 assets / 25K paths / 252 timesteps — identical to ours. SUT-scale-1 (1 GPU, 1 CPU thread): cold 1.528 s, warm 1.276 s. |
| INTC260430 | HPE ProLiant Compute XD230 1U, 2x Intel Xeon 6980P (128 P-cores/socket, 256 total), 24x 64 GB Micron DDR5 MRDIMM @ 8800 MT/s (1.5 TB) | 0.033 s | **not public** | STAC, audited 2026-05-05. Intel STAC-A2 Pack for oneAPI (Rev R). The warm absolute is not in any public summary; only a **1.62x warm ratio**, and that ratio's reference SUT is described only as "a prior-generation Xeon Platinum 8592+ platform" — **the reference SUT ID is not disclosed publicly**, so the ratio itself is against a machine that is named but not fully specified. |
| NVDA200909 | NVIDIA DGX A100, 8x A100 SXM 40 GiB, CUDA 11 | **not published** | **not published** | Posted 2020-10-17. The public page gives **ratios only** — 2.15x SUT INTC181012, 1.78x SUT INTC190903 — and does not state those SUTs' configurations. Every one of those ratios is against an unstated machine as published, so no Ratio row is computed against it here. |

**Cross-revision warning.** The 2013 K20Xm report is spec revision b2; the 2026 Xeon report is
Pack Rev R. They are not comparable to each other, let alone jointly to us. The K20Xm report's
`MAX_PATHS` is 8,500,000 and the Xeon report's is 1,000,000 — that is a spec change, not a
regression, and no trend line should be drawn across them.

### Why we lose

The reasons are structural and are not a mystery:

1. **Scalar fp64 throughout.** No SIMD across the asset or the path axis. The Box-Muller
   `log`/`cos` pair plus the QE `sqrt` chain is roughly ten transcendentals per asset-step, all
   scalar.
2. **CPU only**, against two GPU submissions and a 256-core dual-socket Xeon. 16 physical cores
   against 256 hardware threads or 2-8 datacentre GPUs.
3. **94 full path regenerations per Greeks set**, and 30 of them are avoidable — see the
   optimization we did not take, below.
4. **Vendor Packs.** The audited submissions run Intel oneAPI Rev R and CUDA 5.5 with
   cuRAND/cuBLAS/CUB, tuned against the real spec and the real harness. We have neither.
5. **The machine was loaded.** Load 37-54 on 16 cores during the baseline run, and 24-122 during
   the K=5 harness run, with sibling agents' workloads resident throughout. Our figures are upper
   bounds on the time and therefore lower bounds on the throughput; the audited figures are from
   dedicated systems under audit conditions. The K=5 table above shows identical work taking 2.1x
   longer at load 102 than at load 50, so the gap on a quiet machine would be smaller than the
   ratios quoted here — but not by two orders of magnitude, and the conclusion does not change.

### What we optimized, and by how much

All measured at the baseline size, single price, 5 assets x 25,000 paths x 252 steps, fp64,
M4 Max arm64, under load 45-77.

| Build / change | 1 thread (s) | 8 threads (s) | Ratio vs previous |
| --- | --- | --- | --- |
| `mojo run` (JIT, no -O3) | 35.393 | 8.205 | baseline |
| `mojo build -O3`, before optimization | 14.304 | 2.914 | 2.47x / 2.82x |
| `mojo build -O3`, after the three below | **10.520** | **2.040** | 1.36x / 1.43x |

The three, all in `mojo/engine/quantfin/heston.mojo`:

1. **One Philox block instead of two.** `counter_rng.rng_normal` calls `philox_word` twice, at
   `draw_index` and `draw_index+1`. Those two indices land in the *same* Philox counter block
   (`c2 = draw_index >> 2`, word selected by `draw_index & 3`), so the second call re-runs all ten
   rounds to extract a word the first already computed and discarded. `counter_rng.mojo` is frozen
   and was not edited; the block is computed once in `heston.mojo` and both words read out of it.
   That duplicates a frozen kernel's arithmetic, so it is paid for with a **hard bit-equality
   gate** — `heston_rng_bit_identity` compares both outputs against the frozen kernel at exact
   fp64 equality across 100,000 draws and the benchmark fails on any mismatch.
2. **`exp` hoisted out of the asset loop.** `max_a exp(x_a) = exp(max_a x_a)` exactly, since `exp`
   is monotonic. Removes four fifths of 31.5M `exp` calls per price at 5 assets.
3. **Discount table.** The LSM backward pass discounted each cash flow with
   `for _ in range(k): d *= disc` — O(n_steps) inside an O(n_paths x n_steps) double loop, 794M
   multiplications per price, for a table of 253 entries.

### The optimization we did NOT take, quantified

A spot bump is the one bump that does not require re-simulation. The Heston log-price SDE's drift
and diffusion do not depend on `S`, so under identical draws
`X_t(S0(1+h)) = X_t(S0) + log(1+h)` **exactly**. The 10 single-spot bumps and the 20 cross-gamma
bumps — **30 of the 94 prices** — could be derived from the base path set rather than re-simulated,
at the cost of storing all `N` asset paths instead of the running best-of (a 5x memory increase,
250 MB at baseline). That is a ~32% saving on the Greeks set and it is **not implemented here**,
so the 131.5 s WARM figure above is conservative rather than tuned.

---

## Reproducing

```
# correctness gates + reduced-size cold/warm/hot tiers, K = 5 processes.
# The harness compiles once with `pixi run mojo build -I../mojo/engine` (no explicit -O3;
# `mojo build` is a release build) and runs the binary K times, so cold excludes JIT.
python3 benchmarks/cold_start_harness.py \
    benchmarks/mojo_benchmarks/bench_stac_a2_workload.mojo -K 5 --mode build

# the STAC baseline problem size, STAC's 1-cold-4-warm protocol, K = 1
cd mojo_env && pixi run mojo build -I../mojo/engine -O3 -o /tmp/stacbase \
    ../benchmarks/mojo_benchmarks/bench_stac_a2_baseline.mojo && /tmp/stacbase
```

Capture `uptime` immediately before and after every run and quote it beside any figure taken
from it. A Mojo process cannot read the load average, and a figure from a busy machine is not a
figure.

### The gate demonstrated failing

The gates were verified by injecting the canonical Heston defect — **naive Euler on the CIR
variance, with the scheme still labelled Andersen-QE** — into a copy of `heston.mojo` and building
the unmodified benchmark against it:

```
   asset  Feller  scheme        MC price  closed form  rel err   Z     negV    zeroV   QE-exp
   0        0.98  Andersen-QE       +inf       6.0637     +inf%  0.00   38509   29061   29061
   GATE FAIL: QE produced 38509 negative variances. The scheme cannot do that; the code did.
   1        0.99  Andersen-QE       +inf       4.5057     +inf%  0.00   54840   41414   41414
   GATE FAIL: QE produced 54840 negative variances. The scheme cannot do that; the code did.
   2        0.80  Andersen-QE       +inf       8.0356     +inf%  0.00   64781   49642   49642
   3        1.20  Andersen-QE       +inf      13.9931     +inf%  0.00   31532   23508   23508
   4        1.01  Andersen-QE       +inf       2.2761     +inf%  0.00   43630   32724   43630
   ...
   GATE FAIL: the exponential branch produced a negative variance.
   GATE FAIL (6)

   1 ADVISORY tier breach(es). NOT gate failures.

BENCH_GATE stac_a2_workload FAIL 6          (exit code 1)
```

Six hard failures: the five per-asset QE non-negativity gates plus the branch-coverage gate. The
defect was then removed and the clean build restored to **`BENCH_GATE stac_a2_workload PASS`**,
confirmed independently by all 5 harness processes above.

Three things this demonstration establishes beyond "a gate fires":

1. **Section 3 still PASSED under the defect.** The Black-Scholes degeneracy anchor runs at
   `xi = 0`, which routes around the injected branch entirely. One correctness anchor is not
   enough, and that is exactly why section 4 exists.
2. **The advisory split works.** The same run reported 1 wall-clock advisory breach and did *not*
   count it toward the 6. A contended timing cannot manufacture a correctness verdict, and a
   correctness verdict cannot be hidden by a quiet machine.
3. **The `+inf` prints as `+inf`.** An earlier version of the formatter saturated non-finite
   values to `922337203685477.5807`, which a reader would parse as a number. That was found by
   this demonstration and fixed.

---

## Files

| Path | What it is |
| --- | --- |
| `mojo/engine/quantfin/heston.mojo` | new additive module: Heston QE + full truncation, multi-asset Cholesky correlation, Longstaff-Schwartz early exercise, CRN-paired Greeks, Fourier closed form, all the correctness anchors |
| `mojo/engine/quantfin/__init__.mojo` | package docstring, including the unaudited disclaimer |
| `benchmarks/mojo_benchmarks/bench_stac_a2_workload.mojo` | 10 sections: sections 1-9 are HARD correctness gates and run before anything is timed; section 10 is the reduced-size cold/warm/hot tier, whose two checks are advisory |
| `benchmarks/mojo_benchmarks/bench_stac_a2_baseline.mojo` | the STAC baseline problem size under STAC's 1-cold-4-warm protocol |
| `benchmarks/QUANTLIB_HESTON_COMPARISON.md` | a separate, narrower comparison against QuantLib 1.43 — a real, installed opponent, unlike the audited-hardware comparison below. No outright win survives scrutiny there either; read it for the honest reasons. |

Nothing existing was edited. `option_pricing.mojo`, `matrix_decomp.mojo`, `regression.mojo`,
`integrate.mojo` and `determinism/counter_rng.mojo` are composed, not modified.
`correlation.mojo`'s `sample_correlated_normal` was deliberately **not** used: it draws from
`std.random.randn_float64`, a global generator with no addressable counter, which would make
common random numbers impossible and the Greeks unreproducible. `engines/monte_carlo.mojo` was
deliberately not used either: it imports `std.python`, which would drag Python interop into the
measured region.

---

## Sources

- STAC Report: STAC-A2 on NVIDIA CUDA 5.5 / 2x Tesla K20Xm, (c) 2013 STAC —
  <https://www.nvidia.com/content/tesla/pdf/STAC-A2-NVIDIA-CUDA-on-K20Xm.pdf>. The richest public
  source: workload description, Operations list, and all metric and quality definitions.
- STAC: SUT INTC260430, HPE ProLiant XD230 with 2x Xeon 6980P, audited 2026-05-05 —
  <https://docs.stacresearch.com/INTC260430> (403 to automated fetch); summarised by StorageReview.
- STAC: SUT NVDA200909, DGX A100, posted 2020-10-17 —
  <https://docs.stacresearch.com/news/NVDA200909>. Ratios only.
- STAC-A2 Working Group — <https://docs.stacresearch.com/a2>. Documents the membership gating that
  is the reason this page says "unaudited" rather than reporting a certified result.
- Andersen, L. (2008). Simple and Efficient Simulation of the Heston Stochastic Volatility Model.
  *Journal of Computational Finance* 11(3).
- Lord, R., Koekkoek, R. & van Dijk, D. (2010). A comparison of biased simulation schemes for
  stochastic volatility models. *Quantitative Finance* 10(2).
- Longstaff, F. & Schwartz, E. (2001). Valuing American Options by Simulation: A Simple
  Least-Squares Approach. *Review of Financial Studies* 14(1).
- Albrecher, H., Mayer, P., Schoutens, W. & Tistaert, J. (2007). The little Heston trap.
  *Wilmott*.
- Brown, Jamieson et al. Fast and energy-efficient derivatives risk analysis: Streaming option
  Greeks on Xilinx and Intel FPGAs. arXiv:2212.13977 — independent restatement of the QE +
  Longstaff-Schwartz stack and the loop order.
