"""
residentk.kernels — the fused Metal kernels one resident decode token is made of. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32, float16, int8, int4
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

A THIRD, additive weight-storage arm: an `_i8` twin of the same five kernels (the four above plus
`_embed_row_kernel`, since the tied embedding/lm_head table is also a weight matrix in this sense)
— `_embed_row_kernel_i8`, `_norm_gemv_kernel_i8`, `_gemv_accum_kernel_i8`,
`_norm_gemv2_swiglu_kernel_i8`, `_lmhead_argmax_kernel_i8`. Same fusion, same Float32
activation/accumulator discipline as the `_f16` arm; the resident weight buffer `w` is `_I8P`
(Int8) with a companion per-output-row Float32 SCALE buffer, and every loaded element is
dequantized in-register — `Float32(i8_val) * wscale[row]` — inside the reduction loop before the
multiply that consumes it. See `_I8P`'s docstring for the per-channel (per-row) symmetric
quantization scheme and its relationship to `gemm.quantized`'s frozen NF4 in-kernel-dequant
pattern. `residentk.session._ResidentQwen3I8` is the third twin session.

A FOURTH, additive weight-storage arm, one bit width narrower: an `_i4` twin of the THREE GEMV-
shaped kernels only (`_norm_gemv_kernel_i4`, `_gemv_accum_kernel_i4`, `_norm_gemv2_swiglu_kernel_i4`
— `w_qkv`/`w_o`/`w_gu`/`w_down`, the four per-layer weight matrices). The tied embedding/lm_head
table deliberately STAYS int8 (`_embed_row_kernel_i8`/`_lmhead_argmax_kernel_i8`, reused verbatim by
`_ResidentQwen3I4`) — a 4-bit vocabulary table is a separate, larger correctness risk on the FINAL
output layer specifically, and this arm's task was scoped to the three per-layer GEMV roles int8
already covers. Same Float32 activation/accumulator discipline; the resident weight buffer `w` is
`_I4P` (two signed 4-bit values packed per byte) with a companion per-output-row Float32 SCALE
buffer, `scale = max(|row|) / 7` — the SAME per-channel symmetric scheme int8 uses, one bit width
down. See `_I4P`'s docstring for the packing convention and the mask+shift unpack, and
`_VEC_I4B`'s for the packed-byte vector-width measurement this arm required that int8 did not (a
packed int4 byte holds two elements, so the byte-width-vs-element-count choice int8 inherited
unchanged from Float32 does not transfer automatically). `residentk.session._ResidentQwen3I4` is
the fourth twin session. **Correctness FAILS on the real 0.6B checkpoint** (a razor-thin argmax
flip at decode step 0, logit-gap 0.0095 — see `_ResidentQwen3I4`'s own docstring and
`benchmarks/llm_smoke/REALRACE_RESULTS.md`'s int4 addendum); kept in-tree as a precisely-diagnosed
dead end, never raced, never combined with anything else.

A FIFTH, additive axis, orthogonal to all four weight-storage arms above (including the failing
int4 one — this axis touches neither `w_qkv`/`w_o`/`w_gu`/`w_down` nor the embedding table): the KV
CACHE itself (`ck`/`cv`, written once per token by `_qk_rope_write_kernel` and read `n_keys` times
per token by `_sdpa_kernel`) is Float32 in every weight arm shipped so far — narrowing WEIGHTS never
touched it. `_qk_rope_write_kernel_kvf16` (write) and `_sdpa_kernel_kvf16` (read) are the fp16-KV-
cache twins: `ck`/`cv` become resident Float16 buffers, narrowed on write and widened to Float32
immediately on read, same discipline as `_HP`'s weight arm. Independent of weight precision because
neither kernel touches a weight MATRIX — `_qk_rope_write_kernel_kvf16` combines with
`_norm_gemv_kernel_i8` and friends exactly as freely as with the Float32 GEMV kernels, since the two
axes share no buffer. `_sdpa_kernel`'s own docstring already establishes that its cost is real
per-key compute that grows with `n_keys = pos + 1`, not padding (PR #510's GPU-counter measurement:
26.85% of per-token time, 28 dispatches) — halving `ck`/`cv`'s bytes-per-entry halves what that
kernel actually streams per key, which is the whole point of this axis. Not combined with the int4
arm above: that arm's own correctness failure means there is nothing usable to combine with (see
`residentk.session._ResidentQwen3I8KVF16`'s own docstring and the RealRace addendum this axis's
task added).

A SIXTH, additive axis, orthogonal to every precision arm above (weights AND the KV cache):
`_sdpa_kernel`'s per-key REDUCTION MECHANISM, not its math or its storage dtype. PR #510's GPU-
counter measurement put `sdpa` at 26.85% of per-token time, and PR #510/#512's own diagnosis named
the reason: the kernel's cost is dominated by a per-key barrier-synchronized shared-memory tree
reduction (`log2(d_head)` levels, each a full threadgroup `barrier()`, plus one more "safety"
barrier before the next key's write can safely reuse `red` — 9 barrier hits per key at this model's
`d_head = 128`), not by the single-scalar KV-cache read `_sdpa_kernel_kvf16`'s narrower storage
already halved. `_sdpa_kernel_simd` (Float32 KV cache) and `_sdpa_kernel_simd_kvf16` (Float16 KV
cache) replace that tree with a two-level reduction: `std.gpu.primitives.warp.sum` reduces each
32-lane SIMD-group via hardware shuffle (`llvm.air.simd_shuffle_xor`, confirmed on this Apple Silicon
target — `std.gpu.WARP_SIZE` resolves to 32 under `is_apple_gpu()`) with NO barrier at all — SIMD-
group execution is lockstep by hardware construction — then a shared-memory combine across the
`d_head / 32` per-group partial sums, needing exactly TWO `barrier()` calls per key instead of nine
(one so every thread sees the per-group partial sums written to shared memory, one so a fast thread
cannot start the next key's write to that same shared array before a slow thread has finished
reading this key's values out of it — the same "safety barrier" purpose `_sdpa_kernel`'s own trailing
barrier serves, one level up). Same
online-softmax math, same accumulator types, same everything except HOW the per-key dot product's
`d_head` partial products collapse to one scalar. Composes with every weight-precision arm exactly as
`_sdpa_kernel`/`_sdpa_kernel_kvf16` already do, since neither touches a weight matrix.

A SEVENTH, additive axis, orthogonal to every arm above: `_sdpa_kernel_simd`'s GRID SIZE, not its
per-key math or its reduction mechanism. PR #519's long-context investigation found `_sdpa_kernel_
simd` degrading 21-29x faster with position than either of two real, installed, independently-
implemented opponents (mlx-lm, llama.cpp) on the identical checkpoint/prompt, and GPU-counter
profiling isolated it to exactly one role: `sdpa`'s own GPU dispatch time scaled 69-144x from a
shallow to a deep position (repeated measurements) while every other role stayed flat. The mechanism
is OCCUPANCY, not the per-key memory-access pattern (a batched-load, cache-defeated scratch probe
disproved that hypothesis directly): `_sdpa_kernel_simd` launches `grid_dim=h_q` threadgroups
regardless of `n_keys` — 16 threadgroups x 4 SIMD-groups = 64 warps GPU-wide at this model's
`h_q=16`, `d_head=128`, launched once per token per layer, completely independent of how deep the KV
cache has grown. As `n_keys` grows into the thousands, the SAME 64 warps just iterate longer; no
more parallelism is ever recruited. `_splitk_partial_kernel_simd` and `_splitk_merge_
kernel_simd` (this file, below `_sdpa_kernel_simd_kvf16`) are the fix: a Flash-Decoding-style split
that launches `h_q * n_splits` threadgroups instead of `h_q`, each covering a slice of `[0, n_keys)`
and writing an unnormalized partial, followed by a tiny per-head merge dispatch. `_sdpa_kernel_simd`
itself is UNCHANGED — every byte of its own body is exactly as PR #515 left it — because a scratch
probe of the real production grid/block shape found splitting a REGRESSION at the published race's
own shallow depth (16 tokens): two dispatches' fixed overhead outweighs the extra parallelism when
there is barely any work to spread across it. `metaldispatch.session._MBQwen3I8AllSimd3` (the
published race's own arm) therefore gates on `n_keys` at the call site, dispatching the ORIGINAL,
byte-unmodified `_sdpa_kernel_simd` below the threshold and the new split/merge pair above it — see
that struct's own docstring for the exact threshold and the measurement that picked it.

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
from std.gpu import barrier, block_idx, grid_dim, lane_id, thread_idx, warp_id, WARP_SIZE
from std.gpu.memory import AddressSpace
from std.gpu.primitives.warp import shuffle_xor as _shuffle_xor, sum as _warp_sum
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

alias _I8P = UnsafePointer[Int8, origin=MutAnyOrigin]
"""A device Int8 buffer — the int8 weight-storage arm's ONLY new pointer type. Every activation,
every accumulator and every norm gain stays `_FP` (Float32) here too, exactly as `_HP`'s fp16 arm
keeps them: only the resident weight matrices themselves are quantized. Paired everywhere with a
per-OUTPUT-ROW `_FP` (Float32) scale buffer — one scale per row, not one for the whole matrix — so
`_norm_gemv_kernel_i8` and its siblings dequantize each loaded element as
`Float32(i8_val) * wscale[row]` INSIDE the reduction loop, in-register, before the multiply that
consumes it: the same "widen immediately, accumulate in Float32" discipline `_HP`'s docstring
establishes for fp16, applied to a coarser storage format that additionally needs a per-row scale
rather than a fixed exponent. This is also the exact in-kernel-dequant PATTERN `gemm.quantized`'s
frozen `gemv_nf4_flat` established for NF4 on the CPU (dequantize inside the reduction loop rather
than materializing a dequantized copy of the whole matrix first) — reused here as a technique, on a
different (per-row-scaled int8, not NF4) format, on a different backend (Metal, not CPU); that
frozen kernel is read-only reference material, never called from here."""

comptime _VEC_I8: Int = 4
"""Int8 elements one lane loads per vectorized step in the int8 weight kernels: 4 x 1 byte = 4
bytes (`char4`).

MEASURED, NOT ASSUMED — same discipline `_VEC_H`'s docstring established for fp16, and with the
same conclusion for the same reason: Metal Shading Language defines vector types at widths 2, 3 and
4 for EVERY scalar type it supports, `char`/`int8` included, and no wider (there is no MSL `char8`
or `char16`). Byte-matching `_VEC`'s Float32 load (4 elements, 16 bytes) would suggest reaching for
a 16-wide int8 vector to move the same 16 bytes per step — exactly the kind of byte-matched guess
`_VEC_H`'s docstring already found wrong for `half` (`half8` is not a real MSL type either). For
`int8` there is only one REAL candidate to measure, `char4`, unlike fp16's two-candidate case, so
this constant is not a choice among alternatives the way `_VEC_H` was — it is the ceiling MSL
allows, confirmed on this M4 Max to compile and run correctly against a scalar int8 reference before
landing (see this package's own docs for the measured decode effect, reported once rather than
asserted here as a number nobody re-checks)."""

comptime _VEC_STRIDE_I8: Int = _LANES * _VEC_I8
"""Elements one SIMD group advances per vectorized step in the int8 kernels: 32 lanes x 4 int8s =
128 — the same per-step ELEMENT count as `_VEC_STRIDE`'s Float32 loop and `_VEC_STRIDE_H`'s fp16
loop, at a QUARTER the per-step BYTE count of the Float32 loop (128 bytes against 512) and HALF the
fp16 loop's (128 against 256) — the next halving of bandwidth this arm exists to deliver."""

alias _I4P = UnsafePointer[UInt8, origin=MutAnyOrigin]
"""A device buffer of PACKED int4 pairs — the int4 weight-storage arm's ONLY new pointer type. Two
signed 4-bit values per byte: bits `[3:0]` are the EVEN k-index element (the "low nibble"), bits
`[7:4]` are the ODD k-index element (the "high nibble"), each in `[-7, 7]` (never `-8`; see
`_quantize_nibble_i4`'s docstring in `residentk.session` for why the range is kept symmetric, one
bit width down from `_I8P`'s `[-127, 127]`). Paired with a per-OUTPUT-ROW `_FP` (Float32) scale
buffer exactly as `_I8P` is — one scale per row, `scale = max(|row|) / 7` — so
`_norm_gemv_kernel_i4` and its siblings dequantize each nibble as `Float32(nibble) * wscale[row]`
INSIDE the reduction loop, in-register, before the multiply that consumes it: the same
"widen-and-scale immediately, accumulate in Float32" discipline `_HP` and `_I8P` both establish, one
storage format coarser. Activations, the accumulator, and every norm gain stay `_FP` here too —
mixed precision, not an all-int4 kernel.

The unpack is mask+shift, not the manual-word-bitcast forms `int8_pack_probe.mojo` already measured
LOSING to a native vector load for int8: shift the low nibble into a SIGNED byte's top 4 bits with
`<< 4` (the shift itself discards the bits that don't belong, no explicit mask needed), then an
ARITHMETIC right-shift by 4 replicates the sign bit down — the standard 4-to-8-bit sign-extension
trick. The high nibble needs an explicit mask (`& 0xF0`) first, since it is already aligned, then
the same arithmetic right-shift. Both are two cheap ALU ops on an already-loaded register, not a
second memory access."""

comptime _VEC_I4B: Int = 4
"""PACKED BYTES one lane loads per vectorized step in the int4 kernels — a `uchar4` vector load, 4
bytes = 8 int4 elements. MEASURED, NOT ASSUMED, per `benchmarks/llm_smoke/int4_pack_probe.mojo`:
unlike int8 (one candidate, `char4`, because a packed int4 byte holds TWO elements per byte where an
int8 byte holds one, this format introduces a genuinely new width choice `_VEC_I8`'s docstring did
not face — unpacking a `uchar2` (2 bytes = 4 elements/lane/step) against a `uchar4` (4 bytes = 8
elements/lane/step) at three real decode-shaped GEMVs on this M4 Max (`k=1024,n=3072`;
`k=3072,n=1024`; `k=2048,n=1024`; median of 200 after 5 warm-ups) found `uchar4` tied or faster in
all three cases (0.0%, -5.0%, -2.5% relative to `uchar2` — negative meaning faster), never slower.
Both variants were checked against an independent pure-host scalar Int4 reference on a small,
deliberately-vector-stride-misaligned shape (`k=136`) BEFORE either timing number was trusted."""

comptime _VEC_I4: Int = _VEC_I4B * 2
"""Int4 ELEMENTS one lane advances per vectorized step: 4 packed bytes x 2 elements/byte = 8 — twice
`_VEC_I8`'s 4, at the SAME 4-byte load width, because this storage format is twice as dense."""

comptime _VEC_STRIDE_I4: Int = _LANES * _VEC_I4
"""ELEMENTS one SIMD group advances per vectorized step in the int4 kernels: 32 lanes x 8 int4s =
256 — DOUBLE `_VEC_STRIDE_I8`'s 128, at HALF the per-step BYTE count (128 bytes against 256), which
is the next halving of bandwidth this arm exists to deliver."""

comptime _VEC_BYTE_STRIDE_I4: Int = _LANES * _VEC_I4B
"""BYTES one SIMD group advances per vectorized step in the int4 kernels: 32 lanes x 4 bytes = 128 —
the quantity the packed-byte pointer arithmetic below actually steps by; `_VEC_STRIDE_I4` (256) is
the same distance measured in elements, at half the bytes."""

comptime _STAGE: Int = RESIDENT_MAX_D_MODEL
"""Compile-time size of the shared staging array. This constant IS `RESIDENT_MAX_D_MODEL`; the
ceiling in the contract exists because of this allocation, not the other way round. 3072 Float32 is
12 KiB of Apple silicon's 32 KiB threadgroup budget."""

comptime _NEG_HUGE: Float32 = -3.0e38
"""Softmax and argmax initial maximum. Finite rather than `-inf` so that `exp(m - new_max)` on the
first key underflows to a clean 0.0 instead of producing `inf - inf`."""


def _embed_row_kernel(hidden: _FP, embed: _FP, token_id: Int, d_model: Int):
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


def _embed_row_kernel_f16(hidden: _FP, embed: _HP, token_id: Int, d_model: Int):
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


def _embed_row_kernel_i8(hidden: _FP, embed: _I8P, embed_scale: _FP, token_id: Int, d_model: Int):
    """The int8-weight twin of `_embed_row_kernel`. `embed` is the SAME tied embedding/lm_head
    table `_lmhead_argmax_kernel_i8` reads as `w` — resident as Int8 in the int8 session, one
    Float32 scale per VOCABULARY ROW in `embed_scale` (so `embed_scale[token_id]` is exactly the
    scale `_lmhead_argmax_kernel_i8` would use for output row `token_id` of the tied projection,
    since a vocabulary row IS an output row either way this table is read). One row (`d_model`
    elements) per step, so the per-element dequant multiply costs nothing measurable here; it
    exists so the int8 session never needs a second, Float32 copy of a 155M-element table just to
    serve the gather.
    """
    var i = Int(block_idx.x) * _TG + Int(thread_idx.x)
    if i < d_model:
        var s = embed_scale[token_id]
        hidden[i] = Float32(embed[token_id * d_model + i]) * s


def _norm_gemv_kernel(
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


def _norm_gemv_kernel_f16(
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


def _norm_gemv_kernel_i8(
    y: _FP, x: _FP, gamma: _FP, w: _I8P, wscale: _FP, k: Int, n: Int, eps: Float32
):
    """The int8-weight twin of `_norm_gemv_kernel`. Identical except `w`'s type: a resident Int8
    buffer instead of Float32, with a companion per-output-row Float32 scale buffer `wscale`
    (`wscale[j]` for output column `j` — see `_I8P`'s docstring). The normalization, the shared
    staging, the accumulator and the reduction are the SAME Float32 arithmetic as the Float32
    kernel; only each weight element's storage is quantized, and it is dequantized — widened to
    Float32 AND multiplied by its row's scale — immediately on load, inside the reduction loop,
    before any multiply consumes it. See `_VEC_I8`'s docstring for why the vector width is `char4`.
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
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC_I8](srow)
        var k_vec = (k // _VEC_STRIDE_I8) * _VEC_STRIDE_I8
        var t = lane * _VEC_I8
        while t < k_vec:
            var xv = xs.load[width=_VEC_I8](t)
            var wv = w.load[width=_VEC_I8](base + t).cast[DType.float32]() * srow_v
            var pv = xv * wv
            for lane_e in range(_VEC_I8):
                acc += pv[lane_e]
            t += _VEC_STRIDE_I8
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
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


def _norm_gemv_kernel_simd_i8(
    y: _FP, x: _FP, gamma: _FP, w: _I8P, wscale: _FP, k: Int, n: Int, eps: Float32
):
    """The REDUCTION-MECHANISM twin of `_norm_gemv_kernel_i8` — IDENTICAL int8-dequant GEMV math,
    IDENTICAL per-output-row `wscale`, only HOW its two internal reductions collapse to a scalar
    differs. Same relationship `_sdpa_kernel_simd` has to `_sdpa_kernel`, applied to a DIFFERENT
    reduction shape — see `gemv_simd_reduce_probe.mojo` for the device-side confirmation this
    docstring's claims rest on, not assumed.

    `_norm_gemv_kernel_i8` has TWO barrier-tree reductions, not one, and they are DIFFERENT shapes:

    1. Sum-of-squares over the whole `k`-length vector, reduced across all `_TG = 256` threads —
       `log2(256) = 8` barrier-synchronized halving levels. Apple's real hardware SIMD-group width
       (`std.gpu.WARP_SIZE` under `is_apple_gpu()`) is 32, confirmed on this M4 Max — so these 256
       threads are EXACTLY `_SUBS = 8` full SIMD-groups, the SAME multi-group shape
       `_sdpa_kernel_simd`'s `d_head = 128 = 4 groups` fix targeted, just twice as many groups.
       Fixed the SAME way: `_warp_sum` reduces each of the 8 groups with NO barrier (hardware
       lockstep), one lane per group writes its group's total into an `_SUBS`-slot shared array,
       ONE `barrier()` makes those 8 writes visible, every thread sums the 8 entries itself (cheap
       — 8 adds). 8 barriers → 1. No trailing "safety" barrier is needed here the way
       `_sdpa_kernel_simd`'s per-KEY loop needs one: this reduction runs exactly ONCE per launch
       (not once per loop iteration reusing the same shared slots), so there is no next iteration
       for a fast thread to race ahead into.

    2. Each output column's dot product, reduced across its own `_LANES = 32`-wide SIMD group —
       `log2(32) = 5` more barrier-synchronized halving levels, one PER OUTPUT COLUMN (there are
       `_SUBS = 8` columns computed per threadgroup, each by its own, fully independent, SIMD
       group). This is a SIMPLER case than either of the above: since one SIMD group maps 1:1 to
       one output column with NOTHING to combine across groups (unlike the sum-of-squares above,
       and unlike `_sdpa_kernel_simd`'s cross-group softmax score), a single-level `_warp_sum`
       alone — no shared array, no barrier at all — IS the complete reduction: it reduces the
       column's 32 partial sums and broadcasts the total to every lane in that group, and the one
       lane at `lane == 0` writes it straight to `y[j]`. 5 barriers → 0.

    13 barriers per launch (`8 + 5`, ignoring the two unrelated staging barriers that protect
    `xs` and are untouched by this change) collapse to 1. Every other line — the normalization
    arithmetic, the int8 dequantization (`Float32(i8) * wscale[row]`, inside the loop, immediately
    on load), the vectorized `char4` load, the accumulation order within one lane — is copied
    byte-for-byte from `_norm_gemv_kernel_i8`, because the math this kernel computes must be, and
    is verified to be, IDENTICAL; only the summation order across lanes/groups differs.
    """
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var grp = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    # ── 1. sum of squares over the whole vector, two-level SIMD-shuffle reduced ──
    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    var ss_group = _warp_sum(ss)
    if lane == 0:
        grp[sub] = ss_group
    barrier()
    var ss_total = Float32(0.0)
    for g in range(_SUBS):
        ss_total += grp[g]
    var inv = 1.0 / sqrt(ss_total / Float32(k) + eps)

    # ── 2. stage the normalized, gamma-scaled vector in threadgroup memory ──────
    var s = tid
    while s < k:
        xs[s] = x[s] * inv * gamma[s]
        s += _TG
    barrier()

    # ── 3. one SIMD group per output column, single-level SIMD-shuffle reduction ─
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var base = j * k
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC_I8](srow)
        var k_vec = (k // _VEC_STRIDE_I8) * _VEC_STRIDE_I8
        var t = lane * _VEC_I8
        while t < k_vec:
            var xv = xs.load[width=_VEC_I8](t)
            var wv = w.load[width=_VEC_I8](base + t).cast[DType.float32]() * srow_v
            var pv = xv * wv
            for lane_e in range(_VEC_I8):
                acc += pv[lane_e]
            t += _VEC_STRIDE_I8
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
            tt += _LANES
    var total = _warp_sum(acc)
    if lane == 0 and j < n:
        y[j] = total


def _norm_gemv_kernel_i4(
    y: _FP, x: _FP, gamma: _FP, w: _I4P, wscale: _FP, k: Int, n: Int, eps: Float32
):
    """The int4-weight twin of `_norm_gemv_kernel_i8`. Identical except `w`'s type: a resident
    PACKED-int4 buffer (two signed nibbles per byte, `_I4P`'s docstring gives the packing and unpack
    convention) instead of one int8 per byte, with the SAME per-output-row Float32 scale buffer
    `wscale` (`scale = max(|row|) / 7`, one bit width down from int8's `/127`). The normalization,
    the shared staging, the accumulator and the reduction are the SAME Float32 arithmetic as the
    int8 kernel; only the weight-load-and-unpack step differs, per `_VEC_I4B`'s docstring's measured
    vector-width choice.
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
        var n_bytes = (k + 1) // 2
        var base = j * n_bytes
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC_I4B](srow)
        var k_vec = (k // _VEC_STRIDE_I4) * _VEC_STRIDE_I4
        # `tb` is a BYTE index into this row's packed weights, not an element index -- the packed
        # format has two elements per byte, so `tb`'s element-space position is `tb * 2`.
        var tb = lane * _VEC_I4B
        while tb * 2 < k_vec:
            var bv = w.load[width=_VEC_I4B](base + tb)
            var lo = ((bv << 4).cast[DType.int8]() >> 4).cast[DType.float32]() * srow_v
            var hi = ((bv & UInt8(0xF0)).cast[DType.int8]() >> 4).cast[DType.float32]() * srow_v
            var elem_off = tb * 2
            for e in range(_VEC_I4B):
                var xv = xs.load[width=2](elem_off + e * 2)
                acc += xv[0] * lo[e] + xv[1] * hi[e]
            tb += _VEC_BYTE_STRIDE_I4
        # Scalar tail: the `k - k_vec` elements a `_VEC_STRIDE_I4`-wide loop cannot cover exactly.
        # Same lane-stride-`_LANES` pattern the whole loop used before vectorization, unpacking one
        # nibble at a time from its byte.
        var tt = k_vec + lane
        while tt < k:
            var bidx = tt // 2
            var b = w[base + bidx]
            var val: Int8
            if tt % 2 == 0:
                val = (b << 4).cast[DType.int8]() >> 4
            else:
                val = (b & UInt8(0xF0)).cast[DType.int8]() >> 4
            acc += xs[tt] * (Float32(val) * srow)
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


def _gemv_accum_kernel(y: _FP, x: _FP, w: _FP, k: Int, n: Int):
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


def _gemv_accum_kernel_f16(y: _FP, x: _FP, w: _HP, k: Int, n: Int):
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


def _gemv_accum_kernel_i8(y: _FP, x: _FP, w: _I8P, wscale: _FP, k: Int, n: Int):
    """The int8-weight twin of `_gemv_accum_kernel` — `o_proj`/`down_proj` plus the residual `+=`,
    with `w` a resident Int8 buffer and `wscale` its per-output-row Float32 scale. See
    `_norm_gemv_kernel_i8`."""
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
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC_I8](srow)
        var k_vec = (k // _VEC_STRIDE_I8) * _VEC_STRIDE_I8
        var t = lane * _VEC_I8
        while t < k_vec:
            var xv = xs.load[width=_VEC_I8](t)
            var wv = w.load[width=_VEC_I8](base + t).cast[DType.float32]() * srow_v
            var pv = xv * wv
            for lane_e in range(_VEC_I8):
                acc += pv[lane_e]
            t += _VEC_STRIDE_I8
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
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


def _gemv_accum_kernel_simd_i8(y: _FP, x: _FP, w: _I8P, wscale: _FP, k: Int, n: Int):
    """The REDUCTION-MECHANISM twin of `_gemv_accum_kernel_i8` — IDENTICAL `o_proj`/`down_proj` +
    residual-add math, only HOW each output column's dot product collapses to a scalar differs.

    `_gemv_accum_kernel_i8` has exactly ONE reduction (no whole-vector norm here, unlike
    `_norm_gemv_kernel_i8` — `x` is only staged into shared memory, a plain parallel copy with no
    reduction): each output column's dot product, reduced across its own `_LANES = 32`-wide SIMD
    group, `log2(32) = 5` barrier-synchronized halving levels, one per column, `_SUBS = 8`
    independent columns per threadgroup. Since one SIMD group maps 1:1 to one output column with
    NOTHING to combine across groups, a single-level `_warp_sum` — no shared array, no barrier at
    all — IS the complete reduction: it reduces the column's 32 partial sums, broadcasts the total
    to every lane in that group, and `lane == 0` adds it into `y[j]`. 5 barriers → 0. See
    `_norm_gemv_kernel_simd_i8`'s docstring for the fuller account of why this shape needs no
    cross-group combine, unlike `_sdpa_kernel_simd`'s or that other kernel's own sum-of-squares
    stage. Every other line is copied byte-for-byte from `_gemv_accum_kernel_i8`.
    """
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
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
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC_I8](srow)
        var k_vec = (k // _VEC_STRIDE_I8) * _VEC_STRIDE_I8
        var t = lane * _VEC_I8
        while t < k_vec:
            var xv = xs.load[width=_VEC_I8](t)
            var wv = w.load[width=_VEC_I8](base + t).cast[DType.float32]() * srow_v
            var pv = xv * wv
            for lane_e in range(_VEC_I8):
                acc += pv[lane_e]
            t += _VEC_STRIDE_I8
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
            tt += _LANES
    var total = _warp_sum(acc)
    if lane == 0 and j < n:
        y[j] = y[j] + total


def _gemv_accum_kernel_i4(y: _FP, x: _FP, w: _I4P, wscale: _FP, k: Int, n: Int):
    """The int4-weight twin of `_gemv_accum_kernel_i8` — `o_proj`/`down_proj` plus the residual
    `+=`, with `w` a resident packed-int4 buffer and `wscale` its per-output-row Float32 scale. See
    `_norm_gemv_kernel_i4`."""
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
        var n_bytes = (k + 1) // 2
        var base = j * n_bytes
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC_I4B](srow)
        var k_vec = (k // _VEC_STRIDE_I4) * _VEC_STRIDE_I4
        var tb = lane * _VEC_I4B
        while tb * 2 < k_vec:
            var bv = w.load[width=_VEC_I4B](base + tb)
            var lo = ((bv << 4).cast[DType.int8]() >> 4).cast[DType.float32]() * srow_v
            var hi = ((bv & UInt8(0xF0)).cast[DType.int8]() >> 4).cast[DType.float32]() * srow_v
            var elem_off = tb * 2
            for e in range(_VEC_I4B):
                var xv = xs.load[width=2](elem_off + e * 2)
                acc += xv[0] * lo[e] + xv[1] * hi[e]
            tb += _VEC_BYTE_STRIDE_I4
        var tt = k_vec + lane
        while tt < k:
            var bidx = tt // 2
            var b = w[base + bidx]
            var val: Int8
            if tt % 2 == 0:
                val = (b << 4).cast[DType.int8]() >> 4
            else:
                val = (b & UInt8(0xF0)).cast[DType.int8]() >> 4
            acc += xs[tt] * (Float32(val) * srow)
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


def _norm_gemv2_swiglu_kernel(
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


def _norm_gemv2_swiglu_kernel_f16(
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


def _norm_gemv2_swiglu_kernel_i8(
    act: _FP, x: _FP, gamma: _FP, w: _I8P, wscale: _FP, k: Int, n_ff: Int, eps: Float32
):
    """The int8-weight twin of `_norm_gemv2_swiglu_kernel` — gate/up/SwiGLU, with `w` a resident
    Int8 buffer and `wscale` a per-output-row Float32 scale over its `2 * n_ff` rows (gate rows
    first, `wscale[j]`; up rows second, `wscale[n_ff + j]` — the exact same row indexing
    `_narrow_transposed_into`'s Float32/Float16 twins already use for the concatenated gate/up
    matrix, applied to the scale buffer alongside it). See `_norm_gemv_kernel_i8`.
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
    var k_vec = (k // _VEC_STRIDE_I8) * _VEC_STRIDE_I8

    # ── gate ────────────────────────────────────────────────────────────────────
    var acc = Float32(0.0)
    if j < n_ff:
        var base = j * k
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC_I8](srow)
        var t = lane * _VEC_I8
        while t < k_vec:
            var xv = xs.load[width=_VEC_I8](t)
            var wv = w.load[width=_VEC_I8](base + t).cast[DType.float32]() * srow_v
            var pv = xv * wv
            for lane_e in range(_VEC_I8):
                acc += pv[lane_e]
            t += _VEC_STRIDE_I8
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
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
        var srow2 = wscale[n_ff + j]
        var srow2_v = SIMD[DType.float32, _VEC_I8](srow2)
        var t2 = lane * _VEC_I8
        while t2 < k_vec:
            var xv2 = xs.load[width=_VEC_I8](t2)
            var wv2 = w.load[width=_VEC_I8](base2 + t2).cast[DType.float32]() * srow2_v
            var pv2 = xv2 * wv2
            for lane_e2 in range(_VEC_I8):
                acc2 += pv2[lane_e2]
            t2 += _VEC_STRIDE_I8
        var tt2 = k_vec + lane
        while tt2 < k:
            acc2 += xs[tt2] * (Float32(w[base2 + tt2]) * srow2)
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


def _norm_gemv2_swiglu_kernel_simd_i8(
    act: _FP, x: _FP, gamma: _FP, w: _I8P, wscale: _FP, k: Int, n_ff: Int, eps: Float32
):
    """The REDUCTION-MECHANISM twin of `_norm_gemv2_swiglu_kernel_i8` — IDENTICAL gate/up/SwiGLU
    math, IDENTICAL per-output-row `wscale` over the concatenated `2 * n_ff` rows, only HOW its
    THREE internal reductions collapse to a scalar differs. See `_norm_gemv_kernel_simd_i8`'s
    docstring for the full account of the two reduction SHAPES this file's GEMV kernels have; this
    kernel has one of each shape, twice (gate and up each get their own column-dot-product stage):

    1. Sum-of-squares over the whole `k`-length vector (256 threads = `_SUBS = 8` full SIMD
       groups): two-level SIMD-shuffle, exactly as `_norm_gemv_kernel_simd_i8`'s own stage 1. 8
       barriers → 1.
    2. Gate projection's per-output-column dot product (one SIMD group per column, nothing to
       combine across groups): single-level `_warp_sum`, no shared array. Its result still needs
       to reach the FINAL combine below, so `lane == 0` writes it to `gsh[sub]` exactly as the
       barrier-tree kernel does — kept behind ONE `barrier()` (down from that kernel's
       five-level tree PLUS its own trailing barrier, six total), out of the same caution
       `_sdpa_kernel_simd`'s trailing safety barrier documents, even though `gsh[sub]` is written
       and later read only by the SAME lane (`lane == 0` of the same group) — a same-thread
       read-after-write that needs no barrier for ITS OWN visibility, but this file does not spend
       a proof of that on removing one launch-once barrier when the cost of being wrong is silent
       wrong output. 6 barriers → 1.
    3. Up projection's per-output-column dot product: identical shape to the gate stage's, but
       nothing downstream needs a barrier afterward — the kernel's very next statement is the
       final combine, executed by the SAME lane that computed this stage's own result. 5 barriers
       → 0.

    19 barriers per launch (`8 + 6 + 5`, ignoring the one unrelated staging barrier that protects
    `xs`) collapse to 2. Every other line is copied byte-for-byte from `_norm_gemv2_swiglu_kernel_i8`.
    """
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var grp = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var gsh = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    var ss_group = _warp_sum(ss)
    if lane == 0:
        grp[sub] = ss_group
    barrier()
    var ss_total = Float32(0.0)
    for g in range(_SUBS):
        ss_total += grp[g]
    var inv = 1.0 / sqrt(ss_total / Float32(k) + eps)

    var s = tid
    while s < k:
        xs[s] = x[s] * inv * gamma[s]
        s += _TG
    barrier()

    var j = Int(block_idx.x) * _SUBS + sub
    var k_vec = (k // _VEC_STRIDE_I8) * _VEC_STRIDE_I8

    # ── gate ────────────────────────────────────────────────────────────────────
    var acc = Float32(0.0)
    if j < n_ff:
        var base = j * k
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC_I8](srow)
        var t = lane * _VEC_I8
        while t < k_vec:
            var xv = xs.load[width=_VEC_I8](t)
            var wv = w.load[width=_VEC_I8](base + t).cast[DType.float32]() * srow_v
            var pv = xv * wv
            for lane_e in range(_VEC_I8):
                acc += pv[lane_e]
            t += _VEC_STRIDE_I8
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
            tt += _LANES
    var gate_total = _warp_sum(acc)
    if lane == 0:
        gsh[sub] = gate_total
    barrier()

    # ── up ──────────────────────────────────────────────────────────────────────
    var acc2 = Float32(0.0)
    if j < n_ff:
        var base2 = (n_ff + j) * k
        var srow2 = wscale[n_ff + j]
        var srow2_v = SIMD[DType.float32, _VEC_I8](srow2)
        var t2 = lane * _VEC_I8
        while t2 < k_vec:
            var xv2 = xs.load[width=_VEC_I8](t2)
            var wv2 = w.load[width=_VEC_I8](base2 + t2).cast[DType.float32]() * srow2_v
            var pv2 = xv2 * wv2
            for lane_e2 in range(_VEC_I8):
                acc2 += pv2[lane_e2]
            t2 += _VEC_STRIDE_I8
        var tt2 = k_vec + lane
        while tt2 < k:
            acc2 += xs[tt2] * (Float32(w[base2 + tt2]) * srow2)
            tt2 += _LANES
    var up_total = _warp_sum(acc2)
    if lane == 0 and j < n_ff:
        var g = gsh[sub]
        act[j] = (g / (1.0 + exp(-g))) * up_total


def _norm_gemv2_swiglu_kernel_i4(
    act: _FP, x: _FP, gamma: _FP, w: _I4P, wscale: _FP, k: Int, n_ff: Int, eps: Float32
):
    """The int4-weight twin of `_norm_gemv2_swiglu_kernel_i8` — gate/up/SwiGLU, with `w` a resident
    packed-int4 buffer and `wscale` a per-output-row Float32 scale over its `2 * n_ff` rows (gate
    rows first, `wscale[j]`; up rows second, `wscale[n_ff + j]` — same row indexing as the int8
    twin). `base`/`base2` are BYTE offsets (`n_bytes = (k + 1) // 2` per row), unlike the int8
    twin's element offsets, because this format packs two elements per byte. See
    `_norm_gemv_kernel_i4`.
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
    var k_vec = (k // _VEC_STRIDE_I4) * _VEC_STRIDE_I4
    var n_bytes = (k + 1) // 2

    # ── gate ────────────────────────────────────────────────────────────────────
    var acc = Float32(0.0)
    if j < n_ff:
        var base = j * n_bytes
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC_I4B](srow)
        var tb = lane * _VEC_I4B
        while tb * 2 < k_vec:
            var bv = w.load[width=_VEC_I4B](base + tb)
            var lo = ((bv << 4).cast[DType.int8]() >> 4).cast[DType.float32]() * srow_v
            var hi = ((bv & UInt8(0xF0)).cast[DType.int8]() >> 4).cast[DType.float32]() * srow_v
            var elem_off = tb * 2
            for e in range(_VEC_I4B):
                var xv = xs.load[width=2](elem_off + e * 2)
                acc += xv[0] * lo[e] + xv[1] * hi[e]
            tb += _VEC_BYTE_STRIDE_I4
        var tt = k_vec + lane
        while tt < k:
            var bidx = tt // 2
            var b = w[base + bidx]
            var val: Int8
            if tt % 2 == 0:
                val = (b << 4).cast[DType.int8]() >> 4
            else:
                val = (b & UInt8(0xF0)).cast[DType.int8]() >> 4
            acc += xs[tt] * (Float32(val) * srow)
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
        var base2 = (n_ff + j) * n_bytes
        var srow2 = wscale[n_ff + j]
        var srow2_v = SIMD[DType.float32, _VEC_I4B](srow2)
        var tb2 = lane * _VEC_I4B
        while tb2 * 2 < k_vec:
            var bv2 = w.load[width=_VEC_I4B](base2 + tb2)
            var lo2 = ((bv2 << 4).cast[DType.int8]() >> 4).cast[DType.float32]() * srow2_v
            var hi2 = ((bv2 & UInt8(0xF0)).cast[DType.int8]() >> 4).cast[DType.float32]() * srow2_v
            var elem_off2 = tb2 * 2
            for e2 in range(_VEC_I4B):
                var xv2 = xs.load[width=2](elem_off2 + e2 * 2)
                acc2 += xv2[0] * lo2[e2] + xv2[1] * hi2[e2]
            tb2 += _VEC_BYTE_STRIDE_I4
        var tt2 = k_vec + lane
        while tt2 < k:
            var bidx2 = tt2 // 2
            var b2 = w[base2 + bidx2]
            var val2: Int8
            if tt2 % 2 == 0:
                val2 = (b2 << 4).cast[DType.int8]() >> 4
            else:
                val2 = (b2 & UInt8(0xF0)).cast[DType.int8]() >> 4
            acc2 += xs[tt2] * (Float32(val2) * srow2)
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


def _qk_rope_write_kernel(
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


def _qk_rope_write_kernel_kvf16(
    q_rot: _FP, ck: _HP, cv: _HP, qkv: _FP, qn_w: _FP, kn_w: _FP,
    cos_t: _FP, sin_t: _FP, pos: Int, h_q: Int, h_kv: Int, d_head: Int, eps: Float32,
):
    """The fp16-KV-CACHE twin of `_qk_rope_write_kernel` — a THIRD precision axis, orthogonal to the
    `_f16`/`_i8` WEIGHT-storage twins above. `ck`/`cv` are resident Float16 here instead of Float32;
    every other buffer (`q_rot`, `qkv`, the norm gains, the RoPE tables) stays `_FP` (Float32),
    exactly the same "only the resident buffer this arm targets narrows" discipline `_HP`'s own
    docstring establishes for weights, applied to the KV CACHE instead of a weight matrix.

    The q_norm/k_norm/RoPE arithmetic itself is BYTE-IDENTICAL to `_qk_rope_write_kernel` — computed
    in Float32 exactly as before, on the same `qkv` (Float32 activation) input. Narrowing happens
    only at the final store: `ck[...] = Float16(o0)` instead of `ck[...] = o0`. Nothing upstream of
    that store differs, so any numerical difference between this kernel's cache contents and the
    Float32 kernel's is attributable to that one narrowing, not to a different rotation or a
    different normalization.

    `q_rot` (the query for THIS step) is never written to the cache and stays Float32 — only `ck`/
    `cv` (the keys/values of every PAST step, read back by `_sdpa_kernel_kvf16` for as many future
    steps as the position stays resident) are the narrowed buffers, since those are what this arm's
    task is reducing the bytes-per-entry of.
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
            ck[kb + e] = Float16(o0)
            ck[kb + e + n_pairs] = Float16(o1)

    # V, narrowed at the store exactly like K above — see this kernel's own docstring.
    if not is_q:
        cv[(pos * h_kv + head) * d_head + e] = Float16(qkv[(h_q + h_kv + head) * d_head + e])


def _sdpa_kernel(
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


def _sdpa_kernel_kvf16(
    attn_out: _FP, q_rot: _FP, ck: _HP, cv: _HP,
    n_keys: Int, h_q: Int, h_kv: Int, d_head: Int, scale: Float32,
):
    """The fp16-KV-cache twin of `_sdpa_kernel` — the READ half of the KV-cache-precision arm, paired
    with `_qk_rope_write_kernel_kvf16`'s WRITE half. `ck`/`cv` are resident Float16; `q_rot` (this
    step's query, never cached) and `attn_out` stay Float32.

    THE WIDEN-IMMEDIATELY DISCIPLINE, same as every weight-precision arm: each Float16 element read
    from `ck`/`cv` is cast to Float32 (`Float32(ck[kb + e])` / `Float32(cv[kb + e])`) the INSTANT it
    is read, before it touches the dot product or the online-softmax accumulator. The running max
    `m`, the running normalizer `denom` and the running output accumulator `o` are Float32
    throughout — IDENTICAL to `_sdpa_kernel`'s own — so this kernel never accumulates in the narrow
    type; only the STORAGE `ck`/`cv` sit in shrinks.

    This is the kernel whose real per-key cost is the target this arm's task names: `_sdpa_kernel`'s
    own docstring already states the cost grows with `n_keys = pos + 1` (real per-key compute, not
    padding — see PR #510's GPU-counter finding, `sdpa` at 26.85% of per-token time). Halving each
    cached K/V element's bytes halves the bytes THIS kernel actually streams per key, independent of
    whatever the weight-precision track does to the four GEMV-shaped kernels elsewhere in this file.
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
        red[e] = qv * Float32(ck[kb + e])
        barrier()
        var stride = d_head // 2
        while stride > 0:
            if e < stride:
                red[e] = red[e] + red[e + stride]
            barrier()
            stride //= 2
        var s = red[0] * scale
        barrier()

        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        o = o * corr + w * Float32(cv[kb + e])
        denom = denom * corr + w
        m = nm

    attn_out[h * d_head + e] = o / denom


def _sdpa_kernel_simd(
    attn_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    n_keys: Int, h_q: Int, h_kv: Int, d_head: Int, scale: Float32,
):
    """The REDUCTION-MECHANISM twin of `_sdpa_kernel` — IDENTICAL online-softmax math, IDENTICAL
    Float32 KV-cache storage, only HOW each key's `d_head`-wide dot product collapses to one scalar
    differs.

    `_sdpa_kernel` reduces with a shared-memory tree: every one of the `log2(d_head)` halving steps
    is a full threadgroup `barrier()`, plus one more "safety" barrier so the next key's write cannot
    race a slow lane still reading this key's score — 9 barrier hits per key at this model's
    `d_head = 128` (see that kernel's own docstring for exactly what the safety barrier guards).
    PR #510's GPU-counter measurement found `sdpa` at 26.85% of per-token time; PR #512's Shrink
    phase named THIS reduction, not the per-scalar cache read, as the reason.

    `d_head = 128` and Apple's hardware SIMD-group width (`std.gpu.WARP_SIZE` under
    `is_apple_gpu()`) is 32 — confirmed on this M4 Max by `benchmarks/llm_smoke/
    sdpa_simd_reduce_probe.mojo`'s own device-side probe, not assumed — so one `_sdpa_kernel`
    threadgroup's `d_head` threads are FOUR separate SIMD-groups, not one. A single-level
    `std.gpu.primitives.warp.sum` call only reduces WITHIN one 32-lane group; it would fold each
    32-lane quarter of the dot product to its own partial sum and stop there. This kernel therefore
    uses a TWO-level reduction:

    1. `_warp_sum(partial)` — `std.gpu.primitives.warp.sum`, a butterfly `shuffle_xor` pattern
       lowered to `llvm.air.simd_shuffle_xor` on this target — reduces each of the four 32-lane
       SIMD-groups to that group's total, broadcast to every lane in the group. Hardware lockstep
       execution within a SIMD-group means this needs NO `barrier()` at all.
    2. The lane at `lane_id() == 0` in each group (there are `d_head // WARP_SIZE` of them) writes
       its group's total into a small shared array; a `barrier()` makes those writes visible to
       every thread; every thread then sums that array's `d_head // WARP_SIZE` entries itself
       (cheap — at most 8 adds). A SECOND `barrier()` follows the read, for the exact same reason
       `_sdpa_kernel`'s own trailing "safety" barrier exists: without it, a fast thread could reach
       the NEXT key's `lane_id() == 0` write to this same shared array before a slow thread has
       finished reading THIS key's values out of it.

    Two barriers per key instead of nine. Everything else — the running max `m`, the running
    normalizer `denom`, the running output accumulator `o`, the rescale-and-accumulate arithmetic —
    is copied byte-for-byte from `_sdpa_kernel`'s own loop body, because the math this kernel
    computes must be, and is verified to be, IDENTICAL.
    """
    comptime _SIMD_GROUPS: Int = RESIDENT_MAX_HEAD_DIM // WARP_SIZE
    """Fixed upper bound on the number of SIMD-groups one threadgroup can contain, sized off the
    same `RESIDENT_MAX_HEAD_DIM` ceiling `red`'s allocation above uses for the same reason: the real
    `d_head` is a runtime value, but `stack_allocation` needs a compile-time size. At this model's
    `d_head = 128` only the first 4 of these 8 slots are ever touched."""
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
        # Safety barrier, same purpose as `_sdpa_kernel`'s own trailing one: every thread has now
        # READ every slot of `grp`, but without this barrier a fast thread could reach the NEXT
        # key's `if lane == 0: grp[grp_id] = ...` write before a slow thread (possibly in a
        # DIFFERENT SIMD-group, which this barrier -- unlike the warp-shuffle above -- CAN order
        # against) has finished this key's read above. Two barriers per key total, against nine for
        # the barrier-tree kernel.
        barrier()

        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        o = o * corr + w * cv[kb + e]
        denom = denom * corr + w
        m = nm

    attn_out[h * d_head + e] = o / denom


def _sdpa_kernel_simd_kvf16(
    attn_out: _FP, q_rot: _FP, ck: _HP, cv: _HP,
    n_keys: Int, h_q: Int, h_kv: Int, d_head: Int, scale: Float32,
):
    """The fp16-KV-cache twin of `_sdpa_kernel_simd`, composing the reduction-mechanism axis with
    the KV-cache-precision axis exactly as `_sdpa_kernel_kvf16` composes the ORIGINAL barrier-tree
    reduction with fp16 KV-cache storage — see that kernel's docstring for the widen-immediately
    discipline (`Float32(ck[kb + e])`/`Float32(cv[kb + e])` the instant each element is read, before
    it touches the dot product or the online-softmax accumulator). Every reduction-mechanism detail
    is identical to `_sdpa_kernel_simd`'s own docstring; only `ck`/`cv`'s storage type differs.
    """
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
        var partial = qv * Float32(ck[kb + e])
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
        o = o * corr + w * Float32(cv[kb + e])
        denom = denom * corr + w
        m = nm

    attn_out[h * d_head + e] = o / denom


def _splitk_partial_kernel_simd(
    m_out: _FP, l_out: _FP, o_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    n_keys: Int, n_splits: Int, h_q: Int, h_kv: Int, d_head: Int, scale: Float32,
):
    """The OCCUPANCY twin of `_sdpa_kernel_simd` — IDENTICAL per-key math (the SIMD-shuffle two-level
    reduction copied byte-for-byte from that kernel's own loop body), only the KEY RANGE and what
    gets written at the end differ. Grid is `h_q * n_splits` threadgroups (`block_idx.x` flattens
    `(head, split)`) instead of `_sdpa_kernel_simd`'s `h_q`, so a deep decode recruits `n_splits`
    times as many warps GPU-wide for the SAME query token — the actual fix for the effect PR #519's
    long-context investigation named: `_sdpa_kernel_simd`'s occupancy is a FIXED 64 warps (`h_q=16`
    threadgroups x 4 SIMD-groups at this model's `d_head=128`) no matter how deep `n_keys` grows,
    so the exact same 64 warps just iterate longer as the KV cache grows — no more parallelism is
    ever recruited. This kernel is the SPLIT half of a two-dispatch Flash-Decoding-style fix: each
    of the `n_splits` blocks assigned to one query head computes an UNNORMALIZED online-softmax
    partial (`m`, `l`, `o`) over its own contiguous slice of `[0, n_keys)`, never divides by `l`, and
    never combines with any other split — `_splitk_merge_kernel_simd` (this file, directly
    below) does that, as a second, tiny, per-head dispatch.

    Split `s` of `n_splits` owns keys `[n_keys * s // n_splits, n_keys * (s + 1) // n_splits)` —
    integer-division ranges that partition `[0, n_keys)` exactly once each, with no gap and no
    overlap, for ANY `n_keys` and `n_splits` (including `n_keys < n_splits`, where the later splits'
    ranges are simply empty: `range(key_start, key_end)` with `key_start == key_end` iterates zero
    times, so an empty split falls out of the SAME loop with no extra branch). An empty split writes
    `m_out = _NEG_HUGE`, `l_out = 0.0`, `o_out = 0.0` for its head — the untouched initial values of
    the same three accumulators every non-empty split starts from — which `_splitk_merge_kernel_
    simd`'s own docstring shows folds into a merge as a true no-op, not a special case.

    Gated by `n_keys` at the call site (`metaldispatch.session._MBQwen3I8AllSimd3.step`), never
    unconditionally: a scratch probe timing the real production grid/block shape (`grid_dim=16,
    block_dim=128`, this model's exact `h_q`/`d_head`) found splitting a REGRESSION at shallow
    `n_keys` (16, the published race's own depth) — two dispatches' fixed launch overhead outweighs
    the extra parallelism when there is barely any work to parallelize — and a growing WIN from
    around `n_keys ~= 500` up (1.4x), widening with depth (4.3x at 2000, 6.3x at 4000, 10.6x at
    8000, the same probe found). `_sdpa_kernel_simd` itself is therefore left untouched and still the
    ONLY kernel dispatched below the session's threshold; this kernel and its merge twin are
    additional, never a replacement.
    """
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


def _splitk_merge_kernel_simd(
    attn_out: _FP, m_in: _FP, l_in: _FP, o_in: _FP, n_splits: Int, d_head: Int,
):
    """The MERGE half of `_splitk_partial_kernel_simd`'s two-dispatch fix — collapses that
    kernel's `n_splits` unnormalized `(m, l, o)` partials per query head into ONE final normalized
    `attn_out`, using the standard associative online-softmax combine (the same rescale-and-add
    `_sdpa_kernel_simd`'s own per-KEY loop uses, one level up: a partial's `m`/`l`/`o` plays exactly
    the role one key's score/weight/value plays there).

    `grid_dim = h_q`, `block_dim = d_head` — ONE thread per `(head, e)` output element, same shape
    `_sdpa_kernel_simd`'s own final write uses. Deliberately NO `barrier()`: thread `e` only ever
    reads column `e` of every split's `o_in` and writes column `e` of `attn_out` — no thread ever
    touches another thread's slot, so there is nothing for a barrier to order (the same "thread-
    private shared slot" property `_lmhead_argmax_kernel`'s per-block winner write already relies on
    for its own no-barrier-needed claim).

    An EMPTY split (`_splitk_partial_kernel_simd`'s own docstring: `m = _NEG_HUGE`, `l = 0.0`,
    `o = 0.0`, whenever that split's key range was empty) folds into this merge as a genuine no-op,
    not a special case needing its own branch: `_NEG_HUGE` is a large FINITE sentinel (`-3.0e38`),
    not IEEE `-inf`, so `nm = max(m, _NEG_HUGE)` is simply whatever `m` already was once any real
    split has been merged, `exp(_NEG_HUGE - nm)` underflows cleanly to `0.0` (no NaN, unlike a true
    `-inf - -inf`), and that `0.0` weight multiplies the empty split's own `l = 0.0` / `o = 0.0` --
    contributing exactly nothing. Verified against a host Float64 reference at ragged `n_keys` that
    deliberately included more splits than keys, in the isolated kernel-level test this pair ships
    with (`test_residentk_attn_splitk_kernel.mojo`), before this docstring's claim was trusted.
    """
    var h = Int(block_idx.x)
    var e = Int(thread_idx.x)

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)
    for s in range(n_splits):
        var idx = h * n_splits + s
        var sm = m_in[idx]
        var sl = l_in[idx]
        var so = o_in[idx * d_head + e]
        var nm = m if m > sm else sm
        var corr = exp(m - nm)
        var w = exp(sm - nm)
        o = o * corr + w * so
        denom = denom * corr + w * sl
        m = nm

    attn_out[h * d_head + e] = o / denom


def _splitk_partial_kernel_simd_batched4(
    m_out: _FP, l_out: _FP, o_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    n_keys: Int, n_splits: Int, h_q: Int, h_kv: Int, d_head: Int, scale: Float32,
):
    """The BARRIER-BATCHING twin of `_splitk_partial_kernel_simd` — IDENTICAL math (same online-
    softmax accumulation, same split-range partition, same two-level SIMD-shuffle-then-shared-array
    reduction per key), only how many keys' worth of reduction happen between one `barrier()` pair
    and the next differs: `_BATCH_K = 4` keys per round here, instead of `_splitk_partial_kernel_
    simd`'s one.

    HONEST RESULT, STATED FIRST: this kernel is CORRECT (bit-exact against `_splitk_partial_kernel_
    simd` in every case this pair's own isolated suite checks, `test_residentk_attn_splitk_batched_
    kernel.mojo` — `split_vs_batched` reads exactly `0.0` at every depth tested, including `n_keys=
    4000`) but it is NOT FASTER — it is measurably, reproducibly SLOWER than the kernel it was meant
    to improve on. GPU-counter measurement (`qwen3_probe_counters_i8_allsimd4_splitk_deepctx.mojo`
    vs. `qwen3_probe_counters_i8_allsimd3_splitk_deepctx.mojo`, identical descriptor plan, identical
    machine, back-to-back, 3 rounds each) found this kernel's own `splitk_partial` role costing
    ~8.0-8.5ms at `n_keys=4000` against the unbatched kernel's own ~7.7-7.8ms there — a real ~4-10%
    REGRESSION, not the hoped-for win — reproduced at `_BATCH_K=2` as well (~8.3-8.4ms, no better),
    ruling out "not enough batching yet" as the explanation. See MOTIVATION below for why this was
    tried, and CONCLUSION at the end of this docstring for the most likely explanation and what this
    rules out. This kernel remains landed, additive, and unwired from anything the published race
    depends on — an honest, verified null result, matching this codebase's own established practice
    for a real investigation that did not pan out (e.g. the fp16-KV-cache "zero speedup" finding).

    MOTIVATION (this task's own Profile phase, `_splitk_partial_kernel_simd`'s per-key loop, GPU-
    counter-isolated): `_splitk_partial`+`_splitk_merge` are 71.5-73.1% of per-token GPU time at
    `n_keys=4000` even after the split-K occupancy fix (PR #520) — by far the largest single-role
    share left — and a from-scratch `n_splits` retune (this same Profile phase) found occupancy
    already saturated around 16-32 splits, ruling out "more parallelism" as a further lever. What was
    hypothesized to be left, per that phase's own conclusion, was the per-key reduction ITSELF:
    `_splitk_partial_kernel_simd`'s loop body (copied byte-for-byte from `_sdpa_kernel_simd`'s own,
    per that kernel's docstring) pays TWO `barrier()` hits per key — one to publish each SIMD-group's
    partial dot-product sum to shared memory, one "safety" hit so a fast thread cannot race the NEXT
    key's write against a slow thread still reading THIS key's values — and the working assumption
    was that a real GPU `barrier()` is not free: every thread in the whole threadgroup must reach it
    before any proceeds, and at `n_keys/n_splits ~= 250` (4000 keys / 16 splits, this model's shipped
    depth) that is 500 barrier hits per threadgroup for ONE token's ONE layer's ONE split. THE
    MEASURED RESULT ABOVE SHOWS THIS ASSUMPTION WAS WRONG for this kernel shape on this hardware —
    see CONCLUSION.

    THE CHANGE: batch `_BATCH_K` keys into ONE barrier round instead of one key into two barriers.
    Per batch of (up to) `_BATCH_K` keys:
      1. For each of the batch's keys, compute this thread's own `qv * ck[...]` product and reduce it
         to a per-SIMD-group total via `_warp_sum` — hardware-lockstep, NO barrier needed (identical
         to `_splitk_partial_kernel_simd`'s own per-key use of `_warp_sum`) — and have lane 0 of each
         group write that key's group-total into `grp[key_in_batch * n_groups + group_id]`. This is
         PURE register/shuffle work across `_BATCH_K` keys with no cross-thread ordering requirement
         yet, so it needs no barrier between keys within the batch.
      2. ONE `barrier()` — makes every key-in-batch's every group-total write visible to every thread.
      3. For each of the batch's keys IN ORDER, every thread sums that key's `n_groups` shared
         group-totals (>= identical arithmetic to `_splitk_partial_kernel_simd`'s own per-key sum),
         scales it, and folds it into the running online-softmax `(m, denom, o)` — the SAME sequential
         rescale-and-accumulate recurrence `_splitk_partial_kernel_simd`'s own per-key loop already
         uses, just executed `_BATCH_K` times per barrier round instead of once.
      4. ONE more `barrier()` — the same "safety" purpose as the original's trailing barrier: every
         thread has now READ every slot of this batch's `grp` region, so the barrier orders that read
         against the NEXT batch's step-1 writes to the SAME shared array before any thread proceeds.

    Two `barrier()` hits per `_BATCH_K`-key batch instead of per key — roughly a 4x reduction in
    barrier COUNT (not, per the HONEST RESULT above, a 4x reduction in wall time — see CONCLUSION),
    with the identical online-softmax recurrence and identical per-key arithmetic order within a
    batch (key 0 before key 1 before key 2 before key 3, exactly as `_splitk_partial_kernel_simd`'s
    sequential loop already visits them) — so the reordering this introduces is confined to WHEN
    shared-memory writes become visible, never to the order the accumulators themselves are updated
    in. `grp` grows from `_SIMD_GROUPS` slots to `_SIMD_GROUPS * _BATCH_K` (32 Float32 at this
    model's `d_head=128`, still a trivial shared-memory footprint) to hold one batch's worth of
    per-key group-totals at once.

    The FINAL batch of a split's key range may hold fewer than `_BATCH_K` keys (`key_end - key_start`
    is not guaranteed to be a multiple of 4) — `batch_n = min(_BATCH_K, key_end - j)` bounds both
    loops to the keys that actually remain, the same "a short last batch just does less work, no
    special-case branch" shape `_splitk_partial_kernel_simd`'s own empty-split handling already
    relies on (see that kernel's docstring). Verified against a host Float64 reference AND against
    `_splitk_partial_kernel_simd` itself, at multiple depths including ragged (`key_end - key_start`
    not a multiple of `_BATCH_K`) and more-than-one-batch-empty-tail cases, in this pair's own
    isolated kernel-level suite (`test_residentk_attn_splitk_batched_kernel.mojo`) before any
    production code depends on it — see that file for the four-way comparison this kernel's own
    unbatched twin's suite already established the pattern for.

    CONCLUSION, from the measured regression (HONEST RESULT above), attempted a SECOND time with an
    obvious efficiency fix (caching each key's `kb` byte offset once, in a small `_BATCH_K`-element
    per-thread array, instead of recomputing it a second time in phase 3 — the first version of this
    kernel computed `kb` twice per key, once per phase; caching it narrowed but did not close the
    regression, so redundant address arithmetic was A real cost but not THE dominant one) and a third
    time at `_BATCH_K=2` (same ~4-10% regression, ruling out "not enough batching yet"): the most
    likely explanation is that a `barrier()` across this kernel's own small, single-threadgroup shape
    (`block_dim=d_head=128` = exactly 4 SIMD-groups, likely resident on relatively few of this Apple
    GPU's ALU clusters at once) is simply not expensive enough on this hardware for removing 3 out of
    4 of them to show up as a net win, while the batched loop structure itself (an outer `while` with
    a per-iteration `min()` and two separate `for kk in range(batch_n)` passes, replacing the
    unbatched kernel's single tight `for j in range(key_start, key_end)` loop) adds real register-
    pressure and instruction-count overhead the compiler does not fully hide. This is a DIFFERENT
    conclusion from the fp16-KV-cache investigation's own "memory bandwidth is not the bottleneck"
    finding — that investigation is about bytes read; this one is about `barrier()` itself, on THIS
    kernel's specific occupancy/register shape, and does not generalize to a claim that GPU barriers
    are cheap everywhere (a much larger threadgroup, or a kernel already register-starved for other
    reasons, could measure differently) — only that batching keys between barriers, done this way,
    for THIS kernel, on THIS hardware, is a net loss. Per-key barrier count is therefore RULED OUT,
    not confirmed, as the dominant remaining long-context lever this codebase's own Profile phase
    hypothesized it might be.

    ADDITIVE ONLY: `_splitk_partial_kernel_simd` (this kernel's unbatched twin) is byte-unmodified.
    Must be compiled into its OWN binary, never alongside `_splitk_partial_kernel_simd` — same
    truncated-Metal-AIR-name substring collision every other role-variant pair in this file's sibling
    module (`metaldispatch.session`) documents: both kernel names contain `splitk_part`, `_classify_
    splitk_pipeline`'s own match substring, so two pipelines matching one role in the same binary
    would collide with no way to tell them apart.
    """
    comptime _SIMD_GROUPS: Int = RESIDENT_MAX_HEAD_DIM // WARP_SIZE
    comptime _BATCH_K: Int = 4
    var grp = stack_allocation[_SIMD_GROUPS * _BATCH_K, DType.float32, address_space = AddressSpace.SHARED]()
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

    var j = key_start
    while j < key_end:
        var batch_n = min(_BATCH_K, key_end - j)

        var kb_arr = InlineArray[Int, _BATCH_K](fill=0)
        """Per-key key-block byte offsets, computed ONCE per key in the first phase below and reused
        in the second — `_splitk_partial_kernel_simd`'s own single-pass loop computes this same `kb`
        once per key and uses it for BOTH the `ck` read (phase 1's job here) and the `cv` read
        (phase 2's), since both happen in the same loop iteration there; splitting the two reads
        across a barrier means the SAME `kb` value is needed again after the barrier, so it is
        cached in this small (`_BATCH_K`-element, plain per-thread) array rather than recomputed —
        recomputing it turned out to measurably cost more than the barrier savings this kernel
        exists to capture (this file's own commit history has the before/after GPU-counter numbers
        that caught it)."""

        for kk in range(batch_n):
            var kb = ((j + kk) * h_kv + hk) * d_head
            kb_arr[kk] = kb
            var partial = qv * ck[kb + e]
            var group_total = _warp_sum(partial)
            if lane == 0:
                grp[kk * n_groups + grp_id] = group_total
        barrier()

        for kk in range(batch_n):
            var s = Float32(0.0)
            for g in range(n_groups):
                s += grp[kk * n_groups + g]
            s *= scale

            var nm = m if m > s else s
            var corr = exp(m - nm)
            var w = exp(s - nm)
            var kb = kb_arr[kk]
            o = o * corr + w * cv[kb + e]
            denom = denom * corr + w
            m = nm
        barrier()

        j += batch_n

    m_out[idx] = m
    l_out[idx] = denom
    o_out[idx * d_head + e] = o


def _splitk_partial_kernel_simd_native(
    m_out: _FP, l_out: _FP, o_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    n_keys: Int, n_splits: Int, h_q: Int, h_kv: Int, d_head: Int, scale: Float32,
):
    """The REDUCTION-SHAPE twin of `_splitk_partial_kernel_simd` — IDENTICAL online-softmax math,
    IDENTICAL split-range partition, IDENTICAL `(m, l, o)` output contract; only HOW one (head,
    split)'s `d_head`-wide per-key dot product collapses to a scalar differs, and by how much of
    `d_head` one thread owns while doing it.

    HONEST RESULT, STATED FIRST: this kernel is CORRECT (bit-exact-within-Float32-reordering-noise
    against `_splitk_partial_kernel_simd` and an independent host-Float64 reference, worst delta
    2.28e-07 at `n_keys=4000` — see `test_residentk_attn_splitk_native_kernel.mojo`'s own numbers)
    but it is NOT FASTER at `n_splits=16` (this task's own scope, deliberately unchanged) — it is
    measurably, reproducibly SLOWER than the kernel it was meant to improve on, and the regression
    GROWS with depth. GPU-counter measurement (`qwen3_probe_counters_i8_allsimd5_splitk_deepctx.mojo`
    vs. `qwen3_probe_counters_i8_allsimd3_splitk_deepctx.mojo`, identical descriptor plan, identical
    machine, back-to-back, repeated rounds) found this kernel's own `splitk_partial` role costing
    ~1.2ms at `n_keys=50` (a small WIN, ~1.04x, over the two-level kernel's ~1.26ms there) but ~3.0ms
    at `n_keys=500` (~1.3x REGRESSION vs ~2.3ms), ~9.1ms at `n_keys=2000` (~1.9x regression vs
    ~4.7ms), and ~17.8-18.0ms at `n_keys=4000` (~2.3x regression vs the two-level kernel's own
    ~7.6-7.7ms there) — a regression that WIDENS with depth, the opposite shape from the design
    phase's own isolated scratch-probe projection (which measured this exact reduction-shape change
    WINNING, and winning MORE at greater depth: 1.20x at 512, 1.44x at 2000 and 4000, 1.78x at 8000).
    The full-token effect matches the role-level finding, not the projection: a real, teacher-forced
    4096-token generation (`qwen3_generate_batch_i8_allsimd5_longctx_probe.mojo` vs. `_allsimd3_`'s
    own, same checkpoint, same prompt) produced BIT-IDENTICAL token ids at all 4096 positions (zero
    mismatches, max logit delta 3.36e-04, well within this codebase's own established Float32-
    reordering tolerance) but measured 75.6-77.7 decode tok/s against the two-level kernel's own
    114.9-125.7 tok/s over the same run, interleaved, repeated rounds — a real, reproducible ~1.5-1.6x
    SLOWDOWN, not the projected +27% speedup. See MOTIVATION below for why this was tried, and
    CONCLUSION at the end of this docstring for the most likely explanation and what this rules out.
    This kernel remains landed, additive, and unwired from anything the published race depends on —
    an honest, verified null result, matching this codebase's own established practice for a real
    investigation that did not pan out (e.g. `_splitk_partial_kernel_simd_batched4`'s own barrier-
    count finding, or the fp16-KV-cache "zero speedup" finding).

    MOTIVATION: two REAL, installed, independently-implemented opponents on the identical checkpoint/
    prompt (mlx-lm's `sdpa_vector`/`sdpa_vector_2pass_1`; llama.cpp's `kernel_flash_attn_ext_vec`)
    both confine this exact reduction to one 32-lane SIMD-group with zero `threadgroup_barrier` calls,
    and an isolated scratch probe (design phase, not committed) measured this same reduction-shape
    change winning in isolation at `n_splits=16` unchanged — see ROOT CAUSE below for the full
    grounding. The isolated probe's methodology ran the candidate kernel ALONE, back-to-back, nothing
    else competing for the GPU; this kernel's own measurement above is the FIRST time the identical
    change was measured EMBEDDED in the real 199-descriptor, 28-layer, 7-dispatches-per-layer
    pipeline `_MBQwen3I8AllSimd5` (`metaldispatch.session`) actually submits — see that struct's own
    docstring for the harness.

    ROOT CAUSE THIS KERNEL FIXES, grounded in real source, not assumption: `_splitk_partial_kernel_
    simd` (this kernel's unbatched twin, immediately above) launches `block_dim = d_head = 128` — one
    thread per head-dimension scalar — copied byte-for-byte from `_sdpa_kernel_simd`'s own loop body
    per that kernel's docstring. Apple's SIMD-group width (`std.gpu.WARP_SIZE` under `is_apple_gpu()`)
    is 32, so those 128 threads are FOUR separate SIMD-groups, and folding one key's dot product back
    to a single scalar needs a shared-memory publish plus TWO `barrier()` calls per key (one so every
    thread sees the four groups' partial sums, one "safety" barrier so a fast thread cannot race the
    NEXT key's write against a slow thread still reading THIS key's values — see that kernel's own
    docstring, inherited from `_sdpa_kernel_simd`'s, for the full account). Two REAL, installed,
    independently-implemented opponents on the identical checkpoint/prompt (mlx-lm's `sdpa_vector`/
    `sdpa_vector_2pass_1`, `mlx/backend/metal/kernels/sdpa_vector.h`; llama.cpp's `kernel_flash_attn_
    ext_vec`, `ggml-metal.metal:7280`) both confine this exact reduction to ONE 32-lane SIMD-group —
    each lane sums `d_head / WARP_SIZE` elements in registers, one `simd_sum`/`_warp_sum` fold, ZERO
    `threadgroup_barrier` calls anywhere in the per-key loop — where Algenta's kernel is the only one
    of the three built the other way around. `_splitk_partial_kernel_simd_batched4`'s own honest null
    result (this file, directly above) already ruled out "the same expensive barrier, just fewer of
    them" as a fix on this exact hot path; this kernel changes the reduction's SHAPE instead, matching
    both real opponents' own approach rather than retrying a barrier-count tweak on the shape that
    already failed.

    THE CHANGE: `block_dim = WARP_SIZE = 32` — one (head, split) pair is now exactly ONE SIMD-group,
    not four. Each lane owns `d_head / WARP_SIZE` head-dimension elements AT STRIDE `WARP_SIZE` (lane
    `e` owns `{e, e + 32, e + 64, ...}, e < 32` — at this model's `d_head = 128` that is 4 elements
    per lane), pre-loaded into a small per-thread `InlineArray` (register-resident, no shared memory
    at all) once before the key loop, exactly the way `_sdpa_kernel_simd`'s own per-thread `qv` is
    loaded once before ITS key loop, just `d_head / WARP_SIZE` values instead of one. Per key: each
    lane sums its OWN `d_head / WARP_SIZE` partial products in registers, THEN one single-level
    `_warp_sum` — `std.gpu.primitives.warp.sum`, the same butterfly `shuffle_xor` every other single-
    SIMD-group reduction in this file already uses (`_gemv_accum_kernel_simd_i8`'s own docstring has
    the fullest account of why one SIMD group owning one independent unit of work, with NOTHING to
    combine across groups, needs no shared array and no barrier at all) — folds the 32 lane-partials
    to the complete `d_head`-wide dot product, broadcast to every lane in the group. Every lane then
    independently recomputes the SAME online-softmax step (`nm`/`corr`/`w`) from that one broadcast
    scalar — cheap, redundant, register-only work, the same redundancy `_sdpa_kernel_simd`'s own four
    SIMD-groups already each pay for `m`/`denom` today — and folds its OWN `d_head / WARP_SIZE` output
    elements into a register-resident `o` accumulator. ZERO `barrier()` calls anywhere in this kernel,
    not just in the per-key loop: unlike the two-level twin above, there is no shared array at all for
    a "safety" barrier to protect between keys.

    Reproduces the *exact* output of both `_splitk_partial_kernel_simd` (this kernel's two-level twin)
    and an independent host-Float64 reference to within Float32 reordering noise — a pure summation-
    associativity reorder (per-lane partial sums accumulated in a different register order before the
    SAME `_warp_sum` butterfly, not a different set of additions), the same category of change this
    codebase already accepted for the original `_sdpa_kernel_simd` SIMD-shuffle fix and for `_splitk_
    partial_kernel_simd_batched4`'s barrier-batching change. Verified against BOTH at a multi-head,
    multi-depth sweep including ragged (`n_keys` not a multiple of `n_splits`) and `n_splits > n_keys`
    (genuinely empty split) cases in this kernel's own isolated suite, `test_residentk_attn_splitk_
    native_kernel.mojo`, before any production code depends on it — see that file for the numbers.

    GENERALITY GAP, closed by an EXISTING check, not a new one: this kernel's `d_head / WARP_SIZE`
    elements-per-lane mapping needs `d_head` to be a positive multiple of `WARP_SIZE` (a `d_head`
    narrower than one 32-lane warp has no well-defined "elements at stride 32" mapping at all). Every
    session struct that could ever dispatch this kernel inherits `_MBQwen3I8AllSimd3`'s own `__init__`
    refusal — `if d_head % WARP_SIZE != 0: raise Error(...)`, BEFORE any GPU work happens — which
    already rejects exactly the shapes this generality gap would otherwise let through; nothing
    further is needed here specifically because that refusal is already inherited, not because the
    gap does not exist in principle for a kernel used outside that discipline.

    `n_splits` UNCHANGED from `_splitk_partial_kernel_simd`'s own shipped value (16) — this kernel
    fixes the reduction SHAPE only, deliberately isolated from any occupancy/grid-width change, so a
    regression (if any) is attributable to exactly one variable. `_splitk_merge_kernel_simd` (this
    file, above) is reused COMPLETELY UNCHANGED: this kernel writes the identical `(m, l, o)` per-
    (head, split) layout — `m_out[idx]`, `l_out[idx]`, `o_out[idx * d_head + e]` for every `e` in
    `[0, d_head)`, just visited as `lane + i * WARP_SIZE` instead of a single `e = thread_idx.x` — so
    the merge kernel's own per-column read has no way to tell which partial kernel produced its input.

    ADDITIVE ONLY: `_splitk_partial_kernel_simd` (the two-level twin) is byte-unmodified. Must be
    compiled into its OWN binary, never alongside `_splitk_partial_kernel_simd` or `_splitk_partial_
    kernel_simd_batched4` — the same truncated-Metal-AIR-name substring collision `_classify_splitk_
    pipeline`'s own docstring documents for every sibling pair: all three kernel names share the
    `splitk_part` 11-character prefix that survives Metal's name truncation on this target, so two (or
    three) pipelines matching the same role in one binary would collide with no way to tell them apart.

    CONCLUSION, from the measured regression (HONEST RESULT above), widening with depth: the most
    likely explanation is OCCUPANCY, not a bug in the arithmetic (correctness is independently
    verified to Float32-reordering noise, both at the kernel level and across a real 4096-token
    generation). `block_dim = WARP_SIZE` shrinks each threadgroup from 128 threads (4 SIMD-groups) to
    32 (1), so at this task's own deliberately-UNCHANGED `n_splits = 16`, the TOTAL number of warps
    this dispatch puts in flight GPU-wide drops 4x (`h_q * n_splits` warps instead of `h_q * n_splits
    * 4`) for the identical grid width (`h_q * n_splits` threadgroups, unchanged) — each of the
    remaining warps now does 4x the register-resident work per key (4 sequential loads + 4 sequential
    FMAs instead of 1) to make up for it. At shallow `n_keys` (50: near parity, a small real win) that
    trade is roughly even; as `n_keys` grows, each surviving warp issues proportionally MORE
    sequential device-memory loads with 4x FEWER concurrent warps GPU-wide available to hide that
    per-load latency by scheduling other work in the gaps — a classic occupancy-vs-per-thread-work
    trade that gets WORSE, not better, with more iterations per thread, matching the exact "regression
    widens with depth" shape measured. This is also the most likely reason the isolated design-phase
    scratch probe (kernel alone, back-to-back, nothing else competing for the GPU) measured a WIN
    that widened with depth (2.16x at `n_keys=4000` with `n_splits` widened to 64, i.e. occupancy
    RESTORED by recruiting more splits) while this kernel's own embedded measurement — at the SAME
    `n_splits = 16` that isolated table's OWN "n_splits=16" column also used — measured a regression
    that widens with depth instead: an isolated probe with no other GPU work queued may not surface
    an occupancy shortfall a real, 199-descriptor, 28-layer pipeline's own GPU scheduling exposes.
    Per-key barrier elimination alone, WITHOUT recruiting the freed SIMD-groups' worth of parallelism
    back via more splits, is therefore RULED OUT as a standalone win here — exactly the gap the
    design plan's own Candidate 1 (widen `_ATTN_SPLITK_N_SPLITS` to recruit the freed SIMD-groups as
    more key-parallel workers) exists to close, and exactly why that candidate is a SEPARATE,
    subsequent step rather than folded into this one.
    """
    comptime _MAX_PER_LANE: Int = RESIDENT_MAX_HEAD_DIM // WARP_SIZE
    """Upper bound on elements one lane can own, sized off the same `RESIDENT_MAX_HEAD_DIM` ceiling
    `_SIMD_GROUPS` above uses for the identical reason: `d_head` is a runtime value but `InlineArray`
    needs a compile-time size. At this model's `d_head = 128` only the first 4 of these 8 slots are
    ever touched."""
    var idx = Int(block_idx.x)
    var h = idx // n_splits
    var sidx = idx % n_splits
    var lane = lane_id()
    var hk = h // (h_q // h_kv)
    var per_lane = d_head // WARP_SIZE

    var qv = InlineArray[Float32, _MAX_PER_LANE](fill=0.0)
    for i in range(per_lane):
        qv[i] = q_rot[h * d_head + lane + i * WARP_SIZE]

    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = InlineArray[Float32, _MAX_PER_LANE](fill=0.0)

    for j in range(key_start, key_end):
        var kb = (j * h_kv + hk) * d_head
        var partial = Float32(0.0)
        for i in range(per_lane):
            partial += qv[i] * ck[kb + lane + i * WARP_SIZE]
        var s = _warp_sum(partial) * scale

        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        for i in range(per_lane):
            o[i] = o[i] * corr + w * cv[kb + lane + i * WARP_SIZE]
        denom = denom * corr + w
        m = nm

    m_out[idx] = m
    l_out[idx] = denom
    for i in range(per_lane):
        o_out[idx * d_head + lane + i * WARP_SIZE] = o[i]


def _lmhead_argmax_kernel(
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


def _lmhead_argmax_kernel_f16(
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


def _lmhead_argmax_kernel_i8(
    blk_val: _FP, blk_idx: _IP, x: _FP, gamma: _FP, w: _I8P, wscale: _FP,
    k: Int, n: Int, eps: Float32, n_iters: Int,
):
    """The int8-weight twin of `_lmhead_argmax_kernel` — final rmsnorm, the tied lm_head projection
    and the per-threadgroup argmax, with `w` a resident Int8 buffer and `wscale` a per-vocabulary-
    row Float32 scale (`wscale[j]` for vocabulary row `j`, the SAME buffer `_embed_row_kernel_i8`
    reads as `embed_scale` — tying holds for the scale exactly as it does for the table itself).

    This is the SINGLE LARGEST resident matrix in the model — `vocab * d_model`, ~155M elements,
    tied with the embedding table — so it is also where int8 storage buys the most per-token
    bandwidth back: a quarter of the Float32 arm's bytes for this one matrix, an eighth counting
    the fp16 arm as the intermediate step. See `_norm_gemv_kernel_i8` for the widening-and-scaling
    discipline and `_I8P` for why this stays a mixed-precision kernel (Float32 activations and
    accumulator throughout) rather than an all-int8 one.
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
    var k_vec = (k // _VEC_STRIDE_I8) * _VEC_STRIDE_I8

    for it in range(n_iters):
        var j = Int(block_idx.x) * _SUBS + sub + it * stride_cols
        var acc = Float32(0.0)
        if j < n:
            var base = j * k
            var srow = wscale[j]
            var srow_v = SIMD[DType.float32, _VEC_I8](srow)
            var t = lane * _VEC_I8
            while t < k_vec:
                var xv = xs.load[width=_VEC_I8](t)
                var wv = w.load[width=_VEC_I8](base + t).cast[DType.float32]() * srow_v
                var pv = xv * wv
                for lane_e in range(_VEC_I8):
                    acc += pv[lane_e]
                t += _VEC_STRIDE_I8
            var tt = k_vec + lane
            while tt < k:
                acc += xs[tt] * (Float32(w[base + tt]) * srow)
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


def _lmhead_argmax_kernel_simd_i8(
    blk_val: _FP, blk_idx: _IP, x: _FP, gamma: _FP, w: _I8P, wscale: _FP,
    k: Int, n: Int, eps: Float32, n_iters: Int,
):
    """The REDUCTION-MECHANISM twin of `_lmhead_argmax_kernel_i8` — IDENTICAL final rmsnorm, tied
    lm_head projection and per-threadgroup argmax math, only HOW its two internal reductions
    collapse to a scalar differs. Same relationship `_norm_gemv_kernel_simd_i8` has to
    `_norm_gemv_kernel_i8` (see that docstring for the fuller account this one leans on), applied to
    the SAME two reduction shapes PLUS the argmax bookkeeping layered on top of shape 2 — see
    `lmhead_argmax_simd_reduce_probe.mojo` for the device-side confirmation this docstring's claims
    rest on, not assumed. This is the single largest individual dispatch in the whole per-token
    cost (~12-13% of per-token GPU time per PR #510's counters, tied with the embedding table for
    the largest resident matrix in the model), and had never been examined through this lens before.

    `_lmhead_argmax_kernel_i8` has TWO barrier-tree reductions, run `1 + n_iters` times total:

    1. Sum-of-squares over the whole `k`-length vector, reduced across all `_TG = 256` threads —
       run ONCE per launch. EXACTLY the same shape as `_norm_gemv_kernel_simd_i8`'s stage 1: 8 full
       32-lane SIMD-groups on this hardware, confirmed by device probe, not assumed. Fixed
       identically: per-group `_warp_sum` with no barrier (hardware lockstep), one lane per group
       writes its group's total into an `_SUBS`-slot shared array, ONE combine `barrier()` makes
       those writes visible, every thread sums the 8 entries itself. 8 barriers -> 1.

    2. Each output column's dot product, reduced across its own `_LANES = 32`-wide SIMD group —
       run ONCE PER ITERATION of the `for it in range(n_iters)` loop, because this kernel walks the
       WHOLE `n`-row vocabulary in `_SUBS`-column strides (unlike a plain GEMV kernel's single pass
       over one column per thread), `_SUBS = 8` independent columns per iteration, `log2(32) = 5`
       barrier-synchronized halving levels PER ITERATION, plus ONE trailing "safety" `barrier()`
       the ORIGINAL kernel pays per iteration that exists ONLY to stop a fast thread from starting
       the next iteration's `red[tid] = acc` write before every thread in its group has finished
       reading `red[]` for the CURRENT iteration's argmax update — `6` barriers/iteration, `6 *
       n_iters` total for this stage alone.

       This shape is the SAME one `_gemv_accum_kernel_simd_i8`'s own per-column stage already
       fixed: one SIMD group maps 1:1 to one output column with NOTHING to combine across groups,
       so a single-level `_warp_sum` — no shared array, no barrier at all — IS the complete
       reduction, broadcasting the column's total to every lane in the group so `lane == 0` can
       compare it against its own LOCAL `best`/`best_i` registers directly, with no shared memory
       touched anywhere in this stage. Because `red[]` is never written or read here, the trailing
       safety barrier the tree version needs has nothing left to guard either — verified by reading
       every use of `red[]`/`best`/`best_i` in `_lmhead_argmax_kernel_i8`: `best`/`best_i` are
       per-thread registers, updated every iteration and only ever read back by the SAME thread on
       a LATER iteration or after the loop; `sv`/`si` (the only place `best`/`best_i` reach shared
       memory) are written exactly once, AFTER the full `it` loop ends. No iteration of this stage
       depends on any other iteration's shared-memory state, so removing every barrier from it —
       not just the 5 tree levels, but the 6th trailing one too — changes nothing about what gets
       read. `6 * n_iters` barriers -> `0`.

    `8 + 6 * n_iters` barriers collapse to `1` per launch. Every other line — the normalization
    arithmetic, the int8 dequantization (`Float32(i8) * wscale[row]`, inside the loop, immediately
    on load), the vectorized `char4`-shaped load, the per-column argmax bookkeeping and its
    tie-break (lowest `id` wins — unchanged: `lane == 0`'s `if total > best` is still a strict `>`,
    evaluated in the same `it` order, so an exact tie still resolves the same way it did against
    `red[sub * _LANES]`), and the final per-threadgroup combine over `sv`/`si` — is copied
    byte-for-byte from `_lmhead_argmax_kernel_i8`, because the math this kernel computes must be,
    and is verified to be, IDENTICAL; only the summation order across lanes/groups (and which
    barriers that reordering makes unnecessary) differs.
    """
    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var grp = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var sv = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var si = stack_allocation[_SUBS, DType.int32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    # ── 1. sum of squares over the whole vector, two-level SIMD-shuffle reduced ──
    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    var ss_group = _warp_sum(ss)
    if lane == 0:
        grp[sub] = ss_group
    barrier()
    var ss_total = Float32(0.0)
    for g in range(_SUBS):
        ss_total += grp[g]
    var inv = 1.0 / sqrt(ss_total / Float32(k) + eps)

    # ── 2. stage the normalized, gamma-scaled vector in threadgroup memory ──────
    var st0 = tid
    while st0 < k:
        xs[st0] = x[st0] * inv * gamma[st0]
        st0 += _TG
    barrier()

    # ── 3. one SIMD group per output column, single-level SIMD-shuffle reduction, no barrier at
    # all across the whole `it` loop -- `red[]` is gone entirely, `best`/`best_i` are registers ──
    var stride_cols = Int(grid_dim.x) * _SUBS
    var best = _NEG_HUGE
    var best_i = Int32(-1)
    var k_vec = (k // _VEC_STRIDE_I8) * _VEC_STRIDE_I8

    for it in range(n_iters):
        var j = Int(block_idx.x) * _SUBS + sub + it * stride_cols
        var acc = Float32(0.0)
        if j < n:
            var base = j * k
            var srow = wscale[j]
            var srow_v = SIMD[DType.float32, _VEC_I8](srow)
            var t = lane * _VEC_I8
            while t < k_vec:
                var xv = xs.load[width=_VEC_I8](t)
                var wv = w.load[width=_VEC_I8](base + t).cast[DType.float32]() * srow_v
                var pv = xv * wv
                for lane_e in range(_VEC_I8):
                    acc += pv[lane_e]
                t += _VEC_STRIDE_I8
            var tt = k_vec + lane
            while tt < k:
                acc += xs[tt] * (Float32(w[base + tt]) * srow)
                tt += _LANES
        var total = _warp_sum(acc)
        if lane == 0 and j < n:
            if total > best:
                best = total
                best_i = Int32(j)

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


def _argmax_reduce_kernel(out_val: _FP, out_idx: _IP, blk_val: _FP, blk_idx: _IP, n: Int):
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


def _argmax_reduce_kernel_simd(out_val: _FP, out_idx: _IP, blk_val: _FP, blk_idx: _IP, n: Int):
    """The REDUCTION-MECHANISM twin of `_argmax_reduce_kernel` — IDENTICAL per-thread grid-stride
    local-best scan over `blk_val`/`blk_idx` and IDENTICAL tie-break-to-lowest-id convention; only
    HOW the `_TG=256`-wide combine collapses every thread's local `(best, best_i)` pair to one final
    scalar differs. `grid_dim=1`, `block_dim=256`, unchanged — this is the single-threadgroup
    dispatch that collapses `_lmhead_argmax_kernel`'s `_LM_BLOCKS=2048` per-threadgroup `(logit, id)`
    pairs down to the one pair the host reads as 8 bytes.

    LAST kernel in the decode path's reduction-mechanism sweep PR #510 named, and the smallest:
    PR #510's GPU-counter measurement put this dispatch at roughly 0.3-0.4% of per-token GPU time
    (against `_sdpa_kernel`'s 26.85%, PR #513, or `_lmhead_argmax_kernel_i8`'s 12-13%, PR #515) — it
    was deliberately skipped when PR #515 landed the lm_head fix, on the grounds that
    `std.gpu.primitives.warp` exposes `sum` (every other kernel in this sweep uses it) but no paired
    argmax primitive: nothing that reduces a `(value, index)` pair TOGETHER the way a bare `sum`
    reduces a scalar. Landing this one anyway completes the sweep rather than leaving a single
    deliberately-unexamined barrier tree in an otherwise fully-audited decode path — the measurable
    effect is expected to be within run-to-run noise at this dispatch's share of total time, and is
    reported as such, not oversold.

    THE GAP, AND HOW IT CLOSES: `std.gpu.primitives.warp.shuffle_xor` (imported here as
    `_shuffle_xor`) IS directly importable and DOES support a hand-rolled compare-exchange
    butterfly — confirmed by direct compilation and an on-device probe before this kernel was
    written (see `argmax_reduce_simd_reduce_probe.mojo`, which checks both the same butterfly in
    isolation AND an explicit two-lanes-tied-different-ids case, lowest id winning, matching
    `numpy.argmax`'s convention). Calling `_shuffle_xor` once for `best` (Float32) and once for
    `best_i` (Int32) at the SAME `offset`, in the SAME butterfly step, then comparing the two
    shuffled-in values against the calling lane's own `best`/`best_i` with the IDENTICAL tie-break
    clause `_argmax_reduce_kernel`'s own tree reduction uses, reduces one 32-lane SIMD group to its
    own argmax winner — replicated to EVERY lane in the group (an all-reduce: every lane runs the
    SAME 5 steps, `offset = 16, 8, 4, 2, 1`, `log2(32)`, so every lane ends the loop holding the
    group's own winner, no different from `warp.sum`'s own broadcast-to-all-lanes behaviour). No
    barrier anywhere in this stage — SIMD-group execution is lockstep by hardware construction, the
    same fact every other `_simd` kernel in this file rests on.

    Two-level combine, the same shape `_lmhead_argmax_kernel_simd_i8`'s own stage 1 uses: level 1 is
    the 5-step lane-butterfly above; level 2 combines the `_SUBS = 8` per-group winners through a
    `_SUBS`-slot shared array with exactly ONE barrier (so every thread sees every group's write),
    then thread 0 ALONE walks all 8 entries with the SAME tie-break clause a third time and writes
    the final `(value, id)` pair — mirroring `_lmhead_argmax_kernel`'s own final `sv`/`si` combine
    over its `_SUBS` sub-groups, one level up, rather than reusing its 256-wide argmax loop, which
    would need the write-visibility barrier this kernel's `warp` version instead avoids by keeping
    `best`/`best_i` in registers until the single group-level write. `log2(256) = 8`
    barrier-synchronized halving levels plus the original kernel's own leading write-visibility
    barrier — 9 barrier hits total — collapse to 1.

    Ties resolve to the LOWEST id, exactly as `_argmax_reduce_kernel`'s own docstring requires: all
    three tie-break sites here (the per-thread grid-stride scan above this docstring, the 5-step
    butterfly, and the final 8-way scalar combine) use the SAME clause —
    `other_val > best or (other_val == best and other_idx >= 0 and (best_i < 0 or other_idx < best_i))`
    — so an exact value tie resolves identically no matter which lane, which SIMD group, or which
    reduction MECHANISM produced the competing entries. The `other_idx >= 0` / `best_i < 0` guards
    exist for the same degenerate reason `_argmax_reduce_kernel`'s own docstring flags: a SIMD group
    (or, in the original, a stride level) whose every entry is the `_NEG_HUGE`/`-1` sentinel — because
    `n` left it with no valid `blk_val`/`blk_idx` entry at all — must not appear to "tie" a real
    winner just because `_NEG_HUGE == _NEG_HUGE`.
    """
    var grp_v = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var grp_i = stack_allocation[_SUBS, DType.int32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    var best = _NEG_HUGE
    var best_i = Int32(-1)
    var i = tid
    while i < n:
        if blk_val[i] > best:
            best = blk_val[i]
            best_i = blk_idx[i]
        i += _TG

    var off = UInt32(_LANES // 2)
    while off > 0:
        var other_val = _shuffle_xor(best, off)
        var other_idx = _shuffle_xor(best_i, off)
        if other_val > best or (other_val == best and other_idx >= 0 and (best_i < 0 or other_idx < best_i)):
            best = other_val
            best_i = other_idx
        off //= 2

    if lane == 0:
        grp_v[sub] = best
        grp_i[sub] = best_i
    barrier()

    if tid == 0:
        var bv = grp_v[0]
        var bi = grp_i[0]
        for u in range(1, _SUBS):
            var other_val = grp_v[u]
            var other_idx = grp_i[u]
            if other_val > bv or (other_val == bv and other_idx >= 0 and (bi < 0 or other_idx < bi)):
                bv = other_val
                bi = other_idx
        out_val[0] = bv
        out_idx[0] = bi


# ============================================================================================
# BATCHED PREFILL KERNELS -- an EIGHTH, structurally different axis from the seven weight-storage/
# KV-cache-precision/reduction-mechanism/grid-size axes documented at the top of this file. Those
# seven all batch NOTHING: every one of them still processes exactly ONE new token per dispatch,
# the shape this whole file's fusion table was designed around. The kernels below process `m_rows`
# NEW tokens per dispatch instead of one -- built for prefill (prompt processing), where the whole
# prompt is already known up front and the per-token dispatch-submission floor this file's own
# module docstring names (`~180 us of host submission ... per dispatch, with no overlap`) is exactly
# what a `for t in range(n_prompt): step(...)` loop would pay per PROMPT TOKEN, not per generated
# token -- fatal once a prompt is hundreds of tokens long (see `metaldispatch.session_prefill`'s own
# module docstring for the measured gap this addresses).
#
# EVERY kernel below is a ROW-FLATTENED twin of an existing, already-verified single-row kernel:
# the per-row MATH is copied byte-for-byte from that kernel's own body (same normalization, same
# int8 dequantization, same reduction shape, same online-softmax recurrence); the ONLY change is
# that `block_idx.x` now flattens `(unit, m)` -- `m` selects which of the `m_rows` prefill rows this
# threadgroup computes, `unit` is that row's OWN original grid index -- and every buffer read/write
# gains a `row * stride` offset selecting row `m`'s own slice. Two rows never share a threadgroup and
# never touch each other's shared memory (shared memory is per-threadgroup, not global), so each
# row's own computation is exactly as independent as `m_rows` separate single-row dispatches would
# have been -- the correctness gate every kernel below is checked against (`test_residentk_prefill_
# kernels.mojo`) diffs against exactly that: `m_rows` independent calls to the existing single-row
# twin, not a restated formula.
#
# Every new kernel's base name starts with `pf_` -- verified DIRECTLY (not merely by inspection of
# the Mojo source names) to survive Metal's AIR truncation with a unique, mutually-distinct, 11-
# characters-or-fewer visible prefix, colliding with none of `_classify_pipeline`'s eight patterns
# nor `_classify_splitk_pipeline`'s two, via `benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_
# prefill_naming.mojo` (compiled with placeholder bodies temporarily added here, run for real,
# confirmed, then reverted before these real bodies replaced them) -- the same throwaway-probe-then-
# real-body sequencing `_classify_splitk_pipeline`'s own docstring documents using to catch two real
# collisions before landing. `metaldispatch.session._classify_prefill_pipeline` is the new
# classifier these six names resolve through, a separate function from `_classify_pipeline`/
# `_classify_splitk_pipeline` for the identical reason those two are already separate from each
# other (folding a new role into `_N_ROLES` would force every OTHER struct in `metaldispatch.session`
# to start demanding a pipeline it never compiles).
#
# ATTENTION IS NOT LIKE THE OTHER FIVE: `_pf_attn_tiled_kernel_simd` below computes at `br = 1`
# (one query row per threadgroup, exactly like every other kernel in this family) for Phase 1 --
# flattened into ONE dispatch across every row, never a per-row loop, so its own cost is measured
# as a single dispatch at every `m_rows` this build is raced at. Whether a REAL register-blocked,
# multiple-queries-per-thread BR-tiled version (`br > 1`, reusing each streamed key across several
# query rows) is needed at all is Phase 1's OWN measurement question, decided from a real GPU-
# counter probe, not assumed from the FLOP table alone -- see the implementation plan's own "Phase
# 1's own measurement decides Phase 2" section. This Phase-1 body is deliberately the SAME kernel
# Phase 2 would extend in place, not a throwaway.
# ============================================================================================


def _pf_embed_rows_kernel_i8(
    hidden: _FP, embed: _I8P, embed_scale: _FP, token_ids: _IP, d_model: Int, m_rows: Int
):
    """Batched twin of `_embed_row_kernel_i8` -- gathers `m_rows` embedding rows in ONE dispatch
    instead of one dispatch per row. `grid_dim = ceil_div(d_model, _TG) * m_rows`; `block_idx.x`
    flattens `(unit, m)` as `unit = block_idx.x % n_units`, `m = block_idx.x // n_units`
    (`n_units = ceil_div(d_model, _TG)`) -- the SAME flattening convention every kernel in this
    family uses. `token_ids` is a resident Int32 buffer of `m_rows` prompt token ids, uploaded once
    per `prefill_batch()` call: a decode step's single `token_id` was always a plain scalar kernel
    argument, but a BATCH of them needs a buffer, since a Metal dispatch's scalar arguments are fixed
    at descriptor-BUILD time (`metaldispatch.ffi._mb_set_arg_int`), not re-suppliable per row within
    one dispatch. `hidden` is `[m_rows, d_model]` row-major -- row `m` is exactly what
    `_embed_row_kernel_i8` would have written for token `token_ids[m]`, independent of every other
    row.
    """
    var n_units = (d_model + _TG - 1) // _TG
    var unit = Int(block_idx.x) % n_units
    var m = Int(block_idx.x) // n_units
    if m >= m_rows:
        return
    var i = unit * _TG + Int(thread_idx.x)
    if i < d_model:
        var token_id = Int(token_ids[m])
        var s = embed_scale[token_id]
        hidden[m * d_model + i] = Float32(embed[token_id * d_model + i]) * s


def _pf_qkv_proj_kernel_simd_i8(
    y: _FP, x: _FP, gamma: _FP, w: _I8P, wscale: _FP, k: Int, n: Int, eps: Float32, m_rows: Int
):
    """Batched twin of `_norm_gemv_kernel_simd_i8` -- IDENTICAL per-row rmsnorm+QKV-projection math
    and IDENTICAL two-level SIMD-shuffle reduction (see that kernel's own docstring for the full
    account this one leans on), computed independently for `m_rows` rows in ONE dispatch instead of
    `m_rows` separate dispatches. `grid_dim = ceil_div(n, _SUBS) * m_rows`; `block_idx.x` flattens
    `(unit, m)` the same way `_pf_embed_rows_kernel_i8` does. `x` is `[m_rows, k]` row-major (row `m`
    is prefill row `m`'s post-embedding hidden state); `y` is `[m_rows, n]` -- row `m`'s own,
    completely independent rmsnorm-then-projection result, with NOTHING shared across rows (the
    sum-of-squares normalization is over row `m`'s own `k` elements only, exactly as if
    `_norm_gemv_kernel_simd_i8` had been called `m_rows` separate times on `m_rows` separate single
    rows -- the oracle this kernel's own correctness gate diffs against).
    """
    var n_units = (n + _SUBS - 1) // _SUBS
    var unit = Int(block_idx.x) % n_units
    var m = Int(block_idx.x) // n_units
    if m >= m_rows:
        return
    var row_x = m * k
    var row_y = m * n

    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var grp = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[row_x + i]
        ss += v * v
        i += _TG
    var ss_group = _warp_sum(ss)
    if lane == 0:
        grp[sub] = ss_group
    barrier()
    var ss_total = Float32(0.0)
    for g in range(_SUBS):
        ss_total += grp[g]
    var inv = 1.0 / sqrt(ss_total / Float32(k) + eps)

    var s = tid
    while s < k:
        xs[s] = x[row_x + s] * inv * gamma[s]
        s += _TG
    barrier()

    var j = unit * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var base = j * k
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC_I8](srow)
        var k_vec = (k // _VEC_STRIDE_I8) * _VEC_STRIDE_I8
        var t = lane * _VEC_I8
        while t < k_vec:
            var xv = xs.load[width=_VEC_I8](t)
            var wv = w.load[width=_VEC_I8](base + t).cast[DType.float32]() * srow_v
            var pv = xv * wv
            for lane_e in range(_VEC_I8):
                acc += pv[lane_e]
            t += _VEC_STRIDE_I8
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
            tt += _LANES
    var total = _warp_sum(acc)
    if lane == 0 and j < n:
        y[row_y + j] = total


def _pf_ropewrt_kernel(
    q_rot: _FP, ck: _FP, cv: _FP, qkv: _FP, qn_w: _FP, kn_w: _FP,
    cos_t: _FP, sin_t: _FP, pos_base: Int, h_q: Int, h_kv: Int, d_head: Int, eps: Float32, m_rows: Int,
):
    """Batched twin of `_qk_rope_write_kernel` -- IDENTICAL per-row q_norm/k_norm/RoPE math and
    IDENTICAL in-place KV-cache write, computed independently for `m_rows` prefill rows in ONE
    dispatch. `grid_dim = (h_q + h_kv) * m_rows`; `block_idx.x` flattens `(b, m)` as
    `n_units = h_q + h_kv`, `b = block_idx.x % n_units`, `m = block_idx.x // n_units`. Row `m`'s
    absolute cache position is `pos_base + m` -- the SAME absolute-position addressing `ck`/`cv`
    already use for decode's single-token `step()`, so this dispatch writes exactly the slots
    `[pos_base, pos_base + m_rows)` a subsequent `step()` call on the same session reads back from,
    with no cache-layout change at all. `q_rot` becomes `[m_rows, h_q * d_head]` row-major (one row
    per prefill position) instead of decode's single-row buffer -- the batched attention dispatch
    immediately after this one reads it row-by-row.
    """
    var n_units = h_q + h_kv
    var b = Int(block_idx.x) % n_units
    var m = Int(block_idx.x) // n_units
    if m >= m_rows:
        return
    var pos = pos_base + m
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var row_qkv = m * n_qkv
    var n_q = h_q * d_head
    var row_q_rot = m * n_q

    var xs = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var red = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var e = Int(thread_idx.x)
    var is_q = b < h_q
    var head = b if is_q else b - h_q

    var src_off = row_qkv + (head * d_head + e if is_q else (h_q + head) * d_head + e)
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
            var qb = row_q_rot + head * d_head
            q_rot[qb + e] = o0
            q_rot[qb + e + n_pairs] = o1
        else:
            var kb = (pos * h_kv + head) * d_head
            ck[kb + e] = o0
            ck[kb + e + n_pairs] = o1

    if not is_q:
        cv[(pos * h_kv + head) * d_head + e] = qkv[row_qkv + (h_q + h_kv + head) * d_head + e]


def _pf_attn_tiled_kernel_simd(
    attn_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    pos_base: Int, h_q: Int, h_kv: Int, d_head: Int, scale: Float32, m_rows: Int,
):
    """Phase-1 batched twin of `_sdpa_kernel_simd` -- IDENTICAL per-key online-softmax math and
    IDENTICAL two-level SIMD-shuffle reduction (see that kernel's own docstring for the full
    account), flattened into ONE dispatch across `m_rows` prefill rows instead of one dispatch per
    row -- never a literal per-row loop, so this kernel's own cost is measured once, as ONE
    dispatch, at every `m_rows` this Phase-1 build is raced at (the FLOP-share-vs-GPU-time-share
    check the implementation plan's own Phase 1 measurement step runs before Phase 2 is ever
    started). `grid_dim = h_q * m_rows`; `block_idx.x` flattens `(h, m)` as `h = block_idx.x % h_q`,
    `m = block_idx.x // h_q`. Row `m` is query position `pos_base + m`; CAUSAL by construction, not
    by an explicit mask: row `m` computes its own `n_keys = pos_base + m + 1` and its per-key loop
    reads exactly `[0, n_keys)`, the identical "n_keys = pos + 1 is the whole mask" contract
    `_sdpa_kernel`'s own docstring establishes for decode, extended to a per-row `pos`. `q_rot`/
    `attn_out` are `[m_rows, h_q * d_head]` row-major -- the batched `_pf_ropewrt_kernel` dispatch
    immediately before this one has already written EVERY row's K/V into `ck`/`cv` at their own
    absolute positions `[pos_base, pos_base + m_rows)`, so row `m`'s causal loop reading keys
    `[0, n_keys)` never reaches a slot written by a LATER row (`n_keys = pos_base + m + 1` stops
    exactly at row `m`'s own slot), and correctly DOES reach every slot written by an earlier
    `step()`/`prefill_batch()` call on this same session -- exactly the keys row `m` is supposed to
    attend to.
    """
    comptime _SIMD_GROUPS: Int = RESIDENT_MAX_HEAD_DIM // WARP_SIZE
    var grp = stack_allocation[_SIMD_GROUPS, DType.float32, address_space = AddressSpace.SHARED]()
    var n_q = h_q * d_head
    var h = Int(block_idx.x) % h_q
    var m = Int(block_idx.x) // h_q
    if m >= m_rows:
        return
    var n_keys = pos_base + m + 1
    var e = Int(thread_idx.x)
    var hk = h // (h_q // h_kv)
    var qv = q_rot[m * n_q + h * d_head + e]
    var lane = lane_id()
    var grp_id = warp_id()
    var n_groups = d_head // WARP_SIZE

    var mx = _NEG_HUGE
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

        var nm = mx if mx > s else s
        var corr = exp(mx - nm)
        var w = exp(s - nm)
        o = o * corr + w * cv[kb + e]
        denom = denom * corr + w
        mx = nm

    attn_out[m * n_q + h * d_head + e] = o / denom


def _pf_gemv_accum_kernel_simd_i8(y: _FP, x: _FP, w: _I8P, wscale: _FP, k: Int, n: Int, m_rows: Int):
    """Batched twin of `_gemv_accum_kernel_simd_i8` -- IDENTICAL projection-plus-residual-`+=` math
    and IDENTICAL single-level SIMD-shuffle reduction, computed independently for `m_rows` rows in
    ONE dispatch. Reused for BOTH `o_proj` (`k = h_q * d_head`, `n = d_model`) and `down_proj`
    (`k = d_ff`, `n = d_model`) exactly as its single-row twin already is by
    `metaldispatch.session_prefill`'s own descriptor plan -- see that module's docstring."""
    var n_units = (n + _SUBS - 1) // _SUBS
    var unit = Int(block_idx.x) % n_units
    var m = Int(block_idx.x) // n_units
    if m >= m_rows:
        return
    var row_x = m * k
    var row_y = m * n

    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var s = tid
    while s < k:
        xs[s] = x[row_x + s]
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = unit * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var base = j * k
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC_I8](srow)
        var k_vec = (k // _VEC_STRIDE_I8) * _VEC_STRIDE_I8
        var t = lane * _VEC_I8
        while t < k_vec:
            var xv = xs.load[width=_VEC_I8](t)
            var wv = w.load[width=_VEC_I8](base + t).cast[DType.float32]() * srow_v
            var pv = xv * wv
            for lane_e in range(_VEC_I8):
                acc += pv[lane_e]
            t += _VEC_STRIDE_I8
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
            tt += _LANES
    var total = _warp_sum(acc)
    if lane == 0 and j < n:
        y[row_y + j] = y[row_y + j] + total


def _pf_swiglu_kernel_simd_i8(
    act: _FP, x: _FP, gamma: _FP, w: _I8P, wscale: _FP, k: Int, n_ff: Int, eps: Float32, m_rows: Int
):
    """Batched twin of `_norm_gemv2_swiglu_kernel_simd_i8` -- IDENTICAL per-row rmsnorm/gate/up/
    SwiGLU math and IDENTICAL reduction shapes (see that kernel's own docstring), computed
    independently for `m_rows` rows in ONE dispatch."""
    var n_units = (n_ff + _SUBS - 1) // _SUBS
    var unit = Int(block_idx.x) % n_units
    var m = Int(block_idx.x) // n_units
    if m >= m_rows:
        return
    var row_x = m * k
    var row_act = m * n_ff

    var xs = stack_allocation[_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var grp = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var gsh = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[row_x + i]
        ss += v * v
        i += _TG
    var ss_group = _warp_sum(ss)
    if lane == 0:
        grp[sub] = ss_group
    barrier()
    var ss_total = Float32(0.0)
    for g in range(_SUBS):
        ss_total += grp[g]
    var inv = 1.0 / sqrt(ss_total / Float32(k) + eps)

    var s = tid
    while s < k:
        xs[s] = x[row_x + s] * inv * gamma[s]
        s += _TG
    barrier()

    var j = unit * _SUBS + sub
    var k_vec = (k // _VEC_STRIDE_I8) * _VEC_STRIDE_I8

    var acc = Float32(0.0)
    if j < n_ff:
        var base = j * k
        var srow = wscale[j]
        var srow_v = SIMD[DType.float32, _VEC_I8](srow)
        var t = lane * _VEC_I8
        while t < k_vec:
            var xv = xs.load[width=_VEC_I8](t)
            var wv = w.load[width=_VEC_I8](base + t).cast[DType.float32]() * srow_v
            var pv = xv * wv
            for lane_e in range(_VEC_I8):
                acc += pv[lane_e]
            t += _VEC_STRIDE_I8
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * (Float32(w[base + tt]) * srow)
            tt += _LANES
    var gate_total = _warp_sum(acc)
    if lane == 0:
        gsh[sub] = gate_total
    barrier()

    var acc2 = Float32(0.0)
    if j < n_ff:
        var base2 = (n_ff + j) * k
        var srow2 = wscale[n_ff + j]
        var srow2_v = SIMD[DType.float32, _VEC_I8](srow2)
        var t2 = lane * _VEC_I8
        while t2 < k_vec:
            var xv2 = xs.load[width=_VEC_I8](t2)
            var wv2 = w.load[width=_VEC_I8](base2 + t2).cast[DType.float32]() * srow2_v
            var pv2 = xv2 * wv2
            for lane_e2 in range(_VEC_I8):
                acc2 += pv2[lane_e2]
            t2 += _VEC_STRIDE_I8
        var tt2 = k_vec + lane
        while tt2 < k:
            acc2 += xs[tt2] * (Float32(w[base2 + tt2]) * srow2)
            tt2 += _LANES
    var up_total = _warp_sum(acc2)
    if lane == 0 and j < n_ff:
        var g = gsh[sub]
        act[row_act + j] = (g / (1.0 + exp(-g))) * up_total


# ============================================================================================
# WEIGHT-STATIONARY TILED GEMM, Phase A -- the GPU-counter measurement of the batched-prefill
# kernels above (`qwen3_probe_counters_i8_allsimd7_prefill.mojo`) found the four GEMV-shaped roles
# (`_pf_qkv_proj_kernel_simd_i8`, `_pf_gemv_accum_kernel_simd_i8`, `_pf_swiglu_kernel_simd_i8`) at
# 86-90% of GPU time at every M tested, NOT attention. Root cause: row-flattening (the family above)
# cuts DISPATCH COUNT but not MEMORY TRAFFIC -- each of the M rows is still an independent GEMV, a
# separate threadgroup per (output-tile, row) re-reading the SAME weight bytes from device memory
# with zero reuse across rows. The kernels below fix that: each threadgroup loads a slice of BOTH
# operands into shared memory ONCE and reuses it across a whole BM x BN output tile, each thread
# owning a TM x TN register block -- the same register-tiling STRATEGY `accel.gemm_metal.
# _tiled_gemm_kernel` already measures a 7.5x win from on this exact GPU (268 -> 2018 GFLOP/s at a
# 2048-cube), adapted here for: int8 dequantized weights (per-output-row scale, exactly this file's
# own existing GEMV kernels' scheme), the `[out, in]` weight layout this file's own module docstring
# establishes (the TRANSPOSE of `gemm_metal`'s own `[K, N]`-row-major `B` operand -- copying that
# kernel's cooperative-load indexing literally would de-coalesce every weight read, the exact 10x
# loss this file's own layout section already measured once for a different kernel), and this
# repo's own 1D-descriptor shim (`metaldispatch.ffi`'s `AlgentaDispatchDesc` has `grid_x`/`threads_x`
# only, no `grid_y` -- `block_idx.x` below flattens `(tile_row, tile_col)` the same way every other
# kernel in this file's `_pf_*` family already flattens `(unit, m)`).
#
# PHASE A SCOPE: qkv_proj only, at ONE hand-picked tile config (`_GEMM_BM=32, _GEMM_BN=32,
# _GEMM_BK=16, _GEMM_TM=2, _GEMM_TN=2` -- `accel.gemm_metal`'s own measured-best for a same-GPU,
# different-shape, different-dtype kernel; a reasonable STARTING point, explicitly NOT yet the
# calibrated choice for THIS shape -- see the implementation plan's own "Calibration methodology"
# section for the real sweep that decides whether this config, a different single config, or a
# policy-selected family of configs actually ships). `_pf_qkv_proj_kernel_simd_i8` above stays
# byte-unmodified -- it is the Gate-0 oracle `_pf_gemm_assign_kernel_i8` is diffed against
# (`test_residentk_prefill_gemm_kernels.mojo`), not a duplicate to delete.
# ============================================================================================

comptime _GEMM_BM: Int = 32
comptime _GEMM_BN: Int = 32
comptime _GEMM_BK: Int = 16
comptime _GEMM_TM: Int = 2
comptime _GEMM_TN: Int = 2
comptime _GEMM_NTHREADS: Int = (_GEMM_BM // _GEMM_TM) * (_GEMM_BN // _GEMM_TN)
"""The WIDE tile config -- see this section's own module comment. `_GEMM_NTHREADS = 256`, matching
`_TG` (not imported as the same symbol on purpose: `_TG` is this file's GEMV-shaped kernels' own
per-threadgroup thread count, a coincidence of both landing on 256, not a shared constraint -- the
GEMM tile's thread count is DERIVED from `_GEMM_BM/_GEMM_TM * _GEMM_BN/_GEMM_TN`, `_TG`'s is not).

MEASURED, NOT ASSUMED to be universally good: real end-to-end runs on the actual Qwen3-0.6B-Base
checkpoint found this config a real win at `m_rows=256` (1165 tok/s, against the row-flattened
family's own 558.9) but a real REGRESSION at `m_rows=5` (91.6 tok/s, against that SAME row-flattened
family's ~558.9-tok/s-implying per-token cost at short prompts) -- a `BM=32` tile is mostly zero-
padding when `m_rows` is a fraction of 32, and every GEMM-shaped role now pays that waste. See
`_GEMM_BM_NARROW`'s own docstring for the second, small-`m_rows`-oriented config this measurement
motivated, and `residentk.contract.residentk_prefill_gemm_use_narrow_tile` for the policy that
picks between them."""

comptime _GEMM_BM_NARROW: Int = 8
comptime _GEMM_TM_NARROW: Int = 1
comptime _GEMM_NTHREADS_NARROW: Int = (_GEMM_BM_NARROW // _GEMM_TM_NARROW) * (_GEMM_BN // _GEMM_TN)
"""The NARROW tile config -- same `_GEMM_BN`/`_GEMM_BK`/`_GEMM_TN` as the wide config (only the
ROW-tile dimension changes, since `m_rows` -- not `n` or `k` -- is the axis that swings 64x across
this arm's own real race points, 8 to 512), `BM=8` instead of 32, `TM=1` instead of 2 (each thread
now owns one row's worth of register accumulator instead of two, matching the narrower tile).
MEASURED, NOT ASSUMED: real end-to-end runs found this config real relief at `m_rows=5` (110.1
tok/s against the wide config's 91.6) but a real REGRESSION at `m_rows=256` (783.3 tok/s against
the wide config's 1165) -- confirming NEITHER config is good across the whole range, the exact
"let the data decide single-vs-multi-variant" outcome the implementation plan's own calibration
methodology anticipated as a real possibility, not a certainty. Compiled as three separate kernel
functions below (`_pf_gnrw_assign_kernel_i8`/`_pf_gnrw_accum_kernel_i8`/`_pf_gnrw_
swiglu_kernel_i8`), named to diverge from their wide twins WITHIN the 11-character truncation
window (`pf_gnrw_ass`/`pf_gnrw_acc`/`pf_gnrw_swi` vs `pf_gemm_ass`/`pf_gemm_acc`/`pf_gemm_swi` --
the OBVIOUS `_pf_gemm_*_narrow` naming was tried first and rejected here, before landing, precisely
because the `_narrow` suffix falls AFTER the 11-character survivor boundary and both variants would
truncate identically) -- exactly the same "multiple pre-compiled variants selected by a calibrated
runtime policy" pattern this file already uses for `_sdpa_kernel_simd` vs `_splitk_partial_kernel_
simd_native` vs `_splitk_partial_kernel_simd_batched4`."""


def _pf_rmsnorm_rows_kernel(xn: _FP, x: _FP, gamma: _FP, k: Int, eps: Float32, m_rows: Int):
    """Batched RMSNorm + gamma over `m_rows` independent rows, writing the normalized result to a
    SEPARATE device buffer (`xn`) rather than keeping it in threadgroup-shared memory the way every
    fused GEMV kernel above does -- this kernel's whole purpose is to make that normalized row
    available to a LATER, separate tiled-GEMM dispatch, not to a same-dispatch reduction.

    `grid_dim = m_rows`, `block_dim = _TG` -- one threadgroup per row, the SAME two-level SIMD-
    shuffle sum-of-squares reduction `_norm_gemv_kernel_simd_i8`'s own docstring establishes (8 full
    32-lane SIMD-groups at `_TG=256`, one `_warp_sum` per group, one combining `barrier()`), copied
    byte-for-byte for that stage since the math is identical; only the final store differs (to
    device memory, not `stack_allocation`).
    """
    var grp = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var m = Int(block_idx.x)
    if m >= m_rows:
        return
    var row = m * k
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[row + i]
        ss += v * v
        i += _TG
    var ss_group = _warp_sum(ss)
    if lane == 0:
        grp[sub] = ss_group
    barrier()
    var ss_total = Float32(0.0)
    for g in range(_SUBS):
        ss_total += grp[g]
    var inv = 1.0 / sqrt(ss_total / Float32(k) + eps)

    var s = tid
    while s < k:
        xn[row + s] = x[row + s] * inv * gamma[s]
        s += _TG


def _pf_gemm_assign_kernel_i8(y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int, k: Int, n: Int):
    """Weight-stationary tiled GEMM: `y[M,n] = xn[M,k] @ W^T[k,n]`, `w` stored `[n,k]` row-major
    (one output row's `k` coefficients contiguous). See this section's own module comment for the
    strategy this adapts from `accel.gemm_metal._tiled_gemm_kernel` and why the weight-tile
    cooperative load below is NOT that kernel's own indexing, copied.

    `block_idx.x` flattens `(tile_row, tile_col)`: `n_tile_cols = ceil(n / _GEMM_BN); tile_col =
    block_idx.x % n_tile_cols; tile_row = block_idx.x // n_tile_cols`. `b_tile` is stored `[BN, BK]`
    (row = output-row offset within the tile, an N-index; col = K-offset) rather than `gemm_metal`'s
    own `[BK, BN]`, specifically so each lane's own cooperative-load stays CONTIGUOUS along `k` for
    one fixed output row -- `w`'s own `[n,k]` layout, unchanged.

    Out-of-range rows/columns (the FINAL tile of `m_rows` or `n`, when neither is an exact multiple
    of `BM`/`BN`) are zero-padded on load rather than skipped, and the final store is bounds-checked
    per element -- the identical two-part discipline `_tiled_gemm_kernel`'s own docstring names:
    every thread must reach both barriers (an early `continue` on a partial tile hangs the group),
    but a padded lane's own OUTPUT is never written if it falls outside `[0,m_rows) x [0,n)`.
    """
    comptime BM = _GEMM_BM
    comptime BN = _GEMM_BN
    comptime BK = _GEMM_BK
    comptime TM = _GEMM_TM
    comptime TN = _GEMM_TN
    comptime NTHREADS = _GEMM_NTHREADS

    var a_tile = stack_allocation[BM * BK, DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[BK * BN, DType.float32, address_space = AddressSpace.SHARED]()
    var acc = stack_allocation[TM * TN, DType.float32]()
    var reg_a = stack_allocation[TM, DType.float32]()
    var reg_b = stack_allocation[TN, DType.float32]()

    for i in range(TM * TN):
        acc[i] = 0.0

    var n_tile_cols = (n + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var n_steps = (k + BK - 1) // BK
    for step in range(n_steps):
        for s in range(BM * BK // NTHREADS):
            var idx = tid + s * NTHREADS
            var ar = idx // BK
            var ac = idx % BK
            var gr = block_row + ar
            var gc = step * BK + ac
            a_tile[idx] = xn[gr * k + gc] if (gr < m_rows and gc < k) else Float32(0.0)
        for s in range(BN * BK // NTHREADS):
            var idx2 = tid + s * NTHREADS
            var br = idx2 // BK
            var bc = idx2 % BK
            var gr2 = block_col + br
            var gc2 = step * BK + bc
            if gr2 < n and gc2 < k:
                b_tile[idx2] = Float32(w[gr2 * k + gc2]) * wscale[gr2]
            else:
                b_tile[idx2] = Float32(0.0)

        barrier()

        for kk in range(BK):
            for i2 in range(TM):
                reg_a[i2] = a_tile[(ty * TM + i2) * BK + kk]
            for j2 in range(TN):
                reg_b[j2] = b_tile[(tx * TN + j2) * BK + kk]
            for i2 in range(TM):
                for j2 in range(TN):
                    acc[i2 * TN + j2] += reg_a[i2] * reg_b[j2]

        barrier()

    for i2 in range(TM):
        for j2 in range(TN):
            var r = block_row + ty * TM + i2
            var c = block_col + tx * TN + j2
            if r < m_rows and c < n:
                y[r * n + c] = acc[i2 * TN + j2]


def _pf_gemm_accum_kernel_i8(y: _FP, x: _FP, w: _I8P, wscale: _FP, m_rows: Int, k: Int, n: Int):
    """Weight-stationary tiled GEMM: `y[M,n] += x[M,k] @ W^T[k,n]` -- byte-for-byte the same tiling
    as `_pf_gemm_assign_kernel_i8` (see that kernel's own docstring for the full account); the ONLY
    difference is the final store, `+=` instead of `=`, matching `_pf_gemv_accum_kernel_simd_i8`'s
    own relationship to `_pf_qkv_proj_kernel_simd_i8`. `x` here is NOT normalized first (unlike
    `qkv_proj`'s `xn`) -- `o_proj`'s input is the attention output, `down_proj`'s is the gated-FFN
    activation, neither of which is ever normalized before this projection in the un-tiled Phase-1
    kernel this replaces either. Reused for BOTH `o_proj` and `down_proj`, exactly as that Phase-1
    kernel already is.
    """
    comptime BM = _GEMM_BM
    comptime BN = _GEMM_BN
    comptime BK = _GEMM_BK
    comptime TM = _GEMM_TM
    comptime TN = _GEMM_TN
    comptime NTHREADS = _GEMM_NTHREADS

    var a_tile = stack_allocation[BM * BK, DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[BK * BN, DType.float32, address_space = AddressSpace.SHARED]()
    var acc = stack_allocation[TM * TN, DType.float32]()
    var reg_a = stack_allocation[TM, DType.float32]()
    var reg_b = stack_allocation[TN, DType.float32]()

    for i in range(TM * TN):
        acc[i] = 0.0

    var n_tile_cols = (n + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var n_steps = (k + BK - 1) // BK
    for step in range(n_steps):
        for s in range(BM * BK // NTHREADS):
            var idx = tid + s * NTHREADS
            var ar = idx // BK
            var ac = idx % BK
            var gr = block_row + ar
            var gc = step * BK + ac
            a_tile[idx] = x[gr * k + gc] if (gr < m_rows and gc < k) else Float32(0.0)
        for s in range(BN * BK // NTHREADS):
            var idx2 = tid + s * NTHREADS
            var br = idx2 // BK
            var bc = idx2 % BK
            var gr2 = block_col + br
            var gc2 = step * BK + bc
            if gr2 < n and gc2 < k:
                b_tile[idx2] = Float32(w[gr2 * k + gc2]) * wscale[gr2]
            else:
                b_tile[idx2] = Float32(0.0)

        barrier()

        for kk in range(BK):
            for i2 in range(TM):
                reg_a[i2] = a_tile[(ty * TM + i2) * BK + kk]
            for j2 in range(TN):
                reg_b[j2] = b_tile[(tx * TN + j2) * BK + kk]
            for i2 in range(TM):
                for j2 in range(TN):
                    acc[i2 * TN + j2] += reg_a[i2] * reg_b[j2]

        barrier()

    for i2 in range(TM):
        for j2 in range(TN):
            var r = block_row + ty * TM + i2
            var c = block_col + tx * TN + j2
            if r < m_rows and c < n:
                y[r * n + c] = y[r * n + c] + acc[i2 * TN + j2]


def _pf_gemm_swiglu_kernel_i8(
    act: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int, k: Int, n_ff: Int
):
    """Weight-stationary tiled GEMM computing BOTH gate and up projections from the SAME loaded
    `xn` tile in one pass -- gate rows `[0, n_ff)` of `w`/`wscale`, up rows `[n_ff, 2*n_ff)`, the SAME
    row-indexing convention `_pf_swiglu_kernel_simd_i8`'s own docstring establishes -- SwiGLU-
    combined on output: `act[m,j] = (gate / (1 + exp(-gate))) * up`. Same `BM x BN` tile / `TM x TN`
    register-block strategy as `_pf_gemm_assign_kernel_i8`, but each thread now holds TWO accumulator
    blocks (`acc_g`, `acc_u`) and each `step` loads TWO weight tiles (`bg_tile`, `bu_tile`) against
    the SAME loaded activation tile (`a_tile`) -- the identical "stage the normalized row once, read
    it twice" reuse `_pf_swiglu_kernel_simd_i8`'s own docstring achieves via `xs`, just register-
    tiled instead of one-column-per-SIMD-group.
    """
    comptime BM = _GEMM_BM
    comptime BN = _GEMM_BN
    comptime BK = _GEMM_BK
    comptime TM = _GEMM_TM
    comptime TN = _GEMM_TN
    comptime NTHREADS = _GEMM_NTHREADS

    var a_tile = stack_allocation[BM * BK, DType.float32, address_space = AddressSpace.SHARED]()
    var bg_tile = stack_allocation[BK * BN, DType.float32, address_space = AddressSpace.SHARED]()
    var bu_tile = stack_allocation[BK * BN, DType.float32, address_space = AddressSpace.SHARED]()
    var acc_g = stack_allocation[TM * TN, DType.float32]()
    var acc_u = stack_allocation[TM * TN, DType.float32]()
    var reg_a = stack_allocation[TM, DType.float32]()
    var reg_bg = stack_allocation[TN, DType.float32]()
    var reg_bu = stack_allocation[TN, DType.float32]()

    for i in range(TM * TN):
        acc_g[i] = 0.0
        acc_u[i] = 0.0

    var n_tile_cols = (n_ff + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var n_steps = (k + BK - 1) // BK
    for step in range(n_steps):
        for s in range(BM * BK // NTHREADS):
            var idx = tid + s * NTHREADS
            var ar = idx // BK
            var ac = idx % BK
            var gr = block_row + ar
            var gc = step * BK + ac
            a_tile[idx] = xn[gr * k + gc] if (gr < m_rows and gc < k) else Float32(0.0)
        for s in range(BN * BK // NTHREADS):
            var idx2 = tid + s * NTHREADS
            var br = idx2 // BK
            var bc = idx2 % BK
            var gr2 = block_col + br
            var gc2 = step * BK + bc
            if gr2 < n_ff and gc2 < k:
                bg_tile[idx2] = Float32(w[gr2 * k + gc2]) * wscale[gr2]
                bu_tile[idx2] = Float32(w[(n_ff + gr2) * k + gc2]) * wscale[n_ff + gr2]
            else:
                bg_tile[idx2] = Float32(0.0)
                bu_tile[idx2] = Float32(0.0)

        barrier()

        for kk in range(BK):
            for i2 in range(TM):
                reg_a[i2] = a_tile[(ty * TM + i2) * BK + kk]
            for j2 in range(TN):
                reg_bg[j2] = bg_tile[(tx * TN + j2) * BK + kk]
                reg_bu[j2] = bu_tile[(tx * TN + j2) * BK + kk]
            for i2 in range(TM):
                for j2 in range(TN):
                    acc_g[i2 * TN + j2] += reg_a[i2] * reg_bg[j2]
                    acc_u[i2 * TN + j2] += reg_a[i2] * reg_bu[j2]

        barrier()

    for i2 in range(TM):
        for j2 in range(TN):
            var r = block_row + ty * TM + i2
            var c = block_col + tx * TN + j2
            if r < m_rows and c < n_ff:
                var g = acc_g[i2 * TN + j2]
                var u = acc_u[i2 * TN + j2]
                act[r * n_ff + c] = (g / (1.0 + exp(-g))) * u


# ============================================================================================
# NARROW-TILE VARIANTS -- see `_GEMM_BM_NARROW`'s own docstring for the measurement that motivated
# these. Byte-for-byte the same math as their WIDE twins immediately above (`_pf_gemm_assign_
# kernel_i8`/`_pf_gemm_accum_kernel_i8`/`_pf_gemm_swiglu_kernel_i8`); the ONLY difference is which
# comptime tile constants each reads (`_GEMM_BM_NARROW`/`_GEMM_TM_NARROW` in place of `_GEMM_BM`/
# `_GEMM_TM`, `_GEMM_BN`/`_GEMM_BK`/`_GEMM_TN` UNCHANGED). Selected at runtime by `residentk.
# contract.residentk_prefill_gemm_use_narrow_tile(m_rows)`, never both for the same dispatch.
# ============================================================================================


def _pf_gnrw_assign_kernel_i8(y: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int, k: Int, n: Int):
    """The NARROW-tile twin of `_pf_gemm_assign_kernel_i8` -- see that kernel's own docstring for
    the full account; only `BM`/`TM` differ."""
    comptime BM = _GEMM_BM_NARROW
    comptime BN = _GEMM_BN
    comptime BK = _GEMM_BK
    comptime TM = _GEMM_TM_NARROW
    comptime TN = _GEMM_TN
    comptime NTHREADS = _GEMM_NTHREADS_NARROW

    var a_tile = stack_allocation[BM * BK, DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[BK * BN, DType.float32, address_space = AddressSpace.SHARED]()
    var acc = stack_allocation[TM * TN, DType.float32]()
    var reg_a = stack_allocation[TM, DType.float32]()
    var reg_b = stack_allocation[TN, DType.float32]()

    for i in range(TM * TN):
        acc[i] = 0.0

    var n_tile_cols = (n + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var n_steps = (k + BK - 1) // BK
    for step in range(n_steps):
        for s in range(BM * BK // NTHREADS):
            var idx = tid + s * NTHREADS
            var ar = idx // BK
            var ac = idx % BK
            var gr = block_row + ar
            var gc = step * BK + ac
            a_tile[idx] = xn[gr * k + gc] if (gr < m_rows and gc < k) else Float32(0.0)
        for s in range(BN * BK // NTHREADS):
            var idx2 = tid + s * NTHREADS
            var br = idx2 // BK
            var bc = idx2 % BK
            var gr2 = block_col + br
            var gc2 = step * BK + bc
            if gr2 < n and gc2 < k:
                b_tile[idx2] = Float32(w[gr2 * k + gc2]) * wscale[gr2]
            else:
                b_tile[idx2] = Float32(0.0)

        barrier()

        for kk in range(BK):
            for i2 in range(TM):
                reg_a[i2] = a_tile[(ty * TM + i2) * BK + kk]
            for j2 in range(TN):
                reg_b[j2] = b_tile[(tx * TN + j2) * BK + kk]
            for i2 in range(TM):
                for j2 in range(TN):
                    acc[i2 * TN + j2] += reg_a[i2] * reg_b[j2]

        barrier()

    for i2 in range(TM):
        for j2 in range(TN):
            var r = block_row + ty * TM + i2
            var c = block_col + tx * TN + j2
            if r < m_rows and c < n:
                y[r * n + c] = acc[i2 * TN + j2]


def _pf_gnrw_accum_kernel_i8(y: _FP, x: _FP, w: _I8P, wscale: _FP, m_rows: Int, k: Int, n: Int):
    """The NARROW-tile twin of `_pf_gemm_accum_kernel_i8` -- see that kernel's own docstring for
    the full account; only `BM`/`TM` differ."""
    comptime BM = _GEMM_BM_NARROW
    comptime BN = _GEMM_BN
    comptime BK = _GEMM_BK
    comptime TM = _GEMM_TM_NARROW
    comptime TN = _GEMM_TN
    comptime NTHREADS = _GEMM_NTHREADS_NARROW

    var a_tile = stack_allocation[BM * BK, DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[BK * BN, DType.float32, address_space = AddressSpace.SHARED]()
    var acc = stack_allocation[TM * TN, DType.float32]()
    var reg_a = stack_allocation[TM, DType.float32]()
    var reg_b = stack_allocation[TN, DType.float32]()

    for i in range(TM * TN):
        acc[i] = 0.0

    var n_tile_cols = (n + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var n_steps = (k + BK - 1) // BK
    for step in range(n_steps):
        for s in range(BM * BK // NTHREADS):
            var idx = tid + s * NTHREADS
            var ar = idx // BK
            var ac = idx % BK
            var gr = block_row + ar
            var gc = step * BK + ac
            a_tile[idx] = x[gr * k + gc] if (gr < m_rows and gc < k) else Float32(0.0)
        for s in range(BN * BK // NTHREADS):
            var idx2 = tid + s * NTHREADS
            var br = idx2 // BK
            var bc = idx2 % BK
            var gr2 = block_col + br
            var gc2 = step * BK + bc
            if gr2 < n and gc2 < k:
                b_tile[idx2] = Float32(w[gr2 * k + gc2]) * wscale[gr2]
            else:
                b_tile[idx2] = Float32(0.0)

        barrier()

        for kk in range(BK):
            for i2 in range(TM):
                reg_a[i2] = a_tile[(ty * TM + i2) * BK + kk]
            for j2 in range(TN):
                reg_b[j2] = b_tile[(tx * TN + j2) * BK + kk]
            for i2 in range(TM):
                for j2 in range(TN):
                    acc[i2 * TN + j2] += reg_a[i2] * reg_b[j2]

        barrier()

    for i2 in range(TM):
        for j2 in range(TN):
            var r = block_row + ty * TM + i2
            var c = block_col + tx * TN + j2
            if r < m_rows and c < n:
                y[r * n + c] = y[r * n + c] + acc[i2 * TN + j2]


def _pf_gnrw_swiglu_kernel_i8(
    act: _FP, xn: _FP, w: _I8P, wscale: _FP, m_rows: Int, k: Int, n_ff: Int
):
    """The NARROW-tile twin of `_pf_gemm_swiglu_kernel_i8` -- see that kernel's own docstring for
    the full account; only `BM`/`TM` differ."""
    comptime BM = _GEMM_BM_NARROW
    comptime BN = _GEMM_BN
    comptime BK = _GEMM_BK
    comptime TM = _GEMM_TM_NARROW
    comptime TN = _GEMM_TN
    comptime NTHREADS = _GEMM_NTHREADS_NARROW

    var a_tile = stack_allocation[BM * BK, DType.float32, address_space = AddressSpace.SHARED]()
    var bg_tile = stack_allocation[BK * BN, DType.float32, address_space = AddressSpace.SHARED]()
    var bu_tile = stack_allocation[BK * BN, DType.float32, address_space = AddressSpace.SHARED]()
    var acc_g = stack_allocation[TM * TN, DType.float32]()
    var acc_u = stack_allocation[TM * TN, DType.float32]()
    var reg_a = stack_allocation[TM, DType.float32]()
    var reg_bg = stack_allocation[TN, DType.float32]()
    var reg_bu = stack_allocation[TN, DType.float32]()

    for i in range(TM * TN):
        acc_g[i] = 0.0
        acc_u[i] = 0.0

    var n_tile_cols = (n_ff + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var n_steps = (k + BK - 1) // BK
    for step in range(n_steps):
        for s in range(BM * BK // NTHREADS):
            var idx = tid + s * NTHREADS
            var ar = idx // BK
            var ac = idx % BK
            var gr = block_row + ar
            var gc = step * BK + ac
            a_tile[idx] = xn[gr * k + gc] if (gr < m_rows and gc < k) else Float32(0.0)
        for s in range(BN * BK // NTHREADS):
            var idx2 = tid + s * NTHREADS
            var br = idx2 // BK
            var bc = idx2 % BK
            var gr2 = block_col + br
            var gc2 = step * BK + bc
            if gr2 < n_ff and gc2 < k:
                bg_tile[idx2] = Float32(w[gr2 * k + gc2]) * wscale[gr2]
                bu_tile[idx2] = Float32(w[(n_ff + gr2) * k + gc2]) * wscale[n_ff + gr2]
            else:
                bg_tile[idx2] = Float32(0.0)
                bu_tile[idx2] = Float32(0.0)

        barrier()

        for kk in range(BK):
            for i2 in range(TM):
                reg_a[i2] = a_tile[(ty * TM + i2) * BK + kk]
            for j2 in range(TN):
                reg_bg[j2] = bg_tile[(tx * TN + j2) * BK + kk]
                reg_bu[j2] = bu_tile[(tx * TN + j2) * BK + kk]
            for i2 in range(TM):
                for j2 in range(TN):
                    acc_g[i2 * TN + j2] += reg_a[i2] * reg_bg[j2]
                    acc_u[i2 * TN + j2] += reg_a[i2] * reg_bu[j2]

        barrier()

    for i2 in range(TM):
        for j2 in range(TN):
            var r = block_row + ty * TM + i2
            var c = block_col + tx * TN + j2
            if r < m_rows and c < n_ff:
                var g = acc_g[i2 * TN + j2]
                var u = acc_u[i2 * TN + j2]
                act[r * n_ff + c] = (g / (1.0 + exp(-g))) * u
