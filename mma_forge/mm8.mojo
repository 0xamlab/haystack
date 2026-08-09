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


comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
"""Same naming convention `attention_forge/*.mojo` already established for an F16 device pointer
alias (`parity_replica.mojo`, `native_kv_producer.mojo`, `grouped_fa_q8_k32_h2_sg8.mojo`, etc.) --
reused here so this file's new pre-packed-F16 pair reads consistently with the rest of the repo."""

comptime _PACK_TG: Int64 = 256
"""Threads per threadgroup for `_pack_i8_weights_to_f16_kernel`'s own flat elementwise grid -- an
independent choice from `_NTHREADS` (the GEMM kernels' own threadgroup size): the pack kernel is a
trivial 1-thread-per-weight-element dequant, not a cooperative-tile kernel, so it has no shared
memory or MMA-fragment constraints to satisfy. 256 chosen simply as a normal, occupancy-friendly
threadgroup size for a bandwidth-bound elementwise pass; the benchmark file dispatching this kernel
computes `grid_dim = ceil_div(n*k, 256)` on the host side using this exact literal, mirroring every
other file in this tournament's own "grid/block sizing lives in the harness, not imported from the
kernel module" convention."""


def _pack_i8_weights_to_f16_kernel(
    w_f16_out: _F16P, w_i8_in: _I8P, wscale_in: _FP, n: Int64, k: Int64
):
    """GEMM tournament, untested-hypothesis follow-up (REALRACE_RESULTS.md, 2026-08-07 "third and
    decisive isolation experiment" entry's synthesis: three kernel-architecture variants --operand
    width, tile shape, K-step pipelining-- all refuted). None of those three experiments changed
    WHEN or HOW OFTEN the Int8->Float32(->Float16) dequant happens: `_qkv_proj_gemm_mma8x8` and
    every variant appended above it all dequantize `w[gr2*k+gc2] * wscale[gr2]` INSIDE every
    threadgroup's own cooperative load, every dispatch -- and at this GEMM's own `BM=32` tiling,
    `M=256/BM=32=8` different M-tile threadgroups all cooperatively-load the IDENTICAL (N,K) weight
    slice for a given N-tile, each one redundantly repeating the exact same dequant arithmetic the
    other 7 already did. This kernel is the fix for that redundancy specifically: a trivial,
    ONE-TIME, one-thread-per-element dequant pass over the FULL `[n,k]` Int8 weight matrix (plus its
    per-row Float32 scale), writing a FULL `[n,k]` Float16 matrix -- run ONCE, outside any hot loop
    (a real session would run this once per weight tensor at load/pack time, then reuse the output
    for every subsequent layer/token), so `_qkv_proj_gemm_mma8x8_prepacked_f16` below never needs to
    dequantize anything at dispatch time, and never redoes the SAME element's dequant 8 times over.

    Flat 1-D grid: `grid_dim = ceil_div(n*k, _PACK_TG)`, `block_dim = _PACK_TG` (both computed on
    the host side, see `_PACK_TG`'s own docstring) -- `idx = block_idx.x * _PACK_TG + thread_idx.x`
    is the flat `[n,k]` row-major element index; `row = idx // k` recovers which output row's
    Float32 scale applies (`_qkv_proj_gemm_mma8x8`'s own per-output-row-quantized convention,
    UNCHANGED here -- this kernel does not introduce a new quantization scheme, it just moves an
    EXISTING one's dequant step out of the hot loop and off the redundant-per-tile schedule).
    Out-of-range `idx >= n*k` threads (the grid is rounded up to a multiple of `_PACK_TG`) write
    nothing, exactly the same bounds-check discipline `_qkv_proj_gemm_mma8x8`'s own cooperative load
    already uses for a partial final tile."""
    var idx = Int64(block_idx.x) * _PACK_TG + Int64(thread_idx.x)
    var total = n * k
    if idx < total:
        var row = idx // k
        w_f16_out[Int(idx)] = Float16(Float32(w_i8_in[Int(idx)]) * wscale_in[Int(row)])


def _qkv_proj_gemm_mma8x8_prepacked_f16(
    y: _FP, xn: _FP, w_f16: _F16P, m_rows: Int64, k: Int64, n: Int64
):
    """GEMM tournament, untested-hypothesis follow-up: the genuinely different, previously-untested
    variable this entry's own motivating critique named -- pre-converting the ENTIRE weight matrix
    to native Float16 ONCE, via `_pack_i8_weights_to_f16_kernel` above, BEFORE this kernel ever runs,
    so THIS kernel's own cooperative load does ZERO dequantization of any kind: no Int8 read, no
    `wscale` read, no `Float32(...) * scale` multiply -- just a straight, already-F16-typed copy from
    `w_f16` into shared memory. This removes BOTH things the already-refuted
    `_qkv_proj_gemm_mma8x8_f16` isolation experiment left untouched: the Int8->Float32 dequant
    itself, AND its 8x redundancy (`M=256/BM=32=8` M-tile threadgroups per N-tile, per this file's
    own `_pack_i8_weights_to_f16_kernel` docstring) -- in one change, isolated from every other
    already-tried axis.

    Explicitly NOT combined with either already-refuted axis: identical `BM=32/BN=32/BK=16`, 8
    SIMD-groups-over-256-threads tile shape (`_qkv_proj_gemm_mma8x8_wide`'s geometry change is not
    reused here), and strictly sequential load->barrier->compute->barrier per K-step, no double
    buffering (`_qkv_proj_gemm_mma8x8_pipelined`'s scheduling change is not reused here either) --
    this kernel changes exactly ONE thing relative to `_qkv_proj_gemm_mma8x8_f16`: WHERE and HOW
    OFTEN the weight is converted to Float16 (once, upstream, vs. every threadgroup's own load).

    The activation side keeps the ALREADY-PROVEN-NOT-refuted half of `_qkv_proj_gemm_mma8x8_f16`'s
    own change: `xn` (Float32 in device memory, exactly like every other kernel in this file) is
    still narrowed to Float16 ONCE per activation-tile cooperative load, same as that kernel's own
    `a_tile` narrowing -- the task this kernel isolates is specifically "does removing the WEIGHT
    side's redundant per-tile dequant close the gap," not "should the activation ever be narrowed at
    all," so the activation narrowing step (which was never the refuted part of that prior
    experiment) is kept unchanged rather than re-litigated.

    Accumulator type is UNCHANGED: `SIMD[DType.float32, 2]`, exactly like every other kernel in this
    file -- mixed-precision (half) multiply, full-precision (float) accumulate, matching llama.cpp's
    own `kernel_mul_mm_f16_f32` scheme this whole GEMM tournament has been comparing against.

    `_qkv_proj_gemm_mma8x8`, `_qkv_proj_gemm_mma8x8_f16`, `_qkv_proj_gemm_mma8x8_wide`,
    `_qkv_proj_gemm_mma8x8_pipelined`, and `_pack_i8_weights_to_f16_kernel` immediately above are all
    left completely untouched by this addition."""
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
            # ZERO runtime dequantization here -- `w_f16` is ALREADY Float16 and ALREADY scaled,
            # produced once by `_pack_i8_weights_to_f16_kernel` before this kernel's own timed hot
            # loop ever starts. A straight copy, no multiply, no Int8 read -- only the SAME
            # transposed-write index convention `_qkv_proj_gemm_mma8x8`'s own `b_tile` already uses
            # (device memory is `[N,K]`; `apple_mma_load_8x8` needs a `[K,N]`-oriented operand).
            var val = w_f16[Int(gr2 * k + gc2)] if (gr2 < n and gc2 < k) else Float16(0.0)
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


comptime _BM_64: Int64 = 64
comptime _BN_64: Int64 = 32
comptime _BK_64: Int64 = 16
comptime _NTHREADS_64: Int64 = 256
comptime _SUBROWS_64: Int64 = _BM_64 // 8
comptime _SUBCOLS_64: Int64 = _BN_64 // 8
comptime _N_SUBTILES_64: Int64 = _SUBROWS_64 * _SUBCOLS_64
comptime _SUBTILES_PER_SG_64: Int64 = _N_SUBTILES_64 // (_NTHREADS_64 // 32)
"""Project Redline reopening (REALRACE_RESULTS.md, "Project Redline reopening (2026-08-08)" entry,
Gap 2): Gap 2's own diagnosis of why `_pack_i8_weights_to_f16_kernel` +
`_qkv_proj_gemm_mma8x8_prepacked_f16` (above) made things WORSE, not better -- removing the
per-tile Int8->Float32 dequant *compute* did nothing about the redundant *traffic* underneath it.
At `_qkv_proj_gemm_mma8x8`'s own `BM=32`, `M=256/BM=32=8` different M-tile threadgroups each
independently re-fetch the IDENTICAL (N,K) weight slice for a given N-tile from device memory, once
per threadgroup, every dispatch -- an 8x redundant DRAM read of the same bytes. Gap 2's own text
named the fix directly: "reducing the redundancy factor itself (larger BM, fewer M-tile
threadgroups sharing the same weight slice)... not pursued without further evidence" -- this is
that further evidence, run down as its own genuinely isolated hypothesis.

DISTINCT FROM THE ALREADY-REFUTED `_qkv_proj_gemm_mma8x8_wide` EXPERIMENT: that experiment changed
`BN` (32->64), `BK` (16->32), AND simdgroup/thread count (8sg/256thr -> 4sg/128thr) TOGETHER, to
match llama.cpp's own whole tile geometry -- three variables bundled into one measurement, and it
measured 4.2-4.3x SLOWER (refuted). This kernel changes exactly ONE thing relative to
`_qkv_proj_gemm_mma8x8`: `BM` (32->64). `BN_64=32` and `BK_64=16` are copies of the ORIGINAL
kernel's own `_BN`/`_BK` values (new names, not new values -- kept as separate comptime constants
here rather than importing `_BN`/`_BK` directly, matching this file's own established convention of
giving every tournament variant its own self-contained constant block, e.g. `_BM_W`/`_BN_W`/`_BK_W`
above). `_NTHREADS_64=256` is likewise unchanged from the original kernel's own `_NTHREADS` --
occupancy allows it: see the shared-memory footprint disclosure below.

STRUCTURAL CONSEQUENCE OF DOUBLING BM ALONE (not a second independent variable -- an unavoidable
downstream effect of the one variable that did change): doubling `BM` from 32 to 64 while holding
`BN=32` fixed doubles the subtile grid from `(32/8)x(32/8)=4x4=16` fragments to
`(64/8)x(32/8)=8x4=32` fragments. Holding simdgroup count fixed at 8 (`_NTHREADS_64=256` unchanged)
means each simdgroup must now own `_SUBTILES_PER_SG_64=4` 8x8 fragments instead of the original
kernel's 2 -- i.e. `_qkv_proj_gemm_mma8x8_bm64` below needs FOUR accumulator registers
(`acc0`..`acc3`) instead of two, and its `which` loop runs `range(4)` instead of `range(2)`, at
BOTH the accumulate step and the final store, cyclically assigned via the SAME
`sub_idx = sg + which * 8` scheme every kernel in this file already uses for an
8-simdgroup/256-thread threadgroup (the multiplier is `_NTHREADS_64 // 32 = 8`, unchanged from the
original kernel specifically BECAUSE simdgroup count did not change). The A-tile cooperative load
scales in lockstep: `a_elems = (BM_64*BK_64)/NTHREADS_64 = 1024/256 = 4` per thread (vs. 2
originally), since `a_tile` now holds twice as many elements over the same 256 threads. The B-tile
(WEIGHT) cooperative load is completely UNCHANGED: `b_elems = (BN_64*BK_64)/NTHREADS_64 = 512/256 =
2`, identical to the original kernel -- this is the entire point of the experiment. Each
threadgroup now does 2x the M-work (64 rows instead of 32) per weight-tile fetch, so the number of
M-tile threadgroups redundantly re-fetching the SAME N-tile's weight slice drops from
`M/BM=256/32=8` to `M/BM_64=256/64=4` -- half the redundant weight traffic, with the activation
(A-tile) side absorbing the corresponding increase in per-threadgroup load/register work instead
(a real, disclosed structural tradeoff, not a free lunch).

SHARED-MEMORY FOOTPRINT, disclosed per this file's own established convention (see
`_qkv_proj_gemm_mma8x8_wide`'s own docstring for the same kind of disclosure): `a_tile` =
`BM_64*BK_64*4B = 64*16*4 = 4096B` (2x the original kernel's 2048B), `b_tile` =
`BK_64*BN_64*4B = 16*32*4 = 2048B` (UNCHANGED from the original), 6144B total per threadgroup --
still well under Apple's typical 32 KiB per-threadgroup shared-memory ceiling (this session's own
standing budget check throughout the GEMM tournament; `_qkv_proj_gemm_mma8x8_pipelined`'s own
8192B footprint and `_qkv_proj_gemm_mma8x8_wide`'s own 12288B footprint were both already judged
comfortable against this same ceiling). No reduction in `_NTHREADS_64` was needed to stay within
budget -- occupancy allows keeping the original 8-simdgroup/256-thread structure, so it is kept,
per this task's own instruction to hold everything BM's doubling does not structurally require
constant."""


def _qkv_proj_gemm_mma8x8_bm64(
    y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """`_qkv_proj_gemm_mma8x8` with `BM_64=64` in place of `BM=32` -- see `_SUBTILES_PER_SG_64`'s
    own docstring immediately above for the full BM-isolation rationale and the structural
    consequences doubling BM requires. `BN_64=32`, `BK_64=16`, and the 8-simdgroup/256-thread
    structure are all UNCHANGED from `_qkv_proj_gemm_mma8x8` -- BM is the ONLY variable under test.
    Byte-for-byte identical to `_qkv_proj_gemm_mma8x8` except: (1) the tile-size constants used
    throughout, (2) `a_tile`'s doubled element count and the correspondingly doubled `a_elems`
    cooperative-load loop trip count, and (3) FOUR accumulator fragments (`acc0`..`acc3`) and a
    `which in range(4)` loop (both at the accumulate step and the final store) instead of two
    fragments and `which in range(2)`, cyclically assigned via `sub_idx = sg + which * 8` over the
    now-`8x4` subtile grid (`_SUBROWS_64 x _SUBCOLS_64`) instead of the original `4x4` grid. The
    B-tile (weight) cooperative load, the per-output-row Int8 dequant-on-load scheme, the
    barrier placement, and the final bounds-checked store via `_frag_row_col` are all identical in
    structure to `_qkv_proj_gemm_mma8x8` -- only re-parameterized for the new tile constants.
    `_qkv_proj_gemm_mma8x8` itself, and every other kernel above, are left completely untouched;
    this is a pure addition."""
    var a_tile = stack_allocation[Int(_BM_64 * _BK_64), DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[Int(_BK_64 * _BN_64), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_tile_cols = (n + _BN_64 - 1) // _BN_64
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM_64
    var block_col = tile_col * _BN_64

    var acc0 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc1 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc2 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc3 = SIMD[DType.float32, 2](0.0, 0.0)

    var n_steps = (k + _BK_64 - 1) // _BK_64
    for step in range(n_steps):
        var a_elems = (_BM_64 * _BK_64) // _NTHREADS_64
        for s in range(a_elems):
            var idx = tid + s * _NTHREADS_64
            var ar = idx // _BK_64
            var ac = idx % _BK_64
            var gr = block_row + ar
            var gc = step * _BK_64 + ac
            a_tile[Int(idx)] = xn[Int(gr * k + gc)] if (gr < m_rows and gc < k) else Float32(0.0)

        var b_elems = (_BN_64 * _BK_64) // _NTHREADS_64
        for s in range(b_elems):
            var idx2 = tid + s * _NTHREADS_64
            var br = idx2 // _BK_64
            var bc = idx2 % _BK_64
            var gr2 = block_col + br
            var gc2 = step * _BK_64 + bc
            var val = Float32(w[Int(gr2 * k + gc2)]) * wscale[Int(gr2)] if (gr2 < n and gc2 < k) else Float32(0.0)
            # Same transposed-write convention as `_qkv_proj_gemm_mma8x8`'s own b_tile: [BK_64,BN_64]
            # so `apple_mma_load_8x8` sees a valid [K,N]-oriented B operand.
            b_tile[Int(bc * _BN_64 + br)] = val

        barrier()

        for ksub in range(Int(_BK_64 // 8)):
            for which in range(4):
                var sub_idx = sg + Int64(which) * 8
                var sub_row = sub_idx // _SUBCOLS_64
                var sub_col = sub_idx % _SUBCOLS_64
                var a_ptr = a_tile + Int(sub_row * 8 * _BK_64 + Int64(ksub) * 8)
                var b_ptr = b_tile + Int(Int64(ksub) * 8 * _BN_64 + sub_col * 8)
                var a_frag = apple_mma_load_8x8[DType.float32](a_ptr, Int(_BK_64))
                var b_frag = apple_mma_load_8x8[DType.float32](b_ptr, Int(_BN_64))
                if which == 0:
                    _mma_apple_8x8(acc0, a_frag, b_frag, acc0)
                elif which == 1:
                    _mma_apple_8x8(acc1, a_frag, b_frag, acc1)
                elif which == 2:
                    _mma_apple_8x8(acc2, a_frag, b_frag, acc2)
                else:
                    _mma_apple_8x8(acc3, a_frag, b_frag, acc3)

        barrier()

    var rc = _frag_row_col(tid)
    for which in range(4):
        var sub_idx = sg + Int64(which) * 8
        var sub_row = sub_idx // _SUBCOLS_64
        var sub_col = sub_idx % _SUBCOLS_64
        var frag = acc0
        if which == 1:
            frag = acc1
        elif which == 2:
            frag = acc2
        elif which == 3:
            frag = acc3
        var r = block_row + sub_row * 8 + rc[0]
        var c0 = block_col + sub_col * 8 + rc[1]
        var c1 = c0 + 1
        if r < m_rows and c0 < n:
            y[Int(r * n + c0)] = frag[0]
        if r < m_rows and c1 < n:
            y[Int(r * n + c1)] = frag[1]


comptime _BM_128: Int64 = 128
comptime _BN_128: Int64 = 32
comptime _BK_128: Int64 = 16
comptime _NTHREADS_128: Int64 = 256
comptime _SUBROWS_128: Int64 = _BM_128 // 8
comptime _SUBCOLS_128: Int64 = _BN_128 // 8
comptime _N_SUBTILES_128: Int64 = _SUBROWS_128 * _SUBCOLS_128
comptime _SUBTILES_PER_SG_128: Int64 = _N_SUBTILES_128 // (_NTHREADS_128 // 32)
"""BM-isolation tournament axis, second data point -- see `_SUBTILES_PER_SG_64`'s own docstring
immediately above for the full rationale (Gap 2's redundant-weight-refetch diagnosis, and why this
is distinct from the already-refuted `_qkv_proj_gemm_mma8x8_wide` bundled-geometry experiment). This
block is `_qkv_proj_gemm_mma8x8_bm64`'s own next step along the SAME single axis: `BM_128=128`
(quadrupling the original kernel's `BM=32`, doubling `_qkv_proj_gemm_mma8x8_bm64`'s own `BM_64=64`)
-- `BN_128=32` and `BK_128=16` stay copies of the ORIGINAL kernel's `_BN`/`_BK` values, unchanged
from both the original kernel and from `_qkv_proj_gemm_mma8x8_bm64`.

STRUCTURAL CONSEQUENCE: the subtile grid grows to `(128/8)x(32/8) = 16x4 = 64` fragments. Holding
simdgroup count fixed at 8 (`_NTHREADS_128=256`, unchanged from both prior kernels -- occupancy
still allows it, see the shared-memory disclosure below) means each simdgroup now owns
`_SUBTILES_PER_SG_128=8` fragments (double `_qkv_proj_gemm_mma8x8_bm64`'s 4, quadruple the original
kernel's 2) -- EIGHT accumulator registers (`acc0`..`acc7`) and a `which in range(8)` loop, at both
the accumulate step and the final store, cyclically assigned via the same
`sub_idx = sg + which * 8` scheme (multiplier still 8 = `_NTHREADS_128 // 32`, unchanged because
simdgroup count did not change) over a `16x4` subtile grid (`_SUBROWS_128 x _SUBCOLS_128`). The
A-tile cooperative load scales again in lockstep: `a_elems = (BM_128*BK_128)/NTHREADS_128 =
2048/256 = 8` per thread (double `_qkv_proj_gemm_mma8x8_bm64`'s 4). The B-tile (WEIGHT) cooperative
load is STILL completely unchanged from the original kernel: `b_elems = (BN_128*BK_128)/
NTHREADS_128 = 512/256 = 2`. Each threadgroup now covers 128 M-rows per weight-tile fetch, so the
number of M-tile threadgroups redundantly re-fetching the SAME N-tile's weight slice drops from the
original kernel's `M/BM=256/32=8` to `M/BM_128=256/128=2` -- a quarter of the original redundant
weight traffic (vs. half for the BM64 variant), at the cost of quadrupling (vs. doubling) the
per-thread accumulator register count and the A-tile cooperative-load trip count relative to the
original kernel.

SHARED-MEMORY FOOTPRINT: `a_tile` = `BM_128*BK_128*4B = 128*16*4 = 8192B` (4x the original kernel's
2048B, 2x `_qkv_proj_gemm_mma8x8_bm64`'s own 4096B), `b_tile` = `BK_128*BN_128*4B = 16*32*4 =
2048B` (still UNCHANGED from the original), 10240B total per threadgroup -- still comfortably under
Apple's typical 32 KiB per-threadgroup shared-memory ceiling, the same standing budget check this
file has applied to every other tournament variant (`_qkv_proj_gemm_mma8x8_wide`'s own 12288B
footprint remains the largest measured in this file, so this kernel's 10240B is not a new high-water
mark). No reduction in `_NTHREADS_128` was needed to stay within that budget, so, per this task's
own instruction, it is kept unchanged."""


def _qkv_proj_gemm_mma8x8_bm128(
    y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """`_qkv_proj_gemm_mma8x8` with `BM_128=128` in place of `BM=32` -- see `_SUBTILES_PER_SG_128`'s
    own docstring immediately above for the full BM-isolation rationale and the structural
    consequences this larger BM requires. `BN_128=32`, `BK_128=16`, and the 8-simdgroup/256-thread
    structure are all UNCHANGED from `_qkv_proj_gemm_mma8x8` -- BM is the ONLY variable under test,
    same axis as `_qkv_proj_gemm_mma8x8_bm64`, one step further along it. Byte-for-byte identical
    to `_qkv_proj_gemm_mma8x8` except: (1) the tile-size constants used throughout, (2) `a_tile`'s
    quadrupled element count and the correspondingly quadrupled `a_elems` cooperative-load loop trip
    count, and (3) EIGHT accumulator fragments (`acc0`..`acc7`) and a `which in range(8)` loop (both
    at the accumulate step and the final store) instead of two fragments and `which in range(2)`,
    cyclically assigned via `sub_idx = sg + which * 8` over the now-`16x4` subtile grid
    (`_SUBROWS_128 x _SUBCOLS_128`) instead of the original `4x4` grid. The B-tile (weight)
    cooperative load, the per-output-row Int8 dequant-on-load scheme, the barrier placement, and the
    final bounds-checked store via `_frag_row_col` are all identical in structure to
    `_qkv_proj_gemm_mma8x8` -- only re-parameterized for the new tile constants. Every other kernel
    in this file, including `_qkv_proj_gemm_mma8x8_bm64` immediately above, is left completely
    untouched; this is a pure addition."""
    var a_tile = stack_allocation[Int(_BM_128 * _BK_128), DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[Int(_BK_128 * _BN_128), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_tile_cols = (n + _BN_128 - 1) // _BN_128
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM_128
    var block_col = tile_col * _BN_128

    var acc0 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc1 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc2 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc3 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc4 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc5 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc6 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc7 = SIMD[DType.float32, 2](0.0, 0.0)

    var n_steps = (k + _BK_128 - 1) // _BK_128
    for step in range(n_steps):
        var a_elems = (_BM_128 * _BK_128) // _NTHREADS_128
        for s in range(a_elems):
            var idx = tid + s * _NTHREADS_128
            var ar = idx // _BK_128
            var ac = idx % _BK_128
            var gr = block_row + ar
            var gc = step * _BK_128 + ac
            a_tile[Int(idx)] = xn[Int(gr * k + gc)] if (gr < m_rows and gc < k) else Float32(0.0)

        var b_elems = (_BN_128 * _BK_128) // _NTHREADS_128
        for s in range(b_elems):
            var idx2 = tid + s * _NTHREADS_128
            var br = idx2 // _BK_128
            var bc = idx2 % _BK_128
            var gr2 = block_col + br
            var gc2 = step * _BK_128 + bc
            var val = Float32(w[Int(gr2 * k + gc2)]) * wscale[Int(gr2)] if (gr2 < n and gc2 < k) else Float32(0.0)
            # Same transposed-write convention as `_qkv_proj_gemm_mma8x8`'s own b_tile:
            # [BK_128,BN_128] so `apple_mma_load_8x8` sees a valid [K,N]-oriented B operand.
            b_tile[Int(bc * _BN_128 + br)] = val

        barrier()

        for ksub in range(Int(_BK_128 // 8)):
            for which in range(8):
                var sub_idx = sg + Int64(which) * 8
                var sub_row = sub_idx // _SUBCOLS_128
                var sub_col = sub_idx % _SUBCOLS_128
                var a_ptr = a_tile + Int(sub_row * 8 * _BK_128 + Int64(ksub) * 8)
                var b_ptr = b_tile + Int(Int64(ksub) * 8 * _BN_128 + sub_col * 8)
                var a_frag = apple_mma_load_8x8[DType.float32](a_ptr, Int(_BK_128))
                var b_frag = apple_mma_load_8x8[DType.float32](b_ptr, Int(_BN_128))
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
        var sub_idx = sg + Int64(which) * 8
        var sub_row = sub_idx // _SUBCOLS_128
        var sub_col = sub_idx % _SUBCOLS_128
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


comptime _BM_BN64: Int64 = 32
comptime _BN_BN64: Int64 = 64
comptime _BK_BN64: Int64 = 16
comptime _NTHREADS_BN64: Int64 = 256
comptime _SUBROWS_BN64: Int64 = _BM_BN64 // 8
comptime _SUBCOLS_BN64: Int64 = _BN_BN64 // 8
comptime _N_SUBTILES_BN64: Int64 = _SUBROWS_BN64 * _SUBCOLS_BN64
comptime _SUBTILES_PER_SG_BN64: Int64 = _N_SUBTILES_BN64 // (_NTHREADS_BN64 // 32)
"""Project Redline reopening -- the BM-isolation axis's own unattacked sibling. `_qkv_proj_gemm_
mma8x8_bm64`/`_qkv_proj_gemm_mma8x8_bm128` above (Gap 2's own follow-up) only ever attacked the
WEIGHT (B) side's redundant-traffic factor: at the original kernel's `BM=32`, `M/BM=8` M-tile
threadgroups each re-fetch the same N-tile's weight slice, so doubling/quadrupling `BM` cuts that
redundancy (8x -> 4x -> 2x) at the cost of more accumulator fragments per simdgroup. Never
attacked: the ACTIVATION (A) side's OWN, symmetric redundant-traffic factor. At the original
kernel's `BN=32`, `N/BN` N-tile threadgroups (for a fixed M-tile row) each independently re-fetch
the SAME M-tile's activation slice from device memory -- `N/BN=4096/32=128` redundant re-fetches of
that slice per M-tile-row's worth of N-tiles, the direct A-side analogue of the B-side redundancy
`_qkv_proj_gemm_mma8x8_bm64` attacked. Doubling `BN` instead of `BM` cuts THIS redundancy factor in
half (`N/BN_BN64=4096/64=64`, half of 128) by the same mechanism: each threadgroup now covers twice
the N-columns per activation-tile fetch, so half as many N-tile threadgroups share (and
redundantly re-fetch) the same M-tile's activation slice.

`_BM_BN64=32` and `_BK_BN64=16` are copies of the ORIGINAL kernel's own `_BM`/`_BK` values (new
names, not new values, same convention `_BM_64`/`_BK_64` and `_BM_128`/`_BK_128` above already
established) -- unchanged from `_qkv_proj_gemm_mma8x8`. `_BN_BN64=64` is the ONLY variable that
changed relative to the original kernel; `_NTHREADS_BN64=256` (8 simdgroups) is likewise unchanged
-- occupancy allows it, see the shared-memory disclosure below.

STRUCTURAL CONSEQUENCE OF DOUBLING BN ALONE (the mirror image of doubling BM): the subtile grid
becomes `(BM_BN64/8)x(BN_BN64/8) = 4x8 = 32` fragments (`_SUBROWS_BN64=4` unchanged from the
original kernel's own 4 M-subrows, `_SUBCOLS_BN64=8` double the original's 4 N-subcols) -- the SAME
total fragment count (32) `_qkv_proj_gemm_mma8x8_bm64` already produced by doubling BM instead
(`8x4=32`), and therefore the SAME `_SUBTILES_PER_SG_BN64=4` fragments per simdgroup
(`32 / (256//32) = 32/8 = 4`) that kernel already proved does not hit the register-pressure cliff
`_qkv_proj_gemm_mma8x8_bm128`'s 8-fragment/SG variant hit (measured ~3.5x SLOWER, attributed to
accumulator-fragment/register pressure). `_qkv_proj_gemm_mma8x8_bn64` below therefore needs FOUR
accumulator fragments (`acc0`..`acc3`) and a `which in range(4)` loop, cyclically assigned via the
SAME `sub_idx = sg + which * 8` scheme every kernel in this file uses, exactly like
`_qkv_proj_gemm_mma8x8_bm64` -- but `sub_row = sub_idx // _SUBCOLS_BN64` / `sub_col = sub_idx %
_SUBCOLS_BN64` walk a `4x8` grid (M-major-4-rows, N-major-8-cols) instead of `_qkv_proj_gemm_mma8x8_
bm64`'s `8x4` grid (N-major-4-cols) -- the row/col roles are transposed, not merely relabeled,
because it is BN, not BM, that doubled here.

The load-side consequence is the MIRROR IMAGE of `_qkv_proj_gemm_mma8x8_bm64`'s: there, the A-tile
(activation) cooperative load doubled (`a_elems`: 2->4 per thread) while the B-tile (weight) load
stayed at the original kernel's own `b_elems=2`. Here, it is the B-tile (weight) cooperative load
that doubles: `b_elems = (BN_BN64*BK_BN64)/NTHREADS_BN64 = (64*16)/256 = 4` (vs. the original
kernel's 2), while the A-tile (activation) load is COMPLETELY UNCHANGED from the original kernel:
`a_elems = (BM_BN64*BK_BN64)/NTHREADS_BN64 = (32*16)/256 = 2`, identical trip count, identical
per-thread indexing -- this is the entire point of the experiment, the direct structural mirror of
`_qkv_proj_gemm_mma8x8_bm64` leaving the B-tile load untouched.

SHARED-MEMORY FOOTPRINT: `a_tile` = `BM_BN64*BK_BN64*4B = 32*16*4 = 2048B` (UNCHANGED from the
original kernel), `b_tile` = `BK_BN64*BN_BN64*4B = 16*64*4 = 4096B` (2x the original kernel's
2048B, and exactly `_qkv_proj_gemm_mma8x8_bm64`'s own `a_tile` size of 4096B -- the mirror-image
byte count, same total). Total per threadgroup: 6144B, BYTE-FOR-BYTE IDENTICAL to
`_qkv_proj_gemm_mma8x8_bm64`'s own 6144B total (2048+4096 either way round) -- well under Apple's
typical 32 KiB per-threadgroup shared-memory ceiling this file has applied to every prior tournament
variant. No reduction in `_NTHREADS_BN64` was needed to stay within budget, so, per this task's own
instruction to hold everything BN's doubling does not structurally require constant, it is kept
unchanged."""


def _qkv_proj_gemm_mma8x8_bn64(
    y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """`_qkv_proj_gemm_mma8x8` with `BN_BN64=64` in place of `BN=32` -- the A-side (activation)
    mirror of `_qkv_proj_gemm_mma8x8_bm64`'s B-side (weight) attack; see `_SUBTILES_PER_SG_BN64`'s
    own docstring immediately above for the full BN-isolation rationale and the structural
    consequences doubling BN requires. `BM_BN64=32`, `BK_BN64=16`, and the 8-simdgroup/256-thread
    structure are all UNCHANGED from `_qkv_proj_gemm_mma8x8` -- BN is the ONE variable under test,
    exactly the same isolation discipline `_qkv_proj_gemm_mma8x8_bm64` applied to BM. Byte-for-byte
    identical to `_qkv_proj_gemm_mma8x8` except: (1) the tile-size constants used throughout, (2)
    `b_tile`'s doubled element count and the correspondingly doubled `b_elems` cooperative-load loop
    trip count (the A-tile load is UNCHANGED), and (3) FOUR accumulator fragments (`acc0`..`acc3`)
    and a `which in range(4)` loop (both at the accumulate step and the final store) instead of two
    fragments and `which in range(2)`, cyclically assigned via `sub_idx = sg + which * 8` over the
    now-`4x8` subtile grid (`_SUBROWS_BN64 x _SUBCOLS_BN64`) instead of the original `4x4` grid. The
    A-tile (activation) cooperative load, the per-output-row Int8 dequant-on-load scheme, the
    barrier placement, and the final bounds-checked store via `_frag_row_col` are all identical in
    structure to `_qkv_proj_gemm_mma8x8` -- only re-parameterized for the new tile constants.
    `_qkv_proj_gemm_mma8x8`, `_qkv_proj_gemm_mma8x8_bm64`, `_qkv_proj_gemm_mma8x8_bm128`, and every
    other kernel above are left completely untouched; this is a pure addition."""
    var a_tile = stack_allocation[Int(_BM_BN64 * _BK_BN64), DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[Int(_BK_BN64 * _BN_BN64), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_tile_cols = (n + _BN_BN64 - 1) // _BN_BN64
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM_BN64
    var block_col = tile_col * _BN_BN64

    var acc0 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc1 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc2 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc3 = SIMD[DType.float32, 2](0.0, 0.0)

    var n_steps = (k + _BK_BN64 - 1) // _BK_BN64
    for step in range(n_steps):
        var a_elems = (_BM_BN64 * _BK_BN64) // _NTHREADS_BN64
        for s in range(a_elems):
            var idx = tid + s * _NTHREADS_BN64
            var ar = idx // _BK_BN64
            var ac = idx % _BK_BN64
            var gr = block_row + ar
            var gc = step * _BK_BN64 + ac
            a_tile[Int(idx)] = xn[Int(gr * k + gc)] if (gr < m_rows and gc < k) else Float32(0.0)

        var b_elems = (_BN_BN64 * _BK_BN64) // _NTHREADS_BN64
        for s in range(b_elems):
            var idx2 = tid + s * _NTHREADS_BN64
            var br = idx2 // _BK_BN64
            var bc = idx2 % _BK_BN64
            var gr2 = block_col + br
            var gc2 = step * _BK_BN64 + bc
            var val = Float32(w[Int(gr2 * k + gc2)]) * wscale[Int(gr2)] if (gr2 < n and gc2 < k) else Float32(0.0)
            # Same transposed-write convention as `_qkv_proj_gemm_mma8x8`'s own b_tile:
            # [BK_BN64,BN_BN64] so `apple_mma_load_8x8` sees a valid [K,N]-oriented B operand.
            b_tile[Int(bc * _BN_BN64 + br)] = val

        barrier()

        for ksub in range(Int(_BK_BN64 // 8)):
            for which in range(4):
                var sub_idx = sg + Int64(which) * 8
                var sub_row = sub_idx // _SUBCOLS_BN64
                var sub_col = sub_idx % _SUBCOLS_BN64
                var a_ptr = a_tile + Int(sub_row * 8 * _BK_BN64 + Int64(ksub) * 8)
                var b_ptr = b_tile + Int(Int64(ksub) * 8 * _BN_BN64 + sub_col * 8)
                var a_frag = apple_mma_load_8x8[DType.float32](a_ptr, Int(_BK_BN64))
                var b_frag = apple_mma_load_8x8[DType.float32](b_ptr, Int(_BN_BN64))
                if which == 0:
                    _mma_apple_8x8(acc0, a_frag, b_frag, acc0)
                elif which == 1:
                    _mma_apple_8x8(acc1, a_frag, b_frag, acc1)
                elif which == 2:
                    _mma_apple_8x8(acc2, a_frag, b_frag, acc2)
                else:
                    _mma_apple_8x8(acc3, a_frag, b_frag, acc3)

        barrier()

    var rc = _frag_row_col(tid)
    for which in range(4):
        var sub_idx = sg + Int64(which) * 8
        var sub_row = sub_idx // _SUBCOLS_BN64
        var sub_col = sub_idx % _SUBCOLS_BN64
        var frag = acc0
        if which == 1:
            frag = acc1
        elif which == 2:
            frag = acc2
        elif which == 3:
            frag = acc3
        var r = block_row + sub_row * 8 + rc[0]
        var c0 = block_col + sub_col * 8 + rc[1]
        var c1 = c0 + 1
        if r < m_rows and c0 < n:
            y[Int(r * n + c0)] = frag[0]
        if r < m_rows and c1 < n:
            y[Int(r * n + c1)] = frag[1]


comptime _VEC4: Int64 = 4
comptime _CHUNKS_PER_ROW_V4: Int64 = _BK // _VEC4
"""`_BK=16` columns per row split into 4-wide chunks -- 4 chunks/row, used only by
`_qkv_proj_gemm_mma8x8_vecload4`'s cooperative-load remap below."""
comptime _N_CHUNKS_V4: Int64 = (_BM * _BK) // _VEC4
"""Total 4-wide chunks needed to cover one A-tile (`_BM*_BK=512` elements -> 128 chunks of 4) --
identically `_BN*_BK=512` elements for the B-tile, since `_BM==_BN==32` here. `_N_CHUNKS_V4=128`
is HALF of `_NTHREADS=256`: only threads `tid < 128` do a cooperative-load chunk this experiment;
`tid >= 128` do nothing during the load phase (still participate in the barrier + MMA compute
below, unchanged). This is the direct, mechanical consequence of widening the load 4x while
holding total element count fixed -- NOT a separate change to thread count or occupancy policy."""


def _qkv_proj_gemm_mma8x8_vecload4(
    y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """Load-instruction-WIDTH isolation experiment: byte-for-byte `_qkv_proj_gemm_mma8x8` (same
    `BM=32/BN=32/BK=16` tile shape, same 256 threads / 8 simdgroups, same all-Float32
    `apple_mma_load_8x8`/`_mma_apple_8x8` fragment load and compute, same final bounds-checked
    store via `_frag_row_col`) with ONLY the device-memory cooperative load re-widened from
    scalar (one Float32 / one Int8 element per load) to 4-wide (`SIMD[DType.float32,4]` /
    `SIMD[DType.int8,4]` via `UnsafePointer.load[width=4]`, the same API this repo's own
    `benchmarks/llm_smoke/int8_pack_probe.mojo` already uses and correctness-gates for both a
    device Int8 pointer and a `stack_allocation`-backed SHARED Float32 pointer). Distinct from
    the already-refuted `_qkv_proj_gemm_mma8x8_wide` (that experiment changed tile geometry, not
    load width) and from `_qkv_proj_gemm_mma8x8_f16` (MMA operand type, not load width) -- see
    `REALRACE_RESULTS.md`'s "Load-instruction width" entry for the disassembly finding this
    isolates: the shipped kernel emits zero wide vector loads from device memory, llama.cpp's
    `kernel_mul_mm` emits `load <4 x float>`/`load <4 x half>` for the identical cooperative-load
    role.

    THREAD-TO-CHUNK REMAP (the one genuinely new piece of logic here): the original scalar loop
    covers `_BM*_BK=512` A-tile elements as `idx = tid + s*256` for `s in {0,1}` (2 elements per
    thread, all 256 threads). `_BK=16` divides evenly into 4 chunks of 4 (`_CHUNKS_PER_ROW_V4=4`),
    so `_N_CHUNKS_V4 = 512/4 = 128` -- HALF of `_NTHREADS`. Chunk `c = tid` (for `tid < 128`) owns
    the 4 contiguous elements at flat index `[c*4, c*4+4)`; since `_BK=16` is itself a multiple of
    4, this 4-element run can never straddle a row boundary, so each chunk maps to exactly ONE
    (row, col_start) pair: `row = tid // 4` (`0..31`, all of `_BM`), `col_start = (tid % 4) * 4`
    (`0, 4, 8, 12`, all of `_BK`). `row` and `col_start` are shared verbatim between the A-tile and
    B-tile remap below because the original kernel's own `idx`/`idx2` loops are already identical
    formulas over the same range (`ar,ac` and `br,bc` are literally the same numbers for a given
    `(tid, s)`, just applied to a different base pointer) -- this experiment does not introduce any
    new asymmetry there. Every one of the 512 elements is covered by exactly one of the 128 active
    threads exactly once (`tid in [0,128)` sweeps `c*4 .. c*4+3` contiguously over `[0,512)`, no
    gaps, no overlap); `tid in [128,256)` loads nothing this phase (still hits the same `barrier()`
    calls as everyone else). Identical chunk count and mapping for the B-tile, since
    `_BN*_BK == _BM*_BK == 512` here.

    A-TILE (activation, Float32): fast path is a single `xn.load[width=4]` device read followed by
    a single `a_tile.store[width=4]` shared-memory write -- valid because BOTH sides are
    contiguous-in-K for a fixed row (`xn` is `[M,K]` row-major; `a_tile` is written `[BM,BK]`
    row-major, the SAME orientation as the original, untouched here). Slow path (any of the 4
    elements out of bounds -- `gr_a >= m_rows` or `gc0_a+3 >= k`) falls back to the ORIGINAL
    kernel's own per-element ternary, verbatim, so zero-padding at ragged M/K matches exactly.

    B-TILE (weight, Int8): fast path is a single `w.load[width=4]` device read (also contiguous-in-
    K for a fixed output row, same layout argument as A), cast to Float32, multiplied by ONE
    `wscale[row]` lookup shared across all 4 elements (a direct, disclosed side effect of chunking
    by whole row -- removes 3 of 4 redundant per-element `wscale` lookups the original issues,
    since the original's `ar,ac`/`br,bc` loops already visit 4 elements of the same row per K-step
    per thread-slot; this is NOT a separate change, it falls out of vectorizing along K within one
    row). The shared-memory write stays 4 separate SCALAR stores, unlike the A-tile: `b_tile` is
    written `[BK,BN]` (TRANSPOSED vs `[BN,BK]`, unchanged from the original, required for
    `apple_mma_load_8x8` to see a valid `[K,N]`-oriented B operand) so 4 consecutive K-values for
    one row land at shared-memory indices `_BN` apart, not contiguous -- a `store[width=4]` is not
    applicable there. Slow path re-does the original's own per-element ternary verbatim (including
    its own per-element `wscale` re-lookup, short-circuited exactly as the original when
    `gr_b >= n`), so the wscale-lookup reduction is strictly a fast-path property, not claimed for
    the (rare, boundary-only) slow path.

    Fragment load/compute/store below this point (the `apple_mma_load_8x8` calls, `_mma_apple_8x8`,
    the `_frag_row_col`-gated final store) are IDENTICAL, unedited, to `_qkv_proj_gemm_mma8x8` --
    this experiment isolates the device-memory cooperative load only, per this task's own scope
    (shared-memory-to-register fragment load width is a separate, not-yet-attempted axis)."""
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
        if tid < _N_CHUNKS_V4:
            var crow = tid // _CHUNKS_PER_ROW_V4
            var ccol_grp = tid % _CHUNKS_PER_ROW_V4
            var col0 = ccol_grp * _VEC4
            var idx0 = crow * _BK + col0

            # A-tile (activation): 4-wide device read + 4-wide shared-memory write on the fast
            # path; original per-element ternary, verbatim, on the slow path.
            var gr_a = block_row + crow
            var gc0_a = step * _BK + col0
            if gr_a < m_rows and gc0_a + 3 < k:
                var av = xn.load[width=4](Int(gr_a * k + gc0_a))
                a_tile.store[width=4](Int(idx0), av)
            else:
                for c in range(4):
                    var gc_a = gc0_a + Int64(c)
                    a_tile[Int(idx0 + Int64(c))] = xn[Int(gr_a * k + gc_a)] if (gr_a < m_rows and gc_a < k) else Float32(0.0)

            # B-tile (weight): 4-wide Int8 device read + ONE wscale lookup on the fast path
            # (disclosed side effect of chunking by row -- see docstring); original per-element
            # ternary, verbatim (including its own re-lookup), on the slow path. Shared-memory
            # write stays scalar x4 either way -- the [BK,BN] transpose layout (unchanged from the
            # original) makes a fixed-row, varying-K chunk land _BN elements apart, not contiguous.
            var gr_b = block_col + crow
            var gc0_b = step * _BK + col0
            if gr_b < n and gc0_b + 3 < k:
                var wv_i8 = w.load[width=4](Int(gr_b * k + gc0_b))
                var scale_v = SIMD[DType.float32, 4](wscale[Int(gr_b)])
                var wv = wv_i8.cast[DType.float32]() * scale_v
                for c in range(4):
                    b_tile[Int((col0 + Int64(c)) * _BN + crow)] = wv[c]
            else:
                for c in range(4):
                    var gc_b = gc0_b + Int64(c)
                    var val = Float32(w[Int(gr_b * k + gc_b)]) * wscale[Int(gr_b)] if (gr_b < n and gc_b < k) else Float32(0.0)
                    b_tile[Int((col0 + Int64(c)) * _BN + crow)] = val

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


def _qkv_proj_gemm_mma8x8_vecload4_f16(
    y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """Combined-arm kernel, built per the F1 decomposition's decision tree AFTER a dedicated
    feasibility task (this session) confirmed native 64-wide MMA fragment loading
    (`air.simdgroup_matrix_8x8_load`, matching llama.cpp's own `kernel_mul_mm_f16_f32`) is a
    confirmed TOOLCHAIN CEILING on `apple_mma_load_8x8` -- not a bug in any real kernel's own
    calling convention, and not fixable by changing pointer/stride construction. That report
    (`mma_forge/probes/mma_fragment_load_probe.mojo`) found Modular's OWN production Apple-8x8
    reference kernel hits the identical ceiling, disassembly-confirmed both for the probe and for
    this file's own kernels. Per the task's own "if UNAVAILABLE" branch, A2/A3 (native-fragment-load
    arms) are correctly NOT attempted here. This kernel is instead the best available combination
    of the two arms that ARE real and already validated separately in this investigation:

      - `_qkv_proj_gemm_mma8x8_vecload4`'s device-memory cooperative-load width (4-wide
        `SIMD[...,4]` loads for both the A-tile activation and the B-tile Int8 weight, via
        `UnsafePointer.load[width=4]`) -- the SAME thread-to-chunk remap, reused verbatim (not
        reinvented): `tid < _N_CHUNKS_V4` chunks of 4 contiguous elements, fast-path vectorized
        load/store with a per-element ternary slow path at ragged M/K boundaries, one `wscale`
        lookup shared per 4-element row-chunk on the B-side (the same disclosed side effect
        `_qkv_proj_gemm_mma8x8_vecload4`'s own docstring already discloses).
      - `_qkv_proj_gemm_mma8x8_f16`'s MMA operand narrowing (`a_tile`/`b_tile` declared
        `DType.float16` instead of `DType.float32`, `apple_mma_load_8x8[DType.float16]` fragment
        loads, `_mma_apple_8x8` consuming Float16 operands into the UNCHANGED
        `SIMD[DType.float32, 2]` accumulator -- mixed-precision multiply, full-precision
        accumulate, matching llama.cpp's own scheme).

    The one new piece of logic this combination requires (neither parent kernel needed it alone):
    the 4-wide device load is Float32 (A-tile) / dequantized-Float32 (B-tile), but the
    shared-memory tile it lands in is now Float16 -- so the fast path narrows via
    `.cast[DType.float16]()` on the SIMD vector BEFORE the store (A-tile: a single 4-wide
    `a_tile.store[width=4]` of the narrowed vector, valid because `a_tile` is `[BM,BK]` row-major
    contiguous-in-K exactly as `_qkv_proj_gemm_mma8x8_vecload4`'s own A-tile already is; B-tile:
    still 4 separate SCALAR stores of the narrowed values, since `b_tile`'s `[BK,BN]` transposed
    layout -- required by `apple_mma_load_8x8` for a valid `[K,N]`-oriented B operand, unchanged
    from every other kernel in this file -- places 4 consecutive K-values `_BN` apart, not
    contiguous, exactly as `_qkv_proj_gemm_mma8x8_vecload4`'s own B-tile fast path already is).
    The slow (ragged-boundary) path narrows to Float16 per element via the SAME ternary
    `_qkv_proj_gemm_mma8x8_f16` already uses, applied at the SAME per-chunk boundary check
    `_qkv_proj_gemm_mma8x8_vecload4` already uses -- two already-proven pieces of logic composed,
    nothing new invented at the boundary.

    Fragment load/compute (`apple_mma_load_8x8[DType.float16]`, `_mma_apple_8x8`) and the final
    bounds-checked store via `_frag_row_col` are IDENTICAL, unedited, to `_qkv_proj_gemm_mma8x8_f16`
    -- this kernel changes ONLY the device-memory cooperative-load width, on top of that kernel's
    already-established F16-operand change. `_qkv_proj_gemm_mma8x8`, `_qkv_proj_gemm_mma8x8_f16`,
    and `_qkv_proj_gemm_mma8x8_vecload4` are all left completely untouched above; this is a pure
    addition, verified via `probes/gemm_qkv_proj_vecload4_f16_bench.mojo`."""
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
        if tid < _N_CHUNKS_V4:
            var crow = tid // _CHUNKS_PER_ROW_V4
            var ccol_grp = tid % _CHUNKS_PER_ROW_V4
            var col0 = ccol_grp * _VEC4
            var idx0 = crow * _BK + col0

            # A-tile (activation): 4-wide device Float32 read, narrowed to Float16, 4-wide
            # shared-memory write on the fast path; per-element ternary (narrowed to Float16,
            # matching `_qkv_proj_gemm_mma8x8_f16`'s own slow-path convention) on the slow path.
            var gr_a = block_row + crow
            var gc0_a = step * _BK + col0
            if gr_a < m_rows and gc0_a + 3 < k:
                var av = xn.load[width=4](Int(gr_a * k + gc0_a))
                var av_f16 = av.cast[DType.float16]()
                a_tile.store[width=4](Int(idx0), av_f16)
            else:
                for c in range(4):
                    var gc_a = gc0_a + Int64(c)
                    a_tile[Int(idx0 + Int64(c))] = Float16(xn[Int(gr_a * k + gc_a)]) if (gr_a < m_rows and gc_a < k) else Float16(0.0)

            # B-tile (weight): 4-wide Int8 device read + ONE wscale lookup (disclosed side effect
            # of chunking by row, same as `_qkv_proj_gemm_mma8x8_vecload4`) dequantized to Float32
            # then narrowed to Float16 on the fast path; per-element ternary (narrowed to Float16,
            # own re-lookup) on the slow path. Shared-memory write stays scalar x4 either way -- the
            # [BK,BN] transposed layout makes a fixed-row, varying-K chunk land `_BN` elements
            # apart, not contiguous, so a vector store is not applicable.
            var gr_b = block_col + crow
            var gc0_b = step * _BK + col0
            if gr_b < n and gc0_b + 3 < k:
                var wv_i8 = w.load[width=4](Int(gr_b * k + gc0_b))
                var scale_v = SIMD[DType.float32, 4](wscale[Int(gr_b)])
                var wv_f16 = (wv_i8.cast[DType.float32]() * scale_v).cast[DType.float16]()
                for c in range(4):
                    b_tile[Int((col0 + Int64(c)) * _BN + crow)] = wv_f16[c]
            else:
                for c in range(4):
                    var gc_b = gc0_b + Int64(c)
                    var val = Float16(Float32(w[Int(gr_b * k + gc_b)]) * wscale[Int(gr_b)]) if (gr_b < n and gc_b < k) else Float16(0.0)
                    b_tile[Int((col0 + Int64(c)) * _BN + crow)] = val

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


comptime _CHUNKS_PER_ROW_V4_BM64: Int64 = _BK_64 // _VEC4
comptime _N_CHUNKS_A_V4_BM64: Int64 = (_BM_64 * _BK_64) // _VEC4
comptime _N_CHUNKS_B_V4_BM64: Int64 = (_BN_64 * _BK_64) // _VEC4
"""Tile-shape x load-width STACKING experiment's own re-derived chunk constants -- see
`_qkv_proj_gemm_mma8x8_bm64_vecload4`'s own docstring below for the full derivation this
generalizes. Reuses `_VEC4` (4-wide) from `_qkv_proj_gemm_mma8x8_vecload4`'s own constant block
verbatim (load width is NOT a variable in this combination) and `_BM_64`/`_BN_64`/`_BK_64`/
`_NTHREADS_64`/`_SUBROWS_64`/`_SUBCOLS_64` from `_qkv_proj_gemm_mma8x8_bm64`'s own constant block
verbatim (tile shape is NOT a variable in this combination either) -- stacking introduces no new
tile-shape or load-width constant, only new CHUNK-COUNT arithmetic over the two ALREADY-FIXED
axes, matching this file's own convention of giving every tournament variant its own
self-contained, named constant block (`_qkv_proj_gemm_mma8x8_vecload4_f16`'s own combined-arm
constants immediately follow the same pattern).

`_CHUNKS_PER_ROW_V4_BM64 = _BK_64 // _VEC4 = 16 // 4 = 4` -- numerically identical to
`_qkv_proj_gemm_mma8x8_vecload4`'s own `_CHUNKS_PER_ROW_V4` (`BK` did not change between the two
parent kernels), kept as its own named constant rather than imported, per this file's established
per-variant-constant-block convention.

`_N_CHUNKS_A_V4_BM64 = (_BM_64*_BK_64)//_VEC4 = 1024//4 = 256` -- DOUBLE
`_qkv_proj_gemm_mma8x8_vecload4`'s own A-tile chunk count (128), because BM64 doubles the A-tile's
element count while the load stays 4-wide. This is the genuinely new structural fact this
combination surfaces: 256 == `_NTHREADS_64`, i.e. the re-derived A-tile chunk count now matches
the FULL thread count exactly -- unlike `_qkv_proj_gemm_mma8x8_vecload4` alone (where only half
the 256 threads, `tid < 128`, are active during the A-tile load phase, the other half idle that
phase), EVERY one of the 256 threads owns exactly one 4-wide A-tile chunk here, none idle.

`_N_CHUNKS_B_V4_BM64 = (_BN_64*_BK_64)//_VEC4 = 512//4 = 128` -- UNCHANGED from
`_qkv_proj_gemm_mma8x8_vecload4`'s own B-tile chunk count (128), because BM64 never touches
`BN`/`BK`: the B-tile's size, and therefore its chunk-to-thread mapping (`tid < 128`, `brow = tid
// 4`, `bcol_grp = tid % 4`), is byte-for-byte identical to the un-stacked
`_qkv_proj_gemm_mma8x8_vecload4`'s own B-tile remap -- reused verbatim below, not re-derived, per
the same "share what didn't change" discipline `_qkv_proj_gemm_mma8x8_vecload4_f16` already
applied to `_qkv_proj_gemm_mma8x8_vecload4`'s own remap when combining with the F16-operand
axis."""


def _qkv_proj_gemm_mma8x8_bm64_vecload4(
    y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """Stacked-axes kernel: `_qkv_proj_gemm_mma8x8_bm64`'s tile-shape change (`BM_64=64` in place
    of `BM=32`, doubling the subtile grid to `8x4=32` fragments, FOUR accumulator fragments per
    simdgroup -- `acc0`..`acc3`, `which in range(4)` at both the accumulate step and the final
    store, cyclically assigned via `sub_idx = sg + which*8` over the `_SUBROWS_64 x _SUBCOLS_64`
    grid, exactly as `_qkv_proj_gemm_mma8x8_bm64` itself does) COMBINED with
    `_qkv_proj_gemm_mma8x8_vecload4`'s device-memory cooperative-load width (4-wide
    `SIMD[DType.float32,4]`/`SIMD[DType.int8,4]` loads via `UnsafePointer.load[width=4]`, a single
    shared `wscale` lookup per B-tile chunk, per-element ternary slow path at ragged M/K
    boundaries). `BN_64=32`, `BK_64=16`, 8 simdgroups / 256 threads, and all-Float32 MMA operands
    are UNCHANGED from BOTH parent kernels -- this combination isolates whether stacking two
    already-independently-confirmed, orthogonal wins (tile shape/weight-traffic redundancy vs.
    memory-transaction width) compounds multiplicatively, sub-additively, or one cannibalizes the
    other; it is not a third new variable.

    THREAD-TO-CHUNK REMAP, RE-DERIVED FOR THE LARGER BM64 A-TILE (the one genuinely new piece of
    logic this stacking requires -- see `_N_CHUNKS_A_V4_BM64`'s own docstring immediately above
    for the full derivation): `_qkv_proj_gemm_mma8x8_vecload4`'s own remap was built for BM=32's
    512-element A-tile (128 chunks of 4, `tid < 128` active, half the 256 threads idle that
    phase). Doubling BM to 64 doubles the A-tile to 1024 elements -- `_N_CHUNKS_A_V4_BM64 = 256`,
    which exactly matches `_NTHREADS_64`, so EVERY thread owns exactly one 4-wide A-tile chunk (no
    `if tid < ...` half-idle split for A specifically, unlike the un-stacked vecload4 kernel):
    `row = tid // _CHUNKS_PER_ROW_V4_BM64` sweeps all `0..63` of `_BM_64`, `col_start = (tid %
    _CHUNKS_PER_ROW_V4_BM64) * 4` sweeps all `0,4,8,12` of `_BK_64` -- the SAME one-vector-load-
    per-active-thread principle as the un-stacked kernel, just covering twice the element count
    with the same thread count. A pleasant side effect: the scalar `_qkv_proj_gemm_mma8x8_bm64`
    needed a `for s in range(4)` loop per thread to cover its own doubled 4-elements-per-thread
    A-tile load; the 4-wide vectorization here collapses that same work to ONE single vector
    instruction per thread, so the A-tile load below has no `s`-loop at all (unlike
    `_qkv_proj_gemm_mma8x8_bm64`'s own scalar A-tile load). The B-tile chunk count is UNCHANGED at
    128 (`_N_CHUNKS_B_V4_BM64`, `tid < 128` active), matching `_qkv_proj_gemm_mma8x8_vecload4`'s
    own B-tile remap byte-for-byte (because `BN`/`BK` never changed) -- reused verbatim, not
    re-derived, with its own single `wscale[row]` lookup per chunk preserved exactly as
    `_qkv_proj_gemm_mma8x8_vecload4` already established. Bounds-checking/zero-padding at ragged
    M/K edges falls back to the ORIGINAL per-element ternary on both tiles, verbatim, identically
    to how `_qkv_proj_gemm_mma8x8_vecload4` itself handles its own ragged edges.

    Fragment load/compute (`apple_mma_load_8x8[DType.float32]`, `_mma_apple_8x8`, all-Float32
    operands into the unchanged `SIMD[DType.float32,2]` accumulators, FOUR fragments, `which in
    range(4)`, the `_SUBROWS_64 x _SUBCOLS_64` grid) and the final `_frag_row_col`-gated
    bounds-checked store are IDENTICAL, unedited, to `_qkv_proj_gemm_mma8x8_bm64`'s own
    accumulate/store loop -- this kernel changes ONLY the device-memory cooperative load, on top
    of `_qkv_proj_gemm_mma8x8_bm64`'s already-established tile-shape change.
    `_qkv_proj_gemm_mma8x8`, `_qkv_proj_gemm_mma8x8_bm64`, and `_qkv_proj_gemm_mma8x8_vecload4` are
    all left completely untouched above; this is a pure addition, verified via
    `probes/gemm_qkv_proj_bm64_vecload4_bench.mojo`."""
    var a_tile = stack_allocation[Int(_BM_64 * _BK_64), DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[Int(_BK_64 * _BN_64), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_tile_cols = (n + _BN_64 - 1) // _BN_64
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM_64
    var block_col = tile_col * _BN_64

    var acc0 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc1 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc2 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc3 = SIMD[DType.float32, 2](0.0, 0.0)

    var n_steps = (k + _BK_64 - 1) // _BK_64
    for step in range(n_steps):
        # A-tile (activation): `_N_CHUNKS_A_V4_BM64 == _NTHREADS_64` (256 == 256) -- every thread
        # owns exactly one 4-wide chunk, none idle (unlike vecload4's own A-tile at BM=32, where
        # only half the 256 threads are active). 4-wide device read + 4-wide shared-memory write
        # on the fast path; original per-element ternary, verbatim, on the slow path.
        if tid < _N_CHUNKS_A_V4_BM64:
            var crow_a = tid // _CHUNKS_PER_ROW_V4_BM64
            var ccol_grp_a = tid % _CHUNKS_PER_ROW_V4_BM64
            var col0_a = ccol_grp_a * _VEC4
            var idx0_a = crow_a * _BK_64 + col0_a

            var gr_a = block_row + crow_a
            var gc0_a = step * _BK_64 + col0_a
            if gr_a < m_rows and gc0_a + 3 < k:
                var av = xn.load[width=4](Int(gr_a * k + gc0_a))
                a_tile.store[width=4](Int(idx0_a), av)
            else:
                for c in range(4):
                    var gc_a = gc0_a + Int64(c)
                    a_tile[Int(idx0_a + Int64(c))] = xn[Int(gr_a * k + gc_a)] if (gr_a < m_rows and gc_a < k) else Float32(0.0)

        # B-tile (weight): `_N_CHUNKS_B_V4_BM64 = 128`, HALF of `_NTHREADS_64` -- unchanged from
        # `_qkv_proj_gemm_mma8x8_vecload4`'s own B-tile chunk count (`BN_64`/`BK_64` identical to
        # `BN`/`BK`), reused verbatim. 4-wide Int8 device read + ONE wscale lookup per chunk on the
        # fast path; original per-element ternary (own re-lookup) on the slow path.
        if tid < _N_CHUNKS_B_V4_BM64:
            var crow_b = tid // _CHUNKS_PER_ROW_V4_BM64
            var ccol_grp_b = tid % _CHUNKS_PER_ROW_V4_BM64
            var col0_b = ccol_grp_b * _VEC4

            var gr_b = block_col + crow_b
            var gc0_b = step * _BK_64 + col0_b
            if gr_b < n and gc0_b + 3 < k:
                var wv_i8 = w.load[width=4](Int(gr_b * k + gc0_b))
                var scale_v = SIMD[DType.float32, 4](wscale[Int(gr_b)])
                var wv = wv_i8.cast[DType.float32]() * scale_v
                for c in range(4):
                    b_tile[Int((col0_b + Int64(c)) * _BN_64 + crow_b)] = wv[c]
            else:
                for c in range(4):
                    var gc_b = gc0_b + Int64(c)
                    var val = Float32(w[Int(gr_b * k + gc_b)]) * wscale[Int(gr_b)] if (gr_b < n and gc_b < k) else Float32(0.0)
                    b_tile[Int((col0_b + Int64(c)) * _BN_64 + crow_b)] = val

        barrier()

        for ksub in range(Int(_BK_64 // 8)):
            for which in range(4):
                var sub_idx = sg + Int64(which) * 8
                var sub_row = sub_idx // _SUBCOLS_64
                var sub_col = sub_idx % _SUBCOLS_64
                var a_ptr = a_tile + Int(sub_row * 8 * _BK_64 + Int64(ksub) * 8)
                var b_ptr = b_tile + Int(Int64(ksub) * 8 * _BN_64 + sub_col * 8)
                var a_frag = apple_mma_load_8x8[DType.float32](a_ptr, Int(_BK_64))
                var b_frag = apple_mma_load_8x8[DType.float32](b_ptr, Int(_BN_64))
                if which == 0:
                    _mma_apple_8x8(acc0, a_frag, b_frag, acc0)
                elif which == 1:
                    _mma_apple_8x8(acc1, a_frag, b_frag, acc1)
                elif which == 2:
                    _mma_apple_8x8(acc2, a_frag, b_frag, acc2)
                else:
                    _mma_apple_8x8(acc3, a_frag, b_frag, acc3)

        barrier()

    var rc = _frag_row_col(tid)
    for which in range(4):
        var sub_idx = sg + Int64(which) * 8
        var sub_row = sub_idx // _SUBCOLS_64
        var sub_col = sub_idx % _SUBCOLS_64
        var frag = acc0
        if which == 1:
            frag = acc1
        elif which == 2:
            frag = acc2
        elif which == 3:
            frag = acc3
        var r = block_row + sub_row * 8 + rc[0]
        var c0 = block_col + sub_col * 8 + rc[1]
        var c1 = c0 + 1
        if r < m_rows and c0 < n:
            y[Int(r * n + c0)] = frag[0]
        if r < m_rows and c1 < n:
            y[Int(r * n + c1)] = frag[1]


def _gemm_accum_mma8x8_vecload4(
    y: _FP, x: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """Load-instruction-WIDTH isolation experiment, ACCUM role: byte-for-byte `_gemm_accum_mma8x8`
    (same `BM=32/BN=32/BK=16` tile shape, same 256 threads / 8 simdgroups, same accumulator-SEEDED-
    FROM-`y` behavior, same all-Float32 `apple_mma_load_8x8`/`_mma_apple_8x8` fragment load/compute,
    same final bounds-checked store via `_frag_row_col`) with ONLY the device-memory cooperative
    load re-widened from scalar to 4-wide, reusing `_qkv_proj_gemm_mma8x8_vecload4`'s own
    thread-to-chunk remap (`_VEC4`/`_CHUNKS_PER_ROW_V4`/`_N_CHUNKS_V4`) VERBATIM, not re-derived.
    `_gemm_accum_mma8x8` uses the exact same `_BM=32/_BN=32/_BK=16` module-level tile constants as
    `_qkv_proj_gemm_mma8x8` (confirmed by direct read of both kernels above: identical shared-memory
    tile sizes, identical `n_tile_cols`/`block_row`/`block_col` indexing, identical `step in
    range((k+_BK-1)//_BK)` loop) -- so the remap `_qkv_proj_gemm_mma8x8_vecload4` already built for
    that exact tile shape applies unchanged here; no new chunk-count constant is needed (unlike the
    BM64-stacking combination elsewhere in this file, which genuinely needed a new
    `_N_CHUNKS_A_V4_BM64` because BM64 changes `_BM`).

    ROLE-SPECIFIC PIECE THIS KERNEL MUST PRESERVE, UNCHANGED FROM `_gemm_accum_mma8x8` (the one
    thing that must NOT be copied from `_qkv_proj_gemm_mma8x8_vecload4`): the two accumulator
    fragments (`acc0`/`acc1`) are SEEDED from the EXISTING `y` values -- via `_frag_row_col` and the
    same per-element bounds check `_gemm_accum_mma8x8` already uses -- BEFORE the k-loop starts,
    instead of zeroed. Copied verbatim from `_gemm_accum_mma8x8` above, untouched by this
    experiment; only the cooperative-load phase inside the k-loop changes. `_mma_apple_8x8`'s own
    `D = A@B + C` shape still makes "+=" just "don't zero C" -- the vectorized load change never
    touches the accumulator itself, only how `a_tile`/`b_tile` get filled each step.

    A-TILE (activation, Float32) / B-TILE (weight, Int8 + one wscale lookup/chunk): identical
    fast-path (`x.load[width=4]`/`w.load[width=4]` + a single `wscale[row]` lookup shared across the
    4-wide chunk) and slow-path (the original per-element ternary, verbatim) logic as
    `_qkv_proj_gemm_mma8x8_vecload4`'s own A-tile/B-tile remap -- see that kernel's own docstring for
    the full thread-to-chunk derivation this reuses. The B-tile's `[BK,BN]` transposed shared-memory
    write (required by `apple_mma_load_8x8` for a valid `[K,N]`-oriented B operand) and its
    consequent "4 separate scalar stores, not one vector store" property are unchanged from that
    kernel too.

    Fragment load/compute (the `ksub`/`which` loop, `apple_mma_load_8x8[DType.float32]`,
    `_mma_apple_8x8`) and the final `_frag_row_col`-gated bounds-checked store are IDENTICAL,
    unedited, to `_gemm_accum_mma8x8`. `_gemm_accum_mma8x8`, `_qkv_proj_gemm_mma8x8_vecload4`, and
    every other kernel above are left completely untouched; this is a pure addition, verified via
    `probes/gemm_accum_vecload4_bench.mojo`. Reused for BOTH o_proj and down_proj, exactly as
    `_gemm_accum_mma8x8` already is."""
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
        if tid < _N_CHUNKS_V4:
            var crow = tid // _CHUNKS_PER_ROW_V4
            var ccol_grp = tid % _CHUNKS_PER_ROW_V4
            var col0 = ccol_grp * _VEC4
            var idx0 = crow * _BK + col0

            # A-tile (activation): 4-wide device read + 4-wide shared-memory write on the fast
            # path; original per-element ternary, verbatim, on the slow path -- identical remap to
            # `_qkv_proj_gemm_mma8x8_vecload4`'s own A-tile, applied to `x` (the accum role's
            # activation operand) instead of `xn`.
            var gr_a = block_row + crow
            var gc0_a = step * _BK + col0
            if gr_a < m_rows and gc0_a + 3 < k:
                var av = x.load[width=4](Int(gr_a * k + gc0_a))
                a_tile.store[width=4](Int(idx0), av)
            else:
                for c in range(4):
                    var gc_a = gc0_a + Int64(c)
                    a_tile[Int(idx0 + Int64(c))] = x[Int(gr_a * k + gc_a)] if (gr_a < m_rows and gc_a < k) else Float32(0.0)

            # B-tile (weight): 4-wide Int8 device read + ONE wscale lookup on the fast path
            # (disclosed side effect of chunking by row, same as `_qkv_proj_gemm_mma8x8_vecload4`);
            # original per-element ternary (own re-lookup) on the slow path. Shared-memory write
            # stays scalar x4 either way -- the `[BK,BN]` transpose layout makes a fixed-row,
            # varying-K chunk land `_BN` elements apart, not contiguous.
            var gr_b = block_col + crow
            var gc0_b = step * _BK + col0
            if gr_b < n and gc0_b + 3 < k:
                var wv_i8 = w.load[width=4](Int(gr_b * k + gc0_b))
                var scale_v = SIMD[DType.float32, 4](wscale[Int(gr_b)])
                var wv = wv_i8.cast[DType.float32]() * scale_v
                for c in range(4):
                    b_tile[Int((col0 + Int64(c)) * _BN + crow)] = wv[c]
            else:
                for c in range(4):
                    var gc_b = gc0_b + Int64(c)
                    var val = Float32(w[Int(gr_b * k + gc_b)]) * wscale[Int(gr_b)] if (gr_b < n and gc_b < k) else Float32(0.0)
                    b_tile[Int((col0 + Int64(c)) * _BN + crow)] = val

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


def _swiglu_gemm_mma8x8_vecload4(
    act: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n_ff: Int64
):
    """Load-instruction-WIDTH isolation experiment, SWIGLU role: byte-for-byte `_swiglu_gemm_mma8x8`
    (same `BM=32/BN=32/BK=16` tile shape, same 256 threads / 8 simdgroups, same FOUR-accumulator-
    fragment gate+up structure, same fused SwiGLU epilogue `(gate/(1+exp(-gate)))*up` computed on
    the raw accumulator fragments right before the store, same all-Float32 `apple_mma_load_8x8`/
    `_mma_apple_8x8` fragment load/compute) with ONLY the device-memory cooperative load re-widened
    from scalar to 4-wide, reusing `_qkv_proj_gemm_mma8x8_vecload4`'s own thread-to-chunk remap
    (`_VEC4`/`_CHUNKS_PER_ROW_V4`/`_N_CHUNKS_V4`) VERBATIM. `_swiglu_gemm_mma8x8` uses the exact same
    `_BM=32/_BN=32/_BK=16` module-level tile constants (confirmed by direct read above: identical
    `a_elems`/`step`-loop structure to `_qkv_proj_gemm_mma8x8`, just with a SECOND B-tile), so no new
    chunk-count constant is needed here either.

    THE ONE GENUINELY NEW PIECE OF LOGIC THIS ROLE REQUIRES (neither `_qkv_proj_gemm_mma8x8_vecload4`
    nor `_gemm_accum_mma8x8_vecload4` needed it): `_swiglu_gemm_mma8x8` cooperatively loads TWO
    B-tiles per K-step, not one -- `bg_tile` from `w`'s gate rows `[0,n_ff)` and `bu_tile` from the
    up rows `[n_ff,2*n_ff)` -- against the SAME loaded A-tile chunk (`crow`/`col0`/`gc0_b`, identical
    row/col arithmetic for both, exactly as the original scalar kernel's own `bc`/`br` are shared
    between its `bg_tile`/`bu_tile` writes). The vecload4 remap is therefore applied TWICE per active
    thread per step, once per B-tile: each does its OWN 4-wide `w.load[width=4]` device read at its
    own row offset (`gr_b*k+gc0_b` for gate, `(n_ff+gr_b)*k+gc0_b` for up) and its OWN single shared
    `wscale` lookup (`wscale[gr_b]` for gate, `wscale[n_ff+gr_b]` for up) -- the same "chunk by row,
    share one wscale across the 4-wide chunk" disclosed side effect `_qkv_proj_gemm_mma8x8_vecload4`
    already discloses, now instantiated twice (once per gate/up row-family) instead of once. Both
    dequantized 4-wide vectors are written with 4 separate SCALAR stores each (the `[BK,BN]`
    transposed shared-memory layout, unchanged from `_swiglu_gemm_mma8x8`'s own `bg_tile`/`bu_tile`,
    makes a fixed-row varying-K chunk land `_BN` elements apart in EITHER tile, not contiguous --
    identical reasoning to `_qkv_proj_gemm_mma8x8_vecload4`'s own single B-tile). The fast-path gate
    condition (`gr_b < n_ff and gc0_b + 3 < k`) covers BOTH tiles at once, since gate/up share the
    same row-validity bound (`n_ff`) and the same K-range -- only the row OFFSET into `w`/`wscale`
    differs between the two, exactly as the original scalar kernel's own single `if gr2 < n_ff and
    gc2 < k` guards both `bg_tile`/`bu_tile` writes together. Slow path re-does the original's own
    per-element branch, verbatim, for BOTH tiles together (including the original's own zero-fill
    for `gr_b >= n_ff or gc_b >= k`, checked once per element, governing both tiles identically).

    A-TILE (activation, Float32): identical fast-path (`xn.load[width=4]` + `a_tile.store[width=4]`)
    and slow-path (original per-element ternary, verbatim) to `_qkv_proj_gemm_mma8x8_vecload4`'s own
    A-tile remap -- unchanged by the two-B-tile structure, since the A-tile is shared/read-once
    exactly as `_swiglu_gemm_mma8x8` itself already does ("stage the activation once, read it
    twice").

    ROLE-SPECIFIC EPILOGUE THIS KERNEL MUST PRESERVE, UNCHANGED FROM `_swiglu_gemm_mma8x8` (the one
    thing NOT touched by this experiment): the four accumulator fragments (`acc_g0`/`acc_g1`/
    `acc_u0`/`acc_u1`) start at zero (assign role, not accum role -- no `y`-seeding here, correctly
    matching `_swiglu_gemm_mma8x8` and NOT `_gemm_accum_mma8x8_vecload4`), and the fused SwiGLU
    combine (`(g/(1+exp(-g)))*u`, elementwise on the two 2-element fragment pairs) runs immediately
    before the final bounds-checked store via `_frag_row_col` -- copied verbatim from
    `_swiglu_gemm_mma8x8`, untouched.

    Fragment load/compute (the `ksub`/`which` loop, both `bg_frag`/`bu_frag` MMA calls against the
    SAME `a_frag`, all-Float32 operands) and the final store are IDENTICAL, unedited, to
    `_swiglu_gemm_mma8x8`. `_swiglu_gemm_mma8x8`, `_qkv_proj_gemm_mma8x8_vecload4`,
    `_gemm_accum_mma8x8_vecload4`, and every other kernel above are left completely untouched; this
    is a pure addition, verified via `probes/gemm_swiglu_vecload4_bench.mojo`."""
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
        if tid < _N_CHUNKS_V4:
            var crow = tid // _CHUNKS_PER_ROW_V4
            var ccol_grp = tid % _CHUNKS_PER_ROW_V4
            var col0 = ccol_grp * _VEC4
            var idx0 = crow * _BK + col0

            # A-tile (activation): identical fast/slow path to `_qkv_proj_gemm_mma8x8_vecload4`'s
            # own A-tile -- shared between gate and up, read once per step.
            var gr_a = block_row + crow
            var gc0_a = step * _BK + col0
            if gr_a < m_rows and gc0_a + 3 < k:
                var av = xn.load[width=4](Int(gr_a * k + gc0_a))
                a_tile.store[width=4](Int(idx0), av)
            else:
                for c in range(4):
                    var gc_a = gc0_a + Int64(c)
                    a_tile[Int(idx0 + Int64(c))] = xn[Int(gr_a * k + gc_a)] if (gr_a < m_rows and gc_a < k) else Float32(0.0)

            # B-tiles (weight, gate + up): two independent 4-wide Int8 device reads sharing the SAME
            # (crow, col0) chunk coordinates, each with its OWN single wscale lookup (row `gr_b` for
            # gate, row `n_ff+gr_b` for up) -- the vecload4 remap applied twice per active thread,
            # once per B-tile, exactly mirroring the original scalar kernel's own shared bc/br
            # indexing into two tiles.
            var gr_b = block_col + crow
            var gc0_b = step * _BK + col0
            if gr_b < n_ff and gc0_b + 3 < k:
                var wg_i8 = w.load[width=4](Int(gr_b * k + gc0_b))
                var wu_i8 = w.load[width=4](Int((n_ff + gr_b) * k + gc0_b))
                var gscale_v = SIMD[DType.float32, 4](wscale[Int(gr_b)])
                var uscale_v = SIMD[DType.float32, 4](wscale[Int(n_ff + gr_b)])
                var wg = wg_i8.cast[DType.float32]() * gscale_v
                var wu = wu_i8.cast[DType.float32]() * uscale_v
                for c in range(4):
                    bg_tile[Int((col0 + Int64(c)) * _BN + crow)] = wg[c]
                    bu_tile[Int((col0 + Int64(c)) * _BN + crow)] = wu[c]
            else:
                for c in range(4):
                    var gc_b = gc0_b + Int64(c)
                    if gr_b < n_ff and gc_b < k:
                        bg_tile[Int((col0 + Int64(c)) * _BN + crow)] = Float32(w[Int(gr_b * k + gc_b)]) * wscale[Int(gr_b)]
                        bu_tile[Int((col0 + Int64(c)) * _BN + crow)] = Float32(w[Int((n_ff + gr_b) * k + gc_b)]) * wscale[Int(n_ff + gr_b)]
                    else:
                        bg_tile[Int((col0 + Int64(c)) * _BN + crow)] = Float32(0.0)
                        bu_tile[Int((col0 + Int64(c)) * _BN + crow)] = Float32(0.0)

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


comptime _NTHREADS_SG4: Int64 = 128
comptime _N_SG_SG4: Int64 = _NTHREADS_SG4 // 32
comptime _SUBTILES_PER_SG_SG4: Int64 = _N_SUBTILES // _N_SG_SG4
"""SIMD-GROUP-COUNT isolation axis, a new, distinct tournament variable from every prior entry in
this file: HALVE the simdgroup/thread count at the ORIGINAL `BM=32/BN=32/BK=16` tile shape, instead
of growing the tile at a fixed simdgroup count (`_qkv_proj_gemm_mma8x8_bm64`'s own axis) or
narrowing the MMA operand type (`_qkv_proj_gemm_mma8x8_f16`'s axis) or widening the cooperative-load
instruction (`_qkv_proj_gemm_mma8x8_vecload4`'s axis, reused here verbatim, not touched).

Motivating hypothesis (see `REALRACE_RESULTS.md`'s own "Project Redline reopening" narrative for the
full arithmetic): `_qkv_proj_gemm_mma8x8_vecload4` schedules `((256+31)//32)*((4096+31)//32) = 8*128
= 1024` threadgroups x 8 simdgroups/threadgroup = 8192 total SIMD-group instances at the real
qkv_proj shape, each doing only `_SUBTILES_PER_SG=2` fragments' worth of useful MMA work while still
paying full per-simdgroup fixed overhead (address generation, loop bookkeeping, barriers,
shared-memory traffic) plus Int8 dequant -- vs. llama.cpp's 512 threadgroups x 4 simdgroups = 2048
total SIMD-group instances for the IDENTICAL mathematical operation count. This kernel tests that
hypothesis DIRECTLY: same output tile (`_BM=32/_BN=32`), same `_BK=16`, same `_VEC4=4`-wide
vectorized global loads (`_qkv_proj_gemm_mma8x8_vecload4`'s own remap, reused verbatim below), same
Int8+per-chunk-scale dequant scheme, same all-Float32 MMA -- but `_NTHREADS_SG4=128` threads /
`_N_SG_SG4=4` simdgroups per threadgroup instead of `_NTHREADS=256`/8, so each simdgroup now owns
`_SUBTILES_PER_SG_SG4 = _N_SUBTILES // _N_SG_SG4 = 16 // 4 = 4` accumulator fragments instead of the
original `_SUBTILES_PER_SG=2` -- the SAME fragment-count-4 resource level
`_qkv_proj_gemm_mma8x8_bm64` already proved viable (well below `_qkv_proj_gemm_mma8x8_bm128`'s
8-fragment cliff), but reached here by HALVING simdgroup count at the ORIGINAL BM=32, not by
doubling BM at a fixed 8 simdgroups. The dispatch grid formula is therefore UNCHANGED from both the
original kernel and `_qkv_proj_gemm_mma8x8_vecload4` (`((M+31)//32)*((N+31)//32)`, still 1024
threadgroups at the real qkv_proj shape) -- ONLY the per-threadgroup simdgroup/thread/fragment count
changes, giving `1024 * _N_SG_SG4 = 1024 * 4 = 4096` total SIMD-group instances, HALF of
`_qkv_proj_gemm_mma8x8_vecload4`'s own 8192, at exactly double the useful-work-per-group (4 fragments
vs 2) -- the same total mathematical work, scheduled as half as many, twice-as-busy SIMD-group
instances.

THREAD-TO-CHUNK REMAP -- reuses `_qkv_proj_gemm_mma8x8_vecload4`'s own `_VEC4`/`_CHUNKS_PER_ROW_V4`/
`_N_CHUNKS_V4` constants VERBATIM (load width and tile shape are not variables in this experiment):
`_N_CHUNKS_V4 = (_BM*_BK)//_VEC4 = 512//4 = 128`, identically `_BN*_BK//_VEC4 = 128` for the B-tile
(same as `_qkv_proj_gemm_mma8x8_vecload4`'s own derivation, `_BM==_BN==32` here). That un-stacked
kernel had `_NTHREADS=256`, so only HALF its threads (`tid < 128`) were active during each tile's
load phase, the other half idling through it (still hitting the same barriers). Here,
`_NTHREADS_SG4=128` matches `_N_CHUNKS_V4` EXACTLY (128 == 128) -- for BOTH tiles, since
`_BM*_BK == _BN*_BK` here -- so EVERY one of the 128 threads owns exactly one 4-wide A-tile chunk
AND exactly one 4-wide B-tile chunk, every step, with no `if tid < _N_CHUNKS_V4:` gate needed at all:
the gate is unconditionally true for every thread in this threadgroup, so it is simply omitted below
(unlike the un-stacked kernel's own half-idle 128-of-256 pattern). This is itself a disclosable
structural property, not a hidden simplification: halving the thread count to exactly match the
already-fixed `_N_CHUNKS_V4=128` chunk count (an arithmetic coincidence of `_BM*_BK/_VEC4` landing on
128, not a new tuning knob) eliminates the load-phase idle-thread split entirely, for both tiles
simultaneously, without changing a single index formula from the un-stacked kernel's own remap.

Fragment accumulate/store: FOUR accumulator fragments (`acc0`..`acc3`) and a `which in range(4)`
loop (both at the accumulate step and the final store), cyclically assigned via
`sub_idx = sg + which * _N_SG_SG4` (multiplier `_N_SG_SG4=4`, the simdgroup count -- NOT 8, since
there are only 4 simdgroups here) over the SAME `4x4` subtile grid `_qkv_proj_gemm_mma8x8` and
`_qkv_proj_gemm_mma8x8_vecload4` already use (`_BM//8=4` rows x `_BN//8=4` cols -- unchanged, since
BM/BN did not change): for `sg in {0,1,2,3}` and `which in {0,1,2,3}`, `sub_idx` sweeps
`{sg, sg+4, sg+8, sg+12}`, and the union over all four `sg` values is exactly `{0..15}` with no gaps
or overlap -- every one of the 16 subtiles (`_N_SUBTILES=16`, unchanged) is covered exactly once.
Byte-for-byte the same `_mma_apple_8x8`/`apple_mma_load_8x8` fragment load/compute and the same
`_frag_row_col`-gated bounds-checked final store as every other kernel in this file -- only the
simdgroup/thread count, the fragment-count-per-simdgroup, and the load-phase idle-thread pattern
change. `_qkv_proj_gemm_mma8x8`, `_qkv_proj_gemm_mma8x8_bm64`, and `_qkv_proj_gemm_mma8x8_vecload4`
are all left completely untouched above; this is a pure addition, verified via
`probes/gemm_qkv_proj_vecload4_sg4_bench.mojo` and
`probes/gemm_qkv_proj_batching_sim_gpuonly_vecload4_sg4.mojo`."""


def _qkv_proj_gemm_mma8x8_vecload4_sg4(
    y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int64, k: Int64, n: Int64
):
    """`_qkv_proj_gemm_mma8x8_vecload4` with simdgroup count HALVED (`_NTHREADS_SG4=128`/
    `_N_SG_SG4=4` in place of `_NTHREADS=256`/8) at the SAME `_BM=32/_BN=32/_BK=16` tile shape --
    see `_SUBTILES_PER_SG_SG4`'s own docstring immediately above for the full motivating hypothesis
    (SIMD-group-instance-count vs useful-work-per-group) and the structural consequences halving
    simdgroup count requires. Byte-for-byte identical to `_qkv_proj_gemm_mma8x8_vecload4` except:
    (1) `_NTHREADS_SG4`/`_N_SG_SG4` in place of `_NTHREADS`/8 everywhere a thread/simdgroup count is
    used, (2) the A-tile and B-tile cooperative loads are UNCONDITIONAL (no `if tid < _N_CHUNKS_V4:`
    gate -- every thread is active, since `_N_CHUNKS_V4 == _NTHREADS_SG4` exactly, unlike the
    un-stacked kernel's own half-idle split), and (3) FOUR accumulator fragments (`acc0`..`acc3`)
    and a `which in range(4)` loop (both at the accumulate step and the final store) instead of two
    fragments and `which in range(2)`, cyclically assigned via `sub_idx = sg + which * _N_SG_SG4`
    over the SAME `4x4` subtile grid the un-stacked kernel already uses (BM/BN unchanged). The
    4-wide vectorized device-memory load/convert, the Int8 per-chunk-scale dequant, the transposed
    `[BK,BN]` B-tile shared-memory layout, the barrier placement, and the final
    `_frag_row_col`-gated bounds-checked store are all identical in structure to
    `_qkv_proj_gemm_mma8x8_vecload4` -- only re-parameterized for the new thread/simdgroup/fragment
    counts. `_qkv_proj_gemm_mma8x8`, `_qkv_proj_gemm_mma8x8_bm64`, and
    `_qkv_proj_gemm_mma8x8_vecload4` themselves, and every other kernel above, are left completely
    untouched; this is a pure addition."""
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
    var acc2 = SIMD[DType.float32, 2](0.0, 0.0)
    var acc3 = SIMD[DType.float32, 2](0.0, 0.0)

    var n_steps = (k + _BK - 1) // _BK
    for step in range(n_steps):
        # `_N_CHUNKS_V4 (128) == _NTHREADS_SG4 (128)` exactly, for BOTH tiles (`_BM*_BK ==
        # _BN*_BK` here) -- every one of the 128 threads owns exactly one 4-wide A-tile chunk AND
        # one 4-wide B-tile chunk, unconditionally, every step. No `if tid < _N_CHUNKS_V4:` gate is
        # needed (unlike `_qkv_proj_gemm_mma8x8_vecload4`'s own half-idle 128-of-256 pattern) --
        # this is a direct arithmetic consequence of halving the thread count to match the
        # already-fixed chunk count, not a new index formula.
        var crow = tid // _CHUNKS_PER_ROW_V4
        var ccol_grp = tid % _CHUNKS_PER_ROW_V4
        var col0 = ccol_grp * _VEC4
        var idx0 = crow * _BK + col0

        # A-tile (activation): 4-wide device read + 4-wide shared-memory write on the fast path;
        # original per-element ternary, verbatim, on the slow path -- byte-for-byte
        # `_qkv_proj_gemm_mma8x8_vecload4`'s own A-tile logic, just no longer gated by `tid`.
        var gr_a = block_row + crow
        var gc0_a = step * _BK + col0
        if gr_a < m_rows and gc0_a + 3 < k:
            var av = xn.load[width=4](Int(gr_a * k + gc0_a))
            a_tile.store[width=4](Int(idx0), av)
        else:
            for c in range(4):
                var gc_a = gc0_a + Int64(c)
                a_tile[Int(idx0 + Int64(c))] = xn[Int(gr_a * k + gc_a)] if (gr_a < m_rows and gc_a < k) else Float32(0.0)

        # B-tile (weight): SAME (crow, col0) chunk coordinates reused for the B-tile, exactly as
        # `_qkv_proj_gemm_mma8x8_vecload4` itself does -- 4-wide Int8 device read + ONE wscale
        # lookup on the fast path, original per-element ternary (own re-lookup) on the slow path.
        var gr_b = block_col + crow
        var gc0_b = step * _BK + col0
        if gr_b < n and gc0_b + 3 < k:
            var wv_i8 = w.load[width=4](Int(gr_b * k + gc0_b))
            var scale_v = SIMD[DType.float32, 4](wscale[Int(gr_b)])
            var wv = wv_i8.cast[DType.float32]() * scale_v
            for c in range(4):
                b_tile[Int((col0 + Int64(c)) * _BN + crow)] = wv[c]
        else:
            for c in range(4):
                var gc_b = gc0_b + Int64(c)
                var val = Float32(w[Int(gr_b * k + gc_b)]) * wscale[Int(gr_b)] if (gr_b < n and gc_b < k) else Float32(0.0)
                b_tile[Int((col0 + Int64(c)) * _BN + crow)] = val

        barrier()

        for ksub in range(Int(_BK // 8)):
            for which in range(4):
                var sub_idx = sg + Int64(which) * _N_SG_SG4
                var sub_row = sub_idx // 4
                var sub_col = sub_idx % 4
                var a_ptr = a_tile + Int(sub_row * 8 * _BK + Int64(ksub) * 8)
                var b_ptr = b_tile + Int(Int64(ksub) * 8 * _BN + sub_col * 8)
                var a_frag = apple_mma_load_8x8[DType.float32](a_ptr, Int(_BK))
                var b_frag = apple_mma_load_8x8[DType.float32](b_ptr, Int(_BN))
                if which == 0:
                    _mma_apple_8x8(acc0, a_frag, b_frag, acc0)
                elif which == 1:
                    _mma_apple_8x8(acc1, a_frag, b_frag, acc1)
                elif which == 2:
                    _mma_apple_8x8(acc2, a_frag, b_frag, acc2)
                else:
                    _mma_apple_8x8(acc3, a_frag, b_frag, acc3)

        barrier()

    var rc = _frag_row_col(tid)
    for which in range(4):
        var sub_idx = sg + Int64(which) * _N_SG_SG4
        var sub_row = sub_idx // 4
        var sub_col = sub_idx % 4
        var frag = acc0
        if which == 1:
            frag = acc1
        elif which == 2:
            frag = acc2
        elif which == 3:
            frag = acc3
        var r = block_row + sub_row * 8 + rc[0]
        var c0 = block_col + sub_col * 8 + rc[1]
        var c1 = c0 + 1
        if r < m_rows and c0 < n:
            y[Int(r * n + c0)] = frag[0]
        if r < m_rows and c1 < n:
            y[Int(r * n + c1)] = frag[1]


def _qkv_proj_gemm_mma8x8_llama_parity(
    y: _FP, xn: _FP, w_f16: _F16P, m_rows: Int64, k: Int64, n: Int64
):
    """Attention Compiler Plan v1.0 ("Project Redline"), MSL-replica-validated llama.cpp GEMM
    structure, ported into Mojo -- the task that follows the MSL replica's own decisive admission-
    gate PASS (`benchmarks/llm_smoke/metal_llama_parity_replica/llama_parity_replica.metal`,
    independently re-verified fresh in THIS session, before writing this kernel: 4/4 fresh runs of
    that replica's own common Objective-C harness land at 0.35-0.39% difference from the real
    llama.cpp `kernel_mul_mm_f16_f32` kernel -- decisively inside the pre-registered 5% admission
    gate, with bit-identical CPU-Float64-oracle correctness for both kernels). This kernel replicates
    EVERY structural choice that MSL replica validated, translated into Mojo's existing hardware-MMA
    idiom (`apple_mma_load_8x8`/`_mma_apple_8x8`, the same mechanism every other kernel in this file
    uses) with exactly ONE disclosed, unavoidable deviation -- see "THE ONE DELIBERATE DEVIATION"
    below.

    TILE SHAPE (`_BM_W=32`/`_BN_W=64`/`_BK_W=32`, `_NTHREADS_W=128` -- 4 simdgroups; REUSED verbatim
    from `_qkv_proj_gemm_mma8x8_wide`'s own already-derived constants above; those constants are pure
    tile-geometry, not tied to that kernel's own cyclic fragment-assignment scheme, so reusing them
    here introduces no coupling to that scheme). llama.cpp's own `kernel_mul_mm` legacy-path geometry
    (`NR0=64` tiles N via `tgpig.y`, `NR1=32` tiles M via `tgpig.x`, `NK=32` K-step, `nsg=4`) was
    already re-derived directly from `ggml-metal.metal`/`ggml-metal-impl.h`/`ggml-metal-ops.cpp` by
    `_qkv_proj_gemm_mma8x8_wide`'s own docstring, and independently again by
    `llama_parity_replica.metal`'s own item-1 provenance comment -- both agree: grid=(8,64,1)=512
    threadgroups at M=256/K=1024/N=4096, matching this whole investigation's own already-established
    figure.

    OPERAND STORAGE -- the genuinely new axis this kernel isolates, per this task's own instruction
    (native F16 storage for BOTH operands, NOT Algenta's Int8+scale dequant scheme): `w_f16` is
    ALREADY Float16 in device memory (produced once, upstream -- e.g. by this file's own
    `_pack_i8_weights_to_f16_kernel`, reused unmodified, not re-derived here), matching
    `llama_parity_replica.metal`'s own `T0=half` weight representation exactly: no Int8 read, no
    `wscale` read, zero runtime dequantization of any kind, a straight copy into shared memory. `xn`
    stays Float32 in device memory, narrowed to Float16 only when scattered into shared memory --
    matching the replica's own `T1=float` activation representation and its own real-kernel-derived
    asymmetry (`kernel_mul_mm_f16_f32`'s own name: F16 weights x F32 activations). Both shared-memory
    tiles (`a_tile`/`b_tile` below) are declared `DType.float16`, so `apple_mma_load_8x8[DType.
    float16]` selects Apple's native `simdgroup_half8x8` fragment type for BOTH operands, mirroring
    the replica's own `S0=S1=half` mixed-precision-multiply/full-precision-accumulate scheme
    (accumulator type stays `SIMD[DType.float32,2]`, unchanged from every other kernel in this file).

    FRAGMENT OWNERSHIP -- the SECOND genuinely new axis, explicitly NOT `_qkv_proj_gemm_mma8x8_wide`'s
    own cyclic `sub_idx = sg + which*4` scheme. Ported instead directly from
    `llama_parity_replica.metal`'s own item-8/9 structure (itself read line-for-line from
    `ggml-metal.metal:10283-10310`): each of the 4 simdgroups owns a CONTIGUOUS 16(M)x32(N) block of
    the 32(M)x64(N) output tile, selected by `sg_m_half = sg // 2` (which 16-row M-half) and
    `sg_n_half = sg % 2` (which 32-col N-half) -- llama.cpp's own `sgitg>>1`/`sgitg&1`. Within that
    block, TWO activation fragments (`a_frag0`/`a_frag1`, covering the block's own two 8-row M-halves
    -- llama.cpp's own `mb[2]`, its "B"-operand-but-actually-activation array, see NAMING DISCLOSURE
    below) are each paired against FOUR weight fragments (`b_frag0..b_frag3`, covering the block's
    own four 8-col N-quarters -- llama.cpp's own `ma[4]`, its "A"-operand-but-actually-weight array)
    to produce exactly 8 accumulators (`mc0..mc7`) -- llama.cpp's OWN `mb[i/4], ma[i%4]` pairing for
    `mc[i], i=0..7`, ported with the SAME 6-load/8-multiply-accumulate structure per K-substep (2
    activation loads + 4 weight loads feeding 8 MMA calls, not 8 independent fragment-pair reloads)
    -- llama.cpp's own real efficiency property, not just its fragment COUNT.

    NAMING DISCLOSURE (read before comparing variable names line-for-line against
    `llama_parity_replica.metal`): llama.cpp's `kernel_mul_mm` names its OWN "A"/`sa`/`ma[]` operand
    as the WEIGHT (`src0`, tied to the N/`ne0`/`nr0=64` axis) and its "B"/`sb`/`mb[]` operand as the
    ACTIVATION (`src1`, tied to the M/`ne1`/`nr1=32` axis) -- confirmed directly from the replica's
    own kernel body (`x`/`sa` reads `src0` at `r0+lr0`, `lr0` ranging over `NR0=64`; `y`/`sb` reads
    `src1` at `r1+lr1`, `lr1` ranging over `NR1=32`). This file keeps ITS OWN, opposite,
    already-established naming (`a_tile`=activation/M, `b_tile`=weight/N, matching every other kernel
    above) rather than adopt llama.cpp's own inverted convention. Re-deriving the matrix-multiply
    roles confirms this is a pure NAMING difference, not a computation difference:
    `simdgroup_multiply_accumulate(mc[i], mb[i/4], ma[i%4], mc[i])` computes `mc = mb @ ma` (`mb` is
    the LEFT/row operand, `ma` is the RIGHT/column operand); since `mb`'s 2 fragments are indexed by
    `i/4` (matching `mc`'s own row/M index) and `ma`'s 4 fragments are indexed by `i%4` (matching
    `mc`'s own col/N index), `mb`(activation) plays EXACTLY the role Algenta's own `a_frag` plays
    (first argument to `_mma_apple_8x8`) and `ma`(weight) plays EXACTLY the role Algenta's own
    `b_frag` plays (second argument) -- so `_mma_apple_8x8(mc_i, a_frag_x, b_frag_y, mc_i)` below is
    the byte-for-byte SAME multiply-accumulate llama.cpp's own kernel issues, just spelled with this
    file's own operand names.

    SHARED-MEMORY TILE SIZE (matches the replica's own item-5 layout exactly, by construction of the
    tile-shape/storage choices above): `a_tile` (activation, natural `[_BM_W,_BK_W]=[32,32]`
    row-major) = 32*32*2B = 2048B, matching the replica's own `sb` (its activation tile) size exactly.
    `b_tile` (weight, TRANSPOSED `[_BK_W,_BN_W]=[32,64]` -- required since `_mma_apple_8x8` has no
    transpose flag, the SAME transpose convention every other kernel in this file already uses for
    its own weight tile) = 32*64*2B = 4096B, matching the replica's own `sa` (its weight tile) size
    exactly. Total 6144B, matching the replica's own driver-derived `4096+2048` total exactly (both
    land at the same total via the same two tile roles, just assigned to oppositely-named variables
    per the NAMING DISCLOSURE above).

    COOPERATIVE LOAD WIDTH -- the THIRD genuinely new axis (matches the replica's own item-6/7 wide
    loads as closely as Mojo's `UnsafePointer.load[width=N]` API allows): with `_NTHREADS_W=128`
    threads and `_BM_W*_BK_W=1024` activation elements, an 8-wide load (`xn.load[width=8]`, narrowed
    to Float16, `a_tile.store[width=8]`) gives EXACTLY 128 chunks -- one per thread, zero idle
    threads during this phase -- mirroring the replica's own 8-wide `half2x4` activation load
    (`NL1=NK/8=4` threads per activation row, `128/4=32=_BM_W` rows covered). With
    `_BK_W*_BN_W=2048` weight elements, a 16-wide load (`w_f16.load[width=16]`, ALREADY Float16, no
    narrowing) gives EXACTLY 128 chunks too -- mirroring the replica's own 16-wide `half4x4` weight
    load (`NL0=NK/16=2` threads per weight row, `128/2=64=_BN_W` rows covered). The weight tile's
    16-wide DEVICE READ is followed by 16 separate scalar THREADGROUP WRITES (the transposed
    `[_BK_W,_BN_W]` layout means 16 consecutive K-values for one row land `_BN_W` elements apart in
    shared memory, not contiguously) -- the SAME "wide read, scalar scatter write" idiom
    `_qkv_proj_gemm_mma8x8_vecload4`'s own docstring already established and disclosed for its own
    B-tile, reused here for the same structural reason.

    THE ONE DELIBERATE DEVIATION FROM FULL STRUCTURAL FIDELITY, matching this task's own explicit
    instruction: llama.cpp's native `simdgroup_load`/`simdgroup_multiply_accumulate` fragment
    mechanism has NO available binding in Mojo on this pinned toolchain -- confirmed decisively,
    twice, independently (`apple_mma_load_8x8`'s own documented 2-element-per-thread return
    contract, AND a direct `llvm_intrinsic` binding spike that hit a real Mojo compiler legalization
    ceiling for ANY pointer-typed operand to this specific intrinsic -- see REALRACE_RESULTS.md's
    "Native 64-wide MMA fragment loading" and "Native Fragment Forge spike" entries). This kernel
    uses `apple_mma_load_8x8`/`_mma_apple_8x8` -- the SAME manual fragment-construction mechanism
    every other kernel in this file already uses -- for the fragment load/store specifically. This
    is the ONE genuine gap versus full fidelity to the MSL replica; every other structural choice
    above (tile shape, operand storage/type, fragment ownership/pairing, tile size, load width) is
    ported as closely as Mojo's existing primitives allow.

    Pure addition: `_qkv_proj_gemm_mma8x8`, `_qkv_proj_gemm_mma8x8_f16`, `_qkv_proj_gemm_mma8x8_wide`,
    `_qkv_proj_gemm_mma8x8_prepacked_f16`, `_qkv_proj_gemm_mma8x8_vecload4`, and every other kernel in
    this file are left completely untouched by this addition."""
    var a_tile = stack_allocation[Int(_BM_W * _BK_W), DType.float16, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[Int(_BK_W * _BN_W), DType.float16, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32
    var sg_m_half = sg // 2
    var sg_n_half = sg % 2

    var n_tile_cols = (n + _BN_W - 1) // _BN_W
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM_W
    var block_col = tile_col * _BN_W

    var mc0 = SIMD[DType.float32, 2](0.0, 0.0)
    var mc1 = SIMD[DType.float32, 2](0.0, 0.0)
    var mc2 = SIMD[DType.float32, 2](0.0, 0.0)
    var mc3 = SIMD[DType.float32, 2](0.0, 0.0)
    var mc4 = SIMD[DType.float32, 2](0.0, 0.0)
    var mc5 = SIMD[DType.float32, 2](0.0, 0.0)
    var mc6 = SIMD[DType.float32, 2](0.0, 0.0)
    var mc7 = SIMD[DType.float32, 2](0.0, 0.0)

    var n_steps = (k + _BK_W - 1) // _BK_W
    for step in range(n_steps):
        # ---- A-tile (activation, Float32 device -> Float16 shared): 8-wide cooperative load, one
        # chunk per thread (128 threads, 128 chunks: _BM_W*_BK_W=1024 elements / 8). Mirrors the
        # replica's own 8-wide `half2x4` activation load width exactly. ----
        var a_row = tid // 4
        var a_which = tid % 4
        var a_col0 = a_which * 8
        var a_idx0 = a_row * _BK_W + a_col0
        var gr_a = block_row + a_row
        var gc0_a = step * _BK_W + a_col0
        if gr_a < m_rows and gc0_a + 7 < k:
            var av = xn.load[width=8](Int(gr_a * k + gc0_a))
            var av_f16 = av.cast[DType.float16]()
            a_tile.store[width=8](Int(a_idx0), av_f16)
        else:
            for c in range(8):
                var gc_a = gc0_a + Int64(c)
                a_tile[Int(a_idx0 + Int64(c))] = Float16(xn[Int(gr_a * k + gc_a)]) if (gr_a < m_rows and gc_a < k) else Float16(0.0)

        # ---- B-tile (weight, ALREADY Float16 device -> Float16 shared, ZERO dequant): 16-wide
        # device read, 16 scalar transposed-scatter writes (one chunk per thread, 128 threads, 128
        # chunks: _BK_W*_BN_W=2048 elements / 16). Mirrors the replica's own 16-wide `half4x4`
        # weight load width exactly. ----
        var b_row = tid // 2
        var b_which = tid % 2
        var b_col0 = b_which * 16
        var gr_b = block_col + b_row
        var gc0_b = step * _BK_W + b_col0
        if gr_b < n and gc0_b + 15 < k:
            var wv = w_f16.load[width=16](Int(gr_b * k + gc0_b))
            for c in range(16):
                b_tile[Int((b_col0 + Int64(c)) * _BN_W + b_row)] = wv[c]
        else:
            for c in range(16):
                var gc_b = gc0_b + Int64(c)
                b_tile[Int((b_col0 + Int64(c)) * _BN_W + b_row)] = w_f16[Int(gr_b * k + gc_b)] if (gr_b < n and gc_b < k) else Float16(0.0)

        barrier()

        for ksub in range(Int(_BK_W // 8)):
            # ---- fragment loads: 2 activation ("mb", Algenta a_frag) + 4 weight ("ma", Algenta
            # b_frag) -- llama.cpp's own 6-load/8-multiply-accumulate structure, not 8 independent
            # fragment-pair reloads. ----
            var m_group0 = sg_m_half * 2
            var m_group1 = sg_m_half * 2 + 1
            var a_ptr0 = a_tile + Int(m_group0 * 8 * _BK_W + Int64(ksub) * 8)
            var a_ptr1 = a_tile + Int(m_group1 * 8 * _BK_W + Int64(ksub) * 8)
            var a_frag0 = apple_mma_load_8x8[DType.float16](a_ptr0, Int(_BK_W))
            var a_frag1 = apple_mma_load_8x8[DType.float16](a_ptr1, Int(_BK_W))

            var n_group0 = sg_n_half * 4
            var n_group1 = sg_n_half * 4 + 1
            var n_group2 = sg_n_half * 4 + 2
            var n_group3 = sg_n_half * 4 + 3
            var b_ptr0 = b_tile + Int(Int64(ksub) * 8 * _BN_W + n_group0 * 8)
            var b_ptr1 = b_tile + Int(Int64(ksub) * 8 * _BN_W + n_group1 * 8)
            var b_ptr2 = b_tile + Int(Int64(ksub) * 8 * _BN_W + n_group2 * 8)
            var b_ptr3 = b_tile + Int(Int64(ksub) * 8 * _BN_W + n_group3 * 8)
            var b_frag0 = apple_mma_load_8x8[DType.float16](b_ptr0, Int(_BN_W))
            var b_frag1 = apple_mma_load_8x8[DType.float16](b_ptr1, Int(_BN_W))
            var b_frag2 = apple_mma_load_8x8[DType.float16](b_ptr2, Int(_BN_W))
            var b_frag3 = apple_mma_load_8x8[DType.float16](b_ptr3, Int(_BN_W))

            # ---- 8 multiply-accumulates: llama.cpp's own `mc[i] = mb[i/4] @ ma[i%4]` pairing,
            # i=0..7, ported verbatim (see NAMING DISCLOSURE above for the operand-role mapping). ----
            _mma_apple_8x8(mc0, a_frag0, b_frag0, mc0)
            _mma_apple_8x8(mc1, a_frag0, b_frag1, mc1)
            _mma_apple_8x8(mc2, a_frag0, b_frag2, mc2)
            _mma_apple_8x8(mc3, a_frag0, b_frag3, mc3)
            _mma_apple_8x8(mc4, a_frag1, b_frag0, mc4)
            _mma_apple_8x8(mc5, a_frag1, b_frag1, mc5)
            _mma_apple_8x8(mc6, a_frag1, b_frag2, mc6)
            _mma_apple_8x8(mc7, a_frag1, b_frag3, mc7)

        barrier()

    # ---- final store: 8 fragments, one contiguous 16(M)x32(N) block per simdgroup, bounds-checked
    # via `_frag_row_col` -- this file's own established partial-tile discipline, unchanged. ----
    var rc = _frag_row_col(tid)
    for which in range(8):
        var a_idx = Int64(which) // 4
        var b_idx = Int64(which) % 4
        var frag = mc0
        if which == 1:
            frag = mc1
        elif which == 2:
            frag = mc2
        elif which == 3:
            frag = mc3
        elif which == 4:
            frag = mc4
        elif which == 5:
            frag = mc5
        elif which == 6:
            frag = mc6
        elif which == 7:
            frag = mc7
        var r = block_row + sg_m_half * 16 + a_idx * 8 + rc[0]
        var c0 = block_col + sg_n_half * 32 + b_idx * 8 + rc[1]
        var c1 = c0 + 1
        if r < m_rows and c0 < n:
            y[Int(r * n + c0)] = frag[0]
        if r < m_rows and c1 < n:
            y[Int(r * n + c1)] = frag[1]


def _gemm_accum_mma8x8_llama_parity(
    y: _FP, x: _FP, w_f16: _F16P, m_rows: Int64, k: Int64, n: Int64
):
    """Attention Compiler Plan v1.0 ("Project Redline"), MSL-replica-validated llama.cpp GEMM
    structure, ported into Mojo for the ACCUM role (o_proj + down_proj) -- the task that follows the
    MSL replica extension's own decisive admission-gate PASS
    (`benchmarks/llm_smoke/metal_llama_parity_replica/llama_parity_replica_oproj.metal` and
    `llama_parity_replica_downproj.metal`, independently re-verified via that task's own fresh
    disassembly/correctness/timing runs before this kernel was written). Byte-for-byte
    `_qkv_proj_gemm_mma8x8_llama_parity` above -- same `_BM_W=32/_BN_W=64/_BK_W=32` tile shape, same 4
    simdgroups/128 threads, same native-F16-storage-for-both-operands asymmetry (`w_f16` already
    Float16 in device memory, zero runtime dequant; `x` narrowed to Float16 only on the shared-memory
    scatter), same llama.cpp-own contiguous-block 8-fragment ownership and `mb[i/4],ma[i%4]` pairing,
    same matched shared-memory sizes/load widths, same ONE disclosed deviation (manual
    `apple_mma_load_8x8`/`_mma_apple_8x8` fragment construction -- native `simdgroup_load` remains
    confirmed unavailable in Mojo on this toolchain) -- EXCEPT the 8 accumulator fragments (`mc0..
    mc7`) are SEEDED from the EXISTING `y` values instead of zero, exactly the same "+=" idea
    `_gemm_accum_mma8x8`'s own docstring already established for the original 2-fragment kernel
    (`_mma_apple_8x8`'s own `D = A@B + C` shape makes "+=" just "don't zero C," no separate add-back
    step needed after the k-loop) and the same idea the MSL replica's own item-2 addition ported into
    Metal's `simdgroup_load`/`dst`-seed (see this task's own prior report: "one new block before the
    K-loop that seeds each `mc[i]` via `simdgroup_load` from `dst` at the exact same address the final
    `simdgroup_store` uses"). Ported here identically: each `mc[i]` is seeded from `y` at the EXACT
    SAME `(r, c0, c1)` address its own final store (below) will later write back to -- computed via
    `_frag_row_col(tid)` ONCE, reused for both the seed and the store, bounds-checked per element the
    same way `_gemm_accum_mma8x8`'s own seed and every kernel's own final store in this file already
    are (a stale `y` read past `m_rows`/`n` would be a memory-safety issue even though its result is
    never stored back).

    ONE kernel, reused for BOTH o_proj (M=256,K=2048,N=1024) and down_proj (M=256,K=3072,N=1024),
    exactly as `_gemm_accum_mma8x8`/`_gemm_accum_mma8x8_vecload4` already are above -- this mirrors
    the real llama.cpp kernel's OWN shape-agnosticism the MSL replica task's admission gate already
    confirmed (`NR0`/`NR1`/`NK`/`nsg` are fixed `constexpr` values, not specialized per shape; the
    o_proj/down_proj MSL replicas needed TWO separate `.metal` files only because that task's harness
    keys pipeline discovery off a distinct Metal function NAME per role, not because the kernel body
    itself needed to differ -- `diff` between those two replicas' kernel bodies was 4 lines, name
    only). Mojo has no such per-role-name constraint (`ctx.enqueue_function` dispatches by Mojo
    function identity, and this file's own `_gemm_accum_mma8x8`/`_gemm_accum_mma8x8_vecload4` already
    establish "one kernel, two roles" as this file's own convention), so this kernel follows that
    SAME established convention rather than introducing two near-duplicate Mojo functions differing
    only in name.

    Correctness: PASS at a small non-tile-aligned shape and at BOTH real production shapes (o_proj,
    down_proj), against a CPU Float64 oracle whose running sum starts from the SAME nonzero `y`-seed
    the device buffer was uploaded with (`mma_forge/probes/gemm_accum_llama_parity_bench.mojo`).
    Static-gate confirmed via fresh `xcrun metal-objdump --disassemble` (`mma_forge/
    mm8_accum_llama_parity_driver.mojo`): F16 MMA operands present, exactly 8 distinct accumulator SSA
    values, matching wide loads present, zero native fragment-load instructions, 6144B shared memory
    and 2 barriers/K-step -- the SAME static signature `_qkv_proj_gemm_mma8x8_llama_parity`'s own gate
    already established, plus one extra `simdgroup`-equivalent load per fragment for the seed (the
    disclosed, task-required accumulator-seed addition, the ACCUM-role analogue of the QKV kernel's
    own zero-fill it replaces).

    Pure addition: `_qkv_proj_gemm_mma8x8_llama_parity`, `_gemm_accum_mma8x8`,
    `_gemm_accum_mma8x8_vecload4`, and every other kernel in this file are left completely untouched
    by this addition."""
    var a_tile = stack_allocation[Int(_BM_W * _BK_W), DType.float16, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[Int(_BK_W * _BN_W), DType.float16, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32
    var sg_m_half = sg // 2
    var sg_n_half = sg % 2

    var n_tile_cols = (n + _BN_W - 1) // _BN_W
    var tile_col = Int64(block_idx.x) % n_tile_cols
    var tile_row = Int64(block_idx.x) // n_tile_cols
    var block_row = tile_row * _BM_W
    var block_col = tile_col * _BN_W

    # ---- "+=" seed: each mc[i] seeded from the EXISTING y at the EXACT SAME (r,c0,c1) address its
    # own final store (below) will later write back to -- `_frag_row_col(tid)` computed ONCE here and
    # reused for the final store too, matching `_gemm_accum_mma8x8`'s own seed-then-store convention. ----
    var rc = _frag_row_col(tid)
    var r0 = block_row + sg_m_half * 16 + 0 * 8 + rc[0]
    var r1 = block_row + sg_m_half * 16 + 1 * 8 + rc[0]
    var c0_0 = block_col + sg_n_half * 32 + 0 * 8 + rc[1]
    var c0_1 = c0_0 + 1
    var c1_0 = block_col + sg_n_half * 32 + 1 * 8 + rc[1]
    var c1_1 = c1_0 + 1
    var c2_0 = block_col + sg_n_half * 32 + 2 * 8 + rc[1]
    var c2_1 = c2_0 + 1
    var c3_0 = block_col + sg_n_half * 32 + 3 * 8 + rc[1]
    var c3_1 = c3_0 + 1

    var mc0 = SIMD[DType.float32, 2](
        y[Int(r0 * n + c0_0)] if (r0 < m_rows and c0_0 < n) else Float32(0.0),
        y[Int(r0 * n + c0_1)] if (r0 < m_rows and c0_1 < n) else Float32(0.0),
    )
    var mc1 = SIMD[DType.float32, 2](
        y[Int(r0 * n + c1_0)] if (r0 < m_rows and c1_0 < n) else Float32(0.0),
        y[Int(r0 * n + c1_1)] if (r0 < m_rows and c1_1 < n) else Float32(0.0),
    )
    var mc2 = SIMD[DType.float32, 2](
        y[Int(r0 * n + c2_0)] if (r0 < m_rows and c2_0 < n) else Float32(0.0),
        y[Int(r0 * n + c2_1)] if (r0 < m_rows and c2_1 < n) else Float32(0.0),
    )
    var mc3 = SIMD[DType.float32, 2](
        y[Int(r0 * n + c3_0)] if (r0 < m_rows and c3_0 < n) else Float32(0.0),
        y[Int(r0 * n + c3_1)] if (r0 < m_rows and c3_1 < n) else Float32(0.0),
    )
    var mc4 = SIMD[DType.float32, 2](
        y[Int(r1 * n + c0_0)] if (r1 < m_rows and c0_0 < n) else Float32(0.0),
        y[Int(r1 * n + c0_1)] if (r1 < m_rows and c0_1 < n) else Float32(0.0),
    )
    var mc5 = SIMD[DType.float32, 2](
        y[Int(r1 * n + c1_0)] if (r1 < m_rows and c1_0 < n) else Float32(0.0),
        y[Int(r1 * n + c1_1)] if (r1 < m_rows and c1_1 < n) else Float32(0.0),
    )
    var mc6 = SIMD[DType.float32, 2](
        y[Int(r1 * n + c2_0)] if (r1 < m_rows and c2_0 < n) else Float32(0.0),
        y[Int(r1 * n + c2_1)] if (r1 < m_rows and c2_1 < n) else Float32(0.0),
    )
    var mc7 = SIMD[DType.float32, 2](
        y[Int(r1 * n + c3_0)] if (r1 < m_rows and c3_0 < n) else Float32(0.0),
        y[Int(r1 * n + c3_1)] if (r1 < m_rows and c3_1 < n) else Float32(0.0),
    )

    var n_steps = (k + _BK_W - 1) // _BK_W
    for step in range(n_steps):
        # ---- A-tile (activation, Float32 device -> Float16 shared): 8-wide cooperative load, one
        # chunk per thread. Byte-for-byte `_qkv_proj_gemm_mma8x8_llama_parity`'s own A-tile, `x` not
        # `xn` (this role's own activation parameter name, matching `_gemm_accum_mma8x8`'s `x`). ----
        var a_row = tid // 4
        var a_which = tid % 4
        var a_col0 = a_which * 8
        var a_idx0 = a_row * _BK_W + a_col0
        var gr_a = block_row + a_row
        var gc0_a = step * _BK_W + a_col0
        if gr_a < m_rows and gc0_a + 7 < k:
            var av = x.load[width=8](Int(gr_a * k + gc0_a))
            var av_f16 = av.cast[DType.float16]()
            a_tile.store[width=8](Int(a_idx0), av_f16)
        else:
            for c in range(8):
                var gc_a = gc0_a + Int64(c)
                a_tile[Int(a_idx0 + Int64(c))] = Float16(x[Int(gr_a * k + gc_a)]) if (gr_a < m_rows and gc_a < k) else Float16(0.0)

        # ---- B-tile (weight, ALREADY Float16 device -> Float16 shared, ZERO dequant): 16-wide
        # device read, 16 scalar transposed-scatter writes -- byte-for-byte
        # `_qkv_proj_gemm_mma8x8_llama_parity`'s own B-tile. ----
        var b_row = tid // 2
        var b_which = tid % 2
        var b_col0 = b_which * 16
        var gr_b = block_col + b_row
        var gc0_b = step * _BK_W + b_col0
        if gr_b < n and gc0_b + 15 < k:
            var wv = w_f16.load[width=16](Int(gr_b * k + gc0_b))
            for c in range(16):
                b_tile[Int((b_col0 + Int64(c)) * _BN_W + b_row)] = wv[c]
        else:
            for c in range(16):
                var gc_b = gc0_b + Int64(c)
                b_tile[Int((b_col0 + Int64(c)) * _BN_W + b_row)] = w_f16[Int(gr_b * k + gc_b)] if (gr_b < n and gc_b < k) else Float16(0.0)

        barrier()

        for ksub in range(Int(_BK_W // 8)):
            # ---- fragment loads: 2 activation ("mb", Algenta a_frag) + 4 weight ("ma", Algenta
            # b_frag) -- byte-for-byte `_qkv_proj_gemm_mma8x8_llama_parity`'s own fragment loads. ----
            var m_group0 = sg_m_half * 2
            var m_group1 = sg_m_half * 2 + 1
            var a_ptr0 = a_tile + Int(m_group0 * 8 * _BK_W + Int64(ksub) * 8)
            var a_ptr1 = a_tile + Int(m_group1 * 8 * _BK_W + Int64(ksub) * 8)
            var a_frag0 = apple_mma_load_8x8[DType.float16](a_ptr0, Int(_BK_W))
            var a_frag1 = apple_mma_load_8x8[DType.float16](a_ptr1, Int(_BK_W))

            var n_group0 = sg_n_half * 4
            var n_group1 = sg_n_half * 4 + 1
            var n_group2 = sg_n_half * 4 + 2
            var n_group3 = sg_n_half * 4 + 3
            var b_ptr0 = b_tile + Int(Int64(ksub) * 8 * _BN_W + n_group0 * 8)
            var b_ptr1 = b_tile + Int(Int64(ksub) * 8 * _BN_W + n_group1 * 8)
            var b_ptr2 = b_tile + Int(Int64(ksub) * 8 * _BN_W + n_group2 * 8)
            var b_ptr3 = b_tile + Int(Int64(ksub) * 8 * _BN_W + n_group3 * 8)
            var b_frag0 = apple_mma_load_8x8[DType.float16](b_ptr0, Int(_BN_W))
            var b_frag1 = apple_mma_load_8x8[DType.float16](b_ptr1, Int(_BN_W))
            var b_frag2 = apple_mma_load_8x8[DType.float16](b_ptr2, Int(_BN_W))
            var b_frag3 = apple_mma_load_8x8[DType.float16](b_ptr3, Int(_BN_W))

            # ---- 8 multiply-accumulates: llama.cpp's own `mc[i] = mb[i/4] @ ma[i%4]` pairing,
            # i=0..7 -- byte-for-byte `_qkv_proj_gemm_mma8x8_llama_parity`'s own compute. `mc0..mc7`
            # already hold the "+=" seed from above, not zero, so this IS the accumulate. ----
            _mma_apple_8x8(mc0, a_frag0, b_frag0, mc0)
            _mma_apple_8x8(mc1, a_frag0, b_frag1, mc1)
            _mma_apple_8x8(mc2, a_frag0, b_frag2, mc2)
            _mma_apple_8x8(mc3, a_frag0, b_frag3, mc3)
            _mma_apple_8x8(mc4, a_frag1, b_frag0, mc4)
            _mma_apple_8x8(mc5, a_frag1, b_frag1, mc5)
            _mma_apple_8x8(mc6, a_frag1, b_frag2, mc6)
            _mma_apple_8x8(mc7, a_frag1, b_frag3, mc7)

        barrier()

    # ---- final store: 8 fragments, one contiguous 16(M)x32(N) block per simdgroup, bounds-checked
    # via the SAME `rc` computed above for the seed -- this file's own established partial-tile
    # discipline, unchanged. ----
    for which in range(8):
        var a_idx = Int64(which) // 4
        var b_idx = Int64(which) % 4
        var frag = mc0
        if which == 1:
            frag = mc1
        elif which == 2:
            frag = mc2
        elif which == 3:
            frag = mc3
        elif which == 4:
            frag = mc4
        elif which == 5:
            frag = mc5
        elif which == 6:
            frag = mc6
        elif which == 7:
            frag = mc7
        var r = block_row + sg_m_half * 16 + a_idx * 8 + rc[0]
        var c0 = block_col + sg_n_half * 32 + b_idx * 8 + rc[1]
        var c1 = c0 + 1
        if r < m_rows and c0 < n:
            y[Int(r * n + c0)] = frag[0]
        if r < m_rows and c1 < n:
            y[Int(r * n + c1)] = frag[1]
