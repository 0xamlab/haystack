"""ext_stream_probe2.mojo — which method launches a KERNEL on a DeviceStream, and what
copy surface does it carry? Each candidate is behind its own comptime gate (dead branches
do not elaborate); flip the gates to test."""

from max.gpu.host import DeviceContext
from std.gpu import block_idx, thread_idx
from std.origin import MutAnyOrigin
from std.sys import exit, has_accelerator
from std.ffi import external_call


alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]


def _fill_kernel(dst: _FP, val_i64: Int64, n_i64: Int64):
    var val = Float32(Float64(Int(val_i64)))
    var n = Int(n_i64)
    var i = Int(block_idx.x) * 256 + Int(thread_idx.x)
    if i < n:
        dst[i] = val


def _probe_create_stream() -> Int:
    return Int(external_call["tc_shim_create_stream", Int64]())


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return

    var ctx = DeviceContext()
    var addr = _probe_create_stream()
    if addr == 0:
        print("STREAM CREATE FAILED")
        exit(1)
    var raw = UnsafePointer[NoneType, origin=MutAnyOrigin](unsafe_from_address=addr)
    var ds = ctx.create_external_stream(raw)

    var buf = ctx.enqueue_create_buffer[DType.float32](256)
    var host = ctx.enqueue_create_host_buffer[DType.float32](256)

    comptime T_ENQUEUE_KERNEL: Bool = True
    comptime T_LAUNCH: Bool = False
    comptime T_ENQUEUE_LAUNCH: Bool = False
    comptime T_SUBMIT: Bool = False
    comptime T_COPY: Bool = False

    @parameter
    if T_ENQUEUE_KERNEL:
        ds.enqueue_kernel[_fill_kernel](
            buf.unsafe_ptr(), Int64(7), Int64(256), grid_dim=1, block_dim=256)
        print("enqueue_kernel COMPILES")
    @parameter
    if T_LAUNCH:
        ds.launch[_fill_kernel](
            buf.unsafe_ptr(), Int64(7), Int64(256), grid_dim=1, block_dim=256)
        print("launch COMPILES")
    @parameter
    if T_ENQUEUE_LAUNCH:
        ds.enqueue_launch[_fill_kernel](
            buf.unsafe_ptr(), Int64(7), Int64(256), grid_dim=1, block_dim=256)
        print("enqueue_launch COMPILES")
    @parameter
    if T_SUBMIT:
        ds.submit[_fill_kernel](
            buf.unsafe_ptr(), Int64(7), Int64(256), grid_dim=1, block_dim=256)
        print("submit COMPILES")
    @parameter
    if T_COPY:
        ds.enqueue_copy(host, buf)
        print("enqueue_copy COMPILES")
    ds.synchronize()
    print("value:", Float64(host.unsafe_ptr()[0]))
    print("PROBE2 DONE")
