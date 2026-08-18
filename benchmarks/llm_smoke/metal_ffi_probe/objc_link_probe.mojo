"""objc_link_probe.mojo — the FIRST question before anything else: can a Mojo binary, built via
`pixi run mojo build`, resolve and call bare libobjc/Metal C symbols (`sel_registerName`,
`objc_getClass`, `objc_msgSend`, `MTLCreateSystemDefaultDevice`) via `external_call`, and does it
even LINK? This is step 0 for background steps 1/2/4 -- everything downstream needs this to work.

Throwaway recon probe, new namespace, touches nothing frozen.

Build:
    cd mojo_env && DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU ../benchmarks/llm_smoke/metal_ffi_probe/objc_link_probe.mojo \
      -o /tmp/objc_link_probe \
      -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker Metal
"""
from std.ffi import external_call
from max.gpu.host import DeviceContext
from std.sys import has_accelerator


def _cstr(s: StaticString) -> UnsafePointer[UInt8, origin=StaticConstantOrigin]:
    return s.unsafe_ptr()


def main() raises:
    # Force Metal.framework to actually be loaded in-process by constructing a real
    # DeviceContext first (MAX's own Metal backend does this internally already).
    if not has_accelerator():
        print("no accelerator; skipping (link behavior still checked at build time)")
    else:
        var ctx = DeviceContext()
        print("DeviceContext constructed:", ctx.name())

    print("")
    print("[1] sel_registerName(\"release\") ...")
    var sel = external_call["sel_registerName", OpaquePointer[MutAnyOrigin]](
        _cstr("release")
    )
    print("    got SEL pointer:", sel)

    print("")
    print("[2] objc_getClass(\"NSString\") ...")
    var cls = external_call["objc_getClass", OpaquePointer[MutAnyOrigin]](
        _cstr("NSString")
    )
    print("    got Class pointer:", cls)

    print("")
    print("[3] MTLCreateSystemDefaultDevice() -- bare C function, not objc_msgSend ...")
    var dev = external_call["MTLCreateSystemDefaultDevice", OpaquePointer[MutAnyOrigin]]()
    print("    got device pointer:", dev)

    print("")
    print("[4] objc_msgSend(dev, sel_registerName(\"retain\")) -- a real message send ...")
    var sel_retain = external_call["sel_registerName", OpaquePointer[MutAnyOrigin]](
        _cstr("retain")
    )
    var retained = external_call[
        "objc_msgSend", OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin]
    ](dev, sel_retain)
    print("    objc_msgSend returned:", retained, " (expect == dev pointer above)")

    print("")
    print("ALL FOUR CALLS RETURNED WITHOUT CRASHING. libobjc + Metal C symbols are reachable")
    print("from Mojo via external_call, in a real build.")
