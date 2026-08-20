"""
residentk — resident GPU state for autoregressive decode: one `DeviceContext`, one Float64->Float32
weight conversion, one upload, an in-place KV cache, and a fused per-token dispatch plan. Zero
Python. Additive: `accel/`, `gemm/`, `attnk/`, `normk/`, `mlpk/` and `llmk/` are untouched.

Why this package exists, measured rather than asserted
---------------------------------------------------------
`accel.gemm_metal.gemm_metal_flat` is a ONE-SHOT call: it opens a `DeviceContext`, allocates three
buffers, narrows both operands from Float64 to Float32, launches, synchronizes, widens the result
back, and drops everything. At the decode shape (`m=1, k=1024, n=3072`) that call was decomposed
stage by stage on this host, compiled binary, median of 9 after 3 warm-ups:

| stage | us | share |
|---|---|---|
| `DeviceContext()` | 107 | 2.5% |
| 3x `enqueue_create_buffer` | 18 | 0.4% |
| narrow + upload the ACTIVATION (1024 f64) | 418 | 9.9% |
| **narrow + upload the WEIGHT (3.1M f64) — reconverted on EVERY call** | **2239** | **53.3%** |
| `enqueue_function` (blocking on this backend — see below) | 1035 | 24.6% |
| `synchronize` | 52 | 1.2% |
| widen + download the RESULT (3072 f32) | 335 | 8.0% |

65% of that call is context setup plus re-narrowing a weight that never changes between tokens.
`benchmarks/llm_smoke/REALRACE_RESULTS.md`'s MetalRoute probe concluded from the same shape that
"Metal is 8-13x slower at decode". The correct conclusion from that data was **build residency**,
not "Metal is wrong": a weight is converted and uploaded once per SESSION, not once per matmul.

What residency actually buys, and the wall it does not move
--------------------------------------------------------------
Residency deletes the 65%. It does not delete host-side submission cost, and on this toolchain that
cost is the binding constraint, for one definitively measured reason:

**`ctx.enqueue_function` on the Metal backend BLOCKS until the kernel completes.** It is not an
enqueue. Fed a 20 ms kernel it returns in 20.392 ms and the following `synchronize()` costs 35 us.
There is no async path — `ctx.stream()` raises `"Metal stream not implemented"`. So a token's wall
time is the SUM of (host submission + kernel) over every dispatch, with no overlap, and the dispatch
COUNT is a first-class design parameter rather than an implementation detail.

Measured on this host (Apple M4 Max), same session, both re-verified in this package's own build:

- one `enqueue_function` through a struct-held compiled handle: **~180 us**; through the
  `enqueue_function[k, k]` parameter form: **~390 us**. The handle is worth 2.2x and this package
  therefore compiles every kernel ONCE at session open (`compile_function`) and stores the
  handle as a field.
- a whole token as 197 unfused split-K GEMVs — 394 dispatches, all 2.38 GB of weights already
  resident — measures **114 ms == 8.8 tok/s**. Residency alone is NOT the win. That is the number
  that makes fusion a correctness condition for the design rather than an optimization: a naive
  port of the CPU driver's ~20 ops per layer would be ~560 dispatches, i.e. ~100 ms of pure
  submission overhead per token, which is worse than the CPU path it replaces.

So the design fuses from day one, to **6 dispatches per layer** plus 3 fixed:

    [rmsnorm1 + fused QKV]                 -> one dispatch, 3 projections, one shared normalization
    [q_norm + k_norm + RoPE + KV write]    -> one dispatch, writes the cache slot IN PLACE
    [SDPA, online softmax]                 -> one dispatch, one threadgroup per query head
    [o_proj + residual]                    -> one dispatch, accumulates straight into `hidden`
    [rmsnorm2 + fused gate/up + SwiGLU]    -> one dispatch, 2 projections + the elementwise stage
    [down_proj + residual]                 -> one dispatch, accumulates straight into `hidden`

plus `[embedding row]`, `[final rmsnorm + lm_head + per-block argmax]` and `[argmax reduce]`.
`residentk.contract.residentk_dispatch_budget` states that arithmetic as a contract function so a
test can assert the count instead of a comment claiming it.

The KV cache is the second, independent win
----------------------------------------------
`llmk.generate.kv_cache_append_flat` allocates a NEW list of `cache_len + n_new` elements and copies
the whole cache on every call, twice per layer per step. Across a generation that is O(N^2) copying:
28 layers x 2 x sum over steps of the running cache length. This package's cache is allocated once
at `max_ctx` positions — a genuine RUNTIME parameter the caller chooses at session-open time,
bounded by `RESIDENT_MAX_CONTEXT`'s safety ceiling rather than fixed to it — and each step writes
ONE slot in place from inside the RoPE kernel, so the copy disappears entirely rather than being
made faster, at any requested context length. That win is measured separately in
`benchmarks/llm_smoke/qwen3_generate_metal.mojo`, because it is not the same lever as residency and
conflating them would make neither attributable.

Precision, stated up front
-----------------------------
The GPU computes in **Float32**; every CPU kernel in this plane computes in Float64. The two do not
compute the same function and this package never claims they do. The bar that matters for
generation is not bit-equality of logits, it is **agreement of the greedy token ids** against the
`transformers`-CPU reference — which is itself a float32 run. `benchmarks/llm_smoke/`'s
`verify_generation.py` is the check, and the measured per-step logit deltas are reported in
`REALRACE_RESULTS.md` rather than hidden behind a tolerance.

Modules
-------
  contract  — status codes 600-619, the shape checks, and the dispatch budget. An ordinary
              contract module: no `std.gpu` import, buildable and honest on any host.
  probe     — the public capability answer. Calls `accel.device.accel_device_probe` (rule 3)
              rather than opening a second `DeviceContext`, and never launches anything.
  kernels   — PRIVATE GPU kernels (portable max.gpu.host; Metal run-verified since 0.7.0, CUDA
              run-verified by the Phase-0 T4 round trip). Not a contract module; nothing here is
              public.
  kernels_prefill_f32 — PRIVATE Float32-weight batched-prefill kernels (the m_rows > 1 tiled GEMM
              path residentk.session_cuda dispatches). Same privacy discipline as `kernels`.
  kernels_cuda_graph — PRIVATE graph-replay twins of the three position-dependent decode kernels
              (embed / RoPE-write / SDPA read their per-token scalar from a resident state buffer
              so ONE captured DeviceGraph serves every decode step). Same privacy discipline.
  session   — PRIVATE resident state: the context, the Float32 weight buffers, the in-place KV
              cache, and the per-token step. Every launch sits inside `@parameter if
              RESIDENT_GPU_BUILD` and every entry point is private.
  session_cuda — PRIVATE CUDA-native resident session: the same resident state plus the batched
              prefill pass. Every launch sits inside `@parameter if CUDA_SESSION_BUILD` (the
              ALGENTA_GPU + ALGENTA_CUDA conjunct), so a Metal or CPU build compiles it with every
              launch elided.

Dependency direction is one-way: `residentk` uses `accel` for the device probe, `attnk.rope` for the
RoPE table and `tensorx` for finiteness, and never the reverse.

What this package is NOT
--------------------------
Not a replacement for `llmk` — `benchmarks/llm_smoke/qwen3_generate.mojo`'s Float64 CPU decode loop
is unchanged and still runnable, and is the baseline this path is measured against. Not a general
GPU inference ABI: the session is shaped for one dense decoder-only model family (Qwen3) and says
so. Not a second `accel`: `accel` owns the device probe and the one-shot GEMM, this owns state that
outlives a call.
"""
