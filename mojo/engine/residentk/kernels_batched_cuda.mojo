"""residentk.kernels_batched_cuda — W1 (continuous-batching decode on the CUDA lane): the
CUDA-side BATCHED kernels the Float32 resident session needs that `residentk.kernels` does not
already carry in a weight-agnostic or f32 form. Additive module — `residentk.kernels` and
`residentk.session_cuda` are byte-unmodified. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/qwen3_batched_cuda.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/qwen3_batched_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Every entry point is private, the same rule `residentk.kernels` states —
leading underscores keep these out of `apps/runtime/mojo_inventory.py`'s inventory and out of the
generated dispatch; `residentk.session_cuda_batched` (also private) is the only module that
reaches them, and every launch there is gated behind `CUDA_SESSION_BUILD` exactly the way
`residentk.session_cuda` gates its own.

WHAT IS NEW HERE, AND WHAT IS REUSED FROM residentk.kernels INSTEAD
--------------------------------------------------------------------
The Metal batched tail (`metaldispatch.session_prefill._ensure_decode_batched_ready`) is three
roles: B-row final rmsnorm, batched lm_head + per-vocab-slice argmax, and B-row argmax reduce.
Mapped onto what this package already holds:

1. B-row final rmsnorm — REUSED, not twinned: `residentk.kernels._pf_rmsnorm_rows_kernel` is the
   m-row rmsnorm the CUDA prefill path already runs, weight-dtype-agnostic (reads only `x` and
   `gamma`, both f32 activations/gains), so `session_cuda_batched` dispatches it at `m_rows = B`
   with `gamma = final_norm`.
2. Batched lm_head + argmax — NEW in this file: `_batched_lmhead_argmax_kernel_f32`. The existing
   `_batched_lmhead_argmax_kernel_simd_i8` (residentk.kernels :3533) is the right SHAPE but reads
   weights through the int8+per-row-scale storage format (`_VEC_I8` loads, `wscale[j]` dequant);
   the CUDA session holds Float32 weights, so this is its f32 twin — same vocab partitioning,
   same all-B-rows-per-weight-sweep structure, same strict-`>` lowest-id tie-break — with the
   width-4 Float32 vector loads `_lmhead_argmax_kernel`'s own f32 body uses.
3. B-row argmax reduce — REUSED, not twinned: `residentk.kernels._batched_argmax_reduce_kernel_simd`
   (:3615) is WEIGHT-AGNOSTIC by construction — it only ever reads the `(logit, id)` pair buffers
   the lm_head role wrote (`blk_val`/`blk_idx`) and collapses B rows of them; no weight type
   appears anywhere in its body. Verified by reading it; `session_cuda_batched` dispatches it
   byte-unmodified at `grid_dim = B`.

Mojo 1.0.0 kernel-parameter discipline: every scalar parameter is a fixed-width `Int64`
(DevicePassable), widened back to `Int` once at entry — `accel/launch.mojo`'s pattern, the same
one `residentk.kernels`' own 1.0.0 migration uses.
"""

from std.origin import MutAnyOrigin
from std.gpu import block_idx, grid_dim, thread_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.gpu.primitives.warp import sum as _warp_sum
from residentk.kernels import (
    _TG,
    _LANES,
    _SUBS,
    _VEC,
    _VEC_STRIDE,
    _NEG_HUGE,
    _BATCH_LMHEAD_MAX_ROWS,
)

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — the SAME spelling `residentk.kernels` uses."""

alias _IP = UnsafePointer[Int32, origin=MutAnyOrigin]
"""A device Int32 buffer — the argmax token ids, the same spelling `residentk.kernels` uses."""


def _batched_lmhead_argmax_kernel_f32(
    blk_val: _FP, blk_idx: _IP, xn: _FP, w: _FP,
    B_i64: Int64, k_i64: Int64, n_i64: Int64, n_iters_i64: Int64,
):
    """Float32-weight twin of `_batched_lmhead_argmax_kernel_simd_i8`: batched lm_head +
    per-vocab-slice argmax for B rows. `grid_dim = _LM_BLOCKS`, `block_dim = _TG`, same vocab
    partitioning as the single-row `_lmhead_argmax_kernel` (column
    `j = block_idx.x*_SUBS + sub + it*stride_cols`), but each SIMD group's column is dotted
    against ALL B rows of `xn` (`[B, k]`, PRE-NORMALIZED by the B-row final rmsnorm dispatch that
    runs immediately before this one — this kernel never normalizes), sweeping the `w` row ONCE
    for all B rows — the tokens-per-weight-sweep win the batched tail exists to capture.

    Writes `blk_val[b*grid_dim.x + block_idx.x]` / `blk_idx[...]` per row — the B-row analogue
    of the single-row kernel's per-threadgroup `(logit, id)` pair, consumed by
    `residentk.kernels._batched_argmax_reduce_kernel_simd` (weight-agnostic, reused
    byte-unmodified). Rows beyond `B` are never touched; `B` must be <= `_BATCH_LMHEAD_MAX_ROWS`
    (the same ceiling the i8 twin enforces, sizing the per-thread accumulator arrays).

    The ONLY structural difference from the i8 twin: the weight loads are width-4 Float32 vector
    loads (no `wscale[j]` dequant, no `_VEC_I8` unpack) — the exact load shape
    `_lmhead_argmax_kernel`'s own f32 body uses, which is the load path the CUDA lane's
    Float32-resident weights stream at full HBM speed. Ties resolve to the LOWEST token id
    (strict `>`), matching every other argmax in this package.

    `n_iters` is passed in rather than derived for the same reason the single-row kernel's own
    docstring gives: the loop contains `barrier()` implicitly through `_warp_sum`'s users AND
    every threadgroup must execute the same trip count (a threadgroup barrier reached by only
    some threads hangs the GPU); the caller computes `_ceil_div(vocab, _LM_BLOCKS * _SUBS)` once.
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives.
    var B = Int(B_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    var n_iters = Int(n_iters_i64)
    var sv = stack_allocation[
        _SUBS * _BATCH_LMHEAD_MAX_ROWS, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var si = stack_allocation[
        _SUBS * _BATCH_LMHEAD_MAX_ROWS, DType.int32, address_space = AddressSpace.SHARED
    ]()
    var acc = stack_allocation[_BATCH_LMHEAD_MAX_ROWS, DType.float32]()
    var best = stack_allocation[_BATCH_LMHEAD_MAX_ROWS, DType.float32]()
    var best_i = stack_allocation[_BATCH_LMHEAD_MAX_ROWS, DType.int32]()

    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    for b in range(B):
        best[b] = _NEG_HUGE
        best_i[b] = Int32(-1)

    var stride_cols = Int(grid_dim.x) * _SUBS
    var k_vec = (k // _VEC_STRIDE) * _VEC_STRIDE

    for it in range(n_iters):
        var j = Int(block_idx.x) * _SUBS + sub + it * stride_cols
        if j < n:
            for b in range(B):
                acc[b] = Float32(0.0)
            var base = j * k
            var t = lane * _VEC
            while t < k_vec:
                var wv = w.load[width=_VEC](base + t)
                for b in range(B):
                    var xv = xn.load[width=_VEC](b * k + t)
                    var pv = xv * wv
                    acc[b] += pv[0] + pv[1] + pv[2] + pv[3]
                t += _VEC_STRIDE
            var tt = k_vec + lane
            while tt < k:
                var wvv = w[base + tt]
                for b in range(B):
                    acc[b] += xn[b * k + tt] * wvv
                tt += _LANES
            for b in range(B):
                var total = _warp_sum(acc[b])
                if lane == 0:
                    if total > best[b]:
                        best[b] = total
                        best_i[b] = Int32(j)

    if lane == 0:
        for b in range(B):
            sv[sub * _BATCH_LMHEAD_MAX_ROWS + b] = best[b]
            si[sub * _BATCH_LMHEAD_MAX_ROWS + b] = best_i[b]
    barrier()
    if tid == 0:
        for b in range(B):
            var bv = sv[b]
            var bi = si[b]
            for u in range(1, _SUBS):
                # Strictly greater, so the lowest id survives an exact tie.
                if sv[u * _BATCH_LMHEAD_MAX_ROWS + b] > bv:
                    bv = sv[u * _BATCH_LMHEAD_MAX_ROWS + b]
                    bi = si[u * _BATCH_LMHEAD_MAX_ROWS + b]
            blk_val[b * Int(grid_dim.x) + Int(block_idx.x)] = bv
            blk_idx[b * Int(grid_dim.x) + Int(block_idx.x)] = bi
