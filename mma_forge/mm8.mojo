"""mm8.mojo -- Phase 1 real MMA kernel. Weight-stationary tiled GEMM using Apple hardware
`simdgroup_matrix` 8x8 multiply-accumulate (`_mma_apple_8x8`), computing the same
`y[M,n] = xn[M,k] @ W^T[k,n]` semantics as the scalar oracle
`mojo/engine/residentk/kernels.mojo:_pf_gemm_assign_kernel_i8`, with `w` stored `[n,k]` row-major
(one output row's `k` coefficients contiguous) -- identical operand shapes and layout convention,
so the two kernels are directly diffable.

Deliberately flat (no package directory) and short-named: this module's own qualified name is the
mangled AIR prefix's budget-eater (empirically re-measured this session -- a `kernels.qkv_proj_
mma8x8` package path truncated the kernel's own name down to an ambiguous, collision-prone 5
characters; a bare `mm8` top-level module lets the full kernel name survive).

Reuses the oracle's `BM=32,BN=32,BK=16` tile shape and shared-memory cooperative-load/barrier
scaffold unchanged. What's genuinely new: the inner accumulate loop is per-SIMDGROUP (32 threads
cooperating on one 8x8 output sub-tile via `apple_mma_load_8x8`/`_mma_apple_8x8`/
`apple_mma_store_8x8`), not per-thread scalar register blocking. A 32x32 output tile is a 4x4 grid
of 8x8 sub-tiles (16 total); a 256-thread threadgroup is 8 simdgroups, so each simdgroup owns 2
sub-tiles (`sub_idx = sg` and `sub_idx = sg + 8`, flattened row-major over the 4x4 grid). Each
BK=16 shared-memory step runs 2 MMA sub-steps (BK/8), since the hardware primitive consumes 8 K
values at a time.

`_mma_apple_8x8` has NO transpose flag (unlike the M5-only 16x16x16 shape) -- the B operand must be
physically laid out `[K,N]` (K-rows, N-cols) for the fragment load to be a valid GEMM B matrix.
Since `w` is `[N,K]` in device memory, `b_tile` is written `[BK,BN]` (the TRANSPOSE of the scalar
oracle's own `[BN,BK]` b_tile) during the cooperative load -- the DEVICE READ stays the exact same
coalesced-by-row pattern the oracle already uses; only the SHARED-MEMORY write index changes,
standard practice for feeding a transpose-free compute stage.

PHASE 1 SCOPE, exactly as staged in the approved plan: correctness of the core MMA tiling only.
Partial-tile M/N padding (the scalar oracle's own zero-pad-and-bounds-check-on-store discipline) is
NOT yet implemented here -- this kernel currently REQUIRES `m_rows % 32 == 0` and `n % 32 == 0`.
`k` partial-tile padding on the LAST BK step IS handled (zero-padded on load, same as the oracle),
since that falls out naturally from the existing cooperative-load bounds check. Extending to
arbitrary M/N is deferred to whenever Phase 1's real GPU-counter measurement justifies Phase 2/3 --
see the plan's own staging rationale.

Uses fixed-width `Int64` scalar kernel arguments throughout (bare `Int`/`UInt` are REJECTED as GPU
kernel arguments on this toolchain, per Modular's own v1.0.0 release notes) and the checked
`ctx.compile_function`/`ctx.enqueue_function` forms (`compile_function_unchecked` was removed
before v1.0). Built with `DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer` --
state this pin explicitly; the cross-compiler ABI equivalence this whole mechanism relies on was
verified under that exact Xcode pin.
"""
from std.gpu import thread_idx, block_idx
from max.gpu.sync import barrier
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.math import exp
from max.gpu.compute.arch.mma_apple import (
    _mma_apple_8x8,
    apple_mma_load_8x8,
    apple_mma_store_8x8,
)

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _I8P = UnsafePointer[Int8, origin=MutAnyOrigin]

comptime _BM: Int64 = 32
comptime _BN: Int64 = 32
comptime _BK: Int64 = 16
comptime _NTHREADS: Int64 = 256
comptime _N_SUBTILES: Int64 = (_BM // 8) * (_BN // 8)
comptime _SUBTILES_PER_SG: Int64 = _N_SUBTILES // (_NTHREADS // 32)


def _qkv_proj_gemm_mma8x8(
    y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    var a_tile = stack_allocation[Int(_BM * _BK), DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[Int(_BK * _BN), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_tile_cols = (n + _BN - 1) // _BN
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM
    var block_col = tile_col * _BN

    var acc0 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc1 = SIMD[DType.float32, 2](0.0, 0.0)

    var n_steps = (k + _BK - 1) // _BK
    for step in range(n_steps):
        var a_elems = (_BM * _BK) // _NTHREADS
        for s in range(a_elems):
            var idx = tid + s * _NTHREADS
            var ar = idx // _BK
            var ac = idx % _BK
            var gr = block_row + ar
            var gc = step * _BK + ac
            a_tile[Int(idx)] = xn[Int(gr * k + gc)] if (gr < m_rows and gc < k) else Float32(0.0)

        var b_elems = (_BN * _BK) // _NTHREADS
        for s in range(b_elems):
            var idx2 = tid + s * _NTHREADS
            var br = idx2 // _BK
            var bc = idx2 % _BK
            var gr2 = block_col + br
            var gc2 = step * _BK + bc
            var val = Float32(w[Int(gr2 * k + gc2)]) * wscale[Int(gr2)] if (gr2 < n and gc2 < k) else Float32(0.0)
            # Transposed write vs. the scalar oracle's [BN,BK] b_tile: [BK,BN] here so
            # apple_mma_load_8x8 sees a valid [K,N]-oriented B operand (no transpose flag exists
            # for the 8x8 MMA primitive).
            b_tile[Int(bc * _BN + br)] = val

        barrier()

        for ksub in range(Int(_BK // 8)):
            for which in range(2):
                var sub_idx = sg + Int64(which) * 8
                var sub_row = sub_idx // 4
                var sub_col = sub_idx % 4
                var a_ptr = a_tile + Int(sub_row * 8 * _BK + Int64(ksub) * 8)
                var b_ptr = b_tile + Int(Int64(ksub) * 8 * _BN + sub_col * 8)
                var a_frag = apple_mma_load_8x8[DType.float32](a_ptr, Int(_BK))
                var b_frag = apple_mma_load_8x8[DType.float32](b_ptr, Int(_BN))
                if which == 0:
                    _mma_apple_8x8(acc0, a_frag, b_frag, acc0)
                else:
                    _mma_apple_8x8(acc1, a_frag, b_frag, acc1)

        barrier()

    for which in range(2):
        var sub_idx = sg + Int64(which) * 8
        var sub_row = sub_idx // 4
        var sub_col = sub_idx % 4
        var y_ptr = y + Int((block_row + sub_row * 8) * n + (block_col + sub_col * 8))
        if which == 0:
            apple_mma_store_8x8[DType.float32](y_ptr, Int(n), acc0)
        else:
            apple_mma_store_8x8[DType.float32](y_ptr, Int(n), acc1)


def _gemm_accum_mma8x8(
    y: _FP, x: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """MMA twin of `_pf_gemm_accum_kernel_i8`: `y[M,n] += x[M,k] @ W^T[k,n]`. Reused for BOTH
    o_proj and down_proj, exactly as the scalar oracle already is. Byte-for-byte
    `_qkv_proj_gemm_mma8x8` except the two accumulator fragments are SEEDED from the EXISTING `y`
    values (loaded via `apple_mma_load_8x8`, same per-lane fragment layout the store side already
    uses) instead of zero -- `_mma_apple_8x8`'s own `D = A@B + C` shape makes "+=" just "don't
    zero C," no separate add-back step needed after the k-loop."""
    var a_tile = stack_allocation[Int(_BM * _BK), DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[Int(_BK * _BN), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_tile_cols = (n + _BN - 1) // _BN
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM
    var block_col = tile_col * _BN

    var acc0 = apple_mma_load_8x8[DType.float32](
        y + Int(block_row + (sg // 4) * 8) * Int(n) + Int(block_col + (sg % 4) * 8), Int(n)
    )
    var acc1 = apple_mma_load_8x8[DType.float32](
        y + Int(block_row + ((sg + 8) // 4) * 8) * Int(n) + Int(block_col + ((sg + 8) % 4) * 8), Int(n)
    )

    var n_steps = (k + _BK - 1) // _BK
    for step in range(n_steps):
        var a_elems = (_BM * _BK) // _NTHREADS
        for s in range(a_elems):
            var idx = tid + s * _NTHREADS
            var ar = idx // _BK
            var ac = idx % _BK
            var gr = block_row + ar
            var gc = step * _BK + ac
            a_tile[Int(idx)] = x[Int(gr * k + gc)] if (gr < m_rows and gc < k) else Float32(0.0)

        var b_elems = (_BN * _BK) // _NTHREADS
        for s in range(b_elems):
            var idx2 = tid + s * _NTHREADS
            var br = idx2 // _BK
            var bc = idx2 % _BK
            var gr2 = block_col + br
            var gc2 = step * _BK + bc
            var val = Float32(w[Int(gr2 * k + gc2)]) * wscale[Int(gr2)] if (gr2 < n and gc2 < k) else Float32(0.0)
            b_tile[Int(bc * _BN + br)] = val

        barrier()

        for ksub in range(Int(_BK // 8)):
            for which in range(2):
                var sub_idx = sg + Int64(which) * 8
                var sub_row = sub_idx // 4
                var sub_col = sub_idx % 4
                var a_ptr = a_tile + Int(sub_row * 8 * _BK + Int64(ksub) * 8)
                var b_ptr = b_tile + Int(Int64(ksub) * 8 * _BN + sub_col * 8)
                var a_frag = apple_mma_load_8x8[DType.float32](a_ptr, Int(_BK))
                var b_frag = apple_mma_load_8x8[DType.float32](b_ptr, Int(_BN))
                if which == 0:
                    _mma_apple_8x8(acc0, a_frag, b_frag, acc0)
                else:
                    _mma_apple_8x8(acc1, a_frag, b_frag, acc1)

        barrier()

    for which in range(2):
        var sub_idx = sg + Int64(which) * 8
        var sub_row = sub_idx // 4
        var sub_col = sub_idx % 4
        var y_ptr = y + Int((block_row + sub_row * 8) * n + (block_col + sub_col * 8))
        if which == 0:
            apple_mma_store_8x8[DType.float32](y_ptr, Int(n), acc0)
        else:
            apple_mma_store_8x8[DType.float32](y_ptr, Int(n), acc1)


comptime _BN_NARROW: Int64 = 16
"""Halved N-tile width for `_gemm_accum_mma8x8_narrow` -- built to test an occupancy hypothesis for
an apparent o_proj/down_proj regression (`N=1024`, `n_tile_cols=32` at BN=32) against qkv_proj's
winning `n_tile_cols=64`: fewer, larger threadgroups might not give the hardware enough concurrent
simdgroups in flight to hide the MMA instruction's own pipeline latency. MEASURED RESULT, NOT
ADOPTED: re-running the comparison (this hypothesis was built to test) on a WARM GPU/driver state
showed the ORIGINAL o_proj/down_proj "regression" was itself a cold-first-run measurement artifact
-- the wide (BN=32) kernel wins 2.19x-2.22x on both shapes with NO tuning needed, and THIS narrow
variant measures WORSE than wide at both (o_proj: 2510 vs 3044 GFLOP/s; down_proj: 2507-2522 vs
3135 GFLOP/s) -- wide tiles suit this MMA kernel better, the opposite of the occupancy hypothesis.
Kept here, correctness-verified, as a real negative result rather than deleted -- not wired into
`mm8_driver.mojo`'s production blob extraction, so it never reaches the shipped binary."""


def _gemm_accum_mma8x8_narrow(
    y: _FP, x: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """Narrow-BN twin of `_gemm_accum_mma8x8` -- see `_BN_NARROW`'s own docstring for the
    occupancy hypothesis this tested AND the measurement that rejected it. Same math, same
    `y += x@W^T` semantics; only `_BN_NARROW` replaces `_BN`, and each simdgroup now owns exactly
    ONE subtile (no `which` loop)."""
    var a_tile = stack_allocation[Int(_BM * _BK), DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[Int(_BK * _BN_NARROW), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_tile_cols = (n + _BN_NARROW - 1) // _BN_NARROW
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM
    var block_col = tile_col * _BN_NARROW

    var sub_row = sg // 2
    var sub_col = sg % 2

    var acc = apple_mma_load_8x8[DType.float32](
        y + Int(block_row + sub_row * 8) * Int(n) + Int(block_col + sub_col * 8), Int(n)
    )

    var n_steps = (k + _BK - 1) // _BK
    for step in range(n_steps):
        var a_elems = (_BM * _BK) // _NTHREADS
        for s in range(a_elems):
            var idx = tid + s * _NTHREADS
            var ar = idx // _BK
            var ac = idx % _BK
            var gr = block_row + ar
            var gc = step * _BK + ac
            a_tile[Int(idx)] = x[Int(gr * k + gc)] if (gr < m_rows and gc < k) else Float32(0.0)

        var b_elems = (_BN_NARROW * _BK) // _NTHREADS
        for s in range(b_elems):
            var idx2 = tid + s * _NTHREADS
            var br = idx2 // _BK
            var bc = idx2 % _BK
            var gr2 = block_col + br
            var gc2 = step * _BK + bc
            var val = Float32(w[Int(gr2 * k + gc2)]) * wscale[Int(gr2)] if (gr2 < n and gc2 < k) else Float32(0.0)
            b_tile[Int(bc * _BN_NARROW + br)] = val

        barrier()

        for ksub in range(Int(_BK // 8)):
            var a_ptr = a_tile + Int(sub_row * 8 * _BK + Int64(ksub) * 8)
            var b_ptr = b_tile + Int(Int64(ksub) * 8 * _BN_NARROW + sub_col * 8)
            var a_frag = apple_mma_load_8x8[DType.float32](a_ptr, Int(_BK))
            var b_frag = apple_mma_load_8x8[DType.float32](b_ptr, Int(_BN_NARROW))
            _mma_apple_8x8(acc, a_frag, b_frag, acc)

        barrier()

    var y_ptr = y + Int((block_row + sub_row * 8) * n + (block_col + sub_col * 8))
    apple_mma_store_8x8[DType.float32](y_ptr, Int(n), acc)


def _swiglu_gemm_mma8x8(
    act: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n_ff: Int64
):
    """MMA twin of `_pf_gemm_swiglu_kernel_i8`: gate rows `[0,n_ff)` of `w`/`wscale`, up rows
    `[n_ff,2*n_ff)`, SwiGLU-combined on output (`act = (gate/(1+exp(-gate)))*up`). Same tiling as
    `_qkv_proj_gemm_mma8x8`, but each simdgroup's 2 owned subtiles now carry FOUR accumulator
    fragments (gate0/up0, gate1/up1) instead of two, and each step loads TWO transposed B-tiles
    against the SAME loaded `xn` A-tile -- the identical "stage the activation once, read it
    twice" reuse the scalar oracle's own docstring names, register-tiled via MMA fragments
    instead of per-thread scalars. The SiLU/SwiGLU combine is a plain elementwise expression on
    the two 2-element accumulator fragments, computed right before the store -- MMA fragments are
    just data once the hardware op is done, nothing about `apple_mma_store_8x8` requires the
    stored values to be the raw accumulator."""
    var a_tile = stack_allocation[Int(_BM * _BK), DType.float32, address_space = AddressSpace.SHARED]()
    var bg_tile = stack_allocation[Int(_BK * _BN), DType.float32, address_space = AddressSpace.SHARED]()
    var bu_tile = stack_allocation[Int(_BK * _BN), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_tile_cols = (n_ff + _BN - 1) // _BN
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM
    var block_col = tile_col * _BN

    var acc_g0 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc_g1 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc_u0 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc_u1 = SIMD[DType.float32, 2](0.0, 0.0)

    var n_steps = (k + _BK - 1) // _BK
    for step in range(n_steps):
        var a_elems = (_BM * _BK) // _NTHREADS
        for s in range(a_elems):
            var idx = tid + s * _NTHREADS
            var ar = idx // _BK
            var ac = idx % _BK
            var gr = block_row + ar
            var gc = step * _BK + ac
            a_tile[Int(idx)] = xn[Int(gr * k + gc)] if (gr < m_rows and gc < k) else Float32(0.0)

        var b_elems = (_BN * _BK) // _NTHREADS
        for s in range(b_elems):
            var idx2 = tid + s * _NTHREADS
            var br = idx2 // _BK
            var bc = idx2 % _BK
            var gr2 = block_col + br
            var gc2 = step * _BK + bc
            if gr2 < n_ff and gc2 < k:
                bg_tile[Int(bc * _BN + br)] = Float32(w[Int(gr2 * k + gc2)]) * wscale[Int(gr2)]
                bu_tile[Int(bc * _BN + br)] = Float32(w[Int((n_ff + gr2) * k + gc2)]) * wscale[Int(n_ff + gr2)]
            else:
                bg_tile[Int(bc * _BN + br)] = Float32(0.0)
                bu_tile[Int(bc * _BN + br)] = Float32(0.0)

        barrier()

        for ksub in range(Int(_BK // 8)):
            for which in range(2):
                var sub_idx = sg + Int64(which) * 8
                var sub_row = sub_idx // 4
                var sub_col = sub_idx % 4
                var a_ptr = a_tile + Int(sub_row * 8 * _BK + Int64(ksub) * 8)
                var bg_ptr = bg_tile + Int(Int64(ksub) * 8 * _BN + sub_col * 8)
                var bu_ptr = bu_tile + Int(Int64(ksub) * 8 * _BN + sub_col * 8)
                var a_frag = apple_mma_load_8x8[DType.float32](a_ptr, Int(_BK))
                var bg_frag = apple_mma_load_8x8[DType.float32](bg_ptr, Int(_BN))
                var bu_frag = apple_mma_load_8x8[DType.float32](bu_ptr, Int(_BN))
                if which == 0:
                    _mma_apple_8x8(acc_g0, a_frag, bg_frag, acc_g0)
                    _mma_apple_8x8(acc_u0, a_frag, bu_frag, acc_u0)
                else:
                    _mma_apple_8x8(acc_g1, a_frag, bg_frag, acc_g1)
                    _mma_apple_8x8(acc_u1, a_frag, bu_frag, acc_u1)

        barrier()

    for which in range(2):
        var sub_idx = sg + Int64(which) * 8
        var sub_row = sub_idx // 4
        var sub_col = sub_idx % 4
        var act_ptr = act + Int((block_row + sub_row * 8) * n_ff + (block_col + sub_col * 8))
        var g = acc_g0 if which == 0 else acc_g1
        var u = acc_u0 if which == 0 else acc_u1
        var combined = SIMD[DType.float32, 2](
            (g[0] / (1.0 + exp(-g[0]))) * u[0],
            (g[1] / (1.0 + exp(-g[1]))) * u[1],
        )
        apple_mma_store_8x8[DType.float32](act_ptr, Int(n_ff), combined)
