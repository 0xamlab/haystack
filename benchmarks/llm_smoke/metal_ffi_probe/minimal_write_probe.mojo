"""minimal_write_probe.mojo — isolate the metal_ffi_dispatch_probe.mojo write-not-observed bug:
does a hand-rolled dispatch of the SIMPLEST possible Mojo-compiled kernel (one buffer arg,
unconditional write, no scalar args, no loop) actually get seen by the host afterward?
"""
from std.origin import MutAnyOrigin  # Mojo 1.0.0: origins left std.builtin.type_aliases
from std.ffi import external_call
from std.gpu import block_dim, block_idx, thread_idx
from max.gpu.host import DeviceContext
from std.memory import alloc
from std.sys import has_accelerator


def _write42(o: UnsafePointer[Float32, origin=MutAnyOrigin]):
    var i = Int(block_idx.x * block_dim.x + thread_idx.x)
    var v = o[i]
    o[i] = v + Float32(42.0)


def _cstr(s: StaticString) -> UnsafePointer[UInt8, origin=StaticConstantOrigin]:
    return s.unsafe_ptr()


def sel(name: StaticString) -> OpaquePointer[MutAnyOrigin]:
    return external_call["algenta_sel", OpaquePointer[MutAnyOrigin], UnsafePointer[UInt8, origin=StaticConstantOrigin]](_cstr(name))


def msg0(recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin]) -> OpaquePointer[MutAnyOrigin]:
    return external_call["algenta_msg0", OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin]](recv, s)


def msg0_void(recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin]):
    external_call["algenta_msg0_void", NoneType, OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin]](recv, s)


def msg1p_void(recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin], a0: OpaquePointer[MutAnyOrigin]):
    external_call["algenta_msg1p_void", NoneType, OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin]](recv, s, a0)


def new_buffer(dev: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin], length: UInt64) -> OpaquePointer[MutAnyOrigin]:
    return external_call["algenta_msg_newbuffer", OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], UInt64, UInt64](dev, s, length, UInt64(0))


def set_buffer(enc: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin], buf: OpaquePointer[MutAnyOrigin], offset: UInt64, index: UInt64):
    external_call["algenta_msg_setbuffer", NoneType, OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], UInt64, UInt64](enc, s, buf, offset, index)


def dispatch_threadgroups(enc: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin], gw: UInt64, gh: UInt64, gd: UInt64, tw: UInt64, th: UInt64, td: UInt64):
    external_call["algenta_msg_dispatch", NoneType, OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], UInt64, UInt64, UInt64, UInt64, UInt64, UInt64](enc, s, gw, gh, gd, tw, th, td)


def dispatch_data_from(ptr: UnsafePointer[UInt8, origin=MutAnyOrigin], length: UInt64) -> OpaquePointer[MutAnyOrigin]:
    return external_call["algenta_dispatch_data_create", OpaquePointer[MutAnyOrigin], UnsafePointer[UInt8, origin=MutAnyOrigin], UInt64](ptr, length)


def msg2p_err(recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin], a0: OpaquePointer[MutAnyOrigin], err_out: UnsafePointer[OpaquePointer[MutAnyOrigin], origin=MutAnyOrigin]) -> OpaquePointer[MutAnyOrigin]:
    return external_call["algenta_msg_2p_err", OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], UnsafePointer[OpaquePointer[MutAnyOrigin], origin=MutAnyOrigin]](recv, s, a0, err_out)


def msg1p(recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin], a0: OpaquePointer[MutAnyOrigin]) -> OpaquePointer[MutAnyOrigin]:
    return external_call["algenta_msg1p", OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin]](recv, s, a0)


def msg1u_ret(recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin], a0: UInt64) -> OpaquePointer[MutAnyOrigin]:
    return external_call["algenta_msg1u_ret", OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], UInt64](recv, s, a0)


def msg0_i64(recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin]) -> Int64:
    return external_call["algenta_msg0_i64", Int64, OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin]](recv, s)


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return
    var ctx = DeviceContext()
    _ = ctx.compile_function[_write42, _write42]()
    print("compiled ok")

    var mh = external_call["_dyld_get_image_header", OpaquePointer[MutAnyOrigin], UInt32](UInt32(0))
    var size_out = UInt64(0)
    var sect = external_call[
        "getsectiondata", UnsafePointer[UInt8, origin=MutAnyOrigin], OpaquePointer[MutAnyOrigin],
        UnsafePointer[UInt8, origin=StaticConstantOrigin], UnsafePointer[UInt8, origin=StaticConstantOrigin],
        UnsafePointer[UInt64, origin=MutAnyOrigin],
    ](mh, _cstr("__TEXT"), _cstr("__const"), UnsafePointer(to=size_out))
    var sect_size = Int(size_out)
    var magic_off = -1
    var declared_len = 0
    var i = 0
    while i < sect_size - 20:
        if sect[i] == 0x4D and sect[i + 1] == 0x54 and sect[i + 2] == 0x4C and sect[i + 3] == 0x42:
            var len_ptr = (sect + i + 16).bitcast[UInt64]()
            var cand = Int(len_ptr[0])
            if cand > 20 and i + cand <= sect_size:
                magic_off = i
                declared_len = cand
                break
        i += 1
    print("MTLB at", magic_off, "len", declared_len)

    var dev = external_call["MTLCreateSystemDefaultDevice", OpaquePointer[MutAnyOrigin]]()
    var ddata = dispatch_data_from(sect + magic_off, UInt64(declared_len))
    var errptr = alloc[OpaquePointer[MutAnyOrigin]](1)
    errptr[0] = OpaquePointer[MutAnyOrigin]()
    var lib = msg2p_err(dev, sel("newLibraryWithData:error:"), ddata, errptr)
    if not lib:
        raise Error("load failed")
    var names = msg0(lib, sel("functionNames"))
    var fname = msg1u_ret(names, sel("objectAtIndex:"), UInt64(0))
    var raw_fn = msg1p(lib, sel("newFunctionWithName:"), fname)
    errptr[0] = OpaquePointer[MutAnyOrigin]()
    var pso = msg2p_err(dev, sel("newComputePipelineStateWithFunction:error:"), raw_fn, errptr)
    if not pso:
        raise Error("pso failed")
    print("pso ok")

    var buf = new_buffer(dev, sel("newBufferWithLength:options:"), UInt64(256 * 4))
    var contents = msg0(buf, sel("contents")).bitcast[Float32]()
    for j in range(256):
        contents[j] = Float32(-1.0)

    var queue = msg0(dev, sel("newCommandQueue"))
    var cb = msg0(queue, sel("commandBuffer"))
    var enc = msg0(cb, sel("computeCommandEncoder"))
    msg1p_void(enc, sel("setComputePipelineState:"), pso)
    set_buffer(enc, sel("setBuffer:offset:atIndex:"), buf, 0, 0)
    dispatch_threadgroups(enc, sel("dispatchThreadgroups:threadsPerThreadgroup:"), 1, 1, 1, 256, 1, 1)
    msg0_void(enc, sel("endEncoding"))
    msg0_void(cb, sel("commit"))
    msg0_void(cb, sel("waitUntilCompleted"))

    var status = msg0_i64(cb, sel("status"))
    print("command buffer status:", status, " (0=notEnqueued 1=enqueued 2=committed 3=scheduled 4=completed 5=error)")
    var cb_err = msg0(cb, sel("error"))
    if cb_err:
        var desc = msg0(cb_err, sel("description"))
        var cdesc = msg0(desc, sel("UTF8String")).bitcast[UInt8]()
        var s2 = String()
        var idx = 0
        while cdesc[idx] != 0 and idx < 2000:
            s2 += chr(Int(cdesc[idx]))
            idx += 1
        print("command buffer error:", s2)
    else:
        print("command buffer error: <none>")

    print("contents[0] =", contents[0], " (expect 42.0)")
    print("contents[7] =", contents[7], " (expect 42.0)")
    print("contents[255] =", contents[255], " (expect 42.0)")
