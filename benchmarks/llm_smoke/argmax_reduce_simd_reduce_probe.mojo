"""argmax_reduce_simd_reduce_probe.mojo — does a hand-rolled `shuffle_xor` compare-exchange
butterfly compute the IDENTICAL paired-argmax reduction `_argmax_reduce_kernel`'s barrier-tree
already computes, and does the exact Metal API exist at this pinned Mojo nightly? Same discipline
as `sdpa_simd_reduce_probe.mojo`/`gemv_simd_reduce_probe.mojo`/`lmhead_argmax_simd_reduce_probe.mojo`,
applied to the LAST barrier-tree reduction PR #510 named in the decode path and the one every prior
round of this sweep (PR #513 SDPA, PR #514 GEMV, PR #515 lm_head) deliberately left unfixed.

    DEVELOPER_DIR=/Applications/Xcode-<version>.app/Contents/Developer \\
      pixi run mojo run -D ALGENTA_GPU -I../mojo/engine ../benchmarks/llm_smoke/argmax_reduce_simd_reduce_probe.mojo

Question being asked, precisely
--------------------------------
`residentk.kernels._argmax_reduce_kernel` launches ONE `_TG = 256`-thread threadgroup
(`grid_dim=1`) that collapses `_lmhead_argmax_kernel`'s `n = _LM_BLOCKS = 2048` per-threadgroup
`(logit, id)` pairs to a single winning pair, via a per-thread grid-stride local-best scan followed
by a `log2(256) = 8`-level barrier-synchronized shared-memory halving tree (plus the tree's own
leading write-visibility barrier — 9 barrier hits total). PR #515's own Reduce agent skipped this
kernel on the grounds that `std.gpu.primitives.warp` exposes `sum` (every OTHER kernel this sweep
has fixed uses it) but no paired-argmax primitive: nothing that reduces a `(value, index)` pair
TOGETHER the way a bare `sum`/`max` reduces a scalar. `shuffle_xor` — importable directly from the
same `std.gpu.primitives.warp` module — is the candidate: call it once for the Float32 value and
once for the Int32 id, at the SAME `offset`, in the SAME butterfly step, and compare the two
shuffled-in values against the calling lane's own running best with the tie-break-to-lowest-id
clause `_argmax_reduce_kernel` already uses. This file checks, on real hardware, before any such
kernel is written:

1. Does `shuffle_xor` exist with a usable signature for both `Float32` (the value) and `Int32` (the
   id) at this pinned nightly? (`p1`..`p9` throwaway probes during development already answered
   this; re-confirmed here as this file's own self-contained check, not assumed from a prior
   session.)
2. Does a 5-step (`log2(32)`) lane butterfly, run identically by every lane so every lane ends the
   loop holding the SAME winning `(value, id)` pair (an all-reduce, matching `warp.sum`'s own
   broadcast-to-all-lanes behaviour), correctly reduce one 32-lane SIMD group?
3. Does the two-level combine (32-lane butterfly, then one shared-memory combine barrier across the
   `_SUBS = 8` groups) correctly reduce the WHOLE 256-thread block, including when `n` leaves some
   groups partially or entirely without a valid entry (the `_NEG_HUGE`/`-1` sentinel path)?
4. THE TIE-BREAK, explicitly, not incidentally: when the true maximum value is tied between two
   different ids, does the winner resolve to the LOWER id — matching `numpy.argmax`'s documented
   convention — in BOTH of the two genuinely different code paths a tie can be decided by (the
   intra-warp butterfly, when both tied entries land in the same 32-lane group, and the cross-group
   combine, when they land in different groups)?

Both candidates are checked against an independent host Float64 reference AND each other, on shapes
small enough to hand-verify, before any timing number from this file is trusted — same protocol
`sdpa_simd_reduce_probe.mojo`/`gemv_simd_reduce_probe.mojo`/`lmhead_argmax_simd_reduce_probe.mojo`
established.
"""

from std.origin import MutAnyOrigin  # Mojo 1.0.0: origins left std.builtin.type_aliases
from max.gpu.host import DeviceContext
from std.gpu import thread_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.gpu.primitives.warp import shuffle_xor
from std.gpu.globals import WARP_SIZE
from std.memory import stack_allocation
from std.sys import has_accelerator, is_defined
from std.time import perf_counter_ns

comptime PROBE_GPU_BUILD: Bool = is_defined["ALGENTA_GPU"]()

comptime _TG: Int = 256
"""The real production `_TG` from `residentk.kernels` — 256 threads for the ONE threadgroup
`_argmax_reduce_kernel`/`_argmax_reduce_kernel_simd` ever launch with (`grid_dim=1` always, at every
one of the four call sites in `residentk.session`)."""

comptime _LANES: Int = 32
"""The real production `_LANES` from `residentk.kernels` — Apple's SIMD width, re-confirmed on real
hardware below rather than re-assumed."""

comptime _SUBS: Int = _TG // _LANES
"""SIMD-groups spanned by one `_TG`-wide threadgroup: 8 — the real production `_SUBS`."""

comptime _NEG_HUGE: Float32 = -3.0e38
"""Same sentinel `residentk.kernels._NEG_HUGE` uses."""


def _argmax_combine_barrier_tree(
    out_val: UnsafePointer[Float32, origin=MutAnyOrigin],
    out_idx: UnsafePointer[Int32, origin=MutAnyOrigin],
    blk_val: UnsafePointer[Float32, origin=MutAnyOrigin],
    blk_idx: UnsafePointer[Int32, origin=MutAnyOrigin],
    n: Int,
):
    """The EXISTING mechanism, copied verbatim in structure from `_argmax_reduce_kernel` — a
    per-thread grid-stride local-best scan, then a `log2(_TG)`-level barrier-synchronized
    shared-memory halving tree with the tie-break-to-lowest-id clause at every level. Duplicated
    here (not imported — every sibling probe in this directory makes the same choice, so this file
    stays a from-scratch check rather than one that could pass by re-running the exact kernel under
    test) so this probe stands alone."""
    var sv = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var si = stack_allocation[_TG, DType.int32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var best = _NEG_HUGE
    var best_i = Int32(-1)
    var i = tid
    while i < n:
        if blk_val[i] > best:
            best = blk_val[i]
            best_i = blk_idx[i]
        i += _TG
    sv[tid] = best
    si[tid] = best_i
    barrier()

    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            var other = sv[tid + stride]
            var other_i = si[tid + stride]
            if other > sv[tid] or (other == sv[tid] and other_i >= 0 and (si[tid] < 0 or other_i < si[tid])):
                sv[tid] = other
                si[tid] = other_i
        barrier()
        stride //= 2

    if tid == 0:
        out_val[0] = sv[0]
        out_idx[0] = si[0]


def _argmax_combine_simd_shuffle(
    out_val: UnsafePointer[Float32, origin=MutAnyOrigin],
    out_idx: UnsafePointer[Int32, origin=MutAnyOrigin],
    blk_val: UnsafePointer[Float32, origin=MutAnyOrigin],
    blk_idx: UnsafePointer[Int32, origin=MutAnyOrigin],
    n: Int,
):
    """The CANDIDATE replacement: IDENTICAL per-thread grid-stride local-best scan, then a two-level
    combine — a 5-step `shuffle_xor` compare-exchange butterfly per 32-lane SIMD group (NO barrier;
    SIMD-group execution is lockstep by hardware construction), then ONE shared-memory combine
    barrier across the `_SUBS = 8` per-group winners, then thread 0 alone walks all 8 with the SAME
    tie-break clause. `log2(256) = 8` tree levels plus the tree's own leading write-visibility
    barrier — 9 barrier hits — collapse to 1."""
    var grp_v = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var grp_i = stack_allocation[_SUBS, DType.int32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    var best = _NEG_HUGE
    var best_i = Int32(-1)
    var i = tid
    while i < n:
        if blk_val[i] > best:
            best = blk_val[i]
            best_i = blk_idx[i]
        i += _TG

    var off = UInt32(_LANES // 2)
    while off > 0:
        var other_val = shuffle_xor(best, off)
        var other_idx = shuffle_xor(best_i, off)
        if other_val > best or (other_val == best and other_idx >= 0 and (best_i < 0 or other_idx < best_i)):
            best = other_val
            best_i = other_idx
        off //= 2

    if lane == 0:
        grp_v[sub] = best
        grp_i[sub] = best_i
    barrier()

    if tid == 0:
        var bv = grp_v[0]
        var bi = grp_i[0]
        for u in range(1, _SUBS):
            var other_val = grp_v[u]
            var other_idx = grp_i[u]
            if other_val > bv or (other_val == bv and other_idx >= 0 and (bi < 0 or other_idx < bi)):
                bv = other_val
                bi = other_idx
        out_val[0] = bv
        out_idx[0] = bi


def _host_argmax(vals: List[Float64], idxs: List[Int], n: Int, mut out_val: List[Float64], mut out_idx: List[Int]):
    """Pure-host Float64 reference — the SAME tie-break-to-lowest-id combine, applied by scanning
    once left to right. This combine (max value; on an exact tie, min id) is a genuine total-order
    maximum over `(value, id)` pairs, so it is associative and commutative: ANY scan order or
    reduction tree shape that applies the SAME per-pair rule at every combine step must produce this
    identical answer, which is exactly the property both device kernels above, and this host
    reference, are being checked against. Out-parameters, not a tuple return — the same discipline
    `lmhead_argmax_simd_reduce_probe.mojo`'s own `_host_block_argmax` uses."""
    var best = -1.0e30
    var best_i = -1
    for i in range(n):
        var v = vals[i]
        var idx = idxs[i]
        if v > best or (v == best and idx >= 0 and (best_i < 0 or idx < best_i)):
            best = v
            best_i = idx
    out_val.append(best)
    out_idx.append(best_i)


def _pseudo_vals(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2)
    return o^


def _pseudo_ids(n: Int, seed: Int) -> List[Int]:
    """Deliberately NOT equal to position `i` — a kernel bug that returned the array POSITION
    instead of the stored `blk_idx` VALUE would pass a same-as-position id scheme by accident and
    should not pass this one."""
    var o = List[Int](capacity=n)
    for i in range(n):
        o.append(((i * 997 + seed * 131) % 100000) + 1)
    return o^


def _run_case(ctx: DeviceContext, label: String, vals: List[Float64], ids: List[Int], n: Int) raises -> Bool:
    var host_val_l = List[Float64]()
    var host_idx_l = List[Int]()
    _host_argmax(vals, ids, n, host_val_l, host_idx_l)
    var host_val = host_val_l[0]
    var host_idx = host_idx_l[0]

    var vbuf = ctx.enqueue_create_buffer[DType.float32](n)
    var ibuf = ctx.enqueue_create_buffer[DType.int32](n)
    with vbuf.map_to_host() as h:
        for i in range(n):
            h[i] = Float32(vals[i])
    with ibuf.map_to_host() as h:
        for i in range(n):
            h[i] = Int32(ids[i])
    ctx.synchronize()

    var out_val_tree = ctx.enqueue_create_buffer[DType.float32](1)
    var out_idx_tree = ctx.enqueue_create_buffer[DType.int32](1)
    var out_val_shfl = ctx.enqueue_create_buffer[DType.float32](1)
    var out_idx_shfl = ctx.enqueue_create_buffer[DType.int32](1)
    var f_tree = ctx.compile_function_unchecked[_argmax_combine_barrier_tree]()
    var f_shfl = ctx.compile_function_unchecked[_argmax_combine_simd_shuffle]()

    ctx.enqueue_function_unchecked(
        f_tree, out_val_tree.unsafe_ptr(), out_idx_tree.unsafe_ptr(),
        vbuf.unsafe_ptr(), ibuf.unsafe_ptr(), n,
        grid_dim=1, block_dim=_TG,
    )
    ctx.enqueue_function_unchecked(
        f_shfl, out_val_shfl.unsafe_ptr(), out_idx_shfl.unsafe_ptr(),
        vbuf.unsafe_ptr(), ibuf.unsafe_ptr(), n,
        grid_dim=1, block_dim=_TG,
    )
    ctx.synchronize()

    var tv = Float64(0.0)
    var ti = 0
    var sv = Float64(0.0)
    var si = 0
    with out_val_tree.map_to_host() as h:
        tv = Float64(h[0])
    with out_idx_tree.map_to_host() as h:
        ti = Int(h[0])
    with out_val_shfl.map_to_host() as h:
        sv = Float64(h[0])
    with out_idx_shfl.map_to_host() as h:
        si = Int(h[0])

    var dt = tv - host_val
    if dt < 0.0:
        dt = -dt
    var ds = sv - host_val
    if ds < 0.0:
        ds = -ds
    var ok = dt < 1e-4 and ds < 1e-4 and ti == host_idx and si == host_idx
    print(
        "   ", label, " n=", n, " host=(", host_val, ",", host_idx, ")",
        " tree=(", tv, ",", ti, ")", " shfl=(", sv, ",", si, ")",
        "  ", "OK" if ok else "MISMATCH",
    )
    return ok


def main() raises:
    print("=== argmax-reduce kernel probe: barrier-tree vs SIMD-shuffle paired argmax ===")
    print("")

    if not PROBE_GPU_BUILD:
        print("Built WITHOUT -D ALGENTA_GPU: refusing to report anything (kernels compiled out).")
        return
    if not has_accelerator():
        print("No usable accelerator. Refusing to report anything.")
        return

    var ctx = DeviceContext()

    print("--- SIMD-group width check: confirm WARP_SIZE matches production's _LANES=32 ---")
    print("   std.gpu.globals.WARP_SIZE (compile-time, is_apple_gpu() branch) =", WARP_SIZE)
    if WARP_SIZE != _LANES:
        print("ASSUMPTION VIOLATED: production's _LANES=32 does not match this hardware. Stopping.")
        return
    print("   CONFIRMED: WARP_SIZE ==", _LANES)
    print("")

    print("--- correctness: general shapes (unique maxima, idle/partial groups exercised) ---")
    var all_ok = True
    all_ok = _run_case(ctx, "n=37  (not a multiple of _TG/_LANES/_SUBS; groups 2..7 fully idle)",
                        _pseudo_vals(37, 5), _pseudo_ids(37, 11), 37) and all_ok
    all_ok = _run_case(ctx, "n=250 (not a multiple of _TG; last _SUBS-group partially idle)",
                        _pseudo_vals(250, 9), _pseudo_ids(250, 23), 250) and all_ok
    all_ok = _run_case(ctx, "n=2048 (real production _LM_BLOCKS; 8 full grid-stride passes/thread)",
                        _pseudo_vals(2048, 13), _pseudo_ids(2048, 41), 2048) and all_ok
    print("")

    print("--- correctness: EXPLICIT tie-break, value tied across two different ids ---")
    # Same-warp tie: positions 3 and 10 both land in thread-group lanes 3 and 10 of SIMD-group 0
    # (grid-stride with n <= _TG means position == thread id == lane + 32*sub exactly), so this tie
    # is decided by the intra-warp shuffle_xor butterfly, not the cross-group combine.
    var same_warp_vals = _pseudo_vals(64, 71)
    var same_warp_ids = _pseudo_ids(64, 83)
    var tie_value = Float64(999.0)
    same_warp_vals[3] = tie_value
    same_warp_vals[10] = tie_value
    same_warp_ids[3] = 500000
    same_warp_ids[10] = 7
    all_ok = _run_case(ctx, "same-warp tie (lanes 3 & 10, ids 500000 vs 7, lower must win)",
                        same_warp_vals, same_warp_ids, 64) and all_ok

    # Cross-warp tie: positions 5 (SIMD-group 0, lane 5) and 200 (SIMD-group 6, lane 8) both land in
    # DIFFERENT 32-lane groups, so this tie can only be decided by the cross-group shared-memory
    # combine, not the intra-warp butterfly (each group's own butterfly sees only ONE of the two
    # tied entries).
    var cross_warp_vals = _pseudo_vals(256, 97)
    var cross_warp_ids = _pseudo_ids(256, 61)
    cross_warp_vals[5] = tie_value
    cross_warp_vals[200] = tie_value
    cross_warp_ids[5] = 900000
    cross_warp_ids[200] = 42
    all_ok = _run_case(ctx, "cross-warp tie (positions 5 & 200, ids 900000 vs 42, lower must win)",
                        cross_warp_vals, cross_warp_ids, 256) and all_ok
    print("")

    if not all_ok:
        print("CORRECTNESS FAILURE: refusing to report any timing number.")
        return

    print("--- timing: barrier-tree vs SIMD-shuffle, n=2048 (real production _LM_BLOCKS) ---")
    _time_case(ctx, 2048, 500)


def _median(mut s: List[Float64]) -> Float64:
    for i in range(1, len(s)):
        var key = s[i]
        var j = i - 1
        while j >= 0 and s[j] > key:
            s[j + 1] = s[j]
            j -= 1
        s[j + 1] = key
    return s[len(s) // 2]


def _time_case(ctx: DeviceContext, n: Int, reps: Int) raises:
    var vals64 = _pseudo_vals(n, 200)
    var ids64 = _pseudo_ids(n, 300)
    var vbuf = ctx.enqueue_create_buffer[DType.float32](n)
    var ibuf = ctx.enqueue_create_buffer[DType.int32](n)
    with vbuf.map_to_host() as h:
        for i in range(n):
            h[i] = Float32(vals64[i])
    with ibuf.map_to_host() as h:
        for i in range(n):
            h[i] = Int32(ids64[i])
    ctx.synchronize()

    var out_val_tree = ctx.enqueue_create_buffer[DType.float32](1)
    var out_idx_tree = ctx.enqueue_create_buffer[DType.int32](1)
    var out_val_shfl = ctx.enqueue_create_buffer[DType.float32](1)
    var out_idx_shfl = ctx.enqueue_create_buffer[DType.int32](1)
    var f_tree = ctx.compile_function_unchecked[_argmax_combine_barrier_tree]()
    var f_shfl = ctx.compile_function_unchecked[_argmax_combine_simd_shuffle]()

    for _ in range(5):
        ctx.enqueue_function_unchecked(
            f_tree, out_val_tree.unsafe_ptr(), out_idx_tree.unsafe_ptr(),
            vbuf.unsafe_ptr(), ibuf.unsafe_ptr(), n,
            grid_dim=1, block_dim=_TG,
        )
    ctx.synchronize()
    var samples_tree = List[Float64]()
    for _ in range(reps):
        var t0 = perf_counter_ns()
        ctx.enqueue_function_unchecked(
            f_tree, out_val_tree.unsafe_ptr(), out_idx_tree.unsafe_ptr(),
            vbuf.unsafe_ptr(), ibuf.unsafe_ptr(), n,
            grid_dim=1, block_dim=_TG,
        )
        ctx.synchronize()
        samples_tree.append(Float64(Int(perf_counter_ns() - t0)) / 1e3)
    var med_tree = _median(samples_tree)

    for _ in range(5):
        ctx.enqueue_function_unchecked(
            f_shfl, out_val_shfl.unsafe_ptr(), out_idx_shfl.unsafe_ptr(),
            vbuf.unsafe_ptr(), ibuf.unsafe_ptr(), n,
            grid_dim=1, block_dim=_TG,
        )
    ctx.synchronize()
    var samples_shfl = List[Float64]()
    for _ in range(reps):
        var t1 = perf_counter_ns()
        ctx.enqueue_function_unchecked(
            f_shfl, out_val_shfl.unsafe_ptr(), out_idx_shfl.unsafe_ptr(),
            vbuf.unsafe_ptr(), ibuf.unsafe_ptr(), n,
            grid_dim=1, block_dim=_TG,
        )
        ctx.synchronize()
        samples_shfl.append(Float64(Int(perf_counter_ns() - t1)) / 1e3)
    var med_shfl = _median(samples_shfl)

    print(
        "   [argmax_reduce] n=", n,
        " barrier_tree median of", reps, "=", med_tree, "us",
        "  simd_shuffle median =", med_shfl, "us",
        "  (", (med_shfl - med_tree) / med_tree * 100.0, "% vs barrier_tree)",
    )
