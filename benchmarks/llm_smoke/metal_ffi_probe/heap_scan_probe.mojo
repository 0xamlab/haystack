"""heap_scan_probe.mojo — background step (1), the real attempt: DeviceFunction._handle and
DeviceContext._handle are directly readable (handle_int_probe.mojo proved that: Mojo does not
enforce field privacy), but they point at an OPAQUE C++ object (`_DeviceFunctionCpp` /
`_DeviceContextCpp` are zero-field placeholder structs in Mojo's own model -- Mojo does not know
the C++ layout at all). This probe asks: does that C++ object's OWN memory, scanned byte-for-byte,
contain an embedded Objective-C object pointer (an `id<MTLFunction>`, `id<MTLLibrary>`,
`id<MTLComputePipelineState>`, `id<MTLDevice>`, `id<MTLCommandQueue>`, ...) reachable without
knowing the C++ layout ahead of time?

Method (safe against crashing on garbage addresses):
  1. Enumerate every currently-loaded Objective-C class via `objc_getClassList` into a lookup set
     of Class pointers -- the `isa` value every live ObjC object has at its OWN address + 0.
  2. Read raw bytes at a candidate address via `mach_vm_read_overwrite` -- a Mach trap that
     validates the target page and returns an error code on failure, rather than delivering
     SIGSEGV to this process. This is what makes pointer-chasing survivable even on garbage.
  3. For every 8-byte-aligned word in the read-back bytes, check for EXACT equality against a
     known-loaded Class pointer (a pure integer compare -- no dereference of the candidate value
     itself, so no crash risk even if the word is garbage).
  4. Any word that looks like a plausible heap pointer (nonzero, in a sane process address range)
     but is not itself a class match is a candidate for one more level of the same read+scan --
     bounded depth, bounded fan-out -- to catch ONE hop of C++ indirection (DeviceFunction -> some
     cache/record -> the actual Metal object) without an unbounded chase.

Throwaway recon probe, new namespace, touches nothing frozen.
"""
from std.builtin.type_aliases import MutAnyOrigin
from std.memory import alloc
from std.ffi import external_call
from std.gpu.host import DeviceContext
from std.sys import has_accelerator

comptime WORDS_PER_SCAN = 512  # 4096 bytes per read
comptime MAX_FOLLOW = 24
comptime FOLLOW_DEPTH = 2


def _k(o: UnsafePointer[Float32, origin=MutAnyOrigin]):
    if o[0] == Float32(999999.0):
        o[0] = Float32(1.0)


def _cptr_to_string(p: OpaquePointer[MutAnyOrigin], max_len: Int = 200) -> String:
    if not p:
        return String("<null>")
    var cp = p.bitcast[UInt8]()
    var s = String()
    var i = 0
    while i < max_len and cp[i] != 0:
        s += chr(Int(cp[i]))
        i += 1
    return s


def task_self() -> UInt32:
    return external_call["task_self_trap", UInt32]()


def safe_read(task: UInt32, addr: UInt64, size: UInt64, dst: UnsafePointer[UInt64, origin=MutAnyOrigin]) -> Bool:
    """mach_vm_read_overwrite: True + dst filled on success, False on any failure (including the
    address being unmapped) -- never a SIGSEGV to this process, unlike a bare dereference."""
    var outsize = UInt64(0)
    var dst_addr = UInt64(Int(dst))
    var kr = external_call[
        "mach_vm_read_overwrite",
        Int32,
        UInt32,
        UInt64,
        UInt64,
        UInt64,
        UnsafePointer[UInt64, origin=MutAnyOrigin],
    ](task, addr, size, dst_addr, UnsafePointer(to=outsize))
    return kr == 0


def class_name(cls_ptr: OpaquePointer[MutAnyOrigin]) -> String:
    var namep = external_call[
        "class_getName", OpaquePointer[MutAnyOrigin], OpaquePointer[MutAnyOrigin]
    ](cls_ptr)
    return _cptr_to_string(namep)


def load_class_table(mut addrs: List[Int], mut names: List[String]) raises:
    var null_buf = UnsafePointer[UInt64, origin=MutAnyOrigin]()
    var count = external_call[
        "objc_getClassList",
        Int32,
        UnsafePointer[UInt64, origin=MutAnyOrigin],
        Int32,
    ](null_buf, Int32(0))
    var cap = Int(count) + 64
    var buf = alloc[UInt64](cap)
    var got = external_call[
        "objc_getClassList",
        Int32,
        UnsafePointer[UInt64, origin=MutAnyOrigin],
        Int32,
    ](buf, Int32(cap))
    print("objc_getClassList: reported", count, "classes, wrote", got)
    for i in range(Int(got)):
        var p_int = Int(buf[i])
        addrs.append(p_int)
        var p_opaque = UnsafePointer[UInt64, origin=MutAnyOrigin](unsafe_from_address=p_int).bitcast[NoneType]()
        names.append(class_name(p_opaque))
    buf.free()


def looks_like_heap_pointer(w: UInt64) -> Bool:
    # macOS ARM64 user-space heap/library addresses observed in practice: nonzero, below the
    # kernel half, above a trivial small-integer range (rules out counters/lengths like the
    # `1024` seen at word[1] in handle_int_probe.mojo's dump).
    if w == 0:
        return False
    if w < 0x0001_0000_0000:
        return False
    if w > 0x0000_7FFF_FFFF_FFFF:
        return False
    return (w & 0x7) == 0  # 8-byte aligned, as any real object pointer must be


def scan_and_report(
    task: UInt32,
    label: String,
    addr: UInt64,
    class_addrs: List[Int],
    class_names: List[String],
    mut follow_queue: List[UInt64],
    mut follow_labels: List[String],
) raises -> Int:
    """Reads WORDS_PER_SCAN words at `addr`, reports any exact class-pointer match, and queues
    any pointer-shaped-but-unmatched word for one more level of follow. Returns match count."""
    var words = alloc[UInt64](WORDS_PER_SCAN)
    var ok = safe_read(task, addr, UInt64(WORDS_PER_SCAN * 8), words)
    if not ok:
        print("  [", label, "] mach_vm_read_overwrite FAILED at", addr, "-- unmapped/unreadable")
        words.free()
        return 0

    var matches = 0
    var queued = 0
    for i in range(WORDS_PER_SCAN):
        var w = words[i]
        var wi = Int(w)
        var matched = False
        for c in range(len(class_addrs)):
            if class_addrs[c] == wi and wi != 0:
                print(
                    "  [", label, "] offset +", i * 8, ": word =", w,
                    " EXACT MATCH to loaded Objective-C class:", class_names[c],
                )
                matches += 1
                matched = True
        if not matched and looks_like_heap_pointer(w) and queued < MAX_FOLLOW:
            follow_queue.append(w)
            follow_labels.append(String(label) + "+" + String(i * 8))
            queued += 1
    words.free()
    print("  [", label, "] scanned", WORDS_PER_SCAN * 8, "bytes:", matches,
          "class-isa matches,", queued, "pointer-shaped words queued to follow")
    return matches


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return
    var ctx = DeviceContext()
    print("device:", ctx.name())
    var fn_obj = ctx.compile_function[_k, _k]()
    print("compiled ok")

    var task = task_self()
    print("task_self() =", task)

    var class_addrs = List[Int]()
    var class_names = List[String]()
    load_class_table(class_addrs, class_names)

    # A short allowlist of names worth flagging explicitly if seen among matches (informational
    # only -- the match/no-match result above is what actually answers the question).
    print("")
    print("Sample of loaded classes with Metal/AGX-shaped names (context, not the answer itself):")
    var shown = 0
    for i in range(len(class_names)):
        var n = class_names[i]
        if ("MTL" in n or "AGX" in n or "Metal" in n) and shown < 15:
            print("   ", n)
            shown += 1
    print("   (", shown, "shown of", len(class_names), "total loaded classes)")

    var fn_handle_int = Int(fn_obj._handle.value())
    var ctx_handle_int = Int(ctx._handle.value())
    print("")
    print("fn_obj._handle  =", fn_handle_int)
    print("ctx._handle     =", ctx_handle_int)

    var follow_queue = List[UInt64]()
    var follow_labels = List[String]()

    print("")
    print("=== depth 0: DeviceFunction's own C++ object memory ===")
    var total_matches = scan_and_report(
        task, String("fn_obj._handle"), UInt64(fn_handle_int),
        class_addrs, class_names, follow_queue, follow_labels,
    )

    print("")
    print("=== depth 0: DeviceContext's own C++ object memory ===")
    total_matches += scan_and_report(
        task, String("ctx._handle"), UInt64(ctx_handle_int),
        class_addrs, class_names, follow_queue, follow_labels,
    )

    for depth in range(1, FOLLOW_DEPTH + 1):
        print("")
        print("=== depth", depth, ":", len(follow_queue), "pointer-shaped candidates queued ===")
        var next_queue = List[UInt64]()
        var next_labels = List[String]()
        var n_to_try = len(follow_queue)
        for i in range(n_to_try):
            total_matches += scan_and_report(
                task, follow_labels[i], follow_queue[i],
                class_addrs, class_names, next_queue, next_labels,
            )
        follow_queue = next_queue^
        follow_labels = next_labels^

    print("")
    print("TOTAL class-isa matches found across all depths:", total_matches)
    if total_matches == 0:
        print("RESULT: no embedded Objective-C object was found reachable from DeviceFunction or")
        print("DeviceContext's own C++ memory within the scanned range/depth. Consistent with the")
        print("AsyncRT C++ object being a thin opaque handle into a closed-source runtime that")
        print("does not store Metal objects as direct/near members of the handle Mojo can see.")
