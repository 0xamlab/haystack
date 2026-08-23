"""residentk.kernels_prefill_attn_flash — the flash-style M-parallel PREFILL ATTENTION kernel
(the A100 autopsy's lever L1): one warp per (query row, query head), warp-shuffle score
reduction, online softmax per key, NO barrier, NO shared memory — replacing the
`_pf_attn_tiled_kernel_simd` dispatch in the serve driver's admission prefill (the autopsy's
gap #2: 252 dispatches x 1.08 ms = 271.4 ms = 47% of prefill GPU at 895 tokens, a 37.7x gap
to llama's flash-attn; the FLOP floor is 8.3 ms at the 17.6 TF f32 SIMT ceiling — pure
arithmetic, needs no tensor cores). Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo --selftest
benchmark: benchmarks/llm_smoke/nvidia_race/ttft_probe.py
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Nothing here is public, the same rule `residentk.kernels` states —
leading underscores keep these out of the inventory, the contract, and the generated
dispatch; only the CUDA serve driver (`benchmarks/llm_smoke/nvidia_race/
qwen3_serve_batched_cuda.mojo`, gated behind its own `-D` flag) reaches this kernel.

WHY THE PRE-CHANGE KERNEL IS SLOW (the measured anatomy)
---------------------------------------------------------
`_pf_attn_tiled_kernel_simd` runs ONE BLOCK of d_head threads per (row, head): every key's
128-element score dot is a FULL-BLOCK reduction — four warps' `_warp_sum` partials combined
through shared memory with TWO `barrier()` hits per key — and the block carries its online
softmax serially. At 895-1038 keys that is ~1800 barriers + ~900 shared round-trips per
(row, head) block; nsys measured the dispatches at 1.08 ms average.

THIS KERNEL'S STRUCTURE (the flash-attention arrangement, SIMT-f32 spelling)
------------------------------------------------------------------------------
* GEOMETRY: `grid_dim = ceil(m_rows / _PF_FLASH_ROWS_PER_BLOCK) * h_q`,
  `block_dim = _PF_FLASH_NTHREADS` (256 = 8 warps). Block `g` covers head `g % h_q` and the
  eight query rows `8 * (g // h_q) + warp_id()` — eight CONSECUTIVE rows of ONE head per
  block, so the block's K/V reads are nested prefixes of one kv-head's cache rows (maximal
  L1/L2 reuse). Row `m` is query position `pos_base + m`, exactly the tiled kernel's own
  absolute-position addressing.
* WARP-PER-ROW: one warp computes one whole (row, head) attention. Lane `e` owns the four
  d_head elements `[4e, 4e+4)` (d_head = 128 = 32 lanes x 4 — the caller enforces the shape;
  other head dims stay on the tiled kernel), so the Q load and every K/V row load is one
  coalesced 128-bit `load[width=4]` per lane.
* SCORE: four FMA partials per lane + ONE `_warp_sum` (hardware shuffle, no barrier, no
  shared) = the full 128-element dot. `s = warp_sum(partial) * scale` — the tiled kernel's
  own post-reduction scale.
* ONLINE SOFTMAX: the tiled kernel's recurrence VERBATIM, per key, ascending j over
  `[0, pos_base + m + 1)`: `nm = max(mx, s); corr = exp(mx - nm); w = exp(s - nm);
  o = o*corr + w*v; denom = denom*corr + w; mx = nm`. Causal by construction, the same
  "n_keys = pos + 1 is the whole mask" contract — row m never reads a key slot a later row
  writes, and reads every slot earlier passes wrote.
* The only numerical difference vs the tiled kernel is the score-reduction TREE (one warp's
  32-lane butterfly over 4-element lane partials vs four warps + shared combine) — the same
  128 products, ulp-level reordering only. The serve driver's selftest (16/16 campaign
  oracle + concurrent-vs-batch-1 token identity) is the acceptance gate.

Mojo 1.0.0 kernel-parameter discipline: every scalar parameter is a fixed-width `Int64`
(DevicePassable), widened back to `Int` once at entry — `accel/launch.mojo`'s pattern, the
same one `residentk.kernels` uses.
"""

from std.gpu import block_idx, lane_id, warp_id
from std.gpu.primitives.warp import sum as _warp_sum
from std.math import exp
from std.origin import MutAnyOrigin
from residentk.kernels import _NEG_HUGE as _PF_FLASH_NEG_HUGE

from residentk.loadvec import _ld4
alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — the SAME spelling `residentk.kernels` uses."""

comptime _PF_FLASH_ROWS_PER_WARP: Int = 4
"""Query rows ONE WARP computes, against the SAME head's K/V stream: the K/V float4 loads
are paid ONCE for all four rows (ncu put the 1-row/warp cut at 88.8% L1TEX throughput —
load-pressure-bound, not compute-bound), cutting the attention K/V wavefronts ~4x. Rows are
consecutive (`m_base + 0..3`), so causality is four staggered prefixes; each row keeps its
OWN online-softmax state, updated with the 1-row kernel's per-key recurrence verbatim —
bit-identical row math, only the load sharing changes."""

comptime _PF_FLASH_WARPS_PER_BLOCK: Int = 8

comptime _PF_FLASH_ROWS_PER_BLOCK: Int = _PF_FLASH_ROWS_PER_WARP * _PF_FLASH_WARPS_PER_BLOCK
"""Query rows one block covers: 8 warps x 4 rows of one head."""

comptime _PF_FLASH_NTHREADS: Int = _PF_FLASH_WARPS_PER_BLOCK * 32
"""Threads per block: 8 warps."""

comptime _PF_FLASH_ELEMS_PER_LANE: Int = 4
"""d_head elements one lane owns — d_head = 128 = WARP_SIZE(32) x 4. The float4 load path
(this backend's proven SIMD surface) needs exactly this; the caller dispatches the tiled
kernel for any other head dim."""


def _pf_attn_flash_kernel(
    attn_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    pos_base_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    scale: Float32, m_rows_i64: Int64,
):
    """Flash-style M-parallel prefill attention, FOUR consecutive rows per warp (one head
    per block-column): `grid_dim = ceil(m_rows / _PF_FLASH_ROWS_PER_BLOCK) * h_q`,
    `block_dim = 256`. Row math bit-identical to the one-row-per-warp form (same per-key
    online-softmax recurrence, same warp-shuffle score tree); the K/V loads are shared
    across the warp's four rows. CONTRACT: `d_head == 128`; rows `[8*(g//h_q)*4 ...]`...
    row ownership: block `g` covers head `g % h_q` and rows
    `(g // h_q) * _PF_FLASH_ROWS_PER_BLOCK + warp_id()*4 + 0..3`."""
    var pos_base = Int(pos_base_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var m_rows = Int(m_rows_i64)

    var h = Int(block_idx.x) % h_q
    var m_base = (Int(block_idx.x) // h_q) * _PF_FLASH_ROWS_PER_BLOCK \
        + Int(warp_id()) * _PF_FLASH_ROWS_PER_WARP
    if m_base >= m_rows:
        return

    var lane = Int(lane_id())
    var e0 = lane * 4
    var hk = h // (h_q // h_kv)
    var n_q = h_q * d_head

    # ── per-row state (rows beyond m_rows are inactive; row 0 is always active here) ──
    var m0 = m_base
    var m1 = m_base + 1
    var m2 = m_base + 2
    var m3 = m_base + 3
    var act1 = m1 < m_rows
    var act2 = m2 < m_rows
    var act3 = m3 < m_rows
    var nk0 = pos_base + m0 + 1
    var nk1 = pos_base + m1 + 1
    var nk2 = pos_base + m2 + 1
    var nk3 = pos_base + m3 + 1
    var nk_max = nk3 if act3 else (nk2 if act2 else (nk1 if act1 else nk0))

    var qb = m0 * n_q + h * d_head + e0
    var q04 = _ld4(q_rot, qb)
    var q00 = q04[0]
    var q01 = q04[1]
    var q02 = q04[2]
    var q03 = q04[3]
    var q10 = Float32(0.0)
    var q11 = Float32(0.0)
    var q12 = Float32(0.0)
    var q13 = Float32(0.0)
    var q20 = Float32(0.0)
    var q21 = Float32(0.0)
    var q22 = Float32(0.0)
    var q23 = Float32(0.0)
    var q30 = Float32(0.0)
    var q31 = Float32(0.0)
    var q32 = Float32(0.0)
    var q33 = Float32(0.0)
    if act1:
        var q14 = _ld4(q_rot, m1 * n_q + h * d_head + e0)
        q10 = q14[0]
        q11 = q14[1]
        q12 = q14[2]
        q13 = q14[3]
    if act2:
        var q24 = _ld4(q_rot, m2 * n_q + h * d_head + e0)
        q20 = q24[0]
        q21 = q24[1]
        q22 = q24[2]
        q23 = q24[3]
    if act3:
        var q34 = _ld4(q_rot, m3 * n_q + h * d_head + e0)
        q30 = q34[0]
        q31 = q34[1]
        q32 = q34[2]
        q33 = q34[3]

    var mx0 = _PF_FLASH_NEG_HUGE
    var mx1 = _PF_FLASH_NEG_HUGE
    var mx2 = _PF_FLASH_NEG_HUGE
    var mx3 = _PF_FLASH_NEG_HUGE
    var den0 = Float32(0.0)
    var den1 = Float32(0.0)
    var den2 = Float32(0.0)
    var den3 = Float32(0.0)
    var o00 = Float32(0.0)
    var o01 = Float32(0.0)
    var o02 = Float32(0.0)
    var o03 = Float32(0.0)
    var o10 = Float32(0.0)
    var o11 = Float32(0.0)
    var o12 = Float32(0.0)
    var o13 = Float32(0.0)
    var o20 = Float32(0.0)
    var o21 = Float32(0.0)
    var o22 = Float32(0.0)
    var o23 = Float32(0.0)
    var o30 = Float32(0.0)
    var o31 = Float32(0.0)
    var o32 = Float32(0.0)
    var o33 = Float32(0.0)

    for j in range(nk_max):
        var kb = (j * h_kv + hk) * d_head + e0
        var kv4 = _ld4(ck, kb)
        var s0 = _PF_FLASH_NEG_HUGE
        var s1 = _PF_FLASH_NEG_HUGE
        var s2 = _PF_FLASH_NEG_HUGE
        var s3 = _PF_FLASH_NEG_HUGE
        s0 = _warp_sum(q00 * kv4[0] + q01 * kv4[1] + q02 * kv4[2] + q03 * kv4[3]) * scale
        if j < nk1:
            s1 = _warp_sum(q10 * kv4[0] + q11 * kv4[1] + q12 * kv4[2] + q13 * kv4[3]) * scale
        if j < nk2:
            s2 = _warp_sum(q20 * kv4[0] + q21 * kv4[1] + q22 * kv4[2] + q23 * kv4[3]) * scale
        if j < nk3:
            s3 = _warp_sum(q30 * kv4[0] + q31 * kv4[1] + q32 * kv4[2] + q33 * kv4[3]) * scale
        var vv4 = _ld4(cv, kb)

        var nm0 = mx0 if mx0 > s0 else s0
        var corr0 = exp(mx0 - nm0)
        var w0 = exp(s0 - nm0)
        o00 = o00 * corr0 + w0 * vv4[0]
        o01 = o01 * corr0 + w0 * vv4[1]
        o02 = o02 * corr0 + w0 * vv4[2]
        o03 = o03 * corr0 + w0 * vv4[3]
        den0 = den0 * corr0 + w0
        mx0 = nm0

        if j < nk1:
            var nm1 = mx1 if mx1 > s1 else s1
            var corr1 = exp(mx1 - nm1)
            var w1 = exp(s1 - nm1)
            o10 = o10 * corr1 + w1 * vv4[0]
            o11 = o11 * corr1 + w1 * vv4[1]
            o12 = o12 * corr1 + w1 * vv4[2]
            o13 = o13 * corr1 + w1 * vv4[3]
            den1 = den1 * corr1 + w1
            mx1 = nm1
        if j < nk2:
            var nm2 = mx2 if mx2 > s2 else s2
            var corr2 = exp(mx2 - nm2)
            var w2 = exp(s2 - nm2)
            o20 = o20 * corr2 + w2 * vv4[0]
            o21 = o21 * corr2 + w2 * vv4[1]
            o22 = o22 * corr2 + w2 * vv4[2]
            o23 = o23 * corr2 + w2 * vv4[3]
            den2 = den2 * corr2 + w2
            mx2 = nm2
        if j < nk3:
            var nm3 = mx3 if mx3 > s3 else s3
            var corr3 = exp(mx3 - nm3)
            var w3 = exp(s3 - nm3)
            o30 = o30 * corr3 + w3 * vv4[0]
            o31 = o31 * corr3 + w3 * vv4[1]
            o32 = o32 * corr3 + w3 * vv4[2]
            o33 = o33 * corr3 + w3 * vv4[3]
            den3 = den3 * corr3 + w3
            mx3 = nm3

    var ob0 = m0 * n_q + h * d_head + e0
    attn_out[ob0 + 0] = o00 / den0
    attn_out[ob0 + 1] = o01 / den0
    attn_out[ob0 + 2] = o02 / den0
    attn_out[ob0 + 3] = o03 / den0
    if act1:
        var ob1 = m1 * n_q + h * d_head + e0
        attn_out[ob1 + 0] = o10 / den1
        attn_out[ob1 + 1] = o11 / den1
        attn_out[ob1 + 2] = o12 / den1
        attn_out[ob1 + 3] = o13 / den1
    if act2:
        var ob2 = m2 * n_q + h * d_head + e0
        attn_out[ob2 + 0] = o20 / den2
        attn_out[ob2 + 1] = o21 / den2
        attn_out[ob2 + 2] = o22 / den2
        attn_out[ob2 + 3] = o23 / den2
    if act3:
        var ob3 = m3 * n_q + h * d_head + e0
        attn_out[ob3 + 0] = o30 / den3
        attn_out[ob3 + 1] = o31 / den3
        attn_out[ob3 + 2] = o32 / den3
        attn_out[ob3 + 3] = o33 / den3
