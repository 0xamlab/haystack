"""Algenta arm of the survival-analysis head-to-head against `lifelines`.

Usage: survival_h2h <mode> ...
  km_rossi   <data_dir> <dump_dir> <reps>            n=432, conf=0.95, real dataset
  km_synth   <n> <dump_dir> <reps>                   conf=0.95, synthetic, deterministic
  cox_rossi  <data_dir> <dump_dir> <reps>            n=432, p=7, real dataset
  cox_synth  <n> <p> <dump_dir> <reps>                synthetic, deterministic

Why this is TWO PROCESSES rather than one, unlike `bench_vs_sort.mojo`
-----------------------------------------------------------------------
`bench_vs_sort.mojo` calls `numpy` in-process via Mojo's Python interop because numpy is
installed in the SAME embedded CPython the Mojo runtime binds to (`mojo_env`'s pixi
environment). `lifelines` is not installed there -- it depends on `pandas`/`scipy`, which
that environment does not carry, and installing it would mean vendoring a dependency this
package (survival_analysis) does not otherwise need. `lifelines` IS installed in the
system Python this repo's tooling already uses elsewhere. So this file writes its results
to disk and a separate Python process (`lifelines_refs.py`, run under the system
interpreter) reads them and computes the `lifelines` side -- the same "dump, then compare
out of process" shape `gemm_h2h.mojo`'s `dumpgemm`/`dumpnf4` modes already use for
NF4-quantized weights. The dump format itself is the RAW BINARY one from
`forecasting_m4_h2h.mojo`'s `read_f64`/`write_f64` (8 little-endian bytes per `Float64`,
no text) rather than gemm's decimal-bit-pattern-per-line text format: the KM sweep goes up
to n=1,000,000 event times, and `np.loadtxt` on a million-line text file measured over a
minute on this machine where `np.fromfile` on the binary equivalent measured under 10 ms --
a difference that would otherwise dwarf the thing being benchmarked. Still an exact round
trip: `lifelines_refs.py`'s `load_dump` is `np.fromfile(path, dtype='<f8')`.

Correctness is therefore checked by `lifelines_refs.py`, not by this file: this file's job
is only to produce the kernel's real output on real (or realistically-shaped synthetic)
input and to time it. Timing here is per-process cold/warm/hot exactly as `gemm_h2h.mojo`
defines it: rep 0 is cold (first call in this process), rep 1 is warm, and the minimum of
the rest is hot. `drive_survival.py` is what enforces a gate over both processes' output.

The two data sources
---------------------
ROSSI: `prep_rossi.py` dumps lifelines' own bundled `load_rossi()` (432 subjects, a real
1980 recidivism study, the exact dataset lifelines' own Cox-regression tutorial uses) to
raw float64 files. This file reads those same bytes, so the Algenta arm and the
`lifelines` arm are provably looking at identical numbers -- not two loaders that are
supposed to agree.

SYNTHETIC: for the scaling sweep, real survival datasets at n = 1e5 or 1e6 do not exist to
borrow, so sizes above what Rossi provides use a closed-form, RNG-free generator -- the
same choice `bench_vs_sort.mojo` and `gemm_h2h.mojo` make for their own scaling sweeps.
Every generator here is pure integer/float arithmetic with no library call on either side,
so the SAME formula, written twice (once here, once in `lifelines_refs.py`), produces
bit-identical IEEE-754 doubles: this is not two implementations hoping to agree, it is one
formula evaluated by two conforming floating-point units.

  KM (`_km_times`/`_km_events`): times are `1 + i*step`, all distinct, except at every
  `tie_period`-th index the time is forced equal to the previous row's -- a controlled tie
  rate (~1/tie_period of rows) rather than an accidental one. Events are censored at every
  `censor_period`-th index -- a controlled, stated censoring fraction.

  Cox (`_pseudo`/`_pseudo_u01`): covariates are the LCG `_pseudo` already proven
  bit-identical to NumPy in `gemm_refs.py` (see that file's docstring). Survival times are
  then drawn from an ACTUAL proportional-hazards process, `T = -ln(U) / exp(eta)` with
  `eta = X @ beta_true`, `U` a second independent LCG stream mapped to (0, 1) -- so the
  covariates and the times are genuinely dependent, the way a real Cox dataset's are,
  rather than generated independently and coincidentally passed through the fitter. A
  fixed administrative censoring horizon `tau` is applied afterward.
"""
from std.math import exp, log
from std.memory import Span
from std.os import getenv
from std.sys import argv
from std.time import perf_counter_ns

from survival_analysis.base import SA_OK
from survival_analysis.cox import cox_fit
from survival_analysis.km import km_fit


fn read_f64(path: String) raises -> List[Float64]:
    """Copied from `forecasting_m4_h2h.mojo`'s helper of the same name."""
    var f = open(path, "r")
    var b = f.read_bytes()
    f.close()
    var n = len(b) // 8
    var p = b.unsafe_ptr().bitcast[Float64]()
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(p[i])
    return out^


fn _dump(path: String, mut v: List[Float64]) raises:
    """Copied from `forecasting_m4_h2h.mojo`'s `write_f64`: raw little-endian bytes."""
    var w = open(path, "w")
    var bp = v.unsafe_ptr().bitcast[UInt8]()
    w.write_bytes(Span[UInt8, origin_of(v)](ptr=bp, length=len(v) * 8))
    w.close()


fn _b(flag: Bool) -> Float64:
    return 1.0 if flag else 0.0


fn _pseudo(n: Int, seed: Int) -> List[Float64]:
    """Bit-identical to `gemm_h2h.mojo`'s `_pseudo` (and to `gemm_refs.py`'s `pseudo`)."""
    var o = List[Float64](capacity=n)
    var s = seed
    for _ in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        o.append(Float64(s % 2000 - 1000) / 1000.0)
    return o^


fn _pseudo_u01(n: Int, seed: Int) -> List[Float64]:
    """Same LCG, mapped to the open interval (0, 1) rather than [-1, 1)."""
    var o = List[Float64](capacity=n)
    var s = seed
    for _ in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        o.append(Float64(s % 1000000000 + 1) / 1000000002.0)
    return o^


fn _km_times(n: Int, step: Float64, tie_period: Int) -> List[Float64]:
    """`1 + i*step`, with every `tie_period`-th row forced onto the previous row's time."""
    var out = List[Float64](capacity=n)
    for i in range(n):
        var t = 1.0 + Float64(i) * step
        if tie_period > 0 and i > 0 and i % tie_period == 0:
            t = out[i - 1]
        out.append(t)
    return out^


fn _km_events(n: Int, censor_period: Int) -> List[Int]:
    var out = List[Int](capacity=n)
    for i in range(n):
        out.append(0 if (censor_period > 0 and i % censor_period == 0) else 1)
    return out^


fn _cox_synth_beta_true(p: Int) -> List[Float64]:
    """A fixed, non-degenerate coefficient pattern: alternating +0.3 / -0.2."""
    var out = List[Float64](capacity=p)
    for k in range(p):
        out.append(0.3 if k % 2 == 0 else -0.2)
    return out^


struct _CoxSynth(Movable):
    var x: List[Float64]
    var times: List[Float64]
    var event: List[Int]

    fn __init__(out self, var x: List[Float64], var times: List[Float64], var event: List[Int]):
        self.x = x^
        self.times = times^
        self.event = event^


fn _cox_synth_data(n: Int, p: Int) -> _CoxSynth:
    """Covariates from `_pseudo`, times from an actual proportional-hazards draw.

    `tau = ln(4)` is the administrative censoring horizon: for a pure `Exp(1)` (the
    `eta = 0` case) that gives `P(T > tau) = 0.25` by construction; the covariate term
    perturbs the realized censoring fraction somewhat, and the realized rate is printed by
    the caller rather than assumed.
    """
    var x = _pseudo(n * p, 7)
    var beta_true = _cox_synth_beta_true(p)
    var u = _pseudo_u01(n, 991)
    comptime tau: Float64 = 1.3862943611198906  # ln(4)
    var times = List[Float64](capacity=n)
    var event = List[Int](capacity=n)
    for i in range(n):
        var eta: Float64 = 0.0
        for k in range(p):
            eta += beta_true[k] * x[i * p + k]
        var raw = -log(u[i]) / exp(eta)
        if raw > tau:
            times.append(tau)
            event.append(0)
        else:
            times.append(raw)
            event.append(1)
    return _CoxSynth(x^, times^, event^)


fn main() raises:
    var a = argv()
    var mode = String(a[1])

    if mode == "km_rossi" or mode == "km_synth":
        var times = List[Float64]()
        var event = List[Int]()
        var n = 0
        var dump_dir = String("")
        var reps = 0
        if mode == "km_rossi":
            var data_dir = String(a[2])
            dump_dir = String(a[3])
            reps = Int(String(a[4]))
            var week = read_f64(data_dir + "/rossi_week.f64")
            var arrest = read_f64(data_dir + "/rossi_arrest.f64")
            n = len(week)
            for i in range(n):
                times.append(week[i])
                event.append(Int(arrest[i] + 0.5))
        else:
            n = Int(String(a[2]))
            dump_dir = String(a[3])
            reps = Int(String(a[4]))
            times = _km_times(n, 0.01, 41)
            event = _km_events(n, 4)
            # Dumped so `lifelines_refs.py` loads these EXACT bytes rather than
            # re-deriving them from its own re-implementation of `_km_times`/`_km_events`.
            # Measured reason this matters: `1.0 + Float64(i) * step` evaluated by Mojo's
            # LLVM backend and the textually-identical expression evaluated by CPython
            # disagreed in the last bit at i=14 (`1.1400000000000001` either way, but that
            # display hides a real ULP: `kmf.durations[14]` compared bit-exact to Python's
            # own recomputation, yet 64 of 738 event times were absent from a by-value
            # lookup against Mojo's dumped kernel-internal time array) -- almost certainly
            # FMA contraction fusing the multiply-add into one rounding step on one side and
            # not the other. Two "identical" formulas in two compiled languages are not
            # proof of bit-identical output; two loads of the same bytes are.
            var event_f = List[Float64](capacity=n)
            for i in range(n):
                event_f.append(_b(event[i] == 1))
            _dump(dump_dir + "/input_time.f64", times)
            _dump(dump_dir + "/input_event.f64", event_f)

        var n_events = 0
        for i in range(n):
            n_events += event[i]
        print("META n", n, "n_events", n_events, "censor_rate", Float64(n - n_events) / Float64(n))

        var fit = km_fit(times, event, 0.95)
        if fit.status != SA_OK:
            print("KM_STATUS_FAIL", fit.status)
            return
        print("META n_event_times", fit.n_event_times, "median_time", fit.median_time, "has_median", fit.has_median)

        var se = List[Float64](capacity=fit.n_event_times)
        var has_se = List[Float64](capacity=fit.n_event_times)
        var has_band = List[Float64](capacity=fit.n_event_times)
        for j in range(fit.n_event_times):
            se.append(fit.std_error[j])
            has_se.append(_b(fit.has_std_error[j]))
            has_band.append(_b(fit.has_band[j]))

        _dump(dump_dir + "/km_time.f64", fit.time)
        _dump(dump_dir + "/km_survival.f64", fit.survival)
        _dump(dump_dir + "/km_se.f64", se)
        _dump(dump_dir + "/km_has_se.f64", has_se)
        _dump(dump_dir + "/km_lower.f64", fit.lower)
        _dump(dump_dir + "/km_upper.f64", fit.upper)
        _dump(dump_dir + "/km_has_band.f64", has_band)
        print("DUMPED km", n)

        for r in range(reps):
            var t0 = perf_counter_ns()
            var f2 = km_fit(times, event, 0.95)
            var ns = Int(perf_counter_ns() - t0)
            if f2.status != SA_OK:
                print("STATUS_FAIL")
            print("T", mode, n, r, ns)

    elif mode == "cox_rossi" or mode == "cox_synth":
        var x = List[Float64]()
        var times = List[Float64]()
        var event = List[Int]()
        var n = 0
        var p = 0
        var dump_dir = String("")
        var reps = 0
        var max_iter = 100
        if mode == "cox_rossi":
            var data_dir = String(a[2])
            dump_dir = String(a[3])
            max_iter = Int(String(a[4]))
            reps = Int(String(a[5]))
            var week = read_f64(data_dir + "/rossi_week.f64")
            var arrest = read_f64(data_dir + "/rossi_arrest.f64")
            n = len(week)
            p = 7
            var cols = List[String]()
            cols.append(String("fin"))
            cols.append(String("age"))
            cols.append(String("race"))
            cols.append(String("wexp"))
            cols.append(String("mar"))
            cols.append(String("paro"))
            cols.append(String("prio"))
            var colvals = List[List[Float64]]()
            for c in range(p):
                colvals.append(read_f64(data_dir + "/rossi_" + cols[c] + ".f64"))
            x = List[Float64](capacity=n * p)
            for i in range(n):
                for c in range(p):
                    x.append(colvals[c][i])
                times.append(week[i])
                event.append(Int(arrest[i] + 0.5))
        else:
            n = Int(String(a[2]))
            p = Int(String(a[3]))
            max_iter = Int(String(a[4]))
            dump_dir = String(a[5])
            reps = Int(String(a[6]))
            var gen = _cox_synth_data(n, p)
            x = gen.x.copy()
            times = gen.times.copy()
            event = gen.event.copy()
            # See the matching comment in the km_synth branch: dumped so
            # `lifelines_refs.py` reads these exact bytes instead of re-deriving them from
            # its own re-implementation of `_pseudo`/`_pseudo_u01`/`_cox_synth_data`.
            var event_f = List[Float64](capacity=n)
            for i in range(n):
                event_f.append(_b(event[i] == 1))
            _dump(dump_dir + "/input_x.f64", x)
            _dump(dump_dir + "/input_time.f64", times)
            _dump(dump_dir + "/input_event.f64", event_f)

        var n_events = 0
        for i in range(n):
            n_events += event[i]
        print("META n", n, "p", p, "n_events", n_events, "censor_rate", Float64(n - n_events) / Float64(n), "max_iter", max_iter)

        # tol = 1e-7: tight enough that `test_survival_analysis_cox.mojo` cross-checks it
        # against an independently written Newton to ~1e-6 relative on beta/se, but not so
        # tight that it chases the last few bits of the log-likelihood -- see the module
        # docstring's note on `SA_COX_FLATNESS_RATIO` needing headroom near the optimum:
        # 1e-9 was observed to trip `SA_ERR_SEPARATION` on well-conditioned synthetic data
        # (n=1000, p=4) that a 1e-7 tolerance converges on cleanly in 3 iterations.
        var fit = cox_fit(x, n, p, times, event, max_iter, 1e-7)
        print("COXFIT status", fit.status, "iterations", fit.iterations, "converged", fit.converged)
        if fit.status != SA_OK:
            print("COX_STATUS_FAIL", fit.status)
            return

        var has_se = List[Float64](capacity=p)
        for k in range(p):
            has_se.append(_b(fit.has_std_error[k]))
        _dump(dump_dir + "/cox_beta.f64", fit.beta)
        _dump(dump_dir + "/cox_se.f64", fit.std_error)
        _dump(dump_dir + "/cox_has_se.f64", has_se)
        var scalars = List[Float64]()
        scalars.append(fit.loglik)
        scalars.append(fit.loglik_null)
        scalars.append(fit.lr_statistic)
        _dump(dump_dir + "/cox_scalars.f64", scalars)
        print("DUMPED cox", n, p)

        for r in range(reps):
            var t0 = perf_counter_ns()
            var f2 = cox_fit(x, n, p, times, event, max_iter, 1e-7)
            var ns = Int(perf_counter_ns() - t0)
            if f2.status != SA_OK:
                print("STATUS_FAIL")
            print("T", mode, n, r, ns)
    else:
        print("unknown mode", mode)
