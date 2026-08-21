"""p1_r1_floor_trunc.mojo — packed-int8 phase 0, probe P1 (recipe R1, the floor-recipe):
does std.math.floor / std.math.trunc on Float32 lower for the NVPTX target? The packed-int8
campaign streams 3 unsigned int8 quants per Float32 word (v = b0 + 256*b1 + 65536*b2, exact
for values < 2^24) through the proven 128-bit float4 load path; R1 unpacks entirely in
Float32 arithmetic: b2 = floor(v/65536); r = v - b2*65536; b1 = floor(r/256); b0 = trunc(r -
b1*256). The kernel recomputes the packed word from the extracted bytes and stores it.

Compile probe (macOS build host, no GPU needed):
    mojo build p1_r1_floor_trunc.mojo --target-accelerator sm_80 -o probe
"""

from std.gpu import thread_idx
from max.gpu.host import DeviceContext
from std.math import floor, trunc
from std.origin import MutAnyOrigin


def _k(dst: UnsafePointer[Float32, origin=MutAnyOrigin]):
    var v = Float32(66051.0)  # b0=3 + 256*b1=2 + 65536*b2=1
    var b2 = floor(v / Float32(65536.0))
    var r = v - b2 * Float32(65536.0)
    var b1 = floor(r / Float32(256.0))
    var b0 = trunc(r - b1 * Float32(256.0))
    dst[Int(thread_idx.x)] = b2 * Float32(65536.0) + b1 * Float32(256.0) + b0


def main() raises:
    var ctx = DeviceContext()
    var buf = ctx.enqueue_create_buffer[DType.float32](32)
    ctx.enqueue_function[_k](buf.unsafe_ptr(), grid_dim=1, block_dim=32)
    ctx.synchronize()
