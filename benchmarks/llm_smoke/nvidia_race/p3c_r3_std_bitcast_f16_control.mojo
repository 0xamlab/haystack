"""p3c_r3_std_bitcast_f16_control.mojo — packed-int8 phase 0, control probe: the PROVEN
direction from f16_vec8_probe.mojo (w_i32.load[width=4](...).unsafe_bitcast[SIMD[Float16, 8]]())
re-spelled with the Mojo 1.0.0 std.memory.bitcast API. The old method spelling fails on the
pinned toolchain (verified: 'SIMD[DType.int32, SIMDLength(4)]' value has no attribute
'unsafe_bitcast'), so the f16 as-int kernel only survives via this spelling — this probe
confirms it lowers for the NVPTX target.

Compile probe (macOS build host, no GPU needed):
    mojo build p3c_r3_std_bitcast_f16_control.mojo --target-accelerator sm_80 -o probe
"""

from std.gpu import thread_idx
from max.gpu.host import DeviceContext
from std.memory import bitcast
from std.origin import MutAnyOrigin


def _k(dst: UnsafePointer[Float32, origin=MutAnyOrigin]):
    var v = SIMD[DType.int32, 4](Int32(1065353216))  # 1.0f bit pattern per word
    var h = bitcast[DType.float16, 8](v)
    var f = h.cast[DType.float32]()
    var s = Float32(0.0)
    for e in range(8):
        s += f[e]
    dst[Int(thread_idx.x)] = s


def main() raises:
    var ctx = DeviceContext()
    var buf = ctx.enqueue_create_buffer[DType.float32](32)
    ctx.enqueue_function[_k](buf.unsafe_ptr(), grid_dim=1, block_dim=32)
    ctx.synchronize()
