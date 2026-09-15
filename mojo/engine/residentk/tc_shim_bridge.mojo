"""
residentk.tc_shim_bridge — the Mojo-side half of the NVIDIA tensor-core escape hatch the
feat/tc-probe round PROVED (REALRACE_RESULTS.md, "THE TENSOR-CORE ESCAPE HATCH", 2026-08-23):
the FFI wrappers over `benchmarks/llm_smoke/nvidia_race/tc_shim.cu`'s extern "C" ABI, the
comptime build gate (`-D ALGENTA_TC_SHIM`), and the ONE native epilogue the integration adds
(the SwiGLU combine the fused v2 GEMM used to do in-kernel). Zero session logic lives here —
`residentk.session_cuda_p3` and `residentk.session_cuda_batched` dispatch these wrappers
behind `TC_SHIM_BUILD`; every other build compiles this module to inert stubs.

NOT a contract module. Everything is private, and every `external_call` expression lives
inside a `@parameter if TC_SHIM_BUILD` branch: a build WITHOUT `-D ALGENTA_TC_SHIM` lowers NO
extern declarations, so its link line stays byte-unmodified (no tc_shim.o, no -lcublas) and
its binary never references the shim.

THE SYNC SEAM (the probe's measured interop model, carried verbatim into the integration)
------------------------------------------------------------------------------------------
MAX 26.5's DeviceContext/DeviceStream surface exposes no raw cudaStream_t, so there is no
stream-ordered handoff between Mojo-enqueued kernels and the shim's own cuBLAS stream. The
seam the sessions implement around every TC GEMM: `ctx.synchronize()` (drain Mojo's stream)
-> wrapper call (the shim converts, runs GemmEx on its own non-blocking stream, and
cudaStreamSynchronize's before returning) -> the session enqueues the next Mojo kernels.
Device-sync cost per GEMM is host-side microseconds; the probe measured the per-call GEMM
savings at 4-24x the v2 kernel cost at the raced shapes, so the seam is noise in the sum.
The ABI keeps `tc_shim_use_stream` ready for a MAX release that exposes stream handles.

UPDATE (gemma3 lane, 2026-08-24): the seam is ABOLISHED without any MAX stream handle at
all. Mojo 1.0.0 did ship `create_external_stream(Pointer[NoneType]) -> DeviceStream`, but
the wrapped DeviceStream carries no kernel launcher (measured, ext_stream_probe2.mojo) and
the external stream never joins the pool `select_stream` addresses — so the lane ships the
LEGACY-STREAM interop instead: `_tc_use_legacy_stream` binds the cuBLAS handle to the CUDA
legacy default stream, which the H100 probe (legacy_probe.mojo) proved is device-ordered
against Mojo's default stream in BOTH directions with zero host syncs. Sessions under
`-D ALGENTA_G3_STREAM` keep their ordinary `ctx` enqueues, dispatch
`_tc_gemm_dispatch_async` (zero syncs inside) at every seam, and drop the per-GEMM
`ctx.synchronize()` too — one stream-ordered pipeline, ONE sync per step (the token
readback), 496 device syncs per 27B decode step removed.

THE GEMM LAYOUT CONTRACT (tc_shim.cu's header, restated)
--------------------------------------------------------
`C[M,N] = A[M,K] @ W[N,K]^T`, ALL row-major — the exact residentk convention the v2 prefill
kernels use (`y[M,n] = xn[M,k] @ W^T[k,n]`, `w` stored `[n,k]`). The integration entries:

* `tc_shim_gemm_f16_32c(a_f32, w_f16, M, K, N, a16_scratch, c_f32, accum)` — THE workhorse:
  A converted f32->f16 into the caller's scratch, GemmEx with f16 A/B, f32 C output and
  CUBLAS_COMPUTE_32F (HMMA with an f32 accumulator), `accum` selecting beta 0 (ASSIGN) or
  beta 1 (ACCUMULATE into the existing f32 residual — the o_proj/down_proj feed, done by
  cuBLAS at f32 precision). The probe's rel distance vs an f64 oracle for this compute mode:
  1.0e-3 (gate 1e-2) — the ship candidate.
* `tc_shim_gemm_tf32_beta(a_f32, w_f32, M, K, N, c_f32, accum)` — fallback ladder rung 2:
  TF32, f32 weights DIRECTLY (zero dual residency), same beta select.
* `tc_shim_gemm_f16_acc16(...)` — fallback ladder rung 3: COMPUTE_16F with a staged f16 C
  (rounds the residual through f16; last resort).
* `tc_shim_dequant_packed3_f16_dense(words, scales, zeros, out_f16, n_rows, k,
  words_per_row, blocks_per_row)` — the one-time session-open weight staging: packed3 ->
  DENSE f16 `[n_rows, k]` (the packed tail dropped, so the GEMM runs at the natural K).
* `tc_shim_f32_to_f16(src, dst, n)` — the weight staging for sessions whose f32 projections
  ARE resident (the batched serve session converts them directly instead of dequantizing).
* `tc_shim_init` / `tc_shim_last_error` / `tc_shim_shutdown` — handle lifecycle; init binds
  the shim to the CURRENT context (Mojo's), proven shared by the probe's correctness runs.

The compute mode shipped is selected by `TC_ACC_MODE` below (0 = 32F/f32-C, the ship
candidate; 1 = TF32; 2 = 16F-accum) — the gate battery's token-identity result decides
whether a fallback rung ever ships; mode != 0 exists ONLY as the brief's contingency ladder.

SwiGLU epilogue
---------------
The v2 chain fuses gate/up GEMM + SwiGLU in one kernel; the TC chain runs ONE GemmEx over
the concatenated `[2*d_ff, d_model]` gate/up table into a `[m, 2*d_ff]` f32 scratch, then
dispatches `_pf_swiglu_rows_kernel` for the combine — the SAME `swish(gate) * up` convention
the fused kernel applies (backwards would generate different text), row-elementwise, so the
epilogue is exact regardless of the GEMM's compute mode.

@capability-module
deterministic: true
stateful: false
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32, float16
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/tc_escape_probe.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/tc_escape_probe.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability
"""

from std.gpu import block_idx, block_dim, thread_idx
from std.math import exp
from std.sys import is_defined
from std.ffi import external_call
from std.origin import MutAnyOrigin
from residentk.session import RESIDENT_GPU_BUILD

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — `residentk.kernels`' spelling."""

comptime TC_SHIM_BUILD: Bool = (
    RESIDENT_GPU_BUILD and is_defined["ALGENTA_CUDA"]() and is_defined["ALGENTA_TC_SHIM"]()
)
"""Whether this binary was built with `-D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_TC_SHIM`
(DEFAULT OFF) — the same conjunct `residentk.session_cuda.CUDA_SESSION_BUILD` carries, plus
the TC selector, defined HERE (not imported from session_cuda) so the session modules can
import this one without a module cycle. With the flag absent every wrapper in this module is
an inert stub lowered to constant error returns and NO extern symbol is emitted — the
non-TC build's link line and binary stay byte-unmodified."""

comptime TC_MIN_M: Int = 128
"""The prefill tile-row threshold below which a tile stays on the native v2 f32 chain: the
probe battery measured the TC seam's win margin collapse toward small M (cuBLAS tile fill +
the per-call sync seam amortize poorly), and the campaign brief fixes ~128 as the crossover.
RUNTIME check (not comptime) because a prompt's FINAL tile is whatever rows remain — a
runtime branch dispatches that tail tile through the native plan while every full tile rides
the TC seam. Documented choice per the brief's "threshold comptime or runtime, document"."""

comptime TC_ACC_MODE: Int = 0
"""The TC compute mode the sessions dispatch: 0 = f16 HMMA with CUBLAS_COMPUTE_32F +
f32 C output (the ship candidate; probe rel 1.0e-3 vs f64), 1 = TF32 (f32 weights direct —
requires the f32 projections resident), 2 = f16 with COMPUTE_16F accumulation (f16 C
staging). The gate battery's token identity decides; if mode 0 fails on any gate prompt the
round re-runs the ladder in order and ships the FIRST mode that passes — or nothing."""

comptime TC_NOSEAM: Bool = TC_SHIM_BUILD and is_defined["ALGENTA_TC_NOSEAM"]()
"""The sync-seam eliminator (-D ALGENTA_TC_NOSEAM, DEFAULT OFF, meaningful only under
TC_SHIM_BUILD): at session open the session calls `_tc_noseam(1)`, which repoints the shim's
cuBLAS handle AND its conversion-kernel launches onto the LEGACY DEFAULT stream and skips
every per-call cudaStreamSynchronize; the session in turn skips the bracketing
ctx.synchronize() around each TC GEMM. Ordering then rides the CUDA legacy-stream contract
(legacy-stream work serializes with every blocking stream of the context). The probe's seam
stayed the ship default because MAX 26.5 exposes no stream handle to prove the runtime's
stream type a priori — the token-identity gates are the proof instead: if the runtime stream
is non-blocking the gates catch the race; if it is blocking/legacy the per-GEMM sync bubble
(2 full device drains per GEMM role per layer) disappears."""


def _tc_noseam(on: Int) -> Int:
    """Switch the shim's integration entries into (on=1) or out of (on=0) NOSEAM mode —
    the legacy default stream + no per-call sync (see TC_NOSEAM). Call ONCE at session open
    after `_tc_init`; 0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(external_call["tc_shim_noseam", Int64](Int64(on)))
    else:
        return -1


def _tc_init() -> Int:
    """Create the shim's cuBLAS handle + dedicated non-blocking stream on the CURRENT
    (Mojo's) context. Idempotent. 0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(external_call["tc_shim_init", Int64]())
    else:
        return -1


def _tc_create_stream() -> Int:
    """Stream factory (gemma3 lane, 2026-08-24): create a NEW non-blocking cudaStream_t on
    the current context, bind the cuBLAS handle to it, return the raw pointer as an Int
    (0 = failure, check `_tc_last_error`). Probed + WORKING, but NOT the shipped interop:
    MAX 1.0.0's `create_external_stream` wraps the pointer into a `DeviceStream` whose
    surface carries NO kernel launcher (measured: no enqueue_kernel/launch/submit/
    enqueue_copy on the value; its `enqueue_function` is the DeviceExternalFunction entry),
    and the external stream does NOT join the context pool `select_stream` addresses. The
    lane ships the legacy-stream ordering below instead; this entry stays for a MAX release
    whose DeviceStream grows a launch surface. Initializes the handle if needed."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(external_call["tc_shim_create_stream", Int64]())
    else:
        return 0


def _tc_use_legacy_stream() -> Int:
    """THE shipped stream-ordered seam (gemma3 lane, 2026-08-24): bind the cuBLAS handle
    (and all shim-internal launches) to the CUDA LEGACY default stream. PROBE-PROVEN on the
    H100 VM (legacy_probe.mojo): Mojo's DeviceContext default stream is device-ordered
    against the legacy stream in BOTH directions (the implicit serialization blocking
    streams have with it) — a 100-iteration Mojo-kernel/legacy-GemmEx/Mojo-kernel chain
    with ZERO host syncs runs data-correct at ~6 us seam cost. With this binding, sessions
    dispatch `_tc_gemm_dispatch_async` (no internal sync) straight between their ordinary
    `ctx` enqueues and drop BOTH halves of the old per-GEMM seam (the ctx.synchronize()
    before AND the cudaStreamSynchronize inside) — 496 device syncs per 27B decode step
    removed. 0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call["tc_shim_use_stream", Int64, Int64](Int64(1))
        )
    else:
        return -1


def _tc_gemm_f16_32c_async(a: Int, w16: Int, m: Int, k: Int, n: Int, a16: Int, c32: Int,
                          accum: Int) -> Int:
    """The ASYNC twin of `_tc_gemm_f16_32c`: same compute (f16 HMMA, COMPUTE_32F, f32 C
    direct, beta by `accum`), zero syncs — the A-convert kernel and the GemmEx enqueue on
    the shim stream and the call returns at once. ONLY legal when the session's Mojo
    enqueues ride the SAME stream the shim is bound to (`_tc_create_stream` + the wrapped
    DeviceStream); the caller owns the single eventual sync. 0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_gemm_f16_32c_async", Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64, Int64,
            ](Int64(a), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(a16), Int64(c32),
              Int64(accum))
        )
    else:
        return -1


def _tc_gemm_f16_32c_pre(a16: Int, w16: Int, m: Int, k: Int, n: Int, c32: Int,
                        accum: Int) -> Int:
    """`C[M,N](f32) = A[M,K](ALREADY f16) @ W[N,K](f16)^T`, COMPUTE_32F, beta by `accum` —
    `_tc_gemm_f16_32c` MINUS its per-call f32->f16 A conversion. The caller asserts A is
    f16 by having its PRODUCER kernel write f16 in the first place (the `-D
    ALGENTA_7B_PF_F16NORM` / `_F16MLP` levers: the rmsnorm rows kernel and the SwiGLU
    epilogue write the f16 the shim would otherwise have produced from their f32, at the
    identical rounded value, saving 6 bytes of global traffic per A element per GEMM).
    Honours the shim's NOSEAM mode exactly like `_tc_gemm_f16_32c` (no internal sync when
    the shim is bound to the legacy stream; the caller's bracketing synchronize() discipline
    is unchanged). 0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_gemm_f16_32c_pre", Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64,
            ](Int64(a16), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(c32),
              Int64(accum))
        )
    else:
        return -1


def _tc_gemm_f16_16c_pre(a16: Int, w16: Int, m: Int, k: Int, n: Int, c16: Int,
                        accum: Int) -> Int:
    """The f16-C twin of `_tc_gemm_f16_32c_pre`: A already f16, W f16, HMMA with an f32
    ACCUMULATOR (COMPUTE_32F) but C written as f16. Used for the gate/up GEMM under `-D
    ALGENTA_7B_PF_F16MLP`, where the `[m, 2*d_ff]` result is read straight back by the
    SwiGLU epilogue — halving both the write and the read of the layer's largest non-GEMM
    traffic term (155 MB -> 77 MB at m=1024, d_ff=18944). NOT bit-identical to the f32-C
    path (the epilogue's inputs round to f16 at the GEMM epilogue instead of after it), so
    it carries its own build flag and its own token-identity gate. 0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_gemm_f16_16c_pre", Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64,
            ](Int64(a16), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(c16),
              Int64(accum))
        )
    else:
        return -1


def _tc_last_error() -> Int:
    """The shim's last recorded error (raw cudaError_t/cublasStatus_t, or a negative
    shim-defined class) — diagnostics when a wrapper returns non-zero."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(external_call["tc_shim_last_error", Int64]())
    else:
        return -1


def _tc_stage_f32_to_f16(src: Int, dst: Int, n: Int) -> Int:
    """One-shot device-side f32 -> f16 conversion of `n` elements (weight staging for
    sessions that hold f32 projections). Launches on the shim stream; the entry does NOT
    sync — the caller owns the seam (the staging battery runs once at session open, before
    the first dispatch)."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call["tc_shim_f32_to_f16", Int64, Int64, Int64, Int64](
                Int64(src), Int64(dst), Int64(n))
        )
    else:
        return -1


def _tc_gemm_f16_32c(a: Int, w16: Int, m: Int, k: Int, n: Int, a16: Int, c32: Int,
                    accum: Int) -> Int:
    """THE integration GEMM: C[M,N](f32) = A[M,K](f32) @ W[N,K](f16)^T, CUBLAS_COMPUTE_32F,
    f32 C written DIRECTLY; `accum`=0 assigns, `accum`=1 accumulates into the existing f32
    C. Syncs the shim stream before returning (the seam). 0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_gemm_f16_32c", Int64, Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64,
            ](Int64(a), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(a16), Int64(c32),
              Int64(accum))
        )
    else:
        return -1


def _tc_gemm_tf32_beta(a: Int, w32: Int, m: Int, k: Int, n: Int, c32: Int, accum: Int) -> Int:
    """Fallback rung 2: TF32 GEMM, f32 in/out DIRECTLY, same beta select."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_gemm_tf32_beta", Int64, Int64, Int64, Int64, Int64, Int64, Int64,
                Int64,
            ](Int64(a), Int64(w32), Int64(m), Int64(k), Int64(n), Int64(c32), Int64(accum))
        )
    else:
        return -1


def _tc_gemm_f16_acc16(a: Int, w16: Int, m: Int, k: Int, n: Int, a16: Int, c16: Int,
                      c32: Int) -> Int:
    """Fallback rung 3: f16 HMMA with COMPUTE_16F — the residual is staged through f16 C
    (documented precision loss), beta fixed at 1 (accumulate form only)."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_gemm_f16_acc16", Int64, Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64,
            ](Int64(a), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(a16), Int64(c16),
              Int64(c32))
        )
    else:
        return -1


def _tc_dequant_packed3_f16_dense(words: Int, scales: Int, zeros: Int, out16: Int,
                                 rows: Int, k: Int, words_per_row: Int,
                                 blocks_per_row: Int) -> Int:
    """One-time packed3 -> DENSE f16 `[rows, k]` dequant (session-open weight staging).
    Syncs the shim stream before returning."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_dequant_packed3_f16_dense", Int64, Int64, Int64, Int64, Int64,
                Int64, Int64, Int64, Int64,
            ](Int64(words), Int64(scales), Int64(zeros), Int64(out16), Int64(rows),
              Int64(k), Int64(words_per_row), Int64(blocks_per_row))
        )
    else:
        return -1


def _tc_gemm_dispatch(a: Int, w16: Int, w32_fallback: Int, m: Int, k: Int, n: Int,
                     a16: Int, c16: Int, c32: Int, accum: Int) -> Int:
    """The ONE call the sessions make for a TC prefill GEMM — routes to the entry the
    comptime `TC_ACC_MODE` selects, so the fallback ladder is a rebuild, not a rewrite.
    `w32_fallback` is the f32 weight address rung 1 (TF32) reads (the f16-resident sessions
    pass 0 and must never select that rung)."""
    @parameter
    if TC_ACC_MODE == 1:
        return _tc_gemm_tf32_beta(a, w32_fallback, m, k, n, c32, accum)
    elif TC_ACC_MODE == 2:
        if accum != 0:
            return _tc_gemm_f16_acc16(a, w16, m, k, n, a16, c16, c32)
        # ASSIGN under rung 2: the probe's original f16-C seam (beta 0) + its f32 convert.
        return _tc_gemm_f16_assign(a, w16, m, k, n, a16, c16, c32)
    else:
        return _tc_gemm_f16_32c(a, w16, m, k, n, a16, c32, accum)


def _tc_gemm_dispatch_async(a: Int, w16: Int, w32_fallback: Int, m: Int, k: Int, n: Int,
                           a16: Int, c16: Int, c32: Int, accum: Int) -> Int:
    """The stream-ordered twin of `_tc_gemm_dispatch` (gemma3 lane): routes to the ASYNC
    entry the comptime `TC_ACC_MODE` selects. Mode 0 (the shipped mode) dispatches
    `_tc_gemm_f16_32c_async`; the fallback rungs have no async twins (their ladder exists
    only for a token-gate failure that never happened), so they dispatch their SYNC forms —
    correct but seam-bearing, and only reachable by a rebuild that changes TC_ACC_MODE."""
    @parameter
    if TC_ACC_MODE == 1:
        return _tc_gemm_tf32_beta(a, w32_fallback, m, k, n, c32, accum)
    elif TC_ACC_MODE == 2:
        if accum != 0:
            return _tc_gemm_f16_acc16(a, w16, m, k, n, a16, c16, c32)
        return _tc_gemm_f16_assign(a, w16, m, k, n, a16, c16, c32)
    else:
        return _tc_gemm_f16_32c_async(a, w16, m, k, n, a16, c32, accum)


comptime G3_STREAM_ORDER: Bool = TC_SHIM_BUILD and is_defined["ALGENTA_G3_STREAM"]()
"""The bridge's own read of the `-D ALGENTA_G3_STREAM` define (the sessions gate their
seam syncs on the same define; both always agree within one binary)."""


def _tc_gemm_dispatch_auto(a: Int, w16: Int, w32_fallback: Int, m: Int, k: Int, n: Int,
                          a16: Int, c16: Int, c32: Int, accum: Int) -> Int:
    """THE one seam call the G3_STREAM sessions make: ASYNC dispatch under
    `-D ALGENTA_G3_STREAM` (legacy-stream-bound handle, zero syncs — the caller must have
    skipped its own pre-seam `ctx.synchronize()` too), the ordinary SYNC dispatch in every
    other build. Same args, same routing ladder as `_tc_gemm_dispatch`."""
    @parameter
    if G3_STREAM_ORDER:
        return _tc_gemm_dispatch_async(a, w16, w32_fallback, m, k, n, a16, c16, c32, accum)
    else:
        return _tc_gemm_dispatch(a, w16, w32_fallback, m, k, n, a16, c16, c32, accum)


def _tc_bgemm_f16_async(a16: Int, b16: Int, c32: Int, m: Int, n: Int, k: Int,
                        ld_a: Int, ld_b: Int, ld_c: Int,
                        stride_a: Int, stride_b: Int, stride_c: Int,
                        batch: Int, trans_b: Int) -> Int:
    """Strided-batched f16 tensor-core GEMM with f32 output, COMPUTE_32F, ASYNC (the
    tensor-core prefill-attention lever). Row-major semantics: `trans_b=1` computes
    `C[M,N] = A[M,K] @ B[N,K]^T` (the QK^T case, B in weights layout); `trans_b=0` computes
    `C[M,N] = A[M,K] @ B[K,N]` (the PV case). `ld_*` are row strides, `stride_*` per-batch
    offsets. Enqueues on the shim stream and returns without syncing (G3_STREAM contract).
    0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_bgemm_f16_async", Int64, Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64,
            ](Int64(a16), Int64(b16), Int64(c32), Int64(m), Int64(n), Int64(k),
              Int64(ld_a), Int64(ld_b), Int64(ld_c), Int64(stride_a), Int64(stride_b),
              Int64(stride_c), Int64(batch), Int64(trans_b))
        )
    else:
        return -1


def _tc_attn_softmax_mask_async(s32: Int, p16: Int, n_keys: Int, m_rows: Int, h_q: Int,
                                pos_base: Int, window: Int) -> Int:
    """Masked causal+window softmax over the QK^T score rows -> f16 attention weights, ASYNC
    (the tensor-core prefill-attention lever's middle stage). One block per (head, position)
    row; key j attended iff j <= pos_base+p and (window <= 0 or j >= pos_base+p+1-window).
    Enqueues on the shim stream, no sync. 0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_attn_softmax_mask_async", Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64,
            ](Int64(s32), Int64(p16), Int64(n_keys), Int64(m_rows), Int64(h_q),
              Int64(pos_base), Int64(window))
        )
    else:
        return -1


def _tc_gemm_f16_assign(a: Int, w16: Int, m: Int, k: Int, n: Int, a16: Int, c16: Int,
                      c32: Int) -> Int:
    """The probe's original ASSIGN seam (f16-C GemmEx + f32 out-convert), rung-2 ASSIGN
    form only."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_gemm_f16", Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64,
            ](Int64(a), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(a16), Int64(c16),
              Int64(c32), Int64(1))
        )
    else:
        return -1


def _pf_swiglu_rows_kernel(act: _FP, gu: _FP, total_i64: Int64, n_ff_i64: Int64):
    """`act[row, j] = swish(gu[row, j]) * gu[row, n_ff + j]` over `m * n_ff` outputs — the
    native epilogue the TC gu GEMM hands its `[m, 2*d_ff]` result to (gate columns
    `0 .. n_ff`, up columns `n_ff .. 2*n_ff`, the concatenation order the packed `[2*d_ff,
    d_model]` gate/up table guarantees). The SAME `swish(gate) * up` expression the fused
    `_pf_gemm_swiglu_kernel_v2` applies in-kernel, elementwise-exact against whatever the
    GEMM produced. Grid: `ceil(m * n_ff / _TG)`, block `_TG` — dispatched with those shapes
    by the sessions (`residentk.kernels._TG`)."""
    var total = Int(total_i64)
    var n_ff = Int(n_ff_i64)
    var i = Int(block_idx.x) * Int(block_dim.x) + Int(thread_idx.x)
    if i < total:
        var row = i // n_ff
        var j = i - row * n_ff
        var g = gu[row * 2 * n_ff + j]
        var u = gu[row * 2 * n_ff + n_ff + j]
        act[i] = (g / (1.0 + exp(-g))) * u
