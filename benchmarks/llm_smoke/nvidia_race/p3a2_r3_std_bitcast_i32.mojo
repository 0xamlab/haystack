"""p3a2_r3_std_bitcast_i32.mojo — packed-int8 phase 0, probe P3a2 (recipe R3, int32 view,
the Mojo 1.0.0 spelling): P3a proved the 1.0.0b2-era `.unsafe_bitcast` SIMD method no longer
exists in mojo 1.0.0; std.mojoc shows its successor is the module function
`std.memory.bitcast[dtype, width](val)` ("Bitcasts a SIMD value to another SIMD value",
bitwidths must match). This probe asks the real R3 question with the pinned toolchain's
spelling: does bitcast[DType.int32, 4](SIMD[float32,4]) + scalar & / >> byte extraction
lower for the NVPTX target?

Compile probe (macOS build host, no GPU needed):
    mojo build p3a2_r3_std_bitcast_i32.mojo --target-accelerator sm_80 -o probe
"""

from std.gpu import thread_idx
from max.gpu.host import DeviceContext
from std.memory import bitcast
from std.origin import MutAnyOrigin


def _k(dst: UnsafePointer[Int32, origin=MutAnyOrigin]):
    var v = SIMD[DType.float32, 4](Float32(66051.0))
    var w = bitcast[DType.int32, 4](v)
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
