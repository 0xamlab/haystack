---
icon: signal-stream
description: Radix-2 FFT and Haar wavelet transforms, two independently-implemented frequency-domain feature modules, window/peak/zero-crossing signal utilities, whole-column statistical data transforms, and the frozen classical-forecasting baselines forecasting.point calls underneath.
---

# Signal transforms and processing kernels

Six modules grouped under one name that turn out to span three unrelated problem domains, and two
of the six are not what their name suggests. `fft` and `wavelet` are genuine frequency- and
scale-domain transforms — a radix-2 Cooley-Tukey FFT and a Haar discrete wavelet transform.
`spectral` and `signal_processing` both compute frequency-domain descriptive statistics (spectral
centroid, flatness, energy) but are two separately-written modules that happen to share three
function names with different signatures and different edge-case behavior, not one module split in
two. `transform`, despite the name, is not a signal transform at all — there is no Laplace or
Z-transform anywhere in this corpus; it is a whole-column statistical preprocessing library
(Box-Cox, standardize, robust/min-max scaling, quantile and rank transforms) in the mold of
`sklearn.preprocessing`, and two of its scaling functions turn out to be bit-identical to functions
already documented in [Classical ML algorithms](ml-classical-algorithms.md). And `series`, which the
name suggests might be low-level array plumbing, is in fact the frozen implementation of the
classical baseline forecasters — naive, drift, seasonal-naive, SMA, single exponential smoothing —
that `forecasting.point`, `forecasting.fitted`, `forecasting.select` and `forecasting.contract`
import and call unchanged, verified directly against those modules' own `from series import ...`
lines below.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

x = [1.0, 0.0, -1.0, 0.0]        # one full cycle sampled at 4 points

X = runtime.execute("fft", "fft", [x])["result"]              # 4 Complex bins (re, im)
mag = runtime.execute("fft", "fft_magnitude", [X])["result"]
mag
# [0.0, 2.0, 0.0, 2.0] -- all the signal's energy sits in bin 1 and its mirror, bin 3

ps = runtime.execute("fft", "power_spectrum", [x])["result"]
ps
# [0.0, 1.0, 0.0, 1.0] -- |X_k|^2 / N, the same shape without a separate magnitude step
```

## The modules

| Module | What it does |
| --- | --- |
| `fft` | Radix-2 Cooley-Tukey FFT/IFFT over a custom `Complex` struct, magnitude, phase, power spectrum, and the power-of-2 sizing helpers (`next_power_of_2`, `zero_pad`) meant to run before it. |
| `spectral` | Frequency-domain analysis with its own internal DFT: power/cross spectral density, coherence, spectral centroid/bandwidth/rolloff/flatness/entropy, band energy, and peak frequency — all take an explicit, caller-supplied frequency axis. |
| `wavelet` | Haar discrete wavelet transform only (forward/inverse, single- and multi-level), hard/soft thresholding, denoising, and detail/approximation-energy extraction. |
| `transform` | Whole-column statistical data transforms — log, log1p, Box-Cox, Z-score standardize, min-max scale, robust (median/IQR) scale, quantile rank, power, clamp, rank, abs, reciprocal — not a signal or integral transform. |
| `signal_processing` | Window functions (Hamming/Hann/Blackman), windowing, peak detection, zero-crossing counting, and its own smaller set of spectral features (energy, centroid, flatness) keyed off a sample rate rather than an explicit frequency list. |
| `series` | Classical baseline forecasters — SMA, OLS linear extrapolation, weighted moving average, single exponential smoothing, naive, seasonal-naive, drift — plus forecast-accuracy (MAE/MAPE/RMSE), trend strength, and autocorrelation-based seasonality detection. |

## `fft`: correct on a power of 2, silently wrong off it

| Function | What it does |
| --- | --- |
| `fft(x)` | Cooley-Tukey radix-2 decimation-in-time FFT. Recursively splits even/odd indices; each level assumes the length halves evenly. |
| `ifft(X)` | Same recursion with the twiddle-angle sign flipped, then divided by `N`. |
| `fft_magnitude(X)` | `sqrt(re^2 + im^2)` per bin. |
| `fft_phase(X)` | `atan2(im, re)` per bin, via a minimax polynomial `atan` (no `std.math.atan2` call). |
| `power_spectrum(x)` | `fft(x)` then `\|X_k\|^2 / N` in one call. |
| `next_power_of_2(n)` | Smallest power of 2 `>= n`. |
| `zero_pad(x, target_len)` | Appends zeros up to `target_len`; does not truncate if `x` is already longer. |

Both `fft(0-length)` and `power_spectrum(0-length)` are explicitly guarded — the source's own
comment explains why: an empty list would split into two empty halves forever, "a stack-overflow
abort" rather than a clean answer, so length 0 returns an empty list instead of recursing.

**There is no guard for a non-power-of-2, non-zero length**, and the recursion does not fail loudly
when it hits one — it silently drops input. Feeding the 5-element fixture the auto-generated test
uses (`[0.5, 0.6, 0.7, 0.4, 0.3]`) straight into `fft` gives
`[2.5, 0.1618-0.1902i, 0.5, 0.0382+0.1902i, 0]` — bin 0 (the plain sum) happens to be correct, but
every other bin is wrong, and the top bin isn't merely inaccurate, it is exactly `0`, because the
`n=3` sub-call only has room to combine one pair from a 2-element even half and a 1-element odd
half, and the second even-half element is never read. Re-running the identical recursion
independently in Python and cross-checking `numpy.fft.fft` on the same 5-point input confirms the
divergence (`numpy` gives `[2.5, -0.112-0.462i, 0.112+0.109i, 0.112-0.109i, -0.112+0.462i]`). The
documented fix is the two helper functions sitting right next to `fft` in the public API:

```python
n = runtime.execute("fft", "next_power_of_2", [5])["result"]      # 8
padded = runtime.execute("fft", "zero_pad", [x5, n])["result"]    # x5 + three zeros

X = runtime.execute("fft", "fft", [padded])["result"]
mag = runtime.execute("fft", "fft_magnitude", [X])["result"]
# [2.5, 1.4479357845415969, 0.22360679774997896, 0.05900816760338921,
#  0.5, 0.05900816760338921, 0.22360679774997896, 1.4479357845415969]
# -- matches numpy.fft.fft(padded) to full float precision
```

`fft` and `ifft` are exact inverses on a power-of-2 input, up to floating-point rounding —
`ifft(fft([1.0, 0.0, -1.0, 0.0]))` returns `[1.0, 0.0, -1.0, 0.0]` (as complex numbers with
near-zero imaginary parts), verified independently in Python against the same recursion.

## `spectral` and `signal_processing`: three shared names, two different modules

Both modules define a function called `spectral_centroid` and one called `spectral_flatness`
(`signal_processing` additionally has `spectral_energy`; `spectral` additionally has
`power_spectral_density`, `cross_spectral_density`, `coherence`, `spectral_bandwidth`,
`spectral_rolloff`, `spectral_entropy`, `band_energy`, and `peak_frequency`). These are not two
call-paths into shared code — reading both `.mojo` files directly shows two independent
implementations with different signatures:

| Function | `signal_processing` signature | `spectral` signature |
| --- | --- | --- |
| `spectral_centroid` | `(magnitudes, sample_rate)` — derives its own bin frequencies as `k * sample_rate / (2N)` | `(magnitudes, frequencies)` — trusts whatever frequency axis the caller hands it |
| `spectral_flatness` | `(magnitudes)` — floors any magnitude below `1e-20` up to `1e-20` rather than refusing | `(magnitudes)` — returns exactly `0.0` the instant **any single** magnitude is `<= 1e-30` |

Calling the wrong module's version compiles and returns a plausible float either way — nothing
checks that a `sample_rate`-shaped call landed in `spectral` or a `frequencies`-shaped call landed
in `signal_processing` — it is simply the wrong number for the arguments given, silently.

`signal_processing`'s spectral trio, worked on the 4-bin magnitude spectrum from the FFT example
above (`[0.0, 2.0, 0.0, 2.0]`, sample rate 8.0 Hz):

```python
runtime.execute("signal_processing", "spectral_energy", [mag])["result"]
# 8.0 -- sum of squared magnitudes

runtime.execute("signal_processing", "spectral_centroid", [mag, 8.0])["result"]
# 2.0 -- bins sit at k * 8.0 / (2*4) = k Hz; weighted mean over [0,1,0,1]*[0,1,2,3] is 2.0

runtime.execute("signal_processing", "spectral_flatness", [mag])["result"]
# 1.4142135623730958e-10 -- the two exact-zero bins are floored to 1e-20, not refused,
# so the result is a tiny nonzero number rather than a hard 0.0
```

`spectral`'s own centroid/bandwidth/rolloff/band-energy/peak-frequency family, over 3 bins with an
explicit frequency axis `[0.0, 1.0, 2.0]` Hz and magnitudes `[0.0, 2.0, 0.0]`:

```python
c = runtime.execute("spectral", "spectral_centroid", [mags3, freqs3])["result"]
c                                                              # 1.0
runtime.execute("spectral", "spectral_bandwidth", [mags3, freqs3, c])["result"]   # 0.0 -- all energy at exactly the centroid
runtime.execute("spectral", "spectral_rolloff", [mags3, freqs3, 0.5])["result"]   # 1.0
runtime.execute("spectral", "band_energy", [mags3, freqs3, 0.5, 1.5])["result"]   # 4.0
runtime.execute("spectral", "peak_frequency", [mags3, freqs3])["result"]          # 1.0
```

And `spectral`'s PSD/CSD/coherence trio, on the same 4-point `x = [1, 0, -1, 0]` against a
90-degree-shifted `y = [0, 1, 0, -1]` at `fs = 4.0`:

```python
runtime.execute("spectral", "power_spectral_density", [x, 4.0])["result"]
# [0.0, 0.25, ~0.0] -- |DFT|^2 / (N*fs), N/2+1 = 3 bins

runtime.execute("spectral", "cross_spectral_density", [x, y, 4.0])["result"]
# [0.0, 0.25, ~0.0]

runtime.execute("spectral", "coherence", [x, y, 4.0])["result"]
# [0.0, 1.0, 0.0] -- perfectly coherent at the one frequency that carries any power
```

`spectral`'s internal DFT is a direct O(N^2) sum, not a call into `fft` — the two modules do not
share code even where they could.

## `wavelet`: Haar only, despite the plural in its own header

The module docstring's header line reads "Wavelet transforms," but the body implements exactly one
wavelet family — Haar — with no Daubechies, Morlet, or any other basis anywhere in the file or the
runtime contract. Every function name in the public API says `haar_*` except the generic-sounding
`threshold_hard` / `threshold_soft` / `denoise_haar` / `energy_ratio` / `detail_coefficients` /
`approx_coefficients`, which are all Haar-coefficient-shaped operations, not wavelet-family-agnostic
ones.

| Function | What it does |
| --- | --- |
| `haar_forward(data)` | 1-level Haar DWT: `[averages..., details...]`, each `(x[2k] +/- x[2k+1]) / sqrt(2)`. |
| `haar_inverse(coeffs)` | Exact inverse of `haar_forward`. |
| `haar_multilevel(data, levels)` | Recursively re-transforms the approximation half; output layout is `[approx_L, detail_L, detail_{L-1}, ..., detail_1]`. |
| `haar_multilevel_inverse(coeffs, levels)` | Exact inverse of `haar_multilevel`. |
| `threshold_hard(coeffs, threshold)` | Zero out any coefficient with `\|c\| < threshold`. |
| `threshold_soft(coeffs, threshold)` | `sign(c) * max(\|c\| - threshold, 0)`. |
| `denoise_haar(data, threshold, levels=1)` | `haar_multilevel` -> `threshold_soft` -> `haar_multilevel_inverse`, composed. |
| `energy_ratio(coeffs)` | Detail-energy / total-energy, assuming `coeffs` is a **1-level** `[approx, detail]` split. |
| `detail_coefficients(coeffs)` | Second half of a 1-level split. |
| `approx_coefficients(coeffs)` | First half of a 1-level split. |

Round-tripping `[1.0, 2.0, 3.0, 4.0]` through `haar_forward` then `haar_inverse` recovers the input
to within floating-point rounding (verified independently in Python: `haar_forward` gives
`[2.1213203435596424, 4.949747468305833, -0.7071067811865475, -0.7071067811865475]`, and
`haar_inverse` of that gives back `[0.9999999999999999, 1.9999999999999998, 3.0, 3.9999999999999996]`).
Two levels on `[1..8]` behave the same way: `haar_multilevel([1..8], 2)` gives
`[5.0, 13.0, -2.0, -2.0, -0.7071..., -0.7071..., -0.7071..., -0.7071...]`, and
`haar_multilevel_inverse` of that at `levels=2` recovers `[1..8]` to the same precision.
`denoise_haar([1..8], 1.0, levels=2)` — soft-thresholding those same coefficients at `1.0` before
inverting — collapses the reconstruction to `[1.5, 1.5, 2.5, 2.5, 5.5, 5.5, 6.5, 6.5]`, four flat
pairs, because every detail coefficient in this particular input has magnitude `<= 1.0` and gets
zeroed, leaving only the coarsest approximation to reconstruct from.

**`energy_ratio`'s docstring names its own precondition, and violating it is silent.** It splits
`coeffs` at `n // 2` and calls the back half "detail energy" — correct for `haar_forward`'s 1-level
output, but `haar_multilevel`'s 2-level output above is laid out as
`[approx_2 (2), detail_2 (2), detail_1 (4)]`; feeding that 8-element array to `energy_ratio` puts
`detail_2` on the "approximation" side of its `n // 2` split rather than the detail side, silently
mixing one level of detail energy into what the function reports as the total-minus-detail
remainder. `energy_ratio` is only correct on a genuine 1-level `haar_forward` output.

## `transform`: statistical preprocessing, not a mathematical transform

This is the one module on this page whose real subject is furthest from what its name suggests. A
name like `transform` in a signal-processing context reads as Laplace, Z-transform, or similar —
this corpus has none of those anywhere. What `transform.mojo` actually implements, per its own
docstring, is "sklearn.preprocessing" reimplemented in pure Mojo: whole-`List[Float64]`-column
statistical transforms that compute their own summary statistics internally.

| Function | What it does |
| --- | --- |
| `log_transform(data)` | `ln(x)`; **raises** on any `x <= 0`. |
| `log1p_transform(data)` | `ln(1+x)`; **raises** if `1+x <= 0`. |
| `box_cox(data, lmbda)` | `(x^lmbda - 1)/lmbda` for `lmbda != 0`, `ln(x)` at `lmbda == 0`; **raises** on any `x <= 0`. |
| `standardize(data)` | `(x - mean) / population_std`; **raises** on empty input or zero std. |
| `min_max_scale(data, new_min=0, new_max=1)` | Scales to `[new_min, new_max]`; **raises** on empty or constant data. |
| `robust_scale(data)` | `(x - median) / IQR` (linear-interpolated quartiles); **raises** on empty data or zero IQR. |
| `quantile_transform(data)` | Percentile rank in `[0, 1]`, ties averaged; **raises** on empty input. |
| `power_transform(data, power)` | `x^power` via `exp(power * ln(\|x\|))`, sign-preserved for negative `x`; `0.0` stays `0.0`. |
| `clamp_values(data, lo, hi)` | Clamp each value to `[lo, hi]`. |
| `rank_transform(data)` | 1-based rank, ties averaged. |
| `abs_transform(data)` | `\|x\|` elementwise. |
| `reciprocal_transform(data)` | `1/x`; **raises** if `\|x\| < 1e-15`. |

Eight of the twelve functions are declared `raises` in Mojo and genuinely propagate an `Error` on
degenerate input, rather than returning `0.0` or an empty list the way most of the other modules on
this page do — a caller treating every function here as "returns a value or a sentinel" will be
surprised the first time one of these throws.

**Two of `transform`'s scaling functions are bit-identical to `ml.preprocessing`'s, and the third
diverges on purpose.** [Classical ML algorithms](ml-classical-algorithms.md) documents
`ml.preprocessing.normalize_minmax` / `normalize_zscore` / `normalize_robust` on the canonical
eight-point dataset `[2, 4, 4, 4, 5, 5, 7, 9]`. Running the same input through `transform`:

```python
data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]

runtime.execute("transform", "min_max_scale", [data, 0.0, 1.0])["result"]
# [0.0, 0.2857142857142857, 0.2857142857142857, 0.2857142857142857,
#  0.42857142857142855, 0.42857142857142855, 0.7142857142857143, 1.0]
# -- identical to ml.preprocessing.normalize_minmax(data)

runtime.execute("transform", "robust_scale", [data])["result"]
# [-1.6666666666666667, -0.3333333333333333, -0.3333333333333333, -0.3333333333333333,
#  0.3333333333333333, 0.3333333333333333, 1.6666666666666667, 3.0]
# -- identical to ml.preprocessing.normalize_robust(data): same median 4.5, same IQR 1.5

runtime.execute("transform", "standardize", [data])["result"]
# [-1.5, -0.5, -0.5, -0.5, 0.0, 0.0, 1.0, 2.0]
# -- NOT identical to ml.preprocessing.normalize_zscore(data), which gives
#    [-1.403121520040228, ..., 1.8708286933869707]
```

`min_max_scale` and `robust_scale` use the same lo/hi and median/IQR formulas as their
`ml.preprocessing` counterparts and land on the exact same numbers. `standardize` diverges because
it divides by the **population** standard deviation (`sqrt(sum((x-mean)^2) / n)`), while
`ml.preprocessing.normalize_zscore` — documented in the same page — uses `math_ext.stdev`, the
**sample** standard deviation (divides by `n - 1`). Porting code that assumes one or the other's
exact output needs to account for that difference, especially at small `n` where the two diverge
most.

This makes `transform` a **third** sibling in the scaling-formula family
[Feedback loops and feature engineering](feedback-loops-and-feature-engineering-kernels.md) already
documents two of: `ml.preprocessing` takes a whole column and computes its own statistics (like
`transform`), while `feature_engineering` takes one value plus caller-supplied statistics and
returns one scaled value. `transform` sits with `ml.preprocessing` on the "whole column, self
sufficient" side of that split, not with `feature_engineering`.

`box_cox` at `lmbda = 0.0` reduces to `log_transform` exactly, by construction (`fabs(lmbda) < 1e-12`
branches to `ln(x)` directly rather than computing `(x^0 - 1)/0`). `power_transform` is the one
function in the table with no `raises` clause and no zero-guard beyond `x == 0.0 -> 0.0`: negative
inputs are handled by computing `exp(power * ln(|x|))` and re-applying the original sign, so
`power_transform([-8.0], 1.0/3.0)` returns `-1.9999999999999998`, a real cube root up to
floating-point rounding, rather than raising on the negative base the way a naive `x**power` would
in a language that refuses fractional powers of negative numbers.

## `series`: the frozen substrate under `forecasting.point`

This module's name suggests generic time-series array plumbing sitting *below* the ARIMA and
forecasting model pages. Reading `series.mojo` confirms the classical-forecaster half of that
guess, and grepping the real `forecasting/*.mojo` source confirms the "underneath" part directly:
`forecasting/point.mojo`, `forecasting/fitted.mojo`, `forecasting/select.mojo`, and
`forecasting/contract.mojo` each contain a literal `from series import ...` line, and
`forecasting.point`'s own module docstring states the relationship in a table:

> | quantity | frozen kernel called unchanged |
> | --- | --- |
> | SES level path / level | `series.exponential_forecast` |
> | naive / drift / window mean | `series.naive_forecast`, `drift_forecast`, `sma_forecast` |
> | seasonal naive | `series.seasonal_naive` |
> | OLS intercept and slope | `series._ols_fit` |

— i.e. the "four baselines" that [Forecasting and backtesting](forecasting.md) describes
`forecasting.point` as offering are `series`'s own `naive_forecast`, `drift_forecast`,
`sma_forecast`, and `seasonal_naive`, called unchanged; `forecasting.point` adds validation, an
absence marker, and a status code on top, but does not re-implement the arithmetic. `series` is
distinct from the two other time-series-adjacent modules already documented: it does not fit AR/MA
coefficients (that is `arima`, in [AR/MA estimation](ml-arima.md)) and it does not compute ACF/PACF
diagnostics (that is `timeseries_stats`, also on that page) — `series` is baseline forecasters and
their scoring, nothing else.

| Function | What it does |
| --- | --- |
| `sma_forecast(data, window, horizon)` | Flat forecast at the mean of the last `window` points (clamped to `len(data)`). |
| `linear_extrapolation(data, horizon)` | OLS line fit to the whole series, extrapolated. |
| `weighted_moving_avg(data, weights)` | Weighted average of the last `len(weights)` points, one scalar. |
| `exponential_forecast(data, alpha, horizon)` | Single exponential smoothing; every horizon step repeats the final smoothed level. |
| `naive_forecast(data, horizon)` | Repeats the last observed value. |
| `seasonal_naive(data, period, horizon)` | Repeats the last full season, cyclically. |
| `drift_forecast(data, horizon)` | Straight line through the first and last points, extrapolated. |
| `forecast_accuracy(actual, predicted)` | Returns `[MAE, MAPE, RMSE]` as a 3-element list. |
| `trend_strength(data)` | `1 - var(OLS residuals) / var(data)`, floored at `0.0`. |
| `detect_seasonality(data, max_period)` | Dominant period in `2..max_period` by highest autocorrelation. |

Worked on a 12-point series with both a trend and a period-4 wobble,
`y = [10, 12, 9, 14, 11, 13, 10, 15, 12, 14, 11, 16]`:

```python
runtime.execute("series", "sma_forecast", [y, 4, 3])["result"]
# [13.25, 13.25, 13.25] -- mean of the last 4 points, repeated

runtime.execute("series", "linear_extrapolation", [y, 3])["result"]
# [14.318181818181818, 14.636363636363637, 14.954545454545453]

runtime.execute("series", "drift_forecast", [y, 3])["result"]
# [16.545454545454547, 17.09090909090909, 17.636363636363637] -- slope = (16-10)/11

runtime.execute("series", "naive_forecast", [y, 3])["result"]
# [16.0, 16.0, 16.0]

runtime.execute("series", "seasonal_naive", [y, 4, 6])["result"]
# [12.0, 14.0, 11.0, 16.0, 12.0, 14.0] -- the last 4 points, tiled

runtime.execute("series", "trend_strength", [y])["result"]
# 0.2770769899956501 -- a real but modest trend against the seasonal wobble

runtime.execute("series", "detect_seasonality", [y, 6])["result"]
# 4 -- correctly recovers the period-4 structure built into y
```

`forecast_accuracy([12.0, 14.0, 11.0], [11.5, 14.5, 10.0])` returns
`[0.6666666666666666, 5.609668109668109, 0.7071067811865476]` — MAE, MAPE (as a percentage), then
RMSE, in that fixed order; there is no flag distinguishing "MAPE undefined at an exact-zero actual"
the way `forecasting.backtest.forecast_errors_flat` reports it — `series.forecast_accuracy` simply
skips zero-actual points inside its own MAPE sum without recording how many it skipped.

`naive_forecast`, `drift_forecast`, and `seasonal_naive` all read `data` at negative or
out-of-bounds-adjacent indices for pathological inputs (empty data, `period <= 0`, `period > n`)
that would be uncatchable aborts in Mojo rather than a Python-style exception; every one of these
guards the pathological case explicitly and returns `horizon` zeros (or, for `drift_forecast` with
fewer than 2 points, `data[0]` repeated) instead — the source code's own comments name exactly
which read would otherwise go out of bounds.

## Verification

All six `mojo/tests/libs/test_*.mojo` files behind this page (`test_fft.mojo`, `test_spectral.mojo`,
`test_wavelet.mojo`, `test_transform.mojo`, `test_signal_processing.mojo`, `test_series.mojo`) are
auto-generated coverage smoke tests: each calls every function once against a fixed
`[0.5, 0.6, 0.7, 0.4, 0.3]`-style fixture and checks only that the result is finite or non-negative
length — none pin a specific numeric output. Notably, `test_fft.mojo` calls `fft` directly on that
5-element (non-power-of-2) fixture and only asserts `len(result) >= 0`, which is true regardless of
correctness — the smoke suite does not exercise, and cannot catch, the silent-truncation behavior
described above.

Every worked number on this page was independently computed by re-implementing the real formulas
from `mojo/engine/fft.mojo`, `spectral.mojo`, `wavelet.mojo`, `transform.mojo`,
`signal_processing.mojo`, and `series.mojo` in Python and running the arithmetic directly — the
power-of-2 FFT results were additionally cross-checked against `numpy.fft.fft` on the same inputs,
matching to full float precision. Every number can be reproduced by re-running the same arithmetic.

**Next:** [Forecasting and backtesting](forecasting.md) and [AR/MA estimation](ml-arima.md) for the
higher-level models `series` sits underneath, [Classical ML algorithms](ml-classical-algorithms.md)
for the `ml.preprocessing` scaling functions `transform` overlaps with, or the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
