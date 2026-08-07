"""mma_abism_probe.mojo — Phase 0 ABI smoke test for the cross-toolchain "kernel forge" mechanism.

THROWAWAY, NOT WIRED INTO PRODUCTION. Proves the whole extraction-and-relink mechanism end to end,
on real Metal hardware, before any real MMA kernel is written: a trivial kernel compiled on the
PINNED toolchain (bare `Int` scalar args, embedded normally via `compile_function_unchecked`) and
the SAME computation compiled on the forge toolchain (`mojo=1.1.0.dev2026080606`+`max`, `Int64`
scalar args, extracted via `mma_forge/tools/extract_blob.py` into `mma_forge/generated/abism_blob.c`
and linked in as one more `-Xlinker` object) are both discovered by the existing, UNMODIFIED
`algenta_open_session()` and dispatched through the existing, UNMODIFIED `algenta_run_token()` —
if their outputs match bit-for-bit, the mechanism (blob extraction, symbol-free re-embedding,
provenance-agnostic discovery, cross-compiler-version argument ABI) is proven for real hardware
kernels, not just theorized.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../mma_forge/generated/abism_blob.c -o /tmp/abism_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/mma_abism_probe.mojo \
        -o /tmp/mma_abism_probe \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/abism_blob.o \
        -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/mma_abism_probe
"""

from metaldispatch.contract import MB_ERR_SESSION_OPEN_FAILED
from metaldispatch.ffi import (
    _mb_open_session,
    _mb_pipeline_count,
    _mb_pipeline_name,
    _mb_alloc_buffer,
    _mb_alloc_descriptors,
    _mb_set_header,
    _mb_set_arg_ptr,
    _mb_set_arg_int,
    _mb_run_token,
)

comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]


def main() raises:
    from std.gpu.host import DeviceContext
    from std.gpu import thread_idx

    def _abism_pinned_kernel_real(d_out: _FP, scale: Int, base: Int):
        var tid = Int(thread_idx.x)
        d_out[tid] = Float32(tid) * Float32(scale) + Float32(base)

    var cctx = DeviceContext()
    _ = cctx.compile_function[_abism_pinned_kernel_real]()

    var opened = _mb_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session failed, status=", MB_ERR_SESSION_OPEN_FAILED)
        return

    var count = _mb_pipeline_count()
    print("discovered pipelines:", count)
    var pinned_idx = -1
    var forge_idx = -1
    for i in range(count):
        var name = String()
        _ = _mb_pipeline_name(i, name)
        print(" [", i, "]", name)
        if "abism_pinned_k" in name:
            pinned_idx = i
        if "abism_forge_kernel" in name:
            forge_idx = i

    if pinned_idx < 0:
        print("FAIL: pinned-toolchain abism kernel not discovered")
        return
    if forge_idx < 0:
        print("FAIL: forge-toolchain abism kernel not discovered -- extraction/relink mechanism broken")
        return
    print("pinned_idx =", pinned_idx, " forge_idx =", forge_idx)

    var addr_pinned: UInt64 = 0
    var contents_pinned = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var addr_forge: UInt64 = 0
    var contents_forge = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    if _mb_alloc_buffer(128, addr_pinned, contents_pinned) < 0:
        print("FAIL: alloc_buffer (pinned) failed")
        return
    if _mb_alloc_buffer(128, addr_forge, contents_forge) < 0:
        print("FAIL: alloc_buffer (forge) failed")
        return

    var descs = _mb_alloc_descriptors(2)
    _mb_set_header(descs, 0, pinned_idx, 1, 32, 3)
    _mb_set_arg_ptr(descs, 0, 0, addr_pinned)
    _mb_set_arg_int(descs, 0, 1, 3)
    _mb_set_arg_int(descs, 0, 2, 7)

    _mb_set_header(descs, 1, forge_idx, 1, 32, 3)
    _mb_set_arg_ptr(descs, 1, 0, addr_forge)
    _mb_set_arg_int(descs, 1, 1, 3)
    _mb_set_arg_int(descs, 1, 2, 7)

    if _mb_run_token(descs, 2) != 0:
        print("FAIL: algenta_run_token failed")
        return

    var out_pinned = contents_pinned.bitcast[Float32]()
    var out_forge = contents_forge.bitcast[Float32]()
    var worst = Float32(0.0)
    for i in range(32):
        var d = out_pinned[i] - out_forge[i]
        if d < 0:
            d = -d
        if d > worst:
            worst = d
        var want = Float32(i) * Float32(3) + Float32(7)
        if out_pinned[i] != want:
            print("MISMATCH pinned vs formula at", i, ":", out_pinned[i], "want", want)

    print("pinned[5] =", out_pinned[5], " forge[5] =", out_forge[5])
    print("worst |pinned-forge| delta:", worst)
    if worst == Float32(0.0):
        print("ABISM PROBE: PASS -- cross-toolchain blob-forge mechanism verified bit-exact")
    else:
        print("ABISM PROBE: FAIL -- pinned and forge outputs diverge")
