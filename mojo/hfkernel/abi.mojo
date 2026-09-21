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


@export
def algenta_runtime_execute(handle_addr: Int, req_addr: Int) abi("C") -> Int:
    _ensure_cpu_device()  # ABI 4.9: the calling thread may not be the one that ran init
    return _to_cstr_address(_execute(handle_addr, req_addr))  # ABI 1.3 / 4.1


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
