"""attention_forge.native_kv_decode_attn_splitk -- beat-llama.cpp campaign (2026-08-08 night): the
SPLIT-K / flash-decoding occupancy twin of `native_kv_decode_attn._native_kv_decode_attn_kernel`,
the decode-side half of the no-mirror plan. This is the kernel the ledger's round-5 finding names
as the blocker for promoting `PF_ATTN_GROUPED_FA_NO_MIRROR`: without an occupancy fix, no-mirror
decode collapses ~2.87x below the legacy path (~100 vs ~259 tok/s at 256-token depth, measured
twice). The campaign's same-night intermediate step -- removing the naive kernel's two per-key
Int64 divisions (its own dated addendum) -- bought a real but insufficient +15-18% (115.3 vs
100.1 tok/s at N=16; 93.9 vs 79.8 at N=200; still 2.25-2.68x below legacy), which isolates the
remainder to OCCUPANCY, exactly the mechanism `_splitk_partial_kernel_simd`'s own docstring in
`mojo/engine/residentk/kernels.mojo` documents for the legacy path's deep decode: one threadgroup
per query head is a FIXED `h_q` threadgroups (= 16 here, 64 warps at d_head=128) no matter how
deep the cache grows, so the same 64 warps just iterate longer. This kernel recruits `n_splits`
times as many threadgroups per head (grid = `h_q * n_splits`) over contiguous key slices, writes
UNNORMALIZED `(m, l, o)` partials, and is merged by a per-head second dispatch -- the SAME two-
dispatch Flash-Decoding shape the legacy path already ships, translated to the native-packed F16
K/V layout.

CONTRACT, IDENTICAL TO THE LEGACY PAIR (deliberate): this kernel writes the exact same per-(head,
split) partial layout `_splitk_partial_kernel_simd` writes -- `m_out[idx]`, `l_out[idx]`,
`o_out[idx * d_head + e]` for `idx = h * n_splits + sidx`, every `e` in `[0, d_head)`, o
UNNORMALIZED -- so `residentk.kernels._splitk_merge_kernel_simd` merges its output COMPLETELY
UNCHANGED (that merge kernel only ever reads the m/l/o scratch; it cannot tell which partial
kernel produced it -- its own docstring's claim, reused verbatim). Empty splits (`n_keys <
n_splits`, later slices with `key_start == key_end`) fall out with the untouched accumulator
initial values (`m = _NEG_HUGE`, `l = 0`, `o = 0`), which the merge folds in as a genuine no-op --
the same construction, with the same finite-sentinel (not `-inf`) underflow discipline.

NATIVE-PACKED ADDRESSING: identical formulas to `native_kv_decode_attn.mojo`'s own module
docstring (K: `((hk * n_blocks + block) * d_head + e) * key_block_size + kk`; V:
`((hk * n_blocks + block) * key_block_size + kk) * d_head + e`, `block = pos // key_block_size`,
`kk = pos % key_block_size`) -- but computed INCREMENTALLY inside the key loop (block/kk advance
with wrap; the two Int64 divisions happen ONCE per threadgroup for the slice's start position,
never per key), the same division-free discipline the naive kernel's own campaign addendum
introduced, carried forward here.

SCOPE, STATED PRECISELY: this is the PARTIAL half only; the merge dispatch is the existing
`_splitk_merge_kernel_simd` (engine-side, pinned toolchain, already compiled by
`_MBQwen3I8AllSimd7Prefill.__init__`'s own unconditional split-K compile pair) -- no forge copy
of the merge exists here, because the merge reads only the layout-agnostic m/l/o scratch. Q is
read from the same `q_native` F16 row the producer writes (`[h_q*d_head]` row-major, dtype-
narrowed only), widen-immediately, same as the naive kernel.

DISCOVERY NAMING: the kernel name deliberately does NOT contain the naive kernel's discovery
substring (`native_kv_decode_attn`) as a DECISION input -- session-side discovery checks the
LONGER `native_kv_decode_attn_splitk` substring FIRST (elif the naive one), so scan order cannot
cross-wire the two pipelines (see `_MBQwen3I8AllSimd7Prefill.__init__`'s discovery loop,
campaign addendum).

INHERITED, KNOWN, NOT-NEW RISKS: (1) the two-level SIMD-shuffle reduction is copied from
`_sdpa_kernel_simd`'s own loop body (via the naive kernel) and carries that kernel's documented
rare Mojo 1.0.0b2 self-race (~1% at d_head=128, n_keys=512) -- carried forward, flagged, not
re-investigated here; (2) `d_head` must be a multiple of 32 (same inherited constraint, owned by
the session struct's constructor check).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge \
      ../attention_forge/native_kv_decode_attn_splitk_driver.mojo
"""
from std.gpu import thread_idx, block_idx
from max.gpu.sync import barrier
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.math import exp
from std.gpu.primitives.warp import sum as _warp_sum

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime _MAX_HEAD_DIM: Int64 = 128
"""Static shared-memory sizing bound -- same convention, same value, same justification as
`native_kv_decode_attn.mojo`'s own `_MAX_HEAD_DIM`."""

comptime _WARP_SIZE: Int64 = 32
"""Apple SIMD-group width, hardcoded per the forge/pinned-toolchain isolation constraint the
naive kernel's own module docstring states."""

comptime _MAX_SIMD_GROUPS: Int64 = _MAX_HEAD_DIM // _WARP_SIZE

comptime _NEG_HUGE: Float32 = -3.0e38
"""Same finite sentinel as the naive kernel and `_splitk_merge_kernel_simd` -- never IEEE `-inf`,
so empty splits' `exp(m - nm)` underflows cleanly to 0.0 at merge time."""


def _native_kv_decode_splitk_partial_kernel(
    m_out: _FP, l_out: _FP, o_out: _FP,
    q_native: _F16P, k_native: _F16P, v_native: _F16P,
    n_keys: Int64, n_splits: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    scale: Float32, key_block_size: Int64, n_blocks: Int64,
):
    """The PARTIAL half of the native-KV flash-decoding pair -- one threadgroup per (query head,
    split) (`grid_dim = h_q * n_splits`, `block_dim = d_head`), per-key math byte-for-byte the
    naive kernel's own two-level SIMD-shuffle reduction (which is itself `_sdpa_kernel_simd`'s
    loop body, translated), only the KEY RANGE (this split's contiguous slice of `[0, n_keys)`)
    and the final write (unnormalized `(m, l, o)` partials, never `o / denom`) differ -- the SAME
    split/merge contract `_splitk_partial_kernel_simd` establishes for the natural-cache path.
    See the module docstring for the addressing and empty-split disciplines."""
    var grp = stack_allocation[Int(_MAX_SIMD_GROUPS), DType.float32, address_space = AddressSpace.SHARED]()
    var idx = Int64(block_idx.x)
    var h = idx // n_splits
    var sidx = idx % n_splits
    var e = Int64(thread_idx.x)
    var group = h_q // h_kv
    var hk = h // group
    var qv = Float32(q_native[Int(h * d_head + e)])
    var lane = e % _WARP_SIZE
    var grp_id = e // _WARP_SIZE
    var n_groups = d_head // _WARP_SIZE

    # Split `sidx` of `n_splits` owns keys [key_start, key_end) -- integer-division ranges that
    # partition [0, n_keys) exactly once each, no gap, no overlap, for ANY n_keys/n_splits pair,
    # copied from `_splitk_partial_kernel_simd`'s own partition (its docstring proves the empty-
    # slice case: key_start == key_end iterates zero times). These two divisions are paid ONCE per
    # threadgroup, never per key.
    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    # Incremental native-packed addressing for the slice: (block, kk) at key_start, advanced with
    # wrap per key -- identical slot sequence to `j // key_block_size` / `j % key_block_size` at a
    # per-threadgroup one-time division cost instead of a per-key one (see module docstring).
    var block = key_start // key_block_size
    var kk = key_start % key_block_size

    var j = key_start
    while j < key_end:
        var k_idx = ((hk * n_blocks + block) * d_head + e) * key_block_size + kk
        var v_idx = ((hk * n_blocks + block) * key_block_size + kk) * d_head + e

        var partial = qv * Float32(k_native[Int(k_idx)])
        var group_total = _warp_sum(partial)
        if lane == 0:
            grp[Int(grp_id)] = group_total
        barrier()
        var s = Float32(0.0)
        for g in range(Int(n_groups)):
            s += grp[g]
        s *= scale
        # Safety barrier -- same purpose as the naive kernel's own (protect the NEXT key's shared-
        # array write against a slow thread still reading THIS key's values).
        barrier()

        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        o = o * corr + w * Float32(v_native[Int(v_idx)])
        denom = denom * corr + w
        m = nm

        kk += 1
        if kk == key_block_size:
            kk = 0
            block += 1
        j += 1

    m_out[Int(idx)] = m
    l_out[Int(idx)] = denom
    o_out[Int(idx * d_head + e)] = o


def _native_kv_decode_splitk_partial_kernel_f4(
    m_out: _FP, l_out: _FP, o_out: _FP,
    q_native: _F16P, k_native: _F16P, v_native: _F16P,
    n_keys: Int64, n_splits: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    scale: Float32, key_block_size: Int64, n_blocks: Int64,
):
    """Float4 SIMD variant of the split-K PARTIAL kernel (large-context optimization 2026-08-10).

    The one-key-per-iteration original reduces each key's dot product with a FULL 128-thread,
    two-level reduction (4 warp-sums + cross-group shared-mem sum + 2 barriers) -- at 4K-8K keys
    that reduction machinery dominates (the three-way load test's decode collapse; the KV-read
    memory ceiling at 8K is ~580 tok/s but Algenta measures 57, i.e. reduction-bound, while
    llama.cpp/MLX use a single simd_sum over SIMD dot products). This variant reorganizes:

    * `grid_dim = h_q * n_splits`, `block_dim = d_head // 4` (ONE simdgroup per (head, split)).
    * Each lane owns FOUR head-elements (`e0 = lane*4 .. e0+3`), loading K as four (strided)
      scalars and V as four CONTIGUOUS values (V is element-contiguous per key in this layout).
    * Each key's dot product is a single `simd_sum` over the 32 lanes -- NO cross-group barrier,
      NO shared scratch -- the same single-level SIMD reduction llama.cpp's decode attention uses.

    The `(m, l, o)` partial contract is IDENTICAL to the original (`m_out[idx]`, `l_out[idx]`,
    `o_out[idx*d_head + e]`, unnormalized `o`), so the existing `_splitk_merge_kernel_simd` merges
    it unchanged. Requires `d_head % 4 == 0` and dispatch with `block_dim = d_head // 4`."""
    var idx = Int64(block_idx.x)
    var h = idx // n_splits
    var sidx = idx % n_splits
    var lane = Int64(thread_idx.x)
    var e0 = lane * 4
    var group = h_q // h_kv
    var hk = h // group

    var qv0 = Float32(q_native[Int(h * d_head + e0)])
    var qv1 = Float32(q_native[Int(h * d_head + e0 + 1)])
    var qv2 = Float32(q_native[Int(h * d_head + e0 + 2)])
    var qv3 = Float32(q_native[Int(h * d_head + e0 + 3)])

    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o0 = Float32(0.0)
    var o1 = Float32(0.0)
    var o2 = Float32(0.0)
    var o3 = Float32(0.0)

    var block = key_start // key_block_size
    var kk = key_start % key_block_size

    var j = key_start
    while j < key_end:
        var k_base = (hk * n_blocks + block) * d_head * key_block_size + kk
        var partial = qv0 * Float32(k_native[Int(k_base + e0 * key_block_size)]) \
            + qv1 * Float32(k_native[Int(k_base + (e0 + 1) * key_block_size)]) \
            + qv2 * Float32(k_native[Int(k_base + (e0 + 2) * key_block_size)]) \
            + qv3 * Float32(k_native[Int(k_base + (e0 + 3) * key_block_size)])
        var s = _warp_sum(partial) * scale

        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)

        var v_base = ((hk * n_blocks + block) * key_block_size + kk) * d_head + e0
        o0 = o0 * corr + w * Float32(v_native[Int(v_base)])
        o1 = o1 * corr + w * Float32(v_native[Int(v_base + 1)])
        o2 = o2 * corr + w * Float32(v_native[Int(v_base + 2)])
        o3 = o3 * corr + w * Float32(v_native[Int(v_base + 3)])
        denom = denom * corr + w
        m = nm

        kk += 1
        if kk == key_block_size:
            kk = 0
            block += 1
        j += 1

    if lane == 0:
        m_out[Int(idx)] = m
        l_out[Int(idx)] = denom
    o_out[Int(idx * d_head + e0)] = o0
    o_out[Int(idx * d_head + e0 + 1)] = o1
    o_out[Int(idx * d_head + e0 + 2)] = o2
    o_out[Int(idx * d_head + e0 + 3)] = o3
