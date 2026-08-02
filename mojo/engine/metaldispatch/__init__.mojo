"""
metaldispatch — batched Metal command-buffer dispatch for `residentk`'s resident Qwen3 decode
session. Zero Python. Additive: `accel/`, `gemm/` and `residentk/` are untouched; this package
CALLS `residentk.kernels`'s compiled functions, it does not rewrite them.

Why this package exists, measured rather than asserted
-----------------------------------------------------------
`residentk` (PR #503) proved a resident-GPU Qwen3 decode session at 20.28 tok/s median, 171 fused
Metal dispatches per token through `DeviceContext.enqueue_function`. `benchmarks/llm_smoke/
REALRACE_RESULTS.md`'s four-way race decomposed the 49.31 ms/token cost and found 16.45 ms (33.4%)
is pure dispatch-submission overhead: `enqueue_function` blocks the host for ~96 us per call
regardless of kernel size, with no async path to hide it behind (`ctx.stream()` raises `"Metal
stream not implemented"` on this backend). A raw-Metal dispatch investigation (`#504`,
`.worktrees/metalffi`) tried to remove that ceiling by hand-driving `MTLCommandBuffer` from Mojo via
`external_call`, and reported a no-go: the extracted, independently-loaded kernel dispatched without
error but its buffer write never landed.

That no-go was a misdiagnosis, not a real limitation. A follow-up investigation
(`.worktrees/metalair`) found the actual bug: Mojo's Metal ABI passes a POINTER kernel argument as
the *value* of the target buffer's 64-bit GPU device address in its own argument slot (bound via
`setBytes:length:atIndex:`), not as a `setBuffer:offset:atIndex:` binding — the no-go's probe used
the wrong Metal call for this ABI. With the correct recipe (`setBytes` of the address + `useResource:`
to declare residency, both proven bit-exact against MAX's own `enqueue_function` on a real 5-arg
GEMV shape), correctness is solved — but a naive port crossing the Mojo<->C FFI boundary once per
Metal API step (get command buffer, get encoder, set pipeline, N x bind-argument, dispatch, end
encoding — roughly 8 crossings per dispatch) measured 839-925 us/dispatch, WORSE than MAX's own
350-362 us, because each `external_call` crossing costs real time and the naive path pays it eight
times over instead of MAX's one.

The fix this package implements: collapse the entire per-token dispatch sequence into ONE C-shim
call. `benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m` builds every compute pipeline ONCE at
session open (from Mojo's own compiled kernel bytes — the embedded `.metallib`s this binary's build
step already produces), and `algenta_run_token` gets one command buffer and one encoder, loops over
all 171 dispatch descriptors ENTIRELY IN OBJECTIVE-C (bind arguments, mark resources, dispatch —
zero Mojo<->C crossings inside that loop), ends encoding once, commits once, and waits once, before
returning control to Mojo. A token's per-step Mojo work is patching the handful of scalar argument
slots that actually vary between tokens (`token_id` once, `pos`/`n_keys` once per layer) and issuing
that one call.

What is reused from `residentk`, and what is new
-----------------------------------------------------
Reused, unmodified, by direct import: every one of `residentk.kernels`' eight compiled Metal
kernels (the actual arithmetic — rmsnorm, fused QKV/gate-up projections, RoPE, online-softmax SDPA,
the lm_head argmax); the 171-dispatch fusion PLAN (one embedding gather, six dispatches per layer,
lm_head + argmax); the KV-cache in-place-write scheme; the `[out, in]` weight transpose layout and
its blocked-tile upload arithmetic; every model-shape constant this package's driver reads from the
same checkpoint manifest `residentk`'s own benchmark reads.

New: the dispatch MECHANISM only. `metaldispatch.session` allocates its own resident Metal buffers
(via the shim, not `DeviceContext.enqueue_create_buffer`) because marking a buffer resident for the
proven ABI recipe needs a live `id<MTLBuffer>` Objective-C object, and no such object is reachable
from `residentk`'s `DeviceContext`/`DeviceBuffer` handles (a separate, already-completed
investigation, `.worktrees/metalffi` Route A, heap-scanned `DeviceContext`/`DeviceFunction` and
found none; the same absence holds for `DeviceBuffer`). The upload math, the KV-cache scheme and the
descriptor building are therefore RE-IMPLEMENTED against a raw pointer instead of
`DeviceBuffer.map_to_host()` — the arithmetic is `residentk.session`'s own, ported to a different
buffer source, never redesigned.

Modules
-------
  contract  — status codes 620-639. An ordinary contract module: no `std.gpu` import, no linked
              shim, buildable and honest on any host.
  ffi       — thin, typed `external_call` wrappers to `batch_shim.m`'s four exported C functions.
              Private; not a contract module.
  session   — PRIVATE resident state: `_MBQwen3` (Float32 weights) and `_MBQwen3F16` (the fp16-
              weight twin, added once the sibling `residentk` vectorized-GEMV + fp16 track landed
              in `#505` — see that struct's own docstring for why it MUST be its own binary, never
              built alongside `_MBQwen3`). Both share the shim-backed buffers, the pipeline-by-name
              resolution and the mostly-static descriptor array; both dispatch with one shim call
              per token.

What this package is NOT
--------------------------
Not a replacement for `residentk` — `residentk.session`'s own MAX-based path is untouched and still
runnable, and is the baseline this path is measured against (`benchmarks/llm_smoke/
qwen3_generate_metal.mojo` is unmodified). Not a general Metal dispatch ABI: shaped for exactly
`residentk.kernels`' eight (now thirteen, with the fp16 twins) functions and this one model family,
the same scope `residentk` itself declares.
"""
