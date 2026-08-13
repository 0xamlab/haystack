"""
metaldispatch.ffi — thin, typed wrappers around `batch_shim.m`'s exported C functions (five as of
`_mb_gpu_core_count`). Zero Python, zero kernel logic (every wrapper here is a one-line
`external_call`).

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32, float16
backend: metal
surfaces: none
golden_vectors: mojo/tests/libs/test_metaldispatch_session.mojo, mojo/tests/libs/test_metaldispatch_session_f16.mojo
benchmark: benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch.mojo, benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_f16.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Private, like `residentk.kernels`/`residentk.session`
--------------------------------------------------------------------------------
This file's only reason to exist separately from `metaldispatch.session` is so the raw
`external_call` signatures live in one place, matching the shim's C prototypes exactly, and nothing
in `session.mojo` has to spell an FFI signature more than once.

The shim (`benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m`) is linked in via `-Xlinker
<path-to-batch_shim.o>` at build time — this file assumes that link happened; calling any function
here in a binary that did not link the shim fails at LINK time with an undefined symbol, not at
runtime, which is the same contract `objc_link_probe.mojo`'s investigation established for
`external_call["objc_msgSend", ...]` in the probe phase this package's design is built on.

`AlgentaDispatchDesc` layout (must match `batch_shim.m`'s C struct byte-for-byte)
-----------------------------------------------------------------------------------
    int32 pipeline_idx
    int32 grid_x        (threadgroup count)
    int32 threads_x      (threads per threadgroup)
    int32 num_args
    ALGENTA_MAX_ARGS x { int32 tag; int32 reserved; uint64 value }   -- tag 0/1/2, see below

`tag` 0 = the arg is a POINTER: `value` holds the target buffer's `gpuAddress`, bound at its
declared slot via `setBytes:length:atIndex:` (NOT `setBuffer:`) — the ABI recipe
`.worktrees/metalair`'s two `.m` probes proved bit-exact against MAX's own `enqueue_function`.
`tag` 1 = an `Int` scalar (Mojo's `Int` is 64-bit on this target; `value` holds it directly).
`tag` 2 = a `Float32` scalar; `value`'s low 4 bytes hold the IEEE-754 bit pattern.

One descriptor is `16 + ALGENTA_MAX_ARGS * 16` bytes. `ALGENTA_MAX_ARGS = 16` here, matching the
shim; the largest real argument list among `residentk.kernels`' kernels is `_pf_ropewrt_kernel`'s
15 (its trailing `qk_norm` family-convention arg added for llama-family support, 2026-08-13), so 16
still leaves headroom without the stride growing again.
"""

from std.builtin.type_aliases import MutAnyOrigin
from std.ffi import external_call
from std.memory import alloc

comptime MB_MAX_ARGS: Int = 16
comptime MB_ARG_STRIDE: Int = 16
"""Bytes per `AlgentaArg`: int32 tag + int32 reserved + uint64 value."""
comptime MB_DESC_HEADER: Int = 16
"""Bytes before the args array: int32 pipeline_idx, grid_x, threads_x, num_args."""
comptime MB_DESC_STRIDE: Int = MB_DESC_HEADER + MB_MAX_ARGS * MB_ARG_STRIDE
"""Bytes per `AlgentaDispatchDesc` — 272 with the constants above."""

comptime MB_TAG_PTR: Int32 = 0
comptime MB_TAG_INT: Int32 = 1
comptime MB_TAG_F32: Int32 = 2


def _mb_open_session() -> Int:
    """Calls `algenta_open_session`. Returns the number of pipelines discovered (>= 0), or a
    negative value if Metal reported a failure building the device/queue/library/pipelines."""
    return Int(external_call["algenta_open_session", Int64]())


def _mb_pipeline_count() -> Int:
    return Int(external_call["algenta_pipeline_count", Int64]())


def _mb_gpu_core_count() -> Int:
    """Calls `algenta_gpu_core_count` (IOKit `AGXAccelerator`/`gpu-core-count` registry read — see
    that C function's own docstring). Returns the core count (> 0), or -1 if the probe could not
    determine one on this host. `residentk.contract.residentk_splitk_policy` documents the fallback
    a caller should apply on a negative result; this wrapper itself never substitutes one, matching
    every other typed-failure wrapper in this file (`_mb_pipeline_name`, `_mb_alloc_buffer`)."""
    return Int(external_call["algenta_gpu_core_count", Int64]())


def _mb_pipeline_name(idx: Int, mut out: String) -> Int:
    """Writes pipeline `idx`'s Metal function name into `out`. Returns the name's length, or -1 if
    `idx` is out of range."""
    var buf = alloc[UInt8](256)
    var n = external_call[
        "algenta_pipeline_name", Int64, Int64, UnsafePointer[UInt8, origin=MutAnyOrigin], Int64
    ](Int64(idx), buf, Int64(256))
    if n < 0:
        buf.free()
        return -1
    var s = String()
    for i in range(Int(n)):
        s += chr(Int(buf[i]))
    out = s
    buf.free()
    return Int(n)


def _mb_alloc_buffer(
    nbytes: Int, mut addr: UInt64, mut contents: UnsafePointer[UInt8, origin=MutAnyOrigin]
) -> Int:
    """Allocates one Shared-storage-mode `MTLBuffer` of `nbytes`. On success, `addr` holds the
    buffer's `gpuAddress` (the value a kernel's pointer argument binds to) and `contents` holds a
    CPU-writable pointer to the same memory (Shared storage is CPU/GPU coherent — no
    `map_to_host`-style call is needed to write it). Returns the internal buffer index (>= 0), or
    -1 on failure."""
    return Int(
        external_call[
            "algenta_alloc_buffer", Int64, Int64,
            UnsafePointer[UInt64, origin=MutAnyOrigin],
            UnsafePointer[UnsafePointer[UInt8, origin=MutAnyOrigin], origin=MutAnyOrigin],
        ](Int64(nbytes), UnsafePointer(to=addr), UnsafePointer(to=contents))
    )


def _mb_run_token(descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin], n: Int) -> Int:
    """THE per-token call: one command buffer, one encoder, `n` dispatches, one commit, one wait —
    entirely inside the shim, zero Mojo<->C crossings between the first dispatch and the last.
    Returns 0 on success, -1 if Metal reported a command-buffer failure."""
    return Int(
        external_call["algenta_run_token", Int64, UnsafePointer[UInt8, origin=MutAnyOrigin], Int64](
            descriptors, Int64(n)
        )
    )


# ── Parity gap 4 (persistent sessions, 2026-08-10): resident-key + adopt wrappers. The resident
# key labels which model's weights live in the shim's buffer table; adopt mode makes the next
# session construction re-adopt those buffers in allocation order instead of allocating fresh.

def _mb_get_resident_key() -> UInt64:
    return UInt64(external_call["algenta_get_resident_key", UInt64]())


def _mb_set_resident_key(key: UInt64):
    _ = external_call["algenta_set_resident_key", Int64, UInt64](key)


def _mb_begin_adopt():
    _ = external_call["algenta_begin_adopt", Int64]()


def _mb_end_adopt():
    _ = external_call["algenta_end_adopt", Int64]()


def _mb_free_all_buffers():
    """Teardown: release every Metal buffer + clear the resident key (a model switch). Pipelines
    persist (name-keyed, compiled once per process)."""
    _ = external_call["algenta_free_all_buffers", Int64]()


def _mb_alloc_descriptors(n: Int) -> UnsafePointer[UInt8, origin=MutAnyOrigin]:
    """Allocates a flat, zero-initialized array of `n` `AlgentaDispatchDesc` records."""
    var total = n * MB_DESC_STRIDE
    var p = alloc[UInt8](total)
    for i in range(total):
        p[i] = 0
    return p


def _mb_set_header(
    descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin],
    desc_idx: Int, pipeline_idx: Int, grid_x: Int, threads_x: Int, num_args: Int,
):
    var base = (descriptors + desc_idx * MB_DESC_STRIDE).bitcast[Int32]()
    base[0] = Int32(pipeline_idx)
    base[1] = Int32(grid_x)
    base[2] = Int32(threads_x)
    base[3] = Int32(num_args)


def _mb_set_arg_ptr(
    descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin], desc_idx: Int, arg_idx: Int, addr: UInt64
):
    var off = descriptors + desc_idx * MB_DESC_STRIDE + MB_DESC_HEADER + arg_idx * MB_ARG_STRIDE
    off.bitcast[Int32]()[0] = MB_TAG_PTR
    (off + 8).bitcast[UInt64]()[0] = addr


def _mb_set_arg_int(
    descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin], desc_idx: Int, arg_idx: Int, v: Int
):
    var off = descriptors + desc_idx * MB_DESC_STRIDE + MB_DESC_HEADER + arg_idx * MB_ARG_STRIDE
    off.bitcast[Int32]()[0] = MB_TAG_INT
    (off + 8).bitcast[UInt64]()[0] = UInt64(v)


def _mb_set_arg_f32(
    descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin], desc_idx: Int, arg_idx: Int, v: Float32
):
    var off = descriptors + desc_idx * MB_DESC_STRIDE + MB_DESC_HEADER + arg_idx * MB_ARG_STRIDE
    off.bitcast[Int32]()[0] = MB_TAG_F32
    var vv = v
    var bits = UInt64(UnsafePointer(to=vv).bitcast[UInt32]()[0])
    (off + 8).bitcast[UInt64]()[0] = bits
