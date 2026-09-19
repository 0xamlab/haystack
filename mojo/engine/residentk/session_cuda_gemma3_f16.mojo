"""
residentk.session_cuda_gemma3_f16 — the CUDA-native FLOAT16-weight resident session for Gemma 3
(Gemma 3 lane, 2026-08-23). This is the arm that makes google/gemma-3-27b-it RUN on one 80 GB
H100: Float32 weights (~109 GB) do not fit, Float16 (~54 GB) does. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float16
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/gemma3/ref_gemma3_torch.py
benchmark: benchmarks/llm_smoke/nvidia_race/gemma3_correctness_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module; private names, launches gated behind `CUDA_GEMMA3_BUILD` exactly the way
`residentk.session_cuda_gemma3` documents.

Mixed-precision discipline — identical to `residentk.session_cuda_f16`'s for Qwen3/llama: the four
per-layer projection matrices and the tied embed/lm_head table are resident Float16; the norm
gains, the RoPE tables, the KV cache, and every activation/accumulator stay Float32. Each weight
element widens to Float32 on load, before the multiply that consumes it, so the arithmetic is the
f32 session's exactly, at half the weight-storage bytes. Gemma 3's family structure (four norms,
post-branch residual wiring, dual rope, sliding window, GeGLU, sqrt(hidden) embed scale) is
unchanged from `_CudaResidentGemma3`; only the weight buffers' dtype and the dispatched kernel
twins differ.
"""

from max.gpu.host import (
    DeviceBuffer,
    DeviceContext,
    DeviceGraph,
    DeviceGraphBuilder,
    HostBuffer,
)
from std.collections import Optional
from std.origin import MutAnyOrigin
from std.sys import is_defined
from residentk.contract import (
    RESIDENT_ERR_CONTEXT_FULL,
    RESIDENT_ERR_LAUNCH_FAILED,
    RESIDENT_ERR_NO_DEVICE,
    RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT,
    RESIDENT_ERR_UPLOAD_LENGTH,
    RESIDENT_OK,
)
from residentk.kernels import (
    _TG,
    _SUBS,
    _argmax_reduce_kernel,
    _lmhead_argmax_kernel_f16,
    _norm_gemv_kernel_f16,
    _pf_rmsnorm_rows_kernel,
    _pf_ropewrt_kernel,
    _qk_rope_write_kernel,
    _splitk_merge_kernel_simd,
)
from residentk.kernels_cuda_graph import (
    _graph_advance_kernel,
    _qk_rope_write_kernel_g,
)
from residentk.kernels_gemma3 import (
    _g3_embed_row_kernel_f16,
    _g3_embed_row_kernel_f16_g,
    _g3_gemv_kernel_f16,
    _g3_norm_accum_kernel,
    _g3_norm_gemv2_geglu_kernel_f16,
    _g3_norm_gemv2_geglu_kernel_f16_u4,
    _g3_norm_inplace_kernel,
    _g3_sdpa_window_kernel,
    _g3_splitk_partial_kernel_simd_g,
)
from residentk.kernels_prefill_gemma3 import (
    G3_PF_TILE,
    _pf_attn_window_kernel,
    _pf_attn_window_flash_kernel,
    _G3_PF_FLASH_ROWS_PER_BLOCK,
    _G3_PF_FLASH_NTHREADS,
    _pf_q_pack_hm_f16,
    _pf_attn_unpack_hm_f32,
    _pf_embed_rows_g3_kernel_f16,
    _pf_geglu_rows_kernel,
    _pf_geglu_rows_f16_kernel,
    _pf_rmsnorm_rows_f16_kernel,
    _pf_ropewrt_warps_kernel,
    _pf_ropewrt_warps_vec_kernel,
    _G3_ROPE_WARPS_PER_BLOCK,
    _G3_ROPEV_HEADS_PER_BLOCK,
    _G3_ROPE_NTHREADS,
    _pf_fill_scale_kernel,
    _pf_gemm_accum_kernel_v2h,
    _pf_gemm_assign_kernel_v2h,
    _pf_gemm_geglu_kernel_v2h,
    _pf_norm_accum_rows_kernel,
    _pf_row_copy_kernel,
)
from residentk.kernels_prefill_f32_v2 import (
    _G2_BM,
    _G2_BN,
    _G2_NTHREADS,
)
from residentk.kernels_batched_gemma3 import (
    _g3_logits_argmax_kernel,
)
from residentk.tc_shim_bridge import (
    TC_SHIM_BUILD,
    TC_MIN_M,
    _tc_init,
    _tc_last_error,
    _tc_gemm_dispatch,
    _tc_gemm_dispatch_auto,
    _tc_use_legacy_stream,
    _tc_bgemm_f16_async,
    _tc_attn_softmax_mask_async,
    _tc_stage_f32_to_f16,
    _tc_stage_f32_to_f16_v8,
    _tc_fa_layout_probe,
    _tc_fa2_layout_probe,
    _tc_fa_g3_window_async,
    _tc_fa_g3_window2_async,
    _tc_fa_g3_window3_async,
    _tc_gemm_f16_32c_pre_async,
    _tc_gemm_f16_16c_pre_async,
)
from residentk.session import (
    RESIDENT_GPU_BUILD,
    _LM_BLOCKS,
    _StepOut,
    _ceil_div,
    _narrow_into,
    _narrow_into_f16,
    _narrow_transposed_into_f16,
)

comptime CUDA_GEMMA3_BUILD: Bool = RESIDENT_GPU_BUILD and is_defined["ALGENTA_CUDA"]()

comptime G3_STREAM: Bool = TC_SHIM_BUILD and is_defined["ALGENTA_G3_STREAM"]()
"""The stream-ordered seam lever (2026-08-24) — the single-stream prefill arm of it: with
`-D ALGENTA_G3_STREAM` the cuBLAS handle binds to the CUDA LEGACY default stream at TC init
and the tiled prefill's four-per-layer GemmEx seams dispatch `_tc_gemm_dispatch_auto`
(async) with NO `ctx.synchronize()` before them — Mojo's default stream is device-ordered
against the legacy stream (legacy_probe.mojo, H100), so the 248 seams of a 550-token TTFT
ingest keep full order with zero host syncs. See `residentk.session_cuda_gemma3_batched`'s
`G3_STREAM` for the decode arm and the full rationale."""

comptime GEMMA3_GRAPH_N_SPLITS: Int = 32
"""The split-K fan-out of the gemma3 graph decode arm (same reasoning as
residentk.session_cuda.CUDA_GRAPH_N_SPLITS: in-graph the launch overhead is gone, so
h_q x splits blocks win at every depth)."""

comptime _G3_GEGLU_U4: Bool = is_defined["ALGENTA_G3_GEGLU_U4"]()
"""GEMV-bandwidth lever sweep (2026-08-24): build with `-D ALGENTA_G3_GEGLU_U4` to dispatch the
4-way-unrolled gate/up GeGLU kernel (`_g3_norm_gemv2_geglu_kernel_f16_u4`) instead of the
baseline. A/B against the baseline by building with/without the define; both arms are
correctness-gated before a winner is kept."""

comptime G3_PF_ATTN_FLASH: Bool = is_defined["ALGENTA_G3_PF_ATTN_FLASH"]()
"""The flash-style M-parallel PREFILL attention lever (the TTFT lever of the vLLM-flip round,
2026-08-24): with `-D ALGENTA_G3_PF_ATTN_FLASH` the tiled prefill's windowed attention
dispatches the warp-per-(4 rows) FLASH twin (`_pf_attn_window_flash_kernel`) instead of the
barrier-tree `_pf_attn_window_kernel`, but ONLY at `d_head == 128` (the flash twin's structural
lane contract); every other head dim stays on the byte-for-byte tiled kernel. Fact-driven
capability dispatch (head-dim), never a per-model branch. Flag-off builds keep the tiled
kernel byte-for-byte."""

comptime G3_PF_TCATTN: Bool = is_defined["ALGENTA_G3_PF_TCATTN"]()
"""The TENSOR-CORE prefill-attention lever (vLLM-flip round 2, 2026-08-24): with
`-D ALGENTA_G3_PF_TCATTN` (and the TC shim ready, `d_head == 128`) the tiled prefill's
windowed attention dispatches the strided-batched cuBLAS HMMA pipeline — Q pack to head-major
f16, QK^T GemmStridedBatchedEx over the KV heads (GQA: g query heads per KV head as g*M
rows), masked causal+window softmax, PV GemmStridedBatchedEx, unpack — instead of the SIMT
kernels. Takes precedence over G3_PF_ATTN_FLASH when both are set. Same fact-driven
capability gate (d_head == 128 + tc_ready); flag-off builds are byte-unmodified."""

comptime G3_PF_FA: Bool = TC_SHIM_BUILD and is_defined["ALGENTA_G3_PF_FA"]()
"""The FUSED TENSOR-CORE prefill-attention lever (round 5, 2026-09-16): with
`-D ALGENTA_G3_PF_FA` the tiled prefill's windowed attention dispatches ONE hand-written WMMA
FlashAttention-2 kernel (`tc_shim_fa_g3_window_async`) instead of G3_PF_TCATTN's five-pass
cuBLAS chain, deleting four GPU passes per layer per tile:

  * the head-major Q pack (`_pf_q_pack_hm_f16`) and the head-major O unpack
    (`_pf_attn_unpack_hm_f32`) — the kernel reads Q straight out of `pf_q_rot` and writes O
    straight into `pf_attn`, both in the session's own position-major f32 layout;
  * the masked softmax (`_attn_softmax_mask_kernel`) — online softmax keeps the score tile in
    the WMMA accumulators, so the `[h_q*m, n_keys]` f32 score matrix (134 MB/layer at
    m=n_keys=1024) and the f16 P twin are never materialized;
  * the K/V f32->f16 staging (`_f32_to_f16_kernel`) — the kernel reads the RESIDENT f32 KV
    cache and converts in-register on the way into shared memory (`kv32=1`), so the staging
    pass and its 6 bytes/element round trip disappear with it.

and adding one the chain never had: the sliding window is applied as a KEY-BLOCK RANGE, so a
local layer (52 of gemma-3-27b's 62) stops loading keys it would mask away — at RAG-4096 the
five-pass chain computes a dense 4096-wide QK^T per local layer to keep 1024 columns.

TENSOR-CORE BY CONSTRUCTION: the QK^T and PV products are `wmma::mma_sync` m16n16k16 f16 HMMA
with an f32 accumulator. This is NOT the SIMT fused-flash twin (`_pf_attn_window_flash_kernel`,
`-D ALGENTA_G3_PF_ATTN_FLASH`), which is a measured 2x REGRESSION at pp1024 and is kept only
as the negative control. Takes precedence over G3_PF_TCATTN and G3_PF_ATTN_FLASH when set.

Same fact-driven capability gate (d_head == 128 + integral GQA + tc_ready + the shim's
on-device WMMA accumulator-layout probe). A DECLINED lever prints DECLINED once at seal() and
keeps the five-pass chain: -301/-304/-305/-310 fall back, any other non-zero status is a real
launch failure and is returned as one. Flag-off builds are byte-unmodified."""

comptime G3_PF_FA2: Bool = G3_PF_FA and is_defined["ALGENTA_G3_PF_FA2"]()
"""The fused windowed attention KERNEL, v2 (round 6, `-D ALGENTA_G3_PF_FA2`): G3_PF_FA's
dispatch slot with #994's 7B FA2 techniques transplanted onto the windowed kernel
(`_tc_fa_g3_window2_async`) — raw `mma.sync m16n8k16` with the P tile's A-fragment packed IN
REGISTERS (deleting `sP` and one of the three per-key-block fences), the O epilogue written
position-major STRAIGHT TO GLOBAL from the ISA-specified D layout (deleting `sO`, its 33.8 KB
window and its fence), and cp.async K/V double buffering on the f16 K/V route — the native-f32
route (kv32=1, production) keeps round 5's synchronous in-register-convert load, because
cp.async copies raw bytes and cannot convert.

Round 5 shipped the WMMA kernel and its own decomposition then named the remainder:
`fused_tc_attention` is the largest non-GEMM bucket at rag4096 (86.379 ms whole-process).

FA2 inherits G3_PF_FA's WHOLE gate rather than restating it — it is a different implementation
of the same dispatch slot, so a build that asked for FA2 without FA gets round 5's kernel, the
one it would have dispatched anyway. A DECLINED v2 (-301/-304/-305/-311, the last being the
shim's raw-mma on-device layout probe) falls back PER CALL to round 5's WMMA kernel, which
keeps its own decline-to-five-pass-chain fallback; the seal()-time banner states which kernel
the binary will run. Numerics: every rounding point is round 5's verbatim; only the summation
ORDER changes (m16n8k16 accumulates 16 keys per instruction where WMMA's m16n16k16 accumulated
16 as two 8-wide halves), so the lever goes through the same token-identity gates. Flag-off
builds are byte-unmodified."""

comptime G3_PF_F16NORM: Bool = TC_SHIM_BUILD and is_defined["ALGENTA_G3_PF_F16NORM"]()
"""The pre-staged-A norm lever (round 5, the gemma-3 twin of `-D ALGENTA_7B_PF_F16NORM`): both
per-layer rmsnorm dispatches write an f16 `pf_xn16` (`_pf_rmsnorm_rows_f16_kernel`) and the
qkv and gate/up projection GEMMs take it directly (`_tc_gemm_f16_32c_pre_async`), deleting the
shim's per-call f32->f16 A conversion. BIT-IDENTICAL to the f32 chain: the f16 value is the
same f32 arithmetic rounded once at the store, which is exactly the rounding the shim's
`_f32_to_f16_kernel` would have applied to that same f32 one launch later — there is no second
rounding point to diverge at."""

comptime G3_PF_F16MLP: Bool = TC_SHIM_BUILD and is_defined["ALGENTA_G3_PF_F16MLP"]()
"""The pre-staged-A MLP lever (round 5, the gemma-3 twin of `-D ALGENTA_7B_PF_F16MLP`): the
gate/up GEMM writes its `[m, 2*d_ff]` result as f16 C (`_tc_gemm_f16_16c_pre_async`),
`_pf_geglu_rows_f16_kernel` combines that f16 into the f16 `pf_act16`, and down_proj takes
`pf_act16` as a pre-staged A. At gemma-3-27b's shapes (m=1024, d_ff=21504) this is the
layer's largest non-GEMM traffic term: the f32 chain writes 176 MB of C, reads it back, writes
88 MB of f32 act, reads that back and writes 44 MB of f16 A; this chain writes 88 MB, reads
88 MB, writes 44 MB and reads 44 MB. NOT bit-identical (the GeGLU inputs round to f16 at the
GEMM epilogue instead of after it), so it carries its own flag and its own token-identity gate;
the down_proj A itself IS bit-identical, since `_pf_geglu_rows_f16_kernel` rounds its f32
result once at the store exactly where the shim's convert pass would have."""

comptime G3_PF_F16ATTN: Bool = G3_PF_FA and is_defined["ALGENTA_G3_PF_F16ATTN"]()
"""The pre-staged-A attention-output lever (round 5): the fused flash kernel writes its
position-major output as f16 `pf_attn16` and o_proj takes it directly
(`_tc_gemm_f16_32c_pre_async`), deleting the o_proj A conversion. Inherits G3_PF_FA's whole
gate rather than restating it — the f16 O is that kernel's `of16=1` instantiation, so without
FA there is no producer for the buffer. Bit-identical given FA's own output (one f32->f16
rounding at the store, where the shim's convert pass would have put it)."""

comptime G3_PF_ROPE2: Bool = is_defined["ALGENTA_G3_PF_ROPE2"]()
"""The warp-per-head q/k-norm + RoPE + KV-write lever (round 5): step 3 dispatches
`_pf_ropewrt_warps_kernel` (one WARP per head, 4 elements per lane, a five-step `shuffle_xor`
reduction, zero `barrier()` and zero shared memory) instead of `_pf_ropewrt_kernel` (one BLOCK
per head, one element per thread, a seven-step shared-memory tree with a barrier per step).

At gemma-3-27b's shapes the twin launches (h_q + h_kv) * m = 49,152 blocks of 128 threads per
1024-row tile — 12.2 million block launches over a RAG-4096 prefill — to move 67 MB per layer,
so it is launch- and barrier-bound rather than bandwidth-bound; round 4's decomposition put this
bucket 25.355 ms behind TensorRT-LLM's single `applyBiasRopeUpdateKVCacheV2`. This is 8x fewer
blocks (6,144) with no barriers at all.

BIT-IDENTICAL to the twin, by construction: the lane owns elements {t, t+32, t+64, t+96}, which
makes the twin's stride-64 and stride-32 reduction steps INTRA-LANE in its exact association and
its stride-16..1 steps five `shuffle_xor`s over the same operand pairs. See the kernel's own
docstring for the unrolled proof. Fact-driven capability gate: `d_head == 4 * WARP_SIZE` (128),
which is also what puts both halves of a RoPE pair in one lane; any other head width keeps the
twin byte-for-byte."""

comptime G3_PF_ROPEVEC: Bool = G3_PF_ROPE2 and not is_defined["ALGENTA_G3_PF_NO_ROPEVEC"]()
"""ROUND 13: **DEFAULT ON**. Opt OUT with `-D ALGENTA_G3_PF_NO_ROPEVEC`, which restores the scalar
ROPE2 kernel byte-for-byte as the A/B control. It is gated on `G3_PF_ROPE2` because it replaces
that kernel and not the block-per-head twin, so with ROPE2 off this is inert by construction and no
build can get the vector kernel without also having the kernel it vectorises.

WHY IT IS NOW DEFAULT ON, with the evidence rather than the argument. CERTIFIED in round 12 against
the cache-free fp32 transformers oracle on a fresh checkpoint at 1410 MHz with offpin=0 on every
cell: pp256 16/16 and 64/64 with the 64-token determinism repeat **2/2 bit-identical**, pp1024
16/16 and 64/64 with det 2/2, val550 16/16 and 64/64 with det 2/2, rag4096 22/22 + EOS-stop —
`GATE ALL_PASS = True` on arm `R9_both` (sha256_16 `ca66b41a2ee34cde`). MEASURED in round 13 on the
same binary, hash re-verified before timing so the certification provably attaches to it: rag4096
interleaved A..B..A against `R9_gqa2`, **delta -1.687 ms (-0.436%)**, bracket drift armor
**+0.116 ms (+0.030%)** so the delta exceeds its armor by **14.5x** and the summariser reports
`resolved = YES`; every cell 1410 MHz on every 1 Hz sample; and a same-session TRT-LLM re-serve
reproducing the stored column within 1% at all three cells, giving rag4096 **1.1140x**. The
same-bracket-only comparison (r6c_ cells alone, n=3 per arm) gives the identical -1.687 ms, so the
pooled median was not leaning on other sessions.

FLIPPED TOGETHER WITH `G3_PF_GQA2`, deliberately. The measured arm is `R9_both` = ship + GQA2 +
ROPEVEC, so flipping this flag alone would have shipped ship+ROPEVEC-without-GQA2 — a configuration
nobody ever timed. Both defaults ON makes **the shipped default exactly the measured arm**. To
isolate either lever in a future A/B, opt out of the one you are testing: `NO_ROPEVEC` alone gives
the GQA2-only arm, `NO_GQA2` alone gives the ROPEVEC-only arm, both together give the pre-round-9
ship. See `run_ab_gemma3_round9.sh` for the wired control arms.

ROUND 7 (authoring): vectorise the ROPE2 warp-per-head kernel's global accesses — step 3 dispatches
`_pf_ropewrt_warps_vec_kernel` (one HALF-warp per head, two contiguous `_ld4`/`_st4` quads per
lane, 16 heads per block) instead of `_pf_ropewrt_warps_kernel` (one warp per head, four STRIDED
scalar elements per lane, 8 heads per block).

WHY. ROPE2 removed the shared-memory round trip and the barriers (36.6 ms -> 7.7 ms
whole-process at rag4096), but it kept scalar 4-byte accesses, because its bit-exactness
argument DEPENDS on the strided lane mapping {t, t+32, t+64, t+96} that makes the twin's
stride-64/32 reduction steps intra-lane. That mapping is also what forces four separate
`ld.global.b32` per array per lane: without `loadvec`'s `alignment=16` annotation a
`load[width=4]` lowers to four scalar loads, not one `ld.global.v4.b32`. Round 6's decomposition
shows the residue — the rope bucket is ~6.2 ms measured against a 3.39 ms traffic roof (14.56 GB
at 4.8 TB/s), i.e. ~49% of roof, while TensorRT-LLM's `applyBiasRopeUpdateKVCacheV2` is 3.47 ms,
essentially AT that roof. So ~2.7 ms of this bucket is instruction shape, not bandwidth. This is
the same defect and the same fix FRONT 5 lever 2 applied to the 7B lane, where it measured ~43%
of roof before; `_pf_biasropewrt_vec_kernel` DECLINES gemma-3 because it cannot do a qk_norm
reduction without shared staging, and gemma-3 always has QK-norm. The half-warp-per-head layout
here is what closes that gap: a lane holds both quads of its four pairs, so the rotation needs no
cross-lane data movement and the norm reduces in four `shuffle_xor` steps inside the half-warp.
~24 memory instructions per head become ~8, and launches drop again (3 blocks per row, not 6).

NOT BIT-IDENTICAL, by the same argument that made ROPE2 exact: contiguous quads re-associate the
qk_norm sum-of-squares (eight intra-lane terms then four half-warp shuffles, instead of four
intra-lane terms then five full-warp shuffles), so `ss` and therefore `inv` round differently.
The scaling and rotation EXPRESSIONS are ROPE2's verbatim on non-interacting SIMD lanes. So this
carries its own flag and goes through the fp32-oracle token gates; the control (flag off) is
byte-preserved. Fact-driven capability gate: `d_head == 128` and `qk_norm`, any other shape stays
on ROPE2."""

comptime _G3_PF_BN32: Bool = is_defined["ALGENTA_G3_PF_BN32"]()
comptime _G3_PF_BN128: Bool = is_defined["ALGENTA_G3_PF_BN128"]()
comptime _G3_PF_FA_BN: Int = 32 if _G3_PF_BN32 else (128 if _G3_PF_BN128 else 64)
"""The fused flash attention's key-block width (the shim implements 32/64/128; anything else
selects 64). 64 is the 7B lane's measured best (`_PF_FA_BN`) and the shared-bandwidth-optimal
tile for FA_BM=64 / d=128 / 4 warps: 144 KB of shared reads per key block against 2.1 MFLOP
of HMMA = 0.069 B/FLOP, ~1.1x the sm_90 ratio of 128 B/clk shared to 2048 FLOP/clk tensor.

ROUND 6: `-D ALGENTA_G3_PF_BN32` / `-D ALGENTA_G3_PF_BN128` override it for A/B sweeps — the
width was inherited from the 7B lane's WMMA kernel and is untuned for BOTH gemma-3 and the v2
raw-mma kernel (#994's 7B FA2 moved to bn=32 when deleting sP/sO lifted occupancy to three
CTAs/SM; the v2 kernel's footprint moved with it, so the optimum is a measurement, not an
inheritance). BN changes the online-softmax block boundaries, i.e. the summation order, so an
override arm goes through the same token-identity gates as any numeric-path change. Default
(no flag) is 64 and a flag-off build is byte-unmodified."""

comptime _G3_PF_FA_MIN_M: Int = 256
"""The tile-row crossover at which the fused kernel takes over from the SIMT windowed kernel.
Held at the five-pass TC chain's OWN measured crossover (H100: TC attention wins from m >= 256,
loses at m = 160) so the round-5 A/B moves exactly one thing — the attention implementation —
and not the dispatch shape gate with it."""

comptime _G3_PF_KV16: Bool = is_defined["ALGENTA_G3_PF_KV16"]()
comptime _G3_PF_FA_KV32: Int = 0 if _G3_PF_KV16 else 1
"""1 = the fused kernel reads the session's RESIDENT f32 K/V cache and converts to f16
in-register on the way into shared memory, deleting the `_f32_to_f16_kernel` staging pass (6
bytes of global traffic per K/V element per layer down to 4, at the identical `__float2half`
rounding point). 0 = the CONTROL ARM: stage to `pf_tc_k16`/`pf_tc_v16` first and let the
kernel read f16, which is the same kernel with the staging pass left in — what the A/B
attributes the staging removal to. Never a model-name branch; the KV cache dtype is the fact.

ROUND 6 (`-D ALGENTA_G3_PF_KV16`): the control arm became a ship candidate. Round 5 chose
kv32=1 from a TRAFFIC MODEL (4 B/element in-register vs 6+2 staged) that its own probe could
not contradict — the probe's timing section was measuring launch gaps, not kernels (fixed
this round: wall clock + device sync). With working timings at BN=64, the f16-source kernel
is faster at EVERY raced shape, by up to 46% at the rag4096 tail (t4 local 140.9 vs 231.1 us,
t4 global 432.3 vs 800.4 us): a layer's f16 K+V at n_keys=4096 is 33.5 MB and re-read by
every q-head CTA through the H200's 60 MB L2, while the f32 form is 67 MB and misses. The
staging pass it costs is ~2-3 ms per rag4096 prefill against a ~24 ms attention saving. The
operands are BIT-IDENTICAL between the routes (round 5's probe: identical max_abs/rms at all
twelve shapes; the staging rounds where the in-register convert rounds), so this flag changes
scheduling and traffic, not numerics — it still carries its own banner and gate because it
changes which kernels run."""

comptime G3_PF_GQA2: Bool = G3_PF_FA2 and not is_defined["ALGENTA_G3_PF_NO_GQA2"]()
"""ROUND 13: **DEFAULT ON**, together with `G3_PF_ROPEVEC`. Opt OUT with
`-D ALGENTA_G3_PF_NO_GQA2`, which restores the v2 one-query-head-per-CTA dispatch byte-for-byte as
the A/B control. Gated on `G3_PF_FA2` because v3 is a variant of the v2 kernel, so with FA2 off this
is inert by construction.

WHY DEFAULT ON, and why BOTH levers flipped in the same change rather than one: the arm that was
**measured** in round 13 is `R9_both` = ship + GQA2 + ROPEVEC. Flipping ROPEVEC alone would have made
the shipped default a *different* configuration — ship + ROPEVEC without GQA2 — whose wall-clock was
never timed, and shipping a never-measured configuration to avoid a second flag flip is exactly
backwards. With both defaults ON, **the shipped default IS the measured arm**, hash-for-hash in flag
terms: rag4096 **385.458 ms**, **1.1140x** vs a same-session TRT-LLM 1.2.1 re-serve, a -1.687 ms
ROPEVEC delta exceeding its bracket drift armor by **14.5x** on top of round 11's RESOLVED -3.397 ms
GQA2 delta (6.4x its armor). GQA2 is the better-evidenced of the two — it is **bit-identical to v2**
(216/216 BITIDENT below) and shape-gated, so its risk is dispatch-only, while ROPEVEC re-associates
the `qk_norm` reduction and rides the fp32 oracle.

ROUND 9 (authoring, `-D ALGENTA_G3_PF_GQA2`, requires G3_PF_FA2): dispatch the fused windowed
attention through v3's GQA-PACKED CTAs — `rt=2` m16 row-tiles per warp spent on TWO QUERY HEADS OF
ONE KV HEAD at the same 16 rows, so `grid.y` falls from `h_q` to `h_q/2` and the K/V tile is fetched
once per (row-block, kv-head) instead of once per query head. Each `ldmatrix.x4` of K or V then
feeds two mma instead of one, halving the per-row shared-load stream that round 6 named as the
binding constraint on this kernel.

BIT-IDENTICAL TO v2 AND PROVEN SO, not asserted: `fa_g3_probe` holds every v3 arm to a
full-element bit comparison against the v2 arm of the same (kv32, of16, dbuf), and on 2026-09-17
that was **216/216 BITIDENT-v2, 0 BITDIFF, 0 FAIL at both BN=32 and BN=64** across all twelve
raced shapes including the odd tail. Both tiles share v2's `row0`, so the key-block range, the
block order and the mma k-grouping are v2's exactly per (row, head). A declined v3 falls through
to v2, which keeps its own fallback to v1 and then to the five-pass chain.

SHAPE-CONDITIONAL, AND THE CONDITION IS A MEASURED SHAPE FACT — see `_G3_PF_GQA2_MIN_NKEYS`.
Below the crossover this flag is a NO-OP: those cells keep v2 bit for bit and cannot regress."""

comptime _G3_PF_GQA2_RT: Int = 2
"""Row-tiles per warp the GQA-packed dispatch asks for. 2 is gemma-3-27b's whole GQA group
(`h_q/h_kv` = 32/16), so one CTA owns exactly the two query heads that share a KV head. The shim
rejects an `rt` that does not divide the group with -304, which is the check that stops a packed
CTA from silently reading the wrong K/V for its second tile."""

comptime _G3_PF_GQA2_MIN_NKEYS: Int = 2048
"""The key-count crossover at which GQA packing engages. A SHAPE FACT, MEASURED NOT MODELLED —
`fa_g3_probe`'s round-7 decision table (median of 30 after 3 warmups, production mapping
kv32=0/of16=1/dbuf=1, BN=32, H200 at 1410 MHz, reproduced at BN=64):

    shape              n_keys    v2 us   GQA2 us    delta
    pp256    local        256     22.5      30.9   +37.6%   LOSES BADLY
    pp1024   local       1024     90.8     101.6   +11.9%   LOSES
    rag t1   local       1024     90.3     101.8   +12.8%   LOSES
    rag t2   local       2048    126.7     110.5   -12.8%   WINS
    rag t2   global      2048    217.9     184.4   -15.4%   WINS
    rag t3   local       3072    126.1     110.9   -12.1%   WINS
    rag t4   local       4096    141.5     111.5   -21.2%   WINS
    rag t4   global      4096    431.2     350.2   -18.8%   WINS

The crossover sits between n_keys=1024 and n_keys=2048, so the threshold is 2048. WHY it sits
there: per-CTA work scales with the key-block count, while GQA packing's costs are per-CTA and
fixed — the Q tile is staged twice (once per head-tile) and the RT=2 register pressure is real
(255 registers, with 24 of 36 v3 instantiations spilling 424-488 B where v2 needs 158-172 and
spills nothing). At n_keys<=1024 a CTA walks <=32 key blocks, so those fixed costs dominate; at
n_keys>=2048 the halved K/V fetch is walked over 64-128 blocks and wins by 12-21%.

This is also WHY ROUND 7's BLANKET REFUTATION WAS WRONG. Round 7 read the register census (255 +
spill) and stopped before taking a single timing, concluding the lever was dead on arrival. The
census measured spill SIZE; what decides a spill is its FREQUENCY IN THE HOT LOOP relative to the
work amortized over it, and at large n_keys the answer is that the spill costs less than the K/V
traffic it saves. The probe had in fact already run to completion on the box and its logs said so
— they were simply not retrieved before the instance went to STOCKOUT. Recovering them reversed
the verdict for three of rag4096's four tiles.

CONSEQUENCE FOR THE RACED CELLS, which is the point of gating on shape at all: a rag4096 prefill
walks n_keys = 1024/2048/3072/4096, so tiles 2-4 take GQA2 and tile 1 keeps v2 — a modelled
-12.7% on the fused attention bucket (sum of the four per-tile probe rows, 484.6 -> 423.2 us),
which against round 6's measured 33.53 ms is about -4.25 ms. pp256 (n_keys=256) and pp1024
(n_keys=1024) fall entirely below the threshold and are UNTOUCHED, bit for bit, so neither can
regress."""

comptime _G3_PF_FA2_DBUF_MIN_N: Int = 0 if _G3_PF_BN32 else 2048
"""The key-count crossover at which the v2 kernel's cp.async K/V double buffering engages on
the f16 route (`dbuf = 1`). A shape fact, measured not inherited, and BN-DEPENDENT — the H200
probe (median of 30, all twelve shapes, 2026-09-16):

  * BN=64: dbuf=1 SLOWER at n_keys=1024 (pp1024 local 111.7 vs 96.6 us single-buffered — the
    second rotating buffer costs occupancy and a 16-block loop never amortizes it) and 14-21%
    FASTER from n_keys=2048 up -> threshold 2048.
  * BN=32: dbuf=1 faster EVERYWHERE, including pp256 (21.5 vs 25.0 us) and pp1024 (91.0 vs
    111.0) — the half-width tile restores the occupancy the second buffer costs -> threshold 0.

kv32=1 never double-buffers at any n (cp.async cannot convert f32)."""

comptime G3_ROUND5_FLAGS: Bool = G3_PF_FA or G3_PF_F16NORM or G3_PF_F16MLP or G3_PF_F16ATTN
"""One gate for the round-5 scratch: any of the four levers needs the f16 pre-staged-A
buffers, so they are allocated together and are 1-element placeholders in a flag-off build."""

alias _FP = UnsafePointer[Float32]


@fieldwise_init
struct _G3LayerGpuF16(Copyable, Movable):
    """One Gemma 3 layer: FOUR f32 norm gains, per-head q/k f32 gains, the four projection
    matrices resident FLOAT16, and the f32 KV slice."""

    var ln1: DeviceBuffer[DType.float32]
    var ln2: DeviceBuffer[DType.float32]
    var ln3: DeviceBuffer[DType.float32]
    var ln4: DeviceBuffer[DType.float32]
    var qn: DeviceBuffer[DType.float32]
    var kn: DeviceBuffer[DType.float32]
    var w_qkv: DeviceBuffer[DType.float16]
    var w_o: DeviceBuffer[DType.float16]
    var w_gu: DeviceBuffer[DType.float16]
    var w_down: DeviceBuffer[DType.float16]
    var ck: DeviceBuffer[DType.float32]
    var cv: DeviceBuffer[DType.float32]


@fieldwise_init
struct _CudaResidentGemma3F16(Movable):
    """The Gemma 3 CUDA-native resident session with Float16 weights (the 27B-fit arm)."""

    var ctx: DeviceContext
    var d_model: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var n_layers: Int
    var vocab: Int
    var max_ctx: Int
    var eps: Float32
    var scale: Float32
    var embed_scale: Float32
    var sliding_window: Int

    var layer_is_global: List[Int]
    var layers: List[_G3LayerGpuF16]
    var embed: DeviceBuffer[DType.float16]
    var final_norm: DeviceBuffer[DType.float32]
    var cos_global: DeviceBuffer[DType.float32]
    var sin_global: DeviceBuffer[DType.float32]
    var cos_local: DeviceBuffer[DType.float32]
    var sin_local: DeviceBuffer[DType.float32]

    var hidden: DeviceBuffer[DType.float32]
    var qkv: DeviceBuffer[DType.float32]
    var q_rot: DeviceBuffer[DType.float32]
    var attn_out: DeviceBuffer[DType.float32]
    var o_tmp: DeviceBuffer[DType.float32]
    var act: DeviceBuffer[DType.float32]
    var d_tmp: DeviceBuffer[DType.float32]
    var logits: DeviceBuffer[DType.float32]
    var blk_val: DeviceBuffer[DType.float32]
    var blk_idx: DeviceBuffer[DType.int32]
    var out_val: DeviceBuffer[DType.float32]
    var out_idx: DeviceBuffer[DType.int32]
    var host_val: HostBuffer[DType.float32]
    var host_idx: HostBuffer[DType.int32]
    var host_logits: HostBuffer[DType.float32]

    # tiled-prefill scratch — one G3_PF_TILE-row working set (the four-norm chain needs the
    # o/down BRANCH output materialised row-major before its norm + residual add; `pf_gu` holds
    # the TC seam's [m, 2*d_ff] gate/up result when the cuBLAS arm runs)
    var pf_tokens: DeviceBuffer[DType.int32]
    var pf_hidden: DeviceBuffer[DType.float32]
    var pf_xn: DeviceBuffer[DType.float32]
    var pf_qkv: DeviceBuffer[DType.float32]
    var pf_q_rot: DeviceBuffer[DType.float32]
    var pf_attn: DeviceBuffer[DType.float32]
    var pf_act: DeviceBuffer[DType.float32]
    var pf_branch: DeviceBuffer[DType.float32]
    var pf_gu: DeviceBuffer[DType.float32]

    # TC escape-hatch scratch — the f16 A staging + the f16-C fallback rung. The resident
    # weights ARE already the f16 B operand (no staging twin needed — that is the fit-fact this
    # arm exists for). Real sizes only under TC_SHIM_BUILD; 1-element placeholders otherwise.
    # `tc_ready`: 0 = init pending, 1 = cuBLAS handle bound, -1 = absent/failed.
    var tc_a16: DeviceBuffer[DType.float16]
    var tc_c16: DeviceBuffer[DType.float16]
    var tc_ready: Int

    # tensor-core prefill-attention scratch (vLLM-flip lever, -D ALGENTA_G3_PF_TCATTN):
    # head-major packed Q f16 [h_q, tile, d], QK^T scores f32 [h_q, tile, max_ctx], softmax
    # P f16 [h_q, tile, max_ctx], PV output f32 [h_q, tile, d]. Real sizes only under
    # TC_SHIM_BUILD; 1-element placeholders otherwise.
    var pf_tc_q16: DeviceBuffer[DType.float16]
    var pf_tc_p16: DeviceBuffer[DType.float16]
    var pf_tc_scores: DeviceBuffer[DType.float32]
    var pf_tc_o32: DeviceBuffer[DType.float32]
    var pf_tc_k16: DeviceBuffer[DType.float16]
    var pf_tc_v16: DeviceBuffer[DType.float16]

    # round-5 pre-staged-A scratch (-D ALGENTA_G3_PF_FA / _F16NORM / _F16MLP / _F16ATTN):
    # the f16 A operands the projection GEMMs read directly, so the shim's per-call
    # f32->f16 conversion disappears. `pf_xn16` [tile, d_model] is both rmsnorms' output,
    # `pf_gu16` [tile, 2*d_ff] the gate/up GEMM's f16 C, `pf_act16` [tile, d_ff] the GeGLU
    # combine's f16 output = down_proj's A, `pf_attn16` [tile, h_q*d] the fused flash
    # kernel's f16 O = o_proj's A. `pf_fa_scale` is the one-float DEVICE cell the fused
    # kernel dereferences (the attention scale travels as a pointer, never a float argument:
    # Mojo's `external_call` has no repo-proven float marshalling and an ABI mismatch there
    # would be a silent numeric bug). `pf_fa_armed` is 1 only once seal() has verified the
    # shim's WMMA accumulator layout ON THIS DEVICE — a declined lever keeps the five-pass
    # chain instead of quietly measuring it and reporting it as the fused one.
    # Real sizes only under G3_ROUND5_FLAGS; 1-element placeholders otherwise.
    var pf_xn16: DeviceBuffer[DType.float16]
    var pf_gu16: DeviceBuffer[DType.float16]
    var pf_act16: DeviceBuffer[DType.float16]
    var pf_attn16: DeviceBuffer[DType.float16]
    var pf_fa_scale: DeviceBuffer[DType.float32]
    var pf_fa_armed: Int

    # decode-graph arm — captured per-token dispatch sequence + dynamic-scalar feed (same design
    # as residentk.session_cuda's graph arm). step_state = [token_id, pos, n_keys].
    var step_state: DeviceBuffer[DType.int64]
    var host_state: HostBuffer[DType.int64]
    var token_log: DeviceBuffer[DType.int64]
    var host_token_log: HostBuffer[DType.int64]
    var sk_m: DeviceBuffer[DType.float32]
    var sk_l: DeviceBuffer[DType.float32]
    var sk_o: DeviceBuffer[DType.float32]
    var decode_graph: Optional[DeviceGraph]
    var decode_graph_built: Bool

    def __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
        embed_scale: Float64, sliding_window: Int, layer_is_global: List[Int],
    ) raises:
        self.ctx = DeviceContext()
        self.d_model = d_model
        self.h_q = h_q
        self.h_kv = h_kv
        self.d_head = d_head
        self.d_ff = d_ff
        self.n_layers = n_layers
        self.vocab = vocab
        self.max_ctx = max_ctx
        self.eps = Float32(eps)
        self.scale = Float32(scale)
        self.embed_scale = Float32(embed_scale)
        self.sliding_window = sliding_window
        self.layer_is_global = List[Int]()
        for i in range(n_layers):
            self.layer_is_global.append(layer_is_global[i])

        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

        self.layers = List[_G3LayerGpuF16]()
        for _ in range(n_layers):
            self.layers.append(
                _G3LayerGpuF16(
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](d_head),
                    self.ctx.enqueue_create_buffer[DType.float16](n_qkv * d_model),
                    self.ctx.enqueue_create_buffer[DType.float16](d_model * h_q * d_head),
                    self.ctx.enqueue_create_buffer[DType.float16](2 * d_ff * d_model),
                    self.ctx.enqueue_create_buffer[DType.float16](d_model * d_ff),
                    self.ctx.enqueue_create_buffer[DType.float32](max_ctx * h_kv * d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](max_ctx * h_kv * d_head),
                )
            )

        self.embed = self.ctx.enqueue_create_buffer[DType.float16](vocab * d_model)
        self.final_norm = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.cos_global = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
        self.sin_global = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
        self.cos_local = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
        self.sin_local = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)

        self.hidden = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.qkv = self.ctx.enqueue_create_buffer[DType.float32](n_qkv)
        self.q_rot = self.ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
        self.attn_out = self.ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
        self.o_tmp = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.act = self.ctx.enqueue_create_buffer[DType.float32](d_ff)
        self.d_tmp = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.logits = self.ctx.enqueue_create_buffer[DType.float32](vocab)
        self.blk_val = self.ctx.enqueue_create_buffer[DType.float32](_LM_BLOCKS)
        self.blk_idx = self.ctx.enqueue_create_buffer[DType.int32](_LM_BLOCKS)
        self.out_val = self.ctx.enqueue_create_buffer[DType.float32](1)
        self.out_idx = self.ctx.enqueue_create_buffer[DType.int32](1)
        self.host_val = self.ctx.enqueue_create_host_buffer[DType.float32](1)
        self.host_idx = self.ctx.enqueue_create_host_buffer[DType.int32](1)
        self.host_logits = self.ctx.enqueue_create_host_buffer[DType.float32](vocab)

        var t = G3_PF_TILE
        self.pf_tokens = self.ctx.enqueue_create_buffer[DType.int32](t)
        self.pf_hidden = self.ctx.enqueue_create_buffer[DType.float32](t * d_model)
        self.pf_xn = self.ctx.enqueue_create_buffer[DType.float32](t * d_model)
        self.pf_qkv = self.ctx.enqueue_create_buffer[DType.float32](t * n_qkv)
        self.pf_q_rot = self.ctx.enqueue_create_buffer[DType.float32](t * h_q * d_head)
        self.pf_attn = self.ctx.enqueue_create_buffer[DType.float32](t * h_q * d_head)
        self.pf_act = self.ctx.enqueue_create_buffer[DType.float32](t * d_ff)
        self.pf_branch = self.ctx.enqueue_create_buffer[DType.float32](t * d_model)
        self.pf_gu = self.ctx.enqueue_create_buffer[DType.float32](t * 2 * d_ff)

        self.tc_a16 = self.ctx.enqueue_create_buffer[DType.float16](1)
        self.tc_c16 = self.ctx.enqueue_create_buffer[DType.float16](1)
        self.tc_ready = -1
        self.pf_tc_q16 = self.ctx.enqueue_create_buffer[DType.float16](1)
        self.pf_tc_p16 = self.ctx.enqueue_create_buffer[DType.float16](1)
        self.pf_tc_scores = self.ctx.enqueue_create_buffer[DType.float32](1)
        self.pf_tc_o32 = self.ctx.enqueue_create_buffer[DType.float32](1)
        self.pf_tc_k16 = self.ctx.enqueue_create_buffer[DType.float16](1)
        self.pf_tc_v16 = self.ctx.enqueue_create_buffer[DType.float16](1)
        self.pf_xn16 = self.ctx.enqueue_create_buffer[DType.float16](1)
        self.pf_gu16 = self.ctx.enqueue_create_buffer[DType.float16](1)
        self.pf_act16 = self.ctx.enqueue_create_buffer[DType.float16](1)
        self.pf_attn16 = self.ctx.enqueue_create_buffer[DType.float16](1)
        self.pf_fa_scale = self.ctx.enqueue_create_buffer[DType.float32](1)
        self.pf_fa_armed = 0
        @parameter
        if G3_ROUND5_FLAGS:
            # ~151 MB at 27B's shapes (t=1024, d_model=5376, d_ff=21504, h_q*d=4096):
            # pf_gu16 88 MB + pf_act16 44 MB + pf_xn16 11 MB + pf_attn16 8 MB. These REPLACE
            # traffic rather than add it — every byte here is a byte the shim's per-call
            # f32->f16 A convert (or the f32 gate/up C round trip) no longer moves.
            self.pf_xn16 = self.ctx.enqueue_create_buffer[DType.float16](t * d_model)
            self.pf_gu16 = self.ctx.enqueue_create_buffer[DType.float16](t * 2 * d_ff)
            self.pf_act16 = self.ctx.enqueue_create_buffer[DType.float16](t * d_ff)
            self.pf_attn16 = self.ctx.enqueue_create_buffer[DType.float16](t * h_q * d_head)
        @parameter
        if TC_SHIM_BUILD:
            # The weights ARE the f16 B operand already; the scratch is ONLY the f32->f16 A
            # staging (rows x the widest K role) + the rung-2 f16-C staging (rows x the widest
            # N role). ~130 MB at 27B's shapes; sized for the largest tile `prefill` dispatches.
            var max_k = d_model
            if h_q * d_head > max_k:
                max_k = h_q * d_head
            if d_ff > max_k:
                max_k = d_ff
            var max_n = n_qkv
            if 2 * d_ff > max_n:
                max_n = 2 * d_ff
            self.tc_a16 = self.ctx.enqueue_create_buffer[DType.float16](t * max_k)
            self.tc_c16 = self.ctx.enqueue_create_buffer[DType.float16](t * max_n)
            # Tensor-core prefill-attention scratch (vLLM-flip lever): head-major Q f16,
            # scores f32 / P f16 over [tile, max_ctx], PV output f32. ~220 MB at 27B.
            self.pf_tc_q16 = self.ctx.enqueue_create_buffer[DType.float16](t * h_q * d_head)
            self.pf_tc_o32 = self.ctx.enqueue_create_buffer[DType.float32](t * h_q * d_head)
            self.pf_tc_scores = self.ctx.enqueue_create_buffer[DType.float32](
                t * h_q * max_ctx)
            self.pf_tc_p16 = self.ctx.enqueue_create_buffer[DType.float16](t * h_q * max_ctx)
            # K/V f16 staging for the f32-KV cache (layout-preserving [max_ctx, h_kv, d]).
            self.pf_tc_k16 = self.ctx.enqueue_create_buffer[DType.float16](
                max_ctx * h_kv * d_head)
            self.pf_tc_v16 = self.ctx.enqueue_create_buffer[DType.float16](
                max_ctx * h_kv * d_head)
            self.tc_ready = 0

        # decode-graph arm buffers (lazy capture in _build_decode_graph; allocated here so every
        # pointer is resident before capture).
        self.step_state = self.ctx.enqueue_create_buffer[DType.int64](3)
        self.host_state = self.ctx.enqueue_create_host_buffer[DType.int64](3)
        self.token_log = self.ctx.enqueue_create_buffer[DType.int64](max_ctx)
        self.host_token_log = self.ctx.enqueue_create_host_buffer[DType.int64](max_ctx)
        self.sk_m = self.ctx.enqueue_create_buffer[DType.float32](h_q * GEMMA3_GRAPH_N_SPLITS)
        self.sk_l = self.ctx.enqueue_create_buffer[DType.float32](h_q * GEMMA3_GRAPH_N_SPLITS)
        self.sk_o = self.ctx.enqueue_create_buffer[DType.float32](
            h_q * GEMMA3_GRAPH_N_SPLITS * d_head
        )
        self.decode_graph = Optional[DeviceGraph]()
        self.decode_graph_built = False

    def device_name(self) raises -> String:
        return self.ctx.name()

    def upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_g: List[Float64], sin_g: List[Float64],
        cos_l: List[Float64], sin_l: List[Float64], n_pos: Int,
    ) raises -> Int:
        var n_pairs = self.d_head // 2
        if n_pos > self.max_ctx:
            return RESIDENT_ERR_CONTEXT_FULL
        var s = _narrow_into_f16(self.embed, embed, self.vocab * self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(self.final_norm, final_norm, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        if len(cos_g) < n_pos * n_pairs or len(sin_g) < n_pos * n_pairs:
            return RESIDENT_ERR_UPLOAD_LENGTH
        if len(cos_l) < n_pos * n_pairs or len(sin_l) < n_pos * n_pairs:
            return RESIDENT_ERR_UPLOAD_LENGTH
        with self.cos_global.map_to_host() as h:
            for i in range(n_pos * n_pairs):
                h[i] = Float32(cos_g[i])
        with self.sin_global.map_to_host() as h:
            for i in range(n_pos * n_pairs):
                h[i] = Float32(sin_g[i])
        with self.cos_local.map_to_host() as h:
            for i in range(n_pos * n_pairs):
                h[i] = Float32(cos_l[i])
        with self.sin_local.map_to_host() as h:
            for i in range(n_pos * n_pairs):
                h[i] = Float32(sin_l[i])
        return RESIDENT_OK

    def upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], ln3: List[Float64], ln4: List[Float64],
        qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        if layer < 0 or layer >= self.n_layers:
            return RESIDENT_ERR_UPLOAD_LENGTH
        ref lw = self.layers[layer]
        var s = _narrow_into(lw.ln1, ln1, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.ln2, ln2, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.ln3, ln3, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.ln4, ln4, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.qn, qn, self.d_head, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.kn, kn, self.d_head, 0)
        if s != RESIDENT_OK:
            return s

        var n_q = self.h_q * self.d_head
        var n_kv = self.h_kv * self.d_head
        s = _narrow_transposed_into_f16(lw.w_qkv, wq, self.d_model, n_q, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_qkv, wk, self.d_model, n_kv, n_q)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_qkv, wv, self.d_model, n_kv, n_q + n_kv)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_o, wo, n_q, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_gu, wgate, self.d_model, self.d_ff, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_gu, wup, self.d_model, self.d_ff, self.d_ff)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_down, wdown, self.d_ff, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        return RESIDENT_OK

    def ensure_tc_ready(mut self) raises -> Int:
        """Bind the TC shim's cuBLAS handle once, at session-setup time.

        Idempotent: the `tc_ready == 0` guard makes every call after the first a no-op, and the
        three outcome branches (bound / legacy-bind failed / init failed -> native chain) and
        their banners are unchanged. `seal()` calls this so a long-lived session binds the handle
        during setup; `prefill()` still calls it as a fallback for a caller that never seals.
        """
        @parameter
        if TC_SHIM_BUILD:
            if self.tc_ready == 0:
                var r = _tc_init()
                if r == 0:
                    @parameter
                    if G3_STREAM:
                        # bind the handle to the legacy default stream — Mojo's default
                        # stream is device-ordered against it (legacy_probe.mojo), so
                        # the async seams below need no host sync at all.
                        var rb = _tc_use_legacy_stream()
                        if rb != 0:
                            self.tc_ready = -1
                            print("gemma3-f16: legacy-stream binding FAILED, status", rb,
                                  "last_error:", _tc_last_error(),
                                  "| prefill stays on the native chain")
                        else:
                            self.tc_ready = 1
                            print("gemma3-f16: TC shim cuBLAS handle BOUND to the LEGACY",
                                  "stream | G3_STREAM: zero-sync async GemmEx seams")
                    else:
                        self.tc_ready = 1
                        print("gemma3-f16: TC shim cuBLAS handle BOUND | full-tile",
                              "prefill GEMMs ride the HMMA seam")
                else:
                    self.tc_ready = -1
                    print("gemma3-f16: TC shim init FAILED, status", r,
                          "last_error:", _tc_last_error(),
                          "| prefill stays on the native chain")
        return RESIDENT_OK

    def _prime_prefill_modules(mut self) raises:
        """Make every CUDA module the prefill path can dispatch resident before the first request.

        CUDA loads modules lazily, so an unprimed session charges the first request for the JIT:
        on H200 at 1410 MHz, nsys CUPTI runtime records inside the prefill region show 9x
        `cuModuleLoadDataEx` (31.963 ms) + 12x `cuLibraryLoadData` (15.168 ms) + one 9.300 ms
        first-launch `cudaLaunchKernel`, against 67.93 ms of GPU idle in a 103.848 ms kernel span
        -- the idle is fully accounted for by host-side one-time work. Binding the cuBLAS handle
        alone recovers only ~17 ms of it, because the rest is per-kernel module residency.

        cuBLAS selects a distinct algorithm, and therefore a distinct module, per GEMM shape, so
        one priming shape does not cover the others. The shapes primed here are the ones the
        shape-fact gates switch on: `TC_MIN_M` (the HMMA seams engage), 256 (`use_tc_attn`
        engages), 512, and `G3_PF_TILE` (the full tile that carries a long prompt's bulk).
        Priming only the full tile measured 56.893 ms for a 256-token first request vs 37.374 ms
        with the bands primed. `CUDA_MODULE_LOADING=EAGER` is not a substitute: it measured
        3136.308 ms, because it pulls every module in the image into the first CUDA call.

        The dummy prompts are all-zero token ids (0 is valid). `prefill()` always restarts at
        pos = 0 and overwrites the same KV slots, so priming leaves no state a real request does
        not immediately replace, and the generated tokens are discarded.
        """
        var shapes = List[Int]()
        shapes.append(Int(TC_MIN_M))
        shapes.append(256)
        shapes.append(512)
        shapes.append(Int(G3_PF_TILE))
        for i in range(len(shapes)):
            var m = shapes[i]
            if m < 1 or m > self.max_ctx:
                continue
            var dummy = List[Int]()
            for _ in range(m):
                dummy.append(0)
            self.prefill(dummy)

    def seal(mut self) raises -> Int:
        # Pay the session's one-time costs here, at setup, so no request is charged for them:
        # the cuBLAS handle bind, the round-5 lever arming, then the lazy per-kernel CUDA
        # module loads (which must come LAST so it also primes whatever the armed levers
        # dispatch — a priming pass that runs before the lever arms primes the wrong kernels).
        self.ensure_tc_ready()
        @parameter
        if G3_PF_FA:
            self._arm_fused_fa()
        @parameter
        if CUDA_GEMMA3_BUILD:
            self._print_round5_flag_audit()
            self._prime_prefill_modules()
        self.ctx.synchronize()
        return RESIDENT_OK

    def _arm_fused_fa(mut self) raises:
        """Publish the attention scale to the device cell the fused kernel dereferences, then
        ARM the lever only if the shim verified its WMMA accumulator element -> (row, col)
        mapping ON THIS DEVICE.

        The WMMA API documents that layout as opaque and `_fa_g3_window_kernel` indexes it by
        row for the causal+window mask, the online-softmax O rescale and the final divide, so
        the mapping is checked on device (`_tc_fa_layout_probe`: A=I, B staged so acc[r][c]
        reads back r*16+c, plus an f16-accumulator `store_matrix_sync` round trip; the buffer
        is zeroed first so a fragment carrying FEWER elements than assumed fails rather than
        passing by luck). A disagreement leaves `pf_fa_armed == 0`, every dispatch then
        declines, and the prefill keeps the five-pass TC chain — a declined lever can never
        masquerade as a measured fused-attention number.

        The verdict is printed once per session so it is a per-binary line in the run log,
        never a silent perf cliff. Runs at seal(), outside every timed region."""
        self.ctx.enqueue_function[_pf_fill_scale_kernel](
            self.pf_fa_scale.unsafe_ptr(), self.scale,
            grid_dim=1, block_dim=1,
        )
        self.ctx.synchronize()
        var rfa = _tc_fa_layout_probe()
        if rfa == 0 and self.tc_ready == 1 and self.d_head == 128 \
                and self.h_q % self.h_kv == 0:
            self.pf_fa_armed = 1
            print("gemma3-f16: fused windowed TC flash attention ARMED | WMMA accumulator",
                  "layout verified on device | BN =", _G3_PF_FA_BN, "| d_head =",
                  self.d_head, "| GQA g =", self.h_q // self.h_kv, "| sliding_window =",
                  self.sliding_window, "| f16 O =", G3_PF_F16ATTN)
        else:
            self.pf_fa_armed = 0
            print("gemma3-f16: fused windowed TC flash attention DECLINED, status", rfa,
                  "| tc_ready =", self.tc_ready, "| d_head =", self.d_head, "| h_q/h_kv =",
                  self.h_q, "/", self.h_kv,
                  "| prefill attention keeps the five-pass TC chain")
        # ROUND 6 (`-D ALGENTA_G3_PF_FA2`): the v2 kernel has its OWN on-device layout probe —
        # it indexes raw mma.sync m16n8k16 A/B/D fragments and both ldmatrix roles, not the
        # WMMA accumulator — and the same rule applies: a declined v2 must be a printed
        # DECLINED that keeps round 5's WMMA kernel, never a silent perf cliff or, worse, a
        # permuted-row attention matrix presented as a measured FA2 number. The dispatch does
        # not gate on this verdict (the shim caches it and returns -311 per call, which falls
        # back), exactly like the 7B lane's `_PF_FA2_SHIP_VARIANT` wiring.
        @parameter
        if G3_PF_FA2:
            var rfa2 = _tc_fa2_layout_probe()
            if rfa2 == 0 and self.tc_ready == 1 and self.d_head == 128 \
                    and self.h_q % self.h_kv == 0:
                print("gemma3-f16: fused windowed TC flash attention v2 ARMED | raw",
                      "mma.sync m16n8k16 A/B/D + both ldmatrix roles verified on device |",
                      "BN =", _G3_PF_FA_BN, "| kv32 =", _G3_PF_FA_KV32,
                      "| cp.async double buffer from n_keys >= (0 = never) =",
                      _G3_PF_FA2_DBUF_MIN_N if _G3_PF_FA_KV32 == 0 else 0,
                      "| d_head =", self.d_head, "| GQA g =", self.h_q // self.h_kv,
                      "| sliding_window =", self.sliding_window, "| f16 O =", G3_PF_F16ATTN)
            else:
                print("gemma3-f16: fused windowed TC flash attention v2 DECLINED, status",
                      rfa2, "| d_head =", self.d_head, "| h_q/h_kv =", self.h_q, "/",
                      self.h_kv, "| prefill attention keeps round 5's WMMA window kernel")

    def _print_round5_flag_audit(self):
        """── THE FLAG AUDIT BANNER ──

        One print per numeric-path flag, INSIDE that flag's own `@parameter if`, so the literal
        only exists in a binary that actually has the flag: `strings` on the shipped binary is
        then a POSITIVE audit of the numerics it will run, and an absent TCFLAG line means OFF
        (a build cannot print a line it lacks). This closes the failure mode that voided the
        first gemma-3-27b H200 column — a rebuild that had silently dropped
        `-D ALGENTA_G3_STREAM`, was wrong at oracle index 0 on 5/6 prompts, and said so nowhere.
        `scripts/audit_tc_flags.sh` greps exactly these literals.

        Deliberately NOT nested under `-D ALGENTA_G3_PF_FA`: the resolved-bool `G3 FLAGS:` line
        is the gemma-3 family's positive control (the audit aborts rather than report an empty
        flag set if a binary that should carry it does not), and the F16NORM / F16MLP banners
        must be auditable in an arm that measures them WITHOUT the fused attention lever.
        Prints at seal(), outside every timed region, once per session."""
        print("G3 FLAGS: TCATTN =", G3_PF_TCATTN, "| ATTN_FLASH =", G3_PF_ATTN_FLASH,
              "| FA =", G3_PF_FA, "| FA2 =", G3_PF_FA2, "| F16NORM =", G3_PF_F16NORM,
              "| F16MLP =", G3_PF_F16MLP, "| F16ATTN =", G3_PF_F16ATTN, "| ROPE2 =",
              G3_PF_ROPE2,
              "| STREAM =", G3_STREAM,
              "| GEGLU_U4 =", _G3_GEGLU_U4, "| FA_BN =", _G3_PF_FA_BN, "| FA_KV32 =",
              _G3_PF_FA_KV32, "| FA_MIN_M =", _G3_PF_FA_MIN_M, "| max_ctx =", self.max_ctx)
        @parameter
        if G3_PF_ROPE2:
            print("TCFLAG ALGENTA_G3_PF_ROPE2=1 (warp-per-head q/k-norm + RoPE + KV-write,",
                  "zero barriers, bit-identical to the block-per-head twin)")
        @parameter
        if G3_PF_ROPEVEC:
            print("TCFLAG ALGENTA_G3_PF_ROPEVEC=1 (DEFAULT ON since round 13; opt out with",
                  "ALGENTA_G3_PF_NO_ROPEVEC) half-warp-per-head RoPE with 16-byte",
                  "_ld4/_st4 quads, 16 heads per block; re-associates the qk_norm reduction",
                  "so it is NOT bit-identical to ROPE2 — certified by the fp32 oracle in",
                  "round 12 and measured at -1.687 ms on rag4096 (14.5x its drift armor) in",
                  "round 13")
        @parameter
        if G3_PF_FA:
            print("TCFLAG ALGENTA_G3_PF_FA=1 (fused windowed tensor-core FlashAttention-2,",
                  "BN =", _G3_PF_FA_BN, ", kv32 =", _G3_PF_FA_KV32, ") — replaces the Q pack",
                  "/ QK^T / masked softmax / PV / O unpack / KV staging chain")
        @parameter
        if G3_PF_FA2:
            print("TCFLAG ALGENTA_G3_PF_FA2=1 (window kernel v2: raw mma.sync m16n8k16,",
                  "P in registers, direct-to-global epilogue, cp.async double buffer from",
                  "n_keys >=", _G3_PF_FA2_DBUF_MIN_N if _G3_PF_FA_KV32 == 0 else 0, ")")
        @parameter
        if G3_PF_GQA2:
            print("TCFLAG ALGENTA_G3_PF_GQA2=1 (DEFAULT ON since round 13; opt out with",
                  "ALGENTA_G3_PF_NO_GQA2) window kernel v3 GQA-PACKED: rt =",
                  _G3_PF_GQA2_RT, "row-tiles per warp spent on", _G3_PF_GQA2_RT,
                  "query heads of ONE kv head, so grid.y is h_q/", _G3_PF_GQA2_RT,
                  "and each K/V ldmatrix feeds", _G3_PF_GQA2_RT, "mma; engaged only from",
                  "n_keys >=", _G3_PF_GQA2_MIN_NKEYS, "where the probe measures -12..-21%,",
                  "and BIT-IDENTICAL to v2 — 216/216 BITIDENT-v2, 0 BITDIFF, 0 FAIL at",
                  "BN=32 and BN=64; below the threshold the dispatch is v2 unchanged.",
                  "Measured RESOLVED at -3.397 ms on rag4096 (6.4x its drift armor) in",
                  "round 11; with ROPEVEC it is the round-13 default arm at 1.1140x")
        @parameter
        if _G3_PF_KV16:
            print("TCFLAG ALGENTA_G3_PF_KV16=1 (fused attention reads the f16 K/V staging",
                  "twin (v8 staging, bit-exact operands); cp.async double buffer legal)")
        @parameter
        if _G3_PF_BN32:
            print("TCFLAG ALGENTA_G3_PF_BN32=1 (fused-attention key-block width 32)")
        @parameter
        if _G3_PF_BN128:
            print("TCFLAG ALGENTA_G3_PF_BN128=1 (fused-attention key-block width 128)")
        @parameter
        if G3_PF_F16NORM:
            print("TCFLAG ALGENTA_G3_PF_F16NORM=1 (both rmsnorms write the f16 pre-staged A)")
        @parameter
        if G3_PF_F16MLP:
            print("TCFLAG ALGENTA_G3_PF_F16MLP=1 (f16 gate/up C + f16 GeGLU -> f16 down A)")
        @parameter
        if G3_PF_F16ATTN:
            print("TCFLAG ALGENTA_G3_PF_F16ATTN=1 (fused attention writes the f16 o_proj A)")
        @parameter
        if G3_STREAM:
            print("TCFLAG ALGENTA_G3_STREAM=1 (legacy-stream-bound cuBLAS, zero seam syncs)")
        @parameter
        if G3_PF_TCATTN:
            print("TCFLAG ALGENTA_G3_PF_TCATTN=1 (five-pass tensor-core prefill attention)")

    def prefill(mut self, prompt_ids: List[Int]) raises -> _StepOut:
        """The WHOLE prompt, tiled — the f16-weight twin of `_CudaResidentGemma3.prefill`'s
        ten-dispatch four-norm plan, plus the tensor-core seam: full tiles (m >= TC_MIN_M) ride
        cuBLAS HMMA GemmEx over the RESIDENT f16 weights under TC_SHIM_BUILD (the weights ARE
        the f16 B operand — no staging twin; that is the fit-fact this arm exists for), with the
        GeGLU combine as the native row-elementwise epilogue; short tiles and flag-off builds
        run the native v2h f32-accumulation chain. Returns the greedy FIRST generated token —
        the same `_StepOut` contract `step` uses; the caller chains `step(...)` starting at
        `pos = len(prompt_ids)`."""

        @parameter
        if not CUDA_GEMMA3_BUILD:
            return _StepOut(-1, 0.0, 0, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            var n_prompt = len(prompt_ids)
            if n_prompt < 1:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)
            if n_prompt > self.max_ctx:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_CONTEXT_FULL)
            for i in range(n_prompt):
                if prompt_ids[i] < 0 or prompt_ids[i] >= self.vocab:
                    return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)

            # Idempotent: `seal()` has normally bound the handle already, so this is a no-op for
            # a sealed session and still covers a caller that never seals.
            self.ensure_tc_ready()

            var n_q = self.h_q * self.d_head
            var n_qkv = (self.h_q + 2 * self.h_kv) * self.d_head
            var issued = 0
            var pos = 0
            var last_m = 0
            while pos < n_prompt:
                var m = G3_PF_TILE
                if n_prompt - pos < m:
                    m = n_prompt - pos
                last_m = m

                var use_tc = False
                @parameter
                if TC_SHIM_BUILD:
                    use_tc = self.tc_ready == 1 and m >= TC_MIN_M

                # ── this chunk's token ids, uploaded once ──
                with self.pf_tokens.map_to_host() as h:
                    for i in range(m):
                        h[i] = Int32(prompt_ids[pos + i])
                self.ctx.synchronize()

                # ── the scaled embedding rows, gathered on-device from the resident table ──
                self.ctx.enqueue_function[_pf_embed_rows_g3_kernel_f16](
                    self.pf_hidden.unsafe_ptr(), self.embed.unsafe_ptr(),
                    self.pf_tokens.unsafe_ptr(),
                    Int64(self.d_model), Int64(m), self.embed_scale,
                    grid_dim=_ceil_div(self.d_model, _TG) * m, block_dim=_TG,
                )
                issued += 1

                for layer in range(self.n_layers):
                    ref lw = self.layers[layer]
                    var is_global = self.layer_is_global[layer]

                    # 1 ── rmsnorm(input_layernorm) over every row. Under
                    #    -D ALGENTA_G3_PF_F16NORM the TC seam's A operand is written f16 BY
                    #    ITS OWN PRODUCER, so this dispatches the f16 twin and step 2 takes it
                    #    pre-staged. The choice rides `use_tc`, never the flag alone: the
                    #    native v2h chain (short tiles, or a shim-less build) reads the f32
                    #    row block, so a sub-TC_MIN_M tile must still get f32.
                    var xn_f16 = False
                    @parameter
                    if G3_PF_F16NORM:
                        xn_f16 = use_tc
                    if xn_f16:
                        self.ctx.enqueue_function[_pf_rmsnorm_rows_f16_kernel](
                            self.pf_xn16.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                            lw.ln1.unsafe_ptr(),
                            Int64(self.d_model), self.eps, Int64(m),
                            grid_dim=m, block_dim=_TG,
                        )
                    else:
                        self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                            self.pf_xn.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                            lw.ln1.unsafe_ptr(),
                            Int64(self.d_model), self.eps, Int64(m),
                            grid_dim=m, block_dim=_TG,
                        )
                    # 2 ── fused Q/K/V projection (ASSIGN) — TC seam or the v2h kernel
                    if use_tc:
                        @parameter
                        if not G3_STREAM:
                            self.ctx.synchronize()
                        var r = 0
                        if xn_f16:
                            r = _tc_gemm_f16_32c_pre_async(
                                Int(self.pf_xn16.unsafe_ptr()),
                                Int(lw.w_qkv.unsafe_ptr()),
                                m, self.d_model, n_qkv,
                                Int(self.pf_qkv.unsafe_ptr()), 0)
                        else:
                            r = _tc_gemm_dispatch_auto(
                                Int(self.pf_xn.unsafe_ptr()),
                                Int(lw.w_qkv.unsafe_ptr()), 0,
                                m, self.d_model, n_qkv,
                                Int(self.tc_a16.unsafe_ptr()),
                                Int(self.tc_c16.unsafe_ptr()),
                                Int(self.pf_qkv.unsafe_ptr()), 0)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                    else:
                        self.ctx.enqueue_function[_pf_gemm_assign_kernel_v2h](
                            self.pf_qkv.unsafe_ptr(), self.pf_xn.unsafe_ptr(),
                            lw.w_qkv.unsafe_ptr(),
                            Int64(m), Int64(self.d_model), Int64(n_qkv),
                            grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(n_qkv, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                    # 3 ── q_norm + k_norm + per-class RoPE + the in-place KV-cache write
                    var cos_p = self.cos_global.unsafe_ptr() if is_global == 1 \
                        else self.cos_local.unsafe_ptr()
                    var sin_p = self.sin_global.unsafe_ptr() if is_global == 1 \
                        else self.sin_local.unsafe_ptr()
                    var use_rope2 = False
                    @parameter
                    if G3_PF_ROPE2:
                        # fact-driven capability gate: the warp-per-head twin's lane contract is
                        # d_head == 4 * WARP_SIZE == 128, which is what puts both halves of a
                        # RoPE pair (e, e + d_head/2) in one lane and makes the twin's
                        # stride-64/32 reduction steps intra-lane. Any other head width stays
                        # byte-for-byte on the block-per-head kernel. (Written as the literal
                        # 128 to match this session's other head-dim capability gates, which
                        # do not import WARP_SIZE.)
                        use_rope2 = self.d_head == 128
                    # ROUND 7, and DEFAULT ON SINCE ROUND 13 (opt out with
                    # `-D ALGENTA_G3_PF_NO_ROPEVEC`): the vector twin REPLACES ROPE2's
                    # kernel rather than the block-per-head one, and it is eligible only where
                    # ROPE2 itself is — same `d_head == 128` lane contract. Gating it on
                    # `use_rope2` rather than on its own head-dim test means a shape ROPE2
                    # declines can never silently fall through to a different re-association of
                    # the qk_norm reduction; it stays byte-for-byte on the twin ROPE2 declined to.
                    # Assigned inside a `@parameter if`, so with the flag off `use_ropev` is
                    # provably False, the vector arm is dead and the emitted code is unchanged.
                    var use_ropev = False
                    @parameter
                    if G3_PF_ROPEVEC:
                        use_ropev = use_rope2
                    if use_ropev:
                        self.ctx.enqueue_function[_pf_ropewrt_warps_vec_kernel](
                            self.pf_q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                            self.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                            cos_p, sin_p,
                            Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                            self.eps, Int64(m),
                            Int64(1),  # gemma3 always has QK-norm
                            Int64(_ceil_div(self.h_q + self.h_kv, _G3_ROPEV_HEADS_PER_BLOCK)),
                            grid_dim=m * _ceil_div(self.h_q + self.h_kv,
                                                  _G3_ROPEV_HEADS_PER_BLOCK),
                            block_dim=_G3_ROPE_NTHREADS,
                        )
                    elif use_rope2:
                        self.ctx.enqueue_function[_pf_ropewrt_warps_kernel](
                            self.pf_q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                            self.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                            cos_p, sin_p,
                            Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                            self.eps, Int64(m),
                            Int64(1),  # gemma3 always has QK-norm
                            Int64(_ceil_div(self.h_q + self.h_kv, _G3_ROPE_WARPS_PER_BLOCK)),
                            grid_dim=m * _ceil_div(self.h_q + self.h_kv,
                                                  _G3_ROPE_WARPS_PER_BLOCK),
                            block_dim=_G3_ROPE_NTHREADS,
                        )
                    else:
                        self.ctx.enqueue_function[_pf_ropewrt_kernel](
                            self.pf_q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                            self.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                            cos_p, sin_p,
                            Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                            self.eps, Int64(m),
                            Int64(1),  # gemma3 always has QK-norm
                            grid_dim=(self.h_q + self.h_kv) * m, block_dim=self.d_head,
                        )
                    # 4 ── windowed causal attention (per-row key lower bound)
                    var use_pf_flash = False
                    @parameter
                    if G3_PF_ATTN_FLASH:
                        # fact-driven capability dispatch: the flash twin's lane contract is
                        # d_head == 128 == WARP_SIZE * 4; any other head dim stays
                        # byte-for-byte on the tiled barrier-tree kernel.
                        use_pf_flash = self.d_head == 128
                    var use_tc_attn = False
                    @parameter
                    if G3_PF_TCATTN:
                        # fact-driven capability gate: d_head == 128 (the strided-batched
                        # lane contract) + the TC shim ready. This session's KV cache is f32,
                        # so the K/V tile is staged to f16 per layer below. The strided-
                        # batched GEMMs only amortize at larger tiles — measured crossover on
                        # the H100: TC attention wins from m >= 256 (121.7 vs 132.3 flash at
                        # 256; 154.3 vs 178.9 at 550) but loses at m=160 (152.9 vs 121.1), so
                        # the dispatch is shape-fact-gated on the tile row count, never the
                        # model name.
                        use_tc_attn = self.d_head == 128 and self.tc_ready == 1 and m >= 256
                    # ── ROUND-5 LEVER (`-D ALGENTA_G3_PF_FA`): ONE fused windowed
                    #    tensor-core FlashAttention-2 kernel INSTEAD OF the five-pass chain
                    #    below. It deletes (i) the head-major Q pack, (iv) the masked softmax,
                    #    (vi) the head-major O unpack and (ii) the K/V f32->f16 staging, and
                    #    folds (iii)+(v) — the QK^T and PV strided-batched GemmEx — into its
                    #    own `wmma::mma_sync` HMMA, so the `[h_q*m, n_keys]` f32 score matrix
                    #    (134 MB/layer at m=n_keys=1024, 8.3 GB over a pp1024 prefill) and its
                    #    67 MB f16 P twin are never materialized. It also does something the
                    #    chain structurally cannot: the sliding window is a KEY-BLOCK RANGE, so
                    #    a local layer never loads the keys it would mask away.
                    #
                    #    The gate is shape facts only, never a model name: `pf_fa_armed` is set
                    #    at seal() only after the shim verified its WMMA accumulator layout ON
                    #    THIS DEVICE, d_head 128 is the one head width the kernel implements,
                    #    integral GQA is what its `hk = h / (h_q/h_kv)` mapping requires, and
                    #    `m >= _G3_PF_FA_MIN_M` is the tile-row crossover the five-pass chain's
                    #    own dispatch uses (kept identical so the A/B moves one thing).
                    #
                    #    DECLINE IS A FALLBACK, NOT AN ERROR: -301 (wrong head_dim), -304
                    #    (non-integral GQA), -305 (out-of-list bn/kv32/of16 selection) and -310
                    #    (the accumulator-layout probe disagreed) all leave `attn_done` False,
                    #    so the five-pass chain below runs and produces the identical result it
                    #    always did. ANY OTHER status is a real CUDA failure and is returned as
                    #    one — a launch error must never be laundered into a slower-but-green
                    #    benchmark cell.
                    var attn_done = False
                    var attn_o_f16 = False
                    @parameter
                    if G3_PF_FA:
                        if self.pf_fa_armed == 1 and self.d_head == 128 \
                                and self.h_q % self.h_kv == 0 and m >= _G3_PF_FA_MIN_M:
                            var n_keys_fa = pos + m
                            var window_fa = 0 if is_global == 1 else self.sliding_window
                            var k_ptr = Int(lw.ck.unsafe_ptr())
                            var v_ptr = Int(lw.cv.unsafe_ptr())
                            @parameter
                            if _G3_PF_FA_KV32 == 0:
                                # f16 K/V route (round 5's control arm; a round-6 ship
                                # candidate under -D ALGENTA_G3_PF_KV16): stage the cache to
                                # the f16 twin first. `_v8` is the 8-elements-per-thread twin
                                # of the staging kernel, BIT-EXACT with it (`__floats2half2_rn`
                                # is the same RNe conversion of each half), and an operand it
                                # cannot vectorize falls back to the scalar kernel INSIDE the
                                # shim entry. h_kv*d_head = 2048 keeps `kvn` a multiple of 8
                                # at every n_keys, but the entry checks that itself.
                                var kvn = n_keys_fa * self.h_kv * self.d_head
                                var rk = _tc_stage_f32_to_f16_v8(
                                    Int(lw.ck.unsafe_ptr()),
                                    Int(self.pf_tc_k16.unsafe_ptr()), kvn)
                                if rk == 0:
                                    rk = _tc_stage_f32_to_f16_v8(
                                        Int(lw.cv.unsafe_ptr()),
                                        Int(self.pf_tc_v16.unsafe_ptr()), kvn)
                                if rk != 0:
                                    return _StepOut(-1, 0.0, issued,
                                                    RESIDENT_ERR_LAUNCH_FAILED)
                                k_ptr = Int(self.pf_tc_k16.unsafe_ptr())
                                v_ptr = Int(self.pf_tc_v16.unsafe_ptr())
                            var o_ptr = Int(self.pf_attn.unsafe_ptr())
                            var of16 = 0
                            @parameter
                            if G3_PF_F16ATTN:
                                o_ptr = Int(self.pf_attn16.unsafe_ptr())
                                of16 = 1
                            # ── ROUND-6 lever (`-D ALGENTA_G3_PF_FA2`): the v2 kernel takes
                            #    the same operands in the same layouts, so it is a drop-in for
                            #    round 5's. `dbuf` engages the cp.async double buffer only on
                            #    the f16 K/V route (cp.async copies raw bytes and cannot
                            #    convert, and the shim rejects the illegal combination with
                            #    -305 before any launch) and only from
                            #    `_G3_PF_FA2_DBUF_MIN_N` keys up, where the probe measures it
                            #    winning; below the crossover the same v2 kernel runs
                            #    single-buffered. A DECLINED v2 (-301 wrong head_dim, -304
                            #    non-integral GQA, -305 out-of-table selection, -311 the
                            #    on-device raw-mma layout probe disagreed) falls through to
                            #    round 5's WMMA kernel, which keeps its own
                            #    decline-to-five-pass-chain fallback. Any OTHER status is a
                            #    real CUDA failure and is returned as one. ──
                            var rfa = 0
                            @parameter
                            if G3_PF_FA2:
                                var dbuf_want = 0
                                @parameter
                                if _G3_PF_FA_KV32 == 0:
                                    dbuf_want = (
                                        1 if n_keys_fa >= _G3_PF_FA2_DBUF_MIN_N else 0
                                    )
                                # ── ROUND 9, and DEFAULT ON SINCE ROUND 13 (opt out with
                                #    `-D ALGENTA_G3_PF_NO_GQA2`): GQA-packed v3, but ONLY
                                #    where the probe measures it winning. `n_keys >=
                                #    _G3_PF_GQA2_MIN_NKEYS` is a measured shape fact, not a
                                #    model (see that constant for the decision table); below it
                                #    packing LOSES (+37.6% at pp256, +11.9% at pp1024) because
                                #    the per-CTA fixed costs — a twice-staged Q tile and RT=2's
                                #    255-register pressure with 24 of 36 instantiations spilling
                                #    — are not amortized over so few key blocks. The group-size
                                #    test is belt-and-braces: the shim also rejects an rt that
                                #    does not divide h_q/h_kv with -304, and that rejection is
                                #    what stops a packed CTA from reading the WRONG K/V for its
                                #    second tile and returning plausible-looking wrong numbers.
                                var gqa2_ok = False
                                var use_gqa2 = False
                                @parameter
                                if G3_PF_GQA2:
                                    use_gqa2 = True
                                if use_gqa2:
                                    if n_keys_fa >= _G3_PF_GQA2_MIN_NKEYS and (
                                            self.h_q % (self.h_kv * _G3_PF_GQA2_RT)) == 0:
                                        rfa = _tc_fa_g3_window3_async(
                                            Int(self.pf_q_rot.unsafe_ptr()), k_ptr, v_ptr,
                                            o_ptr, Int(self.pf_fa_scale.unsafe_ptr()),
                                            m, n_keys_fa, self.h_q, self.h_kv, self.d_head,
                                            pos, window_fa, _G3_PF_FA_BN, _G3_PF_FA_KV32,
                                            of16, dbuf_want, _G3_PF_GQA2_RT, 1)
                                        gqa2_ok = rfa == 0
                                        if not gqa2_ok and (
                                                rfa == -301 or rfa == -304 or rfa == -305
                                                or rfa == -311):
                                            # DECLINED, not failed: take v2's path exactly as if
                                            # GQA2 were off. A declined lever never masquerades.
                                            rfa = 0
                                        # Any OTHER non-zero status is a real launch failure and
                                        # is deliberately NOT retried on v2: masking it would
                                        # turn a CUDA error into a silently different kernel.
                                if not gqa2_ok and rfa == 0:
                                    rfa = _tc_fa_g3_window2_async(
                                        Int(self.pf_q_rot.unsafe_ptr()), k_ptr, v_ptr, o_ptr,
                                        Int(self.pf_fa_scale.unsafe_ptr()),
                                        m, n_keys_fa, self.h_q, self.h_kv, self.d_head, pos,
                                        window_fa, _G3_PF_FA_BN, _G3_PF_FA_KV32, of16,
                                        dbuf_want)
                                    if rfa == -301 or rfa == -304 or rfa == -305 \
                                            or rfa == -311:
                                        rfa = _tc_fa_g3_window_async(
                                            Int(self.pf_q_rot.unsafe_ptr()), k_ptr, v_ptr,
                                            o_ptr, Int(self.pf_fa_scale.unsafe_ptr()),
                                            m, n_keys_fa, self.h_q, self.h_kv, self.d_head,
                                            pos, window_fa, _G3_PF_FA_BN, _G3_PF_FA_KV32,
                                            of16)
                            else:
                                rfa = _tc_fa_g3_window_async(
                                    Int(self.pf_q_rot.unsafe_ptr()), k_ptr, v_ptr, o_ptr,
                                    Int(self.pf_fa_scale.unsafe_ptr()),
                                    m, n_keys_fa, self.h_q, self.h_kv, self.d_head, pos,
                                    window_fa, _G3_PF_FA_BN, _G3_PF_FA_KV32, of16)
                            if rfa == 0:
                                attn_done = True
                                attn_o_f16 = of16 == 1
                                use_tc_attn = False
                            elif rfa != -301 and rfa != -304 and rfa != -305 \
                                    and rfa != -310:
                                return _StepOut(-1, 0.0, issued,
                                                RESIDENT_ERR_LAUNCH_FAILED)
                    if attn_done:
                        issued += 1
                    elif use_tc_attn:
                        var n_keys_tc = pos + m
                        var gqa = self.h_q // self.h_kv
                        var gm = gqa * m
                        var window_arg = 0 if is_global == 1 else self.sliding_window
                        # (i) Q pack [m, h_q*d] f32 -> head-major [h_q, m, d] f16 (scaled)
                        self.ctx.enqueue_function[_pf_q_pack_hm_f16](
                            self.pf_tc_q16.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                            Int64(m), Int64(self.h_q), Int64(self.d_head), self.scale,
                            grid_dim=_ceil_div(self.h_q * m * self.d_head, _TG),
                            block_dim=_TG,
                        )
                        @parameter
                        if not G3_STREAM:
                            self.ctx.synchronize()
                        # (ii) K/V f32 cache -> f16 staging (layout-preserving, keys 0..n_keys)
                        var rkv = _tc_stage_f32_to_f16(
                            Int(lw.ck.unsafe_ptr()), Int(self.pf_tc_k16.unsafe_ptr()),
                            n_keys_tc * self.h_kv * self.d_head)
                        if rkv != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                        rkv = _tc_stage_f32_to_f16(
                            Int(lw.cv.unsafe_ptr()), Int(self.pf_tc_v16.unsafe_ptr()),
                            n_keys_tc * self.h_kv * self.d_head)
                        if rkv != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                        # (iii) QK^T: scores[h_kv, g*m, n_keys] = Q @ K^T (batched over KV heads)
                        var ra = _tc_bgemm_f16_async(
                            Int(self.pf_tc_q16.unsafe_ptr()),
                            Int(self.pf_tc_k16.unsafe_ptr()),
                            Int(self.pf_tc_scores.unsafe_ptr()),
                            gm, n_keys_tc, self.d_head,
                            self.d_head, self.h_kv * self.d_head, n_keys_tc,
                            gm * self.d_head, self.d_head, gm * n_keys_tc,
                            self.h_kv, 1)
                        if ra != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                        # (iv) causal+window masked softmax -> P f16
                        ra = _tc_attn_softmax_mask_async(
                            Int(self.pf_tc_scores.unsafe_ptr()),
                            Int(self.pf_tc_p16.unsafe_ptr()),
                            n_keys_tc, m, self.h_q, pos, window_arg)
                        if ra != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                        # (v) PV: out[h_kv, g*m, d] = P @ V (batched over KV heads)
                        ra = _tc_bgemm_f16_async(
                            Int(self.pf_tc_p16.unsafe_ptr()),
                            Int(self.pf_tc_v16.unsafe_ptr()),
                            Int(self.pf_tc_o32.unsafe_ptr()),
                            gm, self.d_head, n_keys_tc,
                            n_keys_tc, self.h_kv * self.d_head, self.d_head,
                            gm * n_keys_tc, self.d_head, gm * self.d_head,
                            self.h_kv, 0)
                        if ra != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                        # (vi) unpack head-major [h_q, m, d] -> position-major [m, h_q*d]
                        self.ctx.enqueue_function[_pf_attn_unpack_hm_f32](
                            self.pf_attn.unsafe_ptr(), self.pf_tc_o32.unsafe_ptr(),
                            Int64(m), Int64(self.h_q), Int64(self.d_head),
                            grid_dim=_ceil_div(self.h_q * m * self.d_head, _TG),
                            block_dim=_TG,
                        )
                        issued += 1
                    elif use_pf_flash:
                        self.ctx.enqueue_function[_pf_attn_window_flash_kernel](
                            self.pf_attn.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                            lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                            Int64(pos), Int64(self.h_q), Int64(self.h_kv),
                            Int64(self.d_head),
                            Int64(self.sliding_window), Int64(is_global), self.scale,
                            Int64(m),
                            grid_dim=_ceil_div(m, _G3_PF_FLASH_ROWS_PER_BLOCK) * self.h_q,
                            block_dim=_G3_PF_FLASH_NTHREADS,
                        )
                    else:
                        self.ctx.enqueue_function[_pf_attn_window_kernel](
                            self.pf_attn.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                            lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                            Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                            Int64(self.sliding_window), Int64(is_global), self.scale, Int64(m),
                            grid_dim=self.h_q * m, block_dim=self.d_head,
                        )
                    # 5 ── o_proj into the BRANCH scratch (ASSIGN — the post-branch norm
                    #      forbids the llama-style residual accumulate). Under
                    #      -D ALGENTA_G3_PF_F16ATTN the fused attention kernel already wrote
                    #      its output as the f16 A this GEMM reads, so the shim's convert pass
                    #      is skipped; `attn_o_f16` is set only by a dispatch that actually
                    #      ran, so a DECLINED fused attention falls back to the f32 A and the
                    #      ordinary ladder with it.
                    if use_tc:
                        @parameter
                        if not G3_STREAM:
                            self.ctx.synchronize()
                        var r = 0
                        if attn_o_f16:
                            r = _tc_gemm_f16_32c_pre_async(
                                Int(self.pf_attn16.unsafe_ptr()),
                                Int(lw.w_o.unsafe_ptr()),
                                m, n_q, self.d_model,
                                Int(self.pf_branch.unsafe_ptr()), 0)
                        else:
                            r = _tc_gemm_dispatch_auto(
                                Int(self.pf_attn.unsafe_ptr()),
                                Int(lw.w_o.unsafe_ptr()), 0,
                                m, n_q, self.d_model,
                                Int(self.tc_a16.unsafe_ptr()),
                                Int(self.tc_c16.unsafe_ptr()),
                                Int(self.pf_branch.unsafe_ptr()), 0)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                    else:
                        self.ctx.enqueue_function[_pf_gemm_assign_kernel_v2h](
                            self.pf_branch.unsafe_ptr(), self.pf_attn.unsafe_ptr(),
                            lw.w_o.unsafe_ptr(),
                            Int64(m), Int64(n_q), Int64(self.d_model),
                            grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.d_model, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                    # 6 ── hidden += rmsnorm(branch) * (1+w_post_attention), every row
                    self.ctx.enqueue_function[_pf_norm_accum_rows_kernel](
                        self.pf_hidden.unsafe_ptr(), self.pf_branch.unsafe_ptr(),
                        lw.ln2.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # 7 ── rmsnorm(pre_feedforward_layernorm) over every row (the f16 twin
                    #      under -D ALGENTA_G3_PF_F16NORM, for the same reason as step 1)
                    if xn_f16:
                        self.ctx.enqueue_function[_pf_rmsnorm_rows_f16_kernel](
                            self.pf_xn16.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                            lw.ln3.unsafe_ptr(),
                            Int64(self.d_model), self.eps, Int64(m),
                            grid_dim=m, block_dim=_TG,
                        )
                    else:
                        self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                            self.pf_xn.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                            lw.ln3.unsafe_ptr(),
                            Int64(self.d_model), self.eps, Int64(m),
                            grid_dim=m, block_dim=_TG,
                        )
                    # 8 ── gate/up + GeGLU — TC seam (+ native GeGLU epilogue) or the fused
                    #      v2h kernel. Under -D ALGENTA_G3_PF_F16MLP the gate/up GEMM writes
                    #      its [m, 2*d_ff] C as f16 and the GeGLU combine reads that f16 and
                    #      writes the f16 A down_proj takes directly: the layer's largest
                    #      non-GEMM traffic term (176 MB of f32 C written + 176 MB read back +
                    #      88 MB of f32 act written + 88 MB read + 44 MB of f16 A written at
                    #      m=1024, d_ff=21504) becomes 88 + 88 + 44 + 44.
                    var gu_f16 = False
                    @parameter
                    if G3_PF_F16MLP:
                        gu_f16 = use_tc
                    if use_tc:
                        @parameter
                        if not G3_STREAM:
                            self.ctx.synchronize()
                        var a_gu = Int(self.pf_xn.unsafe_ptr())
                        if xn_f16:
                            a_gu = Int(self.pf_xn16.unsafe_ptr())
                        elif gu_f16:
                            # F16MLP without F16NORM: the A still needs one convert, but into
                            # the f16 the 16c GEMM reads. The lever's own traffic win is the
                            # C + act round trip, which does not depend on the norm lever, so
                            # the two stay independently measurable.
                            var rs = _tc_stage_f32_to_f16(
                                Int(self.pf_xn.unsafe_ptr()),
                                Int(self.tc_a16.unsafe_ptr()), m * self.d_model)
                            if rs != 0:
                                return _StepOut(-1, 0.0, issued,
                                                RESIDENT_ERR_LAUNCH_FAILED)
                            a_gu = Int(self.tc_a16.unsafe_ptr())
                        var r = 0
                        if gu_f16:
                            r = _tc_gemm_f16_16c_pre_async(
                                a_gu, Int(lw.w_gu.unsafe_ptr()),
                                m, self.d_model, 2 * self.d_ff,
                                Int(self.pf_gu16.unsafe_ptr()), 0)
                        elif xn_f16:
                            r = _tc_gemm_f16_32c_pre_async(
                                a_gu, Int(lw.w_gu.unsafe_ptr()),
                                m, self.d_model, 2 * self.d_ff,
                                Int(self.pf_gu.unsafe_ptr()), 0)
                        else:
                            r = _tc_gemm_dispatch_auto(
                                a_gu, Int(lw.w_gu.unsafe_ptr()), 0,
                                m, self.d_model, 2 * self.d_ff,
                                Int(self.tc_a16.unsafe_ptr()),
                                Int(self.tc_c16.unsafe_ptr()),
                                Int(self.pf_gu.unsafe_ptr()), 0)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                        if gu_f16:
                            self.ctx.enqueue_function[_pf_geglu_rows_f16_kernel](
                                self.pf_act16.unsafe_ptr(), self.pf_gu16.unsafe_ptr(),
                                Int64(m * self.d_ff), Int64(self.d_ff),
                                grid_dim=_ceil_div(m * self.d_ff, _TG), block_dim=_TG,
                            )
                        else:
                            self.ctx.enqueue_function[_pf_geglu_rows_kernel](
                                self.pf_act.unsafe_ptr(), self.pf_gu.unsafe_ptr(),
                                Int64(m * self.d_ff), Int64(self.d_ff),
                                grid_dim=_ceil_div(m * self.d_ff, _TG), block_dim=_TG,
                            )
                    else:
                        self.ctx.enqueue_function[_pf_gemm_geglu_kernel_v2h](
                            self.pf_act.unsafe_ptr(), self.pf_xn.unsafe_ptr(),
                            lw.w_gu.unsafe_ptr(),
                            Int64(m), Int64(self.d_model), Int64(self.d_ff),
                            grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.d_ff, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                    # 9 ── down_proj into the branch scratch (ASSIGN); pre-staged A under
                    #      -D ALGENTA_G3_PF_F16MLP, where `pf_act16` IS the f16 A and the
                    #      22.0M-element convert pass (132 MB of traffic per layer at m=1024)
                    #      has nothing left to do.
                    if use_tc:
                        @parameter
                        if not G3_STREAM:
                            self.ctx.synchronize()
                        var r = 0
                        if gu_f16:
                            r = _tc_gemm_f16_32c_pre_async(
                                Int(self.pf_act16.unsafe_ptr()),
                                Int(lw.w_down.unsafe_ptr()),
                                m, self.d_ff, self.d_model,
                                Int(self.pf_branch.unsafe_ptr()), 0)
                        else:
                            r = _tc_gemm_dispatch_auto(
                                Int(self.pf_act.unsafe_ptr()),
                                Int(lw.w_down.unsafe_ptr()), 0,
                                m, self.d_ff, self.d_model,
                                Int(self.tc_a16.unsafe_ptr()),
                                Int(self.tc_c16.unsafe_ptr()),
                                Int(self.pf_branch.unsafe_ptr()), 0)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                    else:
                        self.ctx.enqueue_function[_pf_gemm_assign_kernel_v2h](
                            self.pf_branch.unsafe_ptr(), self.pf_act.unsafe_ptr(),
                            lw.w_down.unsafe_ptr(),
                            Int64(m), Int64(self.d_ff), Int64(self.d_model),
                            grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.d_model, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                    # 10 ── hidden += rmsnorm(branch) * (1+w_post_feedforward), every row
                    self.ctx.enqueue_function[_pf_norm_accum_rows_kernel](
                        self.pf_hidden.unsafe_ptr(), self.pf_branch.unsafe_ptr(),
                        lw.ln4.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    issued += 10
                pos += m

            # ── the final residual row into the decode-shaped `hidden` (so `dump_logits` and a
            #    following `step`/graph chain see the serial-ingest state), then final rmsnorm +
            #    tied lm_head + per-threadgroup argmax ──
            self.ctx.enqueue_function[_pf_row_copy_kernel](
                self.hidden.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                Int64(last_m - 1), Int64(self.d_model),
                grid_dim=_ceil_div(self.d_model, _TG), block_dim=_TG,
            )
            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
            @parameter
            if G3_STREAM:
                # the cuBLAS lm_head lever's single-stream arm (the TTFT tail): the fused
                # decode-shaped sweep cost ~13 ms on the 27B first token; normalize the one
                # residual row into d_tmp, ride the stream-ordered seam for the [1, vocab]
                # logits GEMM over the resident f16 tie table, one single-row argmax sweep.
                self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                    self.d_tmp.unsafe_ptr(), self.hidden.unsafe_ptr(),
                    self.final_norm.unsafe_ptr(),
                    Int64(self.d_model), self.eps, Int64(1),
                    grid_dim=1, block_dim=_TG,
                )
                var r = _tc_gemm_dispatch_auto(
                    Int(self.d_tmp.unsafe_ptr()),
                    Int(self.embed.unsafe_ptr()), 0,
                    1, self.d_model, self.vocab,
                    Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                    Int(self.logits.unsafe_ptr()), 0)
                if r != 0:
                    return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                self.ctx.enqueue_function[_g3_logits_argmax_kernel](
                    self.out_val.unsafe_ptr(), self.out_idx.unsafe_ptr(),
                    self.logits.unsafe_ptr(), Int64(1), Int64(self.vocab),
                    grid_dim=1, block_dim=_TG,
                )
            else:
                self.ctx.enqueue_function[_lmhead_argmax_kernel_f16](
                    self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(),
                    self.hidden.unsafe_ptr(),
                    self.final_norm.unsafe_ptr(), self.embed.unsafe_ptr(),
                    Int64(self.d_model), Int64(self.vocab), self.eps, Int64(n_iters),
                    grid_dim=_LM_BLOCKS, block_dim=_TG,
                )
                self.ctx.enqueue_function[_argmax_reduce_kernel](
                    self.out_val.unsafe_ptr(), self.out_idx.unsafe_ptr(),
                    self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(),
                    Int64(_LM_BLOCKS),
                    grid_dim=1, block_dim=_TG,
                )
            issued += 3

            self.ctx.enqueue_copy(self.host_val, self.out_val)
            self.ctx.enqueue_copy(self.host_idx, self.out_idx)
            self.ctx.synchronize()
            var tok = Int(self.host_idx.unsafe_ptr()[0])
            var lg = Float64(self.host_val.unsafe_ptr()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(tok, lg, issued, RESIDENT_OK)

    def step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        @parameter
        if not CUDA_GEMMA3_BUILD:
            return _StepOut(-1, 0.0, 0, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)

            var n_q = self.h_q * self.d_head
            var n_kv = self.h_kv * self.d_head
            var n_qkv = n_q + 2 * n_kv
            var n_keys = pos + 1
            var issued = 0

            self.ctx.enqueue_function[_g3_embed_row_kernel_f16](
                self.hidden.unsafe_ptr(), self.embed.unsafe_ptr(),
                Int64(token_id), Int64(self.d_model), self.embed_scale,
                grid_dim=_ceil_div(self.d_model, _TG), block_dim=_TG,
            )
            issued += 1

            for layer in range(self.n_layers):
                ref lw = self.layers[layer]
                var is_global = self.layer_is_global[layer]

                # 1 ── rmsnorm(input_layernorm) + fused Q/K/V projection (f16 weights)
                self.ctx.enqueue_function[_norm_gemv_kernel_f16](
                    self.qkv.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln1.unsafe_ptr(),
                    lw.w_qkv.unsafe_ptr(), Int64(self.d_model), Int64(n_qkv), self.eps,
                    grid_dim=_ceil_div(n_qkv, _SUBS), block_dim=_TG,
                )
                # 2 ── q_norm + k_norm + RoPE (per-class table) + KV-cache write
                var cos_p = self.cos_global.unsafe_ptr() if is_global == 1 \
                    else self.cos_local.unsafe_ptr()
                var sin_p = self.sin_global.unsafe_ptr() if is_global == 1 \
                    else self.sin_local.unsafe_ptr()
                self.ctx.enqueue_function[_qk_rope_write_kernel](
                    self.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    self.qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                    cos_p, sin_p,
                    Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head), self.eps,
                    Int64(1),
                    grid_dim=self.h_q + self.h_kv, block_dim=self.d_head,
                )
                # 3 ── windowed attention
                var key_lo = 0
                if is_global != 1:
                    key_lo = n_keys - self.sliding_window
                    if key_lo < 0:
                        key_lo = 0
                self.ctx.enqueue_function[_g3_sdpa_window_kernel](
                    self.attn_out.unsafe_ptr(), self.q_rot.unsafe_ptr(),
                    lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    Int64(key_lo), Int64(n_keys), Int64(self.h_q), Int64(self.h_kv),
                    Int64(self.d_head), self.scale,
                    grid_dim=self.h_q, block_dim=self.d_head,
                )
                # 4 ── o_proj (f16) to scratch
                self.ctx.enqueue_function[_g3_gemv_kernel_f16](
                    self.o_tmp.unsafe_ptr(), self.attn_out.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                    Int64(n_q), Int64(self.d_model),
                    grid_dim=_ceil_div(self.d_model, _SUBS), block_dim=_TG,
                )
                # 5 ── hidden += rmsnorm(o_proj_out) * gain
                self.ctx.enqueue_function[_g3_norm_accum_kernel](
                    self.hidden.unsafe_ptr(), self.o_tmp.unsafe_ptr(), lw.ln2.unsafe_ptr(),
                    Int64(self.d_model), self.eps,
                    grid_dim=1, block_dim=_TG,
                )
                # 6 ── rmsnorm(pre_ffn) + gate/up (f16) + GeGLU
                @parameter
                if _G3_GEGLU_U4:
                    self.ctx.enqueue_function[_g3_norm_gemv2_geglu_kernel_f16_u4](
                        self.act.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln3.unsafe_ptr(),
                        lw.w_gu.unsafe_ptr(), Int64(self.d_model), Int64(self.d_ff), self.eps,
                        grid_dim=_ceil_div(self.d_ff, _SUBS), block_dim=_TG,
                    )
                else:
                    self.ctx.enqueue_function[_g3_norm_gemv2_geglu_kernel_f16](
                        self.act.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln3.unsafe_ptr(),
                        lw.w_gu.unsafe_ptr(), Int64(self.d_model), Int64(self.d_ff), self.eps,
                        grid_dim=_ceil_div(self.d_ff, _SUBS), block_dim=_TG,
                    )
                # 7 ── down_proj (f16) to scratch
                self.ctx.enqueue_function[_g3_gemv_kernel_f16](
                    self.d_tmp.unsafe_ptr(), self.act.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                    Int64(self.d_ff), Int64(self.d_model),
                    grid_dim=_ceil_div(self.d_model, _SUBS), block_dim=_TG,
                )
                # 8 ── hidden += rmsnorm(down_out) * gain
                self.ctx.enqueue_function[_g3_norm_accum_kernel](
                    self.hidden.unsafe_ptr(), self.d_tmp.unsafe_ptr(), lw.ln4.unsafe_ptr(),
                    Int64(self.d_model), self.eps,
                    grid_dim=1, block_dim=_TG,
                )
                issued += 8

            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
            self.ctx.enqueue_function[_lmhead_argmax_kernel_f16](
                self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(), self.hidden.unsafe_ptr(),
                self.final_norm.unsafe_ptr(), self.embed.unsafe_ptr(),
                Int64(self.d_model), Int64(self.vocab), self.eps, Int64(n_iters),
                grid_dim=_LM_BLOCKS, block_dim=_TG,
            )
            self.ctx.enqueue_function[_argmax_reduce_kernel](
                self.out_val.unsafe_ptr(), self.out_idx.unsafe_ptr(),
                self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(), Int64(_LM_BLOCKS),
                grid_dim=1, block_dim=_TG,
            )
            issued += 2

            self.ctx.enqueue_copy(self.host_val, self.out_val)
            self.ctx.enqueue_copy(self.host_idx, self.out_idx)
            self.ctx.synchronize()
            var tok = Int(self.host_idx.unsafe_ptr()[0])
            var lg = Float64(self.host_val.unsafe_ptr()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(tok, lg, issued, RESIDENT_OK)

    def dump_logits(mut self) raises -> Int:
        @parameter
        if not CUDA_GEMMA3_BUILD:
            return RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT
        else:
            self.ctx.enqueue_function[_g3_norm_inplace_kernel](
                self.hidden.unsafe_ptr(), self.final_norm.unsafe_ptr(),
                Int64(self.d_model), self.eps,
                grid_dim=1, block_dim=_TG,
            )
            self.ctx.enqueue_function[_g3_gemv_kernel_f16](
                self.logits.unsafe_ptr(), self.hidden.unsafe_ptr(), self.embed.unsafe_ptr(),
                Int64(self.d_model), Int64(self.vocab),
                grid_dim=_ceil_div(self.vocab, _SUBS), block_dim=_TG,
            )
            self.ctx.enqueue_copy(self.host_logits, self.logits)
            self.ctx.synchronize()
            return RESIDENT_OK

    def read_logits(mut self) -> List[Float64]:
        var out = List[Float64]()
        var h = self.host_logits.unsafe_ptr()
        for i in range(self.vocab):
            out.append(Float64(h[i]))
        return out^

    # ── CUDA-graph decode arm ────────────────────────────────────────────────────────────────
    # ONE captured graph per token: the gemma3 9-dispatch/layer plan (four norms, windowed
    # split-K attention, GeGLU) with the three dynamic scalars (token_id, pos, n_keys) read from
    # the resident step_state buffer through the _g kernel twins. Per-layer rope-table selection
    # (global vs local) and the sliding-window bound for local layers are baked at capture time.

    def _build_decode_graph(mut self) raises:
        var hidden_a = Int(self.hidden.unsafe_ptr())
        var qkv_a = Int(self.qkv.unsafe_ptr())
        var q_rot_a = Int(self.q_rot.unsafe_ptr())
        var attn_out_a = Int(self.attn_out.unsafe_ptr())
        var o_tmp_a = Int(self.o_tmp.unsafe_ptr())
        var act_a = Int(self.act.unsafe_ptr())
        var d_tmp_a = Int(self.d_tmp.unsafe_ptr())
        var blk_val_a = Int(self.blk_val.unsafe_ptr())
        var blk_idx_a = Int(self.blk_idx.unsafe_ptr())
        var out_val_a = Int(self.out_val.unsafe_ptr())
        var out_idx_a = Int(self.out_idx.unsafe_ptr())
        var embed_a = Int(self.embed.unsafe_ptr())
        var final_norm_a = Int(self.final_norm.unsafe_ptr())
        var cos_g_a = Int(self.cos_global.unsafe_ptr())
        var sin_g_a = Int(self.sin_global.unsafe_ptr())
        var cos_l_a = Int(self.cos_local.unsafe_ptr())
        var sin_l_a = Int(self.sin_local.unsafe_ptr())
        var state_a = Int(self.step_state.unsafe_ptr())
        var tlog_a = Int(self.token_log.unsafe_ptr())
        var skm_a = Int(self.sk_m.unsafe_ptr())
        var skl_a = Int(self.sk_l.unsafe_ptr())
        var sko_a = Int(self.sk_o.unsafe_ptr())

        var ln1s = List[Int]()
        var ln2s = List[Int]()
        var ln3s = List[Int]()
        var ln4s = List[Int]()
        var qns = List[Int]()
        var kns = List[Int]()
        var w_qkvs = List[Int]()
        var w_os = List[Int]()
        var w_gus = List[Int]()
        var w_downs = List[Int]()
        var cks = List[Int]()
        var cvs = List[Int]()
        var lglob = List[Int]()
        for layer in range(self.n_layers):
            ref lw = self.layers[layer]
            ln1s.append(Int(lw.ln1.unsafe_ptr()))
            ln2s.append(Int(lw.ln2.unsafe_ptr()))
            ln3s.append(Int(lw.ln3.unsafe_ptr()))
            ln4s.append(Int(lw.ln4.unsafe_ptr()))
            qns.append(Int(lw.qn.unsafe_ptr()))
            kns.append(Int(lw.kn.unsafe_ptr()))
            w_qkvs.append(Int(lw.w_qkv.unsafe_ptr()))
            w_os.append(Int(lw.w_o.unsafe_ptr()))
            w_gus.append(Int(lw.w_gu.unsafe_ptr()))
            w_downs.append(Int(lw.w_down.unsafe_ptr()))
            cks.append(Int(lw.ck.unsafe_ptr()))
            cvs.append(Int(lw.cv.unsafe_ptr()))
            lglob.append(self.layer_is_global[layer])

        var n_layers_c = self.n_layers
        var d_model_i = Int64(self.d_model)
        var n_q = self.h_q * self.d_head
        var n_kv = self.h_kv * self.d_head
        var n_qkv_i = Int64(n_q + 2 * n_kv)
        var h_q_i = Int64(self.h_q)
        var h_kv_i = Int64(self.h_kv)
        var d_head_i = Int64(self.d_head)
        var n_q_i = Int64(n_q)
        var d_ff_i = Int64(self.d_ff)
        var vocab_i = Int64(self.vocab)
        var eps_c = self.eps
        var scale_c = self.scale
        var embed_scale_c = self.embed_scale
        var window_c = Int64(self.sliding_window)
        var n_iters_i = Int64(_ceil_div(self.vocab, _LM_BLOCKS * _SUBS))

        def build(mut builder: DeviceGraphBuilder) raises {imm}:
            var hidden_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=hidden_a)
            var qkv_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=qkv_a)
            var q_rot_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=q_rot_a)
            var attn_out_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=attn_out_a)
            var o_tmp_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=o_tmp_a)
            var act_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=act_a)
            var d_tmp_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=d_tmp_a)
            var blk_val_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=blk_val_a)
            var blk_idx_p = UnsafePointer[Int32, origin=MutAnyOrigin](unsafe_from_address=blk_idx_a)
            var out_val_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=out_val_a)
            var out_idx_p = UnsafePointer[Int32, origin=MutAnyOrigin](unsafe_from_address=out_idx_a)
            var embed_p = UnsafePointer[Float16, origin=MutAnyOrigin](unsafe_from_address=embed_a)
            var final_norm_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=final_norm_a)
            var cos_g_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cos_g_a)
            var sin_g_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=sin_g_a)
            var cos_l_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cos_l_a)
            var sin_l_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=sin_l_a)
            var state_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=state_a)

            var rec = builder.recording_context()

            # the scaled embedding row, token from state[0]
            rec.enqueue_function[_g3_embed_row_kernel_f16_g](
                hidden_p, embed_p, state_p, d_model_i, embed_scale_c,
                grid_dim=_ceil_div(Int(d_model_i), _TG), block_dim=_TG,
            )

            for layer in range(n_layers_c):
                var ln1_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=ln1s[layer])
                var ln2_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=ln2s[layer])
                var ln3_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=ln3s[layer])
                var ln4_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=ln4s[layer])
                var qn_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=qns[layer])
                var kn_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=kns[layer])
                var wqkv_p = UnsafePointer[Float16, origin=MutAnyOrigin](unsafe_from_address=w_qkvs[layer])
                var wo_p = UnsafePointer[Float16, origin=MutAnyOrigin](unsafe_from_address=w_os[layer])
                var wgu_p = UnsafePointer[Float16, origin=MutAnyOrigin](unsafe_from_address=w_gus[layer])
                var wd_p = UnsafePointer[Float16, origin=MutAnyOrigin](unsafe_from_address=w_downs[layer])
                var ck_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cks[layer])
                var cv_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cvs[layer])
                # per-layer rope table + window, baked at capture
                var is_global = lglob[layer]
                var cos_p = cos_g_p if is_global == 1 else cos_l_p
                var sin_p = sin_g_p if is_global == 1 else sin_l_p
                var win = Int64(0) if is_global == 1 else window_c

                # 1 ── rmsnorm(input_layernorm) + fused Q/K/V projection
                rec.enqueue_function[_norm_gemv_kernel_f16](
                    qkv_p, hidden_p, ln1_p,
                    wqkv_p, d_model_i, n_qkv_i, eps_c,
                    grid_dim=_ceil_div(Int(n_qkv_i), _SUBS), block_dim=_TG,
                )
                # 2 ── q_norm + k_norm + RoPE (per-class table) + KV-cache slot write (pos: state[1])
                rec.enqueue_function[_qk_rope_write_kernel_g](
                    q_rot_p, ck_p, cv_p,
                    qkv_p, qn_p, kn_p,
                    cos_p, sin_p,
                    state_p, h_q_i, h_kv_i, d_head_i, eps_c,
                    Int64(1),  # gemma3 always QK-norms
                    grid_dim=Int(h_q_i) + Int(h_kv_i), block_dim=Int(d_head_i),
                )
                # 3 ── WINDOWED split-K attention (n_keys: state[2]; local layers windowed)
                var skm_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=skm_a)
                var skl_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=skl_a)
                var sko_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=sko_a)
                rec.enqueue_function[_g3_splitk_partial_kernel_simd_g](
                    skm_p, skl_p, sko_p, q_rot_p,
                    ck_p, cv_p,
                    state_p, Int64(GEMMA3_GRAPH_N_SPLITS), h_q_i, h_kv_i, d_head_i, scale_c, win,
                    grid_dim=Int(h_q_i) * GEMMA3_GRAPH_N_SPLITS, block_dim=Int(d_head_i),
                )
                rec.enqueue_function[_splitk_merge_kernel_simd](
                    attn_out_p, skm_p, skl_p, sko_p,
                    Int64(GEMMA3_GRAPH_N_SPLITS), d_head_i,
                    grid_dim=Int(h_q_i), block_dim=Int(d_head_i),
                )
                # 4 ── o_proj into scratch
                rec.enqueue_function[_g3_gemv_kernel_f16](
                    o_tmp_p, attn_out_p, wo_p,
                    n_q_i, d_model_i,
                    grid_dim=_ceil_div(Int(d_model_i), _SUBS), block_dim=_TG,
                )
                # 5 ── hidden += rmsnorm(o_proj_out) * gain(ln2)
                rec.enqueue_function[_g3_norm_accum_kernel](
                    hidden_p, o_tmp_p, ln2_p,
                    d_model_i, eps_c,
                    grid_dim=1, block_dim=_TG,
                )
                # 6 ── rmsnorm(pre_ffn) + gate/up + GeGLU
                @parameter
                if _G3_GEGLU_U4:
                    rec.enqueue_function[_g3_norm_gemv2_geglu_kernel_f16_u4](
                        act_p, hidden_p, ln3_p,
                        wgu_p, d_model_i, d_ff_i, eps_c,
                        grid_dim=_ceil_div(Int(d_ff_i), _SUBS), block_dim=_TG,
                    )
                else:
                    rec.enqueue_function[_g3_norm_gemv2_geglu_kernel_f16](
                        act_p, hidden_p, ln3_p,
                        wgu_p, d_model_i, d_ff_i, eps_c,
                        grid_dim=_ceil_div(Int(d_ff_i), _SUBS), block_dim=_TG,
                    )
                # 7 ── down_proj into scratch
                rec.enqueue_function[_g3_gemv_kernel_f16](
                    d_tmp_p, act_p, wd_p,
                    d_ff_i, d_model_i,
                    grid_dim=_ceil_div(Int(d_model_i), _SUBS), block_dim=_TG,
                )
                # 8 ── hidden += rmsnorm(down_out) * gain(ln4)
                rec.enqueue_function[_g3_norm_accum_kernel](
                    hidden_p, d_tmp_p, ln4_p,
                    d_model_i, eps_c,
                    grid_dim=1, block_dim=_TG,
                )

            # final rmsnorm + tied lm_head (the f16 embed table) + argmax, then reduce + advance
            rec.enqueue_function[_lmhead_argmax_kernel_f16](
                blk_val_p, blk_idx_p, hidden_p,
                final_norm_p, embed_p,
                d_model_i, vocab_i, eps_c, n_iters_i,
                grid_dim=_LM_BLOCKS, block_dim=_TG,
            )
            rec.enqueue_function[_argmax_reduce_kernel](
                out_val_p, out_idx_p,
                blk_val_p, blk_idx_p, Int64(_LM_BLOCKS),
                grid_dim=1, block_dim=_TG,
            )
            var tlog_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=tlog_a)
            rec.enqueue_function[_graph_advance_kernel](
                state_p, out_idx_p, tlog_p,
                grid_dim=1, block_dim=1,
            )

        self.decode_graph = DeviceGraph.create(self.ctx, build)

    def step_graph(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        @parameter
        if not CUDA_GEMMA3_BUILD:
            return _StepOut(-1, 0.0, 0, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)

            if not self.decode_graph_built:
                self._build_decode_graph()
                self.decode_graph_built = True

            var state_h = self.host_state.unsafe_ptr()
            state_h[0] = Int64(token_id)
            state_h[1] = Int64(pos)
            state_h[2] = Int64(pos + 1)
            self.ctx.enqueue_copy(self.step_state, self.host_state)

            self.decode_graph.value().replay()

            self.ctx.enqueue_copy(self.host_val, self.out_val)
            self.ctx.enqueue_copy(self.host_idx, self.out_idx)
            self.ctx.synchronize()

            var tok = Int(self.host_idx.unsafe_ptr()[0])
            var lg = Float64(self.host_val.unsafe_ptr()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(tok, lg, self.n_layers * 9 + 4, RESIDENT_OK)

    def seed_and_run_graph(
        mut self, first_token: Int, start_pos: Int, n_steps: Int,
    ) raises -> Int:
        @parameter
        if not CUDA_GEMMA3_BUILD:
            return RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT
        else:
            if n_steps < 1:
                return RESIDENT_ERR_UPLOAD_LENGTH
            if start_pos < 0 or start_pos + n_steps > self.max_ctx:
                return RESIDENT_ERR_CONTEXT_FULL
            if first_token < 0 or first_token >= self.vocab:
                return RESIDENT_ERR_UPLOAD_LENGTH

            if not self.decode_graph_built:
                self._build_decode_graph()
                self.decode_graph_built = True

            var state_h = self.host_state.unsafe_ptr()
            state_h[0] = Int64(first_token)
            state_h[1] = Int64(start_pos)
            state_h[2] = Int64(start_pos + 1)
            self.ctx.enqueue_copy(self.step_state, self.host_state)

            for _ in range(n_steps):
                self.decode_graph.value().replay()

            self.ctx.synchronize()
            self.ctx.enqueue_copy(self.host_token_log, self.token_log)
            self.ctx.synchronize()
            return RESIDENT_OK

    def graph_token(self, pos: Int) raises -> Int:
        return Int(self.host_token_log.unsafe_ptr()[pos])

    def ensure_graph(mut self) raises:
        """Build the decode graph eagerly (outside any timed region). Idempotent."""
        if not self.decode_graph_built:
            self._build_decode_graph()
            self.decode_graph_built = True
