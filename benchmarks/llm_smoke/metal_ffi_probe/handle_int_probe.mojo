from std.builtin.type_aliases import MutAnyOrigin
from std.gpu.host import DeviceContext
from std.sys import has_accelerator


fn _k(o: UnsafePointer[Float32, origin=MutAnyOrigin]):
    if o[0] == Float32(999999.0):
        o[0] = Float32(1.0)


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return
    var ctx = DeviceContext()
    var fn_obj = ctx.compile_function[_k, _k]()

    var raw = fn_obj._handle
    print("raw handle:", raw)
    var ptr = raw.value()
    var as_int = Int(ptr)
    print("as int:", as_int)

    var as_u64ptr = ptr.bitcast[UInt64]()
    print("bitcast to UInt64 ptr ok:", as_u64ptr)
    print("word[0] =", as_u64ptr[0])
    print("word[1] =", as_u64ptr[1])
    print("word[2] =", as_u64ptr[2])
    print("word[3] =", as_u64ptr[3])
