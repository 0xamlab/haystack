"""residentk.session_cuda_batched_graph — W2 of the campaign gap inventory: the CAPTURED-GRAPH
arm of the W1 continuous-batching (B-sequence) decode session. One `DeviceGraph` per batch size
B captures the ENTIRE W1 step chain — 1 embed + 9 dispatches per layer + lm_head + reduce +
the device-side advance kernel — and N back-to-back replays run N whole B-token steps with ZERO
per-step host dispatch, mirroring how the single-stream graph arm (`residentk.session_cuda`'s
`seed_and_run_graph`) took single-stream decode 71 -> 330 tok/s on the A100. Additive — the W1
session (`residentk.session_cuda_batched`), every W1 kernel, and the single-stream graph arm are
byte-unmodified. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/qwen3_batched_graph_cuda.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/qwen3_batched_graph_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Every entry point is private, and every launch is gated — the same two
defences `residentk.session_cuda`'s module docstring documents: nothing here is public, so it
never enters the runtime contract; and every function that issues an `enqueue_function` opens
with `@parameter if not CUDA_SESSION_BUILD: return <shader_toolchain_absent>`, so with either
`-D ALGENTA_GPU` or `-D ALGENTA_CUDA` unset the launches are removed BEFORE shader codegen runs.
The constructor carries no gate (a constructor must initialise every field) and is protected
structurally: the struct is constructed ONLY from inside a `@parameter if CUDA_SESSION_BUILD`
branch, exactly the protection `_CudaResidentQwen3Batched.__init__` has.

COMPOSITION, NOT COPY
---------------------
`_CudaResidentQwen3BatchedGraph` HOLDS a W1 `_CudaResidentQwen3Batched` and delegates
upload/seal/prefill and the per-dispatch step path to it — the graph arm replays against the
SAME resident weights, RoPE tables, per-sequence KV slots and scratch buffers the W1 session
owns, so the two arms can never drift in state, and the driver's graph-vs-per-dispatch token
diff runs on one set of weights. The ONLY state this module adds is graph-arm state: one STATE
buffer region + pinned twin per captured B, the shared token-log buffer, and one `DeviceGraph`
per B.

THE CAPTURED STEP CHAIN (per replay; `_bg` = a `residentk.kernels_batched_cuda_graph` twin
reading its per-step scalars from the STATE buffer, everything else the W1 kernel byte-unmodified):

    _pf_embed_rows_kernel_bg                 grid ceil(d_model/_TG)*B   token ids: state[0..B)
    per layer:
      _pf_rmsnorm_rows_kernel                grid B
      _pf_gemm_assign_kernel_v2              qkv GEMM (ASSIGN)
      _native_kv_producer_batched_f32_kernel_bg  grid (h_q+h_kv)*B      poss: state[B..2B)
      _native_kv_decode_splitk_partial_batched_f32_kernel_bg
                                             grid B*h_q*16              nkeys: state[2B..3B)
      _native_kv_decode_splitk_merge_batched_f32_kernel   grid B*h_q
      _pf_gemm_accum_kernel_v2               o_proj (ACCUM residual)
      _pf_rmsnorm_rows_kernel                grid B
      _pf_gemm_swiglu_kernel_v2              gate/up + SwiGLU
      _pf_gemm_accum_kernel_v2               down_proj (ACCUM residual)
    _pf_rmsnorm_rows_kernel                  grid B (final norm)
    _batched_lmhead_argmax_kernel_f32        grid _LM_BLOCKS
    _batched_argmax_reduce_kernel_simd       grid B
    _graph_advance_batched_kernel            grid 1 / block B — logs the B tokens to the
                                             token-log device buffer, feeds them back as the
                                             next embed inputs, advances poss/nkeys, and bumps
                                             the region's step counter

= 1 + n_layers*9 + 4 kernel nodes per replay (258 at Qwen3-0.6B), captured ONCE per B.

THE PROVEN CAPTURE RULES (paid for by the single-stream graph arm on the A100, restated because
this module follows them to the letter):
  (a) KERNELS-ONLY capture via `builder.recording_context()`. NO memcpy nodes are recorded in
      either direction — recorded copies read capture-time snapshots and land in graph-owned
      staging, so ALL H2D/D2H copies happen EAGERLY around the replay batch.
  (b) Per-step dynamic scalars (B token ids, B positions, B key counts) come from the device
      STATE buffer the `_bg` twins read; every other launch argument is a session-resident
      address or a constant, valid for the session's life.
  (c) ONE eager H2D of the pinned host_state region seeds the STATE region before each replay
      batch.
  (d) `_graph_advance_batched_kernel` does the device-side chain so N replays run N steps; the
      host synchronizes ONCE after the last replay and pulls the token log back eagerly.

THE STATE BUFFER LAYOUT (all Int64, one region per captured B; the documented +1 deviation):
    [0, B)    next token ids        (embed twin)
    [B, 2B)   poss                  (kvprod twin)
    [2B, 3B)  nkeys                 (partial twin; seed invariant nkeys = poss + 1)
    [3B]      replay-step counter   — the ONE slot beyond the 3*B design brief, needed so the
              advance kernel can write token_log[step*B + b] without a per-sequence start-pos
              array on device; it needs no seed bookkeeping because every seed resets it to 0.

THE POINTER HOISTING DISCIPLINE is `_build_decode_graph`'s own (paid in three build failures,
recorded there): the build callback is an `{imm}` closure, so every device address is taken in
the method scope where `self` is mut, kept as a plain Int, and rebuilt inside the capture as a
mutable MutAnyOrigin pointer via `unsafe_from_address`. Session buffers are resident for the
session's life, so the addresses are stable for every replay.
"""

from max.gpu.host import (
    DeviceBuffer,
    DeviceGraph,
    DeviceGraphBuilder,
    HostBuffer,
)
from std.collections import Optional
from std.origin import MutAnyOrigin
from residentk.contract import (
    RESIDENT_ERR_CONTEXT_FULL,
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
from residentk.kernels_batched_cuda_graph import (
    _pf_embed_rows_kernel_bg,
    _native_kv_producer_batched_f32_kernel_bg,
    _native_kv_decode_splitk_partial_batched_f32_kernel_bg,
    _graph_advance_batched_kernel,
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


@fieldwise_init
struct _CudaResidentQwen3BatchedGraph(Movable):
    """The W1 batched session PLUS its captured-graph arm. Holds ONE W1 session (weights, RoPE
    tables, per-sequence KV slots, prefill, the per-dispatch step path — all delegated) and adds
    per-B graph arms: one STATE region + pinned twin (3*B+1 Int64 slots — the +1 is the replay
    step counter, see the module docstring), one shared token-log device buffer
    (`_CUDA_BATCH_DECODE_MAX_SEQS * max_ctx` Int64, enough for B_MAX sequences x max_ctx steps),
    and one lazily captured `DeviceGraph` per B actually used.

    Arms live in four parallel lists indexed together (B, STATE buffer, pinned twin, graph).
    `_CudaResidentQwen3Batched` is Movable-not-Copyable, so this struct is Movable only, for
    the same reason the W1 session's own docstring gives.
    """

    var inner: _CudaResidentQwen3Batched
    var graph_token_log: DeviceBuffer[DType.int64]
    var host_graph_token_log: HostBuffer[DType.int64]
    var arms_B: List[Int]
    var arms_state: List[DeviceBuffer[DType.int64]]
    var arms_host_state: List[HostBuffer[DType.int64]]
    var arms_graph: List[Optional[DeviceGraph]]
    var last_B: Int

    def __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
        """Open the W1 session (the ONLY `DeviceContext` in this struct) and allocate the
        graph-arm additions ONCE. Called only from inside a `@parameter if CUDA_SESSION_BUILD`
        branch — see the module docstring for why a constructor cannot carry the gate itself.
        The caller must have validated the shape with `residentk_dims_check` first, exactly as
        the W1 session's own constructor requires."""
        self.inner = _CudaResidentQwen3Batched(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab, max_ctx, eps, scale
        )
        var log_elems = _CUDA_BATCH_DECODE_MAX_SEQS * max_ctx
        self.graph_token_log = self.inner.ctx.enqueue_create_buffer[DType.int64](log_elems)
        self.host_graph_token_log = self.inner.ctx.enqueue_create_host_buffer[DType.int64](
            log_elems
        )
        self.arms_B = List[Int]()
        self.arms_state = List[DeviceBuffer[DType.int64]]()
        self.arms_host_state = List[HostBuffer[DType.int64]]()
        self.arms_graph = List[Optional[DeviceGraph]]()
        self.last_B = 0

    # ═══════════════════════════════ delegation to the W1 session ═══════════════════════════

    def device_name(self) raises -> String:
        return self.inner.device_name()

    def max_seqs(self) -> Int:
        return self.inner.max_seqs()

    def batched_dispatch_count(self, B: Int) -> Int:
        """The W1 per-dispatch plan size this graph arm replaces: `1 + n_layers*9 + 3`."""
        return self.inner.batched_dispatch_count(B)

    def batched_graph_node_count(self, B: Int) -> Int:
        """Kernel nodes in ONE captured replay: the W1 plan plus the device-side advance
        kernel. B does not change the count — it changes each node's grid, which is baked at
        capture."""
        return self.inner.batched_dispatch_count(B) + 1

    def upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        return self.inner.upload_globals(embed, final_norm, cos_t, sin_t, n_pos)

    def upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        return self.inner.upload_layer(
            layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wgate, wup, wdown
        )

    def seal(mut self) raises -> Int:
        return self.inner.seal()

    def prefill_batched(mut self, ref prompts: List[List[Int]]) raises -> List[Int]:
        return self.inner.prefill_batched(prompts)

    def step_batched_tokens(
        mut self, ref token_ids: List[Int], ref poss: List[Int],
    ) raises -> List[Int]:
        return self.inner.step_batched_tokens(token_ids, poss)

    def seed_and_run_batched(
        mut self, ref first_tokens: List[Int], ref start_poss: List[Int], n_steps: Int,
    ) raises -> Int:
        return self.inner.seed_and_run_batched(first_tokens, start_poss, n_steps)

    def batched_token(self, seq: Int, step: Int) -> Int:
        return self.inner.batched_token(seq, step)

    # ═══════════════════════════════ the captured-graph arm ═══════════════════════════════

    def _ensure_arm(mut self, B: Int) raises -> Int:
        """Find-or-create the graph arm for batch size B; returns its index in the parallel
        lists. Creation allocates the STATE region + pinned twin on the W1 session's context,
        then captures the step chain into a `DeviceGraph` — lazily, because capture needs every
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
        self._build_batched_graph(idx, B)
        return idx

    def _build_batched_graph(mut self, idx: Int, B: Int) raises:
        """Capture the ENTIRE W1 batched step chain for batch size B into ONE `DeviceGraph` —
        literally the W1 `step_batched_tokens` dispatch plan replayed against the recording
        context, with the three position-dependent launches swapped to their `_bg` twins
        reading the STATE region, and `_graph_advance_batched_kernel` appended as the
        device-side generation chain.

        Pointer hoisting discipline: `_build_decode_graph`'s own (see the module docstring).
        """
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
        for layer in range(self.inner.n_layers):
            ref lw = self.inner.layers[layer]
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

        var n_layers_c = self.inner.n_layers
        var B_c = B
        var d_model_i = Int64(self.inner.d_model)
        var n_q = self.inner.h_q * self.inner.d_head
        var n_kv = self.inner.h_kv * self.inner.d_head
        var n_qkv_i = Int64(n_q + 2 * n_kv)
        var n_q_i = Int64(n_q)
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

            var rec = builder.recording_context()

            # NOTE: the host_state -> STATE region feed is DELIBERATELY NOT recorded here —
            # the single-stream arm's A100 finding, inherited: a host->device copy captured
            # into the graph reads a capture-time snapshot of the host buffer, never the live
            # contents. `seed_and_run_batched_graph` feeds the region with ONE eager H2D
            # before the replay batch. NO memcpy nodes are recorded in either direction.

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
                var wqkv_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=w_qkvs[layer])
                var wo_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=w_os[layer])
                var wgu_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=w_gus[layer])
                var wd_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=w_downs[layer])
                var ck_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cks[layer])
                var cv_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cvs[layer])
                # 1 ── rmsnorm(input_layernorm) over all B rows — W1 kernel, no dynamic args
                rec.enqueue_function[_pf_rmsnorm_rows_kernel](
                    xn_p, hidden_p, ln1_p,
                    d_model_i, eps_c, B_i,
                    grid_dim=B_c, block_dim=_TG,
                )
                # 2 ── qkv_proj GEMM (ASSIGN, v2) — W1 kernel, no dynamic args
                rec.enqueue_function[_pf_gemm_assign_kernel_v2](
                    qkv_p, xn_p, wqkv_p,
                    B_i, d_model_i, n_qkv_i,
                    grid_dim=_ceil_div(B_c, _G2_BM) * _ceil_div(Int(n_qkv_i), _G2_BN),
                    block_dim=_G2_NTHREADS,
                )
                # 3 ── batched KV producer: poss from STATE[B+seq]
                rec.enqueue_function[_native_kv_producer_batched_f32_kernel_bg](
                    q_rot_p, ck_p, cv_p,
                    qkv_p, qn_p, kn_p,
                    cos_p, sin_p,
                    state_p, B_i, kv_stride_i,
                    h_q_i, h_kv_i, d_head_i, eps_c,
                    Int64(1),  # qk_norm: Qwen3-family only, per-head QK-norm always on
                    grid_dim=(Int(h_q_i) + Int(h_kv_i)) * B_c, block_dim=Int(d_head_i),
                )
                # 4 ── batched attention PARTIAL: nkeys from STATE[2B+b]
                rec.enqueue_function[_native_kv_decode_splitk_partial_batched_f32_kernel_bg](
                    skm_p, skl_p, sko_p, q_rot_p,
                    ck_p, cv_p,
                    state_p, B_i, kv_stride_i,
                    Int64(CUDA_BATCH_N_SPLITS), h_q_i, h_kv_i, d_head_i, scale_c,
                    grid_dim=B_c * Int(h_q_i) * CUDA_BATCH_N_SPLITS, block_dim=Int(d_head_i),
                )
                # 5 ── batched attention MERGE — W1 forge kernel, no dynamic args
                rec.enqueue_function[_native_kv_decode_splitk_merge_batched_f32_kernel](
                    attn_p, skm_p, skl_p, sko_p,
                    Int64(CUDA_BATCH_N_SPLITS), h_q_i, d_head_i,
                    grid_dim=B_c * Int(h_q_i), block_dim=Int(d_head_i),
                )
                # 6 ── o_proj GEMM ACCUMULATED into the residual stream (v2)
                rec.enqueue_function[_pf_gemm_accum_kernel_v2](
                    hidden_p, attn_p, wo_p,
                    B_i, n_q_i, d_model_i,
                    grid_dim=_ceil_div(B_c, _G2_BM) * _ceil_div(Int(d_model_i), _G2_BN),
                    block_dim=_G2_NTHREADS,
                )
                # 7 ── rmsnorm(post_attention_layernorm) over all B rows
                rec.enqueue_function[_pf_rmsnorm_rows_kernel](
                    xn_p, hidden_p, ln2_p,
                    d_model_i, eps_c, B_i,
                    grid_dim=B_c, block_dim=_TG,
                )
                # 8 ── gate/up + SwiGLU, one tiled GEMM pair (v2)
                rec.enqueue_function[_pf_gemm_swiglu_kernel_v2](
                    act_p, xn_p, wgu_p,
                    B_i, d_model_i, d_ff_i,
                    grid_dim=_ceil_div(B_c, _G2_BM) * _ceil_div(Int(d_ff_i), _G2_BN),
                    block_dim=_G2_NTHREADS,
                )
                # 9 ── down_proj GEMM ACCUMULATED into the residual stream (v2)
                rec.enqueue_function[_pf_gemm_accum_kernel_v2](
                    hidden_p, act_p, wd_p,
                    B_i, d_ff_i, d_model_i,
                    grid_dim=_ceil_div(B_c, _G2_BM) * _ceil_div(Int(d_model_i), _G2_BN),
                    block_dim=_G2_NTHREADS,
                )

            # ── tail: final rmsnorm (B rows) + batched lm_head + B-row argmax reduce ──
            rec.enqueue_function[_pf_rmsnorm_rows_kernel](
                xn_p, hidden_p, final_norm_p,
                d_model_i, eps_c, B_i,
                grid_dim=B_c, block_dim=_TG,
            )
            rec.enqueue_function[_batched_lmhead_argmax_kernel_f32](
                blk_val_p, blk_idx_p, xn_p, embed_p,
                B_i, d_model_i, vocab_i, n_iters_i,
                grid_dim=_LM_BLOCKS, block_dim=_TG,
            )
            rec.enqueue_function[_batched_argmax_reduce_kernel_simd](
                out_val_p, out_idx_p,
                blk_val_p, blk_idx_p, Int64(_LM_BLOCKS),
                grid_dim=B_c, block_dim=_TG,
            )
            # ── the device-side generation chain: log the B tokens, feed them forward,
            #    advance poss/nkeys + the step counter — so N back-to-back replays run N
            #    whole B-token steps with zero per-step host traffic ──
            rec.enqueue_function[_graph_advance_batched_kernel](
                state_p, out_idx_p, tlog_p, B_i,
                grid_dim=1, block_dim=B_c,
            )

        self.arms_graph[idx] = DeviceGraph.create(self.inner.ctx, build)

    def seed_and_run_batched_graph(
        mut self, ref first_tokens: List[Int], ref start_poss: List[Int], n_steps: Int,
    ) raises -> Int:
        """Run `n_steps` batched decode steps as `n_steps` back-to-back replays of the ONE
        captured graph for B = len(first_tokens), with ZERO per-step host dispatch — the
        device-side chain (`_graph_advance_batched_kernel`, the graph's last node) logs each
        step's B tokens to the token-log device buffer at offset `step*B`, feeds them back as
        the next embed inputs, and advances poss/nkeys; replays run in stream order, so replay
        k consumes exactly what replay k-1 advanced. The host seeds the STATE region once
        (eager H2D), enqueues every replay, synchronizes once, and pulls the token log back
        eagerly (a recorded D2H copy would land in graph-owned staging, never the host buffer).

        Same state contract as the W1 `seed_and_run_batched`: returns a RESIDENT_* status, and
        the token sequence `seq` generated at decode step `step` (position
        `start_poss[seq] + step`) is read afterwards with `graph_batched_token(seq, step)`.
        The next position after this call is `start_poss[b] + n_steps`, caller-owned, exactly
        as with the W1 arm."""

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
                if start_poss[b] < 0 or start_poss[b] + n_steps > self.inner.max_ctx:
                    return RESIDENT_ERR_CONTEXT_FULL
                if first_tokens[b] < 0 or first_tokens[b] >= self.inner.vocab:
                    return RESIDENT_ERR_UPLOAD_LENGTH

            var idx = self._ensure_arm(B)
            self.last_B = B

            # Seed the region once: B tokens, B positions, B key counts (invariant
            # nkeys = poss + 1, preserved by the advance kernel), step counter 0.
            # HostBuffer is host-visible already — write through its pointer directly.
            var sh = self.arms_host_state[idx].unsafe_ptr()
            for b in range(B):
                sh[b] = Int64(first_tokens[b])
                sh[B + b] = Int64(start_poss[b])
                sh[2 * B + b] = Int64(start_poss[b] + 1)
            sh[3 * B] = Int64(0)

            # The feed: ONE eager H2D copy on the context stream, ordered before the replays.
            self.inner.ctx.enqueue_copy(self.arms_state[idx], self.arms_host_state[idx])

            for _ in range(n_steps):
                self.arms_graph[idx].value().replay()

            # One synchronize for the whole generation, then the log readback (eager — a
            # recorded copy would land in graph-owned staging, never this host buffer).
            self.inner.ctx.synchronize()
            self.inner.ctx.enqueue_copy(self.host_graph_token_log, self.graph_token_log)
            self.inner.ctx.synchronize()
            return RESIDENT_OK

    def graph_batched_token(self, seq: Int, step: Int) -> Int:
        """The token sequence `seq` generated at decode step `step` of the last
        `seed_and_run_batched_graph` call, read from the host-side token log
        (`token_log[step * B + seq]`, B = that call's batch size)."""
        return Int(self.host_graph_token_log.unsafe_ptr()[step * self.last_B + seq])
