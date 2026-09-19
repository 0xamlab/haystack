# ===----------------------------------------------------------------------=== #
# Algenta × Mojo quickstart
#
# Talks to the signed Algenta native runtime — the same artifact that
# `pip install algenta` resolves from the `algenta-runtime-native` wheel on
# PyPI — using nothing but the Mojo standard library and direct C FFI calls.
#
# What this demonstrates, end to end:
#   1. Resolving the runtime worker executable from the Python environment
#      that pixi installs the wheel into (override: $ALGENTA_RUNTIME_LIB).
#   2. Spawning the worker (`std.os.process.Process`) with the embedded-
#      interpreter environment it expects (PYTHONHOME / MOJO_PYTHON_LIBRARY).
#   3. Speaking the runtime's public wire protocol — JSON frames prefixed by
#      a 4-byte big-endian length over a Unix domain socket — via raw
#      `external_call` bindings to libc (socket / connect / poll / send /
#      recv). Mojo's stdlib has no socket module yet; the FFI layer below is
#      deliberately explicit so it reads as a reference binding.
#   4. A deterministic compute round-trip: the runtime evaluates the GELU
#      activation (one of its published library functions) and the result is
#      checked against the expected value.
#
# The demo exits 0 only if every step succeeds; any failure prints a
# diagnostic prefixed with `error:` and exits 1.
#
# Protocol reference (public, stable):
#   launch:    algenta-runtime-worker --server <unix-socket-path>
#   handshake: worker sends {"status": "ready", ...}   (fields are additive)
#   ping:      > {"type": "ping"}                      < {"status": "ok"}
#   execute:   > {"type": "library_execute", "module": "activations",
#                  "function": "gelu", "args": [1.0]}   < {"result": 0.8411…}
#   shutdown:  > {"type": "shutdown"}                  < {"status": "bye"}
# ===----------------------------------------------------------------------=== #

from std.collections import List, Span
from std.ffi import c_int, c_ssize_t, c_uint, external_call
from std.os import getenv, listdir, remove, setenv
from std.os.path import exists
from std.os.process import Process
from std.subprocess import run
from std.sys import CompilationTarget, exit
from std.time import sleep


# --- Protocol constants (mirrors the published wire format) ---------------- #

comptime AF_UNIX: c_int = 1
comptime SOCK_STREAM: c_int = 1
comptime POLLIN: Int32 = 0x1
comptime SIGPIPE: c_int = 13
comptime SIG_IGN: UInt = 1

# struct sockaddr_un: family (2 bytes) + sun_path. BSD/macOS prepends a
# sun_len byte and allows 104 path bytes; Linux allows 108.
comptime SUN_PATH_CAPACITY: Int = 104 if CompilationTarget.is_macos() else 108
comptime SOCKADDR_UN_SIZE: Int = 2 + SUN_PATH_CAPACITY

comptime MAX_FRAME_BYTES: Int = 64 * 1024 * 1024
comptime STARTUP_TIMEOUT_SECONDS: Float64 = 15.0
comptime IO_TIMEOUT_MS: c_int = 30_000

# The deterministic library call this demo makes: GELU(1.0), exact prefix.
comptime DEMO_MODULE = "activations"
comptime DEMO_FUNCTION = "gelu"
comptime DEMO_ARGS_JSON = "[1.0]"
comptime DEMO_RESULT_PREFIX = "0.841191"


# --- Minimal JSON field extraction ----------------------------------------- #
# The demo exchanges a fixed, tiny ASCII schema, so a full JSON parser would
# be dead weight. These helpers work on raw UTF-8 bytes: locate `"key"`,
# skip whitespace and the colon, then read the value. They tolerate arbitrary
# key order and whitespace.

comptime BYTE_QUOTE: Byte = 0x22  # "
comptime BYTE_COLON: Byte = 0x3A  # :
comptime BYTE_COMMA: Byte = 0x2C  # ,
comptime BYTE_CLOSE_OBJ: Byte = 0x7D  # }
comptime BYTE_CLOSE_ARR: Byte = 0x5D  # ]


def _is_gap_char(b: Byte) -> Bool:
    """Characters allowed between the closing quote of a key and its value."""
    return (
        b == 0x20  # space
        or b == 0x09  # tab
        or b == 0x0A  # LF
        or b == 0x0D  # CR
        or b == BYTE_COLON
    )


def _find_quote(bytes: Span[Byte, _], start: Int) -> Int:
    var i = start
    while i < len(bytes):
        if bytes[i] == BYTE_QUOTE:
            return i
        i += 1
    return -1


def _find_value_start(payload: String, key: String) raises -> Int:
    var bytes = payload.as_bytes()
    var needle = ('"' + key + '"').as_bytes()
    var last = len(bytes) - len(needle)
    var at = -1
    var i = 0
    while i <= last:
        var matched = True
        for j in range(len(needle)):
            if bytes[i + j] != needle[j]:
                matched = False
                break
        if matched:
            at = i
            break
        i += 1
    if at < 0:
        raise Error(
            "protocol error: field `" + key + "` missing in: " + payload
        )
    i = at + len(needle)
    while i < len(bytes) and _is_gap_char(bytes[i]):
        i += 1
    if i >= len(bytes):
        raise Error("protocol error: truncated value for `" + key + "`")
    return i


def json_string_field(payload: String, key: String) raises -> String:
    """Extracts the value of a string field: {"key": "value"}."""
    var bytes = payload.as_bytes()
    var i = _find_value_start(payload, key)
    if bytes[i] != BYTE_QUOTE:
        raise Error("protocol error: field `" + key + "` is not a string")
    var end = _find_quote(bytes, i + 1)
    if end < 0:
        raise Error("protocol error: unterminated string for `" + key + "`")
    return String(StringSlice(from_utf8=bytes[i + 1 : end]))


def json_number_token(payload: String, key: String) raises -> String:
    """Extracts the raw token of a numeric field: {"key": 0.8411…}."""
    var bytes = payload.as_bytes()
    var i = _find_value_start(payload, key)
    var end = i
    while end < len(bytes) and (
        bytes[end] != BYTE_COMMA
        and bytes[end] != BYTE_CLOSE_OBJ
        and bytes[end] != BYTE_CLOSE_ARR
        and not _is_gap_char(bytes[end])
    ):
        end += 1
    if end == i:
        raise Error("protocol error: empty value for `" + key + "`")
    return String(StringSlice(from_utf8=bytes[i:end]))


# --- Unix domain socket client (libc via external_call) -------------------- #
# `external_call["name", Ret, Arg0, Arg1, ...](args)` resolves `name` at
# compile time against the libraries every Mojo binary already links
# (libSystem on macOS, libc on Linux), so there is nothing to dlopen here.
# To bind a third-party shared library that is *not* linked by default, use
# `std.ffi.OwnedDLHandle` + `get_function` instead — same call shape.


struct UnixSocket:
    """A blocking Unix domain socket with poll-bounded reads."""

    var _fd: c_int

    def __init__(out self) raises:
        self._fd = external_call["socket", c_int](AF_UNIX, SOCK_STREAM, 0)
        if self._fd < 0:
            raise Error(
                "socket() failed — cannot create a Unix domain socket"
            )

    def __deinit__(deinit self):
        if self._fd >= 0:
            _ = external_call["close", c_int](self._fd)

    def connect(self, path: String) raises:
        var path_bytes = path.as_bytes()
        if len(path_bytes) + 1 > SUN_PATH_CAPACITY:
            raise Error(
                "socket path exceeds "
                + String(SUN_PATH_CAPACITY - 1)
                + " bytes: "
                + path
            )
        var addr = Array[Byte, SOCKADDR_UN_SIZE](fill=0)
        comptime if CompilationTarget.is_macos():
            addr[0] = Byte(SOCKADDR_UN_SIZE)  # sun_len (BSD convention)
            addr[1] = Byte(AF_UNIX)  # sun_family is one byte on BSD
        else:
            addr.unsafe_ptr().unsafe_bitcast[UInt16]()[] = UInt16(AF_UNIX)
        for i in range(len(path_bytes)):
            addr[2 + i] = path_bytes[i]
        var rc = external_call["connect", c_int](
            self._fd, addr.unsafe_ptr(), c_uint(SOCKADDR_UN_SIZE)
        )
        if rc != 0:
            raise Error(
                "connect() failed for " + path + " — worker not listening"
            )

    def _wait_readable(self) raises:
        """Bounds every read with poll(2) so a stuck worker fails, not hangs."""
        var pfd = Array[Byte, 8](fill=0)  # struct pollfd {fd, events, revents}
        var fields = pfd.unsafe_ptr().unsafe_bitcast[Int32]()
        fields[unsafe_offset=0] = self._fd
        fields[unsafe_offset=1] = POLLIN  # events=POLLIN, revents=0
        var rc = external_call["poll", c_int](pfd.unsafe_ptr(), 1, IO_TIMEOUT_MS)
        if rc == 0:
            raise Error("timed out waiting for the runtime worker")
        if rc < 0:
            raise Error("poll() failed while waiting for the runtime worker")

    def send_all(self, bytes: Span[Byte, _]) raises:
        var sent = 0
        while sent < len(bytes):
            var n = external_call["send", c_ssize_t](
                self._fd, bytes.unsafe_ptr().unsafe_offset(sent), len(bytes) - sent, 0
            )
            if n <= 0:
                raise Error(
                    "send() failed — runtime worker closed the connection"
                )
            sent += n

    def recv_exact(self, count: Int) raises -> List[Byte]:
        var buf = List[Byte](length=count, fill=0)
        var got = 0
        while got < count:
            self._wait_readable()
            var n = external_call["recv", c_ssize_t](
                self._fd, buf.unsafe_ptr().unsafe_offset(got), count - got, 0
            )
            if n <= 0:
                raise Error(
                    "recv() failed — runtime worker closed the connection"
                )
            got += n
        return buf^


# --- Framed JSON protocol --------------------------------------------------- #


def send_frame(mut sock: UnixSocket, payload: String) raises:
    """Sends one frame: 4-byte big-endian length + UTF-8 JSON payload."""
    var body = payload.as_bytes()
    if len(body) == 0 or len(body) > MAX_FRAME_BYTES:
        raise Error(
            "refusing to send a frame of " + String(len(body)) + " bytes"
        )
    var header = List[Byte]()
    header.append(Byte((len(body) >> 24) & 0xFF))
    header.append(Byte((len(body) >> 16) & 0xFF))
    header.append(Byte((len(body) >> 8) & 0xFF))
    header.append(Byte(len(body) & 0xFF))
    sock.send_all(Span(header))
    sock.send_all(body)


def recv_frame(mut sock: UnixSocket) raises -> String:
    """Receives one frame and returns the payload as a String."""
    var header = sock.recv_exact(4)
    var size = (
        (Int(header[0]) << 24)
        | (Int(header[1]) << 16)
        | (Int(header[2]) << 8)
        | Int(header[3])
    )
    if size <= 0 or size > MAX_FRAME_BYTES:
        raise Error("worker declared an invalid frame size: " + String(size))
    var body = sock.recv_exact(size)
    return String(StringSlice(from_utf8=Span(body)))


# --- Runtime discovery ------------------------------------------------------ #


def latest_python_dir(conda_prefix: String) raises -> String:
    """Finds the `python3.*` dir under `<prefix>/lib` (exactly one per env)."""
    var lib_dir = conda_prefix + "/lib"
    var found = ""
    for entry in listdir(lib_dir):
        if entry.startswith("python3."):
            found = entry
            break
    if found.byte_length() == 0:
        raise Error("no python3.* found under " + lib_dir)
    return found


def resolve_python_prefix() raises -> String:
    """Finds a Python 3.14 prefix for the worker's embedded interpreter.

    The worker embeds CPython but ships no standard library, so it always
    needs a real interpreter home. Inside pixi that is simply CONDA_PREFIX;
    otherwise we ask a `python3.14` found on PATH.
    """
    var prefix = getenv("CONDA_PREFIX")
    if prefix.byte_length() > 0:
        return prefix
    try:
        var detected = run(
            "python3.14 -c 'import sys; print(sys.base_prefix)'"
        )
        if detected.byte_length() > 0 and exists(detected):
            return detected
    except:
        pass  # fall through to the actionable error below
    raise Error(
        "no Python environment found — run via `pixi run demo`, or install"
        " Python 3.14 so the runtime worker can locate its standard library"
    )


def resolve_worker_path(prefix: String) raises -> String:
    """$ALGENTA_RUNTIME_LIB wins; otherwise resolve from the environment."""
    var override = getenv("ALGENTA_RUNTIME_LIB")
    if override.byte_length() > 0:
        if not exists(override):
            raise Error("ALGENTA_RUNTIME_LIB does not exist: " + override)
        return override
    var site = (
        prefix + "/lib/" + latest_python_dir(prefix) + "/site-packages"
    )
    var worker = site + "/algenta_runtime_native/algenta-runtime-worker"
    if not exists(worker):
        raise Error(
            "no Algenta runtime worker at "
            + worker
            + " — is the algenta-runtime-native wheel installed for this"
            " platform? (set ALGENTA_RUNTIME_LIB to override the path)"
        )
    return worker


def configure_worker_environment(
    conda_prefix: String, worker_path: String
) raises:
    """Prepares the embedded-interpreter environment the worker expects.

    The runtime worker embeds CPython and must be told where its home and
    shared libpython live — the same two variables the Python SDK's runtime
    launcher sets before exec'ing the worker:
      * PYTHONHOME          → the environment prefix (its stdlib home)
      * MOJO_PYTHON_LIBRARY → the matching shared libpython
    The environment's own libpython is preferred because it exactly matches
    the interpreter distribution under PYTHONHOME; the wheel bundles a
    fallback copy next to the worker executable.
    """
    _ = setenv("PYTHONHOME", conda_prefix)
    var libpython = "lib" + latest_python_dir(conda_prefix)
    var candidates = List[String]()
    comptime if CompilationTarget.is_macos():
        candidates.append(conda_prefix + "/lib/" + libpython + ".dylib")
    else:
        candidates.append(conda_prefix + "/lib/" + libpython + ".so.1.0")
        candidates.append(conda_prefix + "/lib/" + libpython + ".so")
    # Fallback: the libpython bundled beside the worker in the wheel.
    var slash = worker_path.rfind("/")
    if slash >= 0:  # 0 = the worker sits directly under the filesystem root
        var worker_dir = String(worker_path[byte = :slash])
        comptime if CompilationTarget.is_macos():
            candidates.append(worker_dir + "/" + libpython + ".dylib")
        else:
            candidates.append(worker_dir + "/" + libpython + ".so.1.0")
    for candidate in candidates:
        if exists(candidate):
            _ = setenv("MOJO_PYTHON_LIBRARY", candidate)
            return
    raise Error("no shared libpython found for " + libpython)


# --- Demo orchestration ------------------------------------------------------ #


def exchange(mut sock: UnixSocket, label: String, payload: String) raises -> String:
    print("  > " + label + ": " + payload)
    send_frame(sock, payload)
    var response = recv_frame(sock)
    print("  < " + response)
    return response


def run_demo() raises:
    var prefix = resolve_python_prefix()
    var worker = resolve_worker_path(prefix)
    print("Algenta × Mojo quickstart")
    print("  python prefix:  " + prefix)
    print("  runtime worker: " + worker)

    configure_worker_environment(prefix, worker)

    # Unique, short socket path (sun_path is capped at ~104 bytes).
    var pid = external_call["getpid", c_int]()
    var tmpdir = getenv("TMPDIR", "/tmp")
    if tmpdir.endswith("/"):
        var trimmed = String(tmpdir[byte = :tmpdir.byte_length() - 1])
        tmpdir = trimmed
    var sock_path = (
        tmpdir + "/algenta-mojo-demo-" + String(Int(pid)) + ".sock"
    )

    # Ignore SIGPIPE so a dead worker surfaces as an error, not a signal kill.
    _ = external_call["signal", UInt](SIGPIPE, SIG_IGN)

    print("  launching worker …")
    var proc = Process.run(worker, ["--server", sock_path])

    # Wait for the worker to create and listen on its socket.
    var sock = UnixSocket()
    var waited = 0.0
    var connected = False
    while waited < STARTUP_TIMEOUT_SECONDS:
        var status = proc.poll()
        if status.has_exited():
            raise Error("runtime worker exited during startup")
        if exists(sock_path):
            try:
                sock.connect(sock_path)
                connected = True
                break
            except:
                pass  # socket file exists before accept() is ready; retry
        sleep(0.01)
        waited += 0.01
    if not connected:
        raise Error("runtime worker did not become ready in time")
    print("  connected: " + sock_path)

    # 1. Handshake: the worker announces itself; "status" must be "ready".
    var handshake = recv_frame(sock)
    print("  < handshake: " + handshake)
    if json_string_field(handshake, "status") != "ready":
        raise Error("unexpected handshake: " + handshake)

    # 2. Ping: the liveness no-op.
    var pong = exchange(sock, "ping", '{"type":"ping"}')
    if json_string_field(pong, "status") != "ok":
        raise Error("ping failed: " + pong)

    # 3. Deterministic library call: activations.gelu(1.0).
    var result = exchange(
        sock,
        "library_execute " + DEMO_MODULE + "." + DEMO_FUNCTION,
        '{"type":"library_execute","module":"'
        + DEMO_MODULE
        + '","function":"'
        + DEMO_FUNCTION
        + '","args":'
        + DEMO_ARGS_JSON
        + "}",
    )
    var value = json_number_token(result, "result")
    if not value.startswith(DEMO_RESULT_PREFIX):
        raise Error("unexpected " + DEMO_FUNCTION + " result: " + value)
    print(
        "  ✓ "
        + DEMO_MODULE
        + "."
        + DEMO_FUNCTION
        + "(1.0) = "
        + value
        + " (deterministic)"
    )

    # 4. Orderly shutdown.
    var bye = exchange(sock, "shutdown", '{"type":"shutdown"}')
    if json_string_field(bye, "status") != "bye":
        raise Error("shutdown failed: " + bye)

    _ = proc.kill()
    _ = proc.wait()
    try:
        remove(sock_path)
    except:
        pass  # the worker may already have unlinked it
    print("ok: handshake, ping, library_execute and shutdown all succeeded")


def main():
    try:
        run_demo()
    except e:
        print("error: " + String(e))
        exit(1)
