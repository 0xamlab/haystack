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
    _dump7b_copy_row_kernel,
    _qkv_bias_add_rows_kernel,
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
from residentk.kernels_prefill_attn_flash import (
    _PF_FLASH_NTHREADS,
    _PF_FLASH_ROWS_PER_BLOCK,
    _pf_attn_flash_kernel,
)
from residentk.kernels_prefill_attn_flash2 import (
    _pf_attn_flash2_kernel,
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
from residentk.tc_shim_bridge import (
    TC_SHIM_BUILD,
    TC_MIN_M,
    TC_ACC_MODE,
    _tc_init,
    _tc_last_error,
    _tc_stage_f32_to_f16,
    _tc_gemm_dispatch,
    _pf_swiglu_rows_kernel,
)
from std.time import perf_counter_ns

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — `residentk.kernels`' spelling."""

comptime CUDA_SESSION_BUILD: Bool = RESIDENT_GPU_BUILD and is_defined["ALGENTA_CUDA"]()
"""Whether this binary was built with `-D ALGENTA_GPU -D ALGENTA_CUDA` — the portable-kernel tier
conjoined with the CUDA backend selector, the two-tier split `metaldispatch.session.MB_GPU_BUILD`
mirrors on the Metal side (with `ALGENTA_METAL`). A Metal build sets `ALGENTA_GPU` but NOT
`ALGENTA_CUDA`, so every launch in this file is removed before shader codegen there — the Metal
lane is untouched by this module's existence."""

comptime ALGENTA_7B_DUMP: Bool = is_defined["ALGENTA_7B_DUMP"]()
"""DEBUG-ONLY layer-by-layer activation-dump hook for the 7B-lane correctness bisection
(2026-08-23): with `-D ALGENTA_7B_DUMP`, `prefill` prints one checksum line per dumped stage
(embed / xn1 / qkv / qrot / attn / post_attn / xn2 / act / post_mlp, per layer, LAST prompt row
only) as `DUMP7B|<layer>|<stage>|<n>|<f64 sum>|<f64 max|x|>|<v0>|<v1>`, to be diffed against the
identical checksums a transformers fp32 CPU forward prints (`dump_transformers_cpu.py`). Without
the define every dump site is removed at comptime — shipped builds carry NONE of it (the copy
kernel, `residentk.kernels._dump7b_copy_row_kernel`, is lowered only at these gated enqueue
sites, so it costs nothing there either)."""

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

comptime CUDA_PREFILL_ONEPASS_B1: Bool = is_defined["ALGENTA_PF_ONEPASS_B1"]()
"""H100-autopsy lever L-H3 (the batch-1 twin of the serve driver's L2): with
`-D ALGENTA_PF_ONEPASS_B1`, `prefill` walks the prompt in windows of up to `_B1_PASS_MAX` rows
instead of `CUDA_PREFILL_TILE` (128-row) chunks — one M-parallel grid per projection per window,
the v2 GEMM grids scaling with M (the H100 ncu evidence: M=128 chunks pin occupancy at 12.5%
= one block/SM on 132 SMs, waves 0.06-0.36 for the narrow-N roles; the fixture's 1.54x
A100->H100 scaling vs the 3.4x f32-peak ratio is this wave quantization, not a clock or
bandwidth effect). Flag-off builds keep the 128-row walk byte-for-byte."""

comptime CUDA_PREFILL_PASS4096: Bool = is_defined["ALGENTA_PF_PASS4096"]()
"""FRONT 6 lever (2026-09-16): widen one batch-1 prefill pass from 1024 rows to 4096, so a
RAG-4096 prompt runs its projections in ONE pass instead of four.

The chunking was costing real money and nobody had priced it, because every previous round
compared kernels against TensorRT-LLM's per-request totals rather than asking whether OUR pass
shape was the efficient one. FRONT 6's `gemm_probe --msweep` (A100-SXM4-40GB, clocks pinned
1410, median of 15, the four Qwen2.5-7B projection roles at their exact dtypes/beta) prices the
same 1905.3 GFLOP of per-layer projection work three ways:

    m     passes   per-layer us    4096-row us    28-layer ms    vs 4x1024
    1024       4        1937.41        7749.63        216.990        +0.00   (SHIPPED)
    2048       2        3649.54        7299.07        204.374      -450.56
    4096       1        7326.72        7326.72        205.148      -422.91

The cause is tail-wave quantization, the same effect the H100 autopsy named for 128-row chunks:
at m=1024 the narrow-N roles tile into 8x28 = 224 output tiles of 128x128 = 2.07 waves on 108
SMs, so a third of the machine sits idle through the second wave. Per role at m=1024 -> 4096
(cublasGemmEx DEFAULT): o_proj 188.9 -> 199.9 TF/s, down 212.8 -> 244.2, qkv 229.4 -> 224.7,
gate/up 278.8 -> 283.7 (gate/up is already at 89% of the 312 TF/s dense f16 peak and was never
the problem; down and o_proj are). nsys independently puts the shipped cublas family at 226.048
ms per RAG-4096 prefill against this probe's 216.990 ms for the same 448 calls, so the probe
reads ~4% optimistic in isolation -- the RANKING is what transfers, and it says one pass.

Costs, stated rather than buried: this is NOT bit-identical. cuBLAS picks a different algorithm
per M, and a different tile/split-K changes the reduction order, so the f32 accumulator rounds
differently. It is gate-decidable exactly like ALGENTA_7B_PF_F16MLP: G0 16/16 against the fp32
transformers oracle and G1 64/64 self-consistency decide it, and the flag stays default OFF so
`_g0` remains byte-identical to FRONT 5's shipped arm. It also costs VRAM: every pf_* / tc_*
scratch buffer is sized by `_B1_PF_ROWS`, so 1024 -> 4096 rows adds ~5.6 GB at the 7B shapes
(2.8 GB of which is `pf_tc_scores` + `pf_tc_p16`, the five-pass attention chain's windows, which
ALGENTA_7B_PF_FA2 leaves dead but which must still be sized because the chain is FA2's runtime
decline path). The existing headroom try in `_tc_stage_weights` still demotes the whole TC plan
with a printed record on a device that cannot hold it, so a tight card degrades instead of
half-allocating.

Prompts of 1024 rows or fewer are UNAFFECTED: `m` is `min(n_prompt, _B1_PASS_MAX)`, so the pp256
and pp1024 cells take the identical single pass with the identical M and the identical cuBLAS
algorithm choice. This flag can only change a prompt LONGER than 1024 -- i.e. exactly the
RAG-4096 cell it targets, and not the two cells this round must not regress."""

comptime _B1_PASS_MAX: Int = 4096 if CUDA_PREFILL_PASS4096 else 1024
"""Rows one batch-1 prefill pass covers under CUDA_PREFILL_ONEPASS_B1: >= the raced fixture
prompt (256) and every chat shape, so those prefill in ONE pass; longer prompts run
ceil(len/1024) passes. Scratch VRAM at this cap: ~55 MB at Qwen3-0.6B's shapes — sized for the
fixture/chat cells this lever targets. CUDA_PREFILL_PASS4096 raises the cap to 4096 (see its
docstring for the measured projection cost of the 1024-row walk and the ~5.6 GB it adds)."""

comptime _B1_PF_ROWS: Int = _B1_PASS_MAX if CUDA_PREFILL_ONEPASS_B1 else CUDA_PREFILL_TILE
"""Prefill scratch rows: the pass cap under the onepass arm, the legacy 128 otherwise."""

comptime CUDA_PREFILL_FLASH_B1: Bool = is_defined["ALGENTA_PF_ATTN_FLASH_B1"]()
"""H100-autopsy lever L-H3's attention half (the batch-1 twin of the serve driver's L1): with
`-D ALGENTA_PF_ATTN_FLASH_B1`, batch-1 prefill dispatches the flash-style M-parallel attention
kernel (`residentk.kernels_prefill_attn_flash._pf_attn_flash_kernel`, one warp per four rows of
one head, warp-shuffle score reduction, online softmax, no barrier/shared) instead of
`_pf_attn_tiled_kernel_simd` (one block per (row, head), two-barrier full-block reduction PER
KEY). The H100 fixture nsys window measured the tiled kernel at 19.5% of the 256-token prefill
GPU (9.88 ms/gen at grid h_q*m). The tiled kernel stays the fallback for any head dim the flash
kernel's float4-lane contract does not cover (d_head != 128) and for flag-off builds. Row math
bit-identical to the tiled kernel's per-key online-softmax recurrence — the session's own
oracle gate is the acceptance test, exactly as the serve driver's L1 was."""

comptime CUDA_PREFILL_FLASH2_B1: Bool = is_defined["ALGENTA_PF_ATTN_FLASH2_B1"]()
"""H100-autopsy lever L-H4's batch-1 twin: under `-D ALGENTA_PF_ATTN_FLASH2_B1` (with
`ALGENTA_PF_ATTN_FLASH_B1`), the batch-1 flash dispatch uses the LATENCY-PIPELINED twin
`_pf_attn_flash2_kernel` (bit-identical to the L1 kernel, 1.16-1.36x faster on H100 — see
`residentk.kernels_prefill_attn_flash2`'s docstring for the ncu stall evidence). Falls
through to the L1 kernel when absent."""


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
    var qk_norm: Int
    var has_lm_head: Int
    var skip_f32_projections: Int
    var has_qkv_bias: Int

    var layers: List[_LayerGpu]
    var qkv_biases: List[DeviceBuffer[DType.float32]]
    var embed: DeviceBuffer[DType.float32]
    var lm_head: DeviceBuffer[DType.float32]
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

    # ── TC escape-hatch prefill (feat/tc-int): f16 twins of the four resident f32
    #    projection tables (staged from those f32 weights ONCE, at first prefill) plus the
    #    per-tile scratch. Real sizes ONLY under TC_SHIM_BUILD (VRAM headroom check: the
    #    dual residency is +1.02 GB at 0.6B, measured by the probe); every other build
    #    holds 1-element placeholders and `tc_staged = -1`. 0 = allocated/staging pending,
    #    1 = staged, -1 = absent (flag off, no resident f32 weights, or headroom failed).
    var w16_qkv: List[DeviceBuffer[DType.float16]]
    var w16_o: List[DeviceBuffer[DType.float16]]
    var w16_gu: List[DeviceBuffer[DType.float16]]
    var w16_down: List[DeviceBuffer[DType.float16]]
    var tc_a16: DeviceBuffer[DType.float16]
    var tc_c16: DeviceBuffer[DType.float16]
    var tc_gu: DeviceBuffer[DType.float32]
    var tc_staged: Int

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
        qk_norm: Int = 1, has_lm_head: Int = 0, skip_f32_projections: Int = 0,
        has_qkv_bias: Int = 0,
    ) raises:
        """Open the context and allocate every resident + scratch buffer. ONCE.

        Called only from inside a `@parameter if CUDA_SESSION_BUILD` branch — see the module
        docstring for why a constructor cannot carry the gate itself. The caller must have
        validated the shape with `residentk_dims_check` first, exactly as `_ResidentQwen3`'s own
        constructor requires.

        7B-lane flags (2026-08-22, all default to the pre-7B behaviour):
        * `qk_norm` — 1 keeps the Qwen3 per-head QK-norm on every ropewrt dispatch; 0 runs the
          llama-family branch (rotate the raw projections; `qn`/`kn` are never read — Qwen2.5
          has NO QK-norm tensors).
        * `has_lm_head` — 1 allocates a SEPARATE resident `lm_head` table (`vocab * d_model`)
          and every lm_head+argmax dispatch binds it instead of the embedding table
          (Qwen2.5-7B's untied head); 0 keeps the tied convention (embed IS lm_head).
        * `skip_f32_projections` — 1 allocates ONLY 1-element placeholders for the four f32
          projection matrices per layer (a 7B's f32+packed3 dual residency exceeds a 40 GB
          device): the session then refuses `prefill`/`step`/graph decode — a composed packed3
          session runs prefill through the JIT-dequant seam instead (`residentk.
          kernels_packed3._p3_dequant_rows_kernel`) and decode through the packed3 chain.
        * `has_qkv_bias` — 1 allocates one resident `[Q|K|V]` bias vector per layer
          (`(h_q + 2*h_kv) * d_head` Float32) and every QKV-producing dispatch follows the
          projection with a `_qkv_bias_add_rows_kernel` add before RoPE (Qwen2/Qwen2.5 carry
          q/k/v projection biases — the 2026-08-23 7B correctness root cause); 0 keeps the
          bias-less convention byte-identical (no buffer, no launch).
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
        self.qk_norm = qk_norm
        self.has_lm_head = has_lm_head
        self.skip_f32_projections = skip_f32_projections
        self.has_qkv_bias = has_qkv_bias

        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

        # 7B memory fit: the f32 projections are the dominant resident (~26 GB at 7B); a
        # p3-composed session that prefills through the JIT-dequant seam allocates 1-element
        # placeholders here and never dispatches a kernel that reads them (guarded above in
        # `prefill`/`step`/the graph arm, and in `upload_layer`'s narrowing skip).
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
                    self.ctx.enqueue_create_buffer[DType.float32](max_ctx * h_kv * d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](max_ctx * h_kv * d_head),
                )
            )

        # 7B-lane attention bias (2026-08-23): one resident `[Q|K|V]` bias vector per layer when
        # the session was opened with `has_qkv_bias=1` (Qwen2/Qwen2.5); a 1-element placeholder
        # otherwise, so a bias-less session allocates nothing meaningful and never dispatches the
        # add. Same Float32 residency as every other weight here.
        self.qkv_biases = List[DeviceBuffer[DType.float32]]()
        var qkv_bias_elems = n_qkv if has_qkv_bias == 1 else 1
        for _ in range(n_layers):
            self.qkv_biases.append(
                self.ctx.enqueue_create_buffer[DType.float32](qkv_bias_elems)
            )

        self.embed = self.ctx.enqueue_create_buffer[DType.float32](vocab * d_model)
        var lm_elems = vocab * d_model
        if has_lm_head != 1:
            lm_elems = 1
        self.lm_head = self.ctx.enqueue_create_buffer[DType.float32](lm_elems)
        self.final_norm = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.cos_t = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
        self.sin_t = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)

        self.hidden = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.qkv = self.ctx.enqueue_create_buffer[DType.float32](n_qkv)
        self.q_rot = self.ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
        # 7B-lane (large tier): the o_proj / down_proj GEMVs read these activations from
        # GLOBAL memory across their full padded width `k_pack = ceil(k/12)*12` (the shared
        # staging would exceed the per-block budget), so the `k_pack - k` tail must exist and
        # stay zero. Allocate the padded size; producers write only `[0, k)` and the buffers
        # are zeroed here once, so the tail stays zero for the session's life.
        var attn_out_elems = ((h_q * d_head + 11) // 12) * 12
        var act_elems = ((d_ff + 11) // 12) * 12
        self.attn_out = self.ctx.enqueue_create_buffer[DType.float32](attn_out_elems)
        self.act = self.ctx.enqueue_create_buffer[DType.float32](act_elems)
        # Zero the `k_pack - k` tails once (producers only write `[0, k)` each step, so the
        # tails stay zero for the session's life). Flushed by the driver's `seal()` sync.
        with self.attn_out.map_to_host() as h_attn:
            for i in range(h_q * d_head, attn_out_elems):
                h_attn[i] = Float32(0.0)
        with self.act.map_to_host() as h_act:
            for i in range(d_ff, act_elems):
                h_act[i] = Float32(0.0)
        self.blk_val = self.ctx.enqueue_create_buffer[DType.float32](_LM_BLOCKS)
        self.blk_idx = self.ctx.enqueue_create_buffer[DType.int32](_LM_BLOCKS)
        self.out_val = self.ctx.enqueue_create_buffer[DType.float32](1)
        self.out_idx = self.ctx.enqueue_create_buffer[DType.int32](1)
        self.host_val = self.ctx.enqueue_create_host_buffer[DType.float32](1)
        self.host_idx = self.ctx.enqueue_create_host_buffer[DType.int32](1)

        var t = _B1_PF_ROWS
        self.pf_tokens = self.ctx.enqueue_create_buffer[DType.int32](t)
        self.pf_hidden = self.ctx.enqueue_create_buffer[DType.float32](t * d_model)
        self.pf_xn = self.ctx.enqueue_create_buffer[DType.float32](t * d_model)
        self.pf_qkv = self.ctx.enqueue_create_buffer[DType.float32](t * n_qkv)
        self.pf_q_rot = self.ctx.enqueue_create_buffer[DType.float32](t * h_q * d_head)
        self.pf_attn = self.ctx.enqueue_create_buffer[DType.float32](t * h_q * d_head)
        self.pf_act = self.ctx.enqueue_create_buffer[DType.float32](t * d_ff)

        # ── TC escape-hatch residency: the constructor allocates ONLY placeholders (every
        #    build, cheap); `tc_staged = 0` under the build flag marks the lazy path in
        #    `_tc_stage_weights`, which performs the REAL allocation inside its headroom
        #    try/except on the first prefill (a constructor cannot borrow self inside a try
        #    before every field is initialized — Mojo's definite-initialization refuses it).
        self.w16_qkv = List[DeviceBuffer[DType.float16]]()
        self.w16_o = List[DeviceBuffer[DType.float16]]()
        self.w16_gu = List[DeviceBuffer[DType.float16]]()
        self.w16_down = List[DeviceBuffer[DType.float16]]()
        self.tc_a16 = self.ctx.enqueue_create_buffer[DType.float16](1)
        self.tc_c16 = self.ctx.enqueue_create_buffer[DType.float16](1)
        self.tc_gu = self.ctx.enqueue_create_buffer[DType.float32](1)
        self.tc_staged = -1
        @parameter
        if TC_SHIM_BUILD:
            self.tc_staged = 0

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

    def upload_lm_head(mut self, lm: List[Float64]) raises -> Int:
        """The SEPARATE lm_head table (7B-lane enablement, 2026-08-22): the untied
        `lm_head.weight` of a checkpoint with `tie_word_embeddings=false` (Qwen2.5-7B),
        narrowed into the session's own `lm_head` buffer — every lm_head+argmax dispatch
        binds it instead of the embedding table when `has_lm_head=1`. Refused unless the
        session was opened with `has_lm_head=1`."""
        if self.has_lm_head != 1:
            return RESIDENT_ERR_UPLOAD_LENGTH
        return _narrow_into(self.lm_head, lm, self.vocab * self.d_model, 0)

    def upload_qkv_bias(
        mut self, layer: Int, q_bias: List[Float64], k_bias: List[Float64],
        v_bias: List[Float64],
    ) raises -> Int:
        """One layer's q/k/v projection biases (7B-lane, 2026-08-23), narrowed and packed into
        the layer's resident `[Q | K | V]` bias vector at offsets 0 / n_q / n_q + n_kv — the SAME
        concatenation order the fused QKV projection writes its output in, so the
        `_qkv_bias_add_rows_kernel` per-column add lands each bias on its own section with no
        head arithmetic. Refused unless the session was opened with `has_qkv_bias=1`."""
        if self.has_qkv_bias != 1:
            return RESIDENT_ERR_UPLOAD_LENGTH
        if layer < 0 or layer >= self.n_layers:
            return RESIDENT_ERR_UPLOAD_LENGTH
        var n_q = self.h_q * self.d_head
        var n_kv = self.h_kv * self.d_head
        ref bias = self.qkv_biases[layer]
        var s = _narrow_into(bias, q_bias, n_q, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(bias, k_bias, n_kv, n_q)
        if s != RESIDENT_OK:
            return s
        return _narrow_into(bias, v_bias, n_kv, n_q + n_kv)

    def lm_head_w(mut self) -> _FP:
        """The matrix pointer every lm_head+argmax dispatch binds: the SEPARATE `lm_head`
        table when the session was opened with `has_lm_head=1` (Qwen2.5-7B's untied head),
        the embedding table otherwise (the tied Qwen3 convention, byte-identical behaviour).
        Returned with the origin erased to `MutAnyOrigin` (the kernel-parameter spelling) via
        the address round-trip the graph captures use."""
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
        # 7B-lane: a no-QK-norm checkpoint (Qwen2.5) delivers NO q_norm/k_norm tensors — the
        # driver passes empty lists, and the gains are filled with the identity 1.0 (the
        # ropewrt kernels with `qk_norm=0` never read them; a qk_norm=1 dispatch on a
        # norm-less model would be a caller bug the prefill/step flags rule out).
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
            # The projection buffers are 1-element placeholders (7B memory fit): validate the
            # wire lengths so a bad tensor still fails here with the honest status, narrow
            # nothing.
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

    def _tc_alloc(
        mut self, n_layers: Int, n_qkv: Int, n_q: Int, d_model: Int, d_ff: Int,
    ) raises:
        """The REAL TC residency (constructor headroom try): dense f16 twins of the four
        f32 projection tables per layer plus the tile scratch, capped at `_B1_PF_ROWS` rows
        (the largest tile `prefill` dispatches — the pf_* scratch sizing)."""
        var rows = _B1_PF_ROWS
        var max_k = d_model
        if n_q > max_k:
            max_k = n_q
        if d_ff > max_k:
            max_k = d_ff
        var max_n = n_qkv
        if 2 * d_ff > max_n:
            max_n = 2 * d_ff
        for _ in range(n_layers):
            self.w16_qkv.append(
                self.ctx.enqueue_create_buffer[DType.float16](n_qkv * d_model))
            self.w16_o.append(self.ctx.enqueue_create_buffer[DType.float16](d_model * n_q))
            self.w16_gu.append(
                self.ctx.enqueue_create_buffer[DType.float16](2 * d_ff * d_model))
            self.w16_down.append(
                self.ctx.enqueue_create_buffer[DType.float16](d_model * d_ff))
        self.tc_a16 = self.ctx.enqueue_create_buffer[DType.float16](rows * max_k)
        self.tc_c16 = self.ctx.enqueue_create_buffer[DType.float16](rows * max_n)
        self.tc_gu = self.ctx.enqueue_create_buffer[DType.float32](rows * 2 * d_ff)

    def _tc_stage_weights(mut self) raises:
        """The ONE-TIME prefill TC enablement, lazy on the first `prefill`: (1) the VRAM
        headroom check — allocate the REAL f16 dual residency + scratch (the constructor
        holds placeholders only); an allocation failure demotes the session to the native
        chain for life with a printed record, never fatal. (2) `tc_shim_init` (cuBLAS
        handle on Mojo's context). (3) every layer's four RESIDENT F32 tables converted to
        their f16 twins by `tc_shim_f32_to_f16` (this session keeps its f32 projections
        resident for every arm that reaches this method — the skip_f32_projections mode
        has none and is refused). Any failure demotes to native with a printed record."""
        if self.tc_staged != 0:
            return
        if self.skip_f32_projections == 1:
            self.tc_staged = -1
            return
        try:
            self._tc_alloc(
                self.n_layers, (self.h_q + 2 * self.h_kv) * self.d_head,
                self.h_q * self.d_head, self.d_model, self.d_ff)
        except e:
            print("TC: VRAM headroom check FAILED — the f16 dual residency could not be",
                  "allocated; prefill stays on the native chain. Recorded:", e)
            self.tc_staged = -1
            return
        var t0 = perf_counter_ns()
        var r = _tc_init()
        if r != 0:
            print("TC: tc_shim_init failed:", r, "last_error:", _tc_last_error(),
                  "| prefill stays on the native chain")
            self.tc_staged = -1
            return
        var n_q = self.h_q * self.d_head
        var n_qkv = (self.h_q + 2 * self.h_kv) * self.d_head
        for layer in range(self.n_layers):
            ref lw = self.layers[layer]
            r = _tc_stage_f32_to_f16(
                Int(lw.w_qkv.unsafe_ptr()), Int(self.w16_qkv[layer].unsafe_ptr()),
                n_qkv * self.d_model)
            if r == 0:
                r = _tc_stage_f32_to_f16(
                    Int(lw.w_o.unsafe_ptr()), Int(self.w16_o[layer].unsafe_ptr()),
                    self.d_model * n_q)
            if r == 0:
                r = _tc_stage_f32_to_f16(
                    Int(lw.w_gu.unsafe_ptr()), Int(self.w16_gu[layer].unsafe_ptr()),
                    2 * self.d_ff * self.d_model)
            if r == 0:
                r = _tc_stage_f32_to_f16(
                    Int(lw.w_down.unsafe_ptr()), Int(self.w16_down[layer].unsafe_ptr()),
                    self.d_model * self.d_ff)
            if r != 0:
                print("TC: f32->f16 staging FAILED at layer", layer, "status", r,
                      "last_error:", _tc_last_error(),
                      "| prefill stays on the native chain")
                self.tc_staged = -1
                return
        self.ctx.synchronize()
        self.tc_staged = 1
        var f16_bytes = Float64(self.n_layers) * Float64(
            n_qkv * self.d_model + self.d_model * n_q + 2 * self.d_ff * self.d_model
            + self.d_model * self.d_ff) * 2.0
        print("TC: prefill f16 residency STAGED |",
              Float64(perf_counter_ns() - t0) / 1.0e6, "ms one-time | tables:",
              f16_bytes / 1.0e9, "GB | compute mode:", TC_ACC_MODE)

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
            if self.skip_f32_projections == 1:
                # 7B memory fit: the f32 projections are not resident; a composed packed3
                # session prefills through the JIT-dequant seam, never this path.
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)
            for i in range(n_prompt):
                if prompt_ids[i] < 0 or prompt_ids[i] >= self.vocab:
                    return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)

            @parameter
            if TC_SHIM_BUILD:
                self._tc_stage_weights()

            var n_q = self.h_q * self.d_head
            var issued = 0
            var pos = 0
            var last_m = 0
            while pos < n_prompt:
                var m = CUDA_PREFILL_TILE
                @parameter
                if CUDA_PREFILL_ONEPASS_B1:
                    m = _B1_PASS_MAX
                if n_prompt - pos < m:
                    m = n_prompt - pos
                last_m = m
                # Runtime TC admission for THIS tile (always False in flag-off builds —
                # `tc_staged` is -1 there): full tiles ride the seam, prompt tails keep v2.
                var use_tc = False
                @parameter
                if TC_SHIM_BUILD:
                    use_tc = self.tc_staged == 1 and m >= TC_MIN_M

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

                # ── 7B-dump hook: embed rows (LAST tile's final row) ──
                @parameter
                if ALGENTA_7B_DUMP:
                    if pos + m == n_prompt:
                        var dg_n = self.d_model
                        var dg_stg = self.ctx.enqueue_create_buffer[DType.float32](dg_n)
                        var dg_hb = self.ctx.enqueue_create_host_buffer[DType.float32](dg_n)
                        self.ctx.enqueue_function[_dump7b_copy_row_kernel](
                            dg_stg.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                            Int64(m - 1), Int64(dg_n),
                            grid_dim=_ceil_div(dg_n, _TG), block_dim=_TG,
                        )
                        self.ctx.enqueue_copy(dg_hb, dg_stg)
                        self.ctx.synchronize()
                        var dp = dg_hb.unsafe_ptr()
                        var dg_sum = Float64(0.0)
                        var dg_max = Float64(0.0)
                        for di in range(dg_n):
                            var dv = Float64(dp[di])
                            dg_sum += dv
                            if abs(dv) > dg_max:
                                dg_max = abs(dv)
                        print("DUMP7B|-1|embed|" + String(dg_n) + "|" + String(dg_sum) + "|"
                              + String(dg_max) + "|" + String(Float64(dp[0])) + "|"
                              + String(Float64(dp[1])))

                for layer in range(self.n_layers):
                    ref lw = self.layers[layer]

                    # 1 ── rmsnorm(input_layernorm) over every row
                    self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        self.pf_xn.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                        lw.ln1.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # ── 7B-dump hook: xn1 (post input_layernorm) ──
                    @parameter
                    if ALGENTA_7B_DUMP:
                        if pos + m == n_prompt:
                            var dg_n = self.d_model
                            var dg_stg = self.ctx.enqueue_create_buffer[DType.float32](dg_n)
                            var dg_hb = self.ctx.enqueue_create_host_buffer[DType.float32](dg_n)
                            self.ctx.enqueue_function[_dump7b_copy_row_kernel](
                                dg_stg.unsafe_ptr(), self.pf_xn.unsafe_ptr(),
                                Int64(m - 1), Int64(dg_n),
                                grid_dim=_ceil_div(dg_n, _TG), block_dim=_TG,
                            )
                            self.ctx.enqueue_copy(dg_hb, dg_stg)
                            self.ctx.synchronize()
                            var dp = dg_hb.unsafe_ptr()
                            var dg_sum = Float64(0.0)
                            var dg_max = Float64(0.0)
                            for di in range(dg_n):
                                var dv = Float64(dp[di])
                                dg_sum += dv
                                if abs(dv) > dg_max:
                                    dg_max = abs(dv)
                            print("DUMP7B|" + String(layer) + "|xn1|" + String(dg_n) + "|"
                                  + String(dg_sum) + "|" + String(dg_max) + "|"
                                  + String(Float64(dp[0])) + "|" + String(Float64(dp[1])))
                    # 2 ── fused Q/K/V projection — TC seam (ASSIGN) or the v2
                    # register-blocked / double-buffered kernel (kernels_prefill_f32_v2)
                    if use_tc:
                        self.ctx.synchronize()
                        var r = _tc_gemm_dispatch(
                            Int(self.pf_xn.unsafe_ptr()),
                            Int(self.w16_qkv[layer].unsafe_ptr()),
                            Int(lw.w_qkv.unsafe_ptr()),
                            m, self.d_model, (self.h_q + 2 * self.h_kv) * self.d_head,
                            Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                            Int(self.pf_qkv.unsafe_ptr()), 0)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                    else:
                        self.ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
                            self.pf_qkv.unsafe_ptr(), self.pf_xn.unsafe_ptr(),
                            lw.w_qkv.unsafe_ptr(),
                            Int64(m), Int64(self.d_model), Int64((self.h_q + 2 * self.h_kv) * self.d_head),
                            grid_dim=_ceil_div(m, _G2_BM) * _ceil_div((self.h_q + 2 * self.h_kv) * self.d_head, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                    # 2b ── 7B-lane attention bias: q/k/v biases onto the QKV output BEFORE RoPE
                    # (dispatched only when the session carries biases; a Qwen3 session never
                    # reaches this launch).
                    if self.has_qkv_bias == 1:
                        self.ctx.enqueue_function[_qkv_bias_add_rows_kernel](
                            self.pf_qkv.unsafe_ptr(), self.qkv_biases[layer].unsafe_ptr(),
                            Int64(m), Int64((self.h_q + 2 * self.h_kv) * self.d_head),
                            grid_dim=_ceil_div(m * (self.h_q + 2 * self.h_kv) * self.d_head, _TG),
                            block_dim=_TG,
                        )
                        issued += 1
                    # ── 7B-dump hook: qkv (fused projection output) ──
                    @parameter
                    if ALGENTA_7B_DUMP:
                        if pos + m == n_prompt:
                            var dg_n = (self.h_q + 2 * self.h_kv) * self.d_head
                            var dg_stg = self.ctx.enqueue_create_buffer[DType.float32](dg_n)
                            var dg_hb = self.ctx.enqueue_create_host_buffer[DType.float32](dg_n)
                            self.ctx.enqueue_function[_dump7b_copy_row_kernel](
                                dg_stg.unsafe_ptr(), self.pf_qkv.unsafe_ptr(),
                                Int64(m - 1), Int64(dg_n),
                                grid_dim=_ceil_div(dg_n, _TG), block_dim=_TG,
                            )
                            self.ctx.enqueue_copy(dg_hb, dg_stg)
                            self.ctx.synchronize()
                            var dp = dg_hb.unsafe_ptr()
                            var dg_sum = Float64(0.0)
                            var dg_max = Float64(0.0)
                            for di in range(dg_n):
                                var dv = Float64(dp[di])
                                dg_sum += dv
                                if abs(dv) > dg_max:
                                    dg_max = abs(dv)
                            print("DUMP7B|" + String(layer) + "|qkv|" + String(dg_n) + "|"
                                  + String(dg_sum) + "|" + String(dg_max) + "|"
                                  + String(Float64(dp[0])) + "|" + String(Float64(dp[1])))
                    # 3 ── q_norm + k_norm + RoPE + the in-place KV-cache write, every row
                    self.ctx.enqueue_function[_pf_ropewrt_kernel](
                        self.pf_q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                        self.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                        self.cos_t.unsafe_ptr(), self.sin_t.unsafe_ptr(),
                        Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                        self.eps, Int64(m),
                        Int64(self.qk_norm),  # qk_norm: runtime flag (Qwen3=1; Qwen2.5/llama=0)
                        grid_dim=(self.h_q + self.h_kv) * m, block_dim=self.d_head,
                    )
                    # ── 7B-dump hook: qrot (rope'd Q heads of the final row) ──
                    @parameter
                    if ALGENTA_7B_DUMP:
                        if pos + m == n_prompt:
                            var dg_n = self.h_q * self.d_head
                            var dg_stg = self.ctx.enqueue_create_buffer[DType.float32](dg_n)
                            var dg_hb = self.ctx.enqueue_create_host_buffer[DType.float32](dg_n)
                            self.ctx.enqueue_function[_dump7b_copy_row_kernel](
                                dg_stg.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                                Int64(m - 1), Int64(dg_n),
                                grid_dim=_ceil_div(dg_n, _TG), block_dim=_TG,
                            )
                            self.ctx.enqueue_copy(dg_hb, dg_stg)
                            self.ctx.synchronize()
                            var dp = dg_hb.unsafe_ptr()
                            var dg_sum = Float64(0.0)
                            var dg_max = Float64(0.0)
                            for di in range(dg_n):
                                var dv = Float64(dp[di])
                                dg_sum += dv
                                if abs(dv) > dg_max:
                                    dg_max = abs(dv)
                            print("DUMP7B|" + String(layer) + "|qrot|" + String(dg_n) + "|"
                                  + String(dg_sum) + "|" + String(dg_max) + "|"
                                  + String(Float64(dp[0])) + "|" + String(Float64(dp[1])))
                    # 4 ── causal attention — the flash-style M-parallel kernel under the
                    # L-H3 flag, the tiled kernel otherwise (byte-unmodified)
                    @parameter
                    if CUDA_PREFILL_FLASH_B1:
                        if self.d_head == 128 and CUDA_PREFILL_FLASH2_B1:
                            self.ctx.enqueue_function[_pf_attn_flash2_kernel](
                                self.pf_attn.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                                lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                                Int64(pos), Int64(self.h_q), Int64(self.h_kv),
                                Int64(self.d_head),
                                self.scale, Int64(m),
                                grid_dim=_ceil_div(m, _PF_FLASH_ROWS_PER_BLOCK) * self.h_q,
                                block_dim=_PF_FLASH_NTHREADS,
                            )
                        elif self.d_head == 128:
                            self.ctx.enqueue_function[_pf_attn_flash_kernel](
                                self.pf_attn.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                                lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                                Int64(pos), Int64(self.h_q), Int64(self.h_kv),
                                Int64(self.d_head),
                                self.scale, Int64(m),
                                grid_dim=_ceil_div(m, _PF_FLASH_ROWS_PER_BLOCK) * self.h_q,
                                block_dim=_PF_FLASH_NTHREADS,
                            )
                        else:
                            self.ctx.enqueue_function[_pf_attn_tiled_kernel_simd](
                                self.pf_attn.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                                lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                                Int64(pos), Int64(self.h_q), Int64(self.h_kv),
                                Int64(self.d_head),
                                self.scale, Int64(m),
                                grid_dim=self.h_q * m, block_dim=self.d_head,
                            )
                    else:
                        self.ctx.enqueue_function[_pf_attn_tiled_kernel_simd](
                            self.pf_attn.unsafe_ptr(), self.pf_q_rot.unsafe_ptr(),
                            lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                            Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head),
                            self.scale, Int64(m),
                            grid_dim=self.h_q * m, block_dim=self.d_head,
                        )
                    # ── 7B-dump hook: attn (attention output, pre o_proj) ──
                    @parameter
                    if ALGENTA_7B_DUMP:
                        if pos + m == n_prompt:
                            var dg_n = self.h_q * self.d_head
                            var dg_stg = self.ctx.enqueue_create_buffer[DType.float32](dg_n)
                            var dg_hb = self.ctx.enqueue_create_host_buffer[DType.float32](dg_n)
                            self.ctx.enqueue_function[_dump7b_copy_row_kernel](
                                dg_stg.unsafe_ptr(), self.pf_attn.unsafe_ptr(),
                                Int64(m - 1), Int64(dg_n),
                                grid_dim=_ceil_div(dg_n, _TG), block_dim=_TG,
                            )
                            self.ctx.enqueue_copy(dg_hb, dg_stg)
                            self.ctx.synchronize()
                            var dp = dg_hb.unsafe_ptr()
                            var dg_sum = Float64(0.0)
                            var dg_max = Float64(0.0)
                            for di in range(dg_n):
                                var dv = Float64(dp[di])
                                dg_sum += dv
                                if abs(dv) > dg_max:
                                    dg_max = abs(dv)
                            print("DUMP7B|" + String(layer) + "|attn|" + String(dg_n) + "|"
                                  + String(dg_sum) + "|" + String(dg_max) + "|"
                                  + String(Float64(dp[0])) + "|" + String(Float64(dp[1])))
                    # 5 ── o_proj ACCUMULATED straight into the residual — TC seam (beta 1)
                    # or the v2 kernel
                    if use_tc:
                        self.ctx.synchronize()
                        var r = _tc_gemm_dispatch(
                            Int(self.pf_attn.unsafe_ptr()),
                            Int(self.w16_o[layer].unsafe_ptr()),
                            Int(lw.w_o.unsafe_ptr()),
                            m, n_q, self.d_model,
                            Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                            Int(self.pf_hidden.unsafe_ptr()), 1)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                    else:
                        self.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                            self.pf_hidden.unsafe_ptr(), self.pf_attn.unsafe_ptr(),
                            lw.w_o.unsafe_ptr(),
                            Int64(m), Int64(n_q), Int64(self.d_model),
                            grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.d_model, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                    # ── 7B-dump hook: post_attn (residual after o_proj) ──
                    @parameter
                    if ALGENTA_7B_DUMP:
                        if pos + m == n_prompt:
                            var dg_n = self.d_model
                            var dg_stg = self.ctx.enqueue_create_buffer[DType.float32](dg_n)
                            var dg_hb = self.ctx.enqueue_create_host_buffer[DType.float32](dg_n)
                            self.ctx.enqueue_function[_dump7b_copy_row_kernel](
                                dg_stg.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                                Int64(m - 1), Int64(dg_n),
                                grid_dim=_ceil_div(dg_n, _TG), block_dim=_TG,
                            )
                            self.ctx.enqueue_copy(dg_hb, dg_stg)
                            self.ctx.synchronize()
                            var dp = dg_hb.unsafe_ptr()
                            var dg_sum = Float64(0.0)
                            var dg_max = Float64(0.0)
                            for di in range(dg_n):
                                var dv = Float64(dp[di])
                                dg_sum += dv
                                if abs(dv) > dg_max:
                                    dg_max = abs(dv)
                            print("DUMP7B|" + String(layer) + "|post_attn|" + String(dg_n) + "|"
                                  + String(dg_sum) + "|" + String(dg_max) + "|"
                                  + String(Float64(dp[0])) + "|" + String(Float64(dp[1])))
                    # 6 ── rmsnorm(post_attention_layernorm) over every row
                    self.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        self.pf_xn.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                        lw.ln2.unsafe_ptr(),
                        Int64(self.d_model), self.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # ── 7B-dump hook: xn2 (post post_attention_layernorm) ──
                    @parameter
                    if ALGENTA_7B_DUMP:
                        if pos + m == n_prompt:
                            var dg_n = self.d_model
                            var dg_stg = self.ctx.enqueue_create_buffer[DType.float32](dg_n)
                            var dg_hb = self.ctx.enqueue_create_host_buffer[DType.float32](dg_n)
                            self.ctx.enqueue_function[_dump7b_copy_row_kernel](
                                dg_stg.unsafe_ptr(), self.pf_xn.unsafe_ptr(),
                                Int64(m - 1), Int64(dg_n),
                                grid_dim=_ceil_div(dg_n, _TG), block_dim=_TG,
                            )
                            self.ctx.enqueue_copy(dg_hb, dg_stg)
                            self.ctx.synchronize()
                            var dp = dg_hb.unsafe_ptr()
                            var dg_sum = Float64(0.0)
                            var dg_max = Float64(0.0)
                            for di in range(dg_n):
                                var dv = Float64(dp[di])
                                dg_sum += dv
                                if abs(dv) > dg_max:
                                    dg_max = abs(dv)
                            print("DUMP7B|" + String(layer) + "|xn2|" + String(dg_n) + "|"
                                  + String(dg_sum) + "|" + String(dg_max) + "|"
                                  + String(Float64(dp[0])) + "|" + String(Float64(dp[1])))
                    # 7 ── gate/up + SwiGLU, one tiled GEMM pair (v2 kernel)
                    if use_tc:
                        # TC seam (ASSIGN into the tc_gu scratch) + native SwiGLU epilogue
                        self.ctx.synchronize()
                        var r = _tc_gemm_dispatch(
                            Int(self.pf_xn.unsafe_ptr()),
                            Int(self.w16_gu[layer].unsafe_ptr()),
                            Int(lw.w_gu.unsafe_ptr()),
                            m, self.d_model, 2 * self.d_ff,
                            Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                            Int(self.tc_gu.unsafe_ptr()), 0)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                        self.ctx.enqueue_function[_pf_swiglu_rows_kernel](
                            self.pf_act.unsafe_ptr(), self.tc_gu.unsafe_ptr(),
                            Int64(m * self.d_ff), Int64(self.d_ff),
                            grid_dim=_ceil_div(m * self.d_ff, _TG), block_dim=_TG,
                        )
                    else:
                        self.ctx.enqueue_function[_pf_gemm_swiglu_kernel_v2](
                            self.pf_act.unsafe_ptr(), self.pf_xn.unsafe_ptr(),
                            lw.w_gu.unsafe_ptr(),
                            Int64(m), Int64(self.d_model), Int64(self.d_ff),
                            grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.d_ff, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                    # ── 7B-dump hook: act (post SwiGLU, pre down_proj) ──
                    @parameter
                    if ALGENTA_7B_DUMP:
                        if pos + m == n_prompt:
                            var dg_n = self.d_ff
                            var dg_stg = self.ctx.enqueue_create_buffer[DType.float32](dg_n)
                            var dg_hb = self.ctx.enqueue_create_host_buffer[DType.float32](dg_n)
                            self.ctx.enqueue_function[_dump7b_copy_row_kernel](
                                dg_stg.unsafe_ptr(), self.pf_act.unsafe_ptr(),
                                Int64(m - 1), Int64(dg_n),
                                grid_dim=_ceil_div(dg_n, _TG), block_dim=_TG,
                            )
                            self.ctx.enqueue_copy(dg_hb, dg_stg)
                            self.ctx.synchronize()
                            var dp = dg_hb.unsafe_ptr()
                            var dg_sum = Float64(0.0)
                            var dg_max = Float64(0.0)
                            for di in range(dg_n):
                                var dv = Float64(dp[di])
                                dg_sum += dv
                                if abs(dv) > dg_max:
                                    dg_max = abs(dv)
                            print("DUMP7B|" + String(layer) + "|act|" + String(dg_n) + "|"
                                  + String(dg_sum) + "|" + String(dg_max) + "|"
                                  + String(Float64(dp[0])) + "|" + String(Float64(dp[1])))
                    # 8 ── down_proj ACCUMULATED straight into the residual — TC seam
                    # (beta 1) or the v2 kernel
                    if use_tc:
                        self.ctx.synchronize()
                        var r = _tc_gemm_dispatch(
                            Int(self.pf_act.unsafe_ptr()),
                            Int(self.w16_down[layer].unsafe_ptr()),
                            Int(lw.w_down.unsafe_ptr()),
                            m, self.d_ff, self.d_model,
                            Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                            Int(self.pf_hidden.unsafe_ptr()), 1)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                    else:
                        self.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                            self.pf_hidden.unsafe_ptr(), self.pf_act.unsafe_ptr(),
                            lw.w_down.unsafe_ptr(),
                            Int64(m), Int64(self.d_ff), Int64(self.d_model),
                            grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.d_model, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                    # ── 7B-dump hook: post_mlp (residual after down_proj) ──
                    @parameter
                    if ALGENTA_7B_DUMP:
                        if pos + m == n_prompt:
                            var dg_n = self.d_model
                            var dg_stg = self.ctx.enqueue_create_buffer[DType.float32](dg_n)
                            var dg_hb = self.ctx.enqueue_create_host_buffer[DType.float32](dg_n)
                            self.ctx.enqueue_function[_dump7b_copy_row_kernel](
                                dg_stg.unsafe_ptr(), self.pf_hidden.unsafe_ptr(),
                                Int64(m - 1), Int64(dg_n),
                                grid_dim=_ceil_div(dg_n, _TG), block_dim=_TG,
                            )
                            self.ctx.enqueue_copy(dg_hb, dg_stg)
                            self.ctx.synchronize()
                            var dp = dg_hb.unsafe_ptr()
                            var dg_sum = Float64(0.0)
                            var dg_max = Float64(0.0)
                            for di in range(dg_n):
                                var dv = Float64(dp[di])
                                dg_sum += dv
                                if abs(dv) > dg_max:
                                    dg_max = abs(dv)
                            print("DUMP7B|" + String(layer) + "|post_mlp|" + String(dg_n) + "|"
                                  + String(dg_sum) + "|" + String(dg_max) + "|"
                                  + String(Float64(dp[0])) + "|" + String(Float64(dp[1])))
                    issued += 8
                pos += m

            # ── final rmsnorm + lm_head + per-threadgroup argmax on the LAST row only ──
            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
            var lm_w = self.lm_head_w()
            self.ctx.enqueue_function[_lmhead_argmax_kernel](
                self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(),
                self.pf_hidden.unsafe_ptr() + (last_m - 1) * self.d_model,
                self.final_norm.unsafe_ptr(), lm_w,
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
            if self.skip_f32_projections == 1:
                # 7B memory fit: decode runs through the composed packed3 session's chain.
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
                # 1b ── 7B-lane attention bias: q/k/v biases onto the QKV output BEFORE RoPE
                # (dispatched only when the session carries biases; a Qwen3 session never
                # reaches this launch).
                if self.has_qkv_bias == 1:
                    self.ctx.enqueue_function[_qkv_bias_add_rows_kernel](
                        self.qkv.unsafe_ptr(), self.qkv_biases[layer].unsafe_ptr(),
                        Int64(1), Int64(n_qkv),
                        grid_dim=_ceil_div(n_qkv, _TG), block_dim=_TG,
                    )
                    issued += 1
                # 2 ── q_norm + k_norm + RoPE + the in-place KV-cache slot write
                self.ctx.enqueue_function[_qk_rope_write_kernel](
                    self.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    self.qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                    self.cos_t.unsafe_ptr(), self.sin_t.unsafe_ptr(),
                    Int64(pos), Int64(self.h_q), Int64(self.h_kv), Int64(self.d_head), self.eps,
                    Int64(self.qk_norm),  # qk_norm: runtime flag (Qwen3=1; Qwen2.5/llama=0)
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
            var lm_w = self.lm_head_w()
            self.ctx.enqueue_function[_lmhead_argmax_kernel](
                self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(), self.hidden.unsafe_ptr(),
                self.final_norm.unsafe_ptr(), lm_w,
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
        var qkv_bias_as = List[Int]()
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
            qkv_bias_as.append(Int(self.qkv_biases[layer].unsafe_ptr()))

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
        # 7B-lane: the lm_head the captured tail binds (separate table vs tied embed) and the
        # qk_norm flag the ropewrt twin reads — both hoisted like every other capture scalar.
        var lm_w_a = Int(self.lm_head_w())
        var qk_norm_c = Int64(self.qk_norm)
        var has_qkv_bias_c = self.has_qkv_bias

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
            var lm_w_p = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=lm_w_a)

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
                # 1b ── 7B-lane attention bias (captured only when the session carries biases)
                if has_qkv_bias_c == 1:
                    var qkv_bias_p = UnsafePointer[Float32, origin=MutAnyOrigin](
                        unsafe_from_address=qkv_bias_as[layer]
                    )
                    rec.enqueue_function[_qkv_bias_add_rows_kernel](
                        qkv_p, qkv_bias_p, Int64(1), n_qkv_i,
                        grid_dim=_ceil_div(Int(n_qkv_i), _TG), block_dim=_TG,
                    )
                # 2 ── q_norm + k_norm + RoPE + the in-place KV-cache slot write (pos: state[1])
                rec.enqueue_function[_qk_rope_write_kernel_g](
                    q_rot_p, ck_p, cv_p,
                    qkv_p, qn_p, kn_p,
                    cos_p, sin_p,
                    state_p, h_q_i, h_kv_i, d_head_i, eps_c,
                    qk_norm_c,  # qk_norm: runtime flag (Qwen3=1; Qwen2.5/llama=0)
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
                final_norm_p, lm_w_p,
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
            if self.skip_f32_projections == 1:
                # 7B memory fit: the f32 graph arm needs the f32 projections resident.
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
