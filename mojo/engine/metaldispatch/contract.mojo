"""
metaldispatch.contract — the status vocabulary for the batched dispatch shim. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_metaldispatch_session.mojo, mojo/tests/libs/test_metaldispatch_session_f16.mojo
benchmark: benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch.mojo, benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_f16.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

What this package is, in one sentence
-----------------------------------------
`residentk` proved a resident-GPU Qwen3 decode session; this package changes ONLY how each of its
171-per-token dispatches reaches the GPU — one C-shim call per token (one command buffer, one
encoder, all 171 dispatches, one commit, one wait) instead of 171 blocking
`DeviceContext.enqueue_function` calls. The kernels dispatched are `residentk.kernels`'s OWN
compiled functions, imported and reused, never rewritten (rule 3). See `metaldispatch/__init__.mojo`
for the full design writeup and `benchmarks/llm_smoke/REALRACE_RESULTS.md`'s batched-dispatch
addendum for the measured result this package produced.

Status range
------------
`metaldispatch` owns **620-639**. Free at the time this was written per the per-package ledger in
`residentk.contract` (`residentk` 600-619) and every other package's own comment — recorded here so
the next package can see what is taken.

This module imports no `std.gpu` and links no shim object
--------------------------------------------------------------
Exactly `residentk.contract`'s own discipline: a caller on any host, GPU or not, Metal or not, can
ask "what does this status code mean" and "how many dispatches would one token issue" with no
device, no shader compiler, and no linked `.o` involved. Everything that touches the shim lives in
`metaldispatch.session` and `metaldispatch.ffi`, both private, neither a contract module.

Public API:
  metaldispatch_status_name(code)     — the status vocabulary
  metaldispatch_dispatch_budget(n)    — dispatches one token issues (calls residentk's own function,
                                         rule 3 — this package does not restate that arithmetic)
"""

from residentk.contract import residentk_dispatch_budget

# ── status codes: metaldispatch owns 620-639 ───────────────────────────────────

comptime MB_OK: Int = 620
"""The shim call succeeded, or the query answered normally."""

comptime MB_ERR_SHADER_TOOLCHAIN_ABSENT: Int = 621
"""Built without `-D ALGENTA_GPU` — no kernel was compiled into this binary, so there is nothing to
extract a metallib from and nothing to open a session for. Same build-vs-deployment distinction
`residentk.contract.RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT` documents."""

comptime MB_ERR_NO_DEVICE: Int = 622
"""Built with GPU kernels, but this host has no accelerator."""

comptime MB_ERR_SESSION_OPEN_FAILED: Int = 623
"""`algenta_open_session` returned a Metal-reported failure (device/queue/library/pipeline build)."""

comptime MB_ERR_PIPELINE_NOT_FOUND: Int = 624
"""A required kernel's compiled pipeline was not among the metallibs the shim discovered in this
binary's own `__TEXT,__const`. Distinguished from 623 because the SESSION opened fine and some
other pipeline did resolve — this kernel specifically did not, which points at a codegen or naming
change rather than a device/toolchain problem."""

comptime MB_ERR_BUFFER_ALLOC_FAILED: Int = 625
"""`algenta_alloc_buffer` returned failure (device out of memory, or the shim's internal buffer
table — sized for this exact model shape — was exhausted)."""

comptime MB_ERR_UPLOAD_LENGTH: Int = 626
"""A weight handed to the session is not the element count its declared shape implies. Same
contract as `residentk.contract.RESIDENT_ERR_UPLOAD_LENGTH`."""

comptime MB_ERR_CONTEXT_FULL: Int = 627
"""The requested run would need more KV-cache positions than this session allocated."""

comptime MB_ERR_DISPATCH_FAILED: Int = 628
"""`algenta_run_token` returned a Metal-reported command-buffer failure (validation error, a
descriptor naming an out-of-range pipeline index, or an unrecognized argument tag)."""

comptime MB_ERR_DISPATCH_COUNT_MISMATCH: Int = 629
"""The session built a different number of dispatch descriptors than
`metaldispatch_dispatch_budget(n_layers)` says one token costs — the design and the code disagree.
Same defensive assertion `residentk.session.step` makes for its own dispatch count."""

comptime MB_ERR_CODE_OUT_OF_RANGE: Int = 630
"""Not one of the codes above. Returned by `metaldispatch_status_name` for an unrecognized code."""


fn metaldispatch_status_name(code: Int) -> String:
    """Human-readable name for a `metaldispatch` status code.

    @capability metaldispatch_status_name
    complexity: O(1)
    @endcapability
    """
    if code == MB_OK:
        return "metaldispatch_ok"
    if code == MB_ERR_SHADER_TOOLCHAIN_ABSENT:
        return "metaldispatch_shader_toolchain_absent"
    if code == MB_ERR_NO_DEVICE:
        return "metaldispatch_no_device"
    if code == MB_ERR_SESSION_OPEN_FAILED:
        return "metaldispatch_session_open_failed"
    if code == MB_ERR_PIPELINE_NOT_FOUND:
        return "metaldispatch_pipeline_not_found"
    if code == MB_ERR_BUFFER_ALLOC_FAILED:
        return "metaldispatch_buffer_alloc_failed"
    if code == MB_ERR_UPLOAD_LENGTH:
        return "metaldispatch_upload_length"
    if code == MB_ERR_CONTEXT_FULL:
        return "metaldispatch_context_full"
    if code == MB_ERR_DISPATCH_FAILED:
        return "metaldispatch_dispatch_failed"
    if code == MB_ERR_DISPATCH_COUNT_MISMATCH:
        return "metaldispatch_dispatch_count_mismatch"
    return "metaldispatch_code_out_of_range"


fn metaldispatch_dispatch_budget(n_layers: Int) -> Int:
    """GPU dispatches ONE token costs through this package's shim path.

    Calls `residentk_dispatch_budget` rather than restating its arithmetic (rule 3): the batched
    shim issues the exact same 171-dispatch plan `residentk.session.step` does, one command buffer
    at a time instead of 171 blocking calls — the SET of dispatches is unchanged, only how they
    reach the GPU is.

    @capability metaldispatch_dispatch_budget
    complexity: O(1)
    @endcapability
    """
    return residentk_dispatch_budget(n_layers)
