"""
bench_vs_torch_normalization.mojo — `normk.rmsnorm` / `normk.layernorm` against PyTorch's norms.

What is on the other side of this comparison
----------------------------------------------
`torch.nn.functional.layer_norm` and `torch.nn.functional.rms_norm`, float64, on CPU. They are NOT
the same class of opponent and the driver proves which is which by reading the aten op stream out of
`torch.profiler` before it times anything:

  * LayerNorm forward is `aten::native_layer_norm` and its backward is
    `aten::native_layer_norm_backward` — genuinely fused single kernels, one pass, hand-written.
    This is the hard fight.
  * RMSNorm on CPU is `aten::_fused_rms_norm`, which despite the name decomposes on this backend
    into `pow` -> `mean` -> `add` -> `rsqrt` -> `mul` -> `mul`, each a full-tensor pass. Calling
    `torch.ops.aten._fused_rms_norm` directly gives the identical decomposition, so there is no
    fused CPU path hiding behind the functional wrapper. Beating it is beating a decomposition, and
    any row that reports it must say so — the same trap as quoting an SDPA win against the math
    fallback instead of flash.

The driver therefore also runs an `torch.compile` (inductor) RMSNorm arm, which IS fused, so the
strongest available PyTorch RMSNorm is on the record and no one has to wonder whether an easier
baseline was chosen.

There is no per-call worker override on this side of the comparison
-----------------------------------------------------------------------
`normk.rmsnorm.rmsnorm_fwd_flat` / `normk.layernorm.layernorm_fwd_flat` and their `_bwd_flat`
counterparts decide their own parallel width internally (one worker below
`normk.rmsnorm.PARALLEL_MIN_CELLS`, `num_physical_cores()` above it) and expose neither a
`requested_workers` parameter nor the width they picked. An earlier draft of this file assumed a
richer, controllable contract (explicit worker counts, a reported backend tag, a reported byte
count) against a sibling module, `normk.layers`, that was never reconciled with the shipped
`rmsnorm.mojo` / `layernorm.mojo` and does not compile. This file targets the real, shipped kernels;
`workers_used` below is INFERRED from the same threshold the kernel itself uses, not read back from
it, and is labelled as such everywhere it is printed.

Why this file has a stdin protocol
------------------------------------
The competitor lives in a different process. On a contended host a one-then-the-other comparison
measures whichever arm got the quieter window. `SERVE` holds this process open and the driver sends
one `FWD`/`BWD` at a time, timing its own PyTorch rep between ours, flipping which arm leads every
round. Same wall-clock window, same neighbours, for both.

Inputs are generated from `splitmix64(index)` on BOTH sides and this process dumps its buffers so
the driver can assert `np.array_equal` against its own generation — bit-identical operands, not
merely statistically similar ones. `z >> 40` is a 24-bit integer and 2^24 is a power of two, so the
scale is exact and every element has the same Float64 bit pattern on both sides.

What is timed, and what is NOT dropped
----------------------------------------
Our kernels allocate their outputs on every call — `y`, or `dx`/`dgamma`/`dbeta` — and that
allocation stays INSIDE the timed region, because PyTorch also allocates its output on every call.
Both sides receive PRE-BUILT inputs: our `List[Float64]` is filled before the clock starts and the
driver's tensors are allocated and touched before the clock starts.

Normalization is BANDWIDTH-bound, so GB/s against the measured 271 GB/s NT-SIMD ceiling is the unit,
not GFLOP/s. Forward moves 16 B/element (read x, write y); backward moves 24 B/element (read x, read
dy, write dx). `gamma`/`beta` and the slot accumulators are cache-resident and are excluded from the
count, matching the original measurement's convention.

Self mode is the correctness-and-cold arm
-------------------------------------------
No argv: run the kernel's own finite-difference gradient check (`rmsnorm_gradcheck_flat` /
`layernorm_gradcheck_flat`) and, for LayerNorm, the two-pass-vs-one-pass variance agreement
(`layernorm_variance_agrees_flat`), then one cold/warm/hot triple for the shape in the environment.
A cold reading is the first call in a fresh process and cannot be taken twice, so self mode times
exactly one configuration and is meant to be run under `benchmarks/cold_start_harness.py -K <k>`.

  NORM_BENCH_ROWS   default 1024      NORM_BENCH_KIND    RMS | LN     default LN
  NORM_BENCH_COLS   default 4096      NORM_BENCH_DIR     FWD | BWD    default FWD

Usage:
  mojo run -I../mojo/engine bench_vs_torch_normalization.mojo         # self: correctness + c/w/h
  mojo run -I../mojo/engine bench_vs_torch_normalization.mojo SERVE   # driven by the .py driver
"""

from std.os import getenv
from std.sys import argv
from std.sys import info
from std.sys.info import simd_width_of
from std.time import perf_counter_ns

from normk.contract import NORM_OK, norm_status_name
from normk.rmsnorm import (
    PARALLEL_MIN_CELLS,
    rmsnorm_agrees_with_frozen_flat,
    rmsnorm_bwd_flat,
    rmsnorm_fwd_flat,
    rmsnorm_gradcheck_flat,
)
from normk.layernorm import (
    layernorm_bwd_flat,
    layernorm_fwd_flat,
    layernorm_gradcheck_flat,
    layernorm_variance_agrees_flat,
)

comptime W: Int = simd_width_of[DType.float64]()

comptime HOT_REPS: Int = 7
"""Hot is min-of-N. Contention can only ever make a reading slower, so the minimum is the least
contaminated statistic available — and the spread across the N is the evidence for whether the
minimum can be trusted at all."""

comptime MAX_SPREAD: Float64 = 1.25
"""Worst hot rep over best hot rep. Tighter than the 2.0 the GEMM bench uses, because a
bandwidth-bound kernel at a fixed shape has almost no legitimate run-to-run variation: past 25% the
reading is about the scheduler, not the kernel."""

comptime GRADCHECK_STEP: Float64 = 1.0e-5
"""Central-difference step handed to `rmsnorm_gradcheck_flat` / `layernorm_gradcheck_flat`, matching
the step both kernels' own docstrings reason about."""

comptime FD_ROWS: Int = 6
comptime FD_COLS: Int = 24
"""Shape for the gradcheck ONLY, deliberately tiny and independent of `NORM_BENCH_ROWS/COLS`.
`rmsnorm_gradcheck_flat` / `layernorm_gradcheck_flat` are `O((n_rows*n_cols)^2)` -- each of their
`n_rows*n_cols` central-difference probes re-runs a full `O(n_rows*n_cols)` forward pass -- so
running them at a real timing shape (the default is 1024x4096 = 4.19M elements) does not finish in
any reasonable time. The check verifies the MATH, which does not depend on the shape; the timing
shape sweep verifies the kernel at scale."""


fn _splitmix(i: UInt64) -> Float64:
    """splitmix64 of an index, mapped to [-0.5, 0.5) with no rounding.

    The driver runs the identical recurrence in NumPy uint64 arithmetic. Indexing by position rather
    than iterating a stream is deliberate: it is vectorizable on the NumPy side and order-free on
    ours, so the two cannot drift.
    """
    var z = i + 0x9E3779B97F4A7C15
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB
    z = z ^ (z >> 31)
    return Float64(Int(z >> 40)) / 16777216.0 - 0.5


fn _fill(count: Int, salt: UInt64) -> List[Float64]:
    var out = List[Float64](capacity=count if count > 0 else 1)
    for i in range(count):
        out.append(_splitmix(UInt64(i) + salt))
    return out^


fn _fill_gamma(count: Int, salt: UInt64) -> List[Float64]:
    """gamma centred on 1.0 rather than 0.0 — a scale parameter that averages zero would make the
    normalized output a rounding-noise field and every relative error meaningless. `1.0 + s` for
    `s` in [-0.5, 0.5) is exact in Float64, so the two sides still agree bit for bit."""
    var out = List[Float64](capacity=count if count > 0 else 1)
    for i in range(count):
        out.append(1.0 + _splitmix(UInt64(i) + salt))
    return out^


fn _dump(path: String, data: List[Float64], count: Int) -> Int:
    """Write `count` Float64 little-endian to `path`. Returns bytes written, or -1."""
    if count <= 0 or count > len(data):
        return -1
    try:
        with open(path, "w") as f:
            f.write_bytes(Span(ptr=data.unsafe_ptr().bitcast[UInt8](), length=count * 8))
        return count * 8
    except:
        return -1


fn _gbs(bytes_moved: Float64, ns: Float64) -> Float64:
    """Bytes per nanosecond IS gigabytes per second (1e9 B / 1e9 ns). No unit fudge factor."""
    if ns <= 0.0:
        return 0.0
    return bytes_moved / ns


fn _env_int(name: String, fallback: Int) -> Int:
    var raw = getenv(name)
    if raw.byte_length() == 0:
        return fallback
    try:
        return Int(raw)
    except:
        return fallback


fn _env_str(name: String, fallback: String) -> String:
    var raw = getenv(name)
    return fallback if raw.byte_length() == 0 else raw


fn _workers_used_inferred(rows: Int, cols: Int) -> Int:
    """The worker count `rmsnorm_fwd_flat` / `layernorm_fwd_flat` would pick for this shape, by the
    same rule they use internally. NOT read back from the kernel — neither result struct reports it
    — so this is an inference, not a measurement, and every caller of this function is a print
    label, never a correctness decision."""
    if rows * cols < PARALLEL_MIN_CELLS or info.num_physical_cores() > rows:
        return 1
    return info.num_physical_cores()


fn _bytes_moved(rows: Int, cols: Int, is_fwd: Bool) -> Float64:
    """16 B/element forward (read x, write y), 24 B/element backward (read x, read dy, write dx).
    `gamma`/`beta` and the accumulator are cache-resident and excluded, matching the convention the
    original measurement used."""
    var per_elem = 16.0 if is_fwd else 24.0
    return per_elem * Float64(rows) * Float64(cols)


fn _self_mode() raises:
    var rows = _env_int("NORM_BENCH_ROWS", 1024)
    var cols = _env_int("NORM_BENCH_COLS", 4096)
    var kind = _env_str("NORM_BENCH_KIND", String("LN"))
    var direction = _env_str("NORM_BENCH_DIR", String("FWD"))
    var is_rms = kind == "RMS"
    var is_fwd = direction == "FWD"
    var eps = 1.0e-6 if is_rms else 1.0e-5

    print(
        "bench_vs_torch_normalization SELF  ", kind, direction, " rows =", rows, " cols =", cols,
        " f64 lanes =", W, " physical cores =", info.num_physical_cores(),
    )

    var failures = 0

    # ── correctness FIRST, before any timing — the kernel's own checks, not a hand-rolled copy ──
    # The gradcheck runs at the tiny FD_ROWS x FD_COLS shape (see its comptime docstring); the
    # agreement checks below run at the REAL timing shape, since those are only O(n_rows*n_cols).
    var x_fd = _fill(FD_ROWS * FD_COLS, 0)
    var gamma_fd = _fill_gamma(FD_COLS, 101_000_000)
    var beta_fd = _fill(FD_COLS, 202_000_000)
    # `NormAgreement` (RMS) and `LayerNormAgreement` (LN) are distinct struct types -- a ternary
    # needs one type on both arms, so the two branches are written out rather than merged.
    var gc_status = NORM_OK
    var gc_max_abs = 0.0
    var gc_tol = 0.0
    var gc_within = False
    var gc_n = 0
    if is_rms:
        var gc = rmsnorm_gradcheck_flat(x_fd, gamma_fd, FD_ROWS, FD_COLS, eps, GRADCHECK_STEP)
        gc_status = gc.status
        gc_max_abs = gc.max_abs_delta
        gc_tol = gc.tolerance_at_max
        gc_within = gc.within_tolerance
        gc_n = gc.n_compared
    else:
        var gc2 = layernorm_gradcheck_flat(
            x_fd, gamma_fd, beta_fd, FD_ROWS, FD_COLS, eps, GRADCHECK_STEP
        )
        gc_status = gc2.status
        gc_max_abs = gc2.max_abs_delta
        gc_tol = gc2.tolerance_at_max
        gc_within = gc2.within_tolerance
        gc_n = gc2.n_compared
    if gc_status != NORM_OK:
        print("  gradcheck status", norm_status_name(gc_status))
        failures += 1
    else:
        print(
            "  finite-difference gradient check (", FD_ROWS, "x", FD_COLS, ", central, step",
            GRADCHECK_STEP, "): max abs delta", gc_max_abs, " tolerance", gc_tol, " within",
            gc_within, " n", gc_n,
        )
        if not gc_within:
            print("  FINITE-DIFFERENCE CHECK FAILED")
            failures += 1

    # The agreement checks are only O(n_rows*n_cols), so they run at the real timing shape --
    # rebuilt at `rows`/`cols` rather than reusing the tiny gradcheck buffers.
    var x_agree = _fill(rows * cols, 0)
    var gamma_agree = _fill_gamma(cols, 101_000_000)
    if is_rms:
        var agree = rmsnorm_agrees_with_frozen_flat(x_agree, gamma_agree, rows, cols, eps)
        print(
            "  agreement with the frozen per-element kernel: max abs delta", agree.max_abs_delta,
            " tolerance", agree.tolerance_at_max, " within", agree.within_tolerance,
        )
        if agree.status != NORM_OK or not agree.within_tolerance:
            failures += 1
    else:
        var va = layernorm_variance_agrees_flat(x_agree, rows, cols)
        print(
            "  two-pass vs one-pass variance identity: max abs delta", va.max_abs_delta,
            " tolerance", va.tolerance_at_max, " within", va.within_tolerance,
        )
        if va.status != NORM_OK or not va.within_tolerance:
            failures += 1

    if failures > 0:
        print("BENCH_GATE normk_self FAIL " + String(failures))
        print("  INVALID -- correctness failed, no timing reported")
        return

    # ── cold / warm / hot, one configuration, one process ─────────────────────
    var x = _fill(rows * cols, 0)
    var gamma = _fill_gamma(cols, 101_000_000)
    var beta = _fill(cols, 202_000_000)
    var dy = _fill(rows * cols, 303_000_000)

    var status = NORM_OK
    # The backward arm needs a matching forward's `rstd` (and, for LayerNorm, `mean`) -- computed
    # once, outside the timed region, exactly like the driver's own GEN/FWD-then-BWD sequencing.
    var rstd_for_bwd = List[Float64]()
    var mean_for_bwd = List[Float64]()
    if not is_fwd:
        if is_rms:
            rstd_for_bwd = rmsnorm_fwd_flat(x, gamma, rows, cols, eps).rstd.copy()
        else:
            var pre = layernorm_fwd_flat(x, gamma, beta, rows, cols, eps)
            rstd_for_bwd = pre.rstd.copy()
            mean_for_bwd = pre.mean.copy()

    var t0 = perf_counter_ns()
    if is_fwd:
        if is_rms:
            var r = rmsnorm_fwd_flat(x, gamma, rows, cols, eps)
            status = r.status
        else:
            var r2 = layernorm_fwd_flat(x, gamma, beta, rows, cols, eps)
            status = r2.status
    else:
        if is_rms:
            var r = rmsnorm_bwd_flat(dy, x, gamma, rstd_for_bwd, rows, cols)
            status = r.status
        else:
            var r2 = layernorm_bwd_flat(dy, x, gamma, mean_for_bwd, rstd_for_bwd, rows, cols)
            status = r2.status
    var cold = Float64(perf_counter_ns() - t0)

    if status != NORM_OK:
        print("  status", norm_status_name(status))
        print("BENCH_GATE normk_self FAIL 1")
        return

    t0 = perf_counter_ns()
    if is_fwd:
        if is_rms:
            _ = rmsnorm_fwd_flat(x, gamma, rows, cols, eps).status
        else:
            _ = layernorm_fwd_flat(x, gamma, beta, rows, cols, eps).status
    else:
        if is_rms:
            _ = rmsnorm_bwd_flat(dy, x, gamma, rstd_for_bwd, rows, cols).status
        else:
            _ = layernorm_bwd_flat(dy, x, gamma, mean_for_bwd, rstd_for_bwd, rows, cols).status
    var warm = Float64(perf_counter_ns() - t0)

    var hot = 0.0
    var hot_worst = 0.0
    for _ in range(HOT_REPS):
        t0 = perf_counter_ns()
        if is_fwd:
            if is_rms:
                _ = rmsnorm_fwd_flat(x, gamma, rows, cols, eps).status
            else:
                _ = layernorm_fwd_flat(x, gamma, beta, rows, cols, eps).status
        else:
            if is_rms:
                _ = rmsnorm_bwd_flat(dy, x, gamma, rstd_for_bwd, rows, cols).status
            else:
                _ = layernorm_bwd_flat(dy, x, gamma, mean_for_bwd, rstd_for_bwd, rows, cols).status
        var ns = Float64(perf_counter_ns() - t0)
        if hot == 0.0 or ns < hot:
            hot = ns
        if ns > hot_worst:
            hot_worst = ns

    var spread = hot_worst / hot if hot > 0.0 else 0.0
    var ordered = hot <= warm
    var moved = _bytes_moved(rows, cols, is_fwd)
    var used_workers = _workers_used_inferred(rows, cols)

    print(
        "  workers_used (inferred, not kernel-reported)", used_workers,
        " bytes/element", moved / Float64(rows * cols),
    )
    var label = String(kind) + "_" + String(direction) + "_" + String(rows) + "x" + String(
        cols
    ) + "_w" + String(used_workers)
    print("COLD_WARM_HOT " + label, cold, warm, hot, "ns")

    if not ordered or spread > MAX_SPREAD:
        print(
            "  INVALID -- ", "hot > warm" if not ordered else "hot<=warm holds", "; spread", spread,
            "against a limit of", MAX_SPREAD, "; no GB/s reported",
        )
        print("BENCH_GATE normk_self FAIL 1")
        return

    print(
        "  cold", cold / 1.0e6, "ms  warm", warm / 1.0e6, "ms  HOT", hot / 1.0e6,
        "ms   HOT", _gbs(moved, hot), "GB/s  =", _gbs(moved, hot) / 271.0 * 100.0,
        "% of the measured 271 GB/s NT-SIMD ceiling  (cold/hot", cold / hot, "x, spread", spread,
        "x over", HOT_REPS, "reps)",
    )
    print("BENCH_GATE normk_self PASS")


fn _serve() raises:
    """One command per line on stdin, one reply per line on stdout.

    GEN rows cols          build x, gamma, beta, dy from splitmix64 indices
    DUMP tag path          tag in X G B DY Y DX DG DB
    FWD RMS|LN <ignored>   one timed forward;  replies `FWD <ns> <workers_used_inferred> <status>`
    BWD RMS|LN <ignored>   one timed backward; replies `BWD <ns> <workers_used_inferred> <status>`
    FD RMS|LN              finite-difference check; replies `FD <max_abs_delta> <tolerance> <status>`
    CORES                  replies `CORES <physical> <lanes>`
    QUIT

    The trailing argument on FWD/BWD is accepted for wire compatibility with a driver that predates
    this file's retarget onto the real `normk.rmsnorm` / `normk.layernorm` API, and is IGNORED:
    neither kernel takes a caller-supplied worker count. See the module docstring.
    """
    var x = List[Float64]()
    var gamma = List[Float64]()
    var beta = List[Float64]()
    var dy = List[Float64]()
    var y = List[Float64]()
    var dx = List[Float64]()
    var dgamma = List[Float64]()
    var dbeta = List[Float64]()
    var last_rstd = List[Float64]()
    var last_mean = List[Float64]()
    var rows = 0
    var cols = 0
    print("SERVE READY")
    while True:
        var line: String
        try:
            line = input()
        except:
            return
        var parts = line.split(" ")
        if len(parts) == 0:
            continue
        var cmd = String(parts[0])
        if cmd == "QUIT":
            print("BYE")
            return
        elif cmd == "CORES":
            print("CORES", info.num_physical_cores(), W)
        elif cmd == "GEN":
            rows = Int(String(parts[1]))
            cols = Int(String(parts[2]))
            x = _fill(rows * cols, 0)
            gamma = _fill_gamma(cols, 101_000_000)
            beta = _fill(cols, 202_000_000)
            dy = _fill(rows * cols, 303_000_000)
            print("GEN", rows, cols, len(x), len(gamma), len(beta), len(dy))
        elif cmd == "DUMP":
            var tag = String(parts[1])
            var path = String(parts[2])
            var wrote = -1
            if tag == "X":
                wrote = _dump(path, x, rows * cols)
            elif tag == "G":
                wrote = _dump(path, gamma, cols)
            elif tag == "B":
                wrote = _dump(path, beta, cols)
            elif tag == "DY":
                wrote = _dump(path, dy, rows * cols)
            elif tag == "Y":
                wrote = _dump(path, y, rows * cols)
            elif tag == "DX":
                wrote = _dump(path, dx, rows * cols)
            elif tag == "DG":
                wrote = _dump(path, dgamma, cols)
            elif tag == "DB":
                wrote = _dump(path, dbeta, cols)
            print("DUMP", tag, wrote)
        elif cmd == "FWD":
            var is_rms = String(parts[1]) == "RMS"
            var eps = 1.0e-6 if is_rms else 1.0e-5
            var t0 = perf_counter_ns()
            if is_rms:
                var r = rmsnorm_fwd_flat(x, gamma, rows, cols, eps)
                var ns = perf_counter_ns() - t0
                y = r.y.copy()
                last_rstd = r.rstd.copy()
                print("FWD", ns, _workers_used_inferred(rows, cols), r.status)
            else:
                var r2 = layernorm_fwd_flat(x, gamma, beta, rows, cols, eps)
                var ns = perf_counter_ns() - t0
                y = r2.y.copy()
                last_rstd = r2.rstd.copy()
                last_mean = r2.mean.copy()
                print("FWD", ns, _workers_used_inferred(rows, cols), r2.status)
        elif cmd == "BWD":
            var is_rms = String(parts[1]) == "RMS"
            var t0 = perf_counter_ns()
            if is_rms:
                var r = rmsnorm_bwd_flat(dy, x, gamma, last_rstd, rows, cols)
                var ns = perf_counter_ns() - t0
                dx = r.dx.copy()
                dgamma = r.dgamma.copy()
                print("BWD", ns, _workers_used_inferred(rows, cols), r.status)
            else:
                var r2 = layernorm_bwd_flat(dy, x, gamma, last_mean, last_rstd, rows, cols)
                var ns = perf_counter_ns() - t0
                dx = r2.dx.copy()
                dgamma = r2.dgamma.copy()
                dbeta = r2.dbeta.copy()
                print("BWD", ns, _workers_used_inferred(rows, cols), r2.status)
        elif cmd == "FD":
            var is_rms = String(parts[1]) == "RMS"
            var eps = 1.0e-6 if is_rms else 1.0e-5
            if is_rms:
                var rep = rmsnorm_gradcheck_flat(x, gamma, rows, cols, eps, GRADCHECK_STEP)
                print("FD", rep.max_abs_delta, rep.tolerance_at_max, rep.status)
            else:
                var rep2 = layernorm_gradcheck_flat(x, gamma, beta, rows, cols, eps, GRADCHECK_STEP)
                print("FD", rep2.max_abs_delta, rep2.tolerance_at_max, rep2.status)
        else:
            print("ERR unknown " + cmd)


fn main() raises:
    var av = argv()
    if len(av) > 1 and String(av[1]) == "SERVE":
        _serve()
    else:
        _self_mode()
