"""p2b_r2_simd_cast_int32.mojo — packed-int8 phase 0, probe P2b (recipe R2, SIMD arm):
does SIMD[DType.float32, 4].cast[DType.int32]() (a numeric float->int conversion on a SIMD
value) lower for the NVPTX target? If this spelling fails, the same target type is also
reached via the unsafe_bitcast spelling — that is probe P3a, which is this probe's fallback.

Compile probe (macOS build host, no GPU needed):
    mojo build p2b_r2_simd_cast_int32.mojo --target-accelerator sm_80 -o probe
"""

from std.gpu import thread_idx
from max.gpu.host import DeviceContext
from std.origin import MutAnyOrigin


def _k(dst: UnsafePointer[Int32, origin=MutAnyOrigin]):
    var v = SIMD[DType.float32, 4](Float32(66051.0))
    var w = v.cast[DType.int32]()
    var s = Int32(0)
    for e in range(4):
        s += w[e]
    dst[Int(thread_idx.x)] = s


def main() raises:
    var ctx = DeviceContext()
    var buf = ctx.enqueue_create_buffer[DType.int32](32)
    ctx.enqueue_function[_k](buf.unsafe_ptr(), grid_dim=1, block_dim=32)
    ctx.synchronize()
