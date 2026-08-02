"""
residentk.kernels — the fused Metal kernels one resident decode token is made of. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32, float16
backend: metal
surfaces: none
golden_vectors: mojo/tests/libs/test_residentk_session.mojo
benchmark: benchmarks/llm_smoke/qwen3_generate_metal.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Nothing here is public, and that is load-bearing
--------------------------------------------------------------------------
Exactly the rule `accel/launch.mojo` states and `tests/test_accel_gpu_isolation.py` enforces: shader
codegen follows the statically REACHABLE call graph at COMPILE time, and the generated runtime
dispatch imports and calls every PUBLIC function of every contract module. A public name in this
file would put a GPU launch in the dispatch's call graph and every build host — including Linux CI,
which has neither a Metal compiler nor a GPU — would start requiring one. Leading underscores keep
these out of `apps/runtime/mojo_inventory.py`'s inventory, out of the contract, and out of the
dispatch.

`surfaces: none` above is therefore a declaration, not a placeholder. `stateful: true` because these
kernels read and WRITE a KV cache that outlives the call. `backend: metal` rather than `mojo`
because what runs is a compiled shader.

What is fused into what, and why each boundary is real
---------------------------------------------------------
`ctx.enqueue_function` BLOCKS until completion on this backend (measured: a 20 ms kernel returns
from the "enqueue" in 20.392 ms), so a token costs the sum of ~180 us of host submission plus kernel
time, per dispatch, with no overlap. At Qwen3-0.6B's 2.38 GB of Float32 weights the arithmetic floor
is ~5.8 ms/token at this host's measured 411 GB/s; the dispatch count is what actually sets
throughput. Six dispatches per layer is the floor Metal's lack of a grid-wide barrier imposes, and
this file is the fusion that reaches it:

| kernel | fuses |
|---|---|
| `_norm_gemv_kernel` | input rmsnorm + Q, K and V projections as ONE `[h_q + 2*h_kv]*d_head` matrix |
| `_qk_rope_write_kernel` | q_norm + k_norm + RoPE on both + the KV-cache slot write, IN PLACE |
| `_sdpa_kernel` | scores + online softmax + the V-weighted sum, one threadgroup per query head |
| `_gemv_accum_kernel` | o_proj (or down_proj) + the residual add, as a `+=` into the stream |
| `_norm_gemv2_swiglu_kernel` | post-attention rmsnorm + gate and up projections + SwiGLU |
| `_lmhead_argmax_kernel` | final rmsnorm + the full-vocabulary projection + a per-block argmax |

Each of the four GEMV-shaped kernels above — everything except `_qk_rope_write_kernel` and
`_sdpa_kernel`, which never touch a weight MATRIX — has an `_f16` twin (`_norm_gemv_kernel_f16`,
`_gemv_accum_kernel_f16`, `_norm_gemv2_swiglu_kernel_f16`, `_lmhead_argmax_kernel_f16`). Additive,
not a replacement: same fusion, same activation/accumulator dtype (Float32 throughout), only the
resident weight buffer `w` is `_HP` (Float16) instead of `_FP`, widened to Float32 immediately on
load. `residentk.session._ResidentQwen3F16` is the twin session that uploads weights narrowed to
Float16 and dispatches through these kernels instead; `_ResidentQwen3` (Float32) is untouched.

Every remaining boundary is a genuine grid-wide dependency — an rmsnorm needs the whole vector the
previous projection produced, and at `d_ff = 3072` that vector spans 384 threadgroups. Fusing across
one would need a persistent kernel with a device-scope spin barrier; deliberately not attempted.

The layout decision the whole file rests on
----------------------------------------------
Weights are held `[out, in]` row-major — one output column's `k` coefficients CONTIGUOUS. That is
the transpose of what `benchmarks/llm_smoke/generate_manifest.py` writes, and the session pays a
one-time host-side blocked transpose during upload to get it, on purpose.

With the `[in, out]` layout a natural GEMV assigns one output column per THREAD, giving
`n / 256` threadgroups: 4 threadgroups for `o_proj` and `down_proj` at `n = d_model = 1024`, on a
GPU with 40 cores. Measured consequence at that occupancy is roughly a 10x loss on those two
projections — about 0.5 ms per layer, 14 ms per token, i.e. the same order as ALL the submission
overhead this design exists to minimise.

With `[out, in]`, one output column is owned by one 32-lane SIMD group and a 256-thread group owns
8 columns, so `o_proj` gets 128 threadgroups and the 32 lanes of a group read 128 contiguous bytes
per step — coalesced. The transpose is a one-time cost measured and reported by the driver; the
occupancy is per token, forever.

Bounds are the caller's job, and the caller is `residentk.session`
---------------------------------------------------------------------
Every kernel here indexes what it is told to index. There is no way for a GPU kernel to report a
bad dimension — out-of-range writes are silent corruption rather than the clean abort a CPU bounds
check gives (rule 1, in its GPU form: it is not even an abort). So every dimension reaching a launch
is validated on the host by `residentk.contract`'s checks BEFORE the session is built, and the
session re-checks the one dimension that changes per step (`pos < max_ctx`) at every step.
"""

from std.builtin.type_aliases import MutAnyOrigin
from std.gpu import barrier, block_idx, grid_dim, thread_idx
from std.gpu.memory import AddressSpace
from std.math import exp, sqrt
from std.memory import stack_allocation
from residentk.contract import RESIDENT_MAX_D_MODEL, RESIDENT_MAX_HEAD_DIM

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter. `MutAnyOrigin` from `std.builtin.type_aliases`,
NOT `MutableAnyOrigin` — the spelling `accel/launch.mojo` documents as costing six attempts."""

alias _IP = UnsafePointer[Int32, origin=MutAnyOrigin]
"""A device Int32 buffer. Used only for argmax token ids, which must survive a vocabulary larger
than Float32's exact-integer range would guarantee."""

alias _HP = UnsafePointer[Float16, origin=MutAnyOrigin]
"""A device Float16 buffer — the fp16 weight-storage arm's ONLY new pointer type. Every activation,
every accumulator and every norm gain stays `_FP` (Float32) in this arm too: only the resident
weight matrices themselves are halved. That is deliberate mixed precision, not a narrower kernel —
`_norm_gemv_kernel_f16` and its siblings widen each loaded half to Float32 with `.cast[DType.float32]()`
before the multiply, and every accumulator (`acc`, `red`, the reductions) is Float32 throughout, so
the summation order and rounding behaviour inside one dot product are identical to the Float32
arm's. The only new source of error is representing each weight to ~3 decimal digits instead of
~7 before that dot product ever starts — the mixed-precision GEMV practice this package's task
description asked for, not an accumulate-in-half shortcut."""

comptime _TG: Int = 256
"""Threads per threadgroup for every projection kernel. A multiple of Apple's 32-wide SIMD group and
of the 32-lane reduction below, and small enough that 8 SIMD groups fit.

MEASURED, NOT ASSUMED: 256 (8 output columns/threadgroup), 512 (16) and 1024 (32) were all built and
run on the same M4 Max, same checkpoint, same prompt, after the vectorized-load change below landed.
All three measured the same decode throughput within run-to-run noise (roughly 26-32 tok/s across
five runs each) — fewer, fatter threadgroups did not amortize the redundant per-threadgroup
normalization into a measurable win, and did not cost one either. Kept at 256 rather than raised:
`o_proj`/`down_proj` at `n = d_model = 1024` would drop to 32 threadgroups at `_SUBS = 32`, close
enough to this GPU's 40 cores that a smaller or differently-shaped model could under-occupy where
256 would not, for a change this measurement says buys nothing."""

comptime _LANES: Int = 32
"""Lanes cooperating on ONE output column. Apple's SIMD width; also the number of contiguous weight
elements read per step, which is what makes the `[out, in]` layout coalesce."""

comptime _SUBS: Int = _TG // _LANES
"""Output columns one threadgroup produces: 8."""

comptime _VEC: Int = 4
"""Floats one lane loads per vectorized step, via `UnsafePointer.load[width=_VEC]`/`.store`. Metal
lowers a width-4 `Float32` load to a single 128-bit vector instruction, so a lane issues one
instruction to move 16 bytes instead of four instructions moving 4 bytes each. The bytes read from
device memory per step are unchanged — GEMV has no data reuse to exploit the way `gemm_metal`'s
register tile does, since every weight element is read exactly once no matter how the loop is
sliced — so this is purely an instruction-count and memory-request-width improvement, not a traffic
reduction. Confirmed correct against a scalar reference on-device before landing (see this
package's git history); the measured effect is reported in `residentk`'s own docs, not asserted
here as a number nobody re-checks."""

comptime _VEC_STRIDE: Int = _LANES * _VEC
"""Elements one SIMD group advances per vectorized step: 32 lanes x 4 floats = 128, i.e. 512 bytes
of weight row per step across the group — up from the scalar loop's 128 bytes per step."""

comptime _VEC_H: Int = 4
"""Halfs one lane loads per vectorized step in the fp16 weight kernels: 4 x 2 bytes = 8 bytes.

MEASURED, NOT ASSUMED, AND THE FIRST GUESS WAS WRONG: the obvious choice was `_VEC_H = 8` — halfs
are half the width of Float32, so 8 halfs match `_VEC = 4` Float32's 128-bit LOAD WIDTH rather than
its element count. Built and run on the same M4 Max, same checkpoint, same prompt as everything
else in this file, `_VEC_H = 8` made the fp16 session measurably SLOWER than the Float32 arm
(~22 tok/s against the Float32 arm's ~23-24), not faster — the fp16 bandwidth halving this arm
exists for was invisible. The reason: Metal Shading Language has no native 8-wide vector type for
`half` (2, 3 and 4 are the vector widths MSL defines for every scalar type); a `SIMD[float16, 8]`
load is not one hardware instruction on this backend, and whatever it lowers to cost more than it
saved. `_VEC_H = 4` — `half4`, a real MSL vector type — measured a CONSISTENT win instead: ~25
tok/s against the same ~23-24 tok/s Float32 baseline, reproduced across ten interleaved runs. The
lesson generalizes past this one constant: matching a Float32 kernel's BYTE-width vector choice
does not carry over to a narrower dtype if the target language's vector types do not go that wide
— check the actual vector types the backend defines, not just the byte arithmetic."""

comptime _VEC_STRIDE_H: Int = _LANES * _VEC_H
"""Elements one SIMD group advances per vectorized step in the fp16 kernels: 32 lanes x 4 halfs =
128 — the same per-step ELEMENT count as `_VEC_STRIDE`'s Float32 loop, at half the per-step BYTE
count (256 bytes against 512), which is exactly the traffic halving this arm exists to deliver."""

comptime _STAGE: Int = RESIDENT_MAX_D_MODEL
"""Compile-time size of the shared staging array. This constant IS `RESIDENT_MAX_D_MODEL`; the
ceiling in the contract exists because of this allocation, not the other way round. 3072 Float32 is
12 KiB of Apple silicon's 32 KiB threadgroup budget."""

comptime _NEG_HUGE: Float32 = -3.0e38
"""Softmax and argmax initial maximum. Finite rather than `-inf` so that `exp(m - new_max)` on the
first key underflows to a clean 0.0 instead of producing `inf - inf`."""


fn _embed_row_kernel(hidden: _FP, embed: _FP, token_id: Int, d_model: Int):
    """`hidden = embed[token_id]` — the one-token embedding gather that starts a decode step.

    Its own dispatch rather than folded into the first projection, and that costs ~180 us per token
    on purpose. Folding it in would mean every threadgroup of the QKV kernel both READING `hidden`
    (for the shared normalization) and WRITING part of it, which is a read/write race across
    threadgroups with no barrier able to order it. The alternative — each threadgroup re-gathering
    the row redundantly — works but then `hidden` is never materialised, and the residual stream
    needs it materialised two dispatches later.
    """
    var i = Int(block_idx.x) * _TG + Int(thread_idx.x)
    if i < d_model:
        hidden[i] = embed[token_id * d_model + i]


fn _embed_row_kernel_f16(hidden: _FP, embed: _HP, token_id: Int, d_model: Int):
    """The fp16-weight twin of `_embed_row_kernel`. `embed` is the SAME tied embedding/lm_head
    table `_lmhead_argmax_kernel_f16` reads as `w` — resident as Float16 in the fp16 session — so
    the gather widens the one row it reads to Float32 before writing `hidden`, which stays Float32
    like every other activation in this arm. One row (`d_model` elements) per step, so this widening
    costs nothing measurable; it exists so the fp16 session never needs a second, Float32 copy of a
    155M-element table just to serve the gather.
    """
    var i = Int(block_idx.x) * _TG + Int(thread_idx.x)
    if i < d_model:
        hidden[i] = Float32(embed[token_id * d_model + i])


fn _norm_gemv_kernel(
    y: _FP, x: _FP, gamma: _FP, w: _FP, k: Int, n: Int, eps: Float32
):
    """`y = W @ (rmsnorm(x) * gamma)`, `W` held `[n, k]` row-major. One dispatch, one normalization.

    Used for the fused Q/K/V projection: `n = (h_q + 2*h_kv) * d_head` and the three destinations
    are contiguous slices of one output buffer, so three matmuls and one rmsnorm become one launch.

    THE REDUNDANT NORMALIZATION IS DELIBERATE. Every threadgroup recomputes the sum of squares over
    all `k` elements of `x` — `n/8` times in total. At `k = 1024` that is 4 KiB re-read per group
    against ~1 MiB of weights per group, under 1% of the traffic, and it buys the elimination of a
    whole dispatch whose host cost (~180 us) is 40x the arithmetic it would perform.

    Threadgroup shape: 256 threads = 8 SIMD groups of 32 lanes, one group per output column, so
    `grid_dim = ceil(n / 8)`.
    """
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    # ── 1. sum of squares over the whole vector, tree-reduced across the group ──
    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    # Every thread reads the same reduced value and derives the same scale. Uniform by construction,
    # so no broadcast is needed — and every read happens before the barrier that ends stage 2, which
    # is what makes reusing `red` for the lane reduction below safe.
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    # ── 2. stage the normalized, gamma-scaled vector in threadgroup memory ──────
    var s = tid
    while s < k:
        xs[s] = x[s] * inv * gamma[s]
        s += _TG
    barrier()

    # ── 3. one SIMD group per output column ────────────────────────────────────
    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var base = j * k
        # Vectorized main pass: 4-wide loads on BOTH operands, `_LANES` steps of `_VEC_STRIDE`
        # elements. `xs` is the shared, already-normalized vector staged above; `w` is this row's
        # slice of the resident device weight matrix. See `_VEC`'s docstring for why this changes
        # instruction count, not byte count.
        var k_vec = (k // _VEC_STRIDE) * _VEC_STRIDE
        var t = lane * _VEC
        while t < k_vec:
            var xv = xs.load[width=_VEC](t)
            var wv = w.load[width=_VEC](base + t)
            var pv = xv * wv
            acc += pv[0] + pv[1] + pv[2] + pv[3]
            t += _VEC_STRIDE
        # Scalar tail: the `k - k_vec` elements a `_VEC_STRIDE`-wide loop cannot cover exactly.
        # Same lane-stride-`_LANES` pattern the whole loop used before vectorization, so every lane
        # still does the same, uniform number of iterations as every other lane in this tail.
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * w[base + tt]
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = red[sub * _LANES]


fn _norm_gemv_kernel_f16(
    y: _FP, x: _FP, gamma: _FP, w: _HP, k: Int, n: Int, eps: Float32
):
    """The fp16-weight twin of `_norm_gemv_kernel`. Identical except `w`'s type: a resident Float16
    buffer instead of Float32. The normalization, the shared staging, the accumulator and the
    reduction are the SAME Float32 arithmetic as the Float32 kernel — only each weight element's
    storage is halved, and it is widened with `.cast[DType.float32]()` immediately on load, before
    any multiply. See `_HP`'s docstring for why that is mixed precision rather than a lower-precision
    kernel, and `_VEC_H`'s for why the vector width is `half4`, not the `half8` a byte-matched
    guess would reach for.
    """
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    var s = tid
    while s < k:
        xs[s] = x[s] * inv * gamma[s]
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var base = j * k
        var k_vec = (k // _VEC_STRIDE_H) * _VEC_STRIDE_H
        var t = lane * _VEC_H
        while t < k_vec:
            var xv = xs.load[width=_VEC_H](t)
            var wv = w.load[width=_VEC_H](base + t).cast[DType.float32]()
            var pv = xv * wv
            for lane_e in range(_VEC_H):
                acc += pv[lane_e]
            t += _VEC_STRIDE_H
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * Float32(w[base + tt])
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = red[sub * _LANES]


fn _gemv_accum_kernel(y: _FP, x: _FP, w: _FP, k: Int, n: Int):
    """`y += W @ x`, `W` held `[n, k]` row-major. The projection AND its residual add, one dispatch.

    `+=` rather than `=` is the whole point: `o_proj` and `down_proj` both feed a residual
    connection, and each output element `j` is owned by exactly one SIMD group in exactly one
    threadgroup, so the read-modify-write has no race and needs no barrier. Splitting the add into
    its own elementwise dispatch would cost ~180 us of blocked host time for ~1 us of arithmetic.
    """
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var s = tid
    while s < k:
        xs[s] = x[s]
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var base = j * k
        var k_vec = (k // _VEC_STRIDE) * _VEC_STRIDE
        var t = lane * _VEC
        while t < k_vec:
            var xv = xs.load[width=_VEC](t)
            var wv = w.load[width=_VEC](base + t)
            var pv = xv * wv
            acc += pv[0] + pv[1] + pv[2] + pv[3]
            t += _VEC_STRIDE
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * w[base + tt]
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = y[j] + red[sub * _LANES]


fn _gemv_accum_kernel_f16(y: _FP, x: _FP, w: _HP, k: Int, n: Int):
    """The fp16-weight twin of `_gemv_accum_kernel` — `o_proj`/`down_proj` plus the residual `+=`,
    with `w` a resident Float16 buffer widened to Float32 on load. See `_norm_gemv_kernel_f16`.
    """
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var s = tid
    while s < k:
        xs[s] = x[s]
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var base = j * k
        var k_vec = (k // _VEC_STRIDE_H) * _VEC_STRIDE_H
        var t = lane * _VEC_H
        while t < k_vec:
            var xv = xs.load[width=_VEC_H](t)
            var wv = w.load[width=_VEC_H](base + t).cast[DType.float32]()
            var pv = xv * wv
            for lane_e in range(_VEC_H):
                acc += pv[lane_e]
            t += _VEC_STRIDE_H
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * Float32(w[base + tt])
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = y[j] + red[sub * _LANES]


fn _norm_gemv2_swiglu_kernel(
    act: _FP, x: _FP, gamma: _FP, w: _FP, k: Int, n_ff: Int, eps: Float32
):
    """`act = swish(W_gate @ xn) * (W_up @ xn)` with `xn = rmsnorm(x) * gamma`. One dispatch.

    `w` is the gate and up matrices CONCATENATED as `[2 * n_ff, k]` row-major — gate rows first.
    Two projections, one normalization and the elementwise SwiGLU stage collapse into a single
    launch because nothing between them crosses a threadgroup boundary: the group that computes
    `gate[j]` and `up[j]` is the same group that combines them.

    `swish(g) * u` is `mlpk.activation`'s SWIGLU convention exactly — `swiglu(value, gate)` is
    `swish(gate) * value`, with `up` as the value and `gate` as the gate. Getting that backwards
    produces a plausible-looking network that generates different text, which is why the naming is
    spelled out here rather than left to the argument order.
    """
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var gsh = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    var s = tid
    while s < k:
        xs[s] = x[s] * inv * gamma[s]
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var k_vec = (k // _VEC_STRIDE) * _VEC_STRIDE

    # ── gate ────────────────────────────────────────────────────────────────────
    var acc = Float32(0.0)
    if j < n_ff:
        var base = j * k
        var t = lane * _VEC
        while t < k_vec:
            var xv = xs.load[width=_VEC](t)
            var wv = w.load[width=_VEC](base + t)
            var pv = xv * wv
            acc += pv[0] + pv[1] + pv[2] + pv[3]
            t += _VEC_STRIDE
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * w[base + tt]
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0:
        gsh[sub] = red[sub * _LANES]
    barrier()

    # ── up ──────────────────────────────────────────────────────────────────────
    var acc2 = Float32(0.0)
    if j < n_ff:
        var base2 = (n_ff + j) * k
        var t2 = lane * _VEC
        while t2 < k_vec:
            var xv2 = xs.load[width=_VEC](t2)
            var wv2 = w.load[width=_VEC](base2 + t2)
            var pv2 = xv2 * wv2
            acc2 += pv2[0] + pv2[1] + pv2[2] + pv2[3]
            t2 += _VEC_STRIDE
        var tt2 = k_vec + lane
        while tt2 < k:
            acc2 += xs[tt2] * w[base2 + tt2]
            tt2 += _LANES
    red[tid] = acc2
    barrier()
    var st2 = _LANES // 2
    while st2 > 0:
        if lane < st2:
            red[tid] = red[tid] + red[tid + st2]
        barrier()
        st2 //= 2
    if lane == 0 and j < n_ff:
        var g = gsh[sub]
        var u = red[sub * _LANES]
        act[j] = (g / (1.0 + exp(-g))) * u


fn _norm_gemv2_swiglu_kernel_f16(
    act: _FP, x: _FP, gamma: _FP, w: _HP, k: Int, n_ff: Int, eps: Float32
):
    """The fp16-weight twin of `_norm_gemv2_swiglu_kernel` — gate/up/SwiGLU, with `w` a resident
    Float16 buffer widened to Float32 on load. See `_norm_gemv_kernel_f16`.
    """
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var gsh = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    var s = tid
    while s < k:
        xs[s] = x[s] * inv * gamma[s]
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var k_vec = (k // _VEC_STRIDE_H) * _VEC_STRIDE_H

    # ── gate ────────────────────────────────────────────────────────────────────
    var acc = Float32(0.0)
    if j < n_ff:
        var base = j * k
        var t = lane * _VEC_H
        while t < k_vec:
            var xv = xs.load[width=_VEC_H](t)
            var wv = w.load[width=_VEC_H](base + t).cast[DType.float32]()
            var pv = xv * wv
            for lane_e in range(_VEC_H):
                acc += pv[lane_e]
            t += _VEC_STRIDE_H
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * Float32(w[base + tt])
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0:
        gsh[sub] = red[sub * _LANES]
    barrier()

    # ── up ──────────────────────────────────────────────────────────────────────
    var acc2 = Float32(0.0)
    if j < n_ff:
        var base2 = (n_ff + j) * k
        var t2 = lane * _VEC_H
        while t2 < k_vec:
            var xv2 = xs.load[width=_VEC_H](t2)
            var wv2 = w.load[width=_VEC_H](base2 + t2).cast[DType.float32]()
            var pv2 = xv2 * wv2
            for lane_e2 in range(_VEC_H):
                acc2 += pv2[lane_e2]
            t2 += _VEC_STRIDE_H
        var tt2 = k_vec + lane
        while tt2 < k:
            acc2 += xs[tt2] * Float32(w[base2 + tt2])
            tt2 += _LANES
    red[tid] = acc2
    barrier()
    var st2 = _LANES // 2
    while st2 > 0:
        if lane < st2:
            red[tid] = red[tid] + red[tid + st2]
        barrier()
        st2 //= 2
    if lane == 0 and j < n_ff:
        var g = gsh[sub]
        var u = red[sub * _LANES]
        act[j] = (g / (1.0 + exp(-g))) * u


fn _qk_rope_write_kernel(
    q_rot: _FP, ck: _FP, cv: _FP, qkv: _FP, qn_w: _FP, kn_w: _FP,
    cos_t: _FP, sin_t: _FP, pos: Int, h_q: Int, h_kv: Int, d_head: Int, eps: Float32,
):
    """Per-head rmsnorm on Q and K, RoPE on both, and the KV-cache slot write — all in one dispatch.

    `grid_dim = h_q + h_kv`, `block_dim = d_head`. Blocks `[0, h_q)` handle a query head and write
    `q_rot`; blocks `[h_q, h_q + h_kv)` handle a key/value head and write BOTH cache slots.

    THE IN-PLACE CACHE WRITE IS THE SECOND WIN, and it lives here rather than in a separate append.
    `llmk.generate.kv_cache_append_flat` allocates `cache_len + n_new` elements and copies the entire
    cache on every call, twice per layer per step — O(N^2) copying across a generation. This writes
    `ck[(pos * h_kv + head) * d_head + e]` directly, so the copy does not get faster, it stops
    existing.

    The rotation is the SPLIT-HALF (GPT-NeoX) pairing `(e, e + d_head/2)`, matching
    `attnk.rope.rope_apply_flat(..., interleaved=False)` — which is Qwen3's convention. The
    interleaved pairing loads, runs, and is wrong; there is no shape error to catch it.

    Note the order: q_norm/k_norm FIRST, then RoPE. Qwen3 normalizes each head before rotating it,
    which is not what every Llama-family model does.
    """
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


fn _sdpa_kernel(
    attn_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    n_keys: Int, h_q: Int, h_kv: Int, d_head: Int, scale: Float32,
):
    """Attention for ONE new query token over `n_keys` cached keys. `grid_dim = h_q`, `block = d_head`.

    ONLINE (streaming) softmax, so no score row is ever materialised: the running maximum, the
    running normalizer and the running output accumulator are rescaled as each key arrives. That is
    what lets the whole of attention be one dispatch at any context length instead of a
    scores-pass, a softmax-pass and a weighted-sum-pass.

    NO MASK IS APPLIED, and that is a claim rather than an omission. A single query at the true
    current position attends to every cached key by construction, so a causal mask over
    `[1, n_keys]` masks exactly nothing — `qwen3_generate.mojo` asserts precisely that
    (`decode_mask.n_masked != 0` is a hard error there). The session enforces the same invariant on
    the host by passing `n_keys = pos + 1`; a wrong `pos` would show up as a wrong token, not as a
    mask that quietly did nothing.

    Grouped-query attention maps query head `h` to key/value head `h / (h_q / h_kv)`, the same
    integer division `attnk.sdpa.sdpa_forward_flat` performs.
    """
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


fn _lmhead_argmax_kernel(
    blk_val: _FP, blk_idx: _IP, x: _FP, gamma: _FP, w: _FP,
    k: Int, n: Int, eps: Float32, n_iters: Int,
):
    """Final rmsnorm, the full-vocabulary projection, and a per-threadgroup argmax. One dispatch.

    The logits are NEVER materialised and never leave the device. At Qwen3's 151,936-word vocabulary
    a full logits row is 608 KB per step; only each threadgroup's best `(logit, id)` pair is written
    out, and `_argmax_reduce_kernel` collapses those to one pair the host reads as 8 bytes.

    A GRID-STRIDE LOOP, not one threadgroup per 8 columns. `grid_dim` is chosen by the session
    (2048) rather than by `n`, because MAX's per-dispatch host cost GROWS with grid size on this
    backend — measured 113 us at 96 threadgroups, 194 us at 4096, and 499 us at the 19,008 a
    column-per-group launch over this vocabulary would need. A 5.7x host-side penalty for the same
    arithmetic is worth a strided loop.

    `n_iters` is passed in rather than derived so that EVERY threadgroup executes the same number of
    iterations. The loop contains `barrier()`, and a threadgroup barrier reached by only some
    threads of the group hangs the GPU; deriving the trip count from `j < n` would give the last
    group a shorter loop.

    Ties resolve to the LOWEST token id, matching `numpy.argmax` and therefore
    `llmk.generate.greedy_argmax_flat`'s documented convention — so a comparison against a reference
    implementation agrees even in an exact tie.
    """
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var sv = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var si = stack_allocation[_SUBS, DType.int32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    var st0 = tid
    while st0 < k:
        xs[st0] = x[st0] * inv * gamma[st0]
        st0 += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var stride_cols = Int(grid_dim.x) * _SUBS
    var best = _NEG_HUGE
    var best_i = Int32(-1)
    var k_vec = (k // _VEC_STRIDE) * _VEC_STRIDE

    for it in range(n_iters):
        var j = Int(block_idx.x) * _SUBS + sub + it * stride_cols
        var acc = Float32(0.0)
        if j < n:
            var base = j * k
            var t = lane * _VEC
            while t < k_vec:
                var xv = xs.load[width=_VEC](t)
                var wv = w.load[width=_VEC](base + t)
                var pv = xv * wv
                acc += pv[0] + pv[1] + pv[2] + pv[3]
                t += _VEC_STRIDE
            var tt = k_vec + lane
            while tt < k:
                acc += xs[tt] * w[base + tt]
                tt += _LANES
        red[tid] = acc
        barrier()
        var st = _LANES // 2
        while st > 0:
            if lane < st:
                red[tid] = red[tid] + red[tid + st]
            barrier()
            st //= 2
        if lane == 0 and j < n:
            var val = red[sub * _LANES]
            if val > best:
                best = val
                best_i = Int32(j)
        barrier()

    if lane == 0:
        sv[sub] = best
        si[sub] = best_i
    barrier()
    if tid == 0:
        var bv = sv[0]
        var bi = si[0]
        for u in range(1, _SUBS):
            # Strictly greater, so the lowest id survives an exact tie.
            if sv[u] > bv:
                bv = sv[u]
                bi = si[u]
        blk_val[Int(block_idx.x)] = bv
        blk_idx[Int(block_idx.x)] = bi


fn _lmhead_argmax_kernel_f16(
    blk_val: _FP, blk_idx: _IP, x: _FP, gamma: _FP, w: _HP,
    k: Int, n: Int, eps: Float32, n_iters: Int,
):
    """The fp16-weight twin of `_lmhead_argmax_kernel` — final rmsnorm, the tied lm_head projection
    and the per-threadgroup argmax, with `w` a resident Float16 buffer widened to Float32 on load.

    This is the SINGLE LARGEST resident matrix in the model — `vocab * d_model`, ~155M elements,
    tied with the embedding table — so it is also where fp16 storage buys the most per-token
    bandwidth back. See `_norm_gemv_kernel_f16` for the widening discipline and `_HP` for why this
    stays a mixed-precision kernel rather than a half-precision one.
    """
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var sv = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var si = stack_allocation[_SUBS, DType.int32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    var st0 = tid
    while st0 < k:
        xs[st0] = x[st0] * inv * gamma[st0]
        st0 += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var stride_cols = Int(grid_dim.x) * _SUBS
    var best = _NEG_HUGE
    var best_i = Int32(-1)
    var k_vec = (k // _VEC_STRIDE_H) * _VEC_STRIDE_H

    for it in range(n_iters):
        var j = Int(block_idx.x) * _SUBS + sub + it * stride_cols
        var acc = Float32(0.0)
        if j < n:
            var base = j * k
            var t = lane * _VEC_H
            while t < k_vec:
                var xv = xs.load[width=_VEC_H](t)
                var wv = w.load[width=_VEC_H](base + t).cast[DType.float32]()
                var pv = xv * wv
                for lane_e in range(_VEC_H):
                    acc += pv[lane_e]
                t += _VEC_STRIDE_H
            var tt = k_vec + lane
            while tt < k:
                acc += xs[tt] * Float32(w[base + tt])
                tt += _LANES
        red[tid] = acc
        barrier()
        var st = _LANES // 2
        while st > 0:
            if lane < st:
                red[tid] = red[tid] + red[tid + st]
            barrier()
            st //= 2
        if lane == 0 and j < n:
            var val = red[sub * _LANES]
            if val > best:
                best = val
                best_i = Int32(j)
        barrier()

    if lane == 0:
        sv[sub] = best
        si[sub] = best_i
    barrier()
    if tid == 0:
        var bv = sv[0]
        var bi = si[0]
        for u in range(1, _SUBS):
            if sv[u] > bv:
                bv = sv[u]
                bi = si[u]
        blk_val[Int(block_idx.x)] = bv
        blk_idx[Int(block_idx.x)] = bi


fn _argmax_reduce_kernel(out_val: _FP, out_idx: _IP, blk_val: _FP, blk_idx: _IP, n: Int):
    """Collapse the per-threadgroup `(logit, id)` pairs to one. `grid_dim = 1`, `block_dim = 256`.

    Ties resolve to the LOWEST id in both stages — the grid-stride scan uses strict `>`, and the
    tree reduction breaks an exact value tie on the smaller index explicitly. Without that second
    clause the winner of a tie would depend on threadgroup scheduling, which is exactly the kind of
    non-determinism that makes a generated sequence irreproducible.
    """
    var sv = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var si = stack_allocation[_TG, DType.int32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var best = _NEG_HUGE
    var best_i = Int32(-1)
    var i = tid
    while i < n:
        if blk_val[i] > best:
            best = blk_val[i]
            best_i = blk_idx[i]
        i += _TG
    sv[tid] = best
    si[tid] = best_i
    barrier()

    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            var other = sv[tid + stride]
            var other_i = si[tid + stride]
            if other > sv[tid] or (other == sv[tid] and other_i >= 0 and (si[tid] < 0 or other_i < si[tid])):
                sv[tid] = other
                si[tid] = other_i
        barrier()
        stride //= 2

    if tid == 0:
        out_val[0] = sv[0]
        out_idx[0] = si[0]
