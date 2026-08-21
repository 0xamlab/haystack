"""p4_control_int32_chain.mojo — packed-int8 phase 0, probe P4 (the control that MUST pass):
scalar Int32 &, >>, % chains on device. Already evidenced by i8_via_int32_probe.mojo's V2
kernel (word & 0xFF on each Int32 word loaded via the proven float4-byte path), included
here so the battery has a known-good baseline: if P4 fails, the battery itself is broken.

Compile probe (macOS build host, no GPU needed):
    mojo build p4_control_int32_chain.mojo --target-accelerator sm_80 -o probe
"""

from std.gpu import thread_idx
from max.gpu.host import DeviceContext
from std.origin import MutAnyOrigin


def _k(dst: UnsafePointer[Int32, origin=MutAnyOrigin]):
    var word = Int32(66051)
    var b0 = word & 255
    var b1 = (word >> 8) & 255
    var b2 = (word >> 16) & 255
    var c = word % 256
    dst[Int(thread_idx.x)] = b0 + b1 + b2 + c


def main() raises:
    var ctx = DeviceContext()
    var buf = ctx.enqueue_create_buffer[DType.int32](32)
    ctx.enqueue_function[_k](buf.unsafe_ptr(), grid_dim=1, block_dim=32)
    ctx.synchronize()
