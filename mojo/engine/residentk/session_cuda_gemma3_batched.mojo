"""
residentk.session_cuda_gemma3_batched — the CUDA-native FLOAT16-weight BATCHED DECODE resident
session for Gemma 3 (Gemma 3 lane, 2026-08-24): B sequences share ONE weight-residency, each
decode step is ONE M=B dispatch plan (the tokens-per-weight-sweep collapse the campaign proved
on Metal and on the Qwen3 CUDA lane), and the four-norm / dual-rope / sliding-window family
structure is carried through the batched chain exactly the way `session_cuda_gemma3_f16`'s
single-stream chain carries it. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float16
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/gemma3_batched_cuda.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/gemma3_batched_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module; private names, launches gated behind `CUDA_GEMMA3_BUILD` exactly the way
`residentk.session_cuda_gemma3` documents.

The per-step plan (B rows, per layer, ten dispatches — the single-stream eight with the two
GEMV-fused norm+projections replaced by rmsnorm-rows + M=B GEMMs and the branch outputs
materialised for the post-branch norms):

    1  _pf_rmsnorm_rows_kernel            input_layernorm, B rows
    2  fused QKV GEMM [B,d_model]->[B,n_qkv]      (TC seam or the native v2h kernel)
    3  _g3_ropewrt_batched_kernel         per-sequence pos (device poss), per-layer rope table,
                                          KV write at b*kv_stride + pos slots
    4  _g3_kv_decode_splitk_partial_batched_kernel + the batched merge (reused from
       attention_forge) — windowed flash-decoding; window=0 for the full layers
    5  o_proj GEMM into the BRANCH scratch (ASSIGN — the post-branch norm forbids accumulate)
    6  _pf_norm_accum_rows_kernel         hidden += rmsnorm(branch) * (1+w_post_attention)
    7  _pf_rmsnorm_rows_kernel            pre_feedforward_layernorm, B rows
    8  gate/up GEMM + GeGLU               (TC seam + _pf_geglu_rows_kernel, or fused v2h)
    9  down_proj GEMM into the branch scratch (ASSIGN)
    10 _pf_norm_accum_rows_kernel         hidden += rmsnorm(branch) * (1+w_post_feedforward)

    tail: _pf_rmsnorm_rows_kernel (final norm, B rows) + _g3_batched_lmhead_argmax_kernel_f16
          (one vocab sweep for all B rows) + _batched_argmax_reduce_kernel_simd (grid B).

Per-sequence ingestion (`ingest`) runs the single-stream tiled prefill chain with the KV
pointers offset by `seq * kv_stride_elems` — the batched cache IS B contiguous single-stream
caches — and lands the sequence's final residual row at `hidden[seq * d_model]`.
"""

from max.gpu.host import (
    DeviceBuffer,
    DeviceContext,
    HostBuffer,
)
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
    _batched_argmax_reduce_kernel_simd,
    _lmhead_argmax_kernel_f16,
    _pf_rmsnorm_rows_kernel,
    _pf_ropewrt_kernel,
)
from residentk.kernels_prefill_gemma3 import (
    G3_PF_TILE,
    _pf_attn_window_kernel,
    _pf_attn_window_kernel_h,
    _pf_attn_window_flash_kernel,
    _pf_attn_window_flash_kernel_h,
    _G3_PF_FLASH_ROWS_PER_BLOCK,
    _G3_PF_FLASH_NTHREADS,
    _pf_embed_rows_g3_kernel_f16,
    _pf_geglu_rows_kernel,
    _pf_gemm_assign_kernel_v2h,
    _pf_gemm_geglu_kernel_v2h,
    _pf_norm_accum_rows_kernel,
    _pf_row_copy_kernel,
    _pf_ropewrt_kernel_h,
)
from residentk.kernels_prefill_f32_v2 import (
    _G2_BM,
    _G2_BN,
    _G2_NTHREADS,
)
from residentk.kernels_batched_gemma3 import (
    _g3_ropewrt_batched_kernel,
    _g3_ropewrt_batched_kernel_kv16,
    _g3_kv_decode_splitk_partial_batched_kernel,
    _g3_kv_decode_splitk_partial_batched_kernel_kv16,
    _g3_kv_decode_splitk_partial_batched_kernel_kv16_flash,
    _g3_batched_lmhead_argmax_kernel_f16,
    _g3_logits_argmax_kernel,
    _G3_DECODE_FLASH_NTHREADS,
    _G3_DECODE_FLASH_WARPS_PER_BLOCK,
)
from native_kv_decode_attn_splitk_batched_f32 import (
    _native_kv_decode_splitk_merge_batched_f32_kernel,
)
from residentk.tc_shim_bridge import (
    TC_SHIM_BUILD,
    _tc_init,
    _tc_last_error,
    _tc_gemm_dispatch,
    _tc_gemm_dispatch_async,
    _tc_gemm_dispatch_auto,
    _tc_use_legacy_stream,
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
from residentk.session_cuda_gemma3_f16 import (
    CUDA_GEMMA3_BUILD,
)

comptime G3_BATCH_N_SPLITS: Int = 16
"""The batched flash-decoding fan-out: B x h_q x n_splits blocks. At B=32, h_q=32 this is 16,384
blocks — the GPU is full at every B the sweep races; at B=1 it is 512 blocks on 132 SMs, still
a comfortable fill. Fewer splits per sequence than the single-stream graph arm's 32 — the batch
axis already supplies the parallelism the splits used to."""

comptime G3_BATCH_KV_F16: Bool = is_defined["ALGENTA_G3_KV_F16"]()
"""The C=50 fit lever (2026-08-24): with `-D ALGENTA_G3_KV_F16` the batched KV cache is resident
Float16 (f32 rope math, narrowed at the store, widened at the read — the accumulation stays
f32), halving the cache footprint so 50 sequences x the sonnet shape fit one 80 GB H100 next to
the 54 GB f16 weight residency. Flag-off builds keep the f32 cache byte-for-byte."""

comptime _G3BKV_DT: DType = DType.float16 if G3_BATCH_KV_F16 else DType.float32
"""The batched KV element dtype this build carries."""

comptime G3_ATTN_FLASH: Bool = is_defined["ALGENTA_G3_ATTN_FLASH"]()
"""The flash-style M-parallel attention lever (lever 1 of the vLLM-flip round, 2026-08-24):
with `-D ALGENTA_G3_ATTN_FLASH` the batched split-K attention partial dispatches the
warp-per-unit FLASH twin (`_g3_kv_decode_splitk_partial_batched_kernel_kv16_flash`, one warp
per (sequence, head, split), block-8 online softmax, zero per-key barriers, 8-byte vector
KV loads) instead of the barrier-tree partial, but ONLY at `d_head == 128` (the flash twin's
structural lane contract); every other head dim stays on the byte-for-byte legacy kernel.
This is a fact-driven capability dispatch (head-dim), never a per-model branch. Flag-off
builds keep the legacy partial byte-for-byte."""

comptime G3_PF_ATTN_FLASH: Bool = is_defined["ALGENTA_G3_PF_ATTN_FLASH"]()
"""The flash-style M-parallel PREFILL attention lever (the TTFT lever of the vLLM-flip round,
2026-08-24): with `-D ALGENTA_G3_PF_ATTN_FLASH` the per-sequence ingest dispatches the
four-rows-per-warp FLASH twin (`_pf_attn_window_flash_kernel` / `_h` kv16) instead of the
barrier-tree windowed kernel, but ONLY at `d_head == 128` (the flash twin's structural lane
contract); every other head dim stays on the byte-for-byte tiled kernel. Fact-driven
capability dispatch (head-dim), never a per-model branch. Flag-off builds keep the tiled
kernel byte-for-byte."""

comptime G3_STREAM: Bool = TC_SHIM_BUILD and is_defined["ALGENTA_G3_STREAM"]()
"""The stream-ordered seam lever (2026-08-24): with `-D ALGENTA_G3_STREAM` the cuBLAS
handle is bound to the CUDA LEGACY default stream at TC init (`_tc_use_legacy_stream`), and
every TC GEMM dispatches `_tc_gemm_dispatch_async` with NO `ctx.synchronize()` before it —
legacy_probe.mojo (H100, this lane) proved Mojo's default stream is device-ordered against
the legacy stream in both directions with zero host syncs, so the whole step stays one
stream-ordered pipeline. The legacy seam paid TWO device syncs per GemmEx (the session's
`ctx.synchronize()` before + the shim's `cudaStreamSynchronize` inside): 4 GEMMs x 62
layers = 248 calls x 2 = 496 device syncs per 27B decode step, all removed. Flag-off
builds keep the legacy seam byte-for-byte; a failed legacy binding at init falls back to
the native v2h chain (correct, slower) exactly like a failed TC init."""

alias _FP = UnsafePointer[Float32]


@fieldwise_init
struct _G3LayerGpuBatched(Copyable, Movable):
    """One Gemma 3 layer for the batched session: the f16 projections + f32 norms of
    `_G3LayerGpuF16`, with the KV slice at this build's batch-KV dtype and sized
    `max_seqs * max_ctx` positions (B contiguous single-stream caches)."""

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
    var ck: DeviceBuffer[_G3BKV_DT]
    var cv: DeviceBuffer[_G3BKV_DT]


@fieldwise_init
struct _CudaResidentGemma3BatchedF16(Movable):
    """The Gemma 3 CUDA-native batched resident session: ONE f16 weight-residency, B contiguous
    per-sequence KV caches (f32), one M=B dispatch plan per decode step."""

    var ctx: DeviceContext
    var d_model: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var n_layers: Int
    var vocab: Int
    var max_seqs: Int
    var max_ctx: Int
    var eps: Float32
    var scale: Float32
    var embed_scale: Float32
    var sliding_window: Int
    var kv_stride_elems: Int

    var layer_is_global: List[Int]
    var layers: List[_G3LayerGpuBatched]
    var embed: DeviceBuffer[DType.float16]
    var final_norm: DeviceBuffer[DType.float32]
    var cos_global: DeviceBuffer[DType.float32]
    var sin_global: DeviceBuffer[DType.float32]
    var cos_local: DeviceBuffer[DType.float32]
    var sin_local: DeviceBuffer[DType.float32]

    # per-sequence dynamic state (device arrays the batched kernels read)
    var dev_tokens: DeviceBuffer[DType.int32]
    var dev_poss: DeviceBuffer[DType.int64]
    var dev_nkeys: DeviceBuffer[DType.int64]
    var host_tokens: HostBuffer[DType.int32]
    var host_poss: HostBuffer[DType.int64]
    var host_nkeys: HostBuffer[DType.int64]

    # batched-step scratch — B-row working set
    var hidden: DeviceBuffer[DType.float32]
    var xn: DeviceBuffer[DType.float32]
    var qkv: DeviceBuffer[DType.float32]
    var q_rot: DeviceBuffer[DType.float32]
    var attn: DeviceBuffer[DType.float32]
    var branch: DeviceBuffer[DType.float32]
    var act: DeviceBuffer[DType.float32]
    var gu: DeviceBuffer[DType.float32]

    # split-K attention partials
    var sk_m: DeviceBuffer[DType.float32]
    var sk_l: DeviceBuffer[DType.float32]
    var sk_o: DeviceBuffer[DType.float32]

    # batched lm_head tail
    var blk_val: DeviceBuffer[DType.float32]
    var blk_idx: DeviceBuffer[DType.int32]
    var out_val: DeviceBuffer[DType.float32]
    var out_idx: DeviceBuffer[DType.int32]
    var host_val: HostBuffer[DType.float32]
    var host_idx: HostBuffer[DType.int32]
    # the G3_STREAM cuBLAS lm_head lever: materialised [max_seqs, vocab] f32 logits table
    var logits: DeviceBuffer[DType.float32]

    # single-stream prefill scratch (per-sequence ingestion)
    var pf_tokens: DeviceBuffer[DType.int32]
    var pf_hidden: DeviceBuffer[DType.float32]
    var pf_xn: DeviceBuffer[DType.float32]
    var pf_qkv: DeviceBuffer[DType.float32]
    var pf_q_rot: DeviceBuffer[DType.float32]
    var pf_attn: DeviceBuffer[DType.float32]
    var pf_act: DeviceBuffer[DType.float32]
    var pf_branch: DeviceBuffer[DType.float32]
    var pf_gu: DeviceBuffer[DType.float32]

    # TC escape-hatch scratch (the resident weights ARE the f16 B operand; scratch is ONLY the
    # f32->f16 A staging + the rung-2 f16-C staging). Real sizes under TC_SHIM_BUILD only.
    var tc_a16: DeviceBuffer[DType.float16]
    var tc_c16: DeviceBuffer[DType.float16]
    var tc_ready: Int

    def __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_seqs: Int, max_ctx: Int,
        eps: Float64, scale: Float64, embed_scale: Float64,
        sliding_window: Int, layer_is_global: List[Int],
    ) raises:
        self.ctx = DeviceContext()
        self.d_model = d_model
        self.h_q = h_q
        self.h_kv = h_kv
        self.d_head = d_head
        self.d_ff = d_ff
        self.n_layers = n_layers
        self.vocab = vocab
        self.max_seqs = max_seqs
        self.max_ctx = max_ctx
        self.eps = Float32(eps)
        self.scale = Float32(scale)
        self.embed_scale = Float32(embed_scale)
        self.sliding_window = sliding_window
        self.kv_stride_elems = max_ctx * h_kv * d_head

        self.layer_is_global = List[Int]()
        for i in range(n_layers):
            self.layer_is_global.append(layer_is_global[i])

        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

        # the batched KV cache: ONE contiguous buffer per layer per cache, B single-stream
        # caches concatenated (sequence b at element offset b * kv_stride_elems) — the
        # uniform-stride contract the batched ropewrt/attention kernels read. Element dtype is
        # this build's batch-KV dtype (f32 default; f16 under -D ALGENTA_G3_KV_F16).
        self.layers = List[_G3LayerGpuBatched]()
        for _ in range(n_layers):
            self.layers.append(
                _G3LayerGpuBatched(
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
                    self.ctx.enqueue_create_buffer[_G3BKV_DT](
                        max_seqs * max_ctx * h_kv * d_head),
                    self.ctx.enqueue_create_buffer[_G3BKV_DT](
                        max_seqs * max_ctx * h_kv * d_head),
                )
            )

        self.embed = self.ctx.enqueue_create_buffer[DType.float16](vocab * d_model)
        self.final_norm = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.cos_global = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
        self.sin_global = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
        self.cos_local = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
        self.sin_local = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)

        self.dev_tokens = self.ctx.enqueue_create_buffer[DType.int32](max_seqs)
        self.dev_poss = self.ctx.enqueue_create_buffer[DType.int64](max_seqs)
        self.dev_nkeys = self.ctx.enqueue_create_buffer[DType.int64](max_seqs)
        self.host_tokens = self.ctx.enqueue_create_host_buffer[DType.int32](max_seqs)
        self.host_poss = self.ctx.enqueue_create_host_buffer[DType.int64](max_seqs)
        self.host_nkeys = self.ctx.enqueue_create_host_buffer[DType.int64](max_seqs)

        var b = max_seqs
        self.hidden = self.ctx.enqueue_create_buffer[DType.float32](b * d_model)
        self.xn = self.ctx.enqueue_create_buffer[DType.float32](b * d_model)
        self.qkv = self.ctx.enqueue_create_buffer[DType.float32](b * n_qkv)
        self.q_rot = self.ctx.enqueue_create_buffer[DType.float32](b * h_q * d_head)
        self.attn = self.ctx.enqueue_create_buffer[DType.float32](b * h_q * d_head)
        self.branch = self.ctx.enqueue_create_buffer[DType.float32](b * d_model)
        self.act = self.ctx.enqueue_create_buffer[DType.float32](b * d_ff)
        self.gu = self.ctx.enqueue_create_buffer[DType.float32](b * 2 * d_ff)

        var n_part = b * h_q * G3_BATCH_N_SPLITS
        self.sk_m = self.ctx.enqueue_create_buffer[DType.float32](n_part)
        self.sk_l = self.ctx.enqueue_create_buffer[DType.float32](n_part)
        self.sk_o = self.ctx.enqueue_create_buffer[DType.float32](n_part * d_head)

        self.blk_val = self.ctx.enqueue_create_buffer[DType.float32](b * _LM_BLOCKS)
        self.blk_idx = self.ctx.enqueue_create_buffer[DType.int32](b * _LM_BLOCKS)
        self.out_val = self.ctx.enqueue_create_buffer[DType.float32](b)
        self.out_idx = self.ctx.enqueue_create_buffer[DType.int32](b)
        self.host_val = self.ctx.enqueue_create_host_buffer[DType.float32](b)
        self.host_idx = self.ctx.enqueue_create_host_buffer[DType.int32](b)
        @parameter
        if G3_STREAM:
            # the cuBLAS lm_head lever's logits table (52 MB at B=50 / vocab 262208)
            self.logits = self.ctx.enqueue_create_buffer[DType.float32](b * vocab)
        else:
            self.logits = self.ctx.enqueue_create_buffer[DType.float32](1)

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
        @parameter
        if TC_SHIM_BUILD:
            var max_k = d_model
            if h_q * d_head > max_k:
                max_k = h_q * d_head
            if d_ff > max_k:
                max_k = d_ff
            var max_n = n_qkv
            if 2 * d_ff > max_n:
                max_n = 2 * d_ff
            # scratch rows: the batched step dispatches at max_seqs rows, but `ingest`'s
            # single-stream tiles run up to G3_PF_TILE rows through the same seam — size for
            # the larger of the two.
            var tc_rows = max_seqs
            if G3_PF_TILE > tc_rows:
                tc_rows = G3_PF_TILE
            self.tc_a16 = self.ctx.enqueue_create_buffer[DType.float16](tc_rows * max_k)
            self.tc_c16 = self.ctx.enqueue_create_buffer[DType.float16](tc_rows * max_n)
            self.tc_ready = 0

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

    def seal(mut self) raises -> Int:
        self.ctx.synchronize()
        return RESIDENT_OK

    def _ensure_tc(mut self) raises:
        @parameter
        if TC_SHIM_BUILD:
            if self.tc_ready == 0:
                var r = _tc_init()
                if r == 0:
                    @parameter
                    if G3_STREAM:
                        # bind the handle to the legacy default stream — Mojo's default
                        # stream is device-ordered against it (legacy_probe.mojo), so the
                        # async dispatches below need no host sync at all.
                        var rb = _tc_use_legacy_stream()
                        if rb != 0:
                            self.tc_ready = -1
                            print("gemma3-batched: legacy-stream binding FAILED, status", rb,
                                  "last_error:", _tc_last_error(),
                                  "| batched decode stays on the native chain")
                            return
                        print("gemma3-batched: TC shim cuBLAS handle BOUND to the LEGACY",
                              "stream | G3_STREAM: zero-sync async GemmEx seams")
                    else:
                        print("gemma3-batched: TC shim cuBLAS handle BOUND | batched GEMMs",
                              "ride the HMMA seam")
                    self.tc_ready = 1
                else:
                    self.tc_ready = -1
                    print("gemma3-batched: TC shim init FAILED, status", r,
                          "last_error:", _tc_last_error(),
                          "| batched decode stays on the native chain")

    def ingest(mut self, seq: Int, prompt_ids: List[Int]) raises -> _StepOut:
        """ONE sequence's prompt through the single-stream tiled prefill chain, writing THIS
        sequence's KV region (the layer caches offset by `seq * kv_stride_elems`) and landing
        the final residual row at `hidden[seq * d_model]`. Returns the sequence's first
        generated token (final-norm + tied lm_head + argmax on that row)."""

        @parameter
        if not CUDA_GEMMA3_BUILD:
            return _StepOut(-1, 0.0, 0, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            self._ensure_tc()
            var n_prompt = len(prompt_ids)
            if n_prompt < 1:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)
            if n_prompt > self.max_ctx:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_CONTEXT_FULL)
            if seq < 0 or seq >= self.max_seqs:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)
            for i in range(n_prompt):
                if prompt_ids[i] < 0 or prompt_ids[i] >= self.vocab:
                    return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)

            var n_q = self.h_q * self.d_head
            var n_qkv = (self.h_q + 2 * self.h_kv) * self.d_head
            var kv_off = seq * self.kv_stride_elems
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
                    use_tc = self.tc_ready == 1 and m >= 128

                with self.pf_tokens.map_to_host() as h:
                    for i in range(m):
                        h[i] = Int32(prompt_ids[pos + i])
                self.ctx.synchronize()

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
                    var ck_p = lw.ck.unsafe_ptr() + kv_off
                    var cv_p = lw.cv.unsafe_ptr() + kv_off

                    self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        self.pf_xn.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                        lw.ln1.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    if use_tc:
                        @parameter
                        if not G3_STREAM:
                            self.ctx.synchronize()
                        var r = _tc_gemm_dispatch_auto(
                            Int(self.pf_xn.unsafe_ptr()),
                            Int(lw.w_qkv.unsafe_ptr()), 0,
                            m, self.d_model, n_qkv,
                            Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
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
                    var cos_p = self.cos_global.unsafe_ptr() if is_global == 1 \
                        else self.cos_local.unsafe_ptr()
                    var sin_p = self.sin_global.unsafe_ptr() if is_global == 1 \
                        else self.sin_local.unsafe_ptr()
                    # ropewrt over m rows with pos_base — the single-stream batched twin; the
                    # KV pointers are already offset into THIS sequence's cache region.
                    @parameter
                    if G3_BATCH_KV_F16:
                        self.ctx.enqueue_function[_pf_ropewrt_kernel_h](
                            self.pf_q_rot.unsafe_ptr(), ck_p, cv_p,
                            self.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                            cos_p, sin_p,
                            Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                            self.eps, Int64(m), Int64(1),
                            grid_dim=(self.h_q + self.h_kv) * m, block_dim=self.d_head,
                        )
                    else:
                        self.ctx.enqueue_function[_pf_ropewrt_kernel](
                            self.pf_q_rot.unsafe_ptr(), ck_p, cv_p,
                            self.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                            cos_p, sin_p,
                            Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                            self.eps, Int64(m), Int64(1),
                            grid_dim=(self.h_q + self.h_kv) * m, block_dim=self.d_head,
                        )
                    var use_pf_flash = False
                    @parameter
                    if G3_PF_ATTN_FLASH:
                        # fact-driven capability dispatch: the flash twin's lane contract is
                        # d_head == 128 == WARP_SIZE * 4; any other head dim stays
                        # byte-for-byte on the tiled barrier-tree kernel.
                        use_pf_flash = self.d_head == 128
                    @parameter
                    if G3_BATCH_KV_F16:
                        if use_pf_flash:
                            self.ctx.enqueue_function[_pf_attn_window_flash_kernel_h](
                                self.pf_attn.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                                ck_p, cv_p,
                                Int64(pos), Int64(self.h_q), Int64(self.h_kv),
                                Int64(self.d_head),
                                Int64(self.sliding_window), Int64(is_global), self.scale,
                                Int64(m),
                                grid_dim=_ceil_div(m, _G3_PF_FLASH_ROWS_PER_BLOCK) * self.h_q,
                                block_dim=_G3_PF_FLASH_NTHREADS,
                            )
                        else:
                            self.ctx.enqueue_function[_pf_attn_window_kernel_h](
                                self.pf_attn.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                                ck_p, cv_p,
                                Int64(pos), Int64(self.h_q), Int64(self.h_kv),
                                Int64(self.d_head),
                                Int64(self.sliding_window), Int64(is_global), self.scale,
                                Int64(m),
                                grid_dim=self.h_q * m, block_dim=self.d_head,
                            )
                    else:
                        if use_pf_flash:
                            self.ctx.enqueue_function[_pf_attn_window_flash_kernel](
                                self.pf_attn.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                                ck_p, cv_p,
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
                                ck_p, cv_p,
                                Int64(pos), Int64(self.h_q), Int64(self.h_kv),
                                Int64(self.d_head),
                                Int64(self.sliding_window), Int64(is_global), self.scale,
                                Int64(m),
                                grid_dim=self.h_q * m, block_dim=self.d_head,
                            )
                    if use_tc:
                        @parameter
                        if not G3_STREAM:
                            self.ctx.synchronize()
                        var r = _tc_gemm_dispatch_auto(
                            Int(self.pf_attn.unsafe_ptr()),
                            Int(lw.w_o.unsafe_ptr()), 0,
                            m, n_q, self.d_model,
                            Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
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
                    self.ctx.enqueue_function[_pf_norm_accum_rows_kernel](
                        self.pf_hidden.unsafe_ptr(), self.pf_branch.unsafe_ptr(),
                        lw.ln2.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        self.pf_xn.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                        lw.ln3.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    if use_tc:
                        @parameter
                        if not G3_STREAM:
                            self.ctx.synchronize()
                        var r = _tc_gemm_dispatch_auto(
                            Int(self.pf_xn.unsafe_ptr()),
                            Int(lw.w_gu.unsafe_ptr()), 0,
                            m, self.d_model, 2 * self.d_ff,
                            Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                            Int(self.pf_gu.unsafe_ptr()), 0)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
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
                    if use_tc:
                        @parameter
                        if not G3_STREAM:
                            self.ctx.synchronize()
                        var r = _tc_gemm_dispatch_auto(
                            Int(self.pf_act.unsafe_ptr()),
                            Int(lw.w_down.unsafe_ptr()), 0,
                            m, self.d_ff, self.d_model,
                            Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
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
                    self.ctx.enqueue_function[_pf_norm_accum_rows_kernel](
                        self.pf_hidden.unsafe_ptr(), self.pf_branch.unsafe_ptr(),
                        lw.ln4.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    issued += 10
                pos += m

            # final residual row -> this sequence's batched-hidden slot
            self.ctx.enqueue_function[_pf_row_copy_kernel](
                self.hidden.unsafe_ptr() + seq * self.d_model, self.pf_hidden.unsafe_ptr(),
                Int64(last_m - 1), Int64(self.d_model),
                grid_dim=_ceil_div(self.d_model, _TG), block_dim=_TG,
            )
            # first generated token: final-norm + tied lm_head + argmax on that row
            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
            @parameter
            if G3_STREAM:
                # the cuBLAS lm_head lever's admission arm: the fused decode-shaped sweep
                # cost ~13 ms per ingestion (50 admissions = 0.66 s of the C=50 ingest);
                # normalize the row, ride the seam for the [1, vocab] logits GEMM, one
                # single-row argmax sweep.
                self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                    self.xn.unsafe_ptr(), self.hidden.unsafe_ptr() + seq * self.d_model,
                    self.final_norm.unsafe_ptr(),
                    Int64(self.d_model), self.eps, Int64(1),
                    grid_dim=1, block_dim=_TG,
                )
                var r = _tc_gemm_dispatch_auto(
                    Int(self.xn.unsafe_ptr()),
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
                    self.hidden.unsafe_ptr() + seq * self.d_model,
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

    def seed_step(
        mut self, B: Int, tokens: List[Int], poss: List[Int], nkeys: List[Int],
    ) raises -> Int:
        """The per-sequence dynamic scalars for the NEXT batched step, uploaded once."""
        if B < 1 or B > self.max_seqs:
            return RESIDENT_ERR_UPLOAD_LENGTH
        var h_tok = self.host_tokens.unsafe_ptr()
        var h_pos = self.host_poss.unsafe_ptr()
        var h_nk = self.host_nkeys.unsafe_ptr()
        for i in range(B):
            h_tok[i] = Int32(tokens[i])
            h_pos[i] = Int64(poss[i])
            h_nk[i] = Int64(nkeys[i])
        self.ctx.enqueue_copy(self.dev_tokens, self.host_tokens)
        self.ctx.enqueue_copy(self.dev_poss, self.host_poss)
        self.ctx.enqueue_copy(self.dev_nkeys, self.host_nkeys)
        return RESIDENT_OK

    def step_batched(mut self, B: Int) raises -> Int:
        """ONE batched decode step for B sequences (tokens/poss/nkeys already seeded): the
        ten-dispatch four-norm plan at M=B plus the batched lm_head tail. Reads the tokens back
        into the host pinned buffer; `batch_token(b)` returns them."""

        @parameter
        if not CUDA_GEMMA3_BUILD:
            return RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT
        else:
            self._ensure_tc()
            if B < 1 or B > self.max_seqs:
                return RESIDENT_ERR_UPLOAD_LENGTH

            comptime _G3B_DBG: Bool = is_defined["ALGENTA_G3_BATCH_DBG"]()

            var n_q = self.h_q * self.d_head
            var n_qkv = (self.h_q + 2 * self.h_kv) * self.d_head
            var use_tc = False
            @parameter
            if TC_SHIM_BUILD:
                # batched decode rides the seam at EVERY B: the native v2h chain's f16 global
                # loads scalarize on this backend, while GemmEx streams the resident weights at
                # HBM speed even at M=1..64 — the M-threshold rationale the prefill path uses
                # (tile-fill amortization) does not apply to decode's weight-streaming GEMMs.
                use_tc = self.tc_ready == 1

            # embed: B token ids -> hidden [B, d_model]
            self.ctx.enqueue_function[_pf_embed_rows_g3_kernel_f16](
                self.hidden.unsafe_ptr(), self.embed.unsafe_ptr(),
                self.dev_tokens.unsafe_ptr(),
                Int64(self.d_model), Int64(B), self.embed_scale,
                grid_dim=_ceil_div(self.d_model, _TG) * B, block_dim=_TG,
            )
            @parameter
            if _G3B_DBG:
                self.ctx.synchronize()
                print("DBG step: embed ok")

            for layer in range(self.n_layers):
                ref lw = self.layers[layer]
                var is_global = self.layer_is_global[layer]

                # 1 ── rmsnorm(input_layernorm), B rows
                self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                    self.xn.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln1.unsafe_ptr(),
                    Int64(self.d_model), self.eps, Int64(B),
                    grid_dim=B, block_dim=_TG,
                )
                # 2 ── fused QKV GEMM [B, d_model] -> [B, n_qkv]
                if use_tc:
                    @parameter
                    if not G3_STREAM:
                        self.ctx.synchronize()
                    var r = _tc_gemm_dispatch_auto(
                        Int(self.xn.unsafe_ptr()),
                        Int(lw.w_qkv.unsafe_ptr()), 0,
                        B, self.d_model, n_qkv,
                        Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                        Int(self.qkv.unsafe_ptr()), 0)
                    if r != 0:
                        return RESIDENT_ERR_LAUNCH_FAILED
                else:
                    self.ctx.enqueue_function[_pf_gemm_assign_kernel_v2h](
                        self.qkv.unsafe_ptr(), self.xn.unsafe_ptr(), lw.w_qkv.unsafe_ptr(),
                        Int64(B), Int64(self.d_model), Int64(n_qkv),
                        grid_dim=_ceil_div(B, _G2_BM) * _ceil_div(n_qkv, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                @parameter
                if _G3B_DBG:
                    if layer == 0 or layer == self.n_layers - 1:
                        self.ctx.synchronize()
                        print("DBG step: L", layer, "qkv ok")
                # 3 ── q/k norm + per-layer rope + KV write at b*kv_stride + pos slots
                var cos_p = self.cos_global.unsafe_ptr() if is_global == 1 \
                    else self.cos_local.unsafe_ptr()
                var sin_p = self.sin_global.unsafe_ptr() if is_global == 1 \
                    else self.sin_local.unsafe_ptr()
                @parameter
                if G3_BATCH_KV_F16:
                    self.ctx.enqueue_function[_g3_ropewrt_batched_kernel_kv16](
                        self.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                        self.qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                        cos_p, sin_p, self.dev_poss.unsafe_ptr(), Int64(self.kv_stride_elems),
                        Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head), self.eps,
                        Int64(B), Int64(1),
                        grid_dim=(self.h_q + self.h_kv) * B, block_dim=self.d_head,
                    )
                else:
                    self.ctx.enqueue_function[_g3_ropewrt_batched_kernel](
                        self.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                        self.qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                        cos_p, sin_p, self.dev_poss.unsafe_ptr(), Int64(self.kv_stride_elems),
                        Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head), self.eps,
                        Int64(B), Int64(1),
                        grid_dim=(self.h_q + self.h_kv) * B, block_dim=self.d_head,
                    )
                # 4 ── windowed batched flash-decoding attention
                var window_arg = 0 if is_global == 1 else self.sliding_window
                @parameter
                if G3_BATCH_KV_F16:
                    var use_flash_attn = False
                    @parameter
                    if G3_ATTN_FLASH:
                        # fact-driven capability dispatch: the flash twin's lane contract is
                        # d_head == 128 == WARP_SIZE * 4; any other head dim stays
                        # byte-for-byte on the legacy partial.
                        use_flash_attn = self.d_head == 128
                    if use_flash_attn:
                        self.ctx.enqueue_function[
                            _g3_kv_decode_splitk_partial_batched_kernel_kv16_flash
                        ](
                            self.sk_m.unsafe_ptr(), self.sk_l.unsafe_ptr(),
                            self.sk_o.unsafe_ptr(),
                            self.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                            self.dev_nkeys.unsafe_ptr(), Int64(B),
                            Int64(self.kv_stride_elems),
                            Int64(G3_BATCH_N_SPLITS), Int64(self.h_q), Int64(self.h_kv),
                            Int64(self.d_head), self.scale, Int64(window_arg),
                            grid_dim=_ceil_div(
                                B * self.h_q * G3_BATCH_N_SPLITS,
                                _G3_DECODE_FLASH_WARPS_PER_BLOCK,
                            ),
                            block_dim=_G3_DECODE_FLASH_NTHREADS,
                        )
                    else:
                        self.ctx.enqueue_function[
                            _g3_kv_decode_splitk_partial_batched_kernel_kv16
                        ](
                            self.sk_m.unsafe_ptr(), self.sk_l.unsafe_ptr(),
                            self.sk_o.unsafe_ptr(),
                            self.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                            self.dev_nkeys.unsafe_ptr(), Int64(self.kv_stride_elems),
                            Int64(G3_BATCH_N_SPLITS), Int64(self.h_q), Int64(self.h_kv),
                            Int64(self.d_head), self.scale, Int64(window_arg),
                            grid_dim=B * self.h_q * G3_BATCH_N_SPLITS, block_dim=self.d_head,
                        )
                else:
                    self.ctx.enqueue_function[_g3_kv_decode_splitk_partial_batched_kernel](
                        self.sk_m.unsafe_ptr(), self.sk_l.unsafe_ptr(), self.sk_o.unsafe_ptr(),
                        self.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                        self.dev_nkeys.unsafe_ptr(), Int64(self.kv_stride_elems),
                        Int64(G3_BATCH_N_SPLITS), Int64(self.h_q), Int64(self.h_kv),
                        Int64(self.d_head), self.scale, Int64(window_arg),
                        grid_dim=B * self.h_q * G3_BATCH_N_SPLITS, block_dim=self.d_head,
                    )
                self.ctx.enqueue_function[_native_kv_decode_splitk_merge_batched_f32_kernel](
                    self.attn.unsafe_ptr(), self.sk_m.unsafe_ptr(), self.sk_l.unsafe_ptr(),
                    self.sk_o.unsafe_ptr(),
                    Int64(G3_BATCH_N_SPLITS), Int64(self.h_q), Int64(self.d_head),
                    grid_dim=B * self.h_q, block_dim=self.d_head,
                )
                @parameter
                if _G3B_DBG:
                    if layer == 0 or layer == self.n_layers - 1:
                        self.ctx.synchronize()
                        print("DBG step: L", layer, "attn ok")
                # 5 ── o_proj into the branch scratch (ASSIGN)
                if use_tc:
                    @parameter
                    if not G3_STREAM:
                        self.ctx.synchronize()
                    var r = _tc_gemm_dispatch_auto(
                        Int(self.attn.unsafe_ptr()),
                        Int(lw.w_o.unsafe_ptr()), 0,
                        B, n_q, self.d_model,
                        Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                        Int(self.branch.unsafe_ptr()), 0)
                    if r != 0:
                        return RESIDENT_ERR_LAUNCH_FAILED
                else:
                    self.ctx.enqueue_function[_pf_gemm_assign_kernel_v2h](
                        self.branch.unsafe_ptr(), self.attn.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                        Int64(B), Int64(n_q), Int64(self.d_model),
                        grid_dim=_ceil_div(B, _G2_BM) * _ceil_div(self.d_model, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                # 6 ── hidden += rmsnorm(branch) * (1+w_post_attention)
                self.ctx.enqueue_function[_pf_norm_accum_rows_kernel](
                    self.hidden.unsafe_ptr(), self.branch.unsafe_ptr(), lw.ln2.unsafe_ptr(),
                    Int64(self.d_model), self.eps, Int64(B),
                    grid_dim=B, block_dim=_TG,
                )
                # 7 ── rmsnorm(pre_feedforward_layernorm)
                self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                    self.xn.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln3.unsafe_ptr(),
                    Int64(self.d_model), self.eps, Int64(B),
                    grid_dim=B, block_dim=_TG,
                )
                # 8 ── gate/up + GeGLU
                if use_tc:
                    @parameter
                    if not G3_STREAM:
                        self.ctx.synchronize()
                    var r = _tc_gemm_dispatch_auto(
                        Int(self.xn.unsafe_ptr()),
                        Int(lw.w_gu.unsafe_ptr()), 0,
                        B, self.d_model, 2 * self.d_ff,
                        Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                        Int(self.gu.unsafe_ptr()), 0)
                    if r != 0:
                        return RESIDENT_ERR_LAUNCH_FAILED
                    self.ctx.enqueue_function[_pf_geglu_rows_kernel](
                        self.act.unsafe_ptr(), self.gu.unsafe_ptr(),
                        Int64(B * self.d_ff), Int64(self.d_ff),
                        grid_dim=_ceil_div(B * self.d_ff, _TG), block_dim=_TG,
                    )
                else:
                    self.ctx.enqueue_function[_pf_gemm_geglu_kernel_v2h](
                        self.act.unsafe_ptr(), self.xn.unsafe_ptr(), lw.w_gu.unsafe_ptr(),
                        Int64(B), Int64(self.d_model), Int64(self.d_ff),
                        grid_dim=_ceil_div(B, _G2_BM) * _ceil_div(self.d_ff, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                # 9 ── down_proj into the branch scratch (ASSIGN)
                if use_tc:
                    @parameter
                    if not G3_STREAM:
                        self.ctx.synchronize()
                    var r = _tc_gemm_dispatch_auto(
                        Int(self.act.unsafe_ptr()),
                        Int(lw.w_down.unsafe_ptr()), 0,
                        B, self.d_ff, self.d_model,
                        Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                        Int(self.branch.unsafe_ptr()), 0)
                    if r != 0:
                        return RESIDENT_ERR_LAUNCH_FAILED
                else:
                    self.ctx.enqueue_function[_pf_gemm_assign_kernel_v2h](
                        self.branch.unsafe_ptr(), self.act.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                        Int64(B), Int64(self.d_ff), Int64(self.d_model),
                        grid_dim=_ceil_div(B, _G2_BM) * _ceil_div(self.d_model, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                # 10 ── hidden += rmsnorm(branch) * (1+w_post_feedforward)
                self.ctx.enqueue_function[_pf_norm_accum_rows_kernel](
                    self.hidden.unsafe_ptr(), self.branch.unsafe_ptr(), lw.ln4.unsafe_ptr(),
                    Int64(self.d_model), self.eps, Int64(B),
                    grid_dim=B, block_dim=_TG,
                )
                @parameter
                if _G3B_DBG:
                    if layer == 0 or layer == self.n_layers - 1:
                        self.ctx.synchronize()
                        print("DBG step: L", layer, "mlp ok")

            # ── tail: B-row final rmsnorm + one-sweep batched lm_head + B-row reduce ──
            self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                self.xn.unsafe_ptr(), self.hidden.unsafe_ptr(), self.final_norm.unsafe_ptr(),
                Int64(self.d_model), self.eps, Int64(B),
                grid_dim=B, block_dim=_TG,
            )
            @parameter
            if _G3B_DBG:
                self.ctx.synchronize()
                print("DBG step: tail norm ok")
            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
            @parameter
            if G3_STREAM:
                # THE cuBLAS lm_head lever (nsys 2026-08-24): the fused B-row kernel cost
                # 48.2 ms/step at B=50 (43% of the 112 ms step — its per-thread B-row
                # accumulator arrays collapse occupancy at B=50); the SAME logits GEMM
                # rides the stream-ordered seam at HBM speed, then one small argmax sweep
                # replaces BOTH the fused kernel and its separate reduce stage.
                var r = _tc_gemm_dispatch_auto(
                    Int(self.xn.unsafe_ptr()),
                    Int(self.embed.unsafe_ptr()), 0,
                    B, self.d_model, self.vocab,
                    Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                    Int(self.logits.unsafe_ptr()), 0)
                if r != 0:
                    return RESIDENT_ERR_LAUNCH_FAILED
                self.ctx.enqueue_function[_g3_logits_argmax_kernel](
                    self.out_val.unsafe_ptr(), self.out_idx.unsafe_ptr(),
                    self.logits.unsafe_ptr(), Int64(B), Int64(self.vocab),
                    grid_dim=B, block_dim=_TG,
                )
            else:
                self.ctx.enqueue_function[_g3_batched_lmhead_argmax_kernel_f16](
                    self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(),
                    self.xn.unsafe_ptr(),
                    self.embed.unsafe_ptr(),
                    Int64(B), Int64(self.d_model), Int64(self.vocab), Int64(n_iters),
                    grid_dim=_LM_BLOCKS, block_dim=_TG,
                )
                @parameter
                if _G3B_DBG:
                    self.ctx.synchronize()
                    print("DBG step: batched lm_head ok")
                self.ctx.enqueue_function[_batched_argmax_reduce_kernel_simd](
                    self.out_val.unsafe_ptr(), self.out_idx.unsafe_ptr(),
                    self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(),
                    Int64(_LM_BLOCKS),
                    grid_dim=B, block_dim=_TG,
                )
            @parameter
            if _G3B_DBG:
                self.ctx.synchronize()
                print("DBG step: reduce ok")

            self.ctx.enqueue_copy(self.host_val, self.out_val)
            self.ctx.enqueue_copy(self.host_idx, self.out_idx)
            self.ctx.synchronize()
            return RESIDENT_OK

    def batch_token(self, b: Int) -> Int:
        return Int(self.host_idx.unsafe_ptr()[b])
