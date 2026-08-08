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

PARTIAL-TILE M/N: the shared-memory A/B tiles are ALREADY zero-padded for out-of-range rows/cols
during the cooperative load (`if (gr < m_rows and gc < k) else 0.0`, etc.) regardless of whether
`m_rows`/`n` are multiples of 32 -- the accumulate math itself has never needed the alignment
restriction. The real gap was the FINAL STORE (and, for the accum kernel, the seed load): both used
`apple_mma_store_8x8`/`apple_mma_load_8x8` unconditionally, which have no masked form and will
write/read past a buffer sized to the real (unaligned) `m_rows`/`n`. Fixed by computing each lane's
own (row, col) via `_frag_row_col` (the same per-lane mapping those library functions use
internally, ground-truthed via Metal `thread_elements()` per the reference this was built from) and
checking `r < m_rows` / `c < n` per element before reading or writing it directly -- the identical
bounds-check discipline the scalar oracle itself already uses on its own final store. Verified
against the scalar oracles at a wide sweep of non-32-aligned `(M,K,N)` shapes, not just tile-aligned
ones (`mma_forge/probes/correctness_probe_partial.mojo`).

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

comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
comptime _I8P = UnsafePointer[Int8, origin=MutAnyOrigin]

comptime _BM: Int64 = 32
comptime _BN: Int64 = 32
comptime _BK: Int64 = 16
comptime _NTHREADS: Int64 = 256
comptime _N_SUBTILES: Int64 = (_BM // 8) * (_BN // 8)
comptime _SUBTILES_PER_SG: Int64 = _N_SUBTILES // (_NTHREADS // 32)


def _frag_row_col(tid: Int64) -> SIMD[DType.int64, 2]:
    """This lane's (row, col_base) within its 8x8 fragment -- the SAME per-lane mapping
    `apple_mma_load_8x8`/`apple_mma_store_8x8` use internally via `lane_id()`, computed locally
    here (not imported) because a bounds-checked, partial-tile-safe store needs to know which two
    (row, col) positions THIS lane owns and test them individually; neither library function has a
    masked-store form. `lane_id() == tid % 32` for a linear threadgroup organized as consecutive
    32-thread simdgroups, the layout every kernel in this file already assumes."""
    var lane = tid % 32
    var row_lo = ((lane & 6) >> 1) + ((lane & 16) >> 2)
    var col_base = ((lane & 1) << 1) + ((lane & 8) >> 1)
    return SIMD[DType.int64, 2](row_lo, col_base)


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

    var rc = _frag_row_col(tid)
    for which in range(2):
        var sub_idx = sg + Int64(which) * 8
        var sub_row = sub_idx // 4
        var sub_col = sub_idx % 4
        var frag = acc0 if which == 0 else acc1
        var r = block_row + sub_row * 8 + rc[0]
        var c0 = block_col + sub_col * 8 + rc[1]
        var c1 = c0 + 1
        if r < m_rows and c0 < n:
            y[Int(r * n + c0)] = frag[0]
        if r < m_rows and c1 < n:
            y[Int(r * n + c1)] = frag[1]


def _gemm_accum_mma8x8(
    y: _FP, x: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """MMA twin of `_pf_gemm_accum_kernel_i8`: `y[M,n] += x[M,k] @ W^T[k,n]`. Reused for BOTH
    o_proj and down_proj, exactly as the scalar oracle already is. Byte-for-byte
    `_qkv_proj_gemm_mma8x8` except the two accumulator fragments are SEEDED from the EXISTING `y`
    values instead of zero (bounds-checked per element via `_frag_row_col`, same as the final store
    -- a stale `y` read past `m_rows`/`n` would be a memory-safety issue even though its result is
    never stored back) -- `_mma_apple_8x8`'s own `D = A@B + C` shape makes "+=" just "don't zero C,"
    no separate add-back step needed after the k-loop."""
    var a_tile = stack_allocation[Int(_BM * _BK), DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[Int(_BK * _BN), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_tile_cols = (n + _BN - 1) // _BN
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM
    var block_col = tile_col * _BN

    var rc_seed = _frag_row_col(tid)
    var r0 = block_row + (sg // 4) * 8 + rc_seed[0]
    var c0_0 = block_col + (sg % 4) * 8 + rc_seed[1]
    var c0_1 = c0_0 + 1
    var acc0 = SIMD[DType.float32, 2](
        y[Int(r0 * n + c0_0)] if (r0 < m_rows and c0_0 < n) else Float32(0.0),
        y[Int(r0 * n + c0_1)] if (r0 < m_rows and c0_1 < n) else Float32(0.0),
    )
    var r1 = block_row + ((sg + 8) // 4) * 8 + rc_seed[0]
    var c1_0 = block_col + ((sg + 8) % 4) * 8 + rc_seed[1]
    var c1_1 = c1_0 + 1
    var acc1 = SIMD[DType.float32, 2](
        y[Int(r1 * n + c1_0)] if (r1 < m_rows and c1_0 < n) else Float32(0.0),
        y[Int(r1 * n + c1_1)] if (r1 < m_rows and c1_1 < n) else Float32(0.0),
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

    var rc = _frag_row_col(tid)
    for which in range(2):
        var sub_idx = sg + Int64(which) * 8
        var sub_row = sub_idx // 4
        var sub_col = sub_idx % 4
        var frag = acc0 if which == 0 else acc1
        var r = block_row + sub_row * 8 + rc[0]
        var c0 = block_col + sub_col * 8 + rc[1]
        var c1 = c0 + 1
        if r < m_rows and c0 < n:
            y[Int(r * n + c0)] = frag[0]
        if r < m_rows and c1 < n:
            y[Int(r * n + c1)] = frag[1]


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

    var rc = _frag_row_col(tid)
    for which in range(2):
        var sub_idx = sg + Int64(which) * 8
        var sub_row = sub_idx // 4
        var sub_col = sub_idx % 4
        var g = acc_g0 if which == 0 else acc_g1
        var u = acc_u0 if which == 0 else acc_u1
        var combined = SIMD[DType.float32, 2](
            (g[0] / (1.0 + exp(-g[0]))) * u[0],
            (g[1] / (1.0 + exp(-g[1]))) * u[1],
        )
        var r = block_row + sub_row * 8 + rc[0]
        var c0 = block_col + sub_col * 8 + rc[1]
        var c1 = c0 + 1
        if r < m_rows and c0 < n_ff:
            act[Int(r * n_ff + c0)] = combined[0]
        if r < m_rows and c1 < n_ff:
            act[Int(r * n_ff + c1)] = combined[1]


def _qkv_proj_gemm_mma8x8_f16(
    y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """GEMM tournament Phase 0 isolation experiment (REALRACE_RESULTS.md, 2026-08-07 entry): an
    F16-MMA-operand variant of `_qkv_proj_gemm_mma8x8` above, changing EXACTLY ONE thing relative
    to it -- the dtype of the shared-memory tiles the hardware MMA op actually consumes -- to
    isolate the "MMA operand width, not storage bandwidth, is the lever" hypothesis that entry's
    roofline analysis raised but did not yet test.

    Identical `BM=32/BN=32/BK=16` tile shape, identical grid/threadgroup layout, identical
    shared-memory cooperative-load/barrier structure, identical Int8 storage with per-output-row
    dequant happening on load (`Float32(w[idx]) * wscale[row]`) -- Algenta's real 2x
    storage-bandwidth advantage stays fully intact, upstream of the tile, exactly as before. The
    ONLY change: `a_tile`/`b_tile` are declared `DType.float16` instead of `DType.float32`, so the
    already-dequantized-to-Float32 weight value and the Float32 activation value are each narrowed
    one further step -- to `Float16` -- at the moment they are written into shared memory. The MMA
    dispatch changes in lockstep (`apple_mma_load_8x8[DType.float16]` instead of `[DType.float32]`,
    consuming those half tiles), which is what actually selects Apple's hardware
    `simdgroup_half8x8` op over `simdgroup_float8x8` -- mirroring llama.cpp's own
    `kernel_mul_mm_f16_f32` scheme (both operands narrowed to `half` right before the multiply).
    The accumulator type is UNCHANGED: `SIMD[DType.float32, 2]`, exactly as
    `_qkv_proj_gemm_mma8x8` already uses -- mixed-precision multiply, full-precision accumulate,
    the same scheme llama.cpp uses (`half` operands accumulating into `simdgroup_float8x8`) and the
    same pattern already proven to compose in this repo by a different kernel family
    (`attention_forge/parity_replica.mojo`'s own QK^T/PV MMA calls: `apple_mma_load_8x8[DType.
    float16]` fragments accumulated into `SIMD[DType.float32, 2]`/`SIMD[DType.float32, 2]`-backed
    fragments via `apple_mma_store_8x8[DType.float32]`) -- so this is not a hypothetical composition,
    it is reused, already-working precedent from this same codebase.

    Every other line -- grid/tile-column indexing, the accumulate loop's `ksub`/`which` structure,
    the final bounds-checked store via `_frag_row_col` -- is byte-for-byte identical to
    `_qkv_proj_gemm_mma8x8`. `_qkv_proj_gemm_mma8x8` itself is left completely untouched above;
    this is a pure addition."""
    var a_tile = stack_allocation[Int(_BM * _BK), DType.float16, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[Int(_BK * _BN), DType.float16, address_space = AddressSpace.SHARED]()

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
            a_tile[Int(idx)] = Float16(xn[Int(gr * k + gc)]) if (gr < m_rows and gc < k) else Float16(0.0)

        var b_elems = (_BN * _BK) // _NTHREADS
        for s in range(b_elems):
            var idx2 = tid + s * _NTHREADS
            var br = idx2 // _BK
            var bc = idx2 % _BK
            var gr2 = block_col + br
            var gc2 = step * _BK + bc
            var val = Float16(Float32(w[Int(gr2 * k + gc2)]) * wscale[Int(gr2)]) if (gr2 < n and gc2 < k) else Float16(0.0)
            # Same transposed-write convention as `_qkv_proj_gemm_mma8x8`'s own b_tile -- only the
            # element dtype (Float16 vs Float32) differs; the index math is identical.
            b_tile[Int(bc * _BN + br)] = val

        barrier()

        for ksub in range(Int(_BK // 8)):
            for which in range(2):
                var sub_idx = sg + Int64(which) * 8
                var sub_row = sub_idx // 4
                var sub_col = sub_idx % 4
                var a_ptr = a_tile + Int(sub_row * 8 * _BK + Int64(ksub) * 8)
                var b_ptr = b_tile + Int(Int64(ksub) * 8 * _BN + sub_col * 8)
                var a_frag = apple_mma_load_8x8[DType.float16](a_ptr, Int(_BK))
                var b_frag = apple_mma_load_8x8[DType.float16](b_ptr, Int(_BN))
                if which == 0:
                    _mma_apple_8x8(acc0, a_frag, b_frag, acc0)
                else:
                    _mma_apple_8x8(acc1, a_frag, b_frag, acc1)

        barrier()

    var rc = _frag_row_col(tid)
    for which in range(2):
        var sub_idx = sg + Int64(which) * 8
        var sub_row = sub_idx // 4
        var sub_col = sub_idx % 4
        var frag = acc0 if which == 0 else acc1
        var r = block_row + sub_row * 8 + rc[0]
        var c0 = block_col + sub_col * 8 + rc[1]
        var c1 = c0 + 1
        if r < m_rows and c0 < n:
            y[Int(r * n + c0)] = frag[0]
        if r < m_rows and c1 < n:
            y[Int(r * n + c1)] = frag[1]


comptime _BM_W: Int64 = 32
comptime _BN_W: Int64 = 64
comptime _BK_W: Int64 = 32
comptime _NTHREADS_W: Int64 = 128
comptime _SUBROWS_W: Int64 = _BM_W // 8
comptime _SUBCOLS_W: Int64 = _BN_W // 8
comptime _N_SUBTILES_W: Int64 = _SUBROWS_W * _SUBCOLS_W
comptime _SUBTILES_PER_SG_W: Int64 = _N_SUBTILES_W // (_NTHREADS_W // 32)
"""Tile-shape tournament axis (REALRACE_RESULTS.md, GEMM tournament Phase 0 entry, 2026-08-07): the
F16-MMA-operand isolation experiment (`_qkv_proj_gemm_mma8x8_f16` above) REFUTED the "MMA operand
width is the lever" hypothesis (did not close the gap; ~14% SLOWER on average than this file's own
F32 `_qkv_proj_gemm_mma8x8`, never beat llama.cpp). That entry's own recorded next step was the
remaining, already-documented axis: TILE SHAPE / THREADGROUP ORGANIZATION. This constant block and
`_qkv_proj_gemm_mma8x8_wide` below are that experiment -- Int8-storage-dequant-to-F32 kept EXACTLY
as `_qkv_proj_gemm_mma8x8` (the F16 operand change is NOT combined here, to avoid confounding two
hypotheses in one measurement), tile shape is the ONLY variable under test.

GEOMETRY, RE-DERIVED DIRECTLY FROM THE VENDORED LLAMA.CPP SOURCE (not taken on faith from any prior
summary): `benchmarks/competitors/llama_cpp/upstream_src/ggml-metal.metal`'s `kernel_mul_mm` has TWO
template bodies gated by `#ifdef GGML_METAL_HAS_TENSOR` (line 10026) -- an Apple-tensor-hardware path
(line 10032, M5-generation `mpp::tensor_ops::matmul2d`) and a legacy `simdgroup_matrix`-only `#else`
path (line 10157). `ggml-metal-device.cpp`'s `ggml_metal_library_get_pipeline_mul_mm` (line 704)
picks `res.nr0=64, res.nr1=32` for the `!has_tensor` branch (line 754-758) -- confirmed as the active
branch on this M4 Max by this session's own prior research (Apple's `mpp::tensor_ops` tensor-matmul
API requires newer-than-M4 GPU family; this repo's own `reference_mojo_gpu_timing_gap.md`/session
notes already established Mojo's own MMA primitive here tops out at 8x8 fragments for the same
hardware-generation reason). The legacy kernel body itself hardcodes `constexpr int NR0=64; NR1=32;
NK=32;` (`ggml-metal.metal:10170-10173`) and `res.nsg = N_MM_SIMD_GROUP_X * N_MM_SIMD_GROUP_Y` (line
761) with both factors `=2` (`ggml-metal-impl.h:14-15`) -> `nsg=4`. The dispatch call itself
(`ggml-metal-ops.cpp:2274`) launches `dispatch_threadgroups(..., threadsPerThreadgroup=(32, nsg, 1))`
-> 4 simdgroups x 32 lanes = 128 threads/threadgroup. So: ONE threadgroup computes a 64x32 output
tile, K-stepped 32 at a time, cooperatively by 4 simdgroups over 128 threads.

MAPPING TO THIS FILE'S OWN (M,N) CONVENTION: llama.cpp's `nr0`/`ne0` axis is walked by `src0` (its
per-row-block-quantized WEIGHT operand, `args.nb01*(r0+lr0)` in the kernel body) -- i.e. it is the
OUTPUT-FEATURE dimension, this file's `n`/`_BN`. llama.cpp's `nr1`/`ne1` axis is walked by `src1`
(its per-row ACTIVATION operand, `args.nb11*(r1+lr1)`) -- i.e. this file's `m_rows`/`_BM`. So in THIS
file's naming: `nr0=64 -> _BN_W=64`, `nr1=32 -> _BM_W=32`, `NK=32 -> _BK_W=32`, `nsg=4 ->
_NTHREADS_W=128` (4 simdgroups x 32 lanes, half this file's existing `_NTHREADS=256`). Note `_BM_W`
happens to equal this file's EXISTING `_BM=32` already -- the real, isolated change vs.
`_qkv_proj_gemm_mma8x8` is `_BN` doubling (32->64) and `_BK` doubling (16->32), with simdgroup count
halved (8->4) to match.

WHERE THIS DESIGN NECESSARILY DIVERGES FROM LLAMA.CPP'S OWN SCHEME, STATED EXPLICITLY (Mojo's 8x8-
fragment-only MMA primitive on this hardware generation cannot express llama.cpp's own construct
byte-for-byte):
  - llama.cpp's legacy kernel already uses raw `simdgroup_float8x8`/`simdgroup_half8x8` (an 8x8
    fragment, same granularity Mojo's `_mma_apple_8x8` exposes) -- so the FRAGMENT SIZE itself is not
    a divergence; both are built from 8x8 hardware ops covering a 64x32 tile with 32 total fragments.
    The divergence is in how those 32 fragments are DISTRIBUTED across the 4 simdgroups: llama.cpp
    assigns each simdgroup a fixed, CONTIGUOUS 32(N)x16(M) block (`sgitg&1` selects an N-halfa,
    `sgitg>>1` selects an M-half, `ggml-metal.metal:10327-10328`) with 8 fragments per simdgroup
    arranged 4(N)x2(M) inside that block. This kernel instead reuses THIS FILE'S OWN established
    cyclic assignment (`sub_idx = sg + which*_NSG`, already used by every other kernel above for
    their own subtile counts) rather than replicating llama.cpp's specific contiguous-block pattern
    -- both are valid, non-overlapping, complete coverings of the same 64x32/32-fragment tile (same
    SIZE, same simdgroup COUNT, per this task's own instructions), and the cyclic form is what this
    file's other kernels already use and have already proven correct, so reusing it minimizes new
    surface area for a genuine tile-shape-only comparison. This is a real, disclosed divergence in
    fragment-ownership ORDER, not in tile size or simdgroup count.
  - llama.cpp's legacy kernel has a branchless fast-output-path when the tile is fully in-bounds
    (`ggml-metal.metal:10324`, `!FC_mul_mm_bc_out`) and a separate staged-through-threadgroup-memory
    slow path only for boundary tiles. This kernel, like every other kernel in this file, always
    uses the same per-element bounds-checked store via `_frag_row_col` (this file's own established,
    already-proven partial-tile discipline -- see the module docstring's "PARTIAL-TILE M/N" section)
    regardless of whether the tile is interior or boundary. Simpler, already-proven in this file,
    and not the axis under test here.
  - llama.cpp's A-operand (`sa`) is dequantized from its own block-quantized format (q4_0/q8_0/f16/
    etc., selected by `dequantize_func`) directly into `S0` (matching this kernel's role); this
    kernel keeps THIS FILE's own Int8-per-row dequant-to-Float32 scheme unchanged from
    `_qkv_proj_gemm_mma8x8` (`Float32(w[...]) * wscale[...]`) -- the storage/dequant format is
    DELIBERATELY NOT changed here (that was the already-tested, already-refuted axis above); only
    the tile geometry is new.

Everything else -- the shared-memory cooperative-load pattern, the zero-padding-on-load partial-tile
handling, the final bounds-checked store via `_frag_row_col` -- is the same discipline
`_qkv_proj_gemm_mma8x8` already uses, just re-parameterized for the new tile constants. Shared memory
footprint: `a_tile` = 32*32*4B = 4096B, `b_tile` = 32*64*4B = 8192B, 12288B total per threadgroup --
well under typical Apple GPU per-threadgroup shared memory budgets (`_qkv_proj_gemm_mma8x8`'s own
tile uses 4096B total, so this is a real, disclosed 3x increase in shared-memory pressure, the
tradeoff for a larger per-threadgroup output tile with fewer, larger threadgroups)."""


def _qkv_proj_gemm_mma8x8_wide(
    y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """`_qkv_proj_gemm_mma8x8` with `_BM_W=32/_BN_W=64/_BK_W=32` (llama.cpp `kernel_mul_mm`'s own
    legacy-path tile geometry, re-derived above) instead of `_BM=32/_BN=32/_BK=16`, and 4 simdgroups/
    128 threads instead of 8 simdgroups/256 threads -- see `_SUBTILES_PER_SG_W`'s own docstring
    immediately above for the full geometry derivation and every place this design necessarily
    diverges from llama.cpp's own scheme. Int8 storage + per-output-row dequant-to-Float32 on load
    is UNCHANGED from `_qkv_proj_gemm_mma8x8` -- tile shape is the ONLY variable under test here.
    Each simdgroup now owns `_SUBTILES_PER_SG_W=8` (vs. 2) 8x8 fragments, cyclically assigned via
    `sub_idx = sg + which*4` (4 simdgroups, vs. `sg + which*8` for 8 simdgroups above) over the
    `_SUBROWS_W=4` x `_SUBCOLS_W=8` fragment grid."""
    var a_tile = stack_allocation[Int(_BM_W * _BK_W), DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[Int(_BK_W * _BN_W), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_tile_cols = (n + _BN_W - 1) // _BN_W
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM_W
    var block_col = tile_col * _BN_W

    var acc0 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc1 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc2 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc3 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc4 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc5 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc6 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc7 = SIMD[DType.float32, 2](0.0, 0.0)

    var n_steps = (k + _BK_W - 1) // _BK_W
    for step in range(n_steps):
        var a_elems = (_BM_W * _BK_W) // _NTHREADS_W
        for s in range(a_elems):
            var idx = tid + s * _NTHREADS_W
            var ar = idx // _BK_W
            var ac = idx % _BK_W
            var gr = block_row + ar
            var gc = step * _BK_W + ac
            a_tile[Int(idx)] = xn[Int(gr * k + gc)] if (gr < m_rows and gc < k) else Float32(0.0)

        var b_elems = (_BN_W * _BK_W) // _NTHREADS_W
        for s in range(b_elems):
            var idx2 = tid + s * _NTHREADS_W
            var br = idx2 // _BK_W
            var bc = idx2 % _BK_W
            var gr2 = block_col + br
            var gc2 = step * _BK_W + bc
            var val = Float32(w[Int(gr2 * k + gc2)]) * wscale[Int(gr2)] if (gr2 < n and gc2 < k) else Float32(0.0)
            # Same transposed-write convention as `_qkv_proj_gemm_mma8x8`'s own b_tile: [BK_W,BN_W]
            # so `apple_mma_load_8x8` sees a valid [K,N]-oriented B operand.
            b_tile[Int(bc * _BN_W + br)] = val

        barrier()

        for ksub in range(Int(_BK_W // 8)):
            for which in range(8):
                var sub_idx = sg + Int64(which) * 4
                var sub_row = sub_idx // _SUBCOLS_W
                var sub_col = sub_idx % _SUBCOLS_W
                var a_ptr = a_tile + Int(sub_row * 8 * _BK_W + Int64(ksub) * 8)
                var b_ptr = b_tile + Int(Int64(ksub) * 8 * _BN_W + sub_col * 8)
                var a_frag = apple_mma_load_8x8[DType.float32](a_ptr, Int(_BK_W))
                var b_frag = apple_mma_load_8x8[DType.float32](b_ptr, Int(_BN_W))
                if which == 0:
                    _mma_apple_8x8(acc0, a_frag, b_frag, acc0)
                elif which == 1:
                    _mma_apple_8x8(acc1, a_frag, b_frag, acc1)
                elif which == 2:
                    _mma_apple_8x8(acc2, a_frag, b_frag, acc2)
                elif which == 3:
                    _mma_apple_8x8(acc3, a_frag, b_frag, acc3)
                elif which == 4:
                    _mma_apple_8x8(acc4, a_frag, b_frag, acc4)
                elif which == 5:
                    _mma_apple_8x8(acc5, a_frag, b_frag, acc5)
                elif which == 6:
                    _mma_apple_8x8(acc6, a_frag, b_frag, acc6)
                else:
                    _mma_apple_8x8(acc7, a_frag, b_frag, acc7)

        barrier()

    var rc = _frag_row_col(tid)
    for which in range(8):
        var sub_idx = sg + Int64(which) * 4
        var sub_row = sub_idx // _SUBCOLS_W
        var sub_col = sub_idx % _SUBCOLS_W
        var frag = acc0
        if which == 1:
            frag = acc1
        elif which == 2:
            frag = acc2
        elif which == 3:
            frag = acc3
        elif which == 4:
            frag = acc4
        elif which == 5:
            frag = acc5
        elif which == 6:
            frag = acc6
        elif which == 7:
            frag = acc7
        var r = block_row + sub_row * 8 + rc[0]
        var c0 = block_col + sub_col * 8 + rc[1]
        var c1 = c0 + 1
        if r < m_rows and c0 < n:
            y[Int(r * n + c0)] = frag[0]
        if r < m_rows and c1 < n:
            y[Int(r * n + c1)] = frag[1]


def _qkv_proj_gemm_mma8x8_pipelined(
    y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """GEMM tournament, third isolation experiment (REALRACE_RESULTS.md, 2026-08-07 "two isolation
    experiments" entry, "What is left" section): software-pipelined / double-buffered K-steps --
    the ledger's own recorded next step, not yet attempted at the time this was written. Genuinely
    different from BOTH already-refuted hypotheses: MMA operand width stays `DType.float32` exactly
    as `_qkv_proj_gemm_mma8x8` (NOT `_qkv_proj_gemm_mma8x8_f16`'s already-refuted axis), and tile
    shape stays `BM=32/BN=32/BK=16`, 8 simdgroups over 256 threads, exactly as
    `_qkv_proj_gemm_mma8x8` (NOT `_qkv_proj_gemm_mma8x8_wide`'s already-refuted axis). The ONLY
    change relative to `_qkv_proj_gemm_mma8x8`: the load/barrier/compute/barrier loop is restructured
    to overlap the NEXT BK=16 K-step's cooperative shared-memory load with the CURRENT step's MMA
    compute, instead of `_qkv_proj_gemm_mma8x8`'s strictly-sequential "load full tile -> barrier ->
    compute full tile -> barrier -> next tile."

    MECHANISM -- ping-pong double buffering with a single trailing barrier per step (the crux of
    this experiment is getting this barrier placement right, reasoned through Metal's actual
    `threadgroup_barrier` semantics, which are all-or-nothing for the whole threadgroup, not
    fine-grained per-address):
      - TWO sets of `a_tile`/`b_tile` shared-memory buffers (`a_tile0`/`b_tile0` and `a_tile1`/
        `b_tile1`), doubling this kernel's shared-memory footprint from `_qkv_proj_gemm_mma8x8`'s
        2048B+2048B=4096B to 2*(2048B+2048B)=8192B total per threadgroup -- a real, disclosed 2x
        increase, still comfortably under Apple's typical 32 KiB per-threadgroup shared-memory
        ceiling (this session's own standing budget check throughout the GEMM tournament).
      - PROLOGUE: cooperatively load step 0's A/B data into buffer set 0, then ONE barrier -- step
        0 has no previous step to overlap with, so this is unavoidably sequential, exactly like
        `_qkv_proj_gemm_mma8x8`'s own first iteration.
      - MAIN LOOP, per step `i` (`cur` = buffer set for step `i`, `nxt` = the OTHER buffer set):
          (a) if `i+1 < n_steps`: cooperatively load step `i+1`'s A/B data into `nxt` -- this is
              the prefetch. Issued with NO barrier immediately before or after it.
          (b)/(c) compute the 4 MMA sub-steps against `cur` -- requires NO barrier here, because
              `cur`'s data was already fully loaded and barriered by the END of the PREVIOUS
              iteration (or the prologue, for step 0), and `cur`/`nxt` are physically disjoint
              shared-memory buffers, so writing `nxt` above and reading `cur` here have no
              cross-thread dependency for the barrier to guard. This is precisely where a
              naively-conservative implementation would insert an unnecessary barrier and
              accidentally serialize the prefetch this experiment exists to overlap.
          (d) ONE barrier at the end of the iteration. This single barrier does double duty, which
              is what makes one-barrier-per-step sufficient rather than two: it makes THIS
              iteration's prefetch (into `nxt`) visible to iteration `i+1`'s compute (which reads
              it as ITS `cur`), AND it ensures THIS iteration's compute (reading `cur`) has
              completed before iteration `i+1`'s OWN prefetch (for step `i+2`) overwrites that same
              buffer set again -- `cur` at step `i` is the same physical buffer as `nxt` at step
              `i+1`. Both hazards are real cross-thread producer/consumer dependencies (any thread
              may read shared-memory addresses another thread wrote), so both genuinely need this
              barrier; nothing here is being skipped for a false optimization.
      - The final step (`i = n_steps-1`) issues no prefetch (there is no `n_steps`-th step) and
        still ends in the same trailing barrier for structural uniformity; it costs one barrier
        with nothing to overlap against, exactly once for the whole kernel, negligible next to
        `n_steps` full loop iterations.

    Net effect vs. `_qkv_proj_gemm_mma8x8`: 1 barrier per step instead of 2 (n_steps+1 total instead
    of 2*n_steps), with the removed barrier being precisely the one that forced the load to fully
    land before compute could begin -- the shared-memory load latency for step `i+1` is now free to
    be in flight concurrently with step `i`'s MMA compute, exactly the standard latency-hiding
    technique double buffering exists for. Whether Mojo's codegen and Apple's GPU scheduler actually
    realize that overlap (vs. the already-refuted operand-width and tile-shape hypotheses) is an
    empirical question this kernel's own benchmark answers, not assumed here.

    Same as every other addition to this file: `_qkv_proj_gemm_mma8x8` and every other existing
    kernel above are left completely untouched; this is a pure addition. Int8 storage with
    per-output-row dequant-to-Float32 on load, grid/tile-column indexing, the `ksub`/`which`
    accumulate structure, and the final bounds-checked store via `_frag_row_col` are all
    byte-for-byte identical to `_qkv_proj_gemm_mma8x8` -- only the load/barrier/compute loop
    structure changed."""
    var a_tile0 = stack_allocation[Int(_BM * _BK), DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile0 = stack_allocation[Int(_BK * _BN), DType.float32, address_space = AddressSpace.SHARED]()
    var a_tile1 = stack_allocation[Int(_BM * _BK), DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile1 = stack_allocation[Int(_BK * _BN), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_tile_cols = (n + _BN - 1) // _BN
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM
    var block_col = tile_col * _BN

    var acc0 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc1 = SIMD[DType.float32, 2](0.0, 0.0)

    var a_elems = (_BM * _BK) // _NTHREADS
    var b_elems = (_BN * _BK) // _NTHREADS
    var n_steps = (k + _BK - 1) // _BK

    # ---- Prologue: cooperatively load step 0's A/B data into buffer set 0. No previous step
    # exists to overlap this with, so this one load is unavoidably sequential -- same as
    # `_qkv_proj_gemm_mma8x8`'s own first iteration.
    for s in range(a_elems):
        var idx = tid + s * _NTHREADS
        var ar = idx // _BK
        var ac = idx % _BK
        var gr = block_row + ar
        var gc = ac
        a_tile0[Int(idx)] = xn[Int(gr * k + gc)] if (gr < m_rows and gc < k) else Float32(0.0)
    for s in range(b_elems):
        var idx2 = tid + s * _NTHREADS
        var br = idx2 // _BK
        var bc = idx2 % _BK
        var gr2 = block_col + br
        var gc2 = bc
        var val = Float32(w[Int(gr2 * k + gc2)]) * wscale[Int(gr2)] if (gr2 < n and gc2 < k) else Float32(0.0)
        b_tile0[Int(bc * _BN + br)] = val

    barrier()

    for step in range(n_steps):
        var cur_even = (step % 2) == 0
        var cur_a = a_tile0 if cur_even else a_tile1
        var cur_b = b_tile0 if cur_even else b_tile1
        var nxt_a = a_tile1 if cur_even else a_tile0
        var nxt_b = b_tile1 if cur_even else b_tile0

        # (a) Prefetch: cooperatively load step `step+1`'s data into the OTHER buffer set, if
        # there is a next step. No barrier immediately before or after this -- it is issued and
        # left to land concurrently with the compute below, which reads a physically disjoint
        # buffer set (`cur_a`/`cur_b`), not this one.
        if step + 1 < n_steps:
            for s in range(a_elems):
                var idx = tid + s * _NTHREADS
                var ar = idx // _BK
                var ac = idx % _BK
                var gr = block_row + ar
                var gc = (step + 1) * _BK + ac
                nxt_a[Int(idx)] = xn[Int(gr * k + gc)] if (gr < m_rows and gc < k) else Float32(0.0)
            for s in range(b_elems):
                var idx2 = tid + s * _NTHREADS
                var br = idx2 // _BK
                var bc = idx2 % _BK
                var gr2 = block_col + br
                var gc2 = (step + 1) * _BK + bc
                var val = Float32(w[Int(gr2 * k + gc2)]) * wscale[Int(gr2)] if (gr2 < n and gc2 < k) else Float32(0.0)
                nxt_b[Int(bc * _BN + br)] = val

        # (b)/(c) Compute the 4 MMA sub-steps against THIS step's buffer set (`cur_a`/`cur_b`) --
        # already fully loaded and barriered by the end of the previous iteration (or the
        # prologue, for step 0). Deliberately NO barrier here: that would serialize the prefetch
        # just issued above for no reason, since it targets the other buffer set entirely.
        for ksub in range(Int(_BK // 8)):
            for which in range(2):
                var sub_idx = sg + Int64(which) * 8
                var sub_row = sub_idx // 4
                var sub_col = sub_idx % 4
                var a_ptr = cur_a + Int(sub_row * 8 * _BK + Int64(ksub) * 8)
                var b_ptr = cur_b + Int(Int64(ksub) * 8 * _BN + sub_col * 8)
                var a_frag = apple_mma_load_8x8[DType.float32](a_ptr, Int(_BK))
                var b_frag = apple_mma_load_8x8[DType.float32](b_ptr, Int(_BN))
                if which == 0:
                    _mma_apple_8x8(acc0, a_frag, b_frag, acc0)
                else:
                    _mma_apple_8x8(acc1, a_frag, b_frag, acc1)

        # (d) One barrier per step, doing double duty: makes THIS step's prefetch (into
        # `nxt_a`/`nxt_b`) visible to the NEXT iteration's compute (which will read it as ITS
        # `cur_a`/`cur_b`), AND ensures THIS step's compute (reading `cur_a`/`cur_b`) has fully
        # completed before the NEXT iteration's OWN prefetch (for step `step+2`) overwrites that
        # same buffer set again. Both are real cross-thread producer/consumer hazards -- neither
        # is skippable.
        barrier()

    var rc = _frag_row_col(tid)
    for which in range(2):
        var sub_idx = sg + Int64(which) * 8
        var sub_row = sub_idx // 4
        var sub_col = sub_idx % 4
        var frag = acc0 if which == 0 else acc1
        var r = block_row + sub_row * 8 + rc[0]
        var c0 = block_col + sub_col * 8 + rc[1]
        var c1 = c0 + 1
        if r < m_rows and c0 < n:
            y[Int(r * n + c0)] = frag[0]
        if r < m_rows and c1 < n:
            y[Int(r * n + c1)] = frag[1]
