"""
bench_vs_torch_feed_forward.mojo — the Mojo half of the gated feed-forward head-to-head.

What this measures, and what the other half is
------------------------------------------------
`mlpk.gated_ffn`'s four gated activations (SwiGLU, GEGLU-tanh, GEGLU-tanh-fast, GEGLU-erf) and the full
SwiGLU block,
against `torch.nn.functional`'s composition of the same expressions. The torch half lives in
`bench_vs_torch_feed_forward_torch.py`; the two are alternated round by round by
`bench_vs_torch_feed_forward_driver.py`, which also records the 1/5/15 load average around every
round. Running this file alone gives you our numbers and no ratio.

Inputs are read, not generated
--------------------------------
The driver writes `gate_<n>.f64` and `up_<n>.f64` once, as raw little-endian float64, and both
implementations read the same bytes. Generating "the same" inputs twice from a formula would put a
last-ulp difference between the two sides and charge it to the kernel as a correctness error. Input
load happens before the timer starts on both sides: both get pre-built buffers, and the marshalling
cost is reported as its own line rather than folded into either kernel.

Cold, warm, hot — and what cold actually costs
------------------------------------------------
`cold` is the first call in this process, `warm` the second, `hot` the best of `reps` more with the
median and p90 alongside. Cold is once per process by construction, so the driver relaunches this
binary K times and takes the median of the cold column; K is printed on the page. Reporting only hot
hides the dispatch and first-touch cost that a real caller pays once, and for torch that cost is much
larger than ours.

The gate
--------
Every measurement prints `BENCH_GATE <name> PASS|FAIL <n>`. FAIL when hot > warm (the machine moved
under us), or p90/p50 > 1.25 (dispersion too wide to quote a median). A FAILing measurement prints
INVALID and no derived figure; the driver refuses to compute a ratio against it.

Usage:
    bench_vs_torch_feed_forward <io_dir> <n> <reps> <workers> <dump_stride> [block]
"""

from std.sys import argv, info
from std.time import perf_counter_ns

from mlpk.contract import MLP_OK, mlp_status_name
from mlpk.gated_ffn import (
    BlockResult,
    GateResult,
    gate_bytes_moved,
    geglu_erf_gate,
    geglu_tanh_fast_gate,
    geglu_tanh_gate,
    swiglu_ffn_block,
    swiglu_gate,
)

comptime GATE_DISPERSION_MAX: Float64 = 1.25


def _sorted_copy(xs: List[Float64]) -> List[Float64]:
    """Insertion sort of a copy. The sample is `reps` long (tens), so an O(r^2) sort is free."""
    var out = List[Float64](capacity=len(xs))
    for i in range(len(xs)):
        out.append(xs[i])
    for i in range(1, len(out)):
        var v = out[i]
        var j = i - 1
        while j >= 0 and out[j] > v:
            out[j + 1] = out[j]
            j -= 1
        out[j + 1] = v
    return out^


def _quantile(sorted_xs: List[Float64], q: Float64) -> Float64:
    if len(sorted_xs) == 0:
        return 0.0
    var idx = Int(q * Float64(len(sorted_xs) - 1) + 0.5)
    if idx < 0:
        idx = 0
    if idx >= len(sorted_xs):
        idx = len(sorted_xs) - 1
    return sorted_xs[idx]


def _read_f64(path: String) raises -> List[Float64]:
    var raw: List[UInt8]
    with open(path, "r") as f:
        raw = f.read_bytes()
    var n = len(raw) // 8
    var out = List[Float64](unsafe_uninit_length=n)
    var src = raw.unsafe_ptr().bitcast[Float64]()
    var dst = out.unsafe_ptr()
    for i in range(n):
        dst[i] = src[i]
    return out^


def _write_f64_strided(path: String, xs: List[Float64], n: Int, stride: Int) raises:
    """Dump every `stride`-th element for the correctness cross-check.

    Full dumps at n = 16.7M are 134 MB a piece; a fixed stride keeps the exchange bounded while still
    comparing real elements rather than a scalar summary. The Python half reads the same stride.
    """
    var count = (n + stride - 1) // stride
    var buf = List[Float64](unsafe_uninit_length=count)
    var bp = buf.unsafe_ptr()
    var j = 0
    var i = 0
    while i < n:
        bp[j] = xs[i]
        j += 1
        i += stride
    var raw = buf.unsafe_ptr().bitcast[UInt8]()
    with open(path, "w") as f:
        f.write_bytes(Span[Byte, origin_of(buf)](ptr=raw, length=count * 8))


def _gate_line(name: String, hot_min: Float64, warm: Float64, p50: Float64, p90: Float64) -> Bool:
    var ok = True
    if hot_min > warm:
        ok = False
    var disp = p90 / p50 if p50 > 0.0 else 1.0e9
    if disp > GATE_DISPERSION_MAX:
        ok = False
    var verdict = "PASS" if ok else "FAIL"
    print("BENCH_GATE", name, verdict, String(disp))
    if not ok:
        print("INVALID", name, "hot_ms=" + String(hot_min / 1.0e6), "warm_ms=" + String(warm / 1.0e6), "p90/p50=" + String(disp), "-- no ratio emitted")
    return ok


def _emit(
    variant: String,
    n: Int,
    workers_req: Int,
    workers_used: Int,
    backend: Int,
    cold_ns: Float64,
    warm_ns: Float64,
    hot: List[Float64],
    checksum: Float64,
    reps: Int,
) -> Bool:
    var s = _sorted_copy(hot)
    var hot_min = s[0]
    var p50 = _quantile(s, 0.5)
    var p90 = _quantile(s, 0.9)
    var name = "mojo_" + variant + "_n" + String(n) + "_w" + String(workers_used)
    var ok = _gate_line(name, hot_min, warm_ns, p50, p90)
    var bytes = gate_bytes_moved(n)
    var gbs = bytes / hot_min if hot_min > 0.0 else 0.0
    print(
        "RESULT",
        "impl=mojo",
        "variant=" + variant,
        "dtype=float64",
        "device=cpu",
        "n=" + String(n),
        "workers_requested=" + String(workers_req),
        "workers_used=" + String(workers_used),
        "backend=" + String(backend),
        "reps=" + String(reps),
        "cold_ms=" + String(cold_ns / 1.0e6),
        "warm_ms=" + String(warm_ns / 1.0e6),
        "hot_min_ms=" + String(hot_min / 1.0e6),
        "hot_p50_ms=" + String(p50 / 1.0e6),
        "hot_p90_ms=" + String(p90 / 1.0e6),
        "bytes_moved=" + String(bytes),
        "gb_per_s=" + String(gbs if ok else 0.0),
        "checksum=" + String(checksum),
        "gate=" + ("PASS" if ok else "FAIL"),
    )
    return ok


def _checksum(xs: List[Float64], n: Int) -> Float64:
    """Cheap whole-array fingerprint, so a dump-free run still detects a silently wrong kernel."""
    var acc = 0.0
    for i in range(n):
        acc += xs[i]
    return acc


def main() raises:
    var av = argv()
    if len(av) < 6:
        print("usage: bench_vs_torch_feed_forward <io_dir> <n> <reps> <workers> <dump_stride> [block]")
        return
    var io_dir = String(av[1])
    var n = Int(String(av[2]))
    var reps = Int(String(av[3]))
    var workers = Int(String(av[4]))
    var stride = Int(String(av[5]))
    var do_block = len(av) > 6 and String(av[6]) == "block"

    print("HOST", "physical_cores=" + String(info.num_physical_cores()), "logical_cores=" + String(info.num_logical_cores()))

    var t_load0 = perf_counter_ns()
    var gate = _read_f64(io_dir + "/gate_" + String(n) + ".f64")
    var up = _read_f64(io_dir + "/up_" + String(n) + ".f64")
    var t_load1 = perf_counter_ns()
    print("SETUP", "impl=mojo", "n=" + String(n), "input_load_ms=" + String(Float64(t_load1 - t_load0) / 1.0e6))
    if len(gate) < n or len(up) < n:
        print("ERROR input buffers shorter than n:", len(gate), len(up), n)
        return

    for vi in range(4):
        var variant = "swiglu"
        if vi == 1:
            variant = "geglu_tanh"
        elif vi == 2:
            variant = "geglu_tanh_fast"
        elif vi == 3:
            variant = "geglu_erf" 

        # cold: the first call to THIS kernel in THIS process.
        var c0 = perf_counter_ns()
        var cold_r: GateResult
        if vi == 0:
            cold_r = swiglu_gate(gate, up, n, workers)
        elif vi == 1:
            cold_r = geglu_tanh_gate(gate, up, n, workers)
        elif vi == 2:
            cold_r = geglu_tanh_fast_gate(gate, up, n, workers)
        else:
            cold_r = geglu_erf_gate(gate, up, n, workers)
        var c1 = perf_counter_ns()
        if cold_r.status != MLP_OK:
            print("ERROR", variant, mlp_status_name(cold_r.status))
            return
        var cold_ns = Float64(c1 - c0)

        # warm: the second call.
        var w0 = perf_counter_ns()
        var warm_r: GateResult
        if vi == 0:
            warm_r = swiglu_gate(gate, up, n, workers)
        elif vi == 1:
            warm_r = geglu_tanh_gate(gate, up, n, workers)
        elif vi == 2:
            warm_r = geglu_tanh_fast_gate(gate, up, n, workers)
        else:
            warm_r = geglu_erf_gate(gate, up, n, workers)
        var w1 = perf_counter_ns()
        var warm_ns = Float64(w1 - w0)

        var hot = List[Float64](capacity=reps)
        var last_sum = 0.0
        var used = warm_r.workers_used
        var backend = warm_r.backend_used
        for rep in range(reps):
            var h0 = perf_counter_ns()
            var r: GateResult
            if vi == 0:
                r = swiglu_gate(gate, up, n, workers)
            elif vi == 1:
                r = geglu_tanh_gate(gate, up, n, workers)
            elif vi == 2:
                r = geglu_tanh_fast_gate(gate, up, n, workers)
            else:
                r = geglu_erf_gate(gate, up, n, workers)
            var h1 = perf_counter_ns()
            hot.append(Float64(h1 - h0))
            # Read one element so the whole call cannot be optimised away, and keep the last output
            # for the dump. Costs one load, outside the timed region.
            last_sum += r.out[n - 1]
            if rep == reps - 1:
                _write_f64_strided(
                    io_dir + "/mojo_" + variant + "_" + String(n) + "_w" + String(used) + ".f64",
                    r.out,
                    n,
                    stride,
                )
                last_sum = _checksum(r.out, n)
            used = r.workers_used
            backend = r.backend_used

        _ = _emit(variant, n, workers, used, backend, cold_ns, warm_ns, hot, last_sum, reps)

    if do_block:
        # Full block: three projections around the gate. tokens x d_model @ d_model x d_ff, gated,
        # then d_ff x d_model back down. Dimensions come from the io_dir's block_dims file.
        var dims = _read_f64(io_dir + "/block_dims.f64")
        var tokens = Int(dims[0])
        var d_model = Int(dims[1])
        var d_ff = Int(dims[2])
        var x = _read_f64(io_dir + "/block_x.f64")
        var wg = _read_f64(io_dir + "/block_wg.f64")
        var wu = _read_f64(io_dir + "/block_wu.f64")
        var wd = _read_f64(io_dir + "/block_wd.f64")

        var b0 = perf_counter_ns()
        var cold_b = swiglu_ffn_block(x, wg, wu, wd, tokens, d_model, d_ff)
        var b1 = perf_counter_ns()
        if cold_b.status != MLP_OK:
            print("ERROR block", mlp_status_name(cold_b.status))
            return
        var cold_block = Float64(b1 - b0)

        var bw0 = perf_counter_ns()
        var warm_b = swiglu_ffn_block(x, wg, wu, wd, tokens, d_model, d_ff)
        var bw1 = perf_counter_ns()
        var warm_block = Float64(bw1 - bw0)

        var block_reps = reps if reps < 5 else 5
        var bhot = List[Float64](capacity=block_reps)
        var bsum = 0.0
        for r in range(block_reps):
            var h0 = perf_counter_ns()
            var bb = swiglu_ffn_block(x, wg, wu, wd, tokens, d_model, d_ff)
            var h1 = perf_counter_ns()
            bhot.append(Float64(h1 - h0))
            if r == block_reps - 1:
                _write_f64_strided(io_dir + "/mojo_block.f64", bb.out, tokens * d_model, stride)
                bsum = _checksum(bb.out, tokens * d_model)

        var bs = _sorted_copy(bhot)
        var bmin = bs[0]
        var bp50 = _quantile(bs, 0.5)
        var bp90 = _quantile(bs, 0.9)
        var bok = _gate_line("mojo_block_t" + String(tokens), bmin, warm_block, bp50, bp90)
        var gflops = warm_b.flop_count / bmin if bmin > 0.0 else 0.0
        print(
            "RESULT",
            "impl=mojo",
            "variant=swiglu_block",
            "dtype=float64",
            "device=cpu",
            "tokens=" + String(tokens),
            "d_model=" + String(d_model),
            "d_ff=" + String(d_ff),
            "workers_used=" + String(warm_b.gate_workers),
            "reps=" + String(block_reps),
            "cold_ms=" + String(cold_block / 1.0e6),
            "warm_ms=" + String(warm_block / 1.0e6),
            "hot_min_ms=" + String(bmin / 1.0e6),
            "hot_p50_ms=" + String(bp50 / 1.0e6),
            "hot_p90_ms=" + String(bp90 / 1.0e6),
            "flops=" + String(warm_b.flop_count),
            "gflop_per_s=" + String(gflops if bok else 0.0),
            "checksum=" + String(bsum),
            "gate=" + ("PASS" if bok else "FAIL"),
        )
