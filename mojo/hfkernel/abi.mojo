"""Algenta in-process C ABI (v1) for Hugging Face kernel packages.

Additive module: lives outside mojo/engine/ so the runtime inventory never scans it, and is
staged next to a FILTERED runtime_library_dispatch_generated.mojo at build time (the same sibling
resolution the shard builder relies on). Contract: docs/hf-kernels/ABI.md (clause numbers below).

Pointer spelling: C pointers cross the boundary as integer addresses (`Int`, pointer-sized on every
supported target, passed in the same register class as a pointer), because Mojo 1.0 pointers are
non-nullable by design and the engine's own FFI models nullable C pointers the same way
(`unsafe_from_address`, 600+ uses). The C prototypes in ABI.md are unchanged.
"""

from std.ffi import external_call
from std.memory import UnsafePointer, alloc
from std.origin import MutUntrackedOrigin
from json.parser import json_get_string
from hf_abi_guard_generated import check_count_relations, is_function_excluded
from hf_abi_router_generated import RouterState, route

comptime ABI_VERSION: Int32 = 1
comptime BytePtr = UnsafePointer[UInt8, origin=MutUntrackedOrigin]
comptime HandlePtr = UnsafePointer[AlgentaHandle, origin=MutUntrackedOrigin]
comptime MAX_REQUEST_BYTES: Int = 64 * 1024 * 1024  # ABI 2.2: the worker's frame cap
comptime MAX_RESPONSE_BYTES: Int = 64 * 1024 * 1024  # ABI 3.3 response_too_large
comptime MAX_JSON_DEPTH: Int = 64  # ABI 3.3 request_nesting_exceeded


struct AlgentaHandle(Movable):
    """Per-init state (ABI 4.5). No module-level mutable state anywhere in this file."""

    var config_json: String
    var router: RouterState

    def __init__(out self, config_json: String):
        self.config_json = config_json
        # ABI 3.5: the family's declared request types (and only their state) live in the
        # generated router; requests outside them are refused before any dispatch.
        self.router = RouterState()


def _bytes_to_string(bytes: List[UInt8]) -> String:
    var out = String()
    out += StringSlice(unsafe_from_utf8=Span(bytes))
    return out


def _json_escape(s: String) -> String:
    """Byte-level JSON string escaping; drops other control bytes."""
    var src = s.unsafe_ptr()
    var n = s.byte_length()
    var bytes = List[UInt8](capacity=n + 8)
    for i in range(n):
        var b = src[i]
        if b == 34:  # "
            bytes.append(92)
            bytes.append(34)
        elif b == 92:  # backslash
            bytes.append(92)
            bytes.append(92)
        elif b == 10:
            bytes.append(92)
            bytes.append(110)
        elif b == 13:
            bytes.append(92)
            bytes.append(114)
        elif b == 9:
            bytes.append(92)
            bytes.append(116)
        elif b < 32:
            pass
        else:
            bytes.append(b)
    return _bytes_to_string(bytes)


def _error(code: String, message: String) -> String:
    """ABI 3.2/3.3: the worker-shaped error envelope."""
    var msg = _json_escape(message)
    return (
        '{"error":"' + code + ': ' + msg + '","error_code":"' + code
        + '","error_message":"' + msg + '"}'
    )


def _bounded_cstr_len(p: BytePtr, bound: Int) -> Int:
    """ABI 2.2: scan for NUL within `bound` bytes BEFORE any copy. -1 if none found."""
    var i = 0
    while i < bound:
        if p[i] == 0:
            return i
        i += 1
    return -1


def _string_from_cstr(p: BytePtr, n: Int) -> String:
    var bytes = List[UInt8](capacity=n)
    for i in range(n):
        bytes.append(p[i])
    return _bytes_to_string(bytes)


def _to_cstr_address(s: String) -> Int:
    """ABI 4.1: fresh heap block, NUL-terminated, owned by the caller; returned as an address."""
    var n = s.byte_length()
    var out = alloc[UInt8](n + 1)
    var src = s.unsafe_ptr()
    for i in range(n):
        out[i] = src[i]
    out[n] = 0
    return Int(out)


def _max_depth(raw: String) -> Int:
    """Linear scan of bracket nesting, string-aware. Cheap pre-parse bound (ABI 3.3)."""
    var depth = 0
    var max_depth = 0
    var in_str = False
    var esc = False
    var ptr = raw.unsafe_ptr()
    var n = raw.byte_length()
    for i in range(n):
        var b = ptr[i]
        if in_str:
            if esc:
                esc = False
            elif b == 92:
                esc = True
            elif b == 34:
                in_str = False
        else:
            if b == 34:
                in_str = True
            elif b == 123 or b == 91:  # { [
                depth += 1
                if depth > max_depth:
                    max_depth = depth
            elif b == 125 or b == 93:  # } ]
                depth -= 1
    return max_depth


def _execute(handle_addr: Int, req_addr: Int) -> String:
    if handle_addr == 0:
        return _error("handle_invalid", "NULL handle")  # ABI 4.6
    if req_addr == 0:
        return _error("request_not_json", "NULL request")
    var handle = HandlePtr(unsafe_from_address=handle_addr)
    var req = BytePtr(unsafe_from_address=req_addr)
    var n = _bounded_cstr_len(req, MAX_REQUEST_BYTES)
    if n < 0:
        return _error("request_too_large", "no NUL within MAX_REQUEST_BYTES")  # ABI 2.2
    var raw = _string_from_cstr(req, n)
    if _max_depth(raw) > MAX_JSON_DEPTH:
        return _error("request_nesting_exceeded", "JSON nesting deeper than MAX_JSON_DEPTH")
    var msg_type = json_get_string(raw, "type")
    if msg_type.byte_length() == 0:
        return _error("request_not_json", 'missing or unreadable "type"')
    if not handle[].router.is_declared(msg_type):
        return _error("request_type_unsupported", "route not declared by this family: " + msg_type)  # ABI 3.5
    if msg_type == "library_execute":
        var module = json_get_string(raw, "module")
        var function = json_get_string(raw, "function")
        # RQ-G: Python-interop-backed functions crash in-process; refused, never dispatched.
        if is_function_excluded(module, function):
            return _error(
                "function_unsupported_in_process",
                module + "." + function + " needs the host Python bridge and is not available in the in-process kernel; use the algenta runtime worker for it",
            )
        # ABI 3.3: count relations enforced at the native boundary, before the frozen dispatch.
        var refusal = check_count_relations(module, function, raw)
        if refusal.byte_length() > 0:
            return refusal
    var response: String
    try:
        response = route(msg_type, raw, handle[].router)
    except e:
        response = _error("runtime_execution_failed", String(e))  # ABI 3.3
    if response.byte_length() > MAX_RESPONSE_BYTES:
        return _error("response_too_large", "response exceeds MAX_RESPONSE_BYTES")
    return response


@export
def algenta_runtime_version() abi("C") -> Int32:
    return ABI_VERSION  # ABI 1.1



def _ensure_cpu_device():
    """ABI 4.9 — mirror the Mojo `main` prologue (`std.builtin._startup._ensure_runtime_init`).

    A shared library never runs that prologue, so the process-wide AsyncRT CPU device that
    `parallelize` schedules onto would not exist and the first parallel kernel would dereference
    NULL inside the runtime (`KGEN_CompilerRT_AsyncRT_ParallelismLevel`). Get-or-create it; the
    reference is held for the process lifetime and never released, because same-toolchain families
    share one runtime image in the host process. Cheap when the calling thread already sees it."""
    var current = external_call["KGEN_CompilerRT_AsyncRT_GetCurrentCPUDevice", Int]()
    if current != 0:
        return
    _ = external_call["KGEN_CompilerRT_AsyncRT_GetOrCreateCPUDevice", Int]()

@export
def algenta_runtime_init(cfg_addr: Int) abi("C") -> Int:
    _ensure_cpu_device()  # ABI 4.9
    var config = String("{}")
    if cfg_addr != 0:
        var cfg = BytePtr(unsafe_from_address=cfg_addr)
        var n = _bounded_cstr_len(cfg, MAX_REQUEST_BYTES)
        if n < 0:
            return 0  # ABI 1.2: NULL on failure
        config = _string_from_cstr(cfg, n)
    var h = alloc[AlgentaHandle](1)
    h.init_pointee_move(AlgentaHandle(config))
    return Int(h)


# ── ABI 9: Community worker cap — enforced HERE, in the compiled library ──────────────────────────
# At most ONE native execution is in flight per device, machine-wide, across every process, thread,
# family and loaded revision. This is the Community licence's `concurrent_worker_limit = 1`
# (apps/runtime/license.py) made technical for a distribution with no device login: the same
# posture as the licensed engine's local broker, but it can never be dark, never be configured and
# never be edited out of Python. Nothing in the environment, the init config or the request turns it
# off — the only way around it is patching this binary, which the ACL prohibits.
#
# Primitive: BSD flock(LOCK_EX) on /dev/null. The anchor is POSIX-guaranteed to exist, root-owned,
# world-openable read-only and undeletable by any user, so there is no lock FILE to delete-and-
# recreate for a second worker. flock is released by the kernel when the holder dies (or when the
# descriptor closes), so a crashed caller can never wedge the device. LOCK_EX without LOCK_NB
# blocks: a second caller queues, gets exactly one worker's throughput, and its result stays
# correct. Fail-closed: if the slot cannot be taken the call is REFUSED
# (community_worker_slot_unavailable) — never a free ride to parallelism.
#
# The descriptor comes from the stdlib's own `open()` (a FileHandle), NOT from an `external_call`
# of ours: libc `open` is variadic and the stdlib declares it with `num_fixed_args=2`; a second
# declaration of the same symbol with any other shape fails to lower ("existing function with
# conflicting signature") in every family that also links std/io/file — algenta-llm did. The only
# extern this block introduces is `flock`, which nothing else in the stdlib or the engine declares.
# `FileHandle._get_raw_fd()` is a private stdlib accessor: the toolchain is deliberately frozen at
# Mojo 1.0.0, and a toolchain bump re-checks this line (the §9 gate fails loudly if it breaks).
# Verified mutually exclusive across processes on macOS arm64 and Linux (ubuntu 22.04); the shipped
# gate is scripts/hf_kernels/community_cap_redteam.py (ABI 9.7). Flag values are identical on every
# supported target.
comptime _CAP_ANCHOR: StaticString = "/dev/null"
comptime _LOCK_EX: Int32 = 2
comptime _LOCK_UN: Int32 = 8


def _take_slot() raises -> FileHandle:
    """ABI 9.1: open the anchor and take the exclusive device slot. Raises, with the reason, if either
    step fails; on a failed flock the descriptor is closed before raising (no lock was ever held)."""
    var anchor = open(String(_CAP_ANCHOR), "r")
    if external_call["flock", Int32](Int32(anchor._get_raw_fd()), _LOCK_EX) != 0:
        try:
            anchor.close()
        except:
            pass
        raise Error("could not take the device worker slot")
    return anchor^


def _release_slot(mut anchor: FileHandle):
    """ABI 9.1: drop the lock and close the descriptor. Never raises — a close failure has nowhere to
    be reported and must never mask the response (closing also drops the lock; belt and braces)."""
    _ = external_call["flock", Int32](Int32(anchor._get_raw_fd()), _LOCK_UN)
    try:
        anchor.close()
    except:
        pass


def _execute_capped(handle_addr: Int, req_addr: Int) -> String:
    """ABI 9.1/9.4: take the device worker slot, run the request, release. Never raises.

    Two failure domains, deliberately kept apart so an error is never misattributed:
      * acquisition (anchor cannot be opened or locked) -> community_worker_slot_unavailable (9.4);
      * execution (anything `_execute` raises outside its own `route` guard, e.g. while decoding
        the request) -> runtime_execution_failed (3.3), exactly as an uncapped call would report it.
    The slot is released on EVERY path once taken, explicitly, before the response crosses the
    boundary — not left to the FileHandle destructor."""
    var anchor: FileHandle
    try:
        anchor = _take_slot()
    except e:
        return _error("community_worker_slot_unavailable", String(e))  # ABI 9.4 fail-closed
    var response: String
    try:
        response = _execute(handle_addr, req_addr)
    except e:
        response = _error("runtime_execution_failed", String(e))  # ABI 3.3 — never blamed on the slot
    _release_slot(anchor)  # ABI 9.1: released on every path, before the response crosses the boundary
    return response


@export
def algenta_runtime_execute(handle_addr: Int, req_addr: Int) abi("C") -> Int:
    _ensure_cpu_device()  # ABI 4.9: the calling thread may not be the one that ran init
    return _to_cstr_address(_execute_capped(handle_addr, req_addr))  # ABI 9.1 / 1.3 / 4.1


@export
def algenta_runtime_free(addr: Int) abi("C"):
    if addr != 0:  # ABI 4.3: free(NULL) is a no-op
        BytePtr(unsafe_from_address=addr).free()


@export
def algenta_runtime_shutdown(handle_addr: Int) abi("C"):
    if handle_addr != 0:  # ABI 4.5
        var h = HandlePtr(unsafe_from_address=handle_addr)
        h.destroy_pointee()
        h.free()
