"""residentk.kernels_decode_attn_flash — the flash-style rewrite of the BATCHED split-K decode
attention PARTIAL half (the A100 autopsy's follow-up finding on the serve lane): one WARP per
(sequence, query head, split) with a warp-shuffle score reduction and float4 K/V loads, zero
barriers — replacing `_native_kv_decode_splitk_partial_batched_f32_kernel` / its `_bg` graph
twin, whose per-key cost is a FULL-BLOCK reduction (four warps' partials through shared memory,
TWO `barrier()` hits per key). nsys on the serve driver measured that kernel at 187.6 µs
average x 28 layers = 5.25 ms of every 19.5 ms C=8 decode step — the single largest decode-step
cost left after levers L2/L1/L4 landed, and the f32 control arm pays the SAME 180.7 µs (the
autopsy's alg_C row for this kernel: 198.36 µs — it was a hidden gap inside the "attention-
decode" category). Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo --selftest
benchmark: benchmarks/llm_smoke/nvidia_race/enterprise_bench.py
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Nothing here is public, the same rule `residentk.kernels` states —
leading underscores keep these out of the inventory, the contract, and the generated
dispatch; only `residentk.session_cuda_batched_p3_graph` reaches them, gated behind
`CUDA_SESSION_BUILD`.

CONTRACT — byte-compatible with the kernels it replaces
--------------------------------------------------------
* PARTIAL layout UNCHANGED: unit index `idx = b*(h_q*n_splits) + h*n_splits + sidx`
  (globally flattened, one unit per (sequence, head, split)); `m_out[idx]` / `l_out[idx]` /
  `o_out[idx*d_head ..]` hold the UNNORMALIZED online-softmax partials; empty splits write
  the same finite `_NEG_HUGE`/0 sentinel and fold into the unchanged merge kernel as genuine
  no-ops. The merge half (`_native_kv_decode_splitk_merge_batched_f32_kernel`) is reused
  byte-unmodified.
* Split `sidx` of `n_splits` owns keys `[n_keys*sidx//n_splits, n_keys*(sidx+1)//n_splits)` —
  the single-stream partition, per sequence, exact once-each coverage.
* PER-SEQUENCE STATE: the eager twin reads `nkeys[b]` (Int64 array); the `_bg` twin reads
  `state[2*B + b]` — each the same origin its replaced kernel read. KV is selected by the
  scalar element offset `b * kv_stride` (flat f32 `[max_ctx, h_kv, d_head]` slots), Q row by
  pure index arithmetic — no indirection beyond the one uniform per-unit scalar read.
* PER-KEY MATH: the original's online-softmax recurrence verbatim (per-key rescale, ascending
  keys); the ONLY numerical difference is the score dot's reduction tree (one warp's 32-lane
  butterfly over 4-element lane partials vs four warps + shared combine) — the same 128
  products, ulp-level reordering. `d_head == 128` = WARP_SIZE x 4 is the shape contract
  (caller-enforced; Qwen3's shape), same `_NEG_HUGE` sentinel.

GEOMETRY: `grid_dim = ceil(B*h_q*n_splits / _DECODE_FLASH_WARPS_PER_BLOCK)`,
`block_dim = _DECODE_FLASH_NTHREADS` (256 = 8 warps); unit `u = block_idx.x*8 + warp_id()`,
lane owns elements `[4*lane, 4*lane+4)` — the same coalesced-float4 lane ownership the
prefill flash kernel (`residentk.kernels_prefill_attn_flash`) establishes. At C=8 that is 256
blocks of 8 units — versus the replaced 2048 blocks of 128 threads, with the per-key barrier
tree deleted entirely.

BLOCK-8 ONLINE SOFTMAX (the latency lever, measured not assumed): the first cut rescaled the
running `(mx, denom, o)` state PER KEY — a serial dependency chain one key long per warp
(score needs the K load; the rescale needs the score; the V-accum needs the rescale), which
ncu/measurement put at ~94 µs per B=8 dispatch despite tiny FLOPs (load-latency-bound, ~13
serial epochs of L2 latency per split). The fix is the standard flash-attention block
recurrence — the SAME algebra `residentk.kernels._pf_attn8_kernel_simd` host-verified
(`benchmarks/llm_smoke/attn_block_update_probe.mojo`): score a BLOCK of up to 8 keys first
(8 independent K loads + dots), ONE rescale for the block max, then the block's V-accum —
cutting the serial chain ~8x. The per-key form stays as written there for the A record; this
file's kernels are the block-8 form.

Mojo 1.0.0 kernel-parameter discipline: every scalar parameter is a fixed-width `Int64`
(DevicePassable), widened back to `Int` once at entry — `accel/launch.mojo`'s pattern.
"""

from std.gpu import block_idx, lane_id, thread_idx, warp_id
from std.gpu.primitives.warp import sum as _warp_sum
from std.math import exp
from std.origin import MutAnyOrigin

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]

comptime _DECODE_FLASH_NTHREADS: Int = 256
"""Threads per block: 8 warps, one (sequence, head, split) unit per warp."""

comptime _DECODE_FLASH_WARPS_PER_BLOCK: Int = _DECODE_FLASH_NTHREADS // 32

comptime _DECODE_FLASH_NEG_HUGE: Float32 = -3.0e38
"""The replaced kernels' own finite softmax-initial sentinel, kept bit-for-bit so an empty
split folds into the unchanged merge exactly the way it always did."""


def _splitk_partial_batched_flash_kernel(
    m_out: _FP, l_out: _FP, o_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    nkeys: _I64P, B_i64: Int64, kv_stride_i64: Int64,
    n_splits_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    scale: Float32,
):
    """Eager (per-dispatch) flash-style batched split-K PARTIAL: drop-in for the forge's
    `_native_kv_decode_splitk_partial_batched_f32_kernel` — same buffers, same partial
    layout, `nkeys[b]` per-sequence key counts (plus `B` for the warp-unit grid guard).
    CONTRACT: `d_head == 128`."""
    var B = Int(B_i64)
    var n_splits = Int(n_splits_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var kv_stride = Int(kv_stride_i64)

    var per_seq = h_q * n_splits
    var u = Int(block_idx.x) * _DECODE_FLASH_WARPS_PER_BLOCK + Int(warp_id())
    if u >= B * per_seq:
        return
    var b = u // per_seq
    var rem = u % per_seq
    var h = rem // n_splits
    var sidx = rem % n_splits

    var lane = Int(lane_id())
    var e0 = lane * 4
    var hk = h // (h_q // h_kv)

    var n_keys = Int(nkeys[b])
    var kv_off = b * kv_stride

    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var qv = q_rot.load[width=4]((b * h_q + h) * d_head + e0)
    var q0 = qv[0]
    var q1 = qv[1]
    var q2 = qv[2]
    var q3 = qv[3]

    var mx = _DECODE_FLASH_NEG_HUGE
    var denom = Float32(0.0)
    var o0 = Float32(0.0)
    var o1 = Float32(0.0)
    var o2 = Float32(0.0)
    var o3 = Float32(0.0)

    # ── block-8 online softmax: 8 independent scores, ONE rescale, then the block's V-accum
    var j0 = key_start
    while j0 < key_end:
        var nb = key_end - j0
        if nb > 8:
            nb = 8

        var bs0 = _DECODE_FLASH_NEG_HUGE
        var bs1 = _DECODE_FLASH_NEG_HUGE
        var bs2 = _DECODE_FLASH_NEG_HUGE
        var bs3 = _DECODE_FLASH_NEG_HUGE
        var bs4 = _DECODE_FLASH_NEG_HUGE
        var bs5 = _DECODE_FLASH_NEG_HUGE
        var bs6 = _DECODE_FLASH_NEG_HUGE
        var bs7 = _DECODE_FLASH_NEG_HUGE
        if nb >= 1:
            var kb = kv_off + (j0 * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs0 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 2:
            var kb = kv_off + ((j0 + 1) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs1 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 3:
            var kb = kv_off + ((j0 + 2) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs2 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 4:
            var kb = kv_off + ((j0 + 3) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs3 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 5:
            var kb = kv_off + ((j0 + 4) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs4 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 6:
            var kb = kv_off + ((j0 + 5) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs5 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 7:
            var kb = kv_off + ((j0 + 6) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs6 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 8:
            var kb = kv_off + ((j0 + 7) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs7 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale

        # ONE rescale for the whole block
        var bmax = bs0
        if bs1 > bmax:
            bmax = bs1
        if bs2 > bmax:
            bmax = bs2
        if bs3 > bmax:
            bmax = bs3
        if bs4 > bmax:
            bmax = bs4
        if bs5 > bmax:
            bmax = bs5
        if bs6 > bmax:
            bmax = bs6
        if bs7 > bmax:
            bmax = bs7
        var nm = mx if mx > bmax else bmax
        var corr = exp(mx - nm)
        o0 = o0 * corr
        o1 = o1 * corr
        o2 = o2 * corr
        o3 = o3 * corr
        denom = denom * corr
        mx = nm

        if nb >= 1:
            var w = exp(bs0 - nm)
            var vv4 = cv.load[width=4](kv_off + (j0 * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 2:
            var w = exp(bs1 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 1) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 3:
            var w = exp(bs2 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 2) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 4:
            var w = exp(bs3 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 3) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 5:
            var w = exp(bs4 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 4) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 6:
            var w = exp(bs5 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 5) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 7:
            var w = exp(bs6 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 6) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 8:
            var w = exp(bs7 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 7) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w

        j0 += 8

    var idx = u
    if lane == 0:
        m_out[idx] = mx
        l_out[idx] = denom
    var ob = idx * d_head + e0
    o_out[ob + 0] = o0
    o_out[ob + 1] = o1
    o_out[ob + 2] = o2
    o_out[ob + 3] = o3


def _splitk_partial_batched_flash_kernel_bg(
    m_out: _FP, l_out: _FP, o_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    state: _I64P, B_i64: Int64, kv_stride_i64: Int64,
    n_splits_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    scale: Float32,
):
    """Graph-replay flash-style twin: reads sequence b's key count from `state[2*B + b]`
    INSTEAD of the `nkeys` array — the `_bg` origin swap of the kernel it replaces, nothing
    else. Same buffers, same partial layout, same `d_head == 128` contract."""
    var B = Int(B_i64)
    var n_splits = Int(n_splits_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var kv_stride = Int(kv_stride_i64)

    var per_seq = h_q * n_splits
    var u = Int(block_idx.x) * _DECODE_FLASH_WARPS_PER_BLOCK + Int(warp_id())
    if u >= B * per_seq:
        return
    var b = u // per_seq
    var rem = u % per_seq
    var h = rem // n_splits
    var sidx = rem % n_splits

    var lane = Int(lane_id())
    var e0 = lane * 4
    var hk = h // (h_q // h_kv)

    var n_keys = Int(state[2 * B + b])
    var kv_off = b * kv_stride

    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var qv = q_rot.load[width=4]((b * h_q + h) * d_head + e0)
    var q0 = qv[0]
    var q1 = qv[1]
    var q2 = qv[2]
    var q3 = qv[3]

    var mx = _DECODE_FLASH_NEG_HUGE
    var denom = Float32(0.0)
    var o0 = Float32(0.0)
    var o1 = Float32(0.0)
    var o2 = Float32(0.0)
    var o3 = Float32(0.0)

    # ── block-8 online softmax — the eager twin's loop verbatim (state-origin swap only) ──
    var j0 = key_start
    while j0 < key_end:
        var nb = key_end - j0
        if nb > 8:
            nb = 8

        var bs0 = _DECODE_FLASH_NEG_HUGE
        var bs1 = _DECODE_FLASH_NEG_HUGE
        var bs2 = _DECODE_FLASH_NEG_HUGE
        var bs3 = _DECODE_FLASH_NEG_HUGE
        var bs4 = _DECODE_FLASH_NEG_HUGE
        var bs5 = _DECODE_FLASH_NEG_HUGE
        var bs6 = _DECODE_FLASH_NEG_HUGE
        var bs7 = _DECODE_FLASH_NEG_HUGE
        if nb >= 1:
            var kb = kv_off + (j0 * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs0 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 2:
            var kb = kv_off + ((j0 + 1) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs1 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 3:
            var kb = kv_off + ((j0 + 2) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs2 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 4:
            var kb = kv_off + ((j0 + 3) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs3 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 5:
            var kb = kv_off + ((j0 + 4) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs4 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 6:
            var kb = kv_off + ((j0 + 5) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs5 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 7:
            var kb = kv_off + ((j0 + 6) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs6 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 8:
            var kb = kv_off + ((j0 + 7) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4](kb)
            bs7 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale

        var bmax = bs0
        if bs1 > bmax:
            bmax = bs1
        if bs2 > bmax:
            bmax = bs2
        if bs3 > bmax:
            bmax = bs3
        if bs4 > bmax:
            bmax = bs4
        if bs5 > bmax:
            bmax = bs5
        if bs6 > bmax:
            bmax = bs6
        if bs7 > bmax:
            bmax = bs7
        var nm = mx if mx > bmax else bmax
        var corr = exp(mx - nm)
        o0 = o0 * corr
        o1 = o1 * corr
        o2 = o2 * corr
        o3 = o3 * corr
        denom = denom * corr
        mx = nm

        if nb >= 1:
            var w = exp(bs0 - nm)
            var vv4 = cv.load[width=4](kv_off + (j0 * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 2:
            var w = exp(bs1 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 1) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 3:
            var w = exp(bs2 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 2) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 4:
            var w = exp(bs3 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 3) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 5:
            var w = exp(bs4 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 4) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 6:
            var w = exp(bs5 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 5) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 7:
            var w = exp(bs6 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 6) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 8:
            var w = exp(bs7 - nm)
            var vv4 = cv.load[width=4](kv_off + ((j0 + 7) * h_kv + hk) * d_head + e0)
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w

        j0 += 8

    var idx = u
    if lane == 0:
        m_out[idx] = mx
        l_out[idx] = denom
    var ob = idx * d_head + e0
    o_out[ob + 0] = o0
    o_out[ob + 1] = o1
    o_out[ob + 2] = o2
    o_out[ob + 3] = o3
