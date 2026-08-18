"""handle_probe.mojo — background step (1): does DeviceFunction (or DeviceContext) expose its
`_handle` field readably from OUTSIDE `std.gpu.host.device_context`, and what does raw memory at
that address look like? Mojo does not enforce field privacy, so this probe just reads `._handle`
directly and dumps memory around it.

Throwaway recon probe, new namespace, touches nothing frozen.
"""
from std.origin import MutAnyOrigin  # Mojo 1.0.0: origins left std.builtin.type_aliases
from max.gpu.host import DeviceContext
from std.sys import has_accelerator


def _k(o: UnsafePointer[Float32, origin=MutAnyOrigin]):
    if o[0] == Float32(999999.0):
        o[0] = Float32(1.0)


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return
    var ctx = DeviceContext()
    print("device:", ctx.name())

    var fn_obj = ctx.compile_function[_k, _k]()
    print("compiled ok")

    var raw = fn_obj._handle
    print("fn_obj._handle =", raw)

    var ctx_handle = ctx._handle
    print("ctx._handle    =", ctx_handle)
