"""p3b2_r3_std_bitcast_u8.mojo — packed-int8 phase 0, probe P3b2 (recipe R3, uint8 view,
the Mojo 1.0.0 spelling): P3b proved the 1.0.0b2-era `.unsafe_bitcast` SIMD method no longer
exists in mojo 1.0.0; this is the pinned toolchain's successor spelling
(std.memory.bitcast, documented example: u8x4 = bitcast[DType.uint8, 4](u32)). 4 Float32
words = 16 bytes = 16 uint8 lanes — a direct byte view of the packed stream, from which the
3 quants per word are pure lane selection. The kernel sums the bytes of the first packed
word (lanes 0-2) widened to Int32 and stores it.

Compile probe (macOS build host, no GPU needed):
    mojo build p3b2_r3_std_bitcast_u8.mojo --target-accelerator sm_80 -o probe
"""

from std.gpu import thread_idx
from max.gpu.host import DeviceContext
from std.memory import bitcast
from std.origin import MutAnyOrigin


def _k(dst: UnsafePointer[Int32, origin=MutAnyOrigin]):
    var v = SIMD[DType.float32, 4](Float32(66051.0))
    var b = bitcast[DType.uint8, 16](v)
    var s = Int32(0)
    for e in range(3):
        s += Int32(b[e])
    dst[Int(thread_idx.x)] = s


def main() raises:
    var ctx = DeviceContext()
    var buf = ctx.enqueue_create_buffer[DType.int32](32)
    ctx.enqueue_function[_k](buf.unsafe_ptr(), grid_dim=1, block_dim=32)
    ctx.synchronize()
