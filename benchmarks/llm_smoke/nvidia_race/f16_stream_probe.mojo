"""f16_stream_probe.mojo — isolates WHERE the f16 weight path collapses on NVIDIA: is it the
Float16 LOAD or the Float16->Float32 CAST? Three pure streaming kernels over the same 12.6 MB
f16 buffer (qkv shape, one full sweep per dispatch):

  A. load f16 (width 4), cast to f32, accumulate in f32   (what the session's kernels do)
  B. load f16 (width 4), accumulate in f16, no cast       (removes the cast)
  C. load the same bytes as Int32 (width 4), sum raw bits (removes f16 entirely)

If B ~= A, the cast is not the problem and the load path is; if C >> B, the Float16-typed load
itself is the slow path (backend lowering), and the fix is Int-typed loads + software unpack.

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/f16_stream_probe.mojo -o probe
"""

from max.gpu.host import DeviceContext
from std.gpu import block_idx, thread_idx, grid_dim as gpu_grid_dim
from std.memory import UnsafePointer
from std.origin import MutAnyOrigin
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns

comptime REPS: Int = 200
comptime N_ELEM: Int = 3072 * 1024          # qkv weight elements
comptime N_I32: Int = N_ELEM // 2
comptime HBM_GB_S: Float64 = 1555.0

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _HP = UnsafePointer[Float16, origin=MutAnyOrigin]
alias _I32P = UnsafePointer[Int32, origin=MutAnyOrigin]


def _stream_f16_cast(w: _HP, sink: _FP, n_i64: Int64):
    """A: f16 load + cast to f32 + f32 accumulate."""
    var n = Int(n_i64)
    var gtid = Int(block_idx.x) * 256 + Int(thread_idx.x)
    var nthreads = Int(gpu_grid_dim.x) * 256
    var acc = Float32(0.0)
    var t = gtid * 4
    while t < n:
        var wv = w.load[width=4](t).cast[DType.float32]()
        for e in range(4):
            acc += wv[e]
        t += nthreads * 4
    if acc == Float32(1.2345e30):
        sink[gtid] = acc  # keep the accumulation alive


def _stream_f16_nocast(w: _HP, sink: _FP, n_i64: Int64):
    """B: f16 load + f16 accumulate (no cast)."""
    var n = Int(n_i64)
    var gtid = Int(block_idx.x) * 256 + Int(thread_idx.x)
    var nthreads = Int(gpu_grid_dim.x) * 256
    var acc = Float16(0.0)
    var t = gtid * 4
    while t < n:
        var wv = w.load[width=4](t)
        for e in range(4):
            acc += wv[e]
        t += nthreads * 4
    if acc == Float16(1.2345e30):
        sink[gtid] = Float32(acc)


def _stream_i32_raw(w: _I32P, sink: _FP, n_i64: Int64):
    """C: same bytes as Int32 loads + integer accumulate."""
    var n = Int(n_i64)
    var gtid = Int(block_idx.x) * 256 + Int(thread_idx.x)
    var nthreads = Int(gpu_grid_dim.x) * 256
    var acc = Int32(0)
    var t = gtid * 4
    while t < n:
        var wv = w.load[width=4](t)
        for e in range(4):
            acc += wv[e]
        t += nthreads * 4
    if acc == Int32(0x7FFFFFFE):
        sink[gtid] = Float32(acc)


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("f16_stream_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("f16_stream_probe: no accelerator")
            return

        var ctx = DeviceContext()
        print("f16_stream_probe: device:", ctx.name())
        var w_f16 = ctx.enqueue_create_buffer[DType.float16](N_ELEM)
        var w_i32 = ctx.enqueue_create_buffer[DType.int32](N_I32)
        var sink = ctx.enqueue_create_buffer[DType.float32](1024 * 1024)

        var bytes_streamed = Float64(N_ELEM) * 2.0
        var grid = 1024

        var t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_stream_f16_cast](
                w_f16.unsafe_ptr(), sink.unsafe_ptr(), Int64(N_ELEM),
                grid_dim=grid, block_dim=256)
        ctx.synchronize()
        var a_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_stream_f16_nocast](
                w_f16.unsafe_ptr(), sink.unsafe_ptr(), Int64(N_ELEM),
                grid_dim=grid, block_dim=256)
        ctx.synchronize()
        var b_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)

        t0 = perf_counter_ns()
        for _ in range(REPS):
            ctx.enqueue_function[_stream_i32_raw](
                w_i32.unsafe_ptr(), sink.unsafe_ptr(), Int64(N_I32),
                grid_dim=grid, block_dim=256)
        ctx.synchronize()
        var c_us = Float64(perf_counter_ns() - t0) / 1.0e3 / Float64(REPS)

        print("streaming", bytes_streamed / 1e6, "MB f16 buffer, grid =", grid, "x 256:")
        print("  A f16 load + cast + f32 acc:", a_us, "us ->",
              bytes_streamed / (a_us * 1e-6) / 1e9, "GB/s")
        print("  B f16 load + f16 acc (no cast):", b_us, "us ->",
              bytes_streamed / (b_us * 1e-6) / 1e9, "GB/s")
        print("  C same bytes as Int32 loads:", c_us, "us ->",
              bytes_streamed / (c_us * 1e-6) / 1e9, "GB/s")
        print("f16_stream_probe: done")
