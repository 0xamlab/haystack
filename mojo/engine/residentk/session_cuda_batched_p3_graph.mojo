"""residentk.session_cuda_batched_p3_graph — LEVER L4 of the A100 autopsy: the
continuous-batching decode session with PACKED3 decode weights and its captured-graph arm.
Additive — `residentk.session_cuda_batched`, `residentk.session_cuda_batched_graph`, every
f32 kernel, and the single-stream p3 modules are byte-unmodified. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float32, uint8-packed
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/enterprise_bench.py
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Every entry point is private, and every launch is gated — the same two
defences `residentk.session_cuda_batched_graph`'s module docstring documents: nothing here is
public, so it never enters the runtime contract; and every `enqueue_function` caller opens
with `@parameter if not CUDA_SESSION_BUILD: return <shader_toolchain_absent>`, so with either
`-D ALGENTA_GPU` or `-D ALGENTA_CUDA` unset the launches are removed BEFORE shader codegen runs.

WHAT THIS SESSION IS FOR
------------------------
The autopsy's gap #3/#4: batched decode streams 2.62 GB of f32 weights per step at ~93 GB/s
(6% of HBM peak — the f32 v2 GEMM grids at M=B are decode-shaped and latency-bound) for a
28.9-33.3 ms TPOT at C=8, while the single-stream packed3 arm already streams the same model
at 470-497 GB/s (probe gates ALL PASS on this exact A100). This session ports packed3 weight
streaming INTO the batched step: the four weight-reading roles and the lm_head tail run the
`residentk.kernels_packed3_batched` M=B kernels (one output row per block, weights swept
ONCE for all B tokens), everything else — embed gather, rmsnorms, QK-norm+RoPE+KV pack,
split-K flash-decoding attention, argmax reduce, the device-side advance kernel — is the f32
batched arm's kernel reused byte-unmodified. The f32 weight residents STAY (the admission
prefill keeps the f32 v2 GEMMs — levers L1/L2 — so prefill = f32 / decode = packed3, the
same split the single-stream `residentk.session_cuda_p3` arm establishes).

COMPOSITION, NOT COPY (the f32 graph arm's own discipline, extended)
---------------------------------------------------------------------
`_CudaResidentQwen3BatchedP3Graph` HOLDS the f32 batched session `inner` (weights, RoPE
tables, per-sequence KV slots, ALL f32 scratch, the prefill pass, the per-dispatch fallback
plan) and adds ONLY: the packed3 weight twins (`_LayerP3` per layer — the single-stream p3
session's own struct — plus the packed tied lm_head table) and its OWN per-B captured graphs
(the p3 step chain). The f32 and p3 arms replay against the SAME resident state, so they can
never drift, and the serve driver's concurrent-vs-sequential token diff runs on one set of
weights.

THE CAPTURED P3 STEP CHAIN (per replay; node count UNCHANGED from the f32 arm — the four
GEMM roles and the lm_head swap 1-for-1):

    _pf_embed_rows_kernel_bg                 grid ceil(d_model/_TG)*B   tokens: state[0..B)
    per layer:
      _pf_rmsnorm_rows_kernel                grid B
      _batched_p3_gemv_assign_kernel         grid n_qkv   (qkv, ASSIGN)
      _native_kv_producer_batched_f32_kernel_bg   poss: state[B..2B)
      _native_kv_decode_splitk_partial_batched_f32_kernel_bg   nkeys: state[2B..3B)
      _native_kv_decode_splitk_merge_batched_f32_kernel
      _batched_p3_gemv_accum_kernel          grid d_model (o_proj, ACCUM residual)
      _pf_rmsnorm_rows_kernel                grid B
      _batched_p3_swiglu_kernel              grid d_ff    (gate/up + SwiGLU)
      _batched_p3_gemv_accum_kernel          grid d_model (down_proj, ACCUM residual)
    _pf_rmsnorm_rows_kernel                  grid B (final norm)
    _batched_lmhead_argmax_kernel_p3         grid _LM_BLOCKS
    _batched_argmax_reduce_kernel_simd       grid B
    _graph_advance_batched_kernel            grid 1 / block B

= 1 + n_layers*9 + 4 kernel nodes per replay (258 at Qwen3-0.6B), captured ONCE per B.

The capture rules are the f32 graph arm's own (kernels-only capture, per-step dynamic
scalars from the STATE region, ONE eager H2D seed per replay batch, device-side advance
kernel), followed to the letter; the STATE layout is unchanged ([0,B) tokens, [B,2B) poss,
[2B,3B) nkeys, [3B] step counter). The pointer hoisting discipline is `_build_batched_graph`'s
own — the p3 weight buffers are hoisted exactly the way the f32 matrices are.
"""

from max.gpu.host import (
    DeviceBuffer,
    DeviceGraph,
    DeviceGraphBuilder,
    HostBuffer,
)
from std.collections import Optional
from std.origin import MutAnyOrigin
from std.gpu import block_idx, grid_dim, thread_idx

alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]
"""A device Int64 buffer as a kernel parameter — the log-head copy's operand type."""

comptime _P3G_LOG_HEAD_CAP: Int = 2048
"""Narrow log-readback staging (MEASURED seam lever): the first cut of
`seed_and_run_batched_graph` D2H-copied the WHOLE token log (32 x max_ctx int64 = 1.2 MB)
after every chunk — the chunk-horizon A/B measured that copy as the graph seam's dominant
cost (~2.4 ms per 8-step seam at C=8). The reader only ever touches the first
`B * n_steps` entries, so one small kernel head-stages those entries into a
`_P3G_LOG_HEAD_CAP`-entry device buffer and ONLY that head crosses to the host. 2048
entries = 32 seqs x the driver's CHUNK_MAX(64) horizon."""


def _p3g_log_head_copy_kernel(dst: _I64P, src: _I64P, n_i64: Int64):
    """First `n` int64s of the chunk's token log, head-staged for the narrow D2H (one
    thread per entry, grid-stride over a 256-thread grid)."""
    var n = Int(n_i64)
    var i = Int(block_idx.x) * 256 + Int(thread_idx.x)
    var stride = Int(grid_dim.x) * 256
    while i < n:
        dst[i] = src[i]
        i += stride
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
    _batched_argmax_reduce_kernel_simd,
)
from residentk.kernels_prefill_f32 import (
    _pf_embed_rows_kernel,
)
from residentk.kernels_packed3 import (
    _p3_words_per_row,
    _p3_blocks_per_row,
)
from residentk.kernels_packed3_batched import (
    _P3B_TG,
    _P3B_GROUPS,
    _batched_p3_gemv_assign_kernel,
    _batched_p3_gemv_accum_kernel,
    _batched_p3_gemv_assign_kernel_r2,
    _batched_p3_gemv_accum_kernel_r2,
    _batched_p3_swiglu_kernel,
    _batched_lmhead_argmax_kernel_p3,
)
from residentk.kernels_batched_cuda_graph import (
    _pf_embed_rows_kernel_bg,
    _native_kv_producer_batched_f32_kernel_bg,
    _graph_advance_batched_kernel,
)
from residentk.kernels_decode_attn_flash import (
    _DECODE_FLASH_NTHREADS,
    _DECODE_FLASH_WARPS_PER_BLOCK,
    _splitk_partial_batched_flash_kernel,
    _splitk_partial_batched_flash_kernel_bg,
)
from kvprod_batched_f32_cuda import (
    _native_kv_producer_batched_f32_kernel,
)
from native_kv_decode_attn_splitk_batched_f32 import (
    _native_kv_decode_splitk_merge_batched_f32_kernel,
)
from residentk.session import (
    _LM_BLOCKS,
    _ceil_div,
)
from residentk.session_cuda import (
    CUDA_SESSION_BUILD,
)
from residentk.session_cuda_batched import (
    CUDA_BATCH_N_SPLITS,
    _CUDA_BATCH_DECODE_MAX_SEQS,
    _CudaResidentQwen3Batched,
)
from residentk.session_cuda_p3 import (
    _LayerP3,
    _pack_transposed_f64_into_p3,
    _pack_f64_into_p3,
)
from std.sys import is_defined

comptime P3G_DBG_TRACE: Bool = is_defined["ALGENTA_P3G_TRACE"]()
"""Debug scalpel (never adopted): with `-D ALGENTA_P3G_TRACE`, every chunk prints its seed
(tokens/poss) and its logged tokens — the instrumentation that bisected the L5 gate-2
divergence between seed-state corruption and in-graph compute corruption."""

comptime P3B_R2: Bool = is_defined["ALGENTA_P3B_R2"]()
"""LEVER L6: with `-D ALGENTA_P3B_R2`, the three packed3 batched decode GEMM roles
(qkv ASSIGN, o ACCUM, down ACCUM) dispatch the TWO-OUTPUT-ROWS-PER-BLOCK kernels —
`kernels_packed3_batched`'s `_r2` family, the p3b_smallm_probe battery's measured winner
(~1.27x effective weight GB/s at B=8, all three roles): the B activation float4 loads
amortize over two rows' packed-weight streams. Per-row math and accumulation order are the
shipped kernels' verbatim — bit-identical tokens, the serve selftest's identity gate
applies unmodified. The swiglu role keeps the shipped kernel (its block already streams two
weight rows)."""

comptime P3G_PSS: Bool = is_defined["ALGENTA_P3G_PSS"]()
"""LEVER L7 scalpel (kept as the measurement record): with `-D ALGENTA_P3G_PSS`,
`seed_and_run_batched_graph` synchronizes the context between CONSECUTIVE replays. Used in
round 3 to test whether the graph-under-lanes corruption was multi-replay overlap: it
changed NOTHING (gate 2 failed identically) — the corruption was the driver's
`move_slot_kv` 4x address under-offset, not replay pacing. Not shipped in any race arm."""


@fieldwise_init
struct _CudaResidentQwen3BatchedP3Graph(Movable):
    """The f32 batched session (held as `inner` — prefill, KV, norms, attention, all f32
    scratch stay f32) PLUS the packed3 decode weight twins and one captured p3 step graph
    per batch size B. Arm state lives in four parallel lists indexed together (B, STATE
    buffer, pinned twin, graph), exactly the f32 graph arm's layout. `Movable` for the same
    reason every other session struct is."""

    var inner: _CudaResidentQwen3Batched
    var layers_p3: List[_LayerP3]
    var p3_lm: DeviceBuffer[DType.float32]
    var p3_lm_s: DeviceBuffer[DType.float32]
    var p3_lm_z: DeviceBuffer[DType.float32]

    var graph_token_log: DeviceBuffer[DType.int64]
    var host_graph_token_log: HostBuffer[DType.int64]
    var log_head: DeviceBuffer[DType.int64]
    var host_log_head: HostBuffer[DType.int64]
    var arms_B: List[Int]
    var arms_state: List[DeviceBuffer[DType.int64]]
    var arms_host_state: List[HostBuffer[DType.int64]]
    var arms_graph: List[Optional[DeviceGraph]]
    var last_B: Int

    def __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
        """Open the f32 batched session (the ONLY `DeviceContext` in this struct), then
        allocate the packed3 decode twins on the SAME context, ONCE. Buffer sizes are the
        single-stream p3 session's own layout arithmetic (`_p3_words_per_row` /
        `_p3_blocks_per_row`). Called only from inside a `@parameter if CUDA_SESSION_BUILD`
        branch — the structural protection every residentk constructor documents."""
        self.inner = _CudaResidentQwen3Batched(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab, max_ctx, eps, scale
        )

        var n_q = h_q * d_head
        var n_kv = h_kv * d_head
        var n_qkv = n_q + 2 * n_kv

        var qkv_words = n_qkv * _p3_words_per_row(d_model)
        var qkv_meta = n_qkv * _p3_blocks_per_row(d_model)
        var o_words = d_model * _p3_words_per_row(n_q)
        var o_meta = d_model * _p3_blocks_per_row(n_q)
        var gu_words = 2 * d_ff * _p3_words_per_row(d_model)
        var gu_meta = 2 * d_ff * _p3_blocks_per_row(d_model)
        var down_words = d_model * _p3_words_per_row(d_ff)
        var down_meta = d_model * _p3_blocks_per_row(d_ff)

        self.layers_p3 = List[_LayerP3]()
        for _ in range(n_layers):
            self.layers_p3.append(
                _LayerP3(
                    self.inner.ctx.enqueue_create_buffer[DType.float32](qkv_words),
                    self.inner.ctx.enqueue_create_buffer[DType.float32](qkv_meta),
                    self.inner.ctx.enqueue_create_buffer[DType.float32](qkv_meta),
                    self.inner.ctx.enqueue_create_buffer[DType.float32](o_words),
                    self.inner.ctx.enqueue_create_buffer[DType.float32](o_meta),
                    self.inner.ctx.enqueue_create_buffer[DType.float32](o_meta),
                    self.inner.ctx.enqueue_create_buffer[DType.float32](gu_words),
                    self.inner.ctx.enqueue_create_buffer[DType.float32](gu_meta),
                    self.inner.ctx.enqueue_create_buffer[DType.float32](gu_meta),
                    self.inner.ctx.enqueue_create_buffer[DType.float32](down_words),
                    self.inner.ctx.enqueue_create_buffer[DType.float32](down_meta),
                    self.inner.ctx.enqueue_create_buffer[DType.float32](down_meta),
                )
            )

        self.p3_lm = self.inner.ctx.enqueue_create_buffer[DType.float32](
            vocab * _p3_words_per_row(d_model)
        )
        self.p3_lm_s = self.inner.ctx.enqueue_create_buffer[DType.float32](
            vocab * _p3_blocks_per_row(d_model)
        )
        self.p3_lm_z = self.inner.ctx.enqueue_create_buffer[DType.float32](
            vocab * _p3_blocks_per_row(d_model)
        )

        var log_elems = _CUDA_BATCH_DECODE_MAX_SEQS * max_ctx
        self.graph_token_log = self.inner.ctx.enqueue_create_buffer[DType.int64](log_elems)
        self.host_graph_token_log = self.inner.ctx.enqueue_create_host_buffer[DType.int64](
            log_elems
        )
        self.log_head = self.inner.ctx.enqueue_create_buffer[DType.int64](_P3G_LOG_HEAD_CAP)
        self.host_log_head = self.inner.ctx.enqueue_create_host_buffer[DType.int64](
            _P3G_LOG_HEAD_CAP
        )
        self.arms_B = List[Int]()
        self.arms_state = List[DeviceBuffer[DType.int64]]()
        self.arms_host_state = List[HostBuffer[DType.int64]]()
        self.arms_graph = List[Optional[DeviceGraph]]()
        self.last_B = 0

    # ═══════════════════════════════ delegation to the f32 session ═══════════════════════

    def device_name(self) raises -> String:
        return self.inner.device_name()

    def max_seqs(self) -> Int:
        return self.inner.max_seqs()

    def upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        """The f32 session's own upload (embed stays f32 — prefill and the embed gather read
        it), then the packed3 twin of the SAME tied table as the decode lm_head weights."""
        var s = self.inner.upload_globals(embed, final_norm, cos_t, sin_t, n_pos)
        if s != RESIDENT_OK:
            return s
        s = _pack_f64_into_p3(
            self.p3_lm, self.p3_lm_s, self.p3_lm_z,
            embed, self.inner.d_model, self.inner.vocab,
        )
        return s

    def upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        """The f32 session's own upload (the f32 matrices the prefill GEMMs read, unchanged),
        then the packed3 twins of the four projection roles — the single-stream p3 session's
        own packing, row for row (q/k/v concatenated into ONE `[n_qkv, d_model]` packed
        buffer; gate/up into ONE `[2*d_ff, d_model]`)."""
        var s = self.inner.upload_layer(
            layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wgate, wup, wdown
        )
        if s != RESIDENT_OK:
            return s

        ref lp = self.layers_p3[layer]
        var n_q = self.inner.h_q * self.inner.d_head
        var n_kv = self.inner.h_kv * self.inner.d_head
        var d_model = self.inner.d_model
        var d_ff = self.inner.d_ff

        s = _pack_transposed_f64_into_p3(
            lp.p3_qkv, lp.p3_qkv_s, lp.p3_qkv_z, wq, d_model, n_q, 0
        )
        if s != RESIDENT_OK:
            return s
        s = _pack_transposed_f64_into_p3(
            lp.p3_qkv, lp.p3_qkv_s, lp.p3_qkv_z, wk, d_model, n_kv, n_q
        )
        if s != RESIDENT_OK:
            return s
        s = _pack_transposed_f64_into_p3(
            lp.p3_qkv, lp.p3_qkv_s, lp.p3_qkv_z, wv, d_model, n_kv, n_q + n_kv
        )
        if s != RESIDENT_OK:
            return s
        s = _pack_transposed_f64_into_p3(
            lp.p3_o, lp.p3_o_s, lp.p3_o_z, wo, n_q, d_model, 0
        )
        if s != RESIDENT_OK:
            return s
        s = _pack_transposed_f64_into_p3(
            lp.p3_gu, lp.p3_gu_s, lp.p3_gu_z, wgate, d_model, d_ff, 0
        )
        if s != RESIDENT_OK:
            return s
        s = _pack_transposed_f64_into_p3(
            lp.p3_gu, lp.p3_gu_s, lp.p3_gu_z, wup, d_model, d_ff, d_ff
        )
        if s != RESIDENT_OK:
            return s
        s = _pack_transposed_f64_into_p3(
            lp.p3_down, lp.p3_down_s, lp.p3_down_z, wdown, d_ff, d_model, 0
        )
        return s

    def seal(mut self) raises -> Int:
        return self.inner.seal()

    def step_batched_tokens(
        mut self, ref token_ids: List[Int], ref poss: List[Int],
    ) raises -> List[Int]:
        """The serve driver's FALLBACK entry point, spelled the way the f32 graph arm spells
        it so the driver's scheduler is arm-agnostic: under this arm the per-dispatch step
        IS the p3 chain."""
        return self.step_batched_p3_tokens(token_ids, poss)

    # ═══════════════ the per-dispatch p3 step (fallback + selftest reference) ═════════════

    def step_batched_p3_tokens(
        mut self, ref token_ids: List[Int], ref poss: List[Int],
    ) raises -> List[Int]:
        """ONE p3 batched decode step, per-dispatch: the f32 batched plan with the four
        GEMM roles and the lm_head tail swapped to their packed3 batched twins (module
        docstring, chain table). Returns the B next tokens in sequence order; the empty
        list signals failure. The serve driver's graph-chunk FALLBACK and the selftest's
        single-stream reference both run through this path."""

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
                if poss[b] < 0 or poss[b] >= self.inner.max_ctx:
                    var empty = List[Int]()
                    return empty^
                if token_ids[b] < 0 or token_ids[b] >= self.inner.vocab:
                    var empty = List[Int]()
                    return empty^

            var n_q = self.inner.h_q * self.inner.d_head
            var n_qkv = (self.inner.h_q + 2 * self.inner.h_kv) * self.inner.d_head
            var kv_stride = Int64(self.inner.kv_stride_elems)
            var n_iters = _ceil_div(self.inner.vocab, _LM_BLOCKS * _SUBS)

            # ── per-sequence state into the device buffers the batched kernels read ──
            with self.inner.b_tokens.map_to_host() as h:
                for b in range(B):
                    h[b] = Int32(token_ids[b])
            with self.inner.b_poss.map_to_host() as h:
                for b in range(B):
                    h[b] = Int64(poss[b])
            with self.inner.b_nkeys.map_to_host() as h:
                for b in range(B):
                    h[b] = Int64(poss[b] + 1)
            self.inner.ctx.synchronize()

            # ── embed: B token ids -> hidden [B, d_model] (f32 arm's kernel, unchanged) ──
            self.inner.ctx.enqueue_function[_pf_embed_rows_kernel](
                self.inner.b_hidden.unsafe_ptr(), self.inner.embed.unsafe_ptr(),
                self.inner.b_tokens.unsafe_ptr(),
                Int64(self.inner.d_model), Int64(B),
                grid_dim=_ceil_div(self.inner.d_model, _TG) * B, block_dim=_TG,
            )

            for layer in range(self.inner.n_layers):
                ref lw = self.inner.layers[layer]
                ref lp = self.layers_p3[layer]

                # 1 ── rmsnorm(input_layernorm) over all B rows (f32 kernel, unchanged)
                self.inner.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                    self.inner.b_xn.unsafe_ptr(), self.inner.b_hidden.unsafe_ptr(),
                    lw.ln1.unsafe_ptr(),
                    Int64(self.inner.d_model), self.inner.eps, Int64(B),
                    grid_dim=B, block_dim=_TG,
                )
                # 2 ── qkv_proj: packed3 batched ASSIGN, weights swept ONCE for all B rows
                # (LEVER L6: the two-rows-per-block `_r2` kernel under `-D ALGENTA_P3B_R2`)
                @parameter
                if P3B_R2:
                    self.inner.ctx.enqueue_function[_batched_p3_gemv_assign_kernel_r2](
                        self.inner.b_qkv.unsafe_ptr(), self.inner.b_xn.unsafe_ptr(),
                        lp.p3_qkv.unsafe_ptr(), lp.p3_qkv_s.unsafe_ptr(),
                        lp.p3_qkv_z.unsafe_ptr(),
                        Int64(self.inner.d_model), Int64(n_qkv), Int64(B),
                        grid_dim=n_qkv // 2, block_dim=_P3B_TG,
                    )
                else:
                    self.inner.ctx.enqueue_function[_batched_p3_gemv_assign_kernel](
                        self.inner.b_qkv.unsafe_ptr(), self.inner.b_xn.unsafe_ptr(),
                        lp.p3_qkv.unsafe_ptr(), lp.p3_qkv_s.unsafe_ptr(),
                        lp.p3_qkv_z.unsafe_ptr(),
                        Int64(self.inner.d_model), Int64(n_qkv), Int64(B),
                        grid_dim=n_qkv, block_dim=_P3B_TG,
                    )
                # 3 ── batched KV producer (f32 arm's kernel, unchanged)
                self.inner.ctx.enqueue_function[_native_kv_producer_batched_f32_kernel](
                    self.inner.b_q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    self.inner.b_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                    self.inner.cos_t.unsafe_ptr(), self.inner.sin_t.unsafe_ptr(),
                    self.inner.b_poss.unsafe_ptr(), kv_stride,
                    Int64(self.inner.h_q), Int64(self.inner.h_kv), Int64(self.inner.d_head),
                    self.inner.eps,
                    Int64(1),  # qk_norm: Qwen3-family only, always on
                    grid_dim=(self.inner.h_q + self.inner.h_kv) * B,
                    block_dim=self.inner.d_head,
                )
                # 4 ── batched attention PARTIAL — the flash-style warp-per-(seq,head,split)
                # kernel (same partial layout the unchanged merge consumes)
                self.inner.ctx.enqueue_function[_splitk_partial_batched_flash_kernel](
                    self.inner.b_sk_m.unsafe_ptr(), self.inner.b_sk_l.unsafe_ptr(),
                    self.inner.b_sk_o.unsafe_ptr(), self.inner.b_q_rot.unsafe_ptr(),
                    lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    self.inner.b_nkeys.unsafe_ptr(), Int64(B), kv_stride,
                    Int64(CUDA_BATCH_N_SPLITS), Int64(self.inner.h_q), Int64(self.inner.h_kv),
                    Int64(self.inner.d_head), self.inner.scale,
                    grid_dim=_ceil_div(
                        B * self.inner.h_q * CUDA_BATCH_N_SPLITS,
                        _DECODE_FLASH_WARPS_PER_BLOCK,
                    ),
                    block_dim=_DECODE_FLASH_NTHREADS,
                )
                # 5 ── batched attention MERGE (f32 arm's kernel, unchanged)
                self.inner.ctx.enqueue_function[
                    _native_kv_decode_splitk_merge_batched_f32_kernel
                ](
                    self.inner.b_attn.unsafe_ptr(), self.inner.b_sk_m.unsafe_ptr(),
                    self.inner.b_sk_l.unsafe_ptr(), self.inner.b_sk_o.unsafe_ptr(),
                    Int64(CUDA_BATCH_N_SPLITS), Int64(self.inner.h_q), Int64(self.inner.d_head),
                    grid_dim=B * self.inner.h_q, block_dim=self.inner.d_head,
                )
                # 6 ── o_proj + residual — packed3 batched ACCUM (LEVER L6 `_r2` under flag)
                @parameter
                if P3B_R2:
                    self.inner.ctx.enqueue_function[_batched_p3_gemv_accum_kernel_r2](
                        self.inner.b_hidden.unsafe_ptr(), self.inner.b_attn.unsafe_ptr(),
                        lp.p3_o.unsafe_ptr(), lp.p3_o_s.unsafe_ptr(), lp.p3_o_z.unsafe_ptr(),
                        Int64(n_q), Int64(self.inner.d_model), Int64(B),
                        grid_dim=self.inner.d_model // 2, block_dim=_P3B_TG,
                    )
                else:
                    self.inner.ctx.enqueue_function[_batched_p3_gemv_accum_kernel](
                        self.inner.b_hidden.unsafe_ptr(), self.inner.b_attn.unsafe_ptr(),
                        lp.p3_o.unsafe_ptr(), lp.p3_o_s.unsafe_ptr(), lp.p3_o_z.unsafe_ptr(),
                        Int64(n_q), Int64(self.inner.d_model), Int64(B),
                        grid_dim=self.inner.d_model, block_dim=_P3B_TG,
                    )
                # 7 ── rmsnorm(post_attention_layernorm) over all B rows
                self.inner.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                    self.inner.b_xn.unsafe_ptr(), self.inner.b_hidden.unsafe_ptr(),
                    lw.ln2.unsafe_ptr(),
                    Int64(self.inner.d_model), self.inner.eps, Int64(B),
                    grid_dim=B, block_dim=_TG,
                )
                # 8 ── gate/up + SwiGLU — packed3 batched
                self.inner.ctx.enqueue_function[_batched_p3_swiglu_kernel](
                    self.inner.b_act.unsafe_ptr(), self.inner.b_xn.unsafe_ptr(),
                    lp.p3_gu.unsafe_ptr(), lp.p3_gu_s.unsafe_ptr(), lp.p3_gu_z.unsafe_ptr(),
                    Int64(self.inner.d_model), Int64(self.inner.d_ff), Int64(B),
                    grid_dim=self.inner.d_ff, block_dim=_P3B_TG,
                )
                # 9 ── down_proj + residual — packed3 batched ACCUM (LEVER L6 `_r2`)
                @parameter
                if P3B_R2:
                    self.inner.ctx.enqueue_function[_batched_p3_gemv_accum_kernel_r2](
                        self.inner.b_hidden.unsafe_ptr(), self.inner.b_act.unsafe_ptr(),
                        lp.p3_down.unsafe_ptr(), lp.p3_down_s.unsafe_ptr(),
                        lp.p3_down_z.unsafe_ptr(),
                        Int64(self.inner.d_ff), Int64(self.inner.d_model), Int64(B),
                        grid_dim=self.inner.d_model // 2, block_dim=_P3B_TG,
                    )
                else:
                    self.inner.ctx.enqueue_function[_batched_p3_gemv_accum_kernel](
                        self.inner.b_hidden.unsafe_ptr(), self.inner.b_act.unsafe_ptr(),
                        lp.p3_down.unsafe_ptr(), lp.p3_down_s.unsafe_ptr(),
                        lp.p3_down_z.unsafe_ptr(),
                        Int64(self.inner.d_ff), Int64(self.inner.d_model), Int64(B),
                        grid_dim=self.inner.d_model, block_dim=_P3B_TG,
                    )

            # ── tail: final rmsnorm (B rows) + packed3 batched lm_head + B-row reduce ──
            self.inner.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                self.inner.b_xn.unsafe_ptr(), self.inner.b_hidden.unsafe_ptr(),
                self.inner.final_norm.unsafe_ptr(),
                Int64(self.inner.d_model), self.inner.eps, Int64(B),
                grid_dim=B, block_dim=_TG,
            )
            self.inner.ctx.enqueue_function[_batched_lmhead_argmax_kernel_p3](
                self.inner.b_blk_val.unsafe_ptr(), self.inner.b_blk_idx.unsafe_ptr(),
                self.inner.b_xn.unsafe_ptr(),
                self.p3_lm.unsafe_ptr(), self.p3_lm_s.unsafe_ptr(), self.p3_lm_z.unsafe_ptr(),
                Int64(B), Int64(self.inner.d_model), Int64(self.inner.vocab), Int64(n_iters),
                grid_dim=_LM_BLOCKS, block_dim=_TG,
            )
            self.inner.ctx.enqueue_function[_batched_argmax_reduce_kernel_simd](
                self.inner.b_out_val.unsafe_ptr(), self.inner.b_out_idx.unsafe_ptr(),
                self.inner.b_blk_val.unsafe_ptr(), self.inner.b_blk_idx.unsafe_ptr(),
                Int64(_LM_BLOCKS),
                grid_dim=B, block_dim=_TG,
            )

            # ── B x 8 bytes back, not B x 608 KB ──
            self.inner.ctx.enqueue_copy(self.inner.host_out_val, self.inner.b_out_val)
            self.inner.ctx.enqueue_copy(self.inner.host_out_idx, self.inner.b_out_idx)
            self.inner.ctx.synchronize()

            var toks = List[Int](capacity=B)
            for b in range(B):
                var t = Int(self.inner.host_out_idx.unsafe_ptr()[b])
                if t < 0 or t >= self.inner.vocab:
                    var empty = List[Int]()
                    return empty^
                toks.append(t)
            return toks^

    # ═══════════════════════════════ the captured p3 graph arm ═══════════════════════════

    def _ensure_arm(mut self, B: Int) raises -> Int:
        """Find-or-create the p3 graph arm for batch size B; returns its index in the
        parallel lists. Lazily captured, the f32 graph arm's own reason: capture needs every
        resident buffer allocated, and most runs only touch a handful of B values."""
        for i in range(len(self.arms_B)):
            if self.arms_B[i] == B:
                return i
        self.arms_B.append(B)
        self.arms_state.append(
            self.inner.ctx.enqueue_create_buffer[DType.int64](3 * B + 1)
        )
        self.arms_host_state.append(
            self.inner.ctx.enqueue_create_host_buffer[DType.int64](3 * B + 1)
        )
        self.arms_graph.append(Optional[DeviceGraph]())
        var idx = len(self.arms_B) - 1
        self._build_batched_graph_p3(idx, B)
        return idx

    def _build_batched_graph_p3(mut self, idx: Int, B: Int) raises:
        """Capture the ENTIRE p3 batched step chain for batch size B into ONE `DeviceGraph`
        — the module docstring's chain table. Pointer hoisting discipline: the f32 graph
        arm's own (addresses taken in mut scope, rebuilt inside the {imm} capture)."""
        # ── hoist every device address in mut scope; rebuild inside the {imm} capture ──
        var hidden_a = Int(self.inner.b_hidden.unsafe_ptr())
        var xn_a = Int(self.inner.b_xn.unsafe_ptr())
        var qkv_a = Int(self.inner.b_qkv.unsafe_ptr())
        var q_rot_a = Int(self.inner.b_q_rot.unsafe_ptr())
        var attn_a = Int(self.inner.b_attn.unsafe_ptr())
        var act_a = Int(self.inner.b_act.unsafe_ptr())
        var skm_a = Int(self.inner.b_sk_m.unsafe_ptr())
        var skl_a = Int(self.inner.b_sk_l.unsafe_ptr())
        var sko_a = Int(self.inner.b_sk_o.unsafe_ptr())
        var blk_val_a = Int(self.inner.b_blk_val.unsafe_ptr())
        var blk_idx_a = Int(self.inner.b_blk_idx.unsafe_ptr())
        var out_val_a = Int(self.inner.b_out_val.unsafe_ptr())
        var out_idx_a = Int(self.inner.b_out_idx.unsafe_ptr())
        var embed_a = Int(self.inner.embed.unsafe_ptr())
        var final_norm_a = Int(self.inner.final_norm.unsafe_ptr())
        var cos_a = Int(self.inner.cos_t.unsafe_ptr())
        var sin_a = Int(self.inner.sin_t.unsafe_ptr())
        var state_a = Int(self.arms_state[idx].unsafe_ptr())
        var tlog_a = Int(self.graph_token_log.unsafe_ptr())
        var p3_lm_a = Int(self.p3_lm.unsafe_ptr())
        var p3_lm_s_a = Int(self.p3_lm_s.unsafe_ptr())
        var p3_lm_z_a = Int(self.p3_lm_z.unsafe_ptr())

        var ln1s = List[Int]()
        var ln2s = List[Int]()
        var qns = List[Int]()
        var kns = List[Int]()
        var cks = List[Int]()
        var cvs = List[Int]()
        var p3_qkv_w = List[Int]()
        var p3_qkv_s = List[Int]()
        var p3_qkv_z = List[Int]()
        var p3_o_w = List[Int]()
        var p3_o_s = List[Int]()
        var p3_o_z = List[Int]()
        var p3_gu_w = List[Int]()
        var p3_gu_s = List[Int]()
        var p3_gu_z = List[Int]()
        var p3_dn_w = List[Int]()
        var p3_dn_s = List[Int]()
        var p3_dn_z = List[Int]()
        for layer in range(self.inner.n_layers):
            ref lw = self.inner.layers[layer]
            ref lp = self.layers_p3[layer]
            ln1s.append(Int(lw.ln1.unsafe_ptr()))
            ln2s.append(Int(lw.ln2.unsafe_ptr()))
            qns.append(Int(lw.qn.unsafe_ptr()))
            kns.append(Int(lw.kn.unsafe_ptr()))
            cks.append(Int(lw.ck.unsafe_ptr()))
            cvs.append(Int(lw.cv.unsafe_ptr()))
            p3_qkv_w.append(Int(lp.p3_qkv.unsafe_ptr()))
            p3_qkv_s.append(Int(lp.p3_qkv_s.unsafe_ptr()))
            p3_qkv_z.append(Int(lp.p3_qkv_z.unsafe_ptr()))
            p3_o_w.append(Int(lp.p3_o.unsafe_ptr()))
            p3_o_s.append(Int(lp.p3_o_s.unsafe_ptr()))
            p3_o_z.append(Int(lp.p3_o_z.unsafe_ptr()))
            p3_gu_w.append(Int(lp.p3_gu.unsafe_ptr()))
            p3_gu_s.append(Int(lp.p3_gu_s.unsafe_ptr()))
            p3_gu_z.append(Int(lp.p3_gu_z.unsafe_ptr()))
            p3_dn_w.append(Int(lp.p3_down.unsafe_ptr()))
            p3_dn_s.append(Int(lp.p3_down_s.unsafe_ptr()))
            p3_dn_z.append(Int(lp.p3_down_z.unsafe_ptr()))

        var n_layers_c = self.inner.n_layers
        var B_c = B
        var d_model_i = Int64(self.inner.d_model)
        var n_q = self.inner.h_q * self.inner.d_head
        var n_kv = self.inner.h_kv * self.inner.d_head
        var n_qkv_i = Int64(n_q + 2 * n_kv)
        var h_q_i = Int64(self.inner.h_q)
        var h_kv_i = Int64(self.inner.h_kv)
        var d_head_i = Int64(self.inner.d_head)
        var d_ff_i = Int64(self.inner.d_ff)
        var vocab_i = Int64(self.inner.vocab)
        var kv_stride_i = Int64(self.inner.kv_stride_elems)
        var eps_c = self.inner.eps
        var scale_c = self.inner.scale
        var B_i = Int64(B)
        var n_iters_i = Int64(_ceil_div(self.inner.vocab, _LM_BLOCKS * _SUBS))

        def build(mut builder: DeviceGraphBuilder) raises {imm}:
            # ── rebuild the mutable MutAnyOrigin pointers from the hoisted addresses ──
            var hidden_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=hidden_a)
            var xn_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=xn_a)
            var qkv_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=qkv_a)
            var q_rot_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=q_rot_a)
            var attn_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=attn_a)
            var act_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=act_a)
            var skm_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=skm_a)
            var skl_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=skl_a)
            var sko_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=sko_a)
            var blk_val_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=blk_val_a)
            var blk_idx_p = UnsafePointer[Int32, origin=MutAnyOrigin](unsafe_from_address=blk_idx_a)
            var out_val_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=out_val_a)
            var out_idx_p = UnsafePointer[Int32, origin=MutAnyOrigin](unsafe_from_address=out_idx_a)
            var embed_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=embed_a)
            var final_norm_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=final_norm_a)
            var cos_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cos_a)
            var sin_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=sin_a)
            var state_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=state_a)
            var tlog_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=tlog_a)
            var p3_lm_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_lm_a)
            var p3_lm_s_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_lm_s_a)
            var p3_lm_z_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_lm_z_a)

            var rec = builder.recording_context()

            # NOTE: the host_state -> STATE feed is DELIBERATELY NOT recorded — the f32
            # arm's own A100 finding, inherited (a captured H2D copy reads a capture-time
            # snapshot, never the live contents). One eager H2D seeds the region before the
            # replay batch; NO memcpy nodes are recorded in either direction.

            # ── embed: B token ids from STATE -> hidden [B, d_model] ──
            rec.enqueue_function[_pf_embed_rows_kernel_bg](
                hidden_p, embed_p, state_p, d_model_i, B_i,
                grid_dim=_ceil_div(Int(d_model_i), _TG) * B_c, block_dim=_TG,
            )

            for layer in range(n_layers_c):
                var ln1_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=ln1s[layer])
                var ln2_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=ln2s[layer])
                var qn_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=qns[layer])
                var kn_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=kns[layer])
                var ck_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cks[layer])
                var cv_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cvs[layer])
                var qkv_w_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_qkv_w[layer])
                var qkv_s_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_qkv_s[layer])
                var qkv_z_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_qkv_z[layer])
                var o_w_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_o_w[layer])
                var o_s_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_o_s[layer])
                var o_z_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_o_z[layer])
                var gu_w_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_gu_w[layer])
                var gu_s_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_gu_s[layer])
                var gu_z_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_gu_z[layer])
                var dn_w_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_dn_w[layer])
                var dn_s_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_dn_s[layer])
                var dn_z_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_dn_z[layer])

                # 1 ── rmsnorm(input_layernorm) over all B rows — f32 kernel, no dynamic args
                rec.enqueue_function[_pf_rmsnorm_rows_kernel](
                    xn_p, hidden_p, ln1_p,
                    d_model_i, eps_c, B_i,
                    grid_dim=B_c, block_dim=_TG,
                )
                # 2 ── qkv_proj — packed3 batched ASSIGN (grid n_qkv, B baked; LEVER L6
                # `_r2` two-rows-per-block under `-D ALGENTA_P3B_R2`, grid n_qkv/2)
                @parameter
                if P3B_R2:
                    rec.enqueue_function[_batched_p3_gemv_assign_kernel_r2](
                        qkv_p, xn_p, qkv_w_p, qkv_s_p, qkv_z_p,
                        d_model_i, n_qkv_i, B_i,
                        grid_dim=Int(n_qkv_i) // 2, block_dim=_P3B_TG,
                    )
                else:
                    rec.enqueue_function[_batched_p3_gemv_assign_kernel](
                        qkv_p, xn_p, qkv_w_p, qkv_s_p, qkv_z_p,
                        d_model_i, n_qkv_i, B_i,
                        grid_dim=Int(n_qkv_i), block_dim=_P3B_TG,
                    )
                # 3 ── batched KV producer: poss from STATE[B+seq]
                rec.enqueue_function[_native_kv_producer_batched_f32_kernel_bg](
                    q_rot_p, ck_p, cv_p,
                    qkv_p, qn_p, kn_p,
                    cos_p, sin_p,
                    state_p, B_i, kv_stride_i,
                    h_q_i, h_kv_i, d_head_i, eps_c,
                    Int64(1),  # qk_norm: Qwen3-family only, always on
                    grid_dim=(Int(h_q_i) + Int(h_kv_i)) * B_c, block_dim=Int(d_head_i),
                )
                # 4 ── batched attention PARTIAL: nkeys from STATE[2B+b] — the flash-style
                # warp-per-(seq,head,split) twin (same partial layout, zero barriers)
                rec.enqueue_function[_splitk_partial_batched_flash_kernel_bg](
                    skm_p, skl_p, sko_p, q_rot_p,
                    ck_p, cv_p,
                    state_p, B_i, kv_stride_i,
                    Int64(CUDA_BATCH_N_SPLITS), h_q_i, h_kv_i, d_head_i, scale_c,
                    grid_dim=_ceil_div(
                        B_c * Int(h_q_i) * CUDA_BATCH_N_SPLITS,
                        _DECODE_FLASH_WARPS_PER_BLOCK,
                    ),
                    block_dim=_DECODE_FLASH_NTHREADS,
                )
                # 5 ── batched attention MERGE — f32 forge kernel, no dynamic args
                rec.enqueue_function[_native_kv_decode_splitk_merge_batched_f32_kernel](
                    attn_p, skm_p, skl_p, sko_p,
                    Int64(CUDA_BATCH_N_SPLITS), h_q_i, d_head_i,
                    grid_dim=B_c * Int(h_q_i), block_dim=Int(d_head_i),
                )
                # 6 ── o_proj ACCUM into the residual stream — packed3 batched (LEVER L6)
                @parameter
                if P3B_R2:
                    rec.enqueue_function[_batched_p3_gemv_accum_kernel_r2](
                        hidden_p, attn_p, o_w_p, o_s_p, o_z_p,
                        Int64(n_q), d_model_i, B_i,
                        grid_dim=Int(d_model_i) // 2, block_dim=_P3B_TG,
                    )
                else:
                    rec.enqueue_function[_batched_p3_gemv_accum_kernel](
                        hidden_p, attn_p, o_w_p, o_s_p, o_z_p,
                        Int64(n_q), d_model_i, B_i,
                        grid_dim=Int(d_model_i), block_dim=_P3B_TG,
                    )
                # 7 ── rmsnorm(post_attention_layernorm) over all B rows
                rec.enqueue_function[_pf_rmsnorm_rows_kernel](
                    xn_p, hidden_p, ln2_p,
                    d_model_i, eps_c, B_i,
                    grid_dim=B_c, block_dim=_TG,
                )
                # 8 ── gate/up + SwiGLU — packed3 batched
                rec.enqueue_function[_batched_p3_swiglu_kernel](
                    act_p, xn_p, gu_w_p, gu_s_p, gu_z_p,
                    d_model_i, d_ff_i, B_i,
                    grid_dim=Int(d_ff_i), block_dim=_P3B_TG,
                )
                # 9 ── down_proj ACCUM into the residual stream — packed3 batched (LEVER L6)
                @parameter
                if P3B_R2:
                    rec.enqueue_function[_batched_p3_gemv_accum_kernel_r2](
                        hidden_p, act_p, dn_w_p, dn_s_p, dn_z_p,
                        d_ff_i, d_model_i, B_i,
                        grid_dim=Int(d_model_i) // 2, block_dim=_P3B_TG,
                    )
                else:
                    rec.enqueue_function[_batched_p3_gemv_accum_kernel](
                        hidden_p, act_p, dn_w_p, dn_s_p, dn_z_p,
                        d_ff_i, d_model_i, B_i,
                        grid_dim=Int(d_model_i), block_dim=_P3B_TG,
                    )

            # ── tail: final rmsnorm + packed3 batched lm_head + B-row argmax reduce ──
            rec.enqueue_function[_pf_rmsnorm_rows_kernel](
                xn_p, hidden_p, final_norm_p,
                d_model_i, eps_c, B_i,
                grid_dim=B_c, block_dim=_TG,
            )
            rec.enqueue_function[_batched_lmhead_argmax_kernel_p3](
                blk_val_p, blk_idx_p, xn_p,
                p3_lm_p, p3_lm_s_p, p3_lm_z_p,
                B_i, d_model_i, vocab_i, n_iters_i,
                grid_dim=_LM_BLOCKS, block_dim=_TG,
            )
            rec.enqueue_function[_batched_argmax_reduce_kernel_simd](
                out_val_p, out_idx_p,
                blk_val_p, blk_idx_p, Int64(_LM_BLOCKS),
                grid_dim=B_c, block_dim=_TG,
            )
            # ── the device-side generation chain (the f32 arm's kernel, unchanged): log
            #    the B tokens, feed them forward, advance poss/nkeys + the step counter ──
            rec.enqueue_function[_graph_advance_batched_kernel](
                state_p, out_idx_p, tlog_p, B_i,
                grid_dim=1, block_dim=B_c,
            )

        # LEVER L7 record: capture STAYS on the base context. graphsync_probe Q3/Q3b
        # (round 3, A100) measured a graph captured against a select_stream view computes
        # garbage (200/200 rounds wrong, fence or no fence; a 1-node side-captured graph
        # works — the multi-node dependency chain tears), and the l7s2 selftest confirmed
        # it in-driver (gate 1 13/16 wrong with no lanes involved). The replay stream is
        # therefore NOT relocatable on this toolchain; the co-residency fix lives in the
        # chunk horizon / replay pacing, not the capture stream.
        self.arms_graph[idx] = DeviceGraph.create(self.inner.ctx, build)

    def seed_and_run_batched_graph(
        mut self, ref first_tokens: List[Int], ref start_poss: List[Int], n_steps: Int,
    ) raises -> Int:
        """The f32 graph arm's own contract, restated for the p3 arm: run `n_steps` batched
        p3 decode steps as `n_steps` back-to-back replays of the ONE captured graph for
        B = len(first_tokens), zero per-step host dispatch; the host seeds the STATE region
        once (eager H2D), enqueues every replay, synchronizes once, and pulls the token log
        back eagerly. Tokens are read afterwards with `graph_batched_token(seq, step)`."""

        @parameter
        if not CUDA_SESSION_BUILD:
            return RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT
        else:
            var B = len(first_tokens)
            if len(start_poss) != B or B < 1 or B > _CUDA_BATCH_DECODE_MAX_SEQS:
                return RESIDENT_ERR_UPLOAD_LENGTH
            if n_steps < 1:
                return RESIDENT_ERR_UPLOAD_LENGTH
            if B * n_steps > _P3G_LOG_HEAD_CAP:
                return RESIDENT_ERR_UPLOAD_LENGTH
            for b in range(B):
                if start_poss[b] < 0 or start_poss[b] + n_steps > self.inner.max_ctx:
                    return RESIDENT_ERR_CONTEXT_FULL
                if first_tokens[b] < 0 or first_tokens[b] >= self.inner.vocab:
                    return RESIDENT_ERR_UPLOAD_LENGTH

            var idx = self._ensure_arm(B)
            self.last_B = B

            # Seed the region once: B tokens, B positions, B key counts (invariant
            # nkeys = poss + 1, preserved by the advance kernel), step counter 0.
            var sh = self.arms_host_state[idx].unsafe_ptr()
            for b in range(B):
                sh[b] = Int64(first_tokens[b])
                sh[B + b] = Int64(start_poss[b])
                sh[2 * B + b] = Int64(start_poss[b] + 1)
            sh[3 * B] = Int64(0)

            # The feed: ONE eager H2D copy on the context stream, ordered before the
            # replays (the round-2 shape — round 3 REVERTED a dedicated-replay-stream
            # routing here: capture is not relocatable on this toolchain, and a seed copy
            # on a stream the replay does not order against would re-open the stale-seed
            # race the L5 sync closed).
            self.inner.ctx.enqueue_copy(self.arms_state[idx], self.arms_host_state[idx])
            # LEVER L5: drain the seed copy before the replays launch. One context sync
            # per CHUNK (not per step) makes the dependency structural.
            self.inner.ctx.synchronize()

            for _ in range(n_steps):
                self.arms_graph[idx].value().replay()
                @parameter
                if P3G_PSS:
                    # LEVER L7 scalpel: serialize consecutive replays on the host. Round-3
                    # measurement: changes nothing against the corruption (which was the
                    # driver's move_slot_kv address bug, not replay pacing) — kept as the
                    # per-step-sync cost reference.
                    self.inner.ctx.synchronize()

            # One synchronize for the whole generation, then the NARROW log readback:
            # head-stage the first B*n_steps entries (the only ones the reader touches) and
            # pull just the head — the full-log D2H (1.2 MB) was the seam's dominant cost.
            self.inner.ctx.synchronize()
            self.inner.ctx.enqueue_function[_p3g_log_head_copy_kernel](
                self.log_head.unsafe_ptr(), self.graph_token_log.unsafe_ptr(),
                Int64(B * n_steps),
                grid_dim=_ceil_div(B * n_steps, 256), block_dim=256,
            )
            self.inner.ctx.synchronize()
            self.inner.ctx.enqueue_copy(self.host_log_head, self.log_head)
            self.inner.ctx.synchronize()
            @parameter
            if P3G_DBG_TRACE:
                var line = String("CHUNK B=") + String(B) + " K=" + String(n_steps)
                line += " | seed tokens=["
                for b in range(B):
                    if b > 0:
                        line += ","
                    line += String(first_tokens[b])
                line += "] poss=["
                for b in range(B):
                    if b > 0:
                        line += ","
                    line += String(start_poss[b])
                line += "] | logged=["
                for s in range(n_steps):
                    if s > 0:
                        line += ";"
                    for b in range(B):
                        if b > 0:
                            line += ","
                        line += String(self.graph_batched_token(b, s))
                line += "]"
                # device-side STATE verification: after the chunk, the region must hold
                # tokens = last logged step, poss = seed + K, nkeys = poss + 1, step = K —
                # any mismatch proves the seed copy or the advance kernel tore
                var hchk = self.inner.ctx.enqueue_create_host_buffer[DType.int64](3 * B + 1)
                self.inner.ctx.enqueue_copy(hchk, self.arms_state[idx])
                self.inner.ctx.synchronize()
                line += " | post-state tokens=["
                for b in range(B):
                    if b > 0:
                        line += ","
                    line += String(hchk[b])
                line += "] poss=["
                for b in range(B):
                    if b > 0:
                        line += ","
                    line += String(hchk[B + b])
                line += "] step=" + String(hchk[3 * B])
                print(line)
            return RESIDENT_OK

    def graph_batched_token(self, seq: Int, step: Int) -> Int:
        """The token sequence `seq` generated at decode step `step` of the last
        `seed_and_run_batched_graph` call (B = that call's batch size) — read from the
        NARROW log head this arm now pulls instead of the full token log."""
        return Int(self.host_log_head.unsafe_ptr()[step * self.last_B + seq])
