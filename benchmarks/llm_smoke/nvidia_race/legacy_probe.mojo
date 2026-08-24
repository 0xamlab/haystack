"""legacy_probe.mojo — is Mojo's DeviceContext default stream ordered against the CUDA
LEGACY default stream (the implicit-sync semantics blocking streams have with it)?

T1: legacy-stream convert BEFORE a Mojo kernel that reads its output — ordered => the
    Mojo stream is blocking (or legacy itself).
T2: Mojo kernel writes, THEN a legacy-stream convert reads it — the reverse direction.
T3: timing sanity — 200 interleaved seams (Mojo kernel, async legacy convert, Mojo kernel)
    with ZERO host syncs; correctness-checked at the end. If this is correct, the whole
    gemma3 TC seam collapses to: bind cuBLAS to the legacy stream, dispatch async, drop
    every per-GEMM sync."""

from max.gpu.host import DeviceContext
from std.gpu import block_idx, thread_idx
from std.origin import MutAnyOrigin
from std.sys import exit, has_accelerator
from std.ffi import external_call
from std.time import perf_counter_ns


alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _HP = UnsafePointer[Float16, origin=MutAnyOrigin]


def _fill_f32(dst: _FP, val_i64: Int64, n_i64: Int64):
    var val = Float32(Float64(Int(val_i64)))
    var n = Int(n_i64)
    var i = Int(block_idx.x) * 256 + Int(thread_idx.x)
    if i < n:
        dst[i] = val


def _read_first_h(src: _HP, dst: _FP, n_i64: Int64):
    # dst[0] = widen(src[0]) + widen(src[n-1]) — proves the whole convert landed
    var n = Int(n_i64)
    var i = Int(block_idx.x) * 256 + Int(thread_idx.x)
    if i == 0:
        dst[0] = Float32(src[0]) + Float32(src[n - 1])


def _write_from_f32(dst: _FP, src: _HP, n_i64: Int64):
    var n = Int(n_i64)
    var i = Int(block_idx.x) * 256 + Int(thread_idx.x)
    if i < n:
        dst[i] = Float32(src[i])


def _shim_init() -> Int:
    return Int(external_call["tc_shim_init", Int64]())


def _use_stream(addr: Int) -> Int:
    return Int(external_call["tc_shim_use_stream", Int64, Int64](Int64(addr)))


def _f32_to_f16(src: Int, dst: Int, n: Int) -> Int:
    return Int(
        external_call["tc_shim_f32_to_f16", Int64, Int64, Int64, Int64](
            Int64(src), Int64(dst), Int64(n))
    )


def _stream_sync() -> Int:
    return Int(external_call["tc_shim_stream_sync", Int64]())


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return
    var ctx = DeviceContext()

    # init the shim, then bind it to the LEGACY default stream (0x1)
    _ = _shim_init()
    var r = _use_stream(1)
    print("tc_shim_use_stream(legacy) ->", r)
    if r != 0:
        exit(1)

    var n = 4096
    var f32a = ctx.enqueue_create_buffer[DType.float32](n)
    var f16a = ctx.enqueue_create_buffer[DType.float16](n)
    var out = ctx.enqueue_create_buffer[DType.float32](256)
    var hout = ctx.enqueue_create_host_buffer[DType.float32](256)

    # ── T1: legacy convert FIRST, Mojo kernel reads it ──
    ctx.enqueue_function[_fill_f32](f32a.unsafe_ptr(), Int64(7), Int64(n),
                                    grid_dim=16, block_dim=256)
    ctx.synchronize()
    r = _f32_to_f16(Int(f32a.unsafe_ptr()), Int(f16a.unsafe_ptr()), n)
    if r != 0:
        print("T1 convert dispatch failed:", r)
        exit(1)
    # NO sync — straight onto the Mojo stream
    ctx.enqueue_function[_read_first_h](f16a.unsafe_ptr(), out.unsafe_ptr(), Int64(n),
                                        grid_dim=1, block_dim=256)
    ctx.enqueue_copy(hout, out)
    ctx.synchronize()
    print("T1 legacy->mojo ordering value:", Float64(hout.unsafe_ptr()[0]),
          "|", "ORDERED" if Float64(hout.unsafe_ptr()[0]) == 14.0 else "| RACE")

    # ── T2: Mojo kernel writes, legacy convert reads it ──
    ctx.enqueue_function[_fill_f32](f32a.unsafe_ptr(), Int64(9), Int64(n),
                                    grid_dim=16, block_dim=256)
    # NO sync — legacy convert enqueues right after
    r = _f32_to_f16(Int(f32a.unsafe_ptr()), Int(f16a.unsafe_ptr()), n)
    if r != 0:
        print("T2 convert dispatch failed:", r)
        exit(1)
    ctx.enqueue_function[_write_from_f32](out.unsafe_ptr(), f16a.unsafe_ptr(), Int64(256),
                                          grid_dim=1, block_dim=256)
    ctx.enqueue_copy(hout, out)
    ctx.synchronize()
    print("T2 mojo->legacy ordering value:", Float64(hout.unsafe_ptr()[0]),
          "|", "ORDERED" if Float64(hout.unsafe_ptr()[0]) == 9.0 else "| RACE")

    # ── T3: 200 interleaved seams, zero host syncs, then one check ──
    var t0 = perf_counter_ns()
    for k in range(100):
        ctx.enqueue_function[_fill_f32](f32a.unsafe_ptr(), Int64(k + 1), Int64(n),
                                        grid_dim=16, block_dim=256)
        _ = _f32_to_f16(Int(f32a.unsafe_ptr()), Int(f16a.unsafe_ptr()), n)
    ctx.enqueue_function[_write_from_f32](out.unsafe_ptr(), f16a.unsafe_ptr(), Int64(256),
                                          grid_dim=1, block_dim=256)
    ctx.enqueue_copy(hout, out)
    ctx.synchronize()
    var t1 = perf_counter_ns()
    print("T3 100-iteration seam chain value:", Float64(hout.unsafe_ptr()[0]),
          "|", "ORDERED" if Float64(hout.unsafe_ptr()[0]) == 100.0 else "| RACE",
          "| wall:", Float64(t1 - t0) / 1.0e6, "ms")
    print("LEGACY PROBE DONE")
