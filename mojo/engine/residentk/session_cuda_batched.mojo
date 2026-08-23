"""residentk.session_cuda_batched — W1 of the campaign gap inventory: CONTINUOUS-BATCHING
(B-sequence) DECODE on the CUDA lane, per-dispatch arm. Additive — `residentk.session_cuda`,
`residentk.kernels` and the Metal batched modules are byte-unmodified. Zero Python.

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

NOT a contract module. Every entry point is private, and every launch is gated — the same two
defences `residentk.session_cuda`'s module docstring documents: nothing here is public, so it
never enters the runtime contract; and every `enqueue_function` caller opens with
`@parameter if not CUDA_SESSION_BUILD: return <shader_toolchain_absent>`, so with either
`-D ALGENTA_GPU` or `-D ALGENTA_CUDA` unset the launches are removed BEFORE shader codegen runs.
The constructor carries no gate (a constructor must initialise every field) and is protected
structurally: the struct is constructed ONLY from inside a `@parameter if CUDA_SESSION_BUILD`
branch, exactly the protection `_CudaResidentQwen3.__init__` has.

WHAT THIS SESSION IS FOR
------------------------
Enterprises benchmark aggregate tok/s AT CONCURRENCY; the Metal batched stack beats llama.cpp
2.1-2.6x concurrent because B sequences step together: every projection becomes the PREFILL
tiled-GEMM shape at m_rows=B (weights swept ONCE for all B tokens), attention becomes per-
sequence flash-decoding over per-sequence KV slots. This session ports that capability to the
CUDA lane, per-dispatch first (the captured-graph arm is W2).

PER-STEP DISPATCH PLAN (mirrors `metaldispatch.session_prefill._ensure_decode_batched_ready`
role-for-role — the substitution table, per role):

  Metal batched role                        CUDA kernel here
  ─ embed (B rows)                          residentk.kernels_prefill_f32._pf_embed_rows_kernel (M=B)
  ─ rmsnorm -> xn                           residentk.kernels._pf_rmsnorm_rows_kernel (M=B)
  ─ qkv GEMM (M=B, ASSIGN)                  residentk.kernels_prefill_f32_v2._pf_gemm_assign_kernel_v2
  ─ batched kvprod (QK-norm+RoPE+pack)      attention_forge.kvprod_batched_f32_cuda (F32 twin — CUDA
                                            KV is flat f32, and only f32 loads stream at HBM speed)
  ─ batched split-K PARTIAL                 attention_forge.native_kv_decode_attn_splitk_batched_f32
                                            (F32 twin of the f16-native blob; ragged nkeys[b], kv_off)
  ─ batched split-K MERGE                   attention_forge..._f32 merge twin (math byte-for-byte
                                            residentk.kernels._batched_splitk_merge_kernel_simd's own)
  ─ o_proj GEMM (M=B, ACCUM residual)       residentk.kernels_prefill_f32_v2._pf_gemm_accum_kernel_v2
  ─ rmsnorm2 -> xn                          _pf_rmsnorm_rows_kernel (M=B)
  ─ gate/up + SwiGLU GEMM (M=B)             residentk.kernels_prefill_f32_v2._pf_gemm_swiglu_kernel_v2
  ─ down_proj GEMM (M=B, ACCUM residual)    _pf_gemm_accum_kernel_v2
  ─ final rmsnorm (B rows)                  _pf_rmsnorm_rows_kernel (M=B, gamma=final_norm)
  ─ batched lm_head + per-slice argmax      residentk.kernels_batched_cuda._batched_lmhead_argmax_kernel_f32
                                            (NEW f32 twin — kernels.mojo's batched lm_head is i8-coupled)
  ─ B-row argmax reduce                     residentk.kernels._batched_argmax_reduce_kernel_simd REUSED
                                            byte-unmodified (weight-agnostic: reads only blk pairs)

  = 1 + n_layers * 9 + 3 dispatches per B-token step.

Every substitution follows the campaign's proven CUDA physics: weights and KV stay Float32 (f16
loads scalarize at 4-7% of peak on this backend), so the Metal f16-native batched kvprod and
attention blobs get F32 twins in `attention_forge` (additive modules), and the KV layout is the
CUDA lane's flat `[max_ctx, h_kv, d_head]` per sequence slot (no block interleave).

PER-SEQUENCE KV (the Metal batched convention, ported): `_CUDA_BATCH_DECODE_MAX_SEQS` independent
sequences' caches per layer, concatenated into ONE oversized K buffer and ONE V buffer per layer,
sequence `b` selected by the flat element offset `b * kv_stride_elems`
(`kv_stride_elems = max_ctx * h_kv * d_head`) — the uniform-stride indirection the f32 batched
kernels' `kv_stride` argument was built for. Prefill ingests each prompt INTO its own slot by
passing the slot-offset cache pointers to the unchanged prefill kernels (pointer arithmetic at
enqueue — no kernel change).

THE GRAPH ARM IS OUT (W2): every step is per-dispatch enqueues on the context stream, exactly
the way `session_cuda.step` launches — no capture, no replay.
"""

from max.gpu.host import (
    DeviceBuffer,
    DeviceContext,
    HostBuffer,
)
from residentk.contract import (
    RESIDENT_ERR_CONTEXT_FULL,
    RESIDENT_ERR_LAUNCH_FAILED,
    RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT,
    RESIDENT_ERR_UPLOAD_LENGTH,
    RESIDENT_OK,
)
from residentk.kernels import (
    _TG,
    _SUBS,
    _pf_rmsnorm_rows_kernel,
    _pf_ropewrt_kernel,
    _pf_attn_tiled_kernel_simd,
    _lmhead_argmax_kernel,
    _argmax_reduce_kernel,
    _batched_argmax_reduce_kernel_simd,
)
from residentk.kernels_prefill_f32 import (
    _pf_embed_rows_kernel,
)
from residentk.kernels_prefill_f32_v2 import (
    _G2_BM,
    _G2_BN,
    _G2_NTHREADS,
    _pf_gemm_assign_kernel_v2,
    _pf_gemm_accum_kernel_v2,
    _pf_gemm_swiglu_kernel_v2,
)
from residentk.kernels_batched_cuda import (
    _batched_lmhead_argmax_kernel_f32,
)
from kvprod_batched_f32_cuda import (
    _native_kv_producer_batched_f32_kernel,
)
from native_kv_decode_attn_splitk_batched_f32 import (
    _native_kv_decode_splitk_partial_batched_f32_kernel,
    _native_kv_decode_splitk_merge_batched_f32_kernel,
)
from residentk.session import (
    _LM_BLOCKS,
    _LayerGpu,
    _StepOut,
    _ceil_div,
    _narrow_into,
    _narrow_transposed_into,
)
from residentk.session_cuda import (
    CUDA_PREFILL_TILE,
    CUDA_SESSION_BUILD,
)

comptime _CUDA_BATCH_DECODE_MAX_SEQS: Int = 32
"""The FIXED maximum number of sequences the batched decode path provisions per-sequence KV
slots for — the same cap the Metal batched stack's `_BATCH_DECODE_MAX_SEQS` (32) uses, so the
two lanes' concurrency ceilings never drift. Each of the B (<= this) sequences gets its OWN
`max_ctx * h_kv * d_head`-element K cache and V cache per layer, laid out contiguously in ONE
oversized buffer per layer per K/V, sequence `b` selected by the flat element offset
`b * kv_stride_elems`. The actual in-flight batch may be any B <= this; the weight-sweep win
grows with B."""

comptime CUDA_BATCH_N_SPLITS: Int = 16
"""The split-K attention fan-out of the batched decode arm — the same constant the Metal batched
stack's `_NATIVE_DECODE_N_SPLITS` (16) uses. At B sequences the partial grid is
`B * h_q * 16` blocks: 256 blocks at B=1 on Qwen3-0.6B (h_q=16), already more than the A100's
108 SMs, so the single-stream CUDA graph arm's 32 splits (an occupancy argument at B=1 inside a
graph) is not needed here — 16 fills the GPU at every B >= 1 this session runs."""


@fieldwise_init
struct _CudaResidentQwen3Batched(Movable):
    """Everything a CUDA-native BATCHED decode+prefill session holds on the device, alive across
    the whole run. Same residency discipline as `_CudaResidentQwen3`: every weight as Float32
    (converted from the Float64 wire ONCE, at upload), the RoPE tables, and the KV cache, all in
    the same struct as their context so no buffer can outlive it.

    The layer struct is `residentk.session._LayerGpu` REUSED: its `ck`/`cv` buffers are simply
    allocated at `_CUDA_BATCH_DECODE_MAX_SEQS x max_ctx` positions instead of `max_ctx` — one
    flat concatenation of per-sequence slots, sequence `b` at `b * kv_stride_elems`. The
    single-stream kernels never see these buffers; only the batched plan's kernels (and the
    slot-offset prefill pointers) index them.

    `Movable` is mandatory for the same reason `_CudaResidentQwen3`'s own docstring gives.
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
    var kv_stride_elems: Int
    var qk_norm: Int
    var has_lm_head: Int
    var skip_f32_projections: Int

    var layers: List[_LayerGpu]
    var embed: DeviceBuffer[DType.float32]
    var lm_head: DeviceBuffer[DType.float32]
    var final_norm: DeviceBuffer[DType.float32]
    var cos_t: DeviceBuffer[DType.float32]
    var sin_t: DeviceBuffer[DType.float32]

    # batched decode scratch — B_MAX rows' working set
    var b_tokens: DeviceBuffer[DType.int32]
    var b_poss: DeviceBuffer[DType.int64]
    var b_nkeys: DeviceBuffer[DType.int64]
    var b_hidden: DeviceBuffer[DType.float32]
    var b_xn: DeviceBuffer[DType.float32]
    var b_qkv: DeviceBuffer[DType.float32]
    var b_q_rot: DeviceBuffer[DType.float32]
    var b_attn: DeviceBuffer[DType.float32]
    var b_act: DeviceBuffer[DType.float32]
    var b_sk_m: DeviceBuffer[DType.float32]
    var b_sk_l: DeviceBuffer[DType.float32]
    var b_sk_o: DeviceBuffer[DType.float32]
    var b_blk_val: DeviceBuffer[DType.float32]
    var b_blk_idx: DeviceBuffer[DType.int32]
    var b_out_val: DeviceBuffer[DType.float32]
    var b_out_idx: DeviceBuffer[DType.int32]
    var host_out_val: HostBuffer[DType.float32]
    var host_out_idx: HostBuffer[DType.int32]

    # prefill scratch — one CUDA_PREFILL_TILE-row working set (shared across sequences: prefills
    # run one sequence at a time, in stream order)
    var pf_tokens: DeviceBuffer[DType.int32]
    var pf_hidden: DeviceBuffer[DType.float32]
    var pf_xn: DeviceBuffer[DType.float32]
    var pf_qkv: DeviceBuffer[DType.float32]
    var pf_q_rot: DeviceBuffer[DType.float32]
    var pf_attn: DeviceBuffer[DType.float32]
    var pf_act: DeviceBuffer[DType.float32]
    # single-row tail buffers for the per-sequence prefill's lm_head + argmax
    var pf_blk_val: DeviceBuffer[DType.float32]
    var pf_blk_idx: DeviceBuffer[DType.int32]
    var pf_out_val: DeviceBuffer[DType.float32]
    var pf_out_idx: DeviceBuffer[DType.int32]
    var host_pf_val: HostBuffer[DType.float32]
    var host_pf_idx: HostBuffer[DType.int32]

    # host-side generation log for seed_and_run_batched: [seq][step] -> token
    var token_log: List[List[Int]]

    def __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
        qk_norm: Int = 1, has_lm_head: Int = 0, skip_f32_projections: Int = 0,
    ) raises:
        """Open the context and allocate every resident + scratch buffer. ONCE.

        Called only from inside a `@parameter if CUDA_SESSION_BUILD` branch — see the module
        docstring for why a constructor cannot carry the gate itself. The caller must have
        validated the shape with `residentk_dims_check` first, exactly as `_CudaResidentQwen3`'s
        own constructor requires. The 7B-lane flags (`qk_norm`, `has_lm_head`,
        `skip_f32_projections`) mirror `_CudaResidentQwen3.__init__`'s; with
        `skip_f32_projections=1` the four f32 projection matrices per layer become 1-element
        placeholders (a 7B's dual residency exceeds a 40 GB device) and the driver prefills
        through the JIT-dequant seam."""
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
        self.kv_stride_elems = max_ctx * h_kv * d_head
        self.qk_norm = qk_norm
        self.has_lm_head = has_lm_head
        self.skip_f32_projections = skip_f32_projections

        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2
        var B = _CUDA_BATCH_DECODE_MAX_SEQS
        var kv_elems = B * max_ctx * h_kv * d_head

        # 7B memory fit: the f32 projections are the dominant resident; a p3-composed serve
        # session that prefills through the JIT-dequant seam allocates 1-element placeholders.
        var w_qkv_elems = n_qkv * d_model
        var w_o_elems = d_model * h_q * d_head
        var w_gu_elems = 2 * d_ff * d_model
        var w_down_elems = d_model * d_ff
        if skip_f32_projections == 1:
            w_qkv_elems = 1
            w_o_elems = 1
            w_gu_elems = 1
            w_down_elems = 1

        self.layers = List[_LayerGpu]()
        for _ in range(n_layers):
            self.layers.append(
                _LayerGpu(
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](w_qkv_elems),
                    self.ctx.enqueue_create_buffer[DType.float32](w_o_elems),
                    self.ctx.enqueue_create_buffer[DType.float32](w_gu_elems),
                    self.ctx.enqueue_create_buffer[DType.float32](w_down_elems),
                    self.ctx.enqueue_create_buffer[DType.float32](kv_elems),
                    self.ctx.enqueue_create_buffer[DType.float32](kv_elems),
                )
            )

        self.embed = self.ctx.enqueue_create_buffer[DType.float32](vocab * d_model)
        var lm_elems = vocab * d_model
        if has_lm_head != 1:
            lm_elems = 1
        self.lm_head = self.ctx.enqueue_create_buffer[DType.float32](lm_elems)
        self.final_norm = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.cos_t = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
        self.sin_t = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)

        self.b_tokens = self.ctx.enqueue_create_buffer[DType.int32](B)
        self.b_poss = self.ctx.enqueue_create_buffer[DType.int64](B)
        self.b_nkeys = self.ctx.enqueue_create_buffer[DType.int64](B)
        self.b_hidden = self.ctx.enqueue_create_buffer[DType.float32](B * d_model)
        self.b_xn = self.ctx.enqueue_create_buffer[DType.float32](B * d_model)
        self.b_qkv = self.ctx.enqueue_create_buffer[DType.float32](B * n_qkv)
        self.b_q_rot = self.ctx.enqueue_create_buffer[DType.float32](B * h_q * d_head)
        self.b_attn = self.ctx.enqueue_create_buffer[DType.float32](B * h_q * d_head)
        self.b_act = self.ctx.enqueue_create_buffer[DType.float32](B * d_ff)
        self.b_sk_m = self.ctx.enqueue_create_buffer[DType.float32](
            B * h_q * CUDA_BATCH_N_SPLITS
        )
        self.b_sk_l = self.ctx.enqueue_create_buffer[DType.float32](
            B * h_q * CUDA_BATCH_N_SPLITS
        )
        self.b_sk_o = self.ctx.enqueue_create_buffer[DType.float32](
            B * h_q * CUDA_BATCH_N_SPLITS * d_head
        )
        self.b_blk_val = self.ctx.enqueue_create_buffer[DType.float32](B * _LM_BLOCKS)
        self.b_blk_idx = self.ctx.enqueue_create_buffer[DType.int32](B * _LM_BLOCKS)
        self.b_out_val = self.ctx.enqueue_create_buffer[DType.float32](B)
        self.b_out_idx = self.ctx.enqueue_create_buffer[DType.int32](B)
        self.host_out_val = self.ctx.enqueue_create_host_buffer[DType.float32](B)
        self.host_out_idx = self.ctx.enqueue_create_host_buffer[DType.int32](B)

        var t = CUDA_PREFILL_TILE
        self.pf_tokens = self.ctx.enqueue_create_buffer[DType.int32](t)
        self.pf_hidden = self.ctx.enqueue_create_buffer[DType.float32](t * d_model)
        self.pf_xn = self.ctx.enqueue_create_buffer[DType.float32](t * d_model)
        self.pf_qkv = self.ctx.enqueue_create_buffer[DType.float32](t * n_qkv)
        self.pf_q_rot = self.ctx.enqueue_create_buffer[DType.float32](t * h_q * d_head)
        self.pf_attn = self.ctx.enqueue_create_buffer[DType.float32](t * h_q * d_head)
        self.pf_act = self.ctx.enqueue_create_buffer[DType.float32](t * d_ff)
        self.pf_blk_val = self.ctx.enqueue_create_buffer[DType.float32](_LM_BLOCKS)
        self.pf_blk_idx = self.ctx.enqueue_create_buffer[DType.int32](_LM_BLOCKS)
        self.pf_out_val = self.ctx.enqueue_create_buffer[DType.float32](1)
        self.pf_out_idx = self.ctx.enqueue_create_buffer[DType.int32](1)
        self.host_pf_val = self.ctx.enqueue_create_host_buffer[DType.float32](1)
        self.host_pf_idx = self.ctx.enqueue_create_host_buffer[DType.int32](1)

        self.token_log = List[List[Int]]()

    def device_name(self) raises -> String:
        return self.ctx.name()

    def max_seqs(self) -> Int:
        """The concurrency ceiling this session was provisioned for."""
        return _CUDA_BATCH_DECODE_MAX_SEQS

    def batched_dispatch_count(self, B: Int) -> Int:
        """The number of per-dispatch enqueues one `step_batched(B)` submission issues:
        `1 + n_layers * 9 + 3` — the plan the module docstring's substitution table documents."""
        return 1 + self.n_layers * 9 + 3

    def upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        """The tied embedding/lm_head table, the final norm gain, and the RoPE tables — the same
        one-time narrowing `_CudaResidentQwen3.upload_globals` performs (the helpers are shared,
        not copied)."""
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

    def upload_lm_head(mut self, lm: List[Float64]) raises -> Int:
        """The SEPARATE lm_head table (7B-lane) — narrowed into the session's own `lm_head`
        buffer, bound by every lm_head+argmax dispatch when `has_lm_head=1`. Refused unless the
        session was opened with `has_lm_head=1`."""
        if self.has_lm_head != 1:
            return RESIDENT_ERR_UPLOAD_LENGTH
        return _narrow_into(self.lm_head, lm, self.vocab * self.d_model, 0)

    def lm_head_w(mut self) -> _FP:
        """The matrix pointer every lm_head+argmax dispatch binds: the SEPARATE `lm_head`
        table when `has_lm_head=1`, the embedding table otherwise (tied convention). Origin
        erased to `MutAnyOrigin` via the address round-trip."""
        var a = Int(self.lm_head.unsafe_ptr())
        if self.has_lm_head != 1:
            a = Int(self.embed.unsafe_ptr())
        return UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=a)

    def upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        """One layer's eleven checkpoint tensors, narrowed and packed into four device matrices —
        byte-for-byte the same upload `_CudaResidentQwen3.upload_layer` performs (same shared
        helpers, same `[out, in]` transpose-once packing)."""
        if layer < 0 or layer >= self.n_layers:
            return RESIDENT_ERR_UPLOAD_LENGTH
        ref lw = self.layers[layer]
        var s = _narrow_into(lw.ln1, ln1, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.ln2, ln2, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        # 7B-lane: a no-QK-norm checkpoint passes empty qn/kn — fill the identity 1.0 gain
        # (the ropewrt kernels with `qk_norm=0` never read them).
        if len(qn) == 0:
            with lw.qn.map_to_host() as h:
                for i in range(self.d_head):
                    h[i] = Float32(1.0)
        else:
            s = _narrow_into(lw.qn, qn, self.d_head, 0)
            if s != RESIDENT_OK:
                return s
        if len(kn) == 0:
            with lw.kn.map_to_host() as h:
                for i in range(self.d_head):
                    h[i] = Float32(1.0)
        else:
            s = _narrow_into(lw.kn, kn, self.d_head, 0)
            if s != RESIDENT_OK:
                return s

        var n_q = self.h_q * self.d_head
        var n_kv = self.h_kv * self.d_head
        if self.skip_f32_projections == 1:
            # 1-element placeholders (7B memory fit): validate wire lengths, narrow nothing.
            if len(wq) != self.d_model * n_q or len(wk) != self.d_model * n_kv \
               or len(wv) != self.d_model * n_kv or len(wo) != n_q * self.d_model \
               or len(wgate) != self.d_model * self.d_ff \
               or len(wup) != self.d_model * self.d_ff \
               or len(wdown) != self.d_ff * self.d_model:
                return RESIDENT_ERR_UPLOAD_LENGTH
            return RESIDENT_OK
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

    def prefill_batched(mut self, ref prompts: List[List[Int]]) raises -> List[Int]:
        """Ingest each sequence's prompt INTO its own slot of the per-layer batched KV caches
        (`b * kv_stride_elems`) and return the B greedy FIRST generated tokens — the exact state
        `step_batched` continues from at poss=[prompt_len]. Borrowed, not consumed: a bench loop
        re-prefills the same prompt set once per timed run.

        Mechanism (the CUDA spelling of Metal's `prefill_batch_batched_ingest` retarget trick,
        simpler here because enqueue takes pointers BY VALUE): the unchanged prefill kernels
        (`_pf_embed_rows_kernel`, `_pf_rmsnorm_rows_kernel`, the v2 GEMMs, `_pf_ropewrt_kernel`,
        `_pf_attn_tiled_kernel_simd`) receive the SLOT-OFFSET cache pointers
        `lw.ck.unsafe_ptr() + b * kv_stride_elems` for the duration of sequence b's prefill —
        every KV write/read lands inside slot b, GEMMs/norms run exactly as the single-stream
        CUDA prefill, and the tail lm_head+argmax yields slot b's first generated token.
        Sequences run one at a time in stream order; the tile scratch is reused across them.
        """

        @parameter
        if not CUDA_SESSION_BUILD:
            # Removed before shader codegen; this is what a non-CUDA build compiles and runs.
            var empty = List[Int]()
            return empty^
        else:
            var B = len(prompts)
            if B < 1 or B > _CUDA_BATCH_DECODE_MAX_SEQS:
                var empty = List[Int]()
                return empty^
            for b in range(B):
                if len(prompts[b]) < 1 or len(prompts[b]) > self.max_ctx:
                    var empty = List[Int]()
                    return empty^
                for i in range(len(prompts[b])):
                    if prompts[b][i] < 0 or prompts[b][i] >= self.vocab:
                        var empty = List[Int]()
                        return empty^

            var n_q = self.h_q * self.d_head
            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
            var first_tokens = List[Int](capacity=B)

            for b in range(B):
                ref prompt = prompts[b]
                var n_prompt = len(prompt)
                var kv_off = b * self.kv_stride_elems
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
                            h[i] = Int32(prompt[pos + i])
                    self.ctx.synchronize()

                    # ── the embedding rows, gathered on-device from the resident table ──
                    self.ctx.enqueue_function[_pf_embed_rows_kernel](
                        self.pf_hidden.unsafe_ptr(), self.embed.unsafe_ptr(),
                        self.pf_tokens.unsafe_ptr(),
                        Int64(self.d_model), Int64(m),
                        grid_dim=_ceil_div(self.d_model, _TG) * m, block_dim=_TG,
                    )

                    for layer in range(self.n_layers):
                        ref lw = self.layers[layer]
                        # THIS sequence's KV slot: the unchanged kernels, slot-offset pointers.
                        var ck_b = lw.ck.unsafe_ptr() + kv_off
                        var cv_b = lw.cv.unsafe_ptr() + kv_off

                        # 1 ── rmsnorm(input_layernorm) over every row
                        self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                            self.pf_xn.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                            lw.ln1.unsafe_ptr(),
                            Int64(self.d_model), self.eps, Int64(m),
                            grid_dim=m, block_dim=_TG,
                        )
                        # 2 ── fused Q/K/V projection, one tiled GEMM (ASSIGN, v2)
                        self.ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
                            self.pf_qkv.unsafe_ptr(), self.pf_xn.unsafe_ptr(),
                            lw.w_qkv.unsafe_ptr(),
                            Int64(m), Int64(self.d_model),
                            Int64((self.h_q + 2 * self.h_kv) * self.d_head),
                            grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(
                                (self.h_q + 2 * self.h_kv) * self.d_head, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                        # 3 ── q_norm + k_norm + RoPE + the KV-cache write, into slot b
                        self.ctx.enqueue_function[_pf_ropewrt_kernel](
                            self.pf_q_rot.unsafe_ptr(), ck_b, cv_b,
                            self.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                            self.cos_t.unsafe_ptr(), self.sin_t.unsafe_ptr(),
                            Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                            self.eps, Int64(m),
                            Int64(self.qk_norm),  # qk_norm: runtime flag (Qwen3=1; Qwen2.5/llama=0)
                            grid_dim=(self.h_q + self.h_kv) * m, block_dim=self.d_head,
                        )
                        # 4 ── causal attention over slot b's cache
                        self.ctx.enqueue_function[_pf_attn_tiled_kernel_simd](
                            self.pf_attn.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                            ck_b, cv_b,
                            Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                            self.scale, Int64(m),
                            grid_dim=self.h_q * m, block_dim=self.d_head,
                        )
                        # 5 ── o_proj ACCUMULATED into the residual stream (v2)
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
                        # 7 ── gate/up + SwiGLU, one tiled GEMM pair (v2)
                        self.ctx.enqueue_function[_pf_gemm_swiglu_kernel_v2](
                            self.pf_act.unsafe_ptr(), self.pf_xn.unsafe_ptr(),
                            lw.w_gu.unsafe_ptr(),
                            Int64(m), Int64(self.d_model), Int64(self.d_ff),
                            grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.d_ff, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                        # 8 ── down_proj ACCUMULATED into the residual stream (v2)
                        self.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                            self.pf_hidden.unsafe_ptr(), self.pf_act.unsafe_ptr(),
                            lw.w_down.unsafe_ptr(),
                            Int64(m), Int64(self.d_ff), Int64(self.d_model),
                            grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.d_model, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                    pos += m

                # ── final rmsnorm + lm_head + argmax on this sequence's LAST row ──
                var lm_w = self.lm_head_w()
                self.ctx.enqueue_function[_lmhead_argmax_kernel](
                    self.pf_blk_val.unsafe_ptr(), self.pf_blk_idx.unsafe_ptr(),
                    self.pf_hidden.unsafe_ptr() + (last_m - 1) * self.d_model,
                    self.final_norm.unsafe_ptr(), lm_w,
                    Int64(self.d_model), Int64(self.vocab), self.eps, Int64(n_iters),
                    grid_dim=_LM_BLOCKS, block_dim=_TG,
                )
                self.ctx.enqueue_function[_argmax_reduce_kernel](
                    self.pf_out_val.unsafe_ptr(), self.pf_out_idx.unsafe_ptr(),
                    self.pf_blk_val.unsafe_ptr(), self.pf_blk_idx.unsafe_ptr(),
                    Int64(_LM_BLOCKS),
                    grid_dim=1, block_dim=_TG,
                )
                self.ctx.enqueue_copy(self.host_pf_val, self.pf_out_val)
                self.ctx.enqueue_copy(self.host_pf_idx, self.pf_out_idx)
                self.ctx.synchronize()
                var tok = Int(self.host_pf_idx.unsafe_ptr()[0])
                if tok < 0 or tok >= self.vocab:
                    var empty = List[Int]()
                    return empty^
                first_tokens.append(tok)

            return first_tokens^

    def step_batched(
        mut self, ref token_ids: List[Int], ref poss: List[Int],
    ) raises -> _StepOut:
        """ONE batched decode step: B sequences stepped together through the per-dispatch plan
        the module docstring's substitution table documents (1 + n_layers*9 + 3 enqueues).
        Writes the per-sequence token/pos/n_keys state into the device buffers, issues the
        chain, reads back B greedy tokens. `_StepOut.token_id` carries the LAST sequence's token
        (callers wanting all B use `step_batched_tokens`); `dispatches` reports the plan size."""

        @parameter
        if not CUDA_SESSION_BUILD:
            return _StepOut(-1, 0.0, 0, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            var toks = self.step_batched_tokens(token_ids, poss)
            if len(toks) != len(token_ids):
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(
                toks[len(toks) - 1], 0.0, self.batched_dispatch_count(len(toks)), RESIDENT_OK
            )

    def step_batched_tokens(
        mut self, ref token_ids: List[Int], ref poss: List[Int],
    ) raises -> List[Int]:
        """The B-token workhorse `step_batched` wraps: returns the B next tokens (one per
        sequence, in sequence order). The empty list signals failure (bad B / out-of-range
        inputs / a device token outside the vocabulary)."""

        @parameter
        if not CUDA_SESSION_BUILD:
            var empty = List[Int]()
            return empty^
        else:
            var B = len(token_ids)
            if len(poss) != B or B < 1 or B > _CUDA_BATCH_DECODE_MAX_SEQS:
                var empty = List[Int]()
                return empty^
            for b in range(B):
                if poss[b] < 0 or poss[b] >= self.max_ctx:
                    var empty = List[Int]()
                    return empty^
                if token_ids[b] < 0 or token_ids[b] >= self.vocab:
                    var empty = List[Int]()
                    return empty^

            var n_q = self.h_q * self.d_head
            var n_qkv = (self.h_q + 2 * self.h_kv) * self.d_head
            var kv_stride = Int64(self.kv_stride_elems)
            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)

            # ── per-sequence state into the device buffers the batched kernels read ──
            with self.b_tokens.map_to_host() as h:
                for b in range(B):
                    h[b] = Int32(token_ids[b])
            with self.b_poss.map_to_host() as h:
                for b in range(B):
                    h[b] = Int64(poss[b])
            with self.b_nkeys.map_to_host() as h:
                for b in range(B):
                    h[b] = Int64(poss[b] + 1)
            self.ctx.synchronize()

            # ── embed: B token ids -> hidden [B, d_model] ──
            self.ctx.enqueue_function[_pf_embed_rows_kernel](
                self.b_hidden.unsafe_ptr(), self.embed.unsafe_ptr(),
                self.b_tokens.unsafe_ptr(),
                Int64(self.d_model), Int64(B),
                grid_dim=_ceil_div(self.d_model, _TG) * B, block_dim=_TG,
            )

            for layer in range(self.n_layers):
                ref lw = self.layers[layer]

                # 1 ── rmsnorm(input_layernorm) over all B rows
                self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                    self.b_xn.unsafe_ptr(), self.b_hidden.unsafe_ptr(),
                    lw.ln1.unsafe_ptr(),
                    Int64(self.d_model), self.eps, Int64(B),
                    grid_dim=B, block_dim=_TG,
                )
                # 2 ── qkv_proj GEMM: xn [B,d_model] @ w_qkv -> qkv [B,n_qkv] (ASSIGN, v2)
                self.ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
                    self.b_qkv.unsafe_ptr(), self.b_xn.unsafe_ptr(),
                    lw.w_qkv.unsafe_ptr(),
                    Int64(B), Int64(self.d_model), Int64(n_qkv),
                    grid_dim=_ceil_div(B, _G2_BM) * _ceil_div(n_qkv, _G2_BN),
                    block_dim=_G2_NTHREADS,
                )
                # 3 ── batched KV producer: QK-norm + RoPE + pack into seq-b slots at poss[b]
                self.ctx.enqueue_function[_native_kv_producer_batched_f32_kernel](
                    self.b_q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    self.b_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                    self.cos_t.unsafe_ptr(), self.sin_t.unsafe_ptr(),
                    self.b_poss.unsafe_ptr(), kv_stride,
                    Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                    self.eps,
                    Int64(self.qk_norm),  # qk_norm: runtime flag (Qwen3=1; Qwen2.5/llama=0)
                    grid_dim=(self.h_q + self.h_kv) * B, block_dim=self.d_head,
                )
                # 4 ── batched attention PARTIAL: per-seq flash-decoding over [0, nkeys[b])
                self.ctx.enqueue_function[_native_kv_decode_splitk_partial_batched_f32_kernel](
                    self.b_sk_m.unsafe_ptr(), self.b_sk_l.unsafe_ptr(),
                    self.b_sk_o.unsafe_ptr(), self.b_q_rot.unsafe_ptr(),
                    lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    self.b_nkeys.unsafe_ptr(), kv_stride,
                    Int64(CUDA_BATCH_N_SPLITS), Int64(self.h_q), Int64(self.h_kv),
                    Int64(self.d_head), self.scale,
                    grid_dim=B * self.h_q * CUDA_BATCH_N_SPLITS, block_dim=self.d_head,
                )
                # 5 ── batched attention MERGE: [B,h_q,n_splits] partials -> attn_out [B,n_q]
                self.ctx.enqueue_function[_native_kv_decode_splitk_merge_batched_f32_kernel](
                    self.b_attn.unsafe_ptr(), self.b_sk_m.unsafe_ptr(),
                    self.b_sk_l.unsafe_ptr(), self.b_sk_o.unsafe_ptr(),
                    Int64(CUDA_BATCH_N_SPLITS), Int64(self.h_q), Int64(self.d_head),
                    grid_dim=B * self.h_q, block_dim=self.d_head,
                )
                # 6 ── o_proj GEMM ACCUMULATED into the residual stream (v2)
                self.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                    self.b_hidden.unsafe_ptr(), self.b_attn.unsafe_ptr(),
                    lw.w_o.unsafe_ptr(),
                    Int64(B), Int64(n_q), Int64(self.d_model),
                    grid_dim=_ceil_div(B, _G2_BM) * _ceil_div(self.d_model, _G2_BN),
                    block_dim=_G2_NTHREADS,
                )
                # 7 ── rmsnorm(post_attention_layernorm) over all B rows
                self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                    self.b_xn.unsafe_ptr(), self.b_hidden.unsafe_ptr(),
                    lw.ln2.unsafe_ptr(),
                    Int64(self.d_model), self.eps, Int64(B),
                    grid_dim=B, block_dim=_TG,
                )
                # 8 ── gate/up + SwiGLU, one tiled GEMM pair (v2)
                self.ctx.enqueue_function[_pf_gemm_swiglu_kernel_v2](
                    self.b_act.unsafe_ptr(), self.b_xn.unsafe_ptr(),
                    lw.w_gu.unsafe_ptr(),
                    Int64(B), Int64(self.d_model), Int64(self.d_ff),
                    grid_dim=_ceil_div(B, _G2_BM) * _ceil_div(self.d_ff, _G2_BN),
                    block_dim=_G2_NTHREADS,
                )
                # 9 ── down_proj GEMM ACCUMULATED into the residual stream (v2)
                self.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                    self.b_hidden.unsafe_ptr(), self.b_act.unsafe_ptr(),
                    lw.w_down.unsafe_ptr(),
                    Int64(B), Int64(self.d_ff), Int64(self.d_model),
                    grid_dim=_ceil_div(B, _G2_BM) * _ceil_div(self.d_model, _G2_BN),
                    block_dim=_G2_NTHREADS,
                )

            # ── tail: final rmsnorm (B rows) + batched lm_head + B-row argmax reduce ──
            self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                self.b_xn.unsafe_ptr(), self.b_hidden.unsafe_ptr(),
                self.final_norm.unsafe_ptr(),
                Int64(self.d_model), self.eps, Int64(B),
                grid_dim=B, block_dim=_TG,
            )
            self.ctx.enqueue_function[_batched_lmhead_argmax_kernel_f32](
                self.b_blk_val.unsafe_ptr(), self.b_blk_idx.unsafe_ptr(),
                self.b_xn.unsafe_ptr(), self.embed.unsafe_ptr(),
                Int64(B), Int64(self.d_model), Int64(self.vocab), Int64(n_iters),
                grid_dim=_LM_BLOCKS, block_dim=_TG,
            )
            self.ctx.enqueue_function[_batched_argmax_reduce_kernel_simd](
                self.b_out_val.unsafe_ptr(), self.b_out_idx.unsafe_ptr(),
                self.b_blk_val.unsafe_ptr(), self.b_blk_idx.unsafe_ptr(),
                Int64(_LM_BLOCKS),
                grid_dim=B, block_dim=_TG,
            )

            # ── B x 8 bytes back, not B x 608 KB ──
            self.ctx.enqueue_copy(self.host_out_val, self.b_out_val)
            self.ctx.enqueue_copy(self.host_out_idx, self.b_out_idx)
            self.ctx.synchronize()

            var toks = List[Int](capacity=B)
            for b in range(B):
                var t = Int(self.host_out_idx.unsafe_ptr()[b])
                if t < 0 or t >= self.vocab:
                    var empty = List[Int]()
                    return empty^
                toks.append(t)
            return toks^

    def seed_and_run_batched(
        mut self, ref first_tokens: List[Int], ref start_poss: List[Int], n_steps: Int,
    ) raises -> Int:
        """Run `n_steps` batched decode steps, feeding each step's B tokens forward as the next
        step's inputs (the host-side chain — the per-dispatch arm pays one small state upload +
        one synchronize per step; the W2 graph arm will move this chain on-device). Tokens are
        logged per sequence; read them afterwards with `batched_token(b, step)` — step `i` is the
        token generated at position `start_poss[b] + i`.

        Returns a RESIDENT_* status. The caller owns `pos` bookkeeping exactly as with the
        single-stream session: the next position after this call is `start_poss[b] + n_steps`.
        """

        @parameter
        if not CUDA_SESSION_BUILD:
            return RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT
        else:
            var B = len(first_tokens)
            if len(start_poss) != B or B < 1 or B > _CUDA_BATCH_DECODE_MAX_SEQS:
                return RESIDENT_ERR_UPLOAD_LENGTH
            if n_steps < 1:
                return RESIDENT_ERR_UPLOAD_LENGTH
            for b in range(B):
                if start_poss[b] < 0 or start_poss[b] + n_steps > self.max_ctx:
                    return RESIDENT_ERR_CONTEXT_FULL
                if first_tokens[b] < 0 or first_tokens[b] >= self.vocab:
                    return RESIDENT_ERR_UPLOAD_LENGTH

            self.token_log = List[List[Int]]()
            for _ in range(B):
                self.token_log.append(List[Int](capacity=n_steps))

            var cur_tokens = List[Int](capacity=B)
            for b in range(B):
                cur_tokens.append(first_tokens[b])
            var cur_poss = List[Int](capacity=B)
            for b in range(B):
                cur_poss.append(start_poss[b])

            for _ in range(n_steps):
                var toks = self.step_batched_tokens(cur_tokens, cur_poss)
                if len(toks) != B:
                    return RESIDENT_ERR_LAUNCH_FAILED
                for b in range(B):
                    self.token_log[b].append(toks[b])
                for b in range(B):
                    cur_tokens[b] = toks[b]
                    cur_poss[b] = cur_poss[b] + 1

            return RESIDENT_OK

    def batched_token(self, seq: Int, step: Int) -> Int:
        """The token sequence `seq` generated at decode step `step` of the last
        `seed_and_run_batched` call, read from the host-side log."""
        return self.token_log[seq][step]
