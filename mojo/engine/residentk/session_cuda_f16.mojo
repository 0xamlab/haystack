"""
residentk.session_cuda_f16 — the CUDA-native FLOAT16-weight resident session: the format-fair
NVIDIA race arm. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float16
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/qwen3_generate_cuda.mojo
benchmark: benchmarks/llm_smoke/qwen3_bench_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Every entry point is private, and every launch is gated — the same two
defences `residentk.session_cuda`'s module docstring documents (private names out of the
inventory/dispatch; `CUDA_SESSION_BUILD` elides every launch before shader codegen on a
Metal/CPU build).

What this session is, and why it exists
----------------------------------------
The A100 kernel sweep (REALRACE_RESULTS.md 2026-08-20) measured the CUDA decode arm's GEMV
family AT its f32 bandwidth floor (54-102% of HBM peak) — the only way to move those kernels
is fewer BYTES. This session halves every weight stream: the four per-layer GEMV matrices and
the tied embed/lm_head table are resident Float16, read through the `_f16` kernel twins the
Metal lane already proved (mixed precision: activations, accumulators, norm gains, RoPE tables
and the KV cache all stay Float32 — storage shrinks, arithmetic does not).

It is ALSO the format-fair race arm: llama.cpp's race control is an F16 GGUF, so F16-vs-F16 is
the apples-to-apples row the f32 arm's fairness caveat always pointed at.

Decode runs through the same CUDA-graph arm `residentk.session_cuda` established (one captured
graph, device-side generation chain, zero per-token host traffic), with the split-K
flash-decoding attention pair — the sweep's named decode bottleneck — included in the capture.
Prefill is the batched m_rows > 1 path with the Float16-weight tiled GEMM twins from
`residentk.kernels_prefill_f16`.
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
from std.sys import has_accelerator, is_defined
from residentk.contract import (
    RESIDENT_ERR_CONTEXT_FULL,
    RESIDENT_ERR_LAUNCH_FAILED,
    RESIDENT_ERR_NO_DEVICE,
    RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT,
    RESIDENT_ERR_UPLOAD_LENGTH,
    RESIDENT_OK,
    residentk_dispatch_budget,
)
from residentk.kernels import (
    _TG,
    _SUBS,
    _argmax_reduce_kernel,
    _embed_row_kernel_f16,
    _gemv_accum_kernel_f16,
    _lmhead_argmax_kernel_f16,
    _norm_gemv_kernel_f16,
    _norm_gemv2_swiglu_kernel_f16,
    _qk_rope_write_kernel,
    _splitk_merge_kernel_simd,
    _pf_rmsnorm_rows_kernel,
    _pf_ropewrt_kernel,
    _pf_attn_tiled_kernel_simd,
)
from residentk.kernels_prefill_f16 import (
    _GEMM_BM,
    _GEMM_BN,
    _GEMM_NTHREADS,
    _pf_embed_rows_kernel_f16,
    _pf_gemm_assign_kernel_f16,
    _pf_gemm_accum_kernel_f16,
    _pf_gemm_swiglu_kernel_f16,
)
from residentk.kernels_cuda_graph import (
    _embed_row_kernel_f16_g,
    _graph_advance_kernel,
    _qk_rope_write_kernel_g,
    _splitk_partial_kernel_simd_g,
)
from residentk.session import (
    RESIDENT_GPU_BUILD,
    _LM_BLOCKS,
    _LayerGpuF16,
    _StepOut,
    _ceil_div,
    _narrow_into,
    _narrow_into_f16,
    _narrow_transposed_into_f16,
)
from residentk.session_cuda import CUDA_GRAPH_N_SPLITS, CUDA_PREFILL_TILE, CUDA_SESSION_BUILD

comptime _HP = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]


@fieldwise_init
struct _CudaResidentQwen3F16(Movable):
    """The Float16-weight CUDA-native resident session. Same resident-state design and same
    per-token contract as `_CudaResidentQwen3`; the four per-layer GEMV matrices and the tied
    embed/lm_head table are resident Float16, everything else (activations, KV cache, norm
    gains, RoPE tables, argmax scratch) stays Float32 — the same mixed-precision split
    `_ResidentQwen3F16` documents on the Metal side."""

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

    var layers: List[_LayerGpuF16]
    var embed: DeviceBuffer[DType.float16]
    var final_norm: DeviceBuffer[DType.float32]
    var cos_t: DeviceBuffer[DType.float32]
    var sin_t: DeviceBuffer[DType.float32]

    # decode scratch — one token's working set (Float32 activations)
    var hidden: DeviceBuffer[DType.float32]
    var qkv: DeviceBuffer[DType.float32]
    var q_rot: DeviceBuffer[DType.float32]
    var attn_out: DeviceBuffer[DType.float32]
    var act: DeviceBuffer[DType.float32]
    var blk_val: DeviceBuffer[DType.float32]
    var blk_idx: DeviceBuffer[DType.int32]
    var out_val: DeviceBuffer[DType.float32]
    var out_idx: DeviceBuffer[DType.int32]
    var host_val: HostBuffer[DType.float32]
    var host_idx: HostBuffer[DType.int32]

    # prefill scratch — one CUDA_PREFILL_TILE-row working set
    var pf_tokens: DeviceBuffer[DType.int32]
    var pf_hidden: DeviceBuffer[DType.float32]
    var pf_xn: DeviceBuffer[DType.float32]
    var pf_qkv: DeviceBuffer[DType.float32]
    var pf_q_rot: DeviceBuffer[DType.float32]
    var pf_attn: DeviceBuffer[DType.float32]
    var pf_act: DeviceBuffer[DType.float32]

    # decode-graph arm (same design as residentk.session_cuda's)
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
    ) raises:
        """Open the context and allocate every resident + scratch buffer. ONCE."""
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

        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

        self.layers = List[_LayerGpuF16]()
        for _ in range(n_layers):
            self.layers.append(
                _LayerGpuF16(
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
        self.cos_t = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
        self.sin_t = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)

        self.hidden = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.qkv = self.ctx.enqueue_create_buffer[DType.float32](n_qkv)
        self.q_rot = self.ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
        self.attn_out = self.ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
        self.act = self.ctx.enqueue_create_buffer[DType.float32](d_ff)
        self.blk_val = self.ctx.enqueue_create_buffer[DType.float32](_LM_BLOCKS)
        self.blk_idx = self.ctx.enqueue_create_buffer[DType.int32](_LM_BLOCKS)
        self.out_val = self.ctx.enqueue_create_buffer[DType.float32](1)
        self.out_idx = self.ctx.enqueue_create_buffer[DType.int32](1)
        self.host_val = self.ctx.enqueue_create_host_buffer[DType.float32](1)
        self.host_idx = self.ctx.enqueue_create_host_buffer[DType.int32](1)

        var t = CUDA_PREFILL_TILE
        self.pf_tokens = self.ctx.enqueue_create_buffer[DType.int32](t)
        self.pf_hidden = self.ctx.enqueue_create_buffer[DType.float32](t * d_model)
        self.pf_xn = self.ctx.enqueue_create_buffer[DType.float32](t * d_model)
        self.pf_qkv = self.ctx.enqueue_create_buffer[DType.float32](t * n_qkv)
        self.pf_q_rot = self.ctx.enqueue_create_buffer[DType.float32](t * h_q * d_head)
        self.pf_attn = self.ctx.enqueue_create_buffer[DType.float32](t * h_q * d_head)
        self.pf_act = self.ctx.enqueue_create_buffer[DType.float32](t * d_ff)

        self.step_state = self.ctx.enqueue_create_buffer[DType.int64](3)
        self.host_state = self.ctx.enqueue_create_host_buffer[DType.int64](3)
        self.token_log = self.ctx.enqueue_create_buffer[DType.int64](max_ctx)
        self.host_token_log = self.ctx.enqueue_create_host_buffer[DType.int64](max_ctx)
        self.sk_m = self.ctx.enqueue_create_buffer[DType.float32](h_q * CUDA_GRAPH_N_SPLITS)
        self.sk_l = self.ctx.enqueue_create_buffer[DType.float32](h_q * CUDA_GRAPH_N_SPLITS)
        self.sk_o = self.ctx.enqueue_create_buffer[DType.float32](
            h_q * CUDA_GRAPH_N_SPLITS * d_head
        )
        self.decode_graph = Optional[DeviceGraph]()
        self.decode_graph_built = False

    def device_name(self) raises -> String:
        return self.ctx.name()

    def dispatch_budget(self) -> Int:
        return residentk_dispatch_budget(self.n_layers)

    def upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        """The tied embedding/lm_head table narrowed to FLOAT16, the final norm gain Float32,
        the RoPE tables Float32 — the f16 twin of `_CudaResidentQwen3.upload_globals`."""
        var n_pairs = self.d_head // 2
        if n_pos > self.max_ctx:
            return RESIDENT_ERR_CONTEXT_FULL
        var s = _narrow_into_f16(self.embed, embed, self.vocab * self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(self.final_norm, final_norm, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        if len(cos_t) < n_pos * n_pairs or len(sin_t) < n_pos * n_pairs:
            return RESIDENT_ERR_UPLOAD_LENGTH
        with self.cos_t.map_to_host() as h:
            for i in range(n_pos * n_pairs):
                h[i] = Float32(cos_t[i])
        with self.sin_t.map_to_host() as h:
            for i in range(n_pos * n_pairs):
                h[i] = Float32(sin_t[i])
        return RESIDENT_OK

    def upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        """One layer's eleven checkpoint tensors: norm gains Float32 (exact, as the f32 session),
        the four GEMV weight matrices transposed and narrowed to FLOAT16."""
        if layer < 0 or layer >= self.n_layers:
            return RESIDENT_ERR_UPLOAD_LENGTH
        ref lw = self.layers[layer]
        var s = _narrow_into(lw.ln1, ln1, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.ln2, ln2, self.d_model, 0)
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
        """Drain every upload before the first dispatch. One synchronize for the whole load."""
        self.ctx.synchronize()
        return RESIDENT_OK

    def prefill(mut self, prompt_ids: List[Int]) raises -> _StepOut:
        """The whole prompt through the batched Float16-weight prefill path, then ONE lm_head +
        argmax on the final position. Same chunking and same `_StepOut` contract as
        `_CudaResidentQwen3.prefill`."""

        @parameter
        if not CUDA_SESSION_BUILD:
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

            var n_q = self.h_q * self.d_head
            var issued = 0
            var pos = 0
            var last_m = 0
            while pos < n_prompt:
                var m = CUDA_PREFILL_TILE
                if n_prompt - pos < m:
                    m = n_prompt - pos
                last_m = m

                with self.pf_tokens.map_to_host() as h:
                    for i in range(m):
                        h[i] = Int32(prompt_ids[pos + i])
                self.ctx.synchronize()

                self.ctx.enqueue_function[_pf_embed_rows_kernel_f16](
                    self.pf_hidden.unsafe_ptr(), self.embed.unsafe_ptr(),
                    self.pf_tokens.unsafe_ptr(),
                    Int64(self.d_model), Int64(m),
                    grid_dim=_ceil_div(self.d_model, _TG) * m, block_dim=_TG,
                )
                issued += 1

                for layer in range(self.n_layers):
                    ref lw = self.layers[layer]

                    # 1 ── rmsnorm over every row (weightless — dispatched byte-unmodified)
                    self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        self.pf_xn.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                        lw.ln1.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # 2 ── fused Q/K/V projection, one tiled GEMM (ASSIGN), f16 weights
                    self.ctx.enqueue_function[_pf_gemm_assign_kernel_f16](
                        self.pf_qkv.unsafe_ptr(), self.pf_xn.unsafe_ptr(),
                        lw.w_qkv.unsafe_ptr(),
                        Int64(m), Int64(self.d_model),
                        Int64((self.h_q + 2 * self.h_kv) * self.d_head),
                        grid_dim=_ceil_div(m, _GEMM_BM)
                            * _ceil_div((self.h_q + 2 * self.h_kv) * self.d_head, _GEMM_BN),
                        block_dim=_GEMM_NTHREADS,
                    )
                    # 3 ── q/k norm + RoPE + in-place KV write, every row (weightless)
                    self.ctx.enqueue_function[_pf_ropewrt_kernel](
                        self.pf_q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                        self.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                        self.cos_t.unsafe_ptr(), self.sin_t.unsafe_ptr(),
                        Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                        self.eps, Int64(m),
                        Int64(1),  # qk_norm: Qwen3-family only, per-head QK-norm always on
                        grid_dim=(self.h_q + self.h_kv) * m, block_dim=self.d_head,
                    )
                    # 4 ── causal attention (weightless)
                    self.ctx.enqueue_function[_pf_attn_tiled_kernel_simd](
                        self.pf_attn.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                        lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                        Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                        self.scale, Int64(m),
                        grid_dim=self.h_q * m, block_dim=self.d_head,
                    )
                    # 5 ── o_proj ACCUMULATE into the residual stream, f16 weights
                    self.ctx.enqueue_function[_pf_gemm_accum_kernel_f16](
                        self.pf_hidden.unsafe_ptr(), self.pf_attn.unsafe_ptr(),
                        lw.w_o.unsafe_ptr(),
                        Int64(m), Int64(n_q), Int64(self.d_model),
                        grid_dim=_ceil_div(m, _GEMM_BM) * _ceil_div(self.d_model, _GEMM_BN),
                        block_dim=_GEMM_NTHREADS,
                    )
                    # 6 ── rmsnorm over every row (weightless)
                    self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        self.pf_xn.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                        lw.ln2.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # 7 ── gate/up + SwiGLU, one tiled GEMM pair, f16 weights
                    self.ctx.enqueue_function[_pf_gemm_swiglu_kernel_f16](
                        self.pf_act.unsafe_ptr(), self.pf_xn.unsafe_ptr(),
                        lw.w_gu.unsafe_ptr(),
                        Int64(m), Int64(self.d_model), Int64(self.d_ff),
                        grid_dim=_ceil_div(m, _GEMM_BM) * _ceil_div(self.d_ff, _GEMM_BN),
                        block_dim=_GEMM_NTHREADS,
                    )
                    # 8 ── down_proj ACCUMULATE into the residual stream, f16 weights
                    self.ctx.enqueue_function[_pf_gemm_accum_kernel_f16](
                        self.pf_hidden.unsafe_ptr(), self.pf_act.unsafe_ptr(),
                        lw.w_down.unsafe_ptr(),
                        Int64(m), Int64(self.d_ff), Int64(self.d_model),
                        grid_dim=_ceil_div(m, _GEMM_BM) * _ceil_div(self.d_model, _GEMM_BN),
                        block_dim=_GEMM_NTHREADS,
                    )
                    issued += 8
                pos += m

            # ── final rmsnorm + f16 lm_head + per-threadgroup argmax on the LAST row only ──
            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
            self.ctx.enqueue_function[_lmhead_argmax_kernel_f16](
                self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(),
                self.pf_hidden.unsafe_ptr() + (last_m - 1) * self.d_model,
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

    def _build_decode_graph(mut self) raises:
        """Capture the Float16-weight per-token decode sequence into ONE DeviceGraph — the same
        kernels-only discipline `residentk.session_cuda._build_decode_graph` documents (eager
        copies around the replay; recorded memcpy nodes never touch the caller's buffers), with
        the f16 GEMV twins and the split-K flash-decoding attention pair in the capture."""
        var hidden_a = Int(self.hidden.unsafe_ptr())
        var qkv_a = Int(self.qkv.unsafe_ptr())
        var q_rot_a = Int(self.q_rot.unsafe_ptr())
        var attn_out_a = Int(self.attn_out.unsafe_ptr())
        var act_a = Int(self.act.unsafe_ptr())
        var blk_val_a = Int(self.blk_val.unsafe_ptr())
        var blk_idx_a = Int(self.blk_idx.unsafe_ptr())
        var out_val_a = Int(self.out_val.unsafe_ptr())
        var out_idx_a = Int(self.out_idx.unsafe_ptr())
        var embed_a = Int(self.embed.unsafe_ptr())
        var final_norm_a = Int(self.final_norm.unsafe_ptr())
        var cos_a = Int(self.cos_t.unsafe_ptr())
        var sin_a = Int(self.sin_t.unsafe_ptr())
        var state_a = Int(self.step_state.unsafe_ptr())
        var tlog_a = Int(self.token_log.unsafe_ptr())
        var skm_a = Int(self.sk_m.unsafe_ptr())
        var skl_a = Int(self.sk_l.unsafe_ptr())
        var sko_a = Int(self.sk_o.unsafe_ptr())

        var ln1s = List[Int]()
        var ln2s = List[Int]()
        var qns = List[Int]()
        var kns = List[Int]()
        var w_qkvs = List[Int]()
        var w_os = List[Int]()
        var w_gus = List[Int]()
        var w_downs = List[Int]()
        var cks = List[Int]()
        var cvs = List[Int]()
        for layer in range(self.n_layers):
            ref lw = self.layers[layer]
            ln1s.append(Int(lw.ln1.unsafe_ptr()))
            ln2s.append(Int(lw.ln2.unsafe_ptr()))
            qns.append(Int(lw.qn.unsafe_ptr()))
            kns.append(Int(lw.kn.unsafe_ptr()))
            w_qkvs.append(Int(lw.w_qkv.unsafe_ptr()))
            w_os.append(Int(lw.w_o.unsafe_ptr()))
            w_gus.append(Int(lw.w_gu.unsafe_ptr()))
            w_downs.append(Int(lw.w_down.unsafe_ptr()))
            cks.append(Int(lw.ck.unsafe_ptr()))
            cvs.append(Int(lw.cv.unsafe_ptr()))

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
        var n_iters_i = Int64(_ceil_div(self.vocab, _LM_BLOCKS * _SUBS))

        def build(mut builder: DeviceGraphBuilder) raises {imm}:
            var hidden_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=hidden_a)
            var qkv_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=qkv_a)
            var q_rot_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=q_rot_a)
            var attn_out_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=attn_out_a)
            var act_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=act_a)
            var blk_val_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=blk_val_a)
            var blk_idx_p = UnsafePointer[Int32, origin=MutAnyOrigin](unsafe_from_address=blk_idx_a)
            var out_val_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=out_val_a)
            var out_idx_p = UnsafePointer[Int32, origin=MutAnyOrigin](unsafe_from_address=out_idx_a)
            var embed_p = UnsafePointer[Float16, origin=MutAnyOrigin](unsafe_from_address=embed_a)
            var final_norm_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=final_norm_a)
            var cos_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cos_a)
            var sin_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=sin_a)
            var state_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=state_a)
            var tlog_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=tlog_a)

            var rec = builder.recording_context()

            # ── the embedding row from the f16 tied table ──
            rec.enqueue_function[_embed_row_kernel_f16_g](
                hidden_p, embed_p, state_p, d_model_i,
                grid_dim=_ceil_div(Int(d_model_i), _TG), block_dim=_TG,
            )

            for layer in range(n_layers_c):
                var ln1_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=ln1s[layer])
                var ln2_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=ln2s[layer])
                var qn_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=qns[layer])
                var kn_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=kns[layer])
                var wqkv_p = UnsafePointer[Float16, origin=MutAnyOrigin](unsafe_from_address=w_qkvs[layer])
                var wo_p = UnsafePointer[Float16, origin=MutAnyOrigin](unsafe_from_address=w_os[layer])
                var wgu_p = UnsafePointer[Float16, origin=MutAnyOrigin](unsafe_from_address=w_gus[layer])
                var wd_p = UnsafePointer[Float16, origin=MutAnyOrigin](unsafe_from_address=w_downs[layer])
                var ck_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cks[layer])
                var cv_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cvs[layer])
                # 1 ── rmsnorm + fused Q/K/V GEMV, f16 weights
                rec.enqueue_function[_norm_gemv_kernel_f16](
                    qkv_p, hidden_p, ln1_p,
                    wqkv_p, d_model_i, n_qkv_i, eps_c,
                    grid_dim=_ceil_div(Int(n_qkv_i), _SUBS), block_dim=_TG,
                )
                # 2 ── q/k norm + RoPE + in-place KV write (pos: state[1])
                rec.enqueue_function[_qk_rope_write_kernel_g](
                    q_rot_p, ck_p, cv_p,
                    qkv_p, qn_p, kn_p,
                    cos_p, sin_p,
                    state_p, h_q_i, h_kv_i, d_head_i, eps_c,
                    Int64(1),
                    grid_dim=Int(h_q_i) + Int(h_kv_i), block_dim=Int(d_head_i),
                )
                # 3 ── split-K flash-decoding attention (n_keys: state[2])
                var skm_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=skm_a)
                var skl_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=skl_a)
                var sko_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=sko_a)
                rec.enqueue_function[_splitk_partial_kernel_simd_g](
                    skm_p, skl_p, sko_p, q_rot_p,
                    ck_p, cv_p,
                    state_p, Int64(CUDA_GRAPH_N_SPLITS), h_q_i, h_kv_i, d_head_i, scale_c,
                    grid_dim=Int(h_q_i) * CUDA_GRAPH_N_SPLITS, block_dim=Int(d_head_i),
                )
                rec.enqueue_function[_splitk_merge_kernel_simd](
                    attn_out_p, skm_p, skl_p, sko_p,
                    Int64(CUDA_GRAPH_N_SPLITS), d_head_i,
                    grid_dim=Int(h_q_i), block_dim=Int(d_head_i),
                )
                # 4 ── o_proj GEMV + residual, f16 weights
                rec.enqueue_function[_gemv_accum_kernel_f16](
                    hidden_p, attn_out_p, wo_p,
                    n_q_i, d_model_i,
                    grid_dim=_ceil_div(Int(d_model_i), _SUBS), block_dim=_TG,
                )
                # 5 ── rmsnorm + gate/up + SwiGLU, f16 weights
                rec.enqueue_function[_norm_gemv2_swiglu_kernel_f16](
                    act_p, hidden_p, ln2_p,
                    wgu_p, d_model_i, d_ff_i, eps_c,
                    grid_dim=_ceil_div(Int(d_ff_i), _SUBS), block_dim=_TG,
                )
                # 6 ── down_proj GEMV + residual, f16 weights
                rec.enqueue_function[_gemv_accum_kernel_f16](
                    hidden_p, act_p, wd_p,
                    d_ff_i, d_model_i,
                    grid_dim=_ceil_div(Int(d_model_i), _SUBS), block_dim=_TG,
                )

            # ── final rmsnorm + f16 lm_head + argmax + reduce ──
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
            # ── the device-side generation chain ──
            rec.enqueue_function[_graph_advance_kernel](
                state_p, out_idx_p, tlog_p,
                grid_dim=1, block_dim=1,
            )

        self.decode_graph = DeviceGraph.create(self.ctx, build)

    def seed_and_run_graph(
        mut self, first_token: Int, start_pos: Int, n_steps: Int,
    ) raises -> Int:
        """Run `n_steps` decode steps as back-to-back replays of the captured f16 graph — the
        same zero-per-token-host-traffic contract and same `graph_token(pos)` readback as
        `_CudaResidentQwen3.seed_and_run_graph`; see that method's docstring for the full
        semantics."""

        @parameter
        if not CUDA_SESSION_BUILD:
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
        """The token generated at ABSOLUTE position `pos` by the last `seed_and_run_graph`
        call, read from the host-side token log."""
        return Int(self.host_token_log.unsafe_ptr()[pos])
