"""
residentk.kernels_cuda_graph — graph-replay twins of the three position-dependent decode
kernels, for the CUDA-native resident session's DeviceGraph arm. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/qwen3_generate_cuda.mojo
benchmark: benchmarks/llm_smoke/qwen3_bench_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Nothing here is public, the same rule `residentk.kernels` states
-------------------------------------------------------------------------------------------
Leading underscores keep these out of `apps/runtime/mojo_inventory.py`'s inventory, out of the
contract, and out of the generated dispatch; `residentk.session_cuda` (also private) is the only
module that reaches them.

Why these twins exist at all
----------------------------
`max.gpu.host.DeviceGraph` captures a launch sequence ONCE and replays it with the arguments it
was captured with. A decode step's dispatch plan is fixed per model — 1 embed + 6 dispatches per
layer + lm_head/argmax/reduce, 171 total at Qwen3-0.6B's 28 layers — but THREE of those launches
take scalars that change every token: `_embed_row_kernel` reads `token_id` (data-dependent, the
previous step's argmax), `_qk_rope_write_kernel` reads `pos` (the KV slot + RoPE offset), and
`_sdpa_kernel` reads `n_keys = pos + 1`. Re-capturing per token would cost more than the launches
it deletes, and `DeviceGraph` exposes no kernel-node parameter update.

The fix is one level of indirection, the standard graph-capture pattern: the three twins take a
`state` pointer to a 3-element resident Int64 buffer INSTEAD of the dynamic scalar, and read it
on-device:

    state[0] = token_id    (read by `_embed_row_kernel_g`)
    state[1] = pos         (read by `_qk_rope_write_kernel_g`)
    state[2] = n_keys      (read by `_sdpa_kernel_g`)

The session writes those three Int64s from the host (one pinned-buffer write + one H2D copy node
recorded at the head of the graph), then replays the ONE captured graph. Every launch now has
fixed arguments — buffer addresses resident for the session's life — so the capture serves every
decode step unchanged.

Numerics are IDENTICAL to the originals by construction
----------------------------------------------------------
Each twin is the original kernel's body with exactly one line changed — the scalar's origin. The
arithmetic the token depends on is untouched, so the graph arm's greedy continuation is the same
oracle the per-dispatch arm produces; `qwen3_generate_cuda.mojo` enforces that under the build
flag that selects the graph arm. The bodies were copied from `residentk.kernels` at the commit
this file landed, and the originals remain the shared Metal/CUDA decode path — untouched, per the
"additive twins, never mutate the shared kernel" discipline this package's precision arms follow.

Mojo 1.0.0 kernel-parameter discipline
----------------------------------------
Every scalar parameter is a fixed-width `Int64` (DevicePassable), widened back to `Int` once at
entry — `accel/launch.mojo`'s pattern, the same one `residentk.kernels`' own 1.0.0 migration uses.
"""

from std.origin import MutAnyOrigin  # Mojo 1.0.0: origins left std.builtin.type_aliases
from std.gpu import block_idx, lane_id, thread_idx, warp_id, WARP_SIZE
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.gpu.primitives.warp import sum as _warp_sum
from std.math import exp, sqrt
from std.memory import stack_allocation
from residentk.contract import RESIDENT_MAX_HEAD_DIM
from residentk.kernels import _TG, _NEG_HUGE

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — the same spelling `residentk.kernels` uses."""

alias _HP = UnsafePointer[Float16, origin=MutAnyOrigin]
"""A device Float16 buffer — the f16 session's weight-storage type."""

alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]
"""The graph-state buffer: three Int64 scalars the session rewrites before every replay."""

alias _I32P = UnsafePointer[Int32, origin=MutAnyOrigin]
"""The argmax token-id output (Int32, the resident arm's argmax dtype)."""


def _embed_row_kernel_g(hidden: _FP, embed: _FP, state: _I64P, d_model_i64: Int64):
    """The graph-replay twin of `residentk.kernels._embed_row_kernel`: `hidden = embed[state[0]]`.

    Body-identical to the original save the token id's origin — `state[0]` instead of a by-value
    `token_id_i64` — so the captured graph's arguments stay fixed while the session feeds each
    step's token through the state buffer.
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var token_id = Int(state[0])
    var d_model = Int(d_model_i64)
    var i = Int(block_idx.x) * _TG + Int(thread_idx.x)
    if i < d_model:
        hidden[i] = embed[token_id * d_model + i]


def _qk_rope_write_kernel_g(
    q_rot: _FP, ck: _FP, cv: _FP, qkv: _FP, qn_w: _FP, kn_w: _FP,
    cos_t: _FP, sin_t: _FP, state: _I64P, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    eps: Float32, qk_norm_i64: Int64,
):
    """The graph-replay twin of `residentk.kernels._qk_rope_write_kernel`: the fused per-head
    QK-norm + RoPE + in-place KV-cache slot write, reading `pos` from `state[1]`.

    Body-identical to the original save the position's origin. The position drives the RoPE
    table offset and the KV-cache slot index exactly as in the original; only where the scalar
    comes from differs.
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var pos = Int(state[1])
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var qk_norm = Int(qk_norm_i64)
    var xs = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var red = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var b = Int(block_idx.x)
    var e = Int(thread_idx.x)
    var is_q = b < h_q
    var head = b if is_q else b - h_q

    # `qkv` is the fused projection's output: [ Q | K | V ], each head-major within its section.
    var src_off = head * d_head + e if is_q else (h_q + head) * d_head + e
    var v = qkv[src_off]
    if qk_norm == 1:
        var g = qn_w[e] if is_q else kn_w[e]

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
        # Llama-family: no QK-norm -- rotate the raw projection; `qn_w`/`kn_w` are never read.
        xs[e] = v
        barrier()

    var n_pairs = d_head // 2
    if e < n_pairs:
        var c = cos_t[pos * n_pairs + e]
        var s = sin_t[pos * n_pairs + e]
        var a0 = xs[e]
        var a1 = xs[e + n_pairs]
        var o0 = a0 * c - a1 * s
        var o1 = a0 * s + a1 * c
        if is_q:
            var qb = head * d_head
            q_rot[qb + e] = o0
            q_rot[qb + e + n_pairs] = o1
        else:
            var kb = (pos * h_kv + head) * d_head
            ck[kb + e] = o0
            ck[kb + e + n_pairs] = o1

    # V is neither normalized nor rotated — it is written straight into its cache slot. All d_head
    # threads participate, which is why this is outside the `e < n_pairs` guard above.
    if not is_q:
        cv[(pos * h_kv + head) * d_head + e] = qkv[(h_q + h_kv + head) * d_head + e]


def _sdpa_kernel_g(
    attn_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    state: _I64P, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64, scale: Float32,
):
    """The graph-replay twin of `residentk.kernels._sdpa_kernel`: one-token online-softmax
    attention over `state[2]` cached keys.

    Body-identical to the original save the key count's origin. The loop bound is a uniform
    device read (every thread reads the same `state[2]`), so the original's barrier discipline
    carries over unchanged.
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var n_keys = Int(state[2])
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var red = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var h = Int(block_idx.x)
    var e = Int(thread_idx.x)
    var hk = h // (h_q // h_kv)
    var qv = q_rot[h * d_head + e]

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    for j in range(n_keys):
        var kb = (j * h_kv + hk) * d_head
        red[e] = qv * ck[kb + e]
        barrier()
        var stride = d_head // 2
        while stride > 0:
            if e < stride:
                red[e] = red[e] + red[e + stride]
            barrier()
            stride //= 2
        var s = red[0] * scale
        # Every thread has now read `red[0]`; this barrier is what makes overwriting it on the next
        # key safe. Without it a fast lane starts key j+1's dot product while a slow one is still
        # reading key j's score, and the answer comes out almost right — worse under load.
        barrier()

        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        o = o * corr + w * cv[kb + e]
        denom = denom * corr + w
        m = nm

    attn_out[h * d_head + e] = o / denom


def _sdpa_kernel_simd_g(
    attn_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    state: _I64P, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64, scale: Float32,
):
    """The graph-replay twin of `residentk.kernels._sdpa_kernel_simd` — the WARP-SHUFFLE
    reduction variant (2 barriers per key, not 9), reading `n_keys` from `state[2]`.

    Adopted on NVIDIA behind `sdpa_simd_nvidia_probe.mojo`'s gate (this tree): the minimal
    d_head=32/n_keys=1 shape that reproduces the documented Metal lane-0/1 codegen bug 100%
    shows ZERO mismatches here, and 2000-dispatch stress at the production shape (h_q=16,
    h_kv=8, d_head=128, n_keys in {257, 512}) matches the barrier-tree reference within the
    F32 bound with worst_abs_diff ~3e-7. The reduction body is byte-for-byte
    `_sdpa_kernel_simd`'s; only the key count's origin differs.
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var n_keys = Int(state[2])
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    comptime _SIMD_GROUPS: Int = RESIDENT_MAX_HEAD_DIM // WARP_SIZE
    var grp = stack_allocation[_SIMD_GROUPS, DType.float32, address_space = AddressSpace.SHARED]()
    var h = Int(block_idx.x)
    var e = Int(thread_idx.x)
    var hk = h // (h_q // h_kv)
    var qv = q_rot[h * d_head + e]
    var lane = lane_id()
    var grp_id = warp_id()
    var n_groups = d_head // WARP_SIZE

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    for j in range(n_keys):
        var kb = (j * h_kv + hk) * d_head
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

    attn_out[h * d_head + e] = o / denom


def _embed_row_kernel_f16_g(hidden: _FP, embed: _HP, state: _I64P, d_model_i64: Int64):
    """The graph-replay twin of `residentk.kernels._embed_row_kernel_f16`: `hidden =
    Float32(embed_f16[state[0]])` — the Float16-table gather for the f16 session's graph arm.
    Body-identical to the original save the token id's origin (`state[0]` instead of a
    by-value scalar), the widening at load unchanged."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var token_id = Int(state[0])
    var d_model = Int(d_model_i64)
    var i = Int(block_idx.x) * _TG + Int(thread_idx.x)
    if i < d_model:
        hidden[i] = Float32(embed[token_id * d_model + i])


def _splitk_partial_kernel_simd_g(
    m_out: _FP, l_out: _FP, o_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    state: _I64P, n_splits_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    scale: Float32,
):
    """The graph-replay twin of `residentk.kernels._splitk_partial_kernel_simd` — the split-K
    (flash-decoding) PARTIAL half, reading `n_keys` from `state[2]`.

    Why split-K inside the graph arm even at race depths: the Metal-side finding that splitting
    REGRESSES below ~500 keys was a fixed-LAUNCH-overhead argument (two dispatches instead of
    one). Inside a captured graph the launch overhead is gone — only device time counts, and the
    occupancy argument stands at every depth: `_sdpa_kernel_simd` recruits exactly `h_q` = 16
    blocks on a 108-SM A100 no matter how deep the cache grows; splitting recruits `h_q *
    n_splits` blocks over the same key range. Empty splits fold into the merge as no-ops per the
    original's docstring (finite `_NEG_HUGE`, not -inf).
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var n_keys = Int(state[2])
    var n_splits = Int(n_splits_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    comptime _SIMD_GROUPS: Int = RESIDENT_MAX_HEAD_DIM // WARP_SIZE
    var grp = stack_allocation[_SIMD_GROUPS, DType.float32, address_space = AddressSpace.SHARED]()
    var idx = Int(block_idx.x)
    var h = idx // n_splits
    var sidx = idx % n_splits
    var e = Int(thread_idx.x)
    var hk = h // (h_q // h_kv)
    var qv = q_rot[h * d_head + e]
    var lane = lane_id()
    var grp_id = warp_id()
    var n_groups = d_head // WARP_SIZE

    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    for j in range(key_start, key_end):
        var kb = (j * h_kv + hk) * d_head
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


def _graph_advance_kernel(state: _I64P, out_idx: _I32P, token_log: _I64P):
    """The device-side generation chain that lets ONE captured graph run a whole generation
    with ZERO per-token host traffic (single-thread, grid 1 / block 1).

    Runs last in the captured sequence, after `_argmax_reduce_kernel`: logs the generated
    token to `token_log[pos]`, feeds it back as the NEXT step's embed input (`state[0]`), and
    advances the position and key count (`state[1] += 1; state[2] = state[1] + 1`). Replays
    execute in stream order, so replay k consumes exactly what replay k-1 advanced — the
    host seeds `state` once before the first replay and synchronizes once after the last.

    `state` layout: [0] = token_id, [1] = pos, [2] = n_keys (the same layout the `_g` twins
    read).
    """
    if Int(thread_idx.x) == 0:
        var tok = Int64(out_idx[0])
        token_log[state[1]] = tok
        state[0] = tok
        state[1] = state[1] + 1
        state[2] = state[1] + 1
