"""
residentk.session_cuda_gemma3 — the CUDA-native FLOAT32 resident session for the Gemma 3 family
(Gemma 3 lane, 2026-08-23). Correctness arm first: byte/greedy identity against
`benchmarks/llm_smoke/gemma3/ref_gemma3_torch.py` is the acceptance gate. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/gemma3/ref_gemma3_torch.py
benchmark: benchmarks/llm_smoke/nvidia_race/gemma3_correctness_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module; private names, launches gated behind `CUDA_SESSION_BUILD` exactly the way
`residentk.session_cuda` documents (a Metal/CPU build elides every launch before shader codegen).

How Gemma 3 differs from the Qwen3/llama resident chain, and where each difference lands
-------------------------------------------------------------------------------------------
* FOUR RMSNorms per layer, and the residual wiring differs: Gemma 3 applies
  `post_attention_layernorm` to the o_proj branch output BEFORE the residual add, and
  `post_feedforward_layernorm` to the down_proj branch output before ITS add (llama/Qwen3 add the
  branch output raw, then norm the stream). So o_proj/down_proj run as a PLAIN GEMV into scratch
  (`_g3_gemv_kernel`) followed by `_g3_norm_accum_kernel` (norm + add), instead of `_gemv_accum_kernel`.
* `(1.0 + weight)` norm gain convention — handled ENTIRELY in the converter, which rebases every
  norm tensor to (1+w) before it reaches this session; every norm kernel here stays a plain
  gain-multiply and computes Gemma's math exactly.
* Dual RoPE: GLOBAL (full-attention) layers use theta_global WITH the config's linear factor
  dividing the inverse frequencies; LOCAL (sliding) layers use theta_local unscaled. The session
  holds TWO rope-table pairs and selects per layer at dispatch (no kernel change).
* Sliding-window attention: local layers attend only the last `sliding_window` keys — the decode
  attention kernel takes a key lower bound (`_g3_sdpa_window_kernel`), full layers pass 0.
* GeGLU with gelu_pytorch_tanh (`_g3_norm_gemv2_geglu_kernel`), not SwiGLU.
* sqrt(hidden_size) input-embedding scale (`_g3_embed_row_kernel`); the tied lm_head stays unscaled.
* Attention score scale is `query_pre_attn_scalar ** -0.5`, passed as `scale` (NOT d_head-based).

Decode-only this round: the prompt is ingested one token at a time through `step` (cautiously
correct — attention is causal and position-based, so sequential ingestion is bit-equivalent to a
parallel prefill), then generation continues through the same `step`. A real tiled prefill is the
named performance follow-up (TTFT); correctness does not depend on it.

Stage tier: built with `-D ALGENTA_STAGE_6144`. Gemma 3 27B's d_ff (21504) EXCEEDS every shared
tier, but `_g3_gemv_kernel` / `_g3_norm_gemv2_geglu_kernel` read the d_ff-wide activation from
GLOBAL memory above `_G3_STAGE_CAP`; only d_model (5376) and h_q*d_head (4096) are ever staged,
both under 6144. The driver validates that itself (`gemma3_dims_ok`) rather than
`residentk_dims_check`, whose stage formula (max(d_model, h_q*d_head, d_ff)) is conservative for a
family that never stages d_ff.
"""

from max.gpu.host import (
    DeviceBuffer,
    DeviceContext,
    HostBuffer,
)
from std.sys import is_defined
from residentk.contract import (
    RESIDENT_ERR_CONTEXT_FULL,
    RESIDENT_ERR_LAUNCH_FAILED,
    RESIDENT_ERR_NO_DEVICE,
    RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT,
    RESIDENT_ERR_UPLOAD_LENGTH,
    RESIDENT_MAX_HEAD_DIM,
    RESIDENT_OK,
)
from residentk.kernels import (
    _TG,
    _SUBS,
    _argmax_reduce_kernel,
    _lmhead_argmax_kernel,
    _norm_gemv_kernel,
    _qk_rope_write_kernel,
)
from residentk.kernels_gemma3 import (
    _g3_embed_row_kernel,
    _g3_gemv_kernel,
    _g3_norm_accum_kernel,
    _g3_norm_gemv2_geglu_kernel,
    _g3_norm_inplace_kernel,
    _g3_sdpa_window_kernel,
)
from residentk.session import (
    RESIDENT_GPU_BUILD,
    _LM_BLOCKS,
    _StepOut,
    _ceil_div,
    _narrow_into,
    _narrow_transposed_into,
)

comptime CUDA_GEMMA3_BUILD: Bool = RESIDENT_GPU_BUILD and is_defined["ALGENTA_CUDA"]()

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]


def gemma3_dims_ok(
    d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int, n_layers: Int, vocab: Int,
) -> Bool:
    """The gemma3 host shape gate. d_ff is allowed to exceed the shared tier (the gemma3 GEMV
    kernels read it from global memory); what MUST fit the staged kernels is
    max(d_model, h_q*d_head)."""
    if d_model <= 0 or h_q <= 0 or h_kv <= 0 or d_head <= 0 or d_ff <= 0:
        return False
    if n_layers <= 0 or vocab <= 0:
        return False
    if h_q % h_kv != 0:
        return False
    if (d_head & (d_head - 1)) != 0 or d_head > RESIDENT_MAX_HEAD_DIM:
        return False
    var staged = d_model
    if h_q * d_head > staged:
        staged = h_q * d_head
    # The reused norm/lmhead kernels stage d_model; the gemma3 GEMV kernels stage at most
    # max(d_model, h_q*d_head) (never d_ff). 6144 = the STAGE_6144 tier this session builds with.
    if staged > 6144:
        return False
    return True


@fieldwise_init
struct _G3LayerGpu(Copyable, Movable):
    """One Gemma 3 layer's resident Float32 weights + KV slice: FOUR norm gains (input_layernorm,
    post_attention_layernorm, pre_feedforward_layernorm, post_feedforward_layernorm), the per-head
    q/k norm gains, the four fused projection matrices, and the layer's KV cache slice."""

    var ln1: DeviceBuffer[DType.float32]
    var ln2: DeviceBuffer[DType.float32]
    var ln3: DeviceBuffer[DType.float32]
    var ln4: DeviceBuffer[DType.float32]
    var qn: DeviceBuffer[DType.float32]
    var kn: DeviceBuffer[DType.float32]
    var w_qkv: DeviceBuffer[DType.float32]
    var w_o: DeviceBuffer[DType.float32]
    var w_gu: DeviceBuffer[DType.float32]
    var w_down: DeviceBuffer[DType.float32]
    var ck: DeviceBuffer[DType.float32]
    var cv: DeviceBuffer[DType.float32]


@fieldwise_init
struct _CudaResidentGemma3(Movable):
    """The Gemma 3 CUDA-native resident session (Float32 weights, correctness arm)."""

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
    var scale: Float32          # query_pre_attn_scalar ** -0.5
    var embed_scale: Float32    # sqrt(hidden_size)
    var sliding_window: Int

    var layer_is_global: List[Int]   # host-side per-layer rope/window class (1 = full, 0 = sliding)
    var layers: List[_G3LayerGpu]
    var embed: DeviceBuffer[DType.float32]
    var final_norm: DeviceBuffer[DType.float32]
    var cos_global: DeviceBuffer[DType.float32]
    var sin_global: DeviceBuffer[DType.float32]
    var cos_local: DeviceBuffer[DType.float32]
    var sin_local: DeviceBuffer[DType.float32]

    # decode scratch
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
        # Copy the caller's per-layer class list element-wise (a borrowed List argument cannot
        # be moved into the field; the copy is n_layers Ints, once, at session-open time).
        self.layer_is_global = List[Int]()
        for i in range(n_layers):
            self.layer_is_global.append(layer_is_global[i])

        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

        self.layers = List[_G3LayerGpu]()
        for _ in range(n_layers):
            self.layers.append(
                _G3LayerGpu(
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](n_qkv * d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model * h_q * d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](2 * d_ff * d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model * d_ff),
                    self.ctx.enqueue_create_buffer[DType.float32](max_ctx * h_kv * d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](max_ctx * h_kv * d_head),
                )
            )

        self.embed = self.ctx.enqueue_create_buffer[DType.float32](vocab * d_model)
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
        var s = _narrow_into(self.embed, embed, self.vocab * self.d_model, 0)
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
        s = _narrow_transposed_into(lw.w_qkv, wq, self.d_model, n_q, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into(lw.w_qkv, wk, self.d_model, n_kv, n_q)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into(lw.w_qkv, wv, self.d_model, n_kv, n_q + n_kv)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into(lw.w_o, wo, n_q, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into(lw.w_gu, wgate, self.d_model, self.d_ff, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into(lw.w_gu, wup, self.d_model, self.d_ff, self.d_ff)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into(lw.w_down, wdown, self.d_ff, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        return RESIDENT_OK

    def seal(mut self) raises -> Int:
        self.ctx.synchronize()
        return RESIDENT_OK

    def step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """ONE Gemma 3 token at position `pos`: embed-scale, then per layer the four-norm chain
        with windowed attention + per-class rope, then final-norm + tied lm_head + argmax."""

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

            # ── the scaled embedding row ──
            self.ctx.enqueue_function[_g3_embed_row_kernel](
                self.hidden.unsafe_ptr(), self.embed.unsafe_ptr(),
                Int64(token_id), Int64(self.d_model), self.embed_scale,
                grid_dim=_ceil_div(self.d_model, _TG), block_dim=_TG,
            )
            issued += 1

            for layer in range(self.n_layers):
                ref lw = self.layers[layer]
                var is_global = self.layer_is_global[layer]

                # 1 ── rmsnorm(input_layernorm) + fused Q/K/V projection (reused kernel; the
                #      rebased (1+w) gain is data).
                self.ctx.enqueue_function[_norm_gemv_kernel](
                    self.qkv.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln1.unsafe_ptr(),
                    lw.w_qkv.unsafe_ptr(), Int64(self.d_model), Int64(n_qkv), self.eps,
                    grid_dim=_ceil_div(n_qkv, _SUBS), block_dim=_TG,
                )
                # 2 ── q_norm + k_norm + RoPE (per-class table) + KV-cache write.
                var cos_p = self.cos_global.unsafe_ptr() if is_global == 1 \
                    else self.cos_local.unsafe_ptr()
                var sin_p = self.sin_global.unsafe_ptr() if is_global == 1 \
                    else self.sin_local.unsafe_ptr()
                self.ctx.enqueue_function[_qk_rope_write_kernel](
                    self.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    self.qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                    cos_p, sin_p,
                    Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head), self.eps,
                    Int64(1),  # gemma3 always has QK-norm
                    grid_dim=self.h_q + self.h_kv, block_dim=self.d_head,
                )
                # 3 ── windowed attention: local layers start at max(0, n_keys - window).
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
                # 4 ── o_proj to scratch ──
                self.ctx.enqueue_function[_g3_gemv_kernel](
                    self.o_tmp.unsafe_ptr(), self.attn_out.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                    Int64(n_q), Int64(self.d_model),
                    grid_dim=_ceil_div(self.d_model, _SUBS), block_dim=_TG,
                )
                # 5 ── hidden += rmsnorm(o_proj_out) * (1+w_post_attention) ──
                self.ctx.enqueue_function[_g3_norm_accum_kernel](
                    self.hidden.unsafe_ptr(), self.o_tmp.unsafe_ptr(), lw.ln2.unsafe_ptr(),
                    Int64(self.d_model), self.eps,
                    grid_dim=1, block_dim=_TG,
                )
                # 6 ── rmsnorm(pre_feedforward_layernorm) + gate/up + GeGLU ──
                self.ctx.enqueue_function[_g3_norm_gemv2_geglu_kernel](
                    self.act.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln3.unsafe_ptr(),
                    lw.w_gu.unsafe_ptr(), Int64(self.d_model), Int64(self.d_ff), self.eps,
                    grid_dim=_ceil_div(self.d_ff, _SUBS), block_dim=_TG,
                )
                # 7 ── down_proj to scratch ──
                self.ctx.enqueue_function[_g3_gemv_kernel](
                    self.d_tmp.unsafe_ptr(), self.act.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                    Int64(self.d_ff), Int64(self.d_model),
                    grid_dim=_ceil_div(self.d_model, _SUBS), block_dim=_TG,
                )
                # 8 ── hidden += rmsnorm(down_out) * (1+w_post_feedforward) ──
                self.ctx.enqueue_function[_g3_norm_accum_kernel](
                    self.hidden.unsafe_ptr(), self.d_tmp.unsafe_ptr(), lw.ln4.unsafe_ptr(),
                    Int64(self.d_model), self.eps,
                    grid_dim=1, block_dim=_TG,
                )
                issued += 8

            # ── final rmsnorm + tied lm_head + per-threadgroup argmax, then the reduce ──
            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
            self.ctx.enqueue_function[_lmhead_argmax_kernel](
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
        """Materialise the current `hidden`'s logits row (final norm + tied lm_head) and copy it
        to the host. The engine-gate's logit-for-logit comparison calls this after ingesting the
        prompt (random-weight synthetic models collapse to token attractors, so the logits are the
        stronger identity proof). Returns a status; read via `read_logits`."""
        @parameter
        if not CUDA_GEMMA3_BUILD:
            return RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT
        else:
            # final norm in place on hidden (rebased gain), then logits = embed @ hidden.
            self.ctx.enqueue_function[_g3_norm_inplace_kernel](
                self.hidden.unsafe_ptr(), self.final_norm.unsafe_ptr(),
                Int64(self.d_model), self.eps,
                grid_dim=1, block_dim=_TG,
            )
            self.ctx.enqueue_function[_g3_gemv_kernel](
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
