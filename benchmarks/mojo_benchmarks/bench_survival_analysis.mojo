"""bench_survival_analysis.mojo — the SHAPE gate for the survival_analysis package.

What is gated, and what is only printed
---------------------------------------
Every gate is on a SHAPE: a per-unit cost that must stay flat as the problem grows, or a
declared work count that must equal the work performed. No absolute nanosecond figure is gated.
Absolute times depend on the machine and its load -- this file was developed on a box carrying a
load average of 500 to 660 from unrelated work -- so a gate on them manufactures failures
instead of signal. They are printed, labelled `(ungated)`, because a reader wants them.

The per-unit gate for the smoothed hazard is the whole reason this file exists
------------------------------------------------------------------------------
`na_smoothed_hazard` used to charge `k * n` against the work budget while the frozen kernel it
called performed TWO `O(k * n)` passes, so a request the budget declared as ~1 s measured
5.97 s: a 6x undercharge, which no memory bound can catch. The estimator is now this package's
own, its cost is exactly the number of in-window (event time, event time) pairs, and that number
is COUNTED in `O(k)` before the first kernel evaluation and published as `kernel_pairs`.

Two gates on it, testing different things:

* `kernel_pairs` equals a hand-derived count (19) on a five-point case, and equals `k * k`
  exactly when the window spans the sample -- the charge is checked against arithmetic a reader
  can do, not against itself.
* nanoseconds per charged pair stays flat as the problem grows in BOTH regimes -- a fixed
  window, where the count grows like `k`, and a full window, where it grows like `k^2`.
* the MARGINAL nanoseconds per charged pair -- the same sample timed at two bandwidths and
  differenced, which cancels the O(n log n) setup exactly -- is flat as the pair count grows
  16x. That is the number the work budget charges for, and it is the gate with teeth: a charge
  wrong by a factor of `k` inflates it 16x.

The two per-regime figures are NOT comparable to each other, and an earlier version of this file
wrongly gated that they were. At a fixed window the setup is amortised over ~17 pairs per point
and dominates; at a full window it is amortised over `k^2`. Measured, they differed 25x with
nothing wrong -- which is why the cross-check is a DIFFERENCE at one size rather than a ratio
across two regimes.

Why every kernel call is inside a one-line helper
-------------------------------------------------
A kernel here returns a struct with a dozen or more `List` fields. Constructing one INSIDE A
LOOP made this file take over ten minutes of CPU to COMPILE, before executing a line; the same
file with the repetition loop removed compiled in 33 s. So each call sits in a helper that
returns `Float64`/`Int` only, and the loops carry flat values. Repeats are unrolled as four
straight-line calls and reduced with a MINIMUM, which is the right statistic here: contention
only ever inflates a measurement. Measured on this box, the identical full-window `k = 2048`
call returned 2.31 ns/pair and 14.50 ns/pair inside ONE process -- a 6x spread with no change
in the work -- so a single sample cannot support a shape gate and the minimum can.

Data is deterministic and RNG-free
----------------------------------
Every input is a closed-form arithmetic pattern. Nothing samples, so there is no seed to record
and two runs on one binary see bit-identical inputs.
"""
from std.time import perf_counter_ns

from survival_analysis.base import SA_OK
from survival_analysis.competing import cif_fit
from survival_analysis.cox import cox_fit
from survival_analysis.hazard import na_fit, na_smoothed_hazard
from survival_analysis.km import km_fit, km_survival_at
from survival_analysis.parametric import lognormal_mle, weibull_mle


def _times(n: Int, step: Float64, tie_mod: Int) -> List[Float64]:
    var out = List[Float64]()
    for i in range(n):
        var group = i // tie_mod if tie_mod > 1 else i
        out.append(1.0 + Float64(group) * step)
    return out^


def _events(n: Int, censor_every: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(n):
        out.append(0 if (censor_every > 0 and i % censor_every == 0) else 1)
    return out^


def _causes(n: Int, n_causes: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(n):
        if i % 5 == 0:
            out.append(0)
        else:
            out.append(1 + (i % n_causes))
    return out^


def _covariates(n: Int, p: Int) -> List[Float64]:
    var out = List[Float64]()
    for i in range(n * p):
        out.append(Float64((i * 37) % 19) / 19.0 - 0.5)
    return out^


def _ratio(a: Float64, b: Float64) -> Float64:
    if b == 0.0:
        return 0.0
    return a / b


def _min2(a: Float64, b: Float64) -> Float64:
    return a if a < b else b


def _say(label: String, value: Float64):
    print("   " + label + " " + String(value) + " (ungated)")


def _say_int(label: String, value: Int):
    print("   " + label + " " + String(value) + " (ungated)")


def _gate(label: String, growth: Float64, ceiling: Float64) -> Int:
    if growth <= 0.0 or growth > ceiling:
        print("   FAIL " + label + " grew " + String(growth) + "x")
        return 1
    print("   PASS " + label + " flat within " + String(growth) + "x")
    return 0


# ── one kernel call per helper; nothing that returns a struct enters a loop ────


def _once_km(t: List[Float64], e: List[Int]) -> Float64:
    var t0 = perf_counter_ns()
    var f = km_fit(t, e, 0.95)
    var t1 = perf_counter_ns()
    return Float64(t1 - t0) if f.status == SA_OK else -1.0


def _once_na(t: List[Float64], e: List[Int]) -> Float64:
    var t0 = perf_counter_ns()
    var f = na_fit(t, e, 0.95)
    var t1 = perf_counter_ns()
    return Float64(t1 - t0) if f.status == SA_OK else -1.0


def _once_smoothed(t: List[Float64], e: List[Int], b: Float64) -> Float64:
    var t0 = perf_counter_ns()
    var f = na_smoothed_hazard(t, e, b)
    var t1 = perf_counter_ns()
    return Float64(t1 - t0) if f.status == SA_OK else -1.0


def _pairs(t: List[Float64], e: List[Int], b: Float64) -> Int:
    var f = na_smoothed_hazard(t, e, b)
    return f.kernel_pairs if f.status == SA_OK else -1


def _once_lookup(t: List[Float64], e: List[Int], q: List[Float64]) -> Float64:
    var t0 = perf_counter_ns()
    var f = km_survival_at(t, e, q)
    var t1 = perf_counter_ns()
    return Float64(t1 - t0) if f.status == SA_OK else -1.0


def _once_cox(x: List[Float64], n: Int, t: List[Float64], e: List[Int]) -> Float64:
    var t0 = perf_counter_ns()
    var f = cox_fit(x, n, 2, t, e, 100, 1e-9)
    var t1 = perf_counter_ns()
    return Float64(t1 - t0) if f.status == SA_OK else -1.0


def _cox_iters(x: List[Float64], n: Int, t: List[Float64], e: List[Int]) -> Int:
    var f = cox_fit(x, n, 2, t, e, 100, 1e-9)
    return f.iterations if f.status == SA_OK else -1


def _once_weibull(t: List[Float64], e: List[Int]) -> Float64:
    var t0 = perf_counter_ns()
    var f = weibull_mle(t, e, 200, 1e-12)
    var t1 = perf_counter_ns()
    return Float64(t1 - t0) if f.status == SA_OK else -1.0


def _weibull_iters(t: List[Float64], e: List[Int]) -> Int:
    var f = weibull_mle(t, e, 200, 1e-12)
    return f.iterations if f.status == SA_OK else -1


def _once_lognormal(t: List[Float64], e: List[Int]) -> Float64:
    var t0 = perf_counter_ns()
    var f = lognormal_mle(t, e, 200, 1e-9)
    var t1 = perf_counter_ns()
    return Float64(t1 - t0) if f.status == SA_OK else -1.0


def _lognormal_iters(t: List[Float64], e: List[Int]) -> Int:
    var f = lognormal_mle(t, e, 200, 1e-9)
    return f.iterations if f.status == SA_OK else -1


def _once_cif(t: List[Float64], c: List[Int]) -> Float64:
    var t0 = perf_counter_ns()
    var f = cif_fit(t, c, 3)
    var t1 = perf_counter_ns()
    return Float64(t1 - t0) if f.status == SA_OK else -1.0


def _cif_cells(t: List[Float64], c: List[Int]) -> Int:
    var f = cif_fit(t, c, 3)
    return f.n_causes * f.n_event_times if f.status == SA_OK else -1



def _t_km(t: List[Float64], e: List[Int]) -> Float64:
    """Fastest of four straight-line calls. See the docstring: a MINIMUM is the right
    statistic on a contended machine (contention only ever inflates a measurement), and the
    repeats are unrolled because a struct constructed in a loop costs minutes of compile."""
    var d1 = _once_km(t, e)
    var d2 = _once_km(t, e)
    var d3 = _once_km(t, e)
    var d4 = _once_km(t, e)
    if d1 < 0.0 or d2 < 0.0 or d3 < 0.0 or d4 < 0.0:
        return -1.0
    return _min2(_min2(d1, d2), _min2(d3, d4))

def _t_na(t: List[Float64], e: List[Int]) -> Float64:
    """Fastest of four straight-line calls. See the docstring: a MINIMUM is the right
    statistic on a contended machine (contention only ever inflates a measurement), and the
    repeats are unrolled because a struct constructed in a loop costs minutes of compile."""
    var d1 = _once_na(t, e)
    var d2 = _once_na(t, e)
    var d3 = _once_na(t, e)
    var d4 = _once_na(t, e)
    if d1 < 0.0 or d2 < 0.0 or d3 < 0.0 or d4 < 0.0:
        return -1.0
    return _min2(_min2(d1, d2), _min2(d3, d4))

def _t_smoothed(t: List[Float64], e: List[Int], b: Float64) -> Float64:
    """Fastest of four straight-line calls. See the docstring: a MINIMUM is the right
    statistic on a contended machine (contention only ever inflates a measurement), and the
    repeats are unrolled because a struct constructed in a loop costs minutes of compile."""
    var d1 = _once_smoothed(t, e, b)
    var d2 = _once_smoothed(t, e, b)
    var d3 = _once_smoothed(t, e, b)
    var d4 = _once_smoothed(t, e, b)
    if d1 < 0.0 or d2 < 0.0 or d3 < 0.0 or d4 < 0.0:
        return -1.0
    return _min2(_min2(d1, d2), _min2(d3, d4))

def _t_lookup(t: List[Float64], e: List[Int], q: List[Float64]) -> Float64:
    """Fastest of four straight-line calls. See the docstring: a MINIMUM is the right
    statistic on a contended machine (contention only ever inflates a measurement), and the
    repeats are unrolled because a struct constructed in a loop costs minutes of compile."""
    var d1 = _once_lookup(t, e, q)
    var d2 = _once_lookup(t, e, q)
    var d3 = _once_lookup(t, e, q)
    var d4 = _once_lookup(t, e, q)
    if d1 < 0.0 or d2 < 0.0 or d3 < 0.0 or d4 < 0.0:
        return -1.0
    return _min2(_min2(d1, d2), _min2(d3, d4))

def _t_cox(x: List[Float64], n: Int, t: List[Float64], e: List[Int]) -> Float64:
    """Fastest of four straight-line calls. See the docstring: a MINIMUM is the right
    statistic on a contended machine (contention only ever inflates a measurement), and the
    repeats are unrolled because a struct constructed in a loop costs minutes of compile."""
    var d1 = _once_cox(x, n, t, e)
    var d2 = _once_cox(x, n, t, e)
    var d3 = _once_cox(x, n, t, e)
    var d4 = _once_cox(x, n, t, e)
    if d1 < 0.0 or d2 < 0.0 or d3 < 0.0 or d4 < 0.0:
        return -1.0
    return _min2(_min2(d1, d2), _min2(d3, d4))

def _t_weibull(t: List[Float64], e: List[Int]) -> Float64:
    """Fastest of four straight-line calls. See the docstring: a MINIMUM is the right
    statistic on a contended machine (contention only ever inflates a measurement), and the
    repeats are unrolled because a struct constructed in a loop costs minutes of compile."""
    var d1 = _once_weibull(t, e)
    var d2 = _once_weibull(t, e)
    var d3 = _once_weibull(t, e)
    var d4 = _once_weibull(t, e)
    if d1 < 0.0 or d2 < 0.0 or d3 < 0.0 or d4 < 0.0:
        return -1.0
    return _min2(_min2(d1, d2), _min2(d3, d4))

def _t_lognormal(t: List[Float64], e: List[Int]) -> Float64:
    """Fastest of four straight-line calls. See the docstring: a MINIMUM is the right
    statistic on a contended machine (contention only ever inflates a measurement), and the
    repeats are unrolled because a struct constructed in a loop costs minutes of compile."""
    var d1 = _once_lognormal(t, e)
    var d2 = _once_lognormal(t, e)
    var d3 = _once_lognormal(t, e)
    var d4 = _once_lognormal(t, e)
    if d1 < 0.0 or d2 < 0.0 or d3 < 0.0 or d4 < 0.0:
        return -1.0
    return _min2(_min2(d1, d2), _min2(d3, d4))

def _t_cif(t: List[Float64], c: List[Int]) -> Float64:
    """Fastest of four straight-line calls. See the docstring: a MINIMUM is the right
    statistic on a contended machine (contention only ever inflates a measurement), and the
    repeats are unrolled because a struct constructed in a loop costs minutes of compile."""
    var d1 = _once_cif(t, c)
    var d2 = _once_cif(t, c)
    var d3 = _once_cif(t, c)
    var d4 = _once_cif(t, c)
    if d1 < 0.0 or d2 < 0.0 or d3 < 0.0 or d4 < 0.0:
        return -1.0
    return _min2(_min2(d1, d2), _min2(d3, d4))

# ── sections ──────────────────────────────────────────────────────────────────


def _bench_curves() -> Int:
    print("-- km_fit / na_fit: ns per observation, O(n log n) claimed --")
    var failures = 0
    var sizes = List[Int]()
    sizes.append(4096)
    sizes.append(16384)
    sizes.append(65536)
    var per_km = List[Float64]()
    var per_na = List[Float64]()
    for s in range(len(sizes)):
        var n = sizes[s]
        var t = _times(n, 0.5, 3)
        var e = _events(n, 4)
        var km = _t_km(t, e)
        var na = _t_na(t, e)
        if km < 0.0 or na < 0.0:
            failures += 1
            print("   FAIL a curve fit was refused")
        per_km.append(km / Float64(n))
        per_na.append(na / Float64(n))
        _say_int("n =", n)
        _say("   km ns/obs =", per_km[s])
        _say("   na ns/obs =", per_na[s])
    # 16x in n at O(n log n) predicts 1.34x in ns/obs. The 4.0 ceiling absorbs cache effects and
    # machine load and still fails an O(n^2) implementation, which would grow 16x.
    failures += _gate("km_fit ns/obs over 16x n", _ratio(per_km[2], per_km[0]), 4.0)
    failures += _gate("na_fit ns/obs over 16x n", _ratio(per_na[2], per_na[0]), 4.0)
    return failures


def _bench_smoothed() -> Int:
    print("-- na_smoothed_hazard: ns per CHARGED kernel pair --")
    var failures = 0

    # hand-derived: times 1..5, all events, b = 2 -> windows 3 + 4 + 5 + 4 + 3 = 19
    var five = _times(5, 1.0, 1)
    var all_ev = _events(5, 0)
    if _pairs(five, all_ev, 2.0) != 19:
        failures += 1
        print("   FAIL hand-derived pair count is not 19")
    else:
        print("   PASS kernel_pairs = 19 on the hand-counted 5-point case")

    var sizes = List[Int]()
    sizes.append(2048)
    sizes.append(8192)
    sizes.append(32768)
    var per_a = List[Float64]()
    for s in range(len(sizes)):
        var n = sizes[s]
        var t = _times(n, 1.0, 1)
        var e = _events(n, 0)
        var pairs = _pairs(t, e, 8.0)
        var best = _t_smoothed(t, e, 8.0)
        if pairs < 0 or best < 0.0:
            failures += 1
            print("   FAIL fixed-window smoothing was refused")
        per_a.append(_ratio(best, Float64(pairs)))
        _say_int("fixed window k =", n)
        _say_int("   kernel_pairs =", pairs)
        _say("   ns/pair =", per_a[s])

    var sizes_b = List[Int]()
    sizes_b.append(512)
    sizes_b.append(1024)
    sizes_b.append(2048)
    var per_b = List[Float64]()
    for s in range(len(sizes_b)):
        var n = sizes_b[s]
        var t = _times(n, 1.0, 1)
        var e = _events(n, 0)
        var band = Float64(n) * 2.0
        var pairs = _pairs(t, e, band)
        var best = _t_smoothed(t, e, band)
        per_b.append(_ratio(best, Float64(pairs)))
        if pairs != n * n:
            failures += 1
            print("   FAIL full window charged " + String(pairs) + ", want k*k")
        else:
            print("   PASS full window charged exactly k*k = " + String(pairs))
        _say("   ns/pair =", per_b[s])

    failures += _gate("ns/pair, fixed window, 16x k", _ratio(per_a[2], per_a[0]), 3.0)
    failures += _gate("ns/pair, full window, 16x pairs", _ratio(per_b[2], per_b[0]), 3.0)

    # THE MARGINAL COST OF ONE CHARGED PAIR, with the setup subtracted out. The two figures
    # above are NOT comparable to each other and an earlier version of this file wrongly gated
    # that they were: at a fixed window the O(n log n) setup -- the sort, the risk table and the
    # frozen cumulative-hazard cross-check -- is amortised over only ~17 pairs per point, so it
    # dominates, while at a full window it is amortised over k^2. Measured, that made the two
    # regimes differ 25x with nothing wrong. Differencing two bandwidths at the SAME k removes
    # the setup exactly, and what is left is the quantity the work budget actually charges for.
    var marg = List[Float64]()
    for s in range(len(sizes_b)):
        var n = sizes_b[s]
        var t = _times(n, 1.0, 1)
        var e = _events(n, 0)
        var band = Float64(n) * 2.0
        var p_small = _pairs(t, e, 1.5)
        var p_full = _pairs(t, e, band)
        var d_small = _t_smoothed(t, e, 1.5)
        var d_full = _t_smoothed(t, e, band)
        if p_small < 0 or p_full <= p_small or d_small < 0.0 or d_full < 0.0:
            failures += 1
            print("   FAIL the marginal-cost measurement is not usable")
        marg.append(_ratio(d_full - d_small, Float64(p_full - p_small)))
        _say_int("marginal at k =", n)
        _say("   marginal ns/pair =", marg[s])
    failures += _gate("marginal ns/pair over 16x pairs", _ratio(marg[2], marg[0]), 3.0)
    return failures


def _bench_lookup() -> Int:
    print("-- km_survival_at: ns per (query x curve point) --")
    var failures = 0
    var sizes = List[Int]()
    sizes.append(256)
    sizes.append(512)
    sizes.append(1024)
    var per_unit = List[Float64]()
    for s in range(len(sizes)):
        var n = sizes[s]
        var t = _times(n, 1.0, 1)
        var e = _events(n, 0)
        var q = _times(n, 1.0, 1)
        var best = _t_lookup(t, e, q)
        if best < 0.0:
            failures += 1
            print("   FAIL the lookup was refused")
        per_unit.append(_ratio(best, Float64(n) * Float64(n)))
        _say_int("q = k =", n)
        _say("   ns/(q*k) =", per_unit[s])
    failures += _gate("ns/(q*k) over 16x units", _ratio(per_unit[2], per_unit[0]), 3.0)
    return failures


def _bench_fits() -> Int:
    print("-- cox_fit / weibull_mle / lognormal_mle: per-iteration unit cost --")
    var failures = 0
    var sizes = List[Int]()
    sizes.append(512)
    sizes.append(2048)
    sizes.append(8192)
    var per_cox = List[Float64]()
    var per_wb = List[Float64]()
    var per_ln = List[Float64]()
    for s in range(len(sizes)):
        var n = sizes[s]
        var t = _times(n, 0.5, 3)
        var e = _events(n, 4)
        var x = _covariates(n, 2)
        var cox_it = _cox_iters(x, n, t, e)
        var wb_it = _weibull_iters(t, e)
        var ln_it = _lognormal_iters(t, e)
        var cox_ns = _t_cox(x, n, t, e)
        var wb_ns = _t_weibull(t, e)
        var ln_ns = _t_lognormal(t, e)
        if cox_it < 0 or wb_it < 0 or ln_it < 0:
            failures += 1
            print("   FAIL a fit was refused")
        per_cox.append(_ratio(cox_ns, Float64(cox_it) * Float64(n) * 4.0))
        per_wb.append(_ratio(wb_ns, Float64(wb_it) * Float64(n)))
        per_ln.append(_ratio(ln_ns, Float64(ln_it) * Float64(n)))
        _say_int("n =", n)
        _say_int("   cox iterations =", cox_it)
        _say("   cox ns/(it*n*p^2) =", per_cox[s])
        _say_int("   weibull steps =", wb_it)
        _say("   weibull ns/(step*n) =", per_wb[s])
        _say_int("   lognormal iterations =", ln_it)
        _say("   lognormal ns/(it*n) =", per_ln[s])
    failures += _gate("cox ns/(it*n*p^2) over 16x n", _ratio(per_cox[2], per_cox[0]), 3.0)
    failures += _gate("weibull ns/(step*n) over 16x n", _ratio(per_wb[2], per_wb[0]), 3.0)
    failures += _gate("lognormal ns/(it*n) over 16x n", _ratio(per_ln[2], per_ln[0]), 3.0)
    return failures


def _bench_cif() -> Int:
    print("-- cif_fit: ns per (cause x event time) cell --")
    var failures = 0
    var sizes = List[Int]()
    sizes.append(1024)
    sizes.append(4096)
    sizes.append(16384)
    var per_cell = List[Float64]()
    for s in range(len(sizes)):
        var n = sizes[s]
        var t = _times(n, 1.0, 1)
        var c = _causes(n, 3)
        var cells = _cif_cells(t, c)
        var best = _t_cif(t, c)
        if cells < 0 or best < 0.0:
            failures += 1
            print("   FAIL the incidence fit was refused")
        per_cell.append(_ratio(best, Float64(cells)))
        _say_int("n =", n)
        _say_int("   cells =", cells)
        _say("   ns/cell =", per_cell[s])
    # The per-cause placement is O(n log k), so ns/cell carries a log factor: 16x in n predicts
    # about 1.3x. The 4.0 ceiling fails the O(n * k) linear scan this deliberately avoids.
    failures += _gate("ns/cell over 16x n", _ratio(per_cell[2], per_cell[0]), 4.0)
    return failures


def main() raises:
    print("== survival_analysis: shape gates, no absolute time is gated ==")
    var failures = 0
    failures += _bench_curves()
    failures += _bench_smoothed()
    failures += _bench_lookup()
    failures += _bench_fits()
    failures += _bench_cif()
    print("== done ==")
    if failures == 0:
        print("BENCH_GATE survival_analysis PASS")
    else:
        print("BENCH_GATE survival_analysis FAIL " + String(failures))
