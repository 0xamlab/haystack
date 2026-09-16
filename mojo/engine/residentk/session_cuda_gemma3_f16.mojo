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
        # the cuBLAS handle bind, then the lazy per-kernel CUDA module loads.
        self.ensure_tc_ready()
        @parameter
        if CUDA_GEMMA3_BUILD:
            self._prime_prefill_modules()
        self.ctx.synchronize()
        return RESIDENT_OK

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

                    # 1 ── rmsnorm(input_layernorm) over every row
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
                    # 3 ── q_norm + k_norm + per-class RoPE + the in-place KV-cache write
                    var cos_p = self.cos_global.unsafe_ptr() if is_global == 1 \
                        else self.cos_local.unsafe_ptr()
                    var sin_p = self.sin_global.unsafe_ptr() if is_global == 1 \
                        else self.sin_local.unsafe_ptr()
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
                    if use_tc_attn:
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
                    #      forbids the llama-style residual accumulate)
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
                    # 6 ── hidden += rmsnorm(branch) * (1+w_post_attention), every row
                    self.ctx.enqueue_function[_pf_norm_accum_rows_kernel](
                        self.pf_hidden.unsafe_ptr(), self.pf_branch.unsafe_ptr(),
                        lw.ln2.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # 7 ── rmsnorm(pre_feedforward_layernorm) over every row
                    self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        self.pf_xn.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                        lw.ln3.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # 8 ── gate/up + GeGLU — TC seam (+ native GeGLU epilogue) or the fused
                    #      v2h kernel
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
                    # 9 ── down_proj into the branch scratch (ASSIGN)
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
