"""
bench_vs_torch_attention.mojo — `attnk` against `torch.nn.functional.scaled_dot_product_attention`.

Why this file has a stdin protocol
-----------------------------------
The competitor is PyTorch 2.13's fused CPU kernel, `aten::_scaled_dot_product_flash_attention_for_cpu`
— confirmed by profiler op-name inspection, for float32 AND float64, with and without GQA. It is NOT
the `math` fallback, which is 3.1-3.7x slower and would inflate any claim made against it by that
factor. It lives in a different process from us, and this host is shared with other agents' benchmark
work: sampled load average while this file was written was 17-30 on 16 cores. A one-then-the-other
comparison on a loaded machine measures the load, not the kernels. So the arms ALTERNATE inside one
wall-clock window: `bench_vs_torch_attention_driver.py` holds this process open with `SERVE` and sends
one `REP` at a time, timing its own `F.scaled_dot_product_attention` call between ours, flipping which
arm leads every round.

Inputs are generated from `splitmix64(index)` on BOTH sides, so the driver can dump our Q, K and V and
assert `np.array_equal` against its own — bit-identical operands, not merely the same distribution.
`z >> 40` is a 24-bit integer and 2^24 is a power of two, so the scale is exact and every element is
representable in Float64 with no rounding on either side. The values are then scaled by sqrt(12) to
unit variance, which puts the logits at std ~1.0 after the 1/sqrt(d) softmax scale — the regime a real
model runs in. Leaving them at uniform[-0.5, 0.5) would give logits of std 0.08, a nearly uniform
softmax, and a stability test that cannot fail no matter what the kernel does.

What is timed, and what is not dropped
---------------------------------------
Both kernels allocate their own output on every call and that stays inside the timed region, because
PyTorch also allocates its output on every call. Q, K and V are pre-built on both sides before any
timer starts, and the driver states that. The tiled kernel's per-worker scratch — score tile,
accumulator, running max and normalizer — is allocated INSIDE the timed region too: it is a real cost
of every call and PyTorch's fused kernel pays the equivalent.

Two of our kernels run, and only one of them is a competitor
-------------------------------------------------------------
`TILED` is the product kernel. `DIRECT` is the materialized-score-matrix kernel that exists so the
memory claim is a measurement rather than an assertion — it is OUR OWN earlier shape, and a
tiled-vs-direct ratio is a self-comparison, which is exactly what this page is replacing. It is
reported as the memory arm only. `UNSTABLE` is never timed; it is run once at an amplified logit scale
to show it producing NaN where both real kernels are exact.

Self mode (no argv) is the cold/warm/hot arm
--------------------------------------------
A cold reading is the first call in a fresh process and cannot be taken twice, so self mode times
exactly one shape and prints one COLD_WARM_HOT line. Run it under `benchmarks/cold_start_harness.py
-K <k>` for K independent cold readings.

Usage:
  mojo run -I../mojo/engine bench_vs_torch_attention.mojo         # self: cold/warm/hot
  mojo run -I../mojo/engine bench_vs_torch_attention.mojo SERVE   # driven by the Python driver
"""

from std.math import sqrt
from std.os import getenv
from std.sys import argv
from std.sys import info
from std.sys.info import simd_width_of
from std.time import perf_counter_ns

from attnk.contract import (
    ATTN_OK,
    attn_backend_name,
    attn_status_name,
    attn_ws_bytes_direct,
    attn_ws_bytes_tiled,
)
from attnk.tiled import (
    BC_DEFAULT,
    BR_DEFAULT,
    EXP_OVERFLOW_ARG,
    attn_flop_count,
    attn_forward_direct,
    attn_forward_tiled,
    attn_forward_unstable,
    attn_reference_delta,
)

comptime W: Int = simd_width_of[DType.float64]()

comptime HOT_REPS: Int = 5
"""Hot is min-of-N. Contention can only ever make a reading slower, so the minimum is the least
contaminated statistic available on a loaded host — and the spread across those N is the evidence for
whether the minimum can be trusted at all."""

comptime MAX_SPREAD: Float64 = 2.0
"""Worst hot rep over best hot rep. Past 2x the process was descheduled mid-kernel and the number is
about the scheduler, not the kernel."""

comptime UNIT_VAR: Float64 = 3.4641016151377544
"""sqrt(12). uniform[-0.5, 0.5) has variance 1/12; this scales it to 1.0. Applied identically on the
NumPy side, and exact in binary floating point only to the extent sqrt(12) is — so the driver
multiplies by the SAME Float64 constant rather than by its own sqrt(12), and the operands stay
bit-identical."""


fn _splitmix(i: UInt64) -> Float64:
    """splitmix64 of an index, mapped to [-0.5, 0.5) with no rounding, then scaled to unit variance.

    Indexing by position rather than iterating a stream is deliberate: it is vectorizable on the NumPy
    side and order-free on ours, so the two cannot drift.
    """
    var z = i + 0x9E3779B97F4A7C15
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB
    z = z ^ (z >> 31)
    return (Float64(Int(z >> 40)) / 16777216.0 - 0.5) * UNIT_VAR


fn _fill(count: Int, salt: UInt64) -> List[Float64]:
    var out = List[Float64](capacity=count if count > 0 else 1)
    for i in range(count):
        out.append(_splitmix(UInt64(i) + salt))
    return out^


fn _fill_amplified(count: Int, salt: UInt64, amp: Float64) -> List[Float64]:
    """Same stream, scaled. Used only to drive the logits past `exp`'s overflow point."""
    var out = List[Float64](capacity=count if count > 0 else 1)
    for i in range(count):
        out.append(_splitmix(UInt64(i) + salt) * amp)
    return out^


fn _dump(path: String, data: List[Float64], count: Int) -> Int:
    """Write `count` Float64 little-endian to `path`. Returns bytes written, or -1."""
    if count <= 0 or count > len(data):
        return -1
    try:
        with open(path, "w") as f:
            f.write_bytes(
                Span(ptr=data.unsafe_ptr().bitcast[UInt8](), length=count * 8)
            )
        return count * 8
    except:
        return -1


fn _env_int(name: String, fallback: Int) -> Int:
    var raw = getenv(name)
    if raw.byte_length() == 0:
        return fallback
    try:
        var v = Int(raw)
        return v if v > 0 else fallback
    except:
        return fallback


fn _gflops(flops: Float64, ns: Float64) -> Float64:
    if ns <= 0.0:
        return 0.0
    return flops / ns


fn _self_mode() raises:
    """Cold / warm / hot for one shape, plus the tiled-vs-direct correctness delta."""
    var b = _env_int("ATTN_BENCH_B", 1)
    var hq = _env_int("ATTN_BENCH_HQ", 8)
    var hkv = _env_int("ATTN_BENCH_HKV", 2)
    var s = _env_int("ATTN_BENCH_S", 1024)
    var d = _env_int("ATTN_BENCH_D", 64)
    var workers = _env_int("ATTN_BENCH_WORKERS", 0)
    var causal = _env_int("ATTN_BENCH_CAUSAL", 0) == 1
    var kernel = getenv("ATTN_BENCH_KERNEL")
    var use_direct = kernel == "DIRECT"

    var cores = info.num_physical_cores()
    print(
        "bench_vs_torch_attention SELF  b =", b, " h_q =", hq, " h_kv =", hkv,
        " s =", s, " d =", d, " causal =", causal,
        " f64 SIMD lanes =", W, " physical cores =", cores,
    )

    var q = _fill(b * hq * s * d, 0)
    var k = _fill(b * hkv * s * d, 111_000_000)
    var v = _fill(b * hkv * s * d, 222_000_000)
    var scale = 1.0 / sqrt(Float64(d))

    # Correctness FIRST, before any timing. A timing without a correctness number is not publishable.
    var small = 256 if s > 256 else s
    var qs = _fill(b * hq * small * d, 0)
    var ks = _fill(b * hkv * small * d, 111_000_000)
    var vs = _fill(b * hkv * small * d, 222_000_000)
    var dl = attn_reference_delta(
        qs, ks, vs, b, hq, hkv, small, small, d, scale, causal
    )
    print(
        "DELTA_TILED_VS_DIRECT s =", small,
        " status =", attn_status_name(dl.status),
        " max_abs =", dl.max_abs_delta,
        " max_rel =", dl.max_rel_delta,
        " tol_at_max =", dl.tolerance_at_max,
        " within =", dl.within_tolerance,
        " n =", dl.n_compared,
    )
    if dl.status != ATTN_OK or not dl.within_tolerance:
        print("BENCH_GATE attn_self_correctness FAIL 1")
        print("INVALID correctness failed; no timing reported")
        return

    var cold_ns = 0.0
    var warm_ns = 0.0
    var best = 0.0
    var worst = 0.0
    var backend = 0
    var ws = 0.0
    var nw = 0
    var flops = 0.0
    var status = ATTN_OK

    for rep in range(HOT_REPS + 2):
        var t0 = perf_counter_ns()
        var r = (
            attn_forward_direct(
                q, k, v, b, hq, hkv, s, s, d, scale, causal, workers
            )
            if use_direct
            else attn_forward_tiled(
                q, k, v, b, hq, hkv, s, s, d, scale, causal,
                BR_DEFAULT, BC_DEFAULT, workers,
            )
        )
        var t1 = perf_counter_ns()
        var ns = Float64(t1 - t0)
        status = r.status
        backend = r.backend_used
        ws = r.working_set_bytes
        nw = r.n_workers
        flops = r.flop_count
        # Keep one element live so the whole call cannot be optimized away.
        if len(r.out) > 0 and r.out[0] == 1.0e308:
            print("unreachable")
        if rep == 0:
            cold_ns = ns
        elif rep == 1:
            warm_ns = ns
        else:
            if best == 0.0 or ns < best:
                best = ns
            if ns > worst:
                worst = ns

    if status != ATTN_OK:
        print("BENCH_GATE attn_self FAIL 1")
        print("INVALID status", attn_status_name(status), "; no timing reported")
        return

    var spread = worst / best if best > 0.0 else 0.0
    var failures = 0
    if best > warm_ns:
        failures += 1
    if spread > MAX_SPREAD:
        failures += 1

    # Machine-readable triple, in the exact grammar `cold_start_harness.py` parses:
    # COLD_WARM_HOT <label> <cold> <warm> <hot> <unit>. The label carries the kernel, the shape,
    # the worker count and the dtype, because a triple whose row cannot be identified later is a
    # number without an experiment attached to it.
    print(
        "COLD_WARM_HOT",
        attn_backend_name(backend) + "/s" + String(s) + "/w" + String(nw) + "/f64",
        cold_ns / 1.0e6, warm_ns / 1.0e6, best / 1.0e6, "ms",
    )
    print(
        "detail kernel =", attn_backend_name(backend),
        " s =", s, " workers =", nw, " dtype = float64",
        " hot_spread =", spread,
        " ws_bytes =", ws,
        " gflops =", _gflops(flops, best),
    )
    if failures == 0:
        print("BENCH_GATE attn_self PASS 0")
    else:
        print("BENCH_GATE attn_self FAIL", failures)
        print("INVALID hot>warm or spread>", MAX_SPREAD, "; no ratio reported")


fn _serve() raises:
    """One command per line on stdin, one reply per line on stdout.

    SHAPE b hq hkv s d causal   rebuild Q/K/V for a shape; replies `SHAPE ok <lenq> <lenk> <lenv>`
    DUMPQ|DUMPK|DUMPV path      write the operand, so the driver can prove the inputs match
    DUMPO path                  write the output of the last REP
    REP TILED|DIRECT workers    one timed forward; replies
                                `REP <ns> <backend> <status> <ws_bytes> <workers> <maxlogit>`
    DELTA                       tiled vs direct; replies `DELTA <status> <abs> <rel> <tol> <within> <n>`
    UNSTABLE amp                run the unstable kernel with Q scaled by `amp`; replies
                                `UNSTABLE <status> <maxlogit> <first_out> <stable_status> <stable_out>`
    QUIT
    """
    var b = 1
    var hq = 8
    var hkv = 2
    var s = 128
    var d = 64
    var causal = False
    var q = _fill(b * hq * s * d, 0)
    var k = _fill(b * hkv * s * d, 111_000_000)
    var v = _fill(b * hkv * s * d, 222_000_000)
    var out = List[Float64]()
    var scale = 1.0 / sqrt(Float64(d))

    print("READY", info.num_physical_cores(), W)

    while True:
        var line: String
        try:
            line = input()
        except:
            break
        if line.byte_length() == 0:
            continue
        var parts = line.split(" ")
        var cmd = String(parts[0])

        if cmd == "QUIT":
            break
        elif cmd == "SHAPE":
            b = Int(parts[1])
            hq = Int(parts[2])
            hkv = Int(parts[3])
            s = Int(parts[4])
            d = Int(parts[5])
            causal = String(parts[6]) == "1"
            q = _fill(b * hq * s * d, 0)
            k = _fill(b * hkv * s * d, 111_000_000)
            v = _fill(b * hkv * s * d, 222_000_000)
            scale = 1.0 / sqrt(Float64(d))
            print("SHAPE ok", len(q), len(k), len(v))
        elif cmd == "DUMPQ":
            print("DUMPQ", _dump(String(parts[1]), q, len(q)))
        elif cmd == "DUMPK":
            print("DUMPK", _dump(String(parts[1]), k, len(k)))
        elif cmd == "DUMPV":
            print("DUMPV", _dump(String(parts[1]), v, len(v)))
        elif cmd == "DUMPO":
            print("DUMPO", _dump(String(parts[1]), out, len(out)))
        elif cmd == "REP":
            var which = String(parts[1])
            var nw_req = Int(parts[2])
            var t0 = perf_counter_ns()
            var r = (
                attn_forward_direct(
                    q, k, v, b, hq, hkv, s, s, d, scale, causal, nw_req
                )
                if which == "DIRECT"
                else attn_forward_tiled(
                    q, k, v, b, hq, hkv, s, s, d, scale, causal,
                    BR_DEFAULT, BC_DEFAULT, nw_req,
                )
            )
            var t1 = perf_counter_ns()
            # After the clock has stopped. A copy inside the timed region would charge our arm for
            # a benchmark artifact PyTorch does not pay.
            out = r.out.copy()
            print(
                "REP", t1 - t0, r.backend_used, r.status,
                r.working_set_bytes, r.n_workers, r.max_abs_logit,
            )
        elif cmd == "DELTA":
            var dl = attn_reference_delta(
                q, k, v, b, hq, hkv, s, s, d, scale, causal
            )
            print(
                "DELTA", dl.status, dl.max_abs_delta, dl.max_rel_delta,
                dl.tolerance_at_max, 1 if dl.within_tolerance else 0,
                dl.n_compared,
            )
        elif cmd == "UNSTABLE":
            # Amplify Q only. The logits scale linearly in |Q|, so this walks the input toward
            # exp()'s overflow point without changing anything else about the problem.
            var amp = Float64(Int(parts[1]))
            var qa = _fill_amplified(b * hq * s * d, 0, amp)
            var ru = attn_forward_unstable(
                qa, k, v, b, hq, hkv, s, s, d, scale, causal, 0
            )
            var rs = attn_forward_tiled(
                qa, k, v, b, hq, hkv, s, s, d, scale, causal,
                BR_DEFAULT, BC_DEFAULT, 0,
            )
            var u0 = ru.out[0] if len(ru.out) > 0 else 0.0
            var s0 = rs.out[0] if len(rs.out) > 0 else 0.0
            print(
                "UNSTABLE", ru.status, ru.max_abs_logit, u0, rs.status, s0,
                EXP_OVERFLOW_ARG,
            )
        elif cmd == "WS":
            # Analytic intermediate footprint for the current shape, both kernels.
            print(
                "WS", attn_ws_bytes_tiled(BR_DEFAULT, BC_DEFAULT, d),
                attn_ws_bytes_direct(s, s, d),
                attn_flop_count(b, hq, s, s, d, causal),
            )
        else:
            print("ERR unknown", cmd)


fn main() raises:
    var args = argv()
    if len(args) > 1 and String(args[1]) == "SERVE":
        _serve()
    else:
        _self_mode()
