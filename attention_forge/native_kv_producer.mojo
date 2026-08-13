"""attention_forge.native_kv_producer -- Attention Compiler Plan v1.0, Phase 2B: the head-complete
QK-norm + RoPE + F16-narrowing + native-KV-packing PRODUCER. Both Phase 2A Round 1 survivors
(`grouped_fa_q8_k32_h2_sg8.mojo` / Candidate A, `splitk_fa.mojo` / Candidate C) currently read K/V
from a device buffer in NATURAL `[position][kv_head][d_head]` layout and re-stage it into shared
memory, transposed for K, every single K-tile dispatch. This file's job is to write K/V into the
plan's own canonical native layout ONCE, at the same point `_pf_ropewrt_kernel`
(`mojo/engine/residentk/kernels.mojo:3218-3288`) already does QK-norm+RoPE+cache-append, so the
per-dispatch transpose-gather has nothing left to do (or next to nothing).

WHAT THIS FILE REUSES FROM `_pf_ropewrt_kernel`, UNCHANGED
------------------------------------------------------------
Grid/threadgroup organization, fused-QKV input contract, and the norm+RoPE math itself are the
SAME as `_pf_ropewrt_kernel` -- independently re-derived here (not copy-pasted; this file lives in
`attention_forge/`'s own forge-toolchain build, never mixed with the pinned production toolchain
that compiles `kernels.mojo`), and cross-checked against that kernel's own documented behavior by
this file's driver's CPU Float64 oracle (see `native_kv_producer_driver.mojo`):
  - `grid_dim = (h_q + h_kv) * m_rows`, `block_idx.x` flattens `(b, m)` as `n_units = h_q + h_kv`,
    `b = block_idx.x % n_units`, `m = block_idx.x // n_units`. `block_dim = d_head` (one thread per
    head-dim lane `e`) -- ONE unit is either one Q head (`b < h_q`) or one KV head (`b - h_q`,
    which owns BOTH that head's K row and V row, exactly as `_pf_ropewrt_kernel`'s own `is_q`
    branch does).
  - Full-head RMSNorm: shared-memory tree reduction of `v*v` over all `d_head` lanes,
    `inv = 1/sqrt(mean_sq + eps)`, `xs[e] = v * inv * g`, `g` read from a length-`d_head` gamma
    vector SHARED ACROSS ALL HEADS of that Q/K type (`qn_w`/`kn_w`), indexed only by `e`, never by
    head -- byte-identical formula.
  - RoPE: NeoX split-half rotation, pairs `(e, e + n_pairs)` with `n_pairs = d_head // 2` (NOT the
    interleaved `(2e, 2e+1)` convention), `cos_t[pos * n_pairs + e]` / `sin_t[pos * n_pairs + e]`
    row-major tables, `pos = pos_base + m` -- so a continuation call with a nonzero `pos_base`
    reads the correct RoPE angle for its own absolute position, exactly as the reference does.
  - Absolute-position addressing: `pos = pos_base + m` is used for EVERY cache write (K, V, and
    the block/key-in-block split below) -- the same mechanism that lets `_pf_ropewrt_kernel`
    correctly append to a `max_ctx`-sized preallocated cache across repeated `step()`/
    `prefill_batch()` calls, with no assumption that `pos_base` is block-aligned.

WHAT CHANGES, AND WHY
----------------------
1. **F16 narrowing at every output** (Q, K, V). `_pf_ropewrt_kernel` writes F32 (`q_rot`/`ck`/`cv`
   are `_FP` throughout); this producer writes `_F16P` throughout -- the dtype both Phase 2A
   candidates already read K/V as, and Q was already read plainly in F16 by every candidate with
   no gather (confirmed by direct reading of `grouped_fa_q8_k32_h2_sg8.mojo`/`splitk_fa.mojo`'s own
   Q-load loops: `sq[idx] = q_ptr[...]` straight from a `_F16P`).
2. **Q layout is UNCHANGED** (`[m_rows][h_q * d_head]` row-major) -- only the dtype narrows.
3. **K and V land in the plan's own canonical native-packed layout instead of
   `[position][kv_head][d_head]`.** Exact flat-index formulas (`hk` = kv_head index, `block` =
   `pos // key_block_size`, `kk` = `pos % key_block_size`, `d` = head-dim index, `n_blocks` =
   caller-supplied total block count the packed buffer was allocated for):

     K: `((hk * n_blocks + block) * d_head + d) * key_block_size + kk`
        layout string: `[kv_head][key_block][d_chunk][key_in_block]` (transposed)
     V: `((hk * n_blocks + block) * key_block_size + kk) * d_head + d`
        layout string: `[kv_head][key_block][key_in_block][d_chunk]` (natural)

   These are BYTE-IDENTICAL to what Candidate A/C's own per-K-tile shared-memory staging already
   builds every dispatch, at `key_block_size = 32` (matching both survivors' `K_TILE`): K's own
   `skv[idx]` staging loop computes `d = idx // _KT; kk = idx % _KT` (i.e. `skv[d*_KT+kk]`) and V's
   own staging loop computes `kk = idx // _D; d = idx % _D` (i.e. `skv[kk*_D+d]`) -- so a WHOLE
   packed block (`d_head * key_block_size` contiguous K elements, or `key_block_size * d_head`
   contiguous V elements, both starting at `(hk * n_blocks + block) * <block_size>`) is, byte for
   byte, exactly what those kernels currently gather into `skv` via a per-element index transform.
   Once K/V live in this layout in device memory, a full aligned block's worth is a single
   contiguous copy (or, per the direct-load experiment below, no copy at all).
4. **Non-block-aligned `pos_base` is handled for free.** `block`/`kk` are derived purely from the
   absolute integer `pos = pos_base + m`, never from an assumption that `pos_base` is a multiple of
   `key_block_size` -- a continuation call starting mid-block (e.g. `pos_base=17` with
   `key_block_size=32`) still lands every row at its own correct `(block, kk)` slot, and two calls
   split at an arbitrary row boundary write the IDENTICAL final buffer a single call would (verified
   by this file's driver's multi-call test).
5. **`n_blocks` is a new caller-supplied parameter** (not present in `_pf_ropewrt_kernel`, which
   only needs `max_ctx` implicitly via how large `ck`/`cv` were allocated): the native layout's own
   flat index needs to know the packed buffer's per-`kv_head` block STRIDE
   (`n_blocks * d_head * key_block_size` elements), which is a property of how the SCRATCH buffer
   was sized, not of any one dispatch -- consistent with the plan's own "scratch allocated once per
   session, reused across layers" requirement (PR 5 description).

KVLayoutDescriptor WIRING
--------------------------
This producer's chosen layout is `attention_forge.abi.KV_LAYOUT_NATIVE_PACKED_V2`
(`layout_version=2`, `key_block_order="[kv_head][key_block][d_chunk][key_in_block]"`,
`value_block_order="[kv_head][key_block][key_in_block][d_chunk]"`, `key_block_size=32`,
`dtype="f16"`) -- a real, named `KVLayoutDescriptor` instance in `abi.py`, not an unused schema.
`generate_variants.py`'s `AttentionKernelArtifactKey.kv_layout_version` is wired to
`abi.KV_LAYOUT_STUB_V1.layout_version` for its OWN Phase-0B stub (which reads no real K/V memory
and so has nothing to describe beyond the honest placeholder), with `abi.py`'s own docstring on
`KV_LAYOUT_NATIVE_PACKED_V2` pointing here as the real geometry Phase 2C's production artifact keys
should carry once a survivor's kernel is rebuilt to consume it -- see `generate_variants.py`'s
`KV_LAYOUT_VERSION` comment for the exact handoff.

THE DEVICE-DIRECT MMA-LOAD EXPERIMENT
---------------------------------------
Per this task's own background note: this session had earlier confirmed `apple_mma_load_8x8`
TYPE-CHECKS against a device (non-shared) F16 pointer, but never verified it is CORRECT at
runtime. `_native_kv_direct_load_probe_kernel` below tests exactly that, in isolation, using only
already-runtime-proven primitives for everything except the ONE thing under test: it loads an 8x8
F16 fragment directly from a device-resident native-packed K block (no shared-memory staging at
all), multiplies it by a shared-memory 8x8 IDENTITY matrix via the same `_mma_apple_8x8` every
candidate already uses, and stores the F32 result. `identity @ B == B` exactly in floating-point
arithmetic (each output element is `1.0 * B[r,c] + 0.0 * (seven other terms)`, and `1.0 * x == x`,
`0.0 * x == 0.0` exactly for any finite `x`), so this is a lossless extraction of the raw device
data through the MMA load path -- comparing the result against the KNOWN values written by the
producer proves whether the device-direct load path is correct, without needing to trust or
introduce any new store-side primitive (`apple_mma_store_8x8[DType.float32]` on a device pointer is
already proven at runtime elsewhere in this repo -- `mma_forge/mm8.mojo`'s
`_gemm_accum_mma8x8_narrow` seeds ITS OWN accumulator via `apple_mma_load_8x8[DType.float32]`
straight from a device `y` pointer and is correctness-verified in production use).

See `native_kv_producer_driver.mojo`'s own report for which outcome (device-direct load kept, or
fallback to a trivial contiguous copy) this session actually observed at runtime -- this docstring
states the experiment's DESIGN, not its result, so it never goes stale relative to what actually
ran.
"""
from std.gpu import thread_idx, block_idx
from max.gpu.sync import barrier
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.math import sqrt
from max.gpu.compute.arch.mma_apple import (
    _mma_apple_8x8,
    apple_mma_load_8x8,
    apple_mma_store_8x8,
)

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime _MAX_HEAD_DIM: Int64 = 128
"""Static shared-memory sizing bound for the RMSNorm scratch arrays -- matches
`mojo/engine/residentk/kernels.mojo`'s own `RESIDENT_MAX_HEAD_DIM` convention (this file does not
import that constant directly, since it lives in the pinned-toolchain package this forge-toolchain
file must not depend on; Qwen3-0.6B-Base's own `d_head=128` is exactly this bound, not merely under
it)."""


def _native_kv_producer_kernel(
    q_rot: _F16P, k_native: _F16P, v_native: _F16P,
    qkv: _FP, qn_w: _FP, kn_w: _FP, cos_t: _FP, sin_t: _FP,
    pos_base: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    key_block_size: Int64, n_blocks: Int64, eps: Float32, m_rows: Int64,
    qk_norm: Int64,
):
    """One threadgroup per (row, head-unit); `block_dim = d_head`. See module docstring for the
    exact grid formula, the norm+RoPE math (byte-identical to `_pf_ropewrt_kernel`), and the exact
    K/V native-packing flat-index formulas this kernel writes.

    Llama-family no-QK-norm support (feat/llama-native-deep, 2026-08-13): the TRAILING `qk_norm`
    flag is the same family-convention flag `residentk.kernels`' own ropewrt kernels carry (1 =
    Qwen3 per-head RMSNorm-then-gain before rotating; 0 = llama-family rotate-the-RAW-projection,
    no QK-norm exists in the checkpoint, `qn_w`/`kn_w` are NEVER READ). With `qk_norm == 1` the
    kernel evaluates the EXACT same formula sequence it always did (the norm block is merely
    wrapped, untouched), so a Qwen3 dispatch passing 1 stays byte-for-byte identical; with
    `qk_norm == 0` the shared-tree reduction is skipped entirely and RoPE rotates the raw
    projection -- the same skip `residentk.kernels._qk_rope_write_kernel`'s own `qk_norm` flag
    implements for the parametric path."""
    var xs = stack_allocation[Int(_MAX_HEAD_DIM), DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[Int(_MAX_HEAD_DIM), DType.float32, address_space = AddressSpace.SHARED]()

    var n_units = h_q + h_kv
    var bidx = Int64(block_idx.x)
    var b = bidx % n_units
    var m = bidx // n_units
    if m >= m_rows:
        return
    var pos = pos_base + m
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var row_qkv = m * n_qkv
    var row_q_rot = m * (h_q * d_head)

    var e = Int64(thread_idx.x)
    var is_q = b < h_q
    var head = b if is_q else b - h_q  # for K/V units, `head` IS the kv_head index `hk`

    var src_off = row_qkv + (head * d_head + e if is_q else (h_q + head) * d_head + e)
    var v = qkv[Int(src_off)]

    if qk_norm == 1:
        var g = qn_w[Int(e)] if is_q else kn_w[Int(e)]

        # Full-head RMSNorm reduction -- shared-memory tree reduction over v*v across all d_head
        # lanes, byte-identical formula to `_pf_ropewrt_kernel`.
        red[Int(e)] = v * v
        barrier()
        var stride = d_head // 2
        while stride > 0:
            if e < stride:
                red[Int(e)] = red[Int(e)] + red[Int(e + stride)]
            barrier()
            stride //= 2
        var inv = 1.0 / sqrt(red[0] / Float32(d_head) + eps)
        xs[Int(e)] = v * inv * g
        barrier()
    else:
        # Llama-family (qk_norm=0): rotate the RAW projection -- no RMSNorm, `qn_w`/`kn_w` never
        # read. Same barrier discipline as the norm arm: every lane publishes its `xs` slot before
        # the NeoX split-half exchange below reads its partner's slot.
        xs[Int(e)] = v
        barrier()

    # NeoX split-half RoPE: pairs (e, e+n_pairs), never the interleaved (2e,2e+1) convention.
    var n_pairs = d_head // 2
    if e < n_pairs:
        var c = cos_t[Int(pos * n_pairs + e)]
        var s = sin_t[Int(pos * n_pairs + e)]
        var a0 = xs[Int(e)]
        var a1 = xs[Int(e + n_pairs)]
        var o0 = a0 * c - a1 * s
        var o1 = a0 * s + a1 * c
        if is_q:
            # Q: UNCHANGED layout, [m_rows][h_q*d_head] row-major -- only the dtype narrows to F16.
            var qb = row_q_rot + head * d_head
            q_rot[Int(qb + e)] = Float16(o0)
            q_rot[Int(qb + e + n_pairs)] = Float16(o1)
        else:
            # K: native transposed packing -- see module docstring's flat-index formula.
            # `hk`=head (this unit's own kv_head), `block`=pos//key_block_size,
            # `kk`=pos%key_block_size -- derived from the ABSOLUTE position, so a non-block-aligned
            # `pos_base` (a continuation call starting mid-block) still lands at the correct slot.
            var hk = head
            var block = pos // key_block_size
            var kk = pos % key_block_size
            var block_base = (hk * n_blocks + block) * d_head
            k_native[Int((block_base + e) * key_block_size + kk)] = Float16(o0)
            k_native[Int((block_base + e + n_pairs) * key_block_size + kk)] = Float16(o1)

    if not is_q:
        # V: no RoPE, just F16-narrow-and-pack into the native NATURAL layout -- all d_head lanes
        # participate (not just e<n_pairs), matching `_pf_ropewrt_kernel`'s own unconditional V
        # write.
        var hk = head
        var block = pos // key_block_size
        var kk = pos % key_block_size
        var v_val = qkv[Int(row_qkv + (h_q + h_kv + head) * d_head + e)]
        var v_block_base = (hk * n_blocks + block) * key_block_size + kk
        v_native[Int(v_block_base * d_head + e)] = Float16(v_val)


def _native_kv_direct_load_probe_kernel(
    k_native_block: _F16P, out_extracted: _FP, d_head: Int64, key_block_size: Int64,
):
    """See module docstring's "THE DEVICE-DIRECT MMA-LOAD EXPERIMENT" section. `k_native_block`
    points directly at ONE (kv_head, block) slice of the native K buffer -- `d_head *
    key_block_size` contiguous F16 elements, laid out `[d][key_in_block]` exactly like this
    module's own K-packing formula produces for a single block. One threadgroup, `block_dim=32`
    (a single SIMD group) is enough: this kernel is a correctness probe, not a production path.
    `out_extracted` is F32, sized `d_head * key_block_size`, and receives `identity @
    k_native_block` computed entirely from device-direct MMA loads of the B operand -- if the probe
    is correct, `out_extracted[i] == Float32(k_native_block[i])` for every `i`, exactly (no
    tolerance needed; see module docstring for why this composition is lossless)."""
    var ident = stack_allocation[64, DType.float16, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var lane = tid % 32

    if lane == 0:
        for idx in range(Int64(64)):
            var row = idx // 8
            var col = idx % 8
            ident[Int(idx)] = Float16(1.0) if row == col else Float16(0.0)
    barrier()

    var n_dsteps = d_head // 8
    var n_cblocks = key_block_size // 8
    for dstep in range(n_dsteps):
        for cb in range(n_cblocks):
            var a_frag = apple_mma_load_8x8[DType.float16](ident, 8)
            # THE thing under test: `k_native_block` is a plain device pointer (no
            # `address_space = AddressSpace.SHARED` annotation, no shared-memory staging step
            # anywhere above) -- everywhere else in this repo, the B operand of an 8x8 MMA is
            # loaded from threadgroup memory.
            var b_frag = apple_mma_load_8x8[DType.float16](
                k_native_block + Int(dstep * 8 * key_block_size + cb * 8), Int(key_block_size)
            )
            var acc = SIMD[DType.float32, 2](0.0, 0.0)
            _mma_apple_8x8(acc, a_frag, b_frag, acc)
            apple_mma_store_8x8[DType.float32](
                out_extracted + Int(dstep * 8 * key_block_size + cb * 8), Int(key_block_size), acc
            )
