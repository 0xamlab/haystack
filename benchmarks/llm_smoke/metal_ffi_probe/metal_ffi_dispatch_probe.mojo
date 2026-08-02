"""metal_ffi_dispatch_probe.mojo — background step (4), the deliverable: ONE Mojo-authored kernel,
dispatched via a HAND-DRIVEN MTLCommandBuffer/MTLComputeCommandEncoder reached from Mojo via
`external_call` to the Objective-C runtime, with correctness verified against the SAME kernel run
through MAX's own `DeviceContext.enqueue_function`.

The path this probe proves real (see the recon notes it grew out of, same session):
  - `objc_link_probe.mojo`  : libobjc + bare Metal C symbols are reachable from Mojo via
                              `external_call`, in a REAL linked build (`-Xlinker -framework Metal`
                              `-Xlinker -framework Foundation`).
  - `heap_scan_probe.mojo`  : `DeviceFunction`/`DeviceContext`'s own `._handle` (readable -- Mojo
                              does not enforce field privacy) points at an OPAQUE C++ object with
                              NO embedded Objective-C Metal object discoverable within 2 hops of
                              pointer-chasing (the scan technique itself is proven correct: it DOES
                              find real, unrelated live Objective-C objects at depth 2, just none
                              named MTL*/AGX* near either handle). Background step (1): not real.
  - `gemv_metallib_dump.mojo` + this file's own extraction: Mojo's `compile_function` embeds a
                              COMPLETE, standalone, well-formed `.metallib` container (magic
                              `MTLB`, a real Apple `air64-apple-macosx26.0.0` compile, the mangled
                              kernel name readable as plain text) directly in the compiled binary's
                              `__TEXT,__const` section, with a self-declared total length at
                              byte offset +16 (verified against Metal's own loader: extracting
                              exactly that many bytes and feeding them to `newLibraryWithData:`
                              (via `dispatch_data_create`, NOT NSData -- `dispatch_data_t` is not
                              toll-free-bridged with `NSData`, confirmed by making a KNOWN-GOOD
                              third-party .metallib on this machine fail the same way until fixed)
                              loads successfully and `newFunctionWithName:` resolves it exactly.
                              Background step (2): real, and simpler than step (1).
  - Metal's `MTLComputePipelineReflection` (via `newComputePipelineStateWithDescriptor:options:
                              reflection:error:`, checked once with a throwaway native probe, not
                              re-derived here) confirms Mojo emits the kernel's 5 declared
                              parameters as 5 SEQUENTIAL buffer-index arguments 0..4, in
                              declaration order -- no separate ABI reverse-engineering needed for
                              THIS kernel shape (3 pointers then 2 `Int` scalars, each `Int` at
                              Metal's `long`/8-byte width, matching Mojo's 64-bit `Int` on this
                              target).

This file does all of it FROM MOJO -- no separate .m binary, no `mojo run` JIT (build only).

RESULT OF RUNNING IT (recorded here, not just in the investigation write-up): the pipeline builds
and dispatches without crashing or erroring (`MTLCommandBuffer.status == completed`, `.error ==
nil`), but the kernel's buffer WRITE never lands -- `y` stays at its pre-dispatch sentinel value,
confirmed on both this kernel and a 1-argument minimal case (`minimal_write_probe.mojo`). This
reproduces IDENTICALLY in a from-scratch, ARC-managed, pure Objective-C harness driving the exact
same extracted `.metallib` bytes (`/tmp/native_dispatch_test.m` in the investigation notes) --
ruling out this file's own FFI/shim as the cause. `MTLComputePipelineReflection` shows the
buffer argument's `Access` as `MTLBindingAccessReadOnly` even though the Mojo kernel writes to it
(and even for a kernel that ONLY writes, never reads it). Working theory: Mojo's Metal codegen
marks kernel buffer arguments read-only in the compiled AIR regardless of actual use, and Metal's
own optimizer, loaded through the PUBLIC `newLibraryWithData:` path, treats the store as dead code
on a declared-read-only buffer and drops it -- something MAX's OWN internal loading/dispatch path
evidently avoids or corrects, since the exact same compiler's output runs correctly (numerically
verified in earlier phases) through `DeviceContext.enqueue_function`. Extraction (background step
2) is real; independent EXECUTION of the extracted bytes outside MAX's runtime is not currently
correct. See the investigation write-up for the full reasoning chain and the go/no-go call this
feeds into.
"""
from std.builtin.type_aliases import MutAnyOrigin
from std.ffi import external_call
from std.gpu import block_dim, block_idx, thread_idx
from std.gpu.host import DeviceContext
from std.memory import alloc
from std.sys import has_accelerator
from std.time import perf_counter_ns

comptime K: Int = 1024
comptime N: Int = 3072
comptime REPS: Int = 30
comptime BATCH: Int = 20  # dispatches batched into ONE command buffer, ONE wait


@fieldwise_init
struct MTLSize(Copyable, Movable):
    var width: UInt64
    var height: UInt64
    var depth: UInt64


fn _gemv_kernel(
    y_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    x_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    w_ptr: UnsafePointer[Float32, origin=MutAnyOrigin],
    k: Int,
    n: Int,
):
    """Decode-shaped, bandwidth-bound GEMV: y[j] = sum_i x[i] * w[i*n + j]. Same shape as
    `decode_metal_probe.mojo` / the raw-Metal controls (`metal_floor.m`, `metal_bw.m`) this probe's
    numbers are meant to sit next to."""
    var j = Int(block_idx.x * block_dim.x + thread_idx.x)
    if j >= n:
        return
    var acc = Float32(0.0)
    for i in range(k):
        acc += x_ptr[i] * w_ptr[i * n + j]
    y_ptr[j] = acc


fn _cstr(s: StaticString) -> UnsafePointer[UInt8, origin=StaticConstantOrigin]:
    return s.unsafe_ptr()


# ── thin, uniquely-named C shim (objc_shim.c, linked in via -Xlinker) ──────────────────────────
# Mojo's own `external_call["objc_msgSend", ...]` registers ONE global extern declaration per
# NAME the first time it is lowered; a second callsite with a DIFFERENT signature under that same
# name fails to compile ("existing function with conflicting signature"). The alternative --
# `dlsym` + an indirect call through a Mojo function-pointer value -- compiles but crashes inside
# `libKGENCompilerRTShared.dylib` at the point of the indirect call on this toolchain (reproduced,
# see write-up). A one-signature-per-C-symbol-name shim sidesteps both; every wrapper in
# objc_shim.c is a one-line, argument-preserving forward to the real `objc_msgSend` / Metal /
# libdispatch C functions -- no kernel logic, no Metal argument-layout knowledge lives there.
fn sel(name: StaticString) -> OpaquePointer[MutAnyOrigin]:
    return external_call["algenta_sel", OpaquePointer[MutAnyOrigin], UnsafePointer[UInt8, origin=StaticConstantOrigin]](_cstr(name))


fn msg0(recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin]) -> OpaquePointer[MutAnyOrigin]:
    return external_call[
        "algenta_msg0", OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin]
    ](recv, s)


fn msg0_void(recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin]):
    external_call[
        "algenta_msg0_void", NoneType, OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin]
    ](recv, s)


fn msg1p(
    recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin], a0: OpaquePointer[MutAnyOrigin]
) -> OpaquePointer[MutAnyOrigin]:
    return external_call[
        "algenta_msg1p",
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
    ](recv, s, a0)


fn msg1p_void(recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin], a0: OpaquePointer[MutAnyOrigin]):
    external_call[
        "algenta_msg1p_void",
        NoneType,
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
    ](recv, s, a0)


fn new_buffer(
    dev: OpaquePointer[MutAnyOrigin], sel_new_buf: OpaquePointer[MutAnyOrigin], length: UInt64
) -> OpaquePointer[MutAnyOrigin]:
    # newBufferWithLength:options: , options=0 == MTLResourceStorageModeShared
    return external_call[
        "algenta_msg_newbuffer",
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        UInt64,
        UInt64,
    ](dev, sel_new_buf, length, UInt64(0))


fn set_buffer(
    enc: OpaquePointer[MutAnyOrigin],
    s: OpaquePointer[MutAnyOrigin],
    buf: OpaquePointer[MutAnyOrigin],
    offset: UInt64,
    index: UInt64,
):
    external_call[
        "algenta_msg_setbuffer",
        NoneType,
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        UInt64,
        UInt64,
    ](enc, s, buf, offset, index)


fn set_bytes(
    enc: OpaquePointer[MutAnyOrigin],
    s: OpaquePointer[MutAnyOrigin],
    data: UnsafePointer[UInt8, origin=MutAnyOrigin],
    length: UInt64,
    index: UInt64,
):
    external_call[
        "algenta_msg_setbytes",
        NoneType,
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        UnsafePointer[UInt8, origin=MutAnyOrigin],
        UInt64,
        UInt64,
    ](enc, s, data, length, index)


fn dispatch_threadgroups(
    enc: OpaquePointer[MutAnyOrigin],
    s: OpaquePointer[MutAnyOrigin],
    groups: MTLSize,
    threads: MTLSize,
):
    # MTLSize (3x uint64 = 24 bytes) by value, TWICE -- handled on the C side of the shim (clang's
    # native AAPCS64 aggregate-by-value lowering), not by asking Mojo's own struct-by-value ABI
    # lowering to match it independently.
    external_call[
        "algenta_msg_dispatch",
        NoneType,
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        UInt64, UInt64, UInt64,
        UInt64, UInt64, UInt64,
    ](enc, s, groups.width, groups.height, groups.depth, threads.width, threads.height, threads.depth)


fn msg2p_err(
    recv: OpaquePointer[MutAnyOrigin],
    s: OpaquePointer[MutAnyOrigin],
    a0: OpaquePointer[MutAnyOrigin],
    err_out: UnsafePointer[OpaquePointer[MutAnyOrigin], origin=MutAnyOrigin],
) -> OpaquePointer[MutAnyOrigin]:
    return external_call[
        "algenta_msg_2p_err",
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        UnsafePointer[OpaquePointer[MutAnyOrigin], origin=MutAnyOrigin],
    ](recv, s, a0, err_out)


fn msg1u_ret(
    recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin], a0: UInt64
) -> OpaquePointer[MutAnyOrigin]:
    return external_call[
        "algenta_msg1u_ret",
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        UInt64,
    ](recv, s, a0)


fn msg0_u64(recv: OpaquePointer[MutAnyOrigin], s: OpaquePointer[MutAnyOrigin]) -> UInt64:
    return external_call[
        "algenta_msg0_u64", UInt64, OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin]
    ](recv, s)


fn dispatch_data_from(ptr: UnsafePointer[UInt8, origin=MutAnyOrigin], length: UInt64) -> OpaquePointer[MutAnyOrigin]:
    return external_call[
        "algenta_dispatch_data_create",
        OpaquePointer[MutAnyOrigin],
        UnsafePointer[UInt8, origin=MutAnyOrigin],
        UInt64,
    ](ptr, length)


struct MetallibBlob(Copyable, Movable):
    var ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var length: Int

    fn __init__(out self, ptr: UnsafePointer[UInt8, origin=MutAnyOrigin], length: Int):
        self.ptr = ptr
        self.length = length


fn find_embedded_metallib() raises -> MetallibBlob:
    """Locates THIS process's own embedded Mojo-compiled metallib blob: `__TEXT,__const`, scanned
    for the `MTLB` magic, sized by the container's own self-declared length at byte offset +16
    (verified against Metal's real loader in the recon that grew this file -- see module doc)."""
    var mh = external_call["_dyld_get_image_header", OpaquePointer[MutAnyOrigin], UInt32](UInt32(0))
    var size_out = UInt64(0)
    var sect = external_call[
        "getsectiondata",
        UnsafePointer[UInt8, origin=MutAnyOrigin],
        OpaquePointer[MutAnyOrigin],
        UnsafePointer[UInt8, origin=StaticConstantOrigin],
        UnsafePointer[UInt8, origin=StaticConstantOrigin],
        UnsafePointer[UInt64, origin=MutAnyOrigin],
    ](mh, _cstr("__TEXT"), _cstr("__const"), UnsafePointer(to=size_out))
    if not sect:
        raise Error("getsectiondata returned null for __TEXT,__const")
    var sect_size = Int(size_out)
    print("  __TEXT,__const: addr present, size =", sect_size, "bytes")

    # A bare 4-byte magic scan can hit an unrelated coincidental match (e.g. other constant data
    # in the same section). Validate each candidate by its OWN self-declared length actually
    # fitting inside the section before accepting it; keep scanning past false positives.
    var magic_off = -1
    var declared_len = 0
    var i = 0
    while i < sect_size - 20:
        if (
            sect[i] == 0x4D and sect[i + 1] == 0x54 and sect[i + 2] == 0x4C and sect[i + 3] == 0x42
        ):  # "MTLB"
            var len_ptr = (sect + i + 16).bitcast[UInt64]()
            var candidate_len = Int(len_ptr[0])
            if candidate_len > 20 and i + candidate_len <= sect_size:
                magic_off = i
                declared_len = candidate_len
                break
        i += 1
    if magic_off < 0:
        raise Error("no MTLB magic with a self-consistent length found in __TEXT,__const")

    print("  MTLB found at __const+", magic_off, " declared container length =", declared_len, "bytes")
    return MetallibBlob(sect + magic_off, declared_len)


fn _median(mut s: List[Float64]) -> Float64:
    for i in range(1, len(s)):
        var key = s[i]
        var j = i - 1
        while j >= 0 and s[j] > key:
            s[j + 1] = s[j]
            j -= 1
        s[j + 1] = key
    return s[len(s) // 2]


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return

    print("=== compile the Mojo kernel (forces the metallib to be embedded) ===")
    var ctx = DeviceContext()
    print("device:", ctx.name())
    var mojo_fn = ctx.compile_function[_gemv_kernel, _gemv_kernel]()
    print("compiled ok")

    print("")
    print("=== extract the embedded metallib from THIS process's own image ===")
    var blob = find_embedded_metallib()
    var blob_ptr = blob.ptr
    var blob_len = blob.length

    print("")
    print("=== load it as an INDEPENDENT MTLLibrary via dispatch_data_t + newLibraryWithData: ===")
    var dev = external_call["MTLCreateSystemDefaultDevice", OpaquePointer[MutAnyOrigin]]()
    var ddata = dispatch_data_from(blob_ptr, UInt64(blob_len))

    var sel_newlib = sel("newLibraryWithData:error:")
    var errptr = alloc[OpaquePointer[MutAnyOrigin]](1)
    errptr[0] = OpaquePointer[MutAnyOrigin]()
    var lib = msg2p_err(dev, sel_newlib, ddata, errptr)
    if not lib:
        raise Error("newLibraryWithData: failed -- see module doc for the dispatch_data_t gotcha")
    print("  MTLLibrary loaded from the extracted blob: OK")

    var names = msg0(lib, sel("functionNames"))
    var count = msg0_u64(names, sel("count"))
    print("  functionNames count:", count, "(expect 1 -- this probe compiles exactly one kernel)")
    var fname = msg1u_ret(names, sel("objectAtIndex:"), UInt64(0))

    var raw_fn = msg1p(lib, sel("newFunctionWithName:"), fname)
    if not raw_fn:
        raise Error("newFunctionWithName: returned nil")
    print("  newFunctionWithName: OK")

    errptr[0] = OpaquePointer[MutAnyOrigin]()
    var pso = msg2p_err(dev, sel("newComputePipelineStateWithFunction:error:"), raw_fn, errptr)
    if not pso:
        raise Error("newComputePipelineStateWithFunction:error: failed")
    print("  MTLComputePipelineState built from Mojo's OWN compiled bytes: OK")

    print("")
    print("=== build inputs, run BOTH paths on IDENTICAL data ===")
    var x_bytes = UInt64(K * 4)
    var w_bytes = UInt64(K * N * 4)
    var y_bytes = UInt64(N * 4)
    var buf_x = new_buffer(dev, sel("newBufferWithLength:options:"), x_bytes)
    var buf_w = new_buffer(dev, sel("newBufferWithLength:options:"), w_bytes)
    var buf_y = new_buffer(dev, sel("newBufferWithLength:options:"), y_bytes)

    var x_contents = msg0(buf_x, sel("contents")).bitcast[Float32]()
    var w_contents = msg0(buf_w, sel("contents")).bitcast[Float32]()
    var y_contents = msg0(buf_y, sel("contents")).bitcast[Float32]()
    for i in range(K):
        x_contents[i] = Float32((i * 61 + 17) % 23) / 11.0 - 1.0
    for i in range(K * N):
        w_contents[i] = Float32((i * 61 + 85) % 23) / 11.0 - 1.0
    for i in range(N):
        y_contents[i] = Float32(-999.0)

    var queue = msg0(dev, sel("newCommandQueue"))
    var sel_cb = sel("commandBuffer")
    var sel_enc = sel("computeCommandEncoder")
    var sel_setpso = sel("setComputePipelineState:")
    var sel_setbuf = sel("setBuffer:offset:atIndex:")
    var sel_setbytes = sel("setBytes:length:atIndex:")
    var sel_dispatch = sel("dispatchThreadgroups:threadsPerThreadgroup:")
    var sel_end = sel("endEncoding")
    var sel_commit = sel("commit")
    var sel_wait = sel("waitUntilCompleted")

    var k_val = Int64(K)
    var n_val = Int64(N)
    var k_ptr = UnsafePointer(to=k_val).bitcast[UInt8]()
    var n_ptr = UnsafePointer(to=n_val).bitcast[UInt8]()
    var groups = MTLSize(UInt64((N + 255) // 256), 1, 1)
    var threads = MTLSize(256, 1, 1)

    var cb = msg0(queue, sel_cb)
    var enc = msg0(cb, sel_enc)
    msg1p_void(enc, sel_setpso, pso)
    set_buffer(enc, sel_setbuf, buf_y, 0, 0)
    set_buffer(enc, sel_setbuf, buf_x, 0, 1)
    set_buffer(enc, sel_setbuf, buf_w, 0, 2)
    set_bytes(enc, sel_setbytes, k_ptr, 8, 3)
    set_bytes(enc, sel_setbytes, n_ptr, 8, 4)
    dispatch_threadgroups(enc, sel_dispatch, groups, threads)
    msg0_void(enc, sel_end)
    msg0_void(cb, sel_commit)
    msg0_void(cb, sel_wait)
    print("  hand-rolled MTLCommandBuffer dispatch of Mojo's OWN kernel bytes: ran without crashing")

    # ---- the SAME computation via MAX's DeviceContext, on IDENTICAL inputs ----
    var mx = ctx.enqueue_create_buffer[DType.float32](K)
    var mw = ctx.enqueue_create_buffer[DType.float32](K * N)
    var my = ctx.enqueue_create_buffer[DType.float32](N)
    with mx.map_to_host() as h:
        for i in range(K):
            h[i] = Float32((i * 61 + 17) % 23) / 11.0 - 1.0
    with mw.map_to_host() as h:
        for i in range(K * N):
            h[i] = Float32((i * 61 + 85) % 23) / 11.0 - 1.0
    ctx.enqueue_function(
        mojo_fn, my.unsafe_ptr(), mx.unsafe_ptr(), mw.unsafe_ptr(), K, N,
        grid_dim=(N + 255) // 256, block_dim=256,
    )
    ctx.synchronize()

    print("")
    print("=== correctness: hand-rolled dispatch vs MAX's own enqueue_function, same kernel bytes ===")
    var max_diff = Float32(0.0)
    var first_mismatch = -1
    with my.map_to_host() as h:
        for i in range(N):
            var d = y_contents[i] - h[i]
            if d < 0:
                d = -d
            if d > max_diff:
                max_diff = d
            if d != Float32(0.0) and first_mismatch < 0:
                first_mismatch = i
    print("  max |hand_rolled[i] - max_enqueued[i]| over", N, "outputs:", max_diff)
    print("  y[0] hand-rolled:", y_contents[0])
    if first_mismatch >= 0:
        print("  first differing index:", first_mismatch)
    else:
        print("  BIT-IDENTICAL across all", N, "outputs.")

    print("")
    print("=== dispatch overhead: hand-rolled (1-per-commit) vs MAX enqueue_function ===")
    var hand_samples = List[Float64]()
    for _ in range(REPS):
        var t0 = perf_counter_ns()
        var cb2 = msg0(queue, sel_cb)
        var enc2 = msg0(cb2, sel_enc)
        msg1p_void(enc2, sel_setpso, pso)
        set_buffer(enc2, sel_setbuf, buf_y, 0, 0)
        set_buffer(enc2, sel_setbuf, buf_x, 0, 1)
        set_buffer(enc2, sel_setbuf, buf_w, 0, 2)
        set_bytes(enc2, sel_setbytes, k_ptr, 8, 3)
        set_bytes(enc2, sel_setbytes, n_ptr, 8, 4)
        dispatch_threadgroups(enc2, sel_dispatch, groups, threads)
        msg0_void(enc2, sel_end)
        msg0_void(cb2, sel_commit)
        msg0_void(cb2, sel_wait)
        hand_samples.append(Float64(Int(perf_counter_ns() - t0)) / 1e3)
    print("  hand-rolled, 1 dispatch/commit+wait, median of", REPS, ":", _median(hand_samples), "us")

    var max_samples = List[Float64]()
    for _ in range(REPS):
        var t0 = perf_counter_ns()
        ctx.enqueue_function(
            mojo_fn, my.unsafe_ptr(), mx.unsafe_ptr(), mw.unsafe_ptr(), K, N,
            grid_dim=(N + 255) // 256, block_dim=256,
        )
        ctx.synchronize()
        max_samples.append(Float64(Int(perf_counter_ns() - t0)) / 1e3)
    print("  MAX enqueue_function + synchronize, median of", REPS, ":", _median(max_samples), "us")

    print("")
    print("=== the actual point: BATCH", BATCH, "dispatches into ONE command buffer, ONE wait ===")
    print("    (MAX's enqueue_function cannot do this -- it blocks synchronously per call, per")
    print("    residentk/kernels.mojo's own measurement note. This is the mechanism this whole")
    print("    investigation was about: does batching survive going through Mojo's own FFI.)")
    var batch_samples = List[Float64]()
    for _ in range(10):
        var t0 = perf_counter_ns()
        var cb3 = msg0(queue, sel_cb)
        var enc3 = msg0(cb3, sel_enc)
        msg1p_void(enc3, sel_setpso, pso)
        for _ in range(BATCH):
            set_buffer(enc3, sel_setbuf, buf_y, 0, 0)
            set_buffer(enc3, sel_setbuf, buf_x, 0, 1)
            set_buffer(enc3, sel_setbuf, buf_w, 0, 2)
            set_bytes(enc3, sel_setbytes, k_ptr, 8, 3)
            set_bytes(enc3, sel_setbytes, n_ptr, 8, 4)
            dispatch_threadgroups(enc3, sel_dispatch, groups, threads)
        msg0_void(enc3, sel_end)
        msg0_void(cb3, sel_commit)
        msg0_void(cb3, sel_wait)
        batch_samples.append(Float64(Int(perf_counter_ns() - t0)) / 1e3)
    var batch_med = _median(batch_samples)
    print("  ", BATCH, "dispatches / ONE command buffer, median of 10:", batch_med, "us  ==",
          batch_med / Float64(BATCH), "us/dispatch")
