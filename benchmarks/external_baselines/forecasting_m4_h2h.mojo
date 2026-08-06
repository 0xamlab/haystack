"""Algenta arm of the M4 joint-axis latency measurement.

Times the SHIPPED fitted kernels (`forecasting.fitted.holt_fitted`, `damped_fitted`,
`ets_aaa_fitted`) on exactly the inputs the accuracy run fed them: Holt/Damped on the
deseasonalised series, ETS(A,A,A) on the raw series with period m.

IN-PROCESS. grep this file for `dispatch_runtime_library`, `library_execute`, `json_parse`
-> 0 occurrences. TOTAL DISPATCH COUNT FOR THE WHOLE WORKLOAD: 0. One in-process loop over
series; no per-item RPC, no serialisation, no daemon on this path.

The timed region is fit + forecast + store-into-a-preallocated-buffer, which is what any
caller pays. Reading the data off disk, slicing it into per-series lists, allocating the
output buffer and writing the buffer to disk are all OUTSIDE it and reported separately.

argv: <dir> <freq> <m> <h> <n> <mode> <nsample> <reps> <workers> [methods] [out_prefix]
  mode    = sample | full
  nsample = series in the deterministic stride sample (mode=sample); full uses all n
  reps    = in-process repetitions; rep 0 = cold, rep 1 = warm, min(rep 2..) = hot.
            A cold reading can only be taken once per process, so the cold tier comes
            from K separate process launches, never from an in-process repeat.
  workers = 1 -> serial loop;  >1 -> std.algorithm.parallelize over series
  methods = comma list from Holt,Damped,ETSAAA
  out_prefix = if given, the last rep's forecasts are written to
               <out_prefix>_<freq>_<method>.f64 AFTER the timer stops
"""
from sys import argv
from std.time import perf_counter_ns
from std.algorithm import parallelize
from std.memory import Span

from forecasting.fitted import damped_fitted, ets_aaa_fitted, holt_fitted


def read_f64(path: String) raises -> List[Float64]:
    var f = open(path, "r")
    var b = f.read_bytes()
    f.close()
    var n = len(b) // 8
    var p = b.unsafe_ptr().bitcast[Float64]()
    var out = List[Float64](capacity=n)
    for i in range(n):
        out.append(p[i])
    return out^


def read_i64(path: String) raises -> List[Int]:
    var f = open(path, "r")
    var b = f.read_bytes()
    f.close()
    var n = len(b) // 8
    var p = b.unsafe_ptr().bitcast[Int64]()
    var out = List[Int](capacity=n)
    for i in range(n):
        out.append(Int(p[i]))
    return out^


def write_f64(path: String, mut v: List[Float64]) raises:
    var w = open(path, "w")
    var bp = v.unsafe_ptr().bitcast[UInt8]()
    w.write_bytes(Span[UInt8, origin_of(v)](ptr=bp, length=len(v) * 8))
    w.close()


struct Bundle(Movable):
    var m: Int
    var h: Int
    var raw: List[List[Float64]]
    var des: List[List[Float64]]

    def __init__(
        out self,
        m: Int,
        h: Int,
        var raw: List[List[Float64]],
        var des: List[List[Float64]],
    ):
        self.m = m
        self.h = h
        self.raw = raw^
        self.des = des^


def one_series(ref b: Bundle, i: Int, method: Int, op: UnsafePointer[Float64, origin=MutAnyOrigin]) -> Int:
    """One shipped-kernel call, result stored into the preallocated output slot.

    Returns 1 when the kernel produced a forecast. NaN-fills a refused series so the
    scorer downstream can count it rather than average over it.
    """
    var h = b.h
    var base = i * h
    if method == 2:
        var f = ets_aaa_fitted(b.raw[i], b.m, h)
        if f.has_forecast:
            for k in range(h):
                op[base + k] = f.values[k]
            return 1
    elif method == 0:
        var f = holt_fitted(b.des[i], h)
        if f.has_forecast:
            for k in range(h):
                op[base + k] = f.values[k]
            return 1
    else:
        var f = damped_fitted(b.des[i], h)
        if f.has_forecast:
            for k in range(h):
                op[base + k] = f.values[k]
            return 1
    for k in range(h):
        op[base + k] = FloatLiteral.nan
    return 0


def pass_serial(ref b: Bundle, method: Int, op: UnsafePointer[Float64, origin=MutAnyOrigin]) -> Int:
    var ok = 0
    for i in range(len(b.raw)):
        ok += one_series(b, i, method, op)
    return ok


def pass_parallel(
    ref b: Bundle, method: Int, op: UnsafePointer[Float64, origin=MutAnyOrigin], workers: Int
) -> Int:
    var n = len(b.raw)
    var part = List[Int](capacity=workers)
    for _ in range(workers):
        part.append(0)
    var pp = part.unsafe_ptr()

    @parameter
    def worker(w: Int):
        var lo = (n * w) // workers
        var hi = (n * (w + 1)) // workers
        var ok = 0
        for i in range(lo, hi):
            ok += one_series(b, i, method, op)
        pp[w] = ok

    parallelize[worker](workers, workers)
    var tot = 0
    for w in range(workers):
        tot += part[w]
    return tot


def main() raises:
    var a = argv()
    var d = String(a[1])
    var freq = String(a[2])
    var m = Int(atol(a[3]))
    var h = Int(atol(a[4]))
    var nser = Int(atol(a[5]))
    var mode = String(a[6])
    var nsample = Int(atol(a[7]))
    var reps = Int(atol(a[8]))
    var workers = Int(atol(a[9]))
    var want = String("Holt,Damped,ETSAAA")
    if len(a) > 10:
        want = String(a[10])
    var out_prefix = String("")
    if len(a) > 11:
        out_prefix = String(a[11])

    var t0 = perf_counter_ns()
    var lens = read_i64(d + "/" + freq + "_lens.i64")
    if len(lens) != nser:
        print("BAD lens", len(lens))
        return
    var raw_flat = read_f64(d + "/" + freq + "_raw.f64")
    var des_flat = read_f64(d + "/" + freq + "_des.f64")

    # Deterministic stride sample so every part of the corpus is represented.
    var idx = List[Int]()
    if mode == "full":
        for s in range(nser):
            idx.append(s)
    else:
        var stride = nser // nsample
        if stride < 1:
            stride = 1
        var s = 0
        while s < nser and len(idx) < nsample:
            idx.append(s)
            s += stride

    var offs = List[Int](capacity=nser)
    var off = 0
    for s in range(nser):
        offs.append(off)
        off += lens[s]

    var raw = List[List[Float64]](capacity=len(idx))
    var des = List[List[Float64]](capacity=len(idx))
    for j in range(len(idx)):
        var s = idx[j]
        var n = lens[s]
        var o = offs[s]
        var yr = List[Float64](capacity=n)
        var yd = List[Float64](capacity=n)
        for t in range(n):
            yr.append(raw_flat[o + t])
            yd.append(des_flat[o + t])
        raw.append(yr^)
        des.append(yd^)
    var b = Bundle(m, h, raw^, des^)
    var ns = len(b.raw)
    var buf = List[Float64](capacity=ns * h)
    for _ in range(ns * h):
        buf.append(0.0)
    var bp = buf.unsafe_ptr()
    var t1 = perf_counter_ns()
    print(
        "COLD_WARM_HOT "
        + freq
        + "_load unresolved unresolved unresolved ms load_ms="
        + String(Float64(t1 - t0) / 1.0e6)
    )

    var names = List[String]()
    names.append(String("Holt"))
    names.append(String("Damped"))
    names.append(String("ETSAAA"))
    for method in range(3):
        if want.find(names[method]) < 0:
            continue
        var rr = List[Float64](capacity=reps)
        var ok = 0
        for _ in range(reps):
            var s0 = perf_counter_ns()
            if workers > 1:
                ok = pass_parallel(b, method, bp, workers)
            else:
                ok = pass_serial(b, method, bp)
            var s1 = perf_counter_ns()
            rr.append(Float64(s1 - s0) / 1.0e6)
        var cold = rr[0]
        var warm = cold
        var hot = cold
        var hmax = cold
        if reps > 1:
            warm = rr[1]
            hot = rr[1]
            hmax = rr[1]
        if reps > 2:
            hot = rr[2]
            hmax = rr[2]
            for i in range(3, reps):
                if rr[i] < hot:
                    hot = rr[i]
                if rr[i] > hmax:
                    hmax = rr[i]
        var label = freq + "_" + names[method]
        print(
            "COLD_WARM_HOT "
            + label
            + " "
            + String(cold)
            + " "
            + String(warm)
            + " "
            + String(hot)
            + " ms"
        )
        print(
            "  ROW "
            + label
            + " series="
            + String(ns)
            + " workers="
            + String(workers)
            + " reps="
            + String(reps)
            + " ok="
            + String(ok)
            + " cold_per_series_ms="
            + String(cold / Float64(ns))
            + " hot_per_series_ms="
            + String(hot / Float64(ns))
            + " hot_disp="
            + String(hmax / hot)
        )
        if len(out_prefix) > 0:
            write_f64(out_prefix + "_" + label + ".f64", buf)
    print("ARM_DONE algenta " + freq + " " + mode)
