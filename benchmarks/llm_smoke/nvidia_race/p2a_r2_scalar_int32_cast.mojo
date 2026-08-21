"""p2a_r2_scalar_int32_cast.mojo — packed-int8 phase 0, probe P2a (recipe R2, scalar arm):
does the scalar numeric conversion Int32(some Float32 var) lower for the NVPTX target? R2
unpacks the packed word by first converting it to Int32, then extracting bytes with integer
& / >>. This probe isolates the conversion primitive itself: cast and store.

Compile probe (macOS build host, no GPU needed):
    mojo build p2a_r2_scalar_int32_cast.mojo --target-accelerator sm_80 -o probe
"""

from std.gpu import thread_idx
from max.gpu.host import DeviceContext
from std.origin import MutAnyOrigin


def _k(dst: UnsafePointer[Int32, origin=MutAnyOrigin]):
    var v = Float32(66051.0)  # b0=3 + 256*b1=2 + 65536*b2=1
    var w = Int32(v)
    dst[Int(thread_idx.x)] = w


def main() raises:
    var ctx = DeviceContext()
    var buf = ctx.enqueue_create_buffer[DType.int32](32)
    ctx.enqueue_function[_k](buf.unsafe_ptr(), grid_dim=1, block_dim=32)
    ctx.synchronize()
