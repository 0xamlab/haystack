"""
residentk.kernels_batched_cuda_graph — W2 of the campaign gap inventory: graph-replay twins of
the THREE position-dependent kernels of the W1 batched (B-sequence) decode step chain, plus the
device-side generation-chain kernel that lets ONE captured graph run a whole multi-step batched
decode with zero per-step host dispatch. Additive — the W1 kernels this twins
(`residentk.kernels_prefill_f32._pf_embed_rows_kernel`, `kvprod_batched_f32_cuda.
_native_kv_producer_batched_f32_kernel`, `native_kv_decode_attn_splitk_batched_f32.
_native_kv_decode_splitk_partial_batched_f32_kernel`) are byte-unmodified, exactly the
"additive twins, never mutate the shared kernel" discipline `residentk.kernels_cuda_graph`
established for the single-stream graph arm. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/qwen3_batched_graph_cuda.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/qwen3_batched_graph_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Nothing here is public, the same rule `residentk.kernels` states —
leading underscores keep these out of `apps/runtime/mojo_inventory.py`'s inventory, out of the
contract, and out of the generated dispatch; `residentk.session_cuda_batched_graph` (also
private) is the only module that reaches them.

Why these twins exist at all
----------------------------
`max.gpu.host.DeviceGraph` captures a launch sequence ONCE and replays it with the arguments it
was captured with. The W1 batched step chain's dispatch plan is fixed per (model, B) — 1 embed
+ 9 dispatches per layer + lm_head/reduce/advance, 258 total at Qwen3-0.6B's 28 layers and any
B — but THREE of those launches take scalars that change every step, one per sequence: the
embed-rows gather reads the B next token ids, the batched KV producer reads the B positions
`poss[b]` (KV slot + RoPE offset), and the batched split-K partial reads the B key counts
`nkeys[b]`. Re-capturing per step would cost more than the launches it deletes, and `DeviceGraph`
exposes no kernel-node parameter update.

The fix is the SAME one-level-of-indirection pattern `residentk.kernels_cuda_graph` proved for
the single-stream arm, widened to B sequences: the three twins take a `state` pointer to a
resident Int64 buffer INSTEAD of the per-sequence scalar arrays, and read it on-device. The
STATE buffer layout (all Int64, one region per captured batch size B):

    state[0 .. B)      next token ids   (read by `_pf_embed_rows_kernel_bg`)
    state[B .. 2B)     poss             (read by `_native_kv_producer_batched_f32_kernel_bg`)
    state[2B .. 3B)    nkeys            (read by `_native_kv_decode_splitk_partial_batched_f32_kernel_bg`)
    state[3B]          replay-step counter (read/written by `_graph_advance_batched_kernel`)

The session seeds the region with ONE eager pinned-buffer H2D before the replay batch (a
RECORDED H2D copy reads a capture-time snapshot, never the live contents — the lesson
`residentk.session_cuda._build_decode_graph` paid for on the A100), then replays N times.

Numerics are IDENTICAL to the W1 per-dispatch arm by construction
------------------------------------------------------------------
Each twin is the W1 kernel's body with exactly one line changed — the scalar's origin. The
arithmetic every sequence's tokens depend on is untouched, so the graph arm's greedy
continuation is the same oracle the per-dispatch arm produces;
`qwen3_batched_graph_cuda.mojo` enforces that token-for-token (G1) for B in {1, 8, 32} at
128 steps. The bodies were copied from the W1 modules at the commit this file landed, and the
originals remain the shared W1 per-dispatch path — untouched.

DEVIATION FROM THE ORIGINAL SIGNATURES (documented per the W2 design brief): each twin takes
the STATE pointer plus ONE extra fixed-width `B_i64` parameter the originals do not have — the
STATE region's section offsets (`B`, `2B`) are B-dependent, and B is a capture-time constant of
the graph that enqueues the twin, so it is a fixed kernel argument at replay, exactly like the
grid dimensions.

Mojo 1.0.0 kernel-parameter discipline
----------------------------------------
Every scalar parameter is a fixed-width `Int64` (DevicePassable), widened back to `Int` once at
entry — `accel/launch.mojo`'s pattern, the same one the W1 kernels' own 1.0.0 bodies use.
"""

from std.origin import MutAnyOrigin  # Mojo 1.0.0: origins left std.builtin.type_aliases
from std.gpu import block_idx, lane_id, thread_idx, warp_id, WARP_SIZE
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.gpu.primitives.warp import sum as _warp_sum
from std.math import exp, sqrt
from std.memory import stack_allocation
from residentk.kernels import _TG

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — the same spelling the W1 kernels use."""

alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]
"""The graph-state buffer: the 3*B+1 resident Int64 scalars the session seeds before each
replay batch and `_graph_advance_batched_kernel` advances after every replay."""

alias _I32P = UnsafePointer[Int32, origin=MutAnyOrigin]
"""The argmax token-id output (Int32, the resident arm's argmax dtype)."""

comptime _MAX_HEAD_DIM: Int = 128
"""Shared-mem sizing ceiling — the same constant the two forge modules this file twins define
for themselves."""

comptime _NEG_HUGE: Float32 = -3.0e38
"""Finite softmax-initial maximum — the batched f32 split-K pair's own sentinel, so an empty
split's `exp(_NEG_HUGE - nm)` underflows to a clean 0.0 instead of `inf - inf`."""


def _pf_embed_rows_kernel_bg(
    hidden: _FP, embed: _FP, state: _I64P, d_model_i64: Int64, m_rows_i64: Int64
):
    """The graph-replay twin of `residentk.kernels_prefill_f32._pf_embed_rows_kernel`: gathers
    `m_rows = B` embedding rows, reading sequence b's token id from `state[b]` INSTEAD of an
    Int32 token-id buffer. Body-identical to the original save the token id's origin and its
    Int64 widening; same `grid_dim = ceil_div(d_model, _TG) * B` flattening
    (`unit = block_idx.x % n_units`, `m = block_idx.x // n_units`)."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives.
    var d_model = Int(d_model_i64)
    var m_rows = Int(m_rows_i64)
    var n_units = (d_model + _TG - 1) // _TG
    var unit = Int(block_idx.x) % n_units
    var m = Int(block_idx.x) // n_units
    if m >= m_rows:
        return
    var i = unit * _TG + Int(thread_idx.x)
    if i < d_model:
        var token_id = Int(state[m])
        hidden[m * d_model + i] = embed[token_id * d_model + i]


def _native_kv_producer_batched_f32_kernel_bg(
    q_rot: _FP, k_cache: _FP, v_cache: _FP,
    qkv: _FP, qn_w: _FP, kn_w: _FP, cos_t: _FP, sin_t: _FP,
    state: _I64P, B_i64: Int64, kv_stride_i64: Int64,
    h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    eps: Float32, qk_norm_i64: Int64,
):
    """The graph-replay twin of `kvprod_batched_f32_cuda._native_kv_producer_batched_f32_kernel`:
    QK-norm + RoPE + flat-f32 KV pack for all B sequences, reading sequence `seq`'s position
    from `state[B + seq]` INSTEAD of the `poss` Int64 array. Body-identical to the original
    save the position's origin — the RoPE angle and the cache slot derive from it exactly as in
    the original; the layout contract (grid `(h_q+h_kv)*B`, one row per sequence, flat
    `kv_off = seq * kv_stride` selection) is unchanged."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives.
    var B = Int(B_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var kv_stride = Int(kv_stride_i64)
    var qk_norm = Int(qk_norm_i64)

    var xs = stack_allocation[_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED]()

    var n_units = h_q + h_kv
    var seq = Int(block_idx.x) // n_units
    var unit = Int(block_idx.x) % n_units
    var pos = Int(state[B + seq])
    var kv_off = seq * kv_stride
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var row_qkv = seq * n_qkv
    var row_q_rot = seq * (h_q * d_head)

    var e = Int(thread_idx.x)
    var is_q = unit < h_q
    var head = unit if is_q else unit - h_q  # for K/V units, `head` IS the kv-head index `hk`

    var src_off = row_qkv + (head * d_head + e if is_q else (h_q + head) * d_head + e)
    var v = qkv[src_off]

    if qk_norm == 1:
        var g = qn_w[e] if is_q else kn_w[e]

        # Full-head RMSNorm reduction — shared-memory tree reduction over v*v across all d_head
        # lanes, byte-identical formula to the W1 producer.
        red[e] = v * v
        barrier()
        var stride = d_head // 2
        while stride > 0:
            if e < stride:
                red[e] = red[e] + red[e + stride]
            barrier()
            stride //= 2
        var inv = 1.0 / sqrt(red[0] / Float32(d_head) + eps)
        xs[e] = v * inv * g
        barrier()
    else:
        # No QK-norm: rotate the RAW projection; `qn_w`/`kn_w` never read. Same barrier
        # discipline as the norm arm.
        xs[e] = v
        barrier()

    # NeoX split-half RoPE: pairs (e, e+n_pairs), never the interleaved (2e,2e+1) convention.
    var n_pairs = d_head // 2
    if e < n_pairs:
        var c = cos_t[pos * n_pairs + e]
        var s = sin_t[pos * n_pairs + e]
        var a0 = xs[e]
        var a1 = xs[e + n_pairs]
        var o0 = a0 * c - a1 * s
        var o1 = a0 * s + a1 * c
        if is_q:
            var qb = row_q_rot + head * d_head
            q_rot[qb + e] = o0
            q_rot[qb + e + n_pairs] = o1
        else:
            # Flat CUDA KV layout: position-major within the kv-head, offset by the sequence slot.
            var kb = kv_off + (pos * h_kv + head) * d_head
            k_cache[kb + e] = o0
            k_cache[kb + e + n_pairs] = o1

    # V is neither normalized nor rotated — straight into its cache slot. All d_head threads
    # participate, which is why this is outside the `e < n_pairs` guard above.
    if not is_q:
        v_cache[kv_off + (pos * h_kv + head) * d_head + e] = qkv[
            row_qkv + (h_q + h_kv + head) * d_head + e
        ]


def _native_kv_decode_splitk_partial_batched_f32_kernel_bg(
    m_out: _FP, l_out: _FP, o_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    state: _I64P, B_i64: Int64, kv_stride_i64: Int64,
    n_splits_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    scale: Float32,
):
    """The graph-replay twin of
    `native_kv_decode_attn_splitk_batched_f32._native_kv_decode_splitk_partial_batched_f32_kernel`:
    the batched flash-decoding PARTIAL half, reading sequence b's key count from
    `state[2*B + b]` INSTEAD of the `nkeys` Int64 array. Body-identical to the original save
    the key count's origin — the loop bound is a uniform device read inside each threadgroup
    (every thread of the group reads the same `state[2*B+b]`), so the original's barrier
    discipline carries over unchanged. The layout contract (globally-flattened
    `idx = b*(h_q*n_splits) + h*n_splits + sidx = block_idx.x`, unnormalized `(m, l, o)`
    partials, empty splits folding into the merge as no-ops) is unchanged."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives.
    var B = Int(B_i64)
    var n_splits = Int(n_splits_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var kv_stride = Int(kv_stride_i64)
    comptime _SIMD_GROUPS: Int = _MAX_HEAD_DIM // WARP_SIZE
    var grp = stack_allocation[_SIMD_GROUPS, DType.float32, address_space = AddressSpace.SHARED]()

    var idx = Int(block_idx.x)
    var per_seq = h_q * n_splits
    var b = idx // per_seq
    var rem = idx % per_seq
    var h = rem // n_splits
    var sidx = rem % n_splits
    var e = Int(thread_idx.x)
    var hk = h // (h_q // h_kv)

    var n_keys = Int(state[2 * B + b])
    var kv_off = b * kv_stride
    var qv = q_rot[(b * h_q + h) * d_head + e]
    var lane = lane_id()
    var grp_id = warp_id()
    var n_groups = d_head // WARP_SIZE

    # Split `sidx` of `n_splits` owns keys [key_start, key_end) of THIS sequence's `n_keys`.
    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    for j in range(key_start, key_end):
        var kb = kv_off + (j * h_kv + hk) * d_head
        var partial = qv * ck[kb + e]
        var group_total = _warp_sum(partial)
        if lane == 0:
            grp[grp_id] = group_total
        barrier()
        var s = Float32(0.0)
        for g in range(n_groups):
            s += grp[g]
        s *= scale
        barrier()

        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        o = o * corr + w * cv[kb + e]
        denom = denom * corr + w
        m = nm

    m_out[idx] = m
    l_out[idx] = denom
    o_out[idx * d_head + e] = o


def _graph_advance_batched_kernel(state: _I64P, out_idx: _I32P, token_log: _I64P, B_i64: Int64):
    """The device-side generation chain that lets ONE captured batched graph run a whole
    multi-step decode with ZERO per-step host traffic — the B-sequence analogue of
    `residentk.kernels_cuda_graph._graph_advance_kernel` (grid 1 / block B, one thread per
    sequence).

    Runs LAST in the captured sequence, after `_batched_argmax_reduce_kernel_simd` wrote the B
    next tokens to `out_idx[b]`: logs each sequence's token to `token_log[step * B + b]`
    (`step` = the region's replay counter `state[3B]`, the ONE documented deviation from the
    3*B STATE layout — the counter needs no per-sequence seed because every replay advances it
    from 0), feeds it back as that sequence's NEXT embed input (`state[b]`), and advances the
    per-sequence position and key count (`state[B+b] += 1; state[2B+b] += 1`, preserving the
    seed invariant `nkeys = poss + 1`). The barrier holds every thread's counter read ahead of
    thread 0's increment; replays execute in stream order, so replay k consumes exactly what
    replay k-1 advanced — the host seeds the region once before the first replay and
    synchronizes once after the last.
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives.
    var B = Int(B_i64)
    var b = Int(thread_idx.x)
    if b < B:
        var tok = Int64(out_idx[b])
        var step = Int(state[3 * B])
        token_log[step * B + b] = tok
        state[b] = tok
        state[B + b] = state[B + b] + 1
        state[2 * B + b] = state[2 * B + b] + 1
    barrier()
    if b == 0:
        state[3 * B] = state[3 * B] + 1
