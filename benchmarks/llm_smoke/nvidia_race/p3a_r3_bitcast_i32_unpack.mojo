"""p3a_r3_bitcast_i32_unpack.mojo — packed-int8 phase 0, probe P3a (recipe R3, int32 view):
does SIMD[DType.float32, 4].unsafe_bitcast[SIMD[DType.int32, 4]]() lower for the NVPTX
target? This mirrors the PROVEN direction in f16_vec8_probe.mojo
(w_i32.load[width=4](...).unsafe_bitcast[SIMD[Float16, 8]]()) — here the integer SIMD is the
TARGET, not the source. The kernel then runs the full R3 unpack: scalar & / >> byte
extraction on each bitcast word, summed and stored.

Compile probe (macOS build host, no GPU needed):
    mojo build p3a_r3_bitcast_i32_unpack.mojo --target-accelerator sm_80 -o probe
"""

from std.gpu import thread_idx
from max.gpu.host import DeviceContext
from std.origin import MutAnyOrigin


def _k(dst: UnsafePointer[Int32, origin=MutAnyOrigin]):
    var v = SIMD[DType.float32, 4](Float32(66051.0))
    var w = v.unsafe_bitcast[SIMD[DType.int32, 4]]()
    var s = Int32(0)
    for e in range(4):
        var word = w[e]
        var b0 = word & 255
        var b1 = (word >> 8) & 255
        var b2 = (word >> 16) & 255
        s += b0 + b1 + b2
    dst[Int(thread_idx.x)] = s


def main() raises:
    var ctx = DeviceContext()
    var buf = ctx.enqueue_create_buffer[DType.int32](32)
    ctx.enqueue_function[_k](buf.unsafe_ptr(), grid_dim=1, block_dim=32)
    ctx.synchronize()
