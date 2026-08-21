"""
residentk.session_cuda — the CUDA-native resident session: the same resident-state design as
`residentk.session._ResidentQwen3` (one `DeviceContext`, one Float64->Float32 narrowing at upload,
an in-place KV cache, compiled-once kernels held for the session's life), plus the batched
m_rows > 1 PREFILL pass the decode-only session never had. Zero Python.

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
benchmark: benchmarks/llm_smoke/qwen3_generate_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Every entry point is private, and every launch is gated — the same two
defences `residentk.session`'s own module docstring documents
-------------------------------------------------------------------------------------------
1. **Private.** Nothing in this file is public, so `apps/runtime/mojo_inventory.py` skips it, it
   never enters the runtime contract, and the generated dispatch never imports it. A launch here
   cannot reach a Linux CI build at all — the worker binary compiles only what `main.mojo`
   reaches.
2. **Compile-time gated.** `CUDA_SESSION_BUILD` below conjuncts the portable-kernel tier
   (`-D ALGENTA_GPU`) with the CUDA backend selector (`-D ALGENTA_CUDA`) — the two-tier split PR
   #765 established. Every function here that issues an `enqueue_function` opens with
   `@parameter if not CUDA_SESSION_BUILD: return <shader_toolchain_absent>`, so with either flag
   unset the launches are removed BEFORE shader codegen runs. The constructor carries no gate (a
   constructor must initialise every field) and is instead protected structurally: the struct is
   constructed ONLY from inside a `@parameter if CUDA_SESSION_BUILD` branch, exactly the
   protection `residentk.session` gives `_ResidentQwen3.__init__`.

What this session is FOR
------------------------
The resident decode path was built portable (`max.gpu.host` only, zero Metal shim), but until this
file landed it had never been compiled for an NVIDIA target, and had no prefill: a prompt was
decoded one position at a time. This session is the first CUDA-native Qwen3 inference in the tree
— cross-compiled with `mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_NN`,
linked against the MAX CUDA runtime (`libMGPRT` + the KGEN/AsyncRT globals), and launched on a
real driver (>= 580) — no CUDA toolkit at build time, no metallib blobs anywhere: every kernel is
compiled by the portable `compile_function` machinery the backend owns.

Prefill: chunked m_rows tiles, one dispatch plan per layer
-----------------------------------------------------------
The prompt is processed in tiles of at most `CUDA_PREFILL_TILE` rows. Per tile, per layer, eight
dispatches (against the decode path's six): rmsnorm-rows, the fused-QKV tiled GEMM (ASSIGN), the
batched RoPE + in-place KV-cache write, the batched causal attention, o_proj (ACCUMULATE into the
residual stream), rmsnorm-rows again, the fused gate/up + SwiGLU tiled GEMM, and down_proj
(ACCUMULATE). The three weightless batched kernels (`_pf_rmsnorm_rows_kernel`, `_pf_ropewrt_
kernel`, `_pf_attn_tiled_kernel_simd`) are dispatched BYTE-UNMODIFIED from `residentk.kernels`;
the four weight-reading roles use this package's new Float32 twins from `residentk.
kernels_prefill_f32`. After the final tile, the tied lm_head + argmax pair from the DECODE path
runs once on the last row — the 151,936-wide logits row is never materialised off-device here
either.

Precision is the same claim `residentk.session` makes, restated: the GPU computes in Float32, the
wire is Float64 narrowed ONCE at upload, and the bar is agreement of the greedy token ids against
the `transformers` reference, not bit-equality of logits.
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
    RESIDENT_MAX_CONTEXT,
    RESIDENT_OK,
    residentk_dispatch_budget,
)
from residentk.kernels import (
    _TG,
    _SUBS,
    _GEMM_BM,
    _GEMM_BN,
    _GEMM_NTHREADS,
    _embed_row_kernel,
    _norm_gemv_kernel,
    _gemv_accum_kernel,
    _norm_gemv2_swiglu_kernel,
    _qk_rope_write_kernel,
    _sdpa_kernel,
    _lmhead_argmax_kernel,
    _argmax_reduce_kernel,
    _pf_rmsnorm_rows_kernel,
    _pf_ropewrt_kernel,
    _pf_attn_tiled_kernel_simd,
    _splitk_merge_kernel_simd,
)
from residentk.kernels_prefill_f32 import (
    _pf_embed_rows_kernel,
    _pf_gemm_assign_kernel,
    _pf_gemm_accum_kernel,
    _pf_gemm_swiglu_kernel,
)
from residentk.kernels_prefill_f32_v2 import (
    _G2_BM,
    _G2_BN,
    _G2_NTHREADS,
    _pf_gemm_assign_kernel_v2,
    _pf_gemm_accum_kernel_v2,
    _pf_gemm_swiglu_kernel_v2,
)
from residentk.kernels_cuda_graph import (
    _embed_row_kernel_g,
    _graph_advance_kernel,
    _qk_rope_write_kernel_g,
    _sdpa_kernel_simd_g,
    _splitk_partial_kernel_simd_g,
)
from residentk.session import (
    RESIDENT_GPU_BUILD,
    _LM_BLOCKS,
    _LayerGpu,
    _StepOut,
    _ceil_div,
    _narrow_into,
    _narrow_transposed_into,
)

comptime CUDA_SESSION_BUILD: Bool = RESIDENT_GPU_BUILD and is_defined["ALGENTA_CUDA"]()
"""Whether this binary was built with `-D ALGENTA_GPU -D ALGENTA_CUDA` — the portable-kernel tier
conjoined with the CUDA backend selector, the two-tier split `metaldispatch.session.MB_GPU_BUILD`
mirrors on the Metal side (with `ALGENTA_METAL`). A Metal build sets `ALGENTA_GPU` but NOT
`ALGENTA_CUDA`, so every launch in this file is removed before shader codegen there — the Metal
lane is untouched by this module's existence."""

comptime CUDA_GRAPH_N_SPLITS: Int = 32
"""The split-K attention fan-out of the graph decode arm: h_q x N_SPLITS = 128 blocks on the
A100's 108 SMs. The extra in-graph dispatch costs nothing (replay amortizes it), so the
Metal-side ~500-key crossover (a launch-overhead argument) does not apply inside the graph."""

comptime CUDA_PREFILL_TILE: Int = 128
"""Largest m_rows tile one prefill chunk processes. 128 keeps every scratch buffer this file
allocates under 1.6 MB at Qwen3-0.6B's dimensions (the QKV tile, the largest, is 128 x 3072
Float32) while amortizing the per-dispatch host cost over 128 positions; the tiled-GEMM kernels'
own `_GEMM_BM = 32` divides it exactly, so no chunk but a prompt's FINAL one ever sees a partial
M-tile."""


@fieldwise_init
struct _CudaResidentQwen3(Movable):
    """Everything a CUDA-native decode+prefill session holds on the device, alive across the whole
    generation. Same residency discipline as `_ResidentQwen3`: every weight as Float32 (converted
    from the Float64 wire ONCE, at upload), the RoPE tables, and the KV cache at `max_ctx`
    positions, all in the same struct as their context so no buffer can outlive it.

    `Movable` is mandatory for the same reason that struct's own docstring gives.
    """

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

    var layers: List[_LayerGpu]
    var embed: DeviceBuffer[DType.float32]
    var final_norm: DeviceBuffer[DType.float32]
    var cos_t: DeviceBuffer[DType.float32]
    var sin_t: DeviceBuffer[DType.float32]

    # decode scratch — one token's working set, identical to `_ResidentQwen3`'s
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

    # decode-graph arm — the captured per-token dispatch sequence and its dynamic-scalar feed.
    # `step_state` holds [token_id, pos, n_keys] on the device; `host_state` is the pinned twin
    # the host rewrites before every replay. The graph itself is built LAZILY on the first
    # `step_graph` call (a constructor must initialise every field; `Optional` is the empty
    # initial, and capture needs every resident buffer already allocated — true only at the end
    # of `__init__`).
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
        """Open the context and allocate every resident + scratch buffer. ONCE.

        Called only from inside a `@parameter if CUDA_SESSION_BUILD` branch — see the module
        docstring for why a constructor cannot carry the gate itself. The caller must have
        validated the shape with `residentk_dims_check` first, exactly as `_ResidentQwen3`'s own
        constructor requires.
        """
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

        self.layers = List[_LayerGpu]()
        for _ in range(n_layers):
            self.layers.append(
                _LayerGpu(
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
        """The DECODE budget — `n_layers * 6 + 3`, the same arithmetic `_ResidentQwen3` reports.
        Prefill's per-chunk budget is `1 + n_layers * 8` plus two more on the final chunk (the
        lm_head + argmax pair), and is reported by `prefill` itself."""
        return residentk_dispatch_budget(self.n_layers)

    def upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        """The tied embedding/lm_head table, the final norm gain, and the RoPE tables — the same
        one-time narrowing `_ResidentQwen3.upload_globals` performs (the helpers are shared, not
        copied)."""
        var n_pairs = self.d_head // 2
        if n_pos > self.max_ctx:
            return RESIDENT_ERR_CONTEXT_FULL
        var s = _narrow_into(self.embed, embed, self.vocab * self.d_model, 0)
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
        """One layer's eleven checkpoint tensors, narrowed and packed into four device matrices —
        the same `[out, in]` transpose-once packing `_ResidentQwen3.upload_layer` performs, shared
        helper-for-helper: the tiled prefill GEMMs read `w` in exactly the `[n, k]` layout that
        packing produces."""
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
        """Drain every upload before the first dispatch. One synchronize for the whole load."""
        self.ctx.synchronize()
        return RESIDENT_OK

    def prefill(mut self, prompt_ids: List[Int]) raises -> _StepOut:
        """The whole prompt: chunked m_rows tiles through every layer, then ONE lm_head + argmax
        on the final position. Returns the greedy FIRST generated token — the same `_StepOut`
        contract `step` uses, so a caller chains `prefill(...)` into `step(...)` exactly the way
        the Metal prefill arm's callers do.

        `pos` bookkeeping is the caller's: every following `step` starts at
        `pos = len(prompt_ids)`.
        """

        @parameter
        if not CUDA_SESSION_BUILD:
            # Removed before shader codegen; this is what a non-CUDA build compiles and runs.
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

                # ── this chunk's token ids, uploaded once ──
                with self.pf_tokens.map_to_host() as h:
                    for i in range(m):
                        h[i] = Int32(prompt_ids[pos + i])
                self.ctx.synchronize()

                # ── the embedding rows, gathered on-device from the resident table ──
                self.ctx.enqueue_function[_pf_embed_rows_kernel](
                    self.pf_hidden.unsafe_ptr(), self.embed.unsafe_ptr(),
                    self.pf_tokens.unsafe_ptr(),
                    Int64(self.d_model), Int64(m),
                    grid_dim=_ceil_div(self.d_model, _TG) * m, block_dim=_TG,
                )
                issued += 1

                for layer in range(self.n_layers):
                    ref lw = self.layers[layer]

                    # 1 ── rmsnorm(input_layernorm) over every row
                    self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        self.pf_xn.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                        lw.ln1.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # 2 ── fused Q/K/V projection, one tiled GEMM (ASSIGN) — the v2
                    # register-blocked / double-buffered kernel (kernels_prefill_f32_v2)
                    self.ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
                        self.pf_qkv.unsafe_ptr(), self.pf_xn.unsafe_ptr(),
                        lw.w_qkv.unsafe_ptr(),
                        Int64(m), Int64(self.d_model), Int64((self.h_q + 2 * self.h_kv) * self.d_head),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div((self.h_q + 2 * self.h_kv) * self.d_head, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                    # 3 ── q_norm + k_norm + RoPE + the in-place KV-cache write, every row
                    self.ctx.enqueue_function[_pf_ropewrt_kernel](
                        self.pf_q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                        self.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                        self.cos_t.unsafe_ptr(), self.sin_t.unsafe_ptr(),
                        Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                        self.eps, Int64(m),
                        Int64(1),  # qk_norm: Qwen3-family only, per-head QK-norm always on
                        grid_dim=(self.h_q + self.h_kv) * m, block_dim=self.d_head,
                    )
                    # 4 ── causal attention, one threadgroup per (row, query head)
                    self.ctx.enqueue_function[_pf_attn_tiled_kernel_simd](
                        self.pf_attn.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                        lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                        Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                        self.scale, Int64(m),
                        grid_dim=self.h_q * m, block_dim=self.d_head,
                    )
                    # 5 ── o_proj ACCUMULATED straight into the residual stream (v2 kernel)
                    self.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                        self.pf_hidden.unsafe_ptr(), self.pf_attn.unsafe_ptr(),
                        lw.w_o.unsafe_ptr(),
                        Int64(m), Int64(n_q), Int64(self.d_model),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.d_model, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                    # 6 ── rmsnorm(post_attention_layernorm) over every row
                    self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        self.pf_xn.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                        lw.ln2.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # 7 ── gate/up + SwiGLU, one tiled GEMM pair (v2 kernel)
                    self.ctx.enqueue_function[_pf_gemm_swiglu_kernel_v2](
                        self.pf_act.unsafe_ptr(), self.pf_xn.unsafe_ptr(),
                        lw.w_gu.unsafe_ptr(),
                        Int64(m), Int64(self.d_model), Int64(self.d_ff),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.d_ff, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                    # 8 ── down_proj ACCUMULATED straight into the residual stream (v2 kernel)
                    self.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                        self.pf_hidden.unsafe_ptr(), self.pf_act.unsafe_ptr(),
                        lw.w_down.unsafe_ptr(),
                        Int64(m), Int64(self.d_ff), Int64(self.d_model),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.d_model, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                    issued += 8
                pos += m

            # ── final rmsnorm + lm_head + per-threadgroup argmax on the LAST row only ──
            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
            self.ctx.enqueue_function[_lmhead_argmax_kernel](
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

            # ── 8 bytes back, not 608 KB ──
            self.ctx.enqueue_copy(self.host_val, self.out_val)
            self.ctx.enqueue_copy(self.host_idx, self.out_idx)
            self.ctx.synchronize()
            var tok = Int(self.host_idx.unsafe_ptr()[0])
            var lg = Float64(self.host_val.unsafe_ptr()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(tok, lg, issued, RESIDENT_OK)

    def step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """ONE decode token, identical dispatch plan to `_ResidentQwen3.step` — six fused
        dispatches per layer plus the fixed three, per-dispatch enqueue, no batching. See that
        function's docstring for the plan; nothing about the SHAPE of the computation differs
        here, only the launch spelling (Mojo 1.0.0's checked parameter form)."""

        @parameter
        if not CUDA_SESSION_BUILD:
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

            # ── the embedding row, gathered on-device from the resident table ──
            self.ctx.enqueue_function[_embed_row_kernel](
                self.hidden.unsafe_ptr(), self.embed.unsafe_ptr(),
                Int64(token_id), Int64(self.d_model),
                grid_dim=_ceil_div(self.d_model, _TG), block_dim=_TG,
            )
            issued += 1

            for layer in range(self.n_layers):
                ref lw = self.layers[layer]

                # 1 ── rmsnorm(input_layernorm) + fused Q/K/V projection
                self.ctx.enqueue_function[_norm_gemv_kernel](
                    self.qkv.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln1.unsafe_ptr(),
                    lw.w_qkv.unsafe_ptr(), Int64(self.d_model), Int64(n_qkv), self.eps,
                    grid_dim=_ceil_div(n_qkv, _SUBS), block_dim=_TG,
                )
                # 2 ── q_norm + k_norm + RoPE + the in-place KV-cache slot write
                self.ctx.enqueue_function[_qk_rope_write_kernel](
                    self.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    self.qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                    self.cos_t.unsafe_ptr(), self.sin_t.unsafe_ptr(),
                    Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head), self.eps,
                    Int64(1),  # qk_norm: Qwen3-family only, per-head QK-norm always on
                    grid_dim=self.h_q + self.h_kv, block_dim=self.d_head,
                )
                # 3 ── attention over every cached key, online softmax
                self.ctx.enqueue_function[_sdpa_kernel](
                    self.attn_out.unsafe_ptr(), self.q_rot.unsafe_ptr(),
                    lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    Int64(n_keys), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                    self.scale,
                    grid_dim=self.h_q, block_dim=self.d_head,
                )
                # 4 ── o_proj accumulated straight into the residual stream
                self.ctx.enqueue_function[_gemv_accum_kernel](
                    self.hidden.unsafe_ptr(), self.attn_out.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                    Int64(n_q), Int64(self.d_model),
                    grid_dim=_ceil_div(self.d_model, _SUBS), block_dim=_TG,
                )
                # 5 ── rmsnorm(post_attention_layernorm) + gate/up + SwiGLU
                self.ctx.enqueue_function[_norm_gemv2_swiglu_kernel](
                    self.act.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln2.unsafe_ptr(),
                    lw.w_gu.unsafe_ptr(), Int64(self.d_model), Int64(self.d_ff), self.eps,
                    grid_dim=_ceil_div(self.d_ff, _SUBS), block_dim=_TG,
                )
                # 6 ── down_proj accumulated straight into the residual stream
                self.ctx.enqueue_function[_gemv_accum_kernel](
                    self.hidden.unsafe_ptr(), self.act.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                    Int64(self.d_ff), Int64(self.d_model),
                    grid_dim=_ceil_div(self.d_model, _SUBS), block_dim=_TG,
                )
                issued += 6

            # ── final rmsnorm + lm_head + per-threadgroup argmax, then the reduce ──
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

            # ── 8 bytes back, not 608 KB ──
            self.ctx.enqueue_copy(self.host_val, self.out_val)
            self.ctx.enqueue_copy(self.host_idx, self.out_idx)
            self.ctx.synchronize()
            var tok = Int(self.host_idx.unsafe_ptr()[0])
            var lg = Float64(self.host_val.unsafe_ptr()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(tok, lg, issued, RESIDENT_OK)

    def _build_decode_graph(mut self) raises:
        """Capture the whole per-token decode dispatch sequence into ONE `DeviceGraph`.

        The recording context (`builder.recording_context()`) records the ordinary
        `enqueue_function` / `enqueue_copy` calls as graph nodes in enqueue order instead of
        executing them — so this method is literally `step`'s dispatch plan, replayed against
        the recording context, with the three position-dependent launches reading their dynamic
        scalars from the resident `step_state` buffer through the `_g` kernel twins
        (`residentk.kernels_cuda_graph`). Every other launch's arguments are fixed addresses and
        constants, valid for the session's life, so ONE captured graph serves every decode step:
        replay feeds it the per-token scalars by copying `host_state -> step_state` (the first
        recorded node), and reads the argmax result back through the two recorded D2H copies.

        Called once, lazily, from `step_graph` — every resident buffer must already exist, and
        the constructor cannot capture a graph of buffers it has not finished allocating.

        POINTER HOISTING DISCIPLINE (paid in three build failures, recorded): the build callback
        is an `{imm}` closure, and an immutable borrow of `self` yields IMMUTABLE branded
        pointers — the kernels' `_FP`/`_IP` parameters are MUTABLE MutAnyOrigin pointers, and
        Mojo 1.0.0 has no implicit branded->MutAnyOrigin conversion at ordinary initialization,
        and an `{imm}` capture cannot take mutable pointers from `self` at all.
        The proven round trip: take each pointer in the method scope (where `self` is mut),
        keep its address as a plain Int (`Int(ptr)`), and rebuild a mutable MutAnyOrigin
        pointer from the address inside the capture (`UnsafePointer[...](unsafe_from_address=
        ...)`, the spelling `metaldispatch.session` uses). Session buffers are resident for the
        session's life, so the addresses are stable for every replay.
        """
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
            # ── rebuild the mutable MutAnyOrigin pointers from the hoisted addresses ──
            var hidden_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=hidden_a)
            var qkv_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=qkv_a)
            var q_rot_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=q_rot_a)
            var attn_out_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=attn_out_a)
            var act_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=act_a)
            var blk_val_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=blk_val_a)
            var blk_idx_p = UnsafePointer[Int32, origin=MutAnyOrigin](unsafe_from_address=blk_idx_a)
            var out_val_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=out_val_a)
            var out_idx_p = UnsafePointer[Int32, origin=MutAnyOrigin](unsafe_from_address=out_idx_a)
            var embed_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=embed_a)
            var final_norm_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=final_norm_a)
            var cos_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cos_a)
            var sin_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=sin_a)
            var state_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=state_a)

            var rec = builder.recording_context()

            # NOTE: the host_state -> step_state feed is DELIBERATELY NOT recorded here.
            # Run-verified on the A100 (oracle FAIL, bit-identical logits on every replay):
            # a host->device copy captured into the graph reads a capture-time snapshot of
            # the host buffer, never the live contents — every replay saw stale state. The
            # feed therefore happens as ONE eager enqueue per token in `step_graph` before
            # the replay (same stream, ordered before the graph's kernels). The device->host
            # argmax readback at the end IS captured: it lands live (run-verified).

            # ── the embedding row, gathered from the resident table ──
            rec.enqueue_function[_embed_row_kernel_g](
                hidden_p, embed_p, state_p, d_model_i,
                grid_dim=_ceil_div(Int(d_model_i), _TG), block_dim=_TG,
            )

            for layer in range(n_layers_c):
                var ln1_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=ln1s[layer])
                var ln2_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=ln2s[layer])
                var qn_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=qns[layer])
                var kn_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=kns[layer])
                var wqkv_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=w_qkvs[layer])
                var wo_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=w_os[layer])
                var wgu_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=w_gus[layer])
                var wd_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=w_downs[layer])
                var ck_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cks[layer])
                var cv_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cvs[layer])
                # 1 ── rmsnorm(input_layernorm) + fused Q/K/V projection
                rec.enqueue_function[_norm_gemv_kernel](
                    qkv_p, hidden_p, ln1_p,
                    wqkv_p, d_model_i, n_qkv_i, eps_c,
                    grid_dim=_ceil_div(Int(n_qkv_i), _SUBS), block_dim=_TG,
                )
                # 2 ── q_norm + k_norm + RoPE + the in-place KV-cache slot write (pos: state[1])
                rec.enqueue_function[_qk_rope_write_kernel_g](
                    q_rot_p, ck_p, cv_p,
                    qkv_p, qn_p, kn_p,
                    cos_p, sin_p,
                    state_p, h_q_i, h_kv_i, d_head_i, eps_c,
                    Int64(1),  # qk_norm: Qwen3-family only, per-head QK-norm always on
                    grid_dim=Int(h_q_i) + Int(h_kv_i), block_dim=Int(d_head_i),
                )
                # 3 ── attention over every cached key (n_keys: state[2]) — the SPLIT-K
                # flash-decoding pair (partial + merge): the simd-shuffle reduction twin split
                # across CUDA_GRAPH_N_SPLITS blocks per head (h_q x splits = 128 blocks on the
                # A100's 108 SMs vs 16 for the unsplit kernel), warp-shuffle reduction body
                # gated by sdpa_simd_nvidia_probe.mojo (0/2100 mismatches vs the barrier-tree
                # reference on this toolchain/GPU). The merge is the residentk engine kernel
                # byte-unmodified — no dynamic arguments, captured directly.
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
                # 4 ── o_proj accumulated straight into the residual stream
                rec.enqueue_function[_gemv_accum_kernel](
                    hidden_p, attn_out_p, wo_p,
                    n_q_i, d_model_i,
                    grid_dim=_ceil_div(Int(d_model_i), _SUBS), block_dim=_TG,
                )
                # 5 ── rmsnorm(post_attention_layernorm) + gate/up + SwiGLU
                rec.enqueue_function[_norm_gemv2_swiglu_kernel](
                    act_p, hidden_p, ln2_p,
                    wgu_p, d_model_i, d_ff_i, eps_c,
                    grid_dim=_ceil_div(Int(d_ff_i), _SUBS), block_dim=_TG,
                )
                # 6 ── down_proj accumulated straight into the residual stream
                rec.enqueue_function[_gemv_accum_kernel](
                    hidden_p, act_p, wd_p,
                    d_ff_i, d_model_i,
                    grid_dim=_ceil_div(Int(d_model_i), _SUBS), block_dim=_TG,
                )

            # ── final rmsnorm + lm_head + per-threadgroup argmax, then the reduce ──
            rec.enqueue_function[_lmhead_argmax_kernel](
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
            # ── the device-side generation chain: log the token, feed it forward, advance
            #    pos/n_keys — so N back-to-back replays run a whole generation with zero
            #    per-token host traffic (the host seeds once and synchronizes once) ──
            var tlog_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=tlog_a)
            rec.enqueue_function[_graph_advance_kernel](
                state_p, out_idx_p, tlog_p,
                grid_dim=1, block_dim=1,
            )
            # NO memcpy nodes are recorded — neither direction. Run-verified on the A100
            # (benchmarks/llm_smoke/nvidia_race/state_probe.mojo, PART1-3): captured copies
            # route through graph-owned staging and never touch the caller's buffers at
            # replay, in either direction; eager copies around the replay do. `step_graph`
            # therefore feeds the state and reads the argmax back eagerly.

        self.decode_graph = DeviceGraph.create(self.ctx, build)

    def step_graph(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """ONE decode token through the captured device graph — the same computation as `step`,
        one replay instead of 171 per-dispatch enqueues. The per-token scalars (token_id, pos,
        n_keys) are written into the pinned `host_state`; the graph's first recorded node copies
        them to the device `step_state` buffer the `_g` kernels read. Same `_StepOut` contract
        as `step`, including the dispatch budget report (the replayed plan IS that budget)."""

        @parameter
        if not CUDA_SESSION_BUILD:
            return _StepOut(-1, 0.0, 0, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)

            if not self.decode_graph_built:
                self._build_decode_graph()
                self.decode_graph_built = True

            # HostBuffer is host-visible already — write the three scalars through its
            # pointer directly (no map_to_host; that is the DeviceBuffer API).
            var state_h = self.host_state.unsafe_ptr()
            state_h[0] = Int64(token_id)
            state_h[1] = Int64(pos)
            state_h[2] = Int64(pos + 1)

            # The feed: ONE eager H2D copy on the context stream, ordered before the replay.
            # A recorded copy would read a capture-time snapshot instead (see
            # `_build_decode_graph`'s note); one enqueue is noise next to the 171 deleted.
            self.ctx.enqueue_copy(self.step_state, self.host_state)

            self.decode_graph.value().replay()

            # The 8-byte readback, eagerly (a recorded D2H copy would land in graph-owned
            # staging, never in these host buffers — state_probe.mojo PART2/3 evidence).
            self.ctx.enqueue_copy(self.host_val, self.out_val)
            self.ctx.enqueue_copy(self.host_idx, self.out_idx)
            self.ctx.synchronize()

            var tok = Int(self.host_idx.unsafe_ptr()[0])
            var lg = Float64(self.host_val.unsafe_ptr()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(
                tok, lg, residentk_dispatch_budget(self.n_layers), RESIDENT_OK
            )

    def seed_and_run_graph(
        mut self, first_token: Int, start_pos: Int, n_steps: Int,
    ) raises -> Int:
        """Run `n_steps` decode steps as `n_steps` back-to-back replays of ONE captured graph,
        with ZERO per-token host traffic — the device-side chain (`_graph_advance_kernel`,
        captured as the graph's last node) logs each token to `token_log`, feeds it as the
        next embed input, and advances pos/n_keys; replays run in stream order, so replay k
        consumes exactly what replay k-1 advanced. The host seeds `step_state` once, enqueues
        every replay, synchronizes once, and pulls the whole token log back eagerly.

        Returns a RESIDENT_* status. Tokens are read afterwards with `graph_token(pos)` —
        the log is indexed by ABSOLUTE position, so the token generated at position
        `start_pos + i` is `graph_token(start_pos + i)`. The caller owns `pos` bookkeeping
        exactly as with `step`/`prefill`: the next position after this call is
        `start_pos + n_steps`.
        """

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

            # Seed the chain once: the prefill's first token + the position it occupies.
            var state_h = self.host_state.unsafe_ptr()
            state_h[0] = Int64(first_token)
            state_h[1] = Int64(start_pos)
            state_h[2] = Int64(start_pos + 1)
            self.ctx.enqueue_copy(self.step_state, self.host_state)

            for _ in range(n_steps):
                self.decode_graph.value().replay()

            # One synchronize for the whole generation, then the log readback (eager — a
            # recorded copy would land in graph-owned staging, never this host buffer).
            self.ctx.synchronize()
            self.ctx.enqueue_copy(self.host_token_log, self.token_log)
            self.ctx.synchronize()
            return RESIDENT_OK

    def graph_token(self, pos: Int) raises -> Int:
        """The token generated at ABSOLUTE position `pos` by the last `seed_and_run_graph`
        call, read from the host-side token log."""
        return Int(self.host_token_log.unsafe_ptr()[pos])
