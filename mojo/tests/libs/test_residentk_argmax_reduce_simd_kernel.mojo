"""test_residentk_argmax_reduce_simd_kernel.mojo — the ARGMAX-REDUCE-reduction-mechanism kernel pair
(`_argmax_reduce_kernel`/`_argmax_reduce_kernel_simd`), isolated at the KERNEL level from everything
else `residentk` does, following `test_residentk_sdpa_simd_kernel.mojo`'s/
`test_residentk_gemv_simd_kernel.mojo`'s/`test_residentk_lmhead_simd_kernel.mojo`'s own pattern
exactly (a dedicated, narrow, kernel-only suite, not folded into `test_residentk_session.mojo`'s big
shared model fixture).

WHY A SEPARATE FIXTURE
--------------------------
`_argmax_reduce_kernel` is the LAST kernel in the decode-path reduction-mechanism sweep PR #510
named — the single-threadgroup (`grid_dim=1`, `block_dim=_TG=256`) dispatch that collapses
`_lmhead_argmax_kernel`'s `n = _LM_BLOCKS = 2048` per-threadgroup `(logit, id)` pairs down to the
one pair the host reads as 8 bytes. It has no weight matrix, no KV cache, and no per-dtype twin
(`_argmax_reduce_kernel` is shared verbatim across every weight-precision arm — Float32, `_f16`,
`_i8`, `_i4` — see that kernel's own docstring and `metaldispatch.session`'s module docstring, which
says so explicitly), so this file's own fixture is just two parallel `List[Float64]` arrays (values,
ids), independent of every other kernel's shapes.

Checked against an INDEPENDENT host Float64 reference AND against each other
------------------------------------------------------------------------------
Same `blk_val`/`blk_idx` inputs, same `n`, both kernels' single `(out_val[0], out_idx[0])` output
compared to a pure-host Float64 reference (`_host_argmax` below) that scans once, left to right,
applying the SAME tie-break-to-lowest-id combine rule at every step. That combine (max value; on an
exact tie, min id) is a genuine total-order maximum over `(value, id)` pairs, so it is associative
and commutative — ANY scan order or reduction-tree shape that applies the SAME per-pair rule at
every combine step must agree with the host reference exactly, which is precisely the property this
file's three-way comparison (barrier-tree, SIMD-shuffle, host reference) checks.

Values are compared with a tight Float32-unit-roundoff bound (this kernel does no arithmetic beyond
comparisons — no accumulation, no dequantization — so an exact match modulo the Float32<->Float64
storage round-trip is expected); winning INDICES are compared for EXACT equality, including in the
two EXPLICIT tie-break cases below, where an inexact match would mean the wrong token was chosen.

THE TIE-BREAK, EXPLICITLY, IN BOTH CODE PATHS A TIE CAN BE DECIDED BY
---------------------------------------------------------------------------
`_argmax_reduce_kernel_simd`'s combine has two genuinely different levels — a 32-lane
`shuffle_xor` butterfly, then an 8-way cross-group combine — and a tie between two candidates
resolves differently depending on which level decides it:
  - SAME-WARP tie: both tied entries land in the SAME 32-lane SIMD group (case `n=64`, positions 3
    and 10, both lanes of group 0) — decided entirely by the intra-warp butterfly.
  - CROSS-WARP tie: the two tied entries land in DIFFERENT SIMD groups (case `n=256`, positions 5
    and 200, groups 0 and 6) — each group's own butterfly sees only ONE of the two, so the tie can
    ONLY be decided by the cross-group shared-memory combine.
Both cases assign the tied value to ids that are NOT equal to their array position (a kernel bug
that returned the array position instead of the stored `blk_idx` value would otherwise pass by
accident), and check that the LOWER id wins — `numpy.argmax`'s documented convention, and the one
`llmk.generate.greedy_argmax_flat` follows.
"""

from max.gpu.host import DeviceContext
from std.sys import has_accelerator
from residentk.session import RESIDENT_GPU_BUILD
from residentk.kernels import (
    _argmax_reduce_kernel,
    _argmax_reduce_kernel_simd,
    _TG,
)


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_vals(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        o.append(Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2)
    return o^


def _pseudo_ids(n: Int, seed: Int) -> List[Int]:
    """Deliberately NOT equal to position `i` — see the module docstring's tie-break section."""
    var o = List[Int](capacity=n)
    for i in range(n):
        o.append(((i * 997 + seed * 131) % 100000) + 1)
    return o^


def _host_argmax(vals: List[Float64], idxs: List[Int], n: Int, mut out_val: List[Float64], mut out_idx: List[Int]):
    """Pure-host Float64 reference — the SAME tie-break-to-lowest-id combine both device kernels
    use, applied by scanning once left to right. See the module docstring for why this is a genuine
    total-order maximum (associative, commutative), so ANY reduction order must agree with it.
    Out-parameters, not a tuple return -- the same discipline
    `argmax_reduce_simd_reduce_probe.mojo`'s own `_host_argmax` uses."""
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


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    @parameter
    if not RESIDENT_GPU_BUILD:
        passed += 1
        print("  ✅ built without -D ALGENTA_GPU: no argmax-reduce-simd kernels compiled, nothing to run")
        print("  [residentk.kernels argmax-reduce-simd-isolated] Passed:", passed, "Failed:", failed)
    else:
        if not has_accelerator():
            passed += 1
            print("  ✅ GPU build, no accelerator: nothing to run at kernel level either")
            print("  [residentk.kernels argmax-reduce-simd-isolated] Passed:", passed, "Failed:", failed)
            return

        var ctx = DeviceContext()

        # Mojo 1.0.0: the checked parameter form is the only launch spelling
        # (`enqueue_function_unchecked` and the `compile_function` handle are removed);
        # the Int scalar widens to the kernels' fixed-width Int64 DevicePassable parameter.

        # ── general shapes: unique maxima, idle/partial SIMD groups exercised ──────────────────
        var n_cases = List[Int]()
        n_cases.append(37)    # not a multiple of _TG/_LANES/_SUBS; groups 2..7 fully idle
        n_cases.append(250)   # not a multiple of _TG; last _SUBS-group partially idle
        n_cases.append(2048)  # real production _LM_BLOCKS; 8 full grid-stride passes/thread

        for case_i in range(len(n_cases)):
            var n = n_cases[case_i]
            var vals = _pseudo_vals(n, 5 + case_i * 19)
            var ids = _pseudo_ids(n, 11 + case_i * 23)
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
            var out_val_simd = ctx.enqueue_create_buffer[DType.float32](1)
            var out_idx_simd = ctx.enqueue_create_buffer[DType.int32](1)

            ctx.enqueue_function[_argmax_reduce_kernel](
                out_val_tree.unsafe_ptr(), out_idx_tree.unsafe_ptr(),
                vbuf.unsafe_ptr(), ibuf.unsafe_ptr(), Int64(n),
                grid_dim=1, block_dim=_TG,
            )
            ctx.enqueue_function[_argmax_reduce_kernel_simd](
                out_val_simd.unsafe_ptr(), out_idx_simd.unsafe_ptr(),
                vbuf.unsafe_ptr(), ibuf.unsafe_ptr(), Int64(n),
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
            with out_val_simd.map_to_host() as h:
                sv = Float64(h[0])
            with out_idx_simd.map_to_host() as h:
                si = Int(h[0])

            var bound = 1.0e-4
            var dt = _abs64(tv - host_val)
            var ds = _abs64(sv - host_val)
            var idx_ok = ti == host_idx and si == host_idx
            var ok = dt <= bound and ds <= bound and idx_ok
            print("  •  n=", n, " host=(", host_val, ",", host_idx, ")",
                  " tree=(", tv, ",", ti, ")", " simd=(", sv, ",", si, ")")
            if ok:
                passed += 1
            else:
                failed += 1
                print("  ❌ n=", n, ": value delta exceeds", bound, "or an argmax index disagreed")

        # ── EXPLICIT tie-break: same-warp (intra-warp butterfly decides) ──────────────────────
        var same_warp_vals = _pseudo_vals(64, 71)
        var same_warp_ids = _pseudo_ids(64, 83)
        var tie_value = Float64(999.0)
        same_warp_vals[3] = tie_value
        same_warp_vals[10] = tie_value
        same_warp_ids[3] = 500000
        same_warp_ids[10] = 7
        var sw_host_val_l = List[Float64]()
        var sw_host_idx_l = List[Int]()
        _host_argmax(same_warp_vals, same_warp_ids, 64, sw_host_val_l, sw_host_idx_l)
        var sw_host_idx = sw_host_idx_l[0]
        if sw_host_idx != 7:
            failed += 1
            print("  ❌ TEST BUG: host reference itself did not pick the lower id 7 for the same-warp tie")
        else:
            var vbuf2 = ctx.enqueue_create_buffer[DType.float32](64)
            var ibuf2 = ctx.enqueue_create_buffer[DType.int32](64)
            with vbuf2.map_to_host() as h:
                for i in range(64):
                    h[i] = Float32(same_warp_vals[i])
            with ibuf2.map_to_host() as h:
                for i in range(64):
                    h[i] = Int32(same_warp_ids[i])
            ctx.synchronize()
            var otv2 = ctx.enqueue_create_buffer[DType.float32](1)
            var oti2 = ctx.enqueue_create_buffer[DType.int32](1)
            var osv2 = ctx.enqueue_create_buffer[DType.float32](1)
            var osi2 = ctx.enqueue_create_buffer[DType.int32](1)
            ctx.enqueue_function[_argmax_reduce_kernel](
                otv2.unsafe_ptr(), oti2.unsafe_ptr(), vbuf2.unsafe_ptr(), ibuf2.unsafe_ptr(), Int64(64),
                grid_dim=1, block_dim=_TG,
            )
            ctx.enqueue_function[_argmax_reduce_kernel_simd](
                osv2.unsafe_ptr(), osi2.unsafe_ptr(), vbuf2.unsafe_ptr(), ibuf2.unsafe_ptr(), Int64(64),
                grid_dim=1, block_dim=_TG,
            )
            ctx.synchronize()
            var ti2 = 0
            var si2 = 0
            with oti2.map_to_host() as h:
                ti2 = Int(h[0])
            with osi2.map_to_host() as h:
                si2 = Int(h[0])
            print("  •  same-warp tie (lanes 3 & 10, ids 500000 vs 7): tree_id=", ti2, " simd_id=", si2,
                  " expected=7")
            if ti2 == 7 and si2 == 7:
                passed += 1
            else:
                failed += 1
                print("  ❌ same-warp tie: expected id 7 (the lower of the two tied ids) to win")

        # ── EXPLICIT tie-break: cross-warp (cross-group shared-memory combine decides) ─────────
        var cross_warp_vals = _pseudo_vals(256, 97)
        var cross_warp_ids = _pseudo_ids(256, 61)
        cross_warp_vals[5] = tie_value
        cross_warp_vals[200] = tie_value
        cross_warp_ids[5] = 900000
        cross_warp_ids[200] = 42
        var cw_host_val_l = List[Float64]()
        var cw_host_idx_l = List[Int]()
        _host_argmax(cross_warp_vals, cross_warp_ids, 256, cw_host_val_l, cw_host_idx_l)
        var cw_host_idx = cw_host_idx_l[0]
        if cw_host_idx != 42:
            failed += 1
            print("  ❌ TEST BUG: host reference itself did not pick the lower id 42 for the cross-warp tie")
        else:
            var vbuf3 = ctx.enqueue_create_buffer[DType.float32](256)
            var ibuf3 = ctx.enqueue_create_buffer[DType.int32](256)
            with vbuf3.map_to_host() as h:
                for i in range(256):
                    h[i] = Float32(cross_warp_vals[i])
            with ibuf3.map_to_host() as h:
                for i in range(256):
                    h[i] = Int32(cross_warp_ids[i])
            ctx.synchronize()
            var otv3 = ctx.enqueue_create_buffer[DType.float32](1)
            var oti3 = ctx.enqueue_create_buffer[DType.int32](1)
            var osv3 = ctx.enqueue_create_buffer[DType.float32](1)
            var osi3 = ctx.enqueue_create_buffer[DType.int32](1)
            ctx.enqueue_function[_argmax_reduce_kernel](
                otv3.unsafe_ptr(), oti3.unsafe_ptr(), vbuf3.unsafe_ptr(), ibuf3.unsafe_ptr(), Int64(256),
                grid_dim=1, block_dim=_TG,
            )
            ctx.enqueue_function[_argmax_reduce_kernel_simd](
                osv3.unsafe_ptr(), osi3.unsafe_ptr(), vbuf3.unsafe_ptr(), ibuf3.unsafe_ptr(), Int64(256),
                grid_dim=1, block_dim=_TG,
            )
            ctx.synchronize()
            var ti3 = 0
            var si3 = 0
            with oti3.map_to_host() as h:
                ti3 = Int(h[0])
            with osi3.map_to_host() as h:
                si3 = Int(h[0])
            print("  •  cross-warp tie (positions 5 & 200, ids 900000 vs 42): tree_id=", ti3, " simd_id=", si3,
                  " expected=42")
            if ti3 == 42 and si3 == 42:
                passed += 1
            else:
                failed += 1
                print("  ❌ cross-warp tie: expected id 42 (the lower of the two tied ids) to win")

        if failed == 0:
            print("  ✅ argmax_reduce: barrier-tree and SIMD-shuffle agree with the host reference",
                  "and each other on VALUE, and EXACTLY on the winning index, across general shapes",
                  "AND both explicit same-warp/cross-warp tie-break cases")

        print("  [residentk.kernels argmax-reduce-simd-isolated] Passed:", passed, "Failed:", failed)
