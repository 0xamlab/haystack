from std.builtin.type_aliases import MutAnyOrigin
from std.gpu import block_dim, block_idx, thread_idx
from std.gpu.host import DeviceContext
from std.sys import has_accelerator


fn _gemv_kernel(
    y_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    x_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    w_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    k: Int,
    n: Int,
):
    var j = Int(block_idx.x * block_dim.x + thread_idx.x)
    if j >= n:
        return
    var acc = Float32(0.0)
    for i in range(k):
        acc += x_ptr[i] * w_ptr[i * n + j]
    y_ptr[j] = acc


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return
    var ctx = DeviceContext()
    var f = ctx.compile_function[_gemv_kernel, _gemv_kernel]()
    print("compiled gemv kernel ok")
