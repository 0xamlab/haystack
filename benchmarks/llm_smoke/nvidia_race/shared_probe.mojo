"""shared_probe.mojo — minimal probe of the CUDA shared-memory ceiling on this A100 + MAX
runtime. Launches a trivial kernel whose ONLY work is allocating a compile-time shared array
of `stage` Float32 and touching element 0, stepping the size up. The program crashes at the
first size whose PTX fails to JIT (CUDA_ERROR_INVALID_PTX) or whose launch is refused, so the
last printed `OK` line is the largest shared staging this backend accepts. This decides whether
the 7B lane's 18944-float (74 KiB) decode staging can run at all."""

from max.gpu.host import DeviceBuffer, DeviceContext
from std.gpu import thread_idx
from max.gpu import barrier
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.origin import MutAnyOrigin
from std.sys import has_accelerator

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]


def _touch_3072(out_p: _FP):
    var xs = stack_allocation[3072, DType.float32, address_space = AddressSpace.SHARED]()
    if Int(thread_idx.x) == 0:
        xs[0] = 1.0
    barrier()


def _touch_6144(out_p: _FP):
    var xs = stack_allocation[6144, DType.float32, address_space = AddressSpace.SHARED]()
    if Int(thread_idx.x) == 0:
        xs[0] = 1.0
    barrier()


def _touch_8192(out_p: _FP):
    var xs = stack_allocation[8192, DType.float32, address_space = AddressSpace.SHARED]()
    if Int(thread_idx.x) == 0:
        xs[0] = 1.0
    barrier()


def _touch_12000(out_p: _FP):
    var xs = stack_allocation[12000, DType.float32, address_space = AddressSpace.SHARED]()
    if Int(thread_idx.x) == 0:
        xs[0] = 1.0
    barrier()


def _touch_16384(out_p: _FP):
    var xs = stack_allocation[16384, DType.float32, address_space = AddressSpace.SHARED]()
    if Int(thread_idx.x) == 0:
        xs[0] = 1.0
    barrier()


def _touch_18944(out_p: _FP):
    var xs = stack_allocation[18944, DType.float32, address_space = AddressSpace.SHARED]()
    if Int(thread_idx.x) == 0:
        xs[0] = 1.0
    barrier()


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return
    var ctx = DeviceContext()
    var buf = ctx.enqueue_create_buffer[DType.float32](8)

    ctx.enqueue_function[_touch_3072](buf.unsafe_ptr(), grid_dim=1, block_dim=256)
    ctx.synchronize()
    print("shared 3072 floats (12.0 KiB) -> OK")

    ctx.enqueue_function[_touch_6144](buf.unsafe_ptr(), grid_dim=1, block_dim=256)
    ctx.synchronize()
    print("shared 6144 floats (24.0 KiB) -> OK")

    ctx.enqueue_function[_touch_8192](buf.unsafe_ptr(), grid_dim=1, block_dim=256)
    ctx.synchronize()
    print("shared 8192 floats (32.0 KiB) -> OK")

    ctx.enqueue_function[_touch_12000](buf.unsafe_ptr(), grid_dim=1, block_dim=256)
    ctx.synchronize()
    print("shared 12000 floats (46.9 KiB) -> OK")

    ctx.enqueue_function[_touch_16384](buf.unsafe_ptr(), grid_dim=1, block_dim=256)
    ctx.synchronize()
    print("shared 16384 floats (64.0 KiB) -> OK")

    ctx.enqueue_function[_touch_18944](buf.unsafe_ptr(), grid_dim=1, block_dim=256)
    ctx.synchronize()
    print("shared 18944 floats (74.0 KiB) -> OK")

    print("SHARED_PROBE_DONE")
