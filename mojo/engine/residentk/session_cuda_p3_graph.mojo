"""
residentk.session_cuda_p3_graph — the CAPTURED-GRAPH arm of the packed3 decode session:
`_CudaResidentQwen3P3Graph` COMPOSES `residentk.session_cuda_p3._CudaResidentQwen3P3` and
captures its whole per-token decode dispatch plan into ONE `DeviceGraph`, so N back-to-back
replays run N whole packed3 decode steps with ZERO per-step host dispatch — the same removal
of per-token host traffic that took the f32 single-stream arm 71 -> 330 tok/s on the A100
(`residentk.session_cuda`'s `seed_and_run_graph`), applied to the arm whose per-token weight
traffic is ~1.19 GB instead of f32's 2.62 GB. Additive — the packed3 session, every packed3
kernel, the f32 session and the f32 graph arm are byte-unmodified. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32, uint8-packed
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Every entry point is private and every launch compile-time gated — the
same two defences `residentk.session_cuda`'s module docstring documents:

1. **Private.** Nothing in this file is public, so `apps/runtime/mojo_inventory.py` skips it,
   it never enters the runtime contract, and the generated dispatch never imports it. Today
   only `benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo` reaches it.
2. **Compile-time gated.** Every function here that issues an `enqueue_function` or replays a
   graph opens with `@parameter if not CUDA_SESSION_BUILD: return <shader_toolchain_absent>` —
   the SAME gate comptime `residentk.session_cuda` defines (`-D ALGENTA_GPU` conjuncted with
   `-D ALGENTA_CUDA`), imported, not re-decided. The constructor carries no gate and is instead
   protected structurally: the struct is constructed ONLY from inside a `@parameter if
   CUDA_SESSION_BUILD` branch.

COMPOSITION, NOT COPY
---------------------
`_CudaResidentQwen3P3Graph` HOLDS a `_CudaResidentQwen3P3` and delegates upload/seal/prefill
and the per-dispatch `step_p3` path to it — the graph arm replays against the SAME resident
weights (f32 AND packed3), RoPE tables, f32 KV cache and scratch buffers the packed3 session
owns, so the two arms can never drift in state, and the driver's graph-vs-per-dispatch token
diff runs on one set of weights. The ONLY state this module adds is graph-arm state: the
3-element STATE buffer + pinned twin, the token-log buffer + pinned twin, the split-K
attention scratch trio, and one lazily captured `DeviceGraph`.

WHY THE GRAPH ARM SWAPS ATTENTION TO SPLIT-K
---------------------------------------------
`step_p3`'s per-dispatch chain attends through the one-piece `_sdpa_kernel`; the captured
chain attends through the split-K flash-decoding pair (`_splitk_partial_kernel_simd_g` +
`_splitk_merge_kernel_simd`) exactly as the f32 graph arm does: inside a captured graph the
extra launch costs nothing (replay amortizes it), and the occupancy argument stands at every
depth — the unsplit kernel recruits exactly `h_q` = 16 blocks on a 108-SM A100 no matter how
deep the cache grows, splitting recruits `h_q * CUDA_GRAPH_N_SPLITS`. Both attention paths
read the SAME f32 KV cache the packed3 session keeps, so the swap is weight-format-agnostic.

THE CAPTURED STEP CHAIN (per replay; `_g` = a `residentk.kernels_cuda_graph` twin reading its
per-step scalar from the STATE buffer; the packed3 roles are the kernels byte-unmodified from
`residentk.session_cuda_p3` / `residentk.kernels_packed3` — ALL of them are STATELESS per step,
so they are captured as-is, no twins needed):

    _embed_row_kernel_g                      grid ceil(d_model/_TG)   token id: state[0]
    per layer:
      _norm_gemv_kernel_p3                   grid ceil(n_qkv/_SUBS)   packed3 qkv
      _qk_rope_write_kernel_g                grid h_q + h_kv          pos: state[1]
      _splitk_partial_kernel_simd_g          grid h_q*32              n_keys: state[2]
      _splitk_merge_kernel_simd              grid h_q
      _packed3_gemv_accum_kernel             grid ceil(d_model/_SUBS) o_proj + residual
      _norm_gemv2_swiglu_kernel_p3           grid ceil(d_ff/_SUBS)    packed3 gate/up + SwiGLU
      _packed3_gemv_accum_kernel             grid ceil(d_model/_SUBS) down_proj + residual
    _lmhead_argmax_kernel_p3                 grid _LM_BLOCKS          packed3 lm_head + argmax
    _argmax_reduce_kernel                    grid 1
    _graph_advance_kernel                    grid 1 / block 1 — logs the token to the token-log
                                             device buffer, feeds it back as the next embed
                                             input, advances pos/n_keys

= 1 + n_layers*7 + 3 kernel nodes per replay (200 at Qwen3-0.6B's 28 layers) vs the
per-dispatch plan's `residentk_dispatch_budget(n_layers)` = 1 + n_layers*6 + 2 = 171 enqueues
per token (the deltas: sdpa -> split-K pair adds one node per layer, plus the advance kernel).

THE packed3 ROLES dispatch through a kernel-generation switch, `P3_GRAPH_V2_KERNELS` (module
top): the default build routes them through the `_v2` twins (Int32 word-view shift/AND
unpack, bit-identical math — see `residentk.session_cuda_p3`'s "THE v2 TWINS"), and
`-D ALGENTA_P3_V1` routes them through the #800/#801 byte-view bodies, so one source tree
yields both A/B binaries. The per-dispatch arm stays on v1 either way, which is what makes
the gate driver's G1 diff a graph-variant-vs-original token-identity check.

THE PROVEN CAPTURE RULES (paid for by the f32 single-stream graph arm on the A100, restated
because this module follows them to the letter):
  (a) KERNELS-ONLY capture via `builder.recording_context()`. NO memcpy nodes are recorded in
      either direction — recorded copies read capture-time snapshots and land in graph-owned
      staging, so ALL H2D/D2H copies happen EAGERLY around the replay batch.
  (b) Per-step dynamic scalars (token_id, pos, n_keys) come from the device STATE buffer the
      three `_g` twins read; every other launch argument is a session-resident address or a
      constant, valid for the session's life. The three `_g` twins are weight-format-agnostic
      and REUSED from `residentk.kernels_cuda_graph` byte-unmodified: embed gathers from the
      f32 embed table the packed3 session keeps, qk_rope/splitk read the f32 KV cache it keeps.
  (c) ONE eager H2D of the pinned host_state seeds the STATE buffer before the replay batch.
  (d) `_graph_advance_kernel` does the device-side chain so N replays run N steps; the host
      synchronizes ONCE after the last replay and pulls the token log back eagerly.

THE POINTER HOISTING DISCIPLINE is `_build_decode_graph`'s own (paid in three build failures,
recorded there): the build callback is an `{imm}` closure, so every device address is taken in
the method scope where `self` is mut, kept as a plain Int, and rebuilt inside the capture as a
mutable MutAnyOrigin pointer via `unsafe_from_address`. Session buffers are resident for the
session's life, so the addresses are stable for every replay.

Build / compile verification (macOS build host, NVPTX ships in the toolchain, no GPU needed)
---------------------------------------------------------------------------------------------
The module compiles THROUGH the gate driver — the campaign's compile-verification form, which
also guarantees the captured chain's kernels are actually LOWERED:

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \\
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/qwen3_p3_graph_cuda.mojo \\
        -o /tmp/qwen3_p3_graph_cuda_sm80
(same with `sm_89` for the L4/4090 lane).
"""

from max.gpu.host import (
    DeviceBuffer,
    DeviceGraph,
    DeviceGraphBuilder,
    HostBuffer,
)
from std.collections import Optional
from std.origin import MutAnyOrigin
from std.sys import is_defined
from residentk.contract import (
    RESIDENT_ERR_CONTEXT_FULL,
    RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT,
    RESIDENT_ERR_UPLOAD_LENGTH,
    RESIDENT_OK,
    residentk_dispatch_budget,
)
from residentk.kernels import (
    _TG,
    _SUBS,
    _argmax_reduce_kernel,
    _splitk_merge_kernel_simd,
)
from residentk.kernels_packed3 import (
    _norm_gemv_kernel_p3,
    _norm_gemv_kernel_p3_v2,
    _norm_gemv_kernel_p3_v3,
)
from residentk.kernels_cuda_graph import (
    _embed_row_kernel_g,
    _graph_advance_kernel,
    _qk_rope_write_kernel_g,
    _splitk_partial_kernel_simd_g,
)
from residentk.session import (
    _LM_BLOCKS,
    _StepOut,
    _ceil_div,
)
from residentk.session_cuda import (
    CUDA_SESSION_BUILD,
    CUDA_GRAPH_N_SPLITS,
)
from residentk.session_cuda_p3 import (
    _CudaResidentQwen3P3,
    _lmhead_argmax_kernel_p3,
    _lmhead_argmax_kernel_p3_v2,
    _lmhead_argmax_kernel_p3_v3,
    _norm_gemv2_swiglu_kernel_p3,
    _norm_gemv2_swiglu_kernel_p3_v2,
    _norm_gemv2_swiglu_kernel_p3_v3,
    _norm_gemv2_swiglu_kernel_p3_v4,
    _packed3_gemv_accum_kernel,
    _packed3_gemv_accum_kernel_v2,
    _packed3_gemv_accum_kernel_v3,
)

comptime P3_GRAPH_V3_KERNELS: Bool = is_defined["ALGENTA_P3_V3"]()
comptime P3_GRAPH_V4_KERNELS: Bool = (
    not is_defined["ALGENTA_P3_V1"]() and not is_defined["ALGENTA_P3_V2"]()
    and not P3_GRAPH_V3_KERNELS
)
comptime P3_GRAPH_V2_KERNELS: Bool = is_defined["ALGENTA_P3_V2"]() or P3_GRAPH_V4_KERNELS
"""Which packed3 kernel generation the captured graph arm dispatches. Exactly one is live:
`-D ALGENTA_P3_V1` -> the #800/#801 byte-view bodies; `-D ALGENTA_P3_V2` -> the v2 twins
(Int32 word-view shift/AND unpack + hoisted crossing classification, bit-identical math);
`-D ALGENTA_P3_V3` -> the v3 twins (v2 PLUS three interleaved accumulators — reassociated,
ulp-different, so the gate driver's G1 becomes the vs-f32 flip-reporting form); default ->
v4 = v2 everywhere PLUS the fused gate/up swiglu kernel (one shared-activation pass for
both dot products, bit-identical math — the ncu-measured issue/L1 bottleneck attack). That
is the campaign's A/B/C/D switch: four binaries from ONE source tree, measured back-to-back
on the same GPU. The per-dispatch arm (`step_p3`) ALWAYS dispatches the v1 bodies regardless
of these flags, so the gate driver's token diff compares the graph arm's kernel generation
against the original packed3 kernels on one session."""


@fieldwise_init
struct _CudaResidentQwen3P3Graph(Movable):
    """The packed3 decode session PLUS its captured-graph arm. Holds ONE
    `_CudaResidentQwen3P3` (its inner f32 session's weights, RoPE tables, f32 KV cache and
    scratch, the packed3 weight twins, prefill and the per-dispatch `step_p3` path — all
    delegated) and adds the graph-arm state: one 3-element STATE buffer + pinned twin
    (`[token_id, pos, n_keys]`, the layout the `_g` twins read), one token-log device buffer +
    pinned twin (`max_ctx` Int64, indexed by ABSOLUTE position), the split-K attention scratch
    trio, and ONE lazily captured `DeviceGraph`.

    `_CudaResidentQwen3P3` is Movable-not-Copyable, so this struct is Movable only, for the
    same reason the packed3 session's own docstring gives.
    """

    var p3: _CudaResidentQwen3P3
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
        """Open the packed3 session (the ONLY `DeviceContext` in this struct — the inner f32
        session's) and allocate the graph-arm additions ONCE. Called only from inside a
        `@parameter if CUDA_SESSION_BUILD` branch — the constructor cannot carry the gate
        itself, the same structural protection the packed3 session's constructor documents.
        The caller must have validated the shape with `residentk_dims_check` first (via
        `_resident_preflight`)."""
        self.p3 = _CudaResidentQwen3P3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab, max_ctx, eps, scale
        )
        self.step_state = self.p3.f32.ctx.enqueue_create_buffer[DType.int64](3)
        self.host_state = self.p3.f32.ctx.enqueue_create_host_buffer[DType.int64](3)
        self.token_log = self.p3.f32.ctx.enqueue_create_buffer[DType.int64](max_ctx)
        self.host_token_log = self.p3.f32.ctx.enqueue_create_host_buffer[DType.int64](max_ctx)
        self.sk_m = self.p3.f32.ctx.enqueue_create_buffer[DType.float32](
            h_q * CUDA_GRAPH_N_SPLITS
        )
        self.sk_l = self.p3.f32.ctx.enqueue_create_buffer[DType.float32](
            h_q * CUDA_GRAPH_N_SPLITS
        )
        self.sk_o = self.p3.f32.ctx.enqueue_create_buffer[DType.float32](
            h_q * CUDA_GRAPH_N_SPLITS * d_head
        )
        self.decode_graph = Optional[DeviceGraph]()
        self.decode_graph_built = False

    # ═══════════════════ delegation to the packed3 session ═══════════════════

    def device_name(self) raises -> String:
        return self.p3.device_name()

    def dispatch_budget(self) -> Int:
        """The per-dispatch DECODE budget this graph arm replaces: `n_layers * 6 + 3`."""
        return self.p3.dispatch_budget()

    def decode_graph_node_count(self) -> Int:
        """Kernel nodes in ONE captured replay: the per-dispatch plan, with `_sdpa_kernel`'s
        one node replaced by the split-K pair (+1 per layer) and the device-side advance
        kernel appended (+1)."""
        return self.p3.dispatch_budget() + self.p3.f32.n_layers + 1

    def graph_kernel_variant(self) -> String:
        """The packed3 kernel generation this build's captured graph dispatches — the value
        of the `P3_GRAPH_V{2,3,4}_KERNELS` switches as a printable label, so a run log always
        names the kernel set that produced its numbers."""
        @parameter
        if P3_GRAPH_V4_KERNELS:
            return "v4 (int32 unpack + fused gate/up swiglu)"
        elif P3_GRAPH_V3_KERNELS:
            return "v3 (int32 unpack + 3-way interleaved accumulators)"
        elif P3_GRAPH_V2_KERNELS:
            return "v2 (int32 word-view unpack)"
        else:
            return "v1 (u8 byte-view unpack)"

    def upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        return self.p3.upload_globals(embed, final_norm, cos_t, sin_t, n_pos)

    def upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        return self.p3.upload_layer(
            layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wgate, wup, wdown
        )

    def seal(mut self) raises -> Int:
        return self.p3.seal()

    def prefill(mut self, prompt_ids: List[Int]) raises -> _StepOut:
        """The whole prompt, delegated through the packed3 session to its inner f32 session —
        the decode = packed3 / prefill = f32 split, unchanged by the graph arm's existence."""
        return self.p3.prefill(prompt_ids)

    def step_p3(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """ONE decode token through the per-dispatch packed3 chain — delegated, so the driver
        can diff the graph arm against the per-dispatch arm on ONE session."""
        return self.p3.step_p3(token_id, pos)

    # ═══════════════════ the captured-graph arm ═══════════════════

    def _build_decode_graph_p3(mut self) raises:
        """Capture the whole packed3 per-token decode dispatch sequence into ONE `DeviceGraph`.

        The recording context (`builder.recording_context()`) records the ordinary
        `enqueue_function` calls as graph nodes in enqueue order instead of executing them —
        so this method is literally `step_p3`'s dispatch plan replayed against the recording
        context, with the three position-dependent launches reading their dynamic scalars from
        the resident `step_state` buffer through the `_g` kernel twins
        (`residentk.kernels_cuda_graph`, reused byte-unmodified), attention swapped to the
        split-K pair (module docstring), and `_graph_advance_kernel` appended as the
        device-side generation chain. Every other launch's arguments are fixed addresses and
        constants, valid for the session's life, so ONE captured graph serves every decode
        step.

        Called once, lazily, from `seed_and_run_graph_p3` — every resident buffer must already
        exist, and the constructor cannot capture a graph of buffers it has not finished
        allocating.

        POINTER HOISTING DISCIPLINE (module docstring): every device address is taken here in
        mut scope as a plain Int and rebuilt inside the `{imm}` capture via
        `unsafe_from_address`.
        """
        # ── hoist every device address in mut scope; rebuild inside the {imm} capture ──
        var hidden_a = Int(self.p3.f32.hidden.unsafe_ptr())
        var qkv_a = Int(self.p3.f32.qkv.unsafe_ptr())
        var q_rot_a = Int(self.p3.f32.q_rot.unsafe_ptr())
        var attn_out_a = Int(self.p3.f32.attn_out.unsafe_ptr())
        var act_a = Int(self.p3.f32.act.unsafe_ptr())
        var blk_val_a = Int(self.p3.f32.blk_val.unsafe_ptr())
        var blk_idx_a = Int(self.p3.f32.blk_idx.unsafe_ptr())
        var out_val_a = Int(self.p3.f32.out_val.unsafe_ptr())
        var out_idx_a = Int(self.p3.f32.out_idx.unsafe_ptr())
        var embed_a = Int(self.p3.f32.embed.unsafe_ptr())
        var final_norm_a = Int(self.p3.f32.final_norm.unsafe_ptr())
        var cos_a = Int(self.p3.f32.cos_t.unsafe_ptr())
        var sin_a = Int(self.p3.f32.sin_t.unsafe_ptr())
        var state_a = Int(self.step_state.unsafe_ptr())
        var tlog_a = Int(self.token_log.unsafe_ptr())
        var skm_a = Int(self.sk_m.unsafe_ptr())
        var skl_a = Int(self.sk_l.unsafe_ptr())
        var sko_a = Int(self.sk_o.unsafe_ptr())
        var lm_p_a = Int(self.p3.p3_lm.unsafe_ptr())
        var lm_s_a = Int(self.p3.p3_lm_s.unsafe_ptr())
        var lm_z_a = Int(self.p3.p3_lm_z.unsafe_ptr())

        var ln1s = List[Int]()
        var ln2s = List[Int]()
        var qns = List[Int]()
        var kns = List[Int]()
        var cks = List[Int]()
        var cvs = List[Int]()
        var p3_qkv_ps = List[Int]()
        var p3_qkv_ss = List[Int]()
        var p3_qkv_zs = List[Int]()
        var p3_o_ps = List[Int]()
        var p3_o_ss = List[Int]()
        var p3_o_zs = List[Int]()
        var p3_gu_ps = List[Int]()
        var p3_gu_ss = List[Int]()
        var p3_gu_zs = List[Int]()
        var p3_down_ps = List[Int]()
        var p3_down_ss = List[Int]()
        var p3_down_zs = List[Int]()
        for layer in range(self.p3.f32.n_layers):
            ref lw = self.p3.f32.layers[layer]
            ref lp = self.p3.layers_p3[layer]
            ln1s.append(Int(lw.ln1.unsafe_ptr()))
            ln2s.append(Int(lw.ln2.unsafe_ptr()))
            qns.append(Int(lw.qn.unsafe_ptr()))
            kns.append(Int(lw.kn.unsafe_ptr()))
            cks.append(Int(lw.ck.unsafe_ptr()))
            cvs.append(Int(lw.cv.unsafe_ptr()))
            p3_qkv_ps.append(Int(lp.p3_qkv.unsafe_ptr()))
            p3_qkv_ss.append(Int(lp.p3_qkv_s.unsafe_ptr()))
            p3_qkv_zs.append(Int(lp.p3_qkv_z.unsafe_ptr()))
            p3_o_ps.append(Int(lp.p3_o.unsafe_ptr()))
            p3_o_ss.append(Int(lp.p3_o_s.unsafe_ptr()))
            p3_o_zs.append(Int(lp.p3_o_z.unsafe_ptr()))
            p3_gu_ps.append(Int(lp.p3_gu.unsafe_ptr()))
            p3_gu_ss.append(Int(lp.p3_gu_s.unsafe_ptr()))
            p3_gu_zs.append(Int(lp.p3_gu_z.unsafe_ptr()))
            p3_down_ps.append(Int(lp.p3_down.unsafe_ptr()))
            p3_down_ss.append(Int(lp.p3_down_s.unsafe_ptr()))
            p3_down_zs.append(Int(lp.p3_down_z.unsafe_ptr()))

        var n_layers_c = self.p3.f32.n_layers
        var d_model_i = Int64(self.p3.f32.d_model)
        var n_q = self.p3.f32.h_q * self.p3.f32.d_head
        var n_kv = self.p3.f32.h_kv * self.p3.f32.d_head
        var n_qkv_i = Int64(n_q + 2 * n_kv)
        var h_q_i = Int64(self.p3.f32.h_q)
        var h_kv_i = Int64(self.p3.f32.h_kv)
        var d_head_i = Int64(self.p3.f32.d_head)
        var n_q_i = Int64(n_q)
        var d_ff_i = Int64(self.p3.f32.d_ff)
        var vocab_i = Int64(self.p3.f32.vocab)
        var eps_c = self.p3.f32.eps
        var scale_c = self.p3.f32.scale
        var n_iters_i = Int64(_ceil_div(self.p3.f32.vocab, _LM_BLOCKS * _SUBS))

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
            var tlog_p = UnsafePointer[Int64, origin=MutAnyOrigin](unsafe_from_address=tlog_a)
            var skm_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=skm_a)
            var skl_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=skl_a)
            var sko_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=sko_a)
            var lm_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=lm_p_a)
            var lm_s_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=lm_s_a)
            var lm_z_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=lm_z_a)

            var rec = builder.recording_context()

            # NOTE: the host_state -> step_state feed is DELIBERATELY NOT recorded here —
            # the f32 arm's A100 finding, inherited: a host->device copy captured into the
            # graph reads a capture-time snapshot of the host buffer, never the live
            # contents. `seed_and_run_graph_p3` feeds the state with ONE eager H2D before
            # the replay batch. NO memcpy nodes are recorded in either direction.

            # ── the embedding row, gathered from the resident f32 table (token: state[0]) ──
            rec.enqueue_function[_embed_row_kernel_g](
                hidden_p, embed_p, state_p, d_model_i,
                grid_dim=_ceil_div(Int(d_model_i), _TG), block_dim=_TG,
            )

            for layer in range(n_layers_c):
                var ln1_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=ln1s[layer])
                var ln2_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=ln2s[layer])
                var qn_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=qns[layer])
                var kn_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=kns[layer])
                var ck_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cks[layer])
                var cv_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=cvs[layer])
                var qkvp_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_qkv_ps[layer])
                var qkvs_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_qkv_ss[layer])
                var qkvz_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_qkv_zs[layer])
                var op_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_o_ps[layer])
                var os_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_o_ss[layer])
                var oz_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_o_zs[layer])
                var gup_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_gu_ps[layer])
                var gus_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_gu_ss[layer])
                var guz_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_gu_zs[layer])
                var dp_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_down_ps[layer])
                var ds_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_down_ss[layer])
                var dz_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=p3_down_zs[layer])
                # 1 ── rmsnorm(input_layernorm) + fused Q/K/V projection — packed3, stateless;
                #      kernel generation selected by P3_GRAPH_V{2,3}_KERNELS (module top)
                @parameter
                if P3_GRAPH_V3_KERNELS:
                    rec.enqueue_function[_norm_gemv_kernel_p3_v3](
                        qkv_p, hidden_p, ln1_p,
                        qkvp_p, qkvs_p, qkvz_p,
                        d_model_i, n_qkv_i, eps_c,
                        grid_dim=_ceil_div(Int(n_qkv_i), _SUBS), block_dim=_TG,
                    )
                elif P3_GRAPH_V2_KERNELS:
                    rec.enqueue_function[_norm_gemv_kernel_p3_v2](
                        qkv_p, hidden_p, ln1_p,
                        qkvp_p, qkvs_p, qkvz_p,
                        d_model_i, n_qkv_i, eps_c,
                        grid_dim=_ceil_div(Int(n_qkv_i), _SUBS), block_dim=_TG,
                    )
                else:
                    rec.enqueue_function[_norm_gemv_kernel_p3](
                        qkv_p, hidden_p, ln1_p,
                        qkvp_p, qkvs_p, qkvz_p,
                        d_model_i, n_qkv_i, eps_c,
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
                # 3 ── attention (n_keys: state[2]) — the SPLIT-K flash-decoding pair
                #    (partial + merge), the f32 graph arm's swap, weight-format-agnostic:
                #    both halves read the f32 KV cache the packed3 session keeps.
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
                # 4 ── o_proj + residual add — packed3 accum twin, stateless
                @parameter
                if P3_GRAPH_V3_KERNELS:
                    rec.enqueue_function[_packed3_gemv_accum_kernel_v3](
                        hidden_p, attn_out_p,
                        op_p, os_p, oz_p,
                        n_q_i, d_model_i,
                        grid_dim=_ceil_div(Int(d_model_i), _SUBS), block_dim=_TG,
                    )
                elif P3_GRAPH_V2_KERNELS:
                    rec.enqueue_function[_packed3_gemv_accum_kernel_v2](
                        hidden_p, attn_out_p,
                        op_p, os_p, oz_p,
                        n_q_i, d_model_i,
                        grid_dim=_ceil_div(Int(d_model_i), _SUBS), block_dim=_TG,
                    )
                else:
                    rec.enqueue_function[_packed3_gemv_accum_kernel](
                        hidden_p, attn_out_p,
                        op_p, os_p, oz_p,
                        n_q_i, d_model_i,
                        grid_dim=_ceil_div(Int(d_model_i), _SUBS), block_dim=_TG,
                    )
                # 5 ── rmsnorm(post_attention_layernorm) + gate/up + SwiGLU — packed3, stateless;
                #      v4 (default) dispatches the fused gate/up twin
                @parameter
                if P3_GRAPH_V4_KERNELS:
                    rec.enqueue_function[_norm_gemv2_swiglu_kernel_p3_v4](
                        act_p, hidden_p, ln2_p,
                        gup_p, gus_p, guz_p,
                        d_model_i, d_ff_i, eps_c,
                        grid_dim=_ceil_div(Int(d_ff_i), _SUBS), block_dim=_TG,
                    )
                elif P3_GRAPH_V3_KERNELS:
                    rec.enqueue_function[_norm_gemv2_swiglu_kernel_p3_v3](
                        act_p, hidden_p, ln2_p,
                        gup_p, gus_p, guz_p,
                        d_model_i, d_ff_i, eps_c,
                        grid_dim=_ceil_div(Int(d_ff_i), _SUBS), block_dim=_TG,
                    )
                elif P3_GRAPH_V2_KERNELS:
                    rec.enqueue_function[_norm_gemv2_swiglu_kernel_p3_v2](
                        act_p, hidden_p, ln2_p,
                        gup_p, gus_p, guz_p,
                        d_model_i, d_ff_i, eps_c,
                        grid_dim=_ceil_div(Int(d_ff_i), _SUBS), block_dim=_TG,
                    )
                else:
                    rec.enqueue_function[_norm_gemv2_swiglu_kernel_p3](
                        act_p, hidden_p, ln2_p,
                        gup_p, gus_p, guz_p,
                        d_model_i, d_ff_i, eps_c,
                        grid_dim=_ceil_div(Int(d_ff_i), _SUBS), block_dim=_TG,
                    )
                # 6 ── down_proj + residual add — packed3 accum twin, stateless
                @parameter
                if P3_GRAPH_V3_KERNELS:
                    rec.enqueue_function[_packed3_gemv_accum_kernel_v3](
                        hidden_p, act_p,
                        dp_p, ds_p, dz_p,
                        d_ff_i, d_model_i,
                        grid_dim=_ceil_div(Int(d_model_i), _SUBS), block_dim=_TG,
                    )
                elif P3_GRAPH_V2_KERNELS:
                    rec.enqueue_function[_packed3_gemv_accum_kernel_v2](
                        hidden_p, act_p,
                        dp_p, ds_p, dz_p,
                        d_ff_i, d_model_i,
                        grid_dim=_ceil_div(Int(d_model_i), _SUBS), block_dim=_TG,
                    )
                else:
                    rec.enqueue_function[_packed3_gemv_accum_kernel](
                        hidden_p, act_p,
                        dp_p, ds_p, dz_p,
                        d_ff_i, d_model_i,
                        grid_dim=_ceil_div(Int(d_model_i), _SUBS), block_dim=_TG,
                    )

            # ── final rmsnorm + packed3 lm_head + per-threadgroup argmax, then the reduce ──
            @parameter
            if P3_GRAPH_V3_KERNELS:
                rec.enqueue_function[_lmhead_argmax_kernel_p3_v3](
                    blk_val_p, blk_idx_p, hidden_p,
                    final_norm_p, lm_p, lm_s_p, lm_z_p,
                    d_model_i, vocab_i, eps_c, n_iters_i,
                    grid_dim=_LM_BLOCKS, block_dim=_TG,
                )
            elif P3_GRAPH_V2_KERNELS:
                rec.enqueue_function[_lmhead_argmax_kernel_p3_v2](
                    blk_val_p, blk_idx_p, hidden_p,
                    final_norm_p, lm_p, lm_s_p, lm_z_p,
                    d_model_i, vocab_i, eps_c, n_iters_i,
                    grid_dim=_LM_BLOCKS, block_dim=_TG,
                )
            else:
                rec.enqueue_function[_lmhead_argmax_kernel_p3](
                    blk_val_p, blk_idx_p, hidden_p,
                    final_norm_p, lm_p, lm_s_p, lm_z_p,
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
            rec.enqueue_function[_graph_advance_kernel](
                state_p, out_idx_p, tlog_p,
                grid_dim=1, block_dim=1,
            )

        self.decode_graph = DeviceGraph.create(self.p3.f32.ctx, build)

    def seed_and_run_graph_p3(
        mut self, first_token: Int, start_pos: Int, n_steps: Int,
    ) raises -> Int:
        """Run `n_steps` packed3 decode steps as `n_steps` back-to-back replays of ONE
        captured graph, with ZERO per-step host traffic — the device-side chain
        (`_graph_advance_kernel`, captured as the graph's last node) logs each token to
        `token_log`, feeds it as the next embed input, and advances pos/n_keys; replays run
        in stream order, so replay k consumes exactly what replay k-1 advanced. The host
        seeds `step_state` once (one eager H2D), enqueues every replay, synchronizes once,
        and pulls the whole token log back eagerly (a recorded D2H copy would land in
        graph-owned staging, never the host buffer).

        Returns a RESIDENT_* status. Tokens are read afterwards with `graph_token(pos)` —
        the log is indexed by ABSOLUTE position, and the indexing convention is the f32
        graph arm's own: the token the per-dispatch loop produces at
        `step(token, pos)` is the token the graph logs at `graph_token(pos)`, so the seed is
        `(prefill's first token, n_prompt)` and replay k's output sits at
        `graph_token(start_pos + k - 1)`. The caller owns `pos` bookkeeping exactly as with
        `step_p3`/`prefill`: the next position after this call is `start_pos + n_steps`.
        """

        @parameter
        if not CUDA_SESSION_BUILD:
            return RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT
        else:
            if n_steps < 1:
                return RESIDENT_ERR_UPLOAD_LENGTH
            if start_pos < 0 or start_pos + n_steps > self.p3.f32.max_ctx:
                return RESIDENT_ERR_CONTEXT_FULL
            if first_token < 0 or first_token >= self.p3.f32.vocab:
                return RESIDENT_ERR_UPLOAD_LENGTH

            if not self.decode_graph_built:
                self._build_decode_graph_p3()
                self.decode_graph_built = True

            # Seed the chain once: the prefill's first token + the position it occupies.
            # HostBuffer is host-visible already — write through its pointer directly.
            var state_h = self.host_state.unsafe_ptr()
            state_h[0] = Int64(first_token)
            state_h[1] = Int64(start_pos)
            state_h[2] = Int64(start_pos + 1)
            self.p3.f32.ctx.enqueue_copy(self.step_state, self.host_state)

            for _ in range(n_steps):
                self.decode_graph.value().replay()

            # One synchronize for the whole generation, then the log readback (eager — a
            # recorded copy would land in graph-owned staging, never this host buffer).
            self.p3.f32.ctx.synchronize()
            self.p3.f32.ctx.enqueue_copy(self.host_token_log, self.token_log)
            self.p3.f32.ctx.synchronize()
            return RESIDENT_OK

    def graph_token(self, pos: Int) -> Int:
        """The token logged at ABSOLUTE position `pos` by the last `seed_and_run_graph_p3`
        call, read from the host-side token log."""
        return Int(self.host_token_log.unsafe_ptr()[pos])
