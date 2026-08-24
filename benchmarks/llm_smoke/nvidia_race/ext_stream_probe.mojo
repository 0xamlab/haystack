"""ext_stream_probe.mojo — does create_external_stream join the context stream pool (so a
select_stream VIEW with the full enqueue surface can address it), and what surface does the
DeviceStream value itself carry? Also verifies a raw extern-created stream + view enqueue
actually EXECUTE (data check)."""

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
    print("num_streams at open:", ctx.num_streams())
    var n0 = ctx.num_streams()

    var addr = _probe_create_stream()
    print("tc_shim_create_stream ->", addr)
    if addr == 0:
        print("STREAM CREATE FAILED")
        exit(1)

    var raw = UnsafePointer[NoneType, origin=MutAnyOrigin](unsafe_from_address=addr)
    var ds = ctx.create_external_stream(raw)
    var n1 = ctx.num_streams()
    print("num_streams after create_external_stream:", n1)

    # Q1: did the pool grow so select_stream can address the external stream?
    if n1 > n0:
        var view = ctx.select_stream(n0)
        var buf = view.enqueue_create_buffer[DType.float32](256)
        var host = view.enqueue_create_host_buffer[DType.float32](256)
        view.enqueue_function[_fill_kernel](
            buf.unsafe_ptr(), Int64(42), Int64(256), grid_dim=1, block_dim=256)
        view.enqueue_copy(host, buf)
        view.synchronize()
        print("Q1 select_stream(external-id) view enqueue value:",
              Float64(host.unsafe_ptr()[0]),
              "| WORKS" if Float64(host.unsafe_ptr()[0]) == 42.0 else "| BROKEN")
    else:
        print("Q1: pool did NOT grow — select_stream cannot address the external stream")

    # Q2: what does the DeviceStream value itself expose? (compile-time surface check —
    # each candidate is behind its own comptime gate; flip to test)
    comptime TEST_DS_SYNC: Bool = True
    @parameter
    if TEST_DS_SYNC:
        ds.synchronize()
        print("Q2a DeviceStream.synchronize() COMPILES")
    print("PROBE DONE")
