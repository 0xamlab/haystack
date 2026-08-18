from std.origin import MutAnyOrigin  # Mojo 1.0.0: origins left std.builtin.type_aliases
from max.gpu.host import DeviceContext
from std.sys import has_accelerator


def _trace_kernel(o: UnsafePointer[Float32, origin=MutAnyOrigin]):
    if o[0] == Float32(12345.0):
        o[0] = Float32(1.0)


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return
    var ctx = DeviceContext()
    var f = ctx.compile_function[_trace_kernel, _trace_kernel]()
    print("compiled")
