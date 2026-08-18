"""gemv_simd_reduce_probe.mojo — does replacing the two GEMV-kernel reductions (sum-of-squares
across a whole threadgroup, and one output column's dot product across one SIMD group) with
hardware SIMD-group shuffle reduction compute the IDENTICAL math, and does the exact Metal API
exist at this pinned Mojo nightly? Same discipline as `sdpa_simd_reduce_probe.mojo`, applied to a
DIFFERENT reduction shape.

    DEVELOPER_DIR=/Applications/Xcode-<version>.app/Contents/Developer \\
      pixi run mojo run -D ALGENTA_GPU -I../mojo/engine ../benchmarks/llm_smoke/gemv_simd_reduce_probe.mojo

Question being asked, precisely
--------------------------------
`residentk.kernels._norm_gemv_kernel_i8`/`_gemv_accum_kernel_i8`/`_norm_gemv2_swiglu_kernel_i8` all
launch `_TG = 256` threads per threadgroup and reduce with shared-memory halving trees, but there
are TWO DIFFERENT reduction SHAPES inside them, not one:

1. Sum-of-squares over the whole `k`-length input vector (`_norm_gemv_kernel_i8` and
   `_norm_gemv2_swiglu_kernel_i8` only, not `_gemv_accum_kernel_i8` which has no norm): every one
   of the `_TG = 256` threads holds a partial sum, reduced to one scalar with `log2(256) = 8`
   barrier-synchronized halving levels. If Apple's real hardware SIMD-group width is 32 (confirmed
   below, not assumed), these 256 threads are EXACTLY 8 full SIMD-groups — the SAME multi-group
   shape `_sdpa_kernel_simd` fixed for `d_head = 128 = 4 groups`, just twice as many groups. Same
   fix: `warp.sum` reduces each group with no barrier, one lane per group writes its total to an
   8-slot shared array, ONE barrier makes those visible, every thread sums the 8 entries itself.
   8 barriers -> 1.

2. Each output column's dot product: `_LANES = 32` threads (one SIMD group) compute ONE output
   column, `_SUBS = _TG // _LANES = 8` columns computed per threadgroup, each by its own,
   independent SIMD group. `log2(32) = 5` barrier-synchronized halving levels PER COLUMN. This is
   a SIMPLER case than (1) and than `_sdpa_kernel_simd`'s own fix: since one SIMD group maps 1:1 to
   one output column with NOTHING to combine across groups, a single-level `warp.sum` alone — no
   shared array, no barrier — IS the complete reduction. 5 barriers -> 0.

Both candidates are checked against an independent host reference AND the existing barrier-tree
kernel's own device output, on shapes small enough to hand-verify, before any timing number from
this file is trusted — same protocol `sdpa_simd_reduce_probe.mojo` established.
"""

from std.origin import MutAnyOrigin  # Mojo 1.0.0: origins left std.builtin.type_aliases
from max.gpu.host import DeviceContext, DeviceBuffer
from std.gpu import thread_idx, block_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.gpu.primitives.warp import sum as warp_sum
from std.gpu.primitives.id import lane_id, warp_id
from std.gpu.globals import WARP_SIZE
from std.memory import stack_allocation
from std.sys import has_accelerator, is_defined
from std.time import perf_counter_ns

comptime PROBE_GPU_BUILD: Bool = is_defined["ALGENTA_GPU"]()

comptime _TG: Int = 256
"""The real production `_TG` from `residentk.kernels` — 256 threads/threadgroup for every
projection kernel."""

comptime _LANES: Int = 32
"""The real production `_LANES` from `residentk.kernels` — Apple's assumed SIMD width, confirmed
below on real hardware, not re-assumed here."""

comptime _SUBS: Int = _TG // _LANES
"""Output columns one threadgroup produces: 8 — also the number of SIMD-groups spanned by one
`_TG`-wide sum-of-squares reduction, the same number, for the same underlying reason (`_TG` is an
exact multiple of `_LANES`)."""

comptime _N_COLS: Int = _SUBS
"""One probe threadgroup produces exactly `_SUBS` output columns, matching the real kernels'
`grid_dim = ceil(n / _SUBS)` layout — this probe uses `grid_dim = 1`, i.e. `n = _SUBS` columns
total, enough to exercise every SIMD-group's independent per-column reduction at once."""


def _lane_width_probe(out_lane: UnsafePointer[Int32, origin=MutAnyOrigin], out_warp: UnsafePointer[Int32, origin=MutAnyOrigin]):
    """Writes `lane_id()`/`warp_id()` for every thread of one `_TG`-wide threadgroup, so the host
    can confirm -- not assume -- that Apple's real SIMD-group width on THIS hardware is 32, and
    that `_TG / 32 = 8` distinct SIMD-groups appear inside one GEMV-kernel-shaped launch."""
    var e = Int(thread_idx.x)
    out_lane[e] = Int32(lane_id())
    out_warp[e] = Int32(warp_id())


def _ss_reduce_barrier_tree(out_val: UnsafePointer[Float32, origin=MutAnyOrigin], x_buf: UnsafePointer[Float32, origin=MutAnyOrigin], k: Int):
    """The EXISTING sum-of-squares mechanism, copied verbatim in structure from
    `_norm_gemv_kernel_i8`'s stage 1 (barrier-synchronized shared-memory tree, `log2(_TG)` levels),
    isolated to just the reduction, over a host-supplied `x` instead of a real activation vector."""
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x_buf[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    if tid == 0:
        out_val[0] = red[0]


def _ss_reduce_simd_shuffle(out_val: UnsafePointer[Float32, origin=MutAnyOrigin], x_buf: UnsafePointer[Float32, origin=MutAnyOrigin], k: Int):
    """The CANDIDATE replacement: two-level reduction, `_TG / 32 = 8` SIMD-groups. Level 1 is
    `warp.sum` inside each 32-lane group -- pure register shuffle, no barrier. Level 2 combines the
    8 per-group partial sums through one shared array and exactly ONE barrier."""
    comptime _N_GROUPS: Int = _TG // WARP_SIZE
    var grp = stack_allocation[_N_GROUPS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = lane_id()
    var grp_id = warp_id()
    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x_buf[i]
        ss += v * v
        i += _TG
    var group_total = warp_sum(ss)
    if lane == 0:
        grp[grp_id] = group_total
    barrier()
    if tid == 0:
        var total = Float32(0.0)
        for g in range(_N_GROUPS):
            total += grp[g]
        out_val[0] = total


def _col_reduce_barrier_tree(
    out_val: UnsafePointer[Float32, origin=MutAnyOrigin],
    x_buf: UnsafePointer[Float32, origin=MutAnyOrigin],
    w_buf: UnsafePointer[Float32, origin=MutAnyOrigin],
    k: Int, n: Int,
):
    """The EXISTING per-column dot-product mechanism, copied verbatim in structure from
    `_norm_gemv_kernel_i8`'s stage 3 (one SIMD group per output column, `log2(_LANES)` barrier
    levels), isolated to just the reduction, over host-supplied `x`/`w` (`w` is `[n, k]` row-major,
    exactly the real kernels' weight layout)."""
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = sub
    var acc = Float32(0.0)
    if j < n:
        var base = j * k
        var t = lane
        while t < k:
            acc += x_buf[t] * w_buf[base + t]
            t += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        out_val[j] = red[sub * _LANES]


def _col_reduce_simd_shuffle(
    out_val: UnsafePointer[Float32, origin=MutAnyOrigin],
    x_buf: UnsafePointer[Float32, origin=MutAnyOrigin],
    w_buf: UnsafePointer[Float32, origin=MutAnyOrigin],
    k: Int, n: Int,
):
    """The CANDIDATE replacement: one SIMD group per output column, NOTHING to combine across
    groups -- a single-level `warp.sum` alone, no shared array, no barrier at all, IS the complete
    reduction."""
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = sub
    var acc = Float32(0.0)
    if j < n:
        var base = j * k
        var t = lane
        while t < k:
            acc += x_buf[t] * w_buf[base + t]
            t += _LANES
    var total = warp_sum(acc)
    if lane == 0 and j < n:
        out_val[j] = total


def _pseudo(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2)
    return o^


def _exp64(x: Float64) -> Float64:
    from std.math import exp
    return exp(x)


def main() raises:
    print("=== GEMV reduction probe: barrier-tree vs SIMD-shuffle, two shapes, same math ===")
    print("")

    if not PROBE_GPU_BUILD:
        print("Built WITHOUT -D ALGENTA_GPU: refusing to report anything (kernels compiled out).")
        return
    if not has_accelerator():
        print("No usable accelerator. Refusing to report anything.")
        return

    var ctx = DeviceContext()

    print("--- SIMD-group width check: confirm WARP_SIZE and the real hardware lane/warp ids at _TG=256 ---")
    var lane_buf = ctx.enqueue_create_buffer[DType.int32](_TG)
    var warp_buf = ctx.enqueue_create_buffer[DType.int32](_TG)
    var f_probe = ctx.compile_function_unchecked[_lane_width_probe]()
    ctx.enqueue_function_unchecked(
        f_probe, lane_buf.unsafe_ptr(), warp_buf.unsafe_ptr(),
        grid_dim=1, block_dim=_TG,
    )
    ctx.synchronize()
    print("   std.gpu.globals.WARP_SIZE (compile-time, is_apple_gpu() branch) =", WARP_SIZE)
    var max_warp = 0
    var lane_ok = True
    with lane_buf.map_to_host() as lh:
        with warp_buf.map_to_host() as wh:
            for e in range(_TG):
                var expect_lane = e % WARP_SIZE
                var expect_warp = e // WARP_SIZE
                if Int(lh[e]) != expect_lane or Int(wh[e]) != expect_warp:
                    lane_ok = False
                if Int(wh[e]) > max_warp:
                    max_warp = Int(wh[e])
    print("   observed distinct SIMD-groups inside one _TG=256 threadgroup =", max_warp + 1)
    print("   lane_id()/warp_id() match thread_idx.x % / // WARP_SIZE exactly:", "OK" if lane_ok else "MISMATCH")
    if not lane_ok or max_warp + 1 != _SUBS or WARP_SIZE != _LANES:
        print("ASSUMPTION VIOLATED: production's _LANES=32/_SUBS=8 do not match this hardware. Stopping.")
        return
    print("   CONFIRMED: _TG=256 is exactly", _SUBS, "full SIMD-groups of", WARP_SIZE, "lanes each",
          "-- matches production's _LANES/_SUBS constants exactly, not by luck.")
    print("")

    print("--- Stage-1 shape (sum-of-squares, 256-wide): barrier-tree vs SIMD-shuffle vs host f64 ref ---")
    for k_case in [37, 256, 1024, 3072]:
        var x64 = _pseudo(k_case, k_case + 5)
        var xbuf = ctx.enqueue_create_buffer[DType.float32](k_case)
        with xbuf.map_to_host() as h:
            for i in range(k_case):
                h[i] = Float32(x64[i])
        ctx.synchronize()

        var host_ss = Float64(0.0)
        for i in range(k_case):
            host_ss += x64[i] * x64[i]

        var out_tree = ctx.enqueue_create_buffer[DType.float32](1)
        var out_shfl = ctx.enqueue_create_buffer[DType.float32](1)
        var f_tree = ctx.compile_function_unchecked[_ss_reduce_barrier_tree]()
        var f_shfl = ctx.compile_function_unchecked[_ss_reduce_simd_shuffle]()
        ctx.enqueue_function_unchecked(f_tree, out_tree.unsafe_ptr(), xbuf.unsafe_ptr(), k_case, grid_dim=1, block_dim=_TG)
        ctx.enqueue_function_unchecked(f_shfl, out_shfl.unsafe_ptr(), xbuf.unsafe_ptr(), k_case, grid_dim=1, block_dim=_TG)
        ctx.synchronize()

        var tree_v = Float64(0.0)
        var shfl_v = Float64(0.0)
        with out_tree.map_to_host() as h:
            tree_v = Float64(h[0])
        with out_shfl.map_to_host() as h:
            shfl_v = Float64(h[0])
        var d_tree = tree_v - host_ss
        if d_tree < 0.0:
            d_tree = -d_tree
        var d_shfl = shfl_v - host_ss
        if d_shfl < 0.0:
            d_shfl = -d_shfl
        var d_cross = tree_v - shfl_v
        if d_cross < 0.0:
            d_cross = -d_cross
        var ok = d_tree < 1e-3 and d_shfl < 1e-3 and d_cross < 1e-3
        print("   k=", k_case, " host=", host_ss, " tree=", tree_v, " shfl=", shfl_v,
              " |tree-host|=", d_tree, " |shfl-host|=", d_shfl, " |tree-shfl|=", d_cross,
              "  ", "OK" if ok else "MISMATCH")
        if not ok:
            print("CORRECTNESS FAILURE: refusing to report any timing number.")
            return
    print("")

    print("--- Stage-3 shape (per-column dot product, one SIMD group/column): barrier-tree vs SIMD-shuffle vs host f64 ref ---")
    for k_case in [17, 128, 1024]:
        var n_case = _N_COLS
        var x64c = _pseudo(k_case, k_case + 11)
        var w64c = _pseudo(n_case * k_case, k_case + 91)

        var xbufc = ctx.enqueue_create_buffer[DType.float32](k_case)
        var wbufc = ctx.enqueue_create_buffer[DType.float32](n_case * k_case)
        with xbufc.map_to_host() as h:
            for i in range(k_case):
                h[i] = Float32(x64c[i])
        with wbufc.map_to_host() as h:
            for i in range(n_case * k_case):
                h[i] = Float32(w64c[i])
        ctx.synchronize()

        var host_cols = List[Float64](capacity=n_case)
        for j in range(n_case):
            var s = Float64(0.0)
            for t in range(k_case):
                s += x64c[t] * w64c[j * k_case + t]
            host_cols.append(s)

        var out_tree_c = ctx.enqueue_create_buffer[DType.float32](n_case)
        var out_shfl_c = ctx.enqueue_create_buffer[DType.float32](n_case)
        var f_tree_c = ctx.compile_function_unchecked[_col_reduce_barrier_tree]()
        var f_shfl_c = ctx.compile_function_unchecked[_col_reduce_simd_shuffle]()
        ctx.enqueue_function_unchecked(
            f_tree_c, out_tree_c.unsafe_ptr(), xbufc.unsafe_ptr(), wbufc.unsafe_ptr(), k_case, n_case,
            grid_dim=1, block_dim=_TG,
        )
        ctx.enqueue_function_unchecked(
            f_shfl_c, out_shfl_c.unsafe_ptr(), xbufc.unsafe_ptr(), wbufc.unsafe_ptr(), k_case, n_case,
            grid_dim=1, block_dim=_TG,
        )
        ctx.synchronize()

        var worst_tree = Float64(0.0)
        var worst_shfl = Float64(0.0)
        var worst_cross = Float64(0.0)
        with out_tree_c.map_to_host() as ht:
            with out_shfl_c.map_to_host() as hs:
                for j in range(n_case):
                    var dt = Float64(ht[j]) - host_cols[j]
                    if dt < 0.0:
                        dt = -dt
                    var ds = Float64(hs[j]) - host_cols[j]
                    if ds < 0.0:
                        ds = -ds
                    var dc = Float64(ht[j]) - Float64(hs[j])
                    if dc < 0.0:
                        dc = -dc
                    if dt > worst_tree:
                        worst_tree = dt
                    if ds > worst_shfl:
                        worst_shfl = ds
                    if dc > worst_cross:
                        worst_cross = dc
        var ok_c = worst_tree < 1e-3 and worst_shfl < 1e-3 and worst_cross < 1e-3
        print("   k=", k_case, " n_cols=", n_case, " worst|tree-host|=", worst_tree,
              " worst|shfl-host|=", worst_shfl, " worst|tree-shfl|=", worst_cross,
              "  ", "OK" if ok_c else "MISMATCH")
        if not ok_c:
            print("CORRECTNESS FAILURE: refusing to report any timing number.")
            return
    print("")

    print("--- timing: barrier-tree vs SIMD-shuffle, both shapes, decode-shaped k ---")
    for k_case in [1024, 2048, 3072]:
        _time_ss_case(ctx, k_case, 500)
    for k_case in [1024, 2048, 3072]:
        _time_col_case(ctx, k_case, _N_COLS, 500)


def _median(mut s: List[Float64]) -> Float64:
    for i in range(1, len(s)):
        var key = s[i]
        var j = i - 1
        while j >= 0 and s[j] > key:
            s[j + 1] = s[j]
            j -= 1
        s[j + 1] = key
    return s[len(s) // 2]


def _time_ss_case(ctx: DeviceContext, k: Int, reps: Int) raises:
    var x64 = _pseudo(k, k + 3)
    var xbuf = ctx.enqueue_create_buffer[DType.float32](k)
    with xbuf.map_to_host() as h:
        for i in range(k):
            h[i] = Float32(x64[i])
    ctx.synchronize()

    var out_tree = ctx.enqueue_create_buffer[DType.float32](1)
    var out_shfl = ctx.enqueue_create_buffer[DType.float32](1)
    var f_tree = ctx.compile_function_unchecked[_ss_reduce_barrier_tree]()
    var f_shfl = ctx.compile_function_unchecked[_ss_reduce_simd_shuffle]()

    for _ in range(5):
        ctx.enqueue_function_unchecked(f_tree, out_tree.unsafe_ptr(), xbuf.unsafe_ptr(), k, grid_dim=1, block_dim=_TG)
    ctx.synchronize()
    var samples_tree = List[Float64]()
    for _ in range(reps):
        var t0 = perf_counter_ns()
        ctx.enqueue_function_unchecked(f_tree, out_tree.unsafe_ptr(), xbuf.unsafe_ptr(), k, grid_dim=1, block_dim=_TG)
        ctx.synchronize()
        samples_tree.append(Float64(Int(perf_counter_ns() - t0)) / 1e3)
    var med_tree = _median(samples_tree)

    for _ in range(5):
        ctx.enqueue_function_unchecked(f_shfl, out_shfl.unsafe_ptr(), xbuf.unsafe_ptr(), k, grid_dim=1, block_dim=_TG)
    ctx.synchronize()
    var samples_shfl = List[Float64]()
    for _ in range(reps):
        var t1 = perf_counter_ns()
        ctx.enqueue_function_unchecked(f_shfl, out_shfl.unsafe_ptr(), xbuf.unsafe_ptr(), k, grid_dim=1, block_dim=_TG)
        ctx.synchronize()
        samples_shfl.append(Float64(Int(perf_counter_ns() - t1)) / 1e3)
    var med_shfl = _median(samples_shfl)

    print(
        "   [sum-of-squares] k=", k,
        " barrier_tree median of", reps, "=", med_tree, "us",
        "  simd_shuffle median =", med_shfl, "us",
        "  (", (med_shfl - med_tree) / med_tree * 100.0, "% vs barrier_tree)",
    )


def _time_col_case(ctx: DeviceContext, k: Int, n: Int, reps: Int) raises:
    var x64 = _pseudo(k, k + 7)
    var w64 = _pseudo(n * k, k + 13)
    var xbuf = ctx.enqueue_create_buffer[DType.float32](k)
    var wbuf = ctx.enqueue_create_buffer[DType.float32](n * k)
    with xbuf.map_to_host() as h:
        for i in range(k):
            h[i] = Float32(x64[i])
    with wbuf.map_to_host() as h:
        for i in range(n * k):
            h[i] = Float32(w64[i])
    ctx.synchronize()

    var out_tree = ctx.enqueue_create_buffer[DType.float32](n)
    var out_shfl = ctx.enqueue_create_buffer[DType.float32](n)
    var f_tree = ctx.compile_function_unchecked[_col_reduce_barrier_tree]()
    var f_shfl = ctx.compile_function_unchecked[_col_reduce_simd_shuffle]()

    for _ in range(5):
        ctx.enqueue_function_unchecked(f_tree, out_tree.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), k, n, grid_dim=1, block_dim=_TG)
    ctx.synchronize()
    var samples_tree = List[Float64]()
    for _ in range(reps):
        var t0 = perf_counter_ns()
        ctx.enqueue_function_unchecked(f_tree, out_tree.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), k, n, grid_dim=1, block_dim=_TG)
        ctx.synchronize()
        samples_tree.append(Float64(Int(perf_counter_ns() - t0)) / 1e3)
    var med_tree = _median(samples_tree)

    for _ in range(5):
        ctx.enqueue_function_unchecked(f_shfl, out_shfl.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), k, n, grid_dim=1, block_dim=_TG)
    ctx.synchronize()
    var samples_shfl = List[Float64]()
    for _ in range(reps):
        var t1 = perf_counter_ns()
        ctx.enqueue_function_unchecked(f_shfl, out_shfl.unsafe_ptr(), xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), k, n, grid_dim=1, block_dim=_TG)
        ctx.synchronize()
        samples_shfl.append(Float64(Int(perf_counter_ns() - t1)) / 1e3)
    var med_shfl = _median(samples_shfl)

    print(
        "   [per-column dot] k=", k, " n_cols=", n,
        " barrier_tree median of", reps, "=", med_tree, "us",
        "  simd_shuffle median =", med_shfl, "us",
        "  (", (med_shfl - med_tree) / med_tree * 100.0, "% vs barrier_tree)",
    )
