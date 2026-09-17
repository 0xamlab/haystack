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


def _tc_lt_init(workspace_bytes: Int) -> Int:
    """FRONT 6 lever 2 (`-D ALGENTA_7B_PF_LTALGO`): create the shim's cublasLt handle and its
    algorithm workspace. Called ONCE from `_tc_stage_weights`'s headroom try, so a device that
    cannot hold the workspace demotes the whole TC plan with a printed record instead of
    half-enabling the lever. 0 = success; -322 = cublasLtCreate failed or the shim object was
    built WITHOUT `ALGENTA_TC_SHIM_LT` (the stock object carries a stub), in which case every
    `_tc_gemm_*_pre_lt` below declines and the session runs the shipped GemmEx path."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(external_call["tc_shim_lt_init", Int64, Int64](Int64(workspace_bytes)))
    else:
        return -1


def _tc_lt_tune(a16: Int, w16: Int, c: Int, m: Int, k: Int, n: Int, c16: Int, accum: Int,
                top: Int, iters: Int) -> Int:
    """Time the top-`top` cublasLt heuristics for ONE (M, K, N, C-dtype, beta) shape and cache
    the winner, so every later dispatch of that shape skips cublasGemmEx's per-call
    CUBLAS_GEMM_DEFAULT heuristic. A TIMED SEARCH, not heuristic result[0]: the heuristic's
    ranking is an estimate and gemm_probe measured winners that were not index 0.

    `c` is SCRATCH and IS WRITTEN (beta is honoured, so an accumulate role accumulates into it
    `iters` times). Pass a buffer the caller is about to overwrite anyway — the session passes
    each role's own prefill destination, all of which the next prefill rewrites before reading.
    Returns the winning heuristic index (>= 0), or negative: -320 not built with the LT macro,
    -322 no handle, -323 cache full, -324 no heuristic returned, -326 no algo could execute."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_lt_tune", Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64, Int64,
            ](Int64(a16), Int64(w16), Int64(c), Int64(m), Int64(k), Int64(n), Int64(c16),
              Int64(accum), Int64(top), Int64(iters))
        )
    else:
        return -1


def _tc_gemm_f16_32c_pre_lt(a16: Int, w16: Int, m: Int, k: Int, n: Int, c32: Int,
                            accum: Int) -> Int:
    """`_tc_gemm_f16_32c_pre` on the shape's TUNED cublasLt algorithm. **-320 means this shape
    was never tuned and the caller MUST decline to `_tc_gemm_f16_32c_pre`** — that is what keeps
    an untuned M (any prompt whose first pass is not the tuned one) on byte-for-byte the shipped
    code path, so the lever can only ever change the shape it was measured on. NOT bit-identical
    to the GemmEx path when the tuned algo splits K or tiles differently: the reduction order
    moves, so the f32 accumulator rounds differently, and the token gates decide it."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_gemm_f16_32c_pre_lt", Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64,
            ](Int64(a16), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(c32),
              Int64(accum))
        )
    else:
        return -1


def _tc_gemm_f16_16c_pre_lt(a16: Int, w16: Int, m: Int, k: Int, n: Int, c16: Int,
                            accum: Int) -> Int:
    """The f16-C twin of `_tc_gemm_f16_32c_pre_lt` (the gate/up role under `-D
    ALGENTA_7B_PF_F16MLP`). Same -320 decline contract."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_gemm_f16_16c_pre_lt", Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64,
            ](Int64(a16), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(c16),
              Int64(accum))
        )
    else:
        return -1


def _tc_lt_count() -> Int:
    """How many shapes the shim has tuned. Printed in the flag-audit banner so a binary that
    claims the lever can be checked against the number of shapes it actually tuned (0 = the
    lever silently declined everywhere, which a flag literal alone would not reveal)."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(external_call["tc_shim_lt_count", Int64]())
    else:
        return 0


# ── FRONT 7 (2026-09-16): the f16 O twin and the in-situ algorithm search ───────────────────
#
# Both blocks below are compiled into the shim ONLY under their own macros
# (`ALGENTA_TC_SHIM_O16`, `ALGENTA_TC_SHIM_LTINSITU`) and have deliberately NO stubs, so an arm
# that passes the Mojo flag but links an object built without the macro fails AT LINK TIME. That
# is the property FRONT 6 paid for: a silent runtime decline would leave a cell measured on the
# shipped path while still printing the flag — the gemma-3-27b H200 column's failure mode.


def _tc_fa2_causal_o16_async(
    q_f32: Int, k16: Int, v16: Int, o_f32: Int, o16: Int, scale_f32: Int, m: Int, n_keys: Int,
    h_q: Int, h_kv: Int, d_head: Int, pos: Int, bn: Int, variant: Int, rev_rows: Int,
) -> Int:
    """FRONT 7 lever 1 (`-D ALGENTA_7B_PF_O16TWIN`): `_tc_fa2_causal_async` with the O epilogue
    writing the position-major f16 twin that `_tc_gemm_f16_32c_pre` consumes directly, so o_proj
    — the one projection whose A was still f32 — needs no convert pass at all.

    `o16` is the twin (`tc_a16`, row stride `h_q * d_head` HALVES, i.e. the identical layout the
    convert produced). `o_f32` MAY BE 0, which is the ship arm: the f32 O is then never written,
    because nothing else in the FA2 path reads it, and halving that write is part of the lever.
    The verify arm (`-D ALGENTA_7B_PF_O16VERIFY`) passes a real `pf_attn` so `_tc_verify_o16`
    has something to compare the twin against, element by element, as bits.

    `rev_rows` reverses the row-block dispatch order (heaviest-CTA-first). Bit-exact either way:
    each CTA computes its own rows and reads no other CTA's output.

    BIT-EXACT against the pass it replaces, by FRONT 4's KVTWIN argument: `__floats2half2_rn`
    rounds each component to nearest-even independently — the identical operation `__float2half`
    performs — on the SAME f32 accumulator register the f32 store would have written for the
    convert kernel to read back. Proven full-element rather than argued; see `_tc_verify_o16`.

    Returns 0, or the same decline codes `_tc_fa2_causal_async` returns (-301 wrong head_dim,
    -304 non-integral GQA, -305 the shared-memory overlay does not fit, -311 the on-device layout
    probe disagreed) plus -306 (no twin buffer). A decline MUST fall back to the f32 entry and
    hence to the shipped convert; any other status is a real CUDA failure."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_fa2_causal_o16_async", Int64, Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64,
            ](
                Int64(q_f32), Int64(k16), Int64(v16), Int64(o_f32), Int64(o16), Int64(scale_f32),
                Int64(m), Int64(n_keys), Int64(h_q), Int64(h_kv), Int64(d_head), Int64(pos),
                Int64(bn), Int64(variant), Int64(rev_rows),
            )
        )
    else:
        return -1


def _tc_verify_o16(o_f32: Int, o16: Int, n: Int) -> Int:
    """Accumulate a FULL-ELEMENT bit comparison of the f16 O twin against `__float2half` of the
    f32 O, over `n` elements, into device counters. Compared as BITS (`__half_as_ushort`), not as
    values, so +0.0/-0.0 and any NaN payload count as mismatches instead of comparing equal —
    "bit-identical" is a claim about bit patterns, so the proof has to test that claim.

    Called once per layer by the verify arm; nothing is printed until `_tc_verify_o16_report`.
    0 = enqueued; -307 = a null operand (a FAILED proof, never a passed one); -308 = the device
    counters could not be allocated."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call["tc_shim_verify_o16", Int64, Int64, Int64, Int64](
                Int64(o_f32), Int64(o16), Int64(n)
            )
        )
    else:
        return -1


def _tc_verify_o16_report() -> Int:
    """Sync, print `TC O16 VERIFY: mismatches = X of Y elements compared | verdict = ...`,
    return X and reset the counters, so the next call reports the next prefill rather than a
    running total nobody can attribute to a layer range. A NEGATIVE return (-309, the counters
    could not be read back) is a FAILED PROOF and must never be reported as zero mismatches."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(external_call["tc_shim_verify_o16_report", Int64]())
    else:
        return -1


def _tc_lt_explore_begin(samples_per_cand: Int) -> Int:
    """FRONT 7 lever 3 (`-D ALGENTA_7B_PF_LTINSITU`): arm the IN-SITU algorithm search. Every
    later projection dispatch rotates through the candidate list `_tc_lt_tune` retained, timing
    each candidate with a stream event pair in its REAL position in the layer chain, until each
    candidate has `samples_per_cand` medians; the shape then freezes itself on the best median.

    Called by the driver AFTER its token gates and BEFORE its warmup loop, so G0/G1 gate exactly
    the algorithm FRONT 6's arm ran and every exploring call is in situ. Returns the number of
    shapes armed (0 = nothing to explore, and the arm then runs FRONT 6's stage-time winners)."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call["tc_shim_lt_explore_begin", Int64, Int64](Int64(samples_per_cand))
        )
    else:
        return -1


def _tc_lt_freeze() -> Int:
    """Hard barrier: sync, drain every in-flight event pair, freeze each shape that has not
    frozen itself, print the per-shape candidate tables (isolated mean next to in-situ median,
    per candidate, with the selected one marked), and return the number of shapes that ended with
    a chosen algorithm. Called between the driver's warmup loop and its timed loop, so a measured
    run can never rotate algorithms between samples. A shape that collected NO samples keeps
    FRONT 6's stage-time winner and is NOT counted — which is why the count, not the flag
    literal, is the audit's runtime-effect field."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(external_call["tc_shim_lt_freeze", Int64]())
    else:
        return -1


def _tc_lt_insitu_state() -> Int:
    """0 = the search was never armed, 1 = STILL EXPLORING, 2 = frozen. A cell measured in state
    1 would rotate algorithms between its own runs, so the flag audit reports state 1 as a FAILED
    lever rather than as a slow one."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(external_call["tc_shim_lt_insitu_state", Int64]())
    else:
        return 0



def _tc_gemm_f16_32c_pre_async(a16: Int, w16: Int, m: Int, k: Int, n: Int, c32: Int,
                              accum: Int) -> Int:
    """`_tc_gemm_f16_32c_pre` with NO sync path at all — the seam discipline the gemma-3 lane
    needs. `_pre` honours `g_noseam`, which only `-D ALGENTA_TC_NOSEAM` sets; the gemma-3
    build gets its zero-sync ordering from `-D ALGENTA_G3_STREAM` (`tc_shim_use_stream` binds
    the handle to the legacy stream, `g_noseam` stays 0), so `_pre` there would put a
    `cudaStreamSynchronize(legacy)` back at every projection seam. This is the identical
    GemmEx (f16 A already staged, f16 W, COMPUTE_32F, f32 C, beta by `accum`) enqueueing and
    returning, exactly like `_tc_gemm_f16_32c_async`. ONLY legal when the session's Mojo
    enqueues ride the same stream the shim is bound to; the caller owns the eventual sync.
    0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_gemm_f16_32c_pre_async", Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64,
            ](Int64(a16), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(c32), Int64(accum))
        )
    else:
        return -1


def _tc_gemm_f16_16c_pre_async(a16: Int, w16: Int, m: Int, k: Int, n: Int, c16: Int,
                              accum: Int) -> Int:
    """The f16-C twin of `_tc_gemm_f16_32c_pre_async` (A already f16, W f16, HMMA with an f32
    accumulator, C written as f16), with no sync path — the gate/up GEMM's output under
    `-D ALGENTA_G3_PF_F16MLP`, whose `[m, 2*d_ff]` result the GeGLU epilogue reads straight
    back. Halves both legs of the layer's largest non-GEMM traffic term (176 MB -> 88 MB at
    m=1024, d_ff=21504). NOT bit-identical to the f32-C path (the epilogue's inputs round to
    f16 at the GEMM epilogue instead of after it), so it carries its own build flag and its own
    token-identity gate. 0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_gemm_f16_16c_pre_async", Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64,
            ](Int64(a16), Int64(w16), Int64(m), Int64(k), Int64(n), Int64(c16), Int64(accum))
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


def _tc_fa_layout_probe() -> Int:
    """Run (once, cached inside the shim) the on-device check of the WMMA accumulator element
    -> (row, col) mapping that `_tc_fa_causal_async` indexes by when it applies the causal
    mask, rescales O by the online-softmax alpha and divides by the row sum. The WMMA API
    documents that layout as opaque, so the kernel does not get to assume it: this returns
    -310 and the shim prints the disagreeing lane/element if it ever changes, and every FA
    call then declines so the session keeps the five-pass chain. Called at TC staging time so
    the ARMED/DECLINED verdict is a per-binary line in the run log, never a silent perf cliff.
    0 = verified."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(external_call["tc_shim_fa_layout_probe", Int64]())
    else:
        return -1


def _tc_fa_causal_async(q32: Int, k16: Int, v16: Int, o32: Int, scale32: Int, m: Int,
                        n_keys: Int, h_q: Int, h_kv: Int, d: Int, pos_base: Int,
                        bn: Int) -> Int:
    """FUSED CAUSAL FLASH ATTENTION (FRONT 3 lever 1, `-D ALGENTA_7B_PF_FA`): one WMMA
    FlashAttention-2 kernel replacing the whole five-pass TC attention chain — the head-major
    Q pack, the QK^T strided-batched GemmEx, the masked softmax, the PV GemmEx and the
    head-major O unpack. The `[h_q*m, n_keys]` f32 score matrix (117 MB/layer at
    m=n_keys=1024) is never materialized: online softmax, the score tile lives in the WMMA
    accumulator registers, and only the f16 P tile round-trips through shared memory.

    `q32` is the session's `pf_q_rot` `[m, h_q*d]` f32 POSITION-major (the RoPE kernel's own
    output — no pack pass), `o32` is `pf_attn` in the same layout (no unpack pass), and
    `k16`/`v16` are the `[n_keys, h_kv*d]` f16 staging the chain already builds. `scale32` is
    a DEVICE POINTER to one f32 holding the attention scale, NOT a float argument: Mojo's
    `external_call` has no repo-proven float-argument marshalling, and an ABI mismatch would
    be a silent numeric bug rather than a crash, so the scale travels as a pointer the shim
    dereferences on device (exact, one L2-resident 4-byte read per CTA).

    `bn` selects the key-block width (32/64/128; anything else -> 64). GQA is internal
    (query head h reads KV head h/(h_q/h_kv)); the causal predicate is the chain's own with
    window 0, so a windowed layer must NOT dispatch here. 0 = success; -301 wrong head_dim;
    -304 h_q not a multiple of h_kv; -310 the shim's on-device WMMA accumulator-layout probe
    disagreed with the mapping the kernel indexes by — the caller MUST fall back to the
    five-pass chain on ANY non-zero return, which is what the dispatch site does."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_fa_causal_async", Int64, Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64, Int64, Int64, Int64, Int64,
            ](Int64(q32), Int64(k16), Int64(v16), Int64(o32), Int64(scale32), Int64(m),
              Int64(n_keys), Int64(h_q), Int64(h_kv), Int64(d), Int64(pos_base), Int64(bn))
        )
    else:
        return -1


def _tc_fa2_layout_probe() -> Int:
    """Run (once, cached inside the shim) the on-device check of the FA2 kernel's operand
    mappings: the `mma.sync.aligned.m16n8k16` A / B / D fragment layouts AND both `ldmatrix`
    roles (the K tile loaded non-transposed, the V tile loaded transposed). Unlike the WMMA
    accumulator those layouts are specified by the ISA rather than documented as opaque, but
    this repo does not get to trust a specification it has not watched this toolkit honour:
    the probe fills A[r][c] = (c==0 ? r+1 : 0) and B[k][n] = (k==0 ? n+1 : 0), runs the exact
    instruction sequences the kernel uses, and requires every lane's four D registers to read
    back (row+1)*(col+1) — exact small integers, no tolerance, no floating-point judgement.
    Returns -311 and prints the disagreeing lane/register if anything moved, and every FA2
    call then declines so the session keeps FRONT 3's fused flash attention. Called at TC
    staging time so the ARMED/DECLINED verdict is a per-binary line in the run log.
    0 = verified."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(external_call["tc_shim_fa2_layout_probe", Int64]())
    else:
        return -1


def _tc_fa2_causal_async(
    q32: Int, k16: Int, v16: Int, o32: Int, scale32: Int, m: Int, n_keys: Int, h_q: Int,
    h_kv: Int, d: Int, pos_base: Int, bn: Int, variant: Int,
) -> Int:
    """FUSED CAUSAL FLASH ATTENTION, v2 (FRONT 4 lever 1, `-D ALGENTA_7B_PF_FA2`): FRONT 3's
    `_tc_fa_causal_async` with the two causes its own nsys autopsy ranked first at long
    `n_keys` removed —

      * the K/V tile for key block kb+1 is in flight (cp.async, 16-byte, zero-filling the
        cache tail) while kb computes, on two rotating buffers, with two block fences per key
        block instead of three, so the HBM round trip is no longer exposed latency at
        2 CTAs/SM;
      * the f16 P tile no longer round-trips through shared memory. `wmma::fragment` cannot be
        reinterpreted as an f16 `matrix_a`, but raw `mma.sync.m16n8k16` puts a lane's two f16
        of a k-pair at exactly the registers where its two f32 of the same k-pair already sit,
        so P's A operand is a convert-and-pack on values already in registers.

    Two more things fall out for free: the O accumulator's element -> (row, col) mapping is
    ISA-specified rather than opaque, so the epilogue writes position-major f32 straight to
    global (no `sO` staging window, no fence), and shared memory per CTA drops to
    `8*bn*FA_LD` bytes because the Q tile is staged inside the second rotating buffer and dies
    the moment its A fragments are in registers.

    Arguments, layouts, the device-pointer scale and the causal predicate are IDENTICAL to
    `_tc_fa_causal_async` — this is a drop-in for it. `variant` selects the attribution arms:
    0 = both sub-levers (the lever), 1 = cp.async double buffering with P still round-tripping
    through shared, 2 = in-register P with synchronous K/V loads. 0 = success; -301 wrong
    head_dim; -304 h_q not a multiple of h_kv; -305 the Q-tile-in-buffer-1 overlay does not
    fit this bn (FA_BM > 2*bn) or the variant does not implement it; -311 the shim's on-device
    FA2 layout probe disagreed. The caller MUST fall back on ANY non-zero return."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_fa2_causal_async", Int64, Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64, Int64, Int64, Int64, Int64, Int64,
            ](
                Int64(q32), Int64(k16), Int64(v16), Int64(o32), Int64(scale32), Int64(m),
                Int64(n_keys), Int64(h_q), Int64(h_kv), Int64(d), Int64(pos_base), Int64(bn),
                Int64(variant),
            )
        )
    else:
        return -1


def _tc_stage_f32_to_f16_v8(src: Int, dst: Int, n: Int) -> Int:
    """`_tc_stage_f32_to_f16` with 8 elements per thread (two float4 loads, one uint4 store)
    instead of one scalar load and one 2-byte store — FRONT 4 lever 2 part (a), the K/V
    staging half. BIT-EXACT: `__floats2half2_rn` is the round-to-nearest-even conversion of
    each half independently, the same operation `__float2half` performs, so every output half
    is the same bit pattern. An operand the 16-byte form cannot legally vectorize falls back
    to the scalar kernel INSIDE the shim entry rather than failing, so the two entries can
    never disagree about an answer. Enqueues on the shim stream, no sync. 0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call["tc_shim_f32_to_f16_v8", Int64, Int64, Int64, Int64](
                Int64(src), Int64(dst), Int64(n))
        )
    else:
        return -1


def _tc_fa_g3_window_async(q32: Int, k: Int, v: Int, o: Int, scale32: Int, m: Int,
                           n_keys: Int, h_q: Int, h_kv: Int, d: Int, pos_base: Int,
                           window: Int, bn: Int, kv32: Int, of16: Int) -> Int:
    """FUSED WINDOWED FLASH ATTENTION for the Gemma 3 lane (round 5, `-D ALGENTA_G3_PF_FA`):
    `_tc_fa_causal_async`'s kernel with the three things Gemma 3 needs and the 7B family does
    not have.

    * `window` — the sliding-window lower bound. `window <= 0` is full-context causal (a global
      layer); `window > 0` is a local layer, and the predicate is
      `_attn_softmax_mask_kernel`'s verbatim (`j <= qpos AND j >= qpos + 1 - window AND
      j < n_keys`). The window is applied as a KEY-BLOCK RANGE, so a local layer stops paying
      for keys it discards: at RAG-4096 the five-pass chain computes a dense 4096-wide QK^T
      per local layer and masks 3072 of those columns away, while this kernel never loads them.
    * `kv32` — 1 reads the session's RESIDENT f32 K/V cache and converts to f16 in-register on
      the way into shared memory, which deletes the `_f32_to_f16_kernel` staging pass (6 bytes
      of global traffic per K/V element per layer down to 4) at the identical `__float2half`
      rounding point; 0 takes an f16 staging twin exactly like `_tc_fa_causal_async`.
    * `of16` — 1 writes the position-major output as f16 (`pf_attn16`, the pre-staged A the
      o_proj GEMM reads under `-D ALGENTA_G3_PF_F16ATTN`); 0 writes f32 (`pf_attn`).

    Layouts are the session's own, all row-major: `q32` = `pf_q_rot` `[m, h_q*d]` f32, `o` =
    `pf_attn`/`pf_attn16` in the same layout, `k`/`v` = `[n_keys, h_kv*d]`. `scale32` is a
    DEVICE POINTER to one f32 (see `_tc_fa_causal_async` for why the scale is not an argument).
    `bn` selects the key-block width (32/64/128; anything else -> 64). 0 = success; -301 wrong
    head_dim; -304 h_q not a multiple of h_kv; -305 an out-of-list (bn, kv32, of16) selection;
    -310 the shim's on-device WMMA accumulator-layout probe disagreed with the mapping the
    kernel indexes by. The caller MUST fall back to the five-pass chain on -301/-304/-305/-310
    and MUST return any other non-zero status as a real launch failure."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_fa_g3_window_async", Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64,
            ](Int64(q32), Int64(k), Int64(v), Int64(o), Int64(scale32), Int64(m),
              Int64(n_keys), Int64(h_q), Int64(h_kv), Int64(d), Int64(pos_base),
              Int64(window), Int64(bn), Int64(kv32), Int64(of16))
        )
    else:
        return -1


def _tc_fa_g3_window2_async(q32: Int, k: Int, v: Int, o: Int, scale32: Int, m: Int,
                            n_keys: Int, h_q: Int, h_kv: Int, d: Int, pos_base: Int,
                            window: Int, bn: Int, kv32: Int, of16: Int, dbuf: Int) -> Int:
    """FUSED WINDOWED FLASH ATTENTION v2 for the Gemma 3 lane (round 6,
    `-D ALGENTA_G3_PF_FA2`): `_tc_fa_g3_window_async`'s kernel with #994's 7B FA2 techniques
    transplanted onto it — raw `mma.sync m16n8k16` with the P tile's A-fragment built IN
    REGISTERS (the f32->f16 pack lands on the exact registers the score accumulator already
    occupies, so `sP` and its per-key-block fence disappear), the O epilogue written
    position-major STRAIGHT TO GLOBAL from the ISA-specified D layout (`sO` and its 33.8 KB
    staging window disappear), and — on the f16 K/V route only — cp.async K/V double buffering
    with the next key block's tile in flight while the current one computes.

    The WINDOW is untouched: `kb_min` still derives from the CTA's first query row's lower
    bound (monotone in `qpos`), the per-element predicate is still
    `_attn_softmax_mask_kernel`'s verbatim, and the kv32 in-register f32->f16 convert still
    rounds where the staging pass rounded. `dbuf=1` is REJECTED together with `kv32=1`
    (cp.async copies raw bytes and cannot convert), so the production native-f32 route runs
    single-buffered synchronous loads with two fences per key block instead of three.

    Same operands, same layouts, same decline contract as v1, with two changes: the layout
    probe is the 7B FA2 raw-mma one (`-311`, not `-310`), and the caller's fallback on
    -301/-304/-305/-311 is v1's WMMA kernel (which keeps its own decline-to-five-pass-chain
    fallback). Any OTHER non-zero status is a real launch failure and must be returned as one.
    0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_fa_g3_window2_async", Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64,
            ](Int64(q32), Int64(k), Int64(v), Int64(o), Int64(scale32), Int64(m),
              Int64(n_keys), Int64(h_q), Int64(h_kv), Int64(d), Int64(pos_base),
              Int64(window), Int64(bn), Int64(kv32), Int64(of16), Int64(dbuf))
        )
    else:
        return -1


def _tc_fa_g3_window3_async(q32: Int, k: Int, v: Int, o: Int, scale32: Int, m: Int,
                            n_keys: Int, h_q: Int, h_kv: Int, d: Int, pos_base: Int,
                            window: Int, bn: Int, kv32: Int, of16: Int, dbuf: Int,
                            rt: Int, gqa: Int) -> Int:
    """FUSED WINDOWED FLASH ATTENTION v3 for the Gemma 3 lane (round 7 kernel, round 9 dispatch):
    v2 with `rt` m16 row-tiles per warp fed by ONE shared B-fragment stream, so each K/V
    `ldmatrix.x4` issues `rt` mma instead of one and the shared-load stream per row falls by `rt`.

    `gqa=1` spends those tiles on GQA-PACKED CTAs: the `rt` tiles are `rt` different QUERY HEADS
    of ONE KV head at the SAME 16 rows, so `grid.y` falls from `h_q` to `h_q/rt` and the K/V tile
    is fetched once per (row-block, kv-head) instead of once per query head. `gqa=0` spends them
    on ROWS instead (FA_BM 64 -> 128).

    BIT-IDENTICAL TO v2, and that was PROVEN rather than assumed: `fa_g3_probe` holds every v3
    arm to a full-element bit comparison against the v2 arm of the same (kv32, of16, dbuf), and on
    2026-09-17 that was **216/216 BITIDENT-v2 with 0 BITDIFF at both BN=32 and BN=64**, across all
    twelve raced shapes including the odd tail. v3 moves no rounding point. For `gqa=1` both tiles
    share v2's `row0`, so the key-block range, block order and mma k-grouping are v2's exactly per
    (row, head). For `gqa=0` the range widens to the union over 128 rows, but every extra block is
    fully masked and the online-softmax rescale annihilates it exactly.

    SHAPE-CONDITIONAL BY NECESSITY, AND THE CONDITION IS MEASURED NOT MODELLED. `gqa=1` halves
    the CTA count, and the probe's decision table (median of 30, production mapping, BN=32) puts
    the crossover at `n_keys`:

        rag t1  n_keys=1024   v2  90.3 us -> GQA2 101.6 us   +11.9%  LOSES
        rag t2  n_keys=2048   v2 126.7 us -> GQA2 110.5 us   -12.8%  WINS
        rag t3  n_keys=3072   v2 126.1 us -> GQA2 110.9 us   -12.1%  WINS
        rag t4  n_keys=4096   v2 141.5 us -> GQA2 111.5 us   -21.2%  WINS
        pp256   n_keys= 256   v2  22.5 us -> GQA2  30.9 us   +37.6%  LOSES BADLY

    Per-CTA work scales with the key-block count, so at small `n_keys` the doubled Q staging and
    the RT=2 register pressure (255 registers, and 24 of 36 instantiations spill 424-488 B) are
    not amortized; at large `n_keys` the halved K/V fetch dominates. The dispatch therefore gates
    on `n_keys` as a shape fact, which is also why this is a WIN for rag4096 and a NO-OP for
    pp256/pp1024 — those cells keep v2 bit for bit and cannot regress.

    Decline contract: -301 head_dim != 128, -304 non-integral GQA or an `rt` that does not divide
    the group size `h_q/h_kv` (the check that stops a packed CTA silently reading the wrong K/V),
    -305 an off-table (bn, kv32, of16, dbuf, rt, gqa) selection — v3's table is BN 32/64 only, and
    `dbuf=1` with `kv32=1` is rejected because cp.async cannot convert — or an ungranted shared
    window; -311 the on-device raw-mma layout probe disagreed. The caller's fallback on
    -301/-304/-305/-311 is v2, which keeps its own fallback to v1 and then to the five-pass chain:
    a declined lever never masquerades as an armed one. 0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_fa_g3_window3_async", Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64, Int64,
                Int64, Int64,
            ](Int64(q32), Int64(k), Int64(v), Int64(o), Int64(scale32), Int64(m),
              Int64(n_keys), Int64(h_q), Int64(h_kv), Int64(d), Int64(pos_base),
              Int64(window), Int64(bn), Int64(kv32), Int64(of16), Int64(dbuf),
              Int64(rt), Int64(gqa))
        )
    else:
        return -1


def _tc_swiglu_f16_fastexp(gu16: Int, act16: Int, m_rows: Int, n_ff: Int) -> Int:
    """Fast-exp SwiGLU epilogue (FRONT 3 lever 2, `-D ALGENTA_7B_PF_FASTEXP`): the shim twin
    of `_pf_swiglu_rows_f16_kernel` — the same `(g / (1 + exp(-g))) * u` over the same f16
    operands with the same f32 intermediate arithmetic and the same single f32->f16 rounding
    at the store, but with `__expf` (the single-instruction ex2.approx.ftz path) instead of a
    libm exp, and a division-free 2-D grid with 16-byte vector loads/stores instead of one
    scalar output per thread indexed by a runtime `i / n_ff`. Requires `n_ff % 8 == 0` and
    16-byte-aligned operands; anything else returns -302 and the caller keeps the Mojo
    epilogue. Enqueues on the shim stream, no sync. 0 = success."""
    @parameter
    if TC_SHIM_BUILD:
        return Int(
            external_call[
                "tc_shim_swiglu_f16_fastexp_async", Int64, Int64, Int64, Int64, Int64,
            ](Int64(gu16), Int64(act16), Int64(m_rows), Int64(n_ff))
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
