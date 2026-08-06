"""lmhead_argmax_simd_reduce_probe.mojo — does replacing `_lmhead_argmax_kernel_i8`'s two barrier-
tree reductions (a `_TG=256`-wide sum-of-squares stage, and a `_LANES=32`-wide per-output-column
dot-product-with-running-argmax stage run once per `it` iteration of its own grid-stride loop) with
hardware SIMD-group shuffle reduction compute the IDENTICAL math, and does the exact Metal API exist
at this pinned Mojo nightly? Same discipline as `sdpa_simd_reduce_probe.mojo`/
`gemv_simd_reduce_probe.mojo`, applied to lm_head's own two shapes — shape 1 is mechanically
IDENTICAL to the GEMV kernels' own stage 1 (re-confirmed here for completeness, not re-derived from
scratch), but shape 2 is NOT a bare twin of the GEMV kernels' own per-column stage: lm_head walks
the WHOLE vocabulary in a `for it in range(n_iters)` loop, re-using its per-thread `best`/`best_i`
registers (and, in the barrier-tree original, its shared `red[]` array) ACROSS iterations, which
the plain single-shot GEMV kernels never do. This file's own novel content is checking THAT shape,
not re-checking shape 1.

    DEVELOPER_DIR=/Applications/Xcode-<version>.app/Contents/Developer \\
      pixi run mojo run -D ALGENTA_GPU -I../mojo/engine ../benchmarks/llm_smoke/lmhead_argmax_simd_reduce_probe.mojo

Question being asked, precisely
--------------------------------
`residentk.kernels._lmhead_argmax_kernel_i8` launches `_TG = 256` threads per threadgroup and reduces
with shared-memory halving trees, but has TWO DIFFERENT reduction shapes, not one:

1. Sum-of-squares over the whole `k`-length input vector, run ONCE per launch: every one of the
   `_TG = 256` threads holds a partial sum, reduced to one scalar with `log2(256) = 8`
   barrier-synchronized halving levels. Mechanically IDENTICAL to `_norm_gemv_kernel_i8`'s own
   stage 1, already fixed and probed by `gemv_simd_reduce_probe.mojo` on this exact hardware — 8
   full SIMD-groups, `warp.sum` per group + one combine barrier, 8 barriers -> 1.

2. Each output column's dot product AND its running argmax, reduced across its own `_LANES = 32`-
   wide SIMD group, run ONCE PER ITERATION of `for it in range(n_iters)` (lm_head walks the WHOLE
   `n`-row vocabulary in `_SUBS`-column strides per threadgroup, not a single pass over one column
   per thread the way a plain GEMV kernel does): `log2(32) = 5` barrier levels PER ITERATION, plus
   ONE trailing "safety" barrier per iteration in the original that stops a fast thread from
   overwriting `red[]` before every thread in its group has read it for the CURRENT iteration's
   argmax update. Since one SIMD group maps 1:1 to one output column with NOTHING to combine across
   groups, a single-level `warp.sum` alone — no shared array, no barrier — IS the complete
   per-iteration reduction; because it never touches `red[]` at all, the trailing safety barrier has
   nothing left to guard either, so ALL SIX per-iteration barriers drop, not just the five tree
   levels. This file's own `_lmhead_col_argmax_barrier_tree`/`_lmhead_col_argmax_simd_shuffle`
   isolate exactly this shape (skipping the int8 dequant and the rmsnorm stage, both unaffected by
   this question — the permanent kernel-level test,
   `mojo/tests/libs/test_residentk_lmhead_simd_kernel.mojo`, exercises the real int8 kernel
   end-to-end including those) at a REALISTIC `grid_dim`/`n_iters` (2048 threadgroups, `n_iters`
   large enough to walk a real ~152K-row vocabulary), so the multi-iteration register-reuse claim is
   checked on real hardware, not assumed from reading the kernel source.

Both candidates are checked against an independent host reference AND the existing barrier-tree
kernel's own device output, on shapes small enough to hand-verify, before any timing number from
this file is trusted — same protocol `sdpa_simd_reduce_probe.mojo`/`gemv_simd_reduce_probe.mojo`
established.
"""

from std.builtin.type_aliases import MutAnyOrigin
from std.gpu.host import DeviceContext, DeviceBuffer
from std.gpu import barrier, thread_idx, block_idx, grid_dim
from std.gpu.memory import AddressSpace
from std.gpu.primitives.warp import sum as warp_sum
from std.gpu.primitives.id import lane_id, warp_id
from std.gpu.globals import WARP_SIZE
from std.memory import stack_allocation
from std.sys import has_accelerator, is_defined
from std.time import perf_counter_ns

comptime PROBE_GPU_BUILD: Bool = is_defined["ALGENTA_GPU"]()

comptime _TG: Int = 256
"""The real production `_TG` from `residentk.kernels` — 256 threads/threadgroup for every
projection kernel, `_lmhead_argmax_kernel_i8` included."""

comptime _LANES: Int = 32
"""The real production `_LANES` from `residentk.kernels` — Apple's assumed SIMD width, confirmed
below on real hardware, not re-assumed here."""

comptime _SUBS: Int = _TG // _LANES
"""Output columns one threadgroup produces per `it` iteration: 8 — also the number of SIMD-groups
spanned by one `_TG`-wide sum-of-squares reduction, the same number, for the same underlying reason
(`_TG` is an exact multiple of `_LANES`)."""

comptime _NEG_HUGE: Float32 = -3.0e38
"""Same sentinel `residentk.kernels._NEG_HUGE` uses — smaller in magnitude than any real dequantized
dot product this model produces, so the first real column visited always replaces it."""


def _lane_width_probe(out_lane: UnsafePointer[Int32, origin=MutAnyOrigin], out_warp: UnsafePointer[Int32, origin=MutAnyOrigin]):
    """Writes `lane_id()`/`warp_id()` for every thread of one `_TG`-wide threadgroup, so the host
    can confirm -- not assume -- that Apple's real SIMD-group width on THIS hardware is 32, and that
    `_TG / 32 = 8` distinct SIMD-groups appear inside one lm_head-shaped launch. Re-confirmed here
    independently of `gemv_simd_reduce_probe.mojo`'s own identical check -- cheap, and this file
    should stand on its own."""
    var e = Int(thread_idx.x)
    out_lane[e] = Int32(lane_id())
    out_warp[e] = Int32(warp_id())


def _ss_reduce_barrier_tree(out_val: UnsafePointer[Float32, origin=MutAnyOrigin], x_buf: UnsafePointer[Float32, origin=MutAnyOrigin], k: Int):
    """The EXISTING sum-of-squares mechanism, copied verbatim in structure from
    `_lmhead_argmax_kernel_i8`'s stage 1 (barrier-synchronized shared-memory tree, `log2(_TG)`
    levels), isolated to just the reduction, over a host-supplied `x` instead of a real activation
    vector. Byte-identical to `gemv_simd_reduce_probe.mojo`'s own `_ss_reduce_barrier_tree` since the
    shape is mechanically the same kernel stage; duplicated here (not imported -- this file has no
    package structure to import from) so this probe is self-contained."""
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


def _lmhead_col_argmax_barrier_tree(
    out_val: UnsafePointer[Float32, origin=MutAnyOrigin],
    out_idx: UnsafePointer[Int32, origin=MutAnyOrigin],
    x_buf: UnsafePointer[Float32, origin=MutAnyOrigin],
    w_buf: UnsafePointer[Float32, origin=MutAnyOrigin],
    k: Int, n: Int, n_iters: Int,
):
    """The EXISTING per-column-dot-plus-running-argmax mechanism, copied verbatim in structure from
    `_lmhead_argmax_kernel_i8`'s stage 2/3 (one SIMD group per output column, `log2(_LANES)` barrier
    levels PER ITERATION of the grid-stride `it` loop, plus one trailing safety barrier per
    iteration), isolated to just the reduction+argmax over host-supplied plain-Float32 `x`/`w` (`w`
    is `[n, k]` row-major, exactly the real kernel's weight layout minus the int8 dequant, which is
    orthogonal to this question). `grid_dim.x` threadgroups, each walking its own `_SUBS`-column
    stride `n_iters` times, exactly the real kernel's own grid-stride loop shape."""
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var sv = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var si = stack_allocation[_SUBS, DType.int32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES
    var stride_cols = Int(grid_dim.x) * _SUBS
    var best = _NEG_HUGE
    var best_i = Int32(-1)

    for it in range(n_iters):
        var j = Int(block_idx.x) * _SUBS + sub + it * stride_cols
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
            var val = red[sub * _LANES]
            if val > best:
                best = val
                best_i = Int32(j)
        barrier()

    if lane == 0:
        sv[sub] = best
        si[sub] = best_i
    barrier()
    if tid == 0:
        var bv = sv[0]
        var bi = si[0]
        for u in range(1, _SUBS):
            if sv[u] > bv:
                bv = sv[u]
                bi = si[u]
        out_val[Int(block_idx.x)] = bv
        out_idx[Int(block_idx.x)] = bi


def _lmhead_col_argmax_simd_shuffle(
    out_val: UnsafePointer[Float32, origin=MutAnyOrigin],
    out_idx: UnsafePointer[Int32, origin=MutAnyOrigin],
    x_buf: UnsafePointer[Float32, origin=MutAnyOrigin],
    w_buf: UnsafePointer[Float32, origin=MutAnyOrigin],
    k: Int, n: Int, n_iters: Int,
):
    """The CANDIDATE replacement: one SIMD group per output column, NOTHING to combine across
    groups -- a single-level `warp.sum` alone, no shared array, no barrier at all, IS the complete
    per-iteration reduction. `best`/`best_i` are per-thread REGISTERS carried across the whole `it`
    loop with zero synchronization between iterations -- the claim this probe exists to check on
    real hardware: no iteration's shared-memory state depends on any other iteration's, because
    NOTHING in this stage touches shared memory until after the loop ends."""
    var sv = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var si = stack_allocation[_SUBS, DType.int32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES
    var stride_cols = Int(grid_dim.x) * _SUBS
    var best = _NEG_HUGE
    var best_i = Int32(-1)

    for it in range(n_iters):
        var j = Int(block_idx.x) * _SUBS + sub + it * stride_cols
        var acc = Float32(0.0)
        if j < n:
            var base = j * k
            var t = lane
            while t < k:
                acc += x_buf[t] * w_buf[base + t]
                t += _LANES
        var total = warp_sum(acc)
        if lane == 0 and j < n:
            if total > best:
                best = total
                best_i = Int32(j)

    if lane == 0:
        sv[sub] = best
        si[sub] = best_i
    barrier()
    if tid == 0:
        var bv = sv[0]
        var bi = si[0]
        for u in range(1, _SUBS):
            if sv[u] > bv:
                bv = sv[u]
                bi = si[u]
        out_val[Int(block_idx.x)] = bv
        out_idx[Int(block_idx.x)] = bi


def _pseudo(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2)
    return o^


def _host_block_argmax(
    x64: List[Float64], w64: List[Float64], k: Int, n: Int, grid_n: Int, n_iters: Int,
    mut out_val: List[Float64], mut out_idx: List[Int],
):
    """Pure-host Float64 reference for the SAME block-strided per-column dot + running-argmax the
    two device kernels above compute -- same scan order (`sub` outer, `it` inner, matching each
    thread's own register-local scan before the final per-threadgroup combine over `sub`), same
    strict `>` tie-break, so an exact tie (never expected with these pseudo-random inputs, but
    checked for anyway) resolves identically on host and device. Out-parameters (not a tuple
    return) so the two result lists stay independently `mut`-able at the call site, the same
    discipline `test_residentk_gemv_simd_kernel.mojo`'s own `_quantize_row_i8_host` uses."""
    var stride_cols = grid_n * _SUBS
    for b in range(grid_n):
        var best = -1.0e30
        var best_i = -1
        for sub in range(_SUBS):
            var sub_best = -1.0e30
            var sub_best_i = -1
            for it in range(n_iters):
                var j = b * _SUBS + sub + it * stride_cols
                if j < n:
                    var s = 0.0
                    var base = j * k
                    for i in range(k):
                        s += x64[i] * w64[base + i]
                    if s > sub_best:
                        sub_best = s
                        sub_best_i = j
            if sub_best_i >= 0 and sub_best > best:
                best = sub_best
                best_i = sub_best_i
        out_val.append(best)
        out_idx.append(best_i)


def main() raises:
    print("=== lm_head argmax reduction probe: barrier-tree vs SIMD-shuffle, two shapes ===")
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
    print("   lane_id()/warp_id() match thread_idx.x % / // 32 exactly:", "OK" if lane_ok else "MISMATCH")
    if not lane_ok or max_warp + 1 != _SUBS or WARP_SIZE != _LANES:
        print("ASSUMPTION VIOLATED: production's _LANES=32/_SUBS=8 do not match this hardware. Stopping.")
        return
    print("   CONFIRMED: _TG=256 is exactly", _SUBS, "full SIMD-groups of", WARP_SIZE, "lanes each.")
    print("")

    print("--- Stage-1 shape (sum-of-squares, 256-wide): re-confirmed, same as gemv_simd_reduce_probe.mojo ---")
    for k_case in [37, 1024, 3072]:
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

    print("--- Stage-2 shape (per-column argmax, MULTI-ITERATION, zero-barrier register reuse): the novel check ---")
    var k_cases = List[Int]()
    k_cases.append(17)
    k_cases.append(128)
    k_cases.append(1024)
    var n_cases = List[Int]()
    n_cases.append(37)
    n_cases.append(53)
    n_cases.append(19)
    # grid_n < ceil(n_case / _SUBS) so at least one column needs a SECOND `it` -- exercises the
    # register-reuse-across-iterations claim, not just a single pass.
    var grid_n_cases = List[Int]()
    grid_n_cases.append(2)
    grid_n_cases.append(3)
    grid_n_cases.append(1)
    for case_i in range(3):
        var k_case = k_cases[case_i]
        var n_case = n_cases[case_i]
        var grid_n = grid_n_cases[case_i]

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

        var stride_cols = grid_n * _SUBS
        var n_iters = (n_case + stride_cols - 1) // stride_cols
        if n_iters < 2:
            n_iters = 2  # force at least 2 iterations even on the smallest case

        var host_val = List[Float64]()
        var host_idx = List[Int]()
        _host_block_argmax(x64c, w64c, k_case, n_case, grid_n, n_iters, host_val, host_idx)

        var out_val_tree = ctx.enqueue_create_buffer[DType.float32](grid_n)
        var out_idx_tree = ctx.enqueue_create_buffer[DType.int32](grid_n)
        var out_val_shfl = ctx.enqueue_create_buffer[DType.float32](grid_n)
        var out_idx_shfl = ctx.enqueue_create_buffer[DType.int32](grid_n)
        var f_tree_c = ctx.compile_function_unchecked[_lmhead_col_argmax_barrier_tree]()
        var f_shfl_c = ctx.compile_function_unchecked[_lmhead_col_argmax_simd_shuffle]()
        ctx.enqueue_function_unchecked(
            f_tree_c, out_val_tree.unsafe_ptr(), out_idx_tree.unsafe_ptr(),
            xbufc.unsafe_ptr(), wbufc.unsafe_ptr(), k_case, n_case, n_iters,
            grid_dim=grid_n, block_dim=_TG,
        )
        ctx.enqueue_function_unchecked(
            f_shfl_c, out_val_shfl.unsafe_ptr(), out_idx_shfl.unsafe_ptr(),
            xbufc.unsafe_ptr(), wbufc.unsafe_ptr(), k_case, n_case, n_iters,
            grid_dim=grid_n, block_dim=_TG,
        )
        ctx.synchronize()

        var worst_tree_host = Float64(0.0)
        var worst_shfl_host = Float64(0.0)
        var worst_cross = Float64(0.0)
        var idx_ok = True
        with out_val_tree.map_to_host() as htv:
            with out_idx_tree.map_to_host() as hti:
                with out_val_shfl.map_to_host() as hsv:
                    with out_idx_shfl.map_to_host() as hsi:
                        for b in range(grid_n):
                            var dt = Float64(htv[b]) - host_val[b]
                            if dt < 0.0:
                                dt = -dt
                            var ds = Float64(hsv[b]) - host_val[b]
                            if ds < 0.0:
                                ds = -ds
                            var dc = Float64(htv[b]) - Float64(hsv[b])
                            if dc < 0.0:
                                dc = -dc
                            if dt > worst_tree_host:
                                worst_tree_host = dt
                            if ds > worst_shfl_host:
                                worst_shfl_host = ds
                            if dc > worst_cross:
                                worst_cross = dc
                            if Int(hti[b]) != host_idx[b] or Int(hsi[b]) != host_idx[b]:
                                idx_ok = False
                                print("      block", b, "index mismatch: host=", host_idx[b],
                                      "tree=", Int(hti[b]), "shfl=", Int(hsi[b]))
        var ok_c = worst_tree_host < 1e-2 and worst_shfl_host < 1e-2 and worst_cross < 1e-2 and idx_ok
        print("   k=", k_case, " n=", n_case, " grid_n=", grid_n, " n_iters=", n_iters,
              " tree vs host: worst|Δ|=", worst_tree_host, " shfl vs host: worst|Δ|=", worst_shfl_host,
              " tree vs shfl: worst|Δ|=", worst_cross,
              " argmax indices match:", "OK" if idx_ok else "MISMATCH",
              "  ", "OK" if ok_c else "FAIL")
        if not ok_c:
            print("CORRECTNESS FAILURE: refusing to report any timing number.")
            return
    print("")

    print("--- timing: barrier-tree vs SIMD-shuffle, decode-shaped k, realistic grid_n/n_iters ratio ---")
    print("   (grid_n=256, n_iters=10 -- the SAME grid_n*_SUBS*n_iters/n ratio production's own")
    print("    grid_n=_LM_BLOCKS=2048, n_iters~10 over a ~152K-row vocab has, scaled down so the")
    print("    weight buffer this probe allocates stays a sane size for a quick timing run; `n` is")
    print("    set to EXACTLY `grid_n * _SUBS * n_iters` so every iteration is fully populated,")
    print("    matching what the correctness section immediately above already checked for both")
    print("    fully- and partially-populated final iterations)")
    for k_case in [1024, 2048, 3072]:
        _time_lmhead_case(ctx, k_case, 256, 10, 200)


def _median(mut s: List[Float64]) -> Float64:
    for i in range(1, len(s)):
        var key = s[i]
        var j = i - 1
        while j >= 0 and s[j] > key:
            s[j + 1] = s[j]
            j -= 1
        s[j + 1] = key
    return s[len(s) // 2]


def _time_lmhead_case(ctx: DeviceContext, k: Int, grid_n: Int, n_iters: Int, reps: Int) raises:
    """`n = grid_n * _SUBS * n_iters` exactly -- every column index the kernel ever computes
    (`j = block_idx.x * _SUBS + sub + it * grid_n * _SUBS`, `it` up to `n_iters - 1`) stays inside
    `[0, n)`, so `wbuf` only needs `n * k` elements, no more, no out-of-bounds device read."""
    var n = grid_n * _SUBS * n_iters
    var x64 = _pseudo(k, k + 3)
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

    var out_val_tree = ctx.enqueue_create_buffer[DType.float32](grid_n)
    var out_idx_tree = ctx.enqueue_create_buffer[DType.int32](grid_n)
    var out_val_shfl = ctx.enqueue_create_buffer[DType.float32](grid_n)
    var out_idx_shfl = ctx.enqueue_create_buffer[DType.int32](grid_n)
    var f_tree = ctx.compile_function_unchecked[_lmhead_col_argmax_barrier_tree]()
    var f_shfl = ctx.compile_function_unchecked[_lmhead_col_argmax_simd_shuffle]()

    for _ in range(3):
        ctx.enqueue_function_unchecked(
            f_tree, out_val_tree.unsafe_ptr(), out_idx_tree.unsafe_ptr(),
            xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), k, n, n_iters,
            grid_dim=grid_n, block_dim=_TG,
        )
    ctx.synchronize()
    var samples_tree = List[Float64]()
    for _ in range(reps):
        var t0 = perf_counter_ns()
        ctx.enqueue_function_unchecked(
            f_tree, out_val_tree.unsafe_ptr(), out_idx_tree.unsafe_ptr(),
            xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), k, n, n_iters,
            grid_dim=grid_n, block_dim=_TG,
        )
        ctx.synchronize()
        samples_tree.append(Float64(Int(perf_counter_ns() - t0)) / 1e3)
    var med_tree = _median(samples_tree)

    for _ in range(3):
        ctx.enqueue_function_unchecked(
            f_shfl, out_val_shfl.unsafe_ptr(), out_idx_shfl.unsafe_ptr(),
            xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), k, n, n_iters,
            grid_dim=grid_n, block_dim=_TG,
        )
    ctx.synchronize()
    var samples_shfl = List[Float64]()
    for _ in range(reps):
        var t1 = perf_counter_ns()
        ctx.enqueue_function_unchecked(
            f_shfl, out_val_shfl.unsafe_ptr(), out_idx_shfl.unsafe_ptr(),
            xbuf.unsafe_ptr(), wbuf.unsafe_ptr(), k, n, n_iters,
            grid_dim=grid_n, block_dim=_TG,
        )
        ctx.synchronize()
        samples_shfl.append(Float64(Int(perf_counter_ns() - t1)) / 1e3)
    var med_shfl = _median(samples_shfl)

    print(
        "   [lm_head argmax] k=", k, " n=", n, " grid_n=", grid_n, " n_iters=", n_iters,
        " barrier_tree median of", reps, "=", med_tree, "us",
        "  simd_shuffle median =", med_shfl, "us",
        "  (", (med_shfl - med_tree) / med_tree * 100.0, "% vs barrier_tree)",
    )
