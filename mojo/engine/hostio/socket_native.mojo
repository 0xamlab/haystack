"""
socket_native.mojo — AF_UNIX sockets and length-prefixed frames over real libc FFI. Zero Python.

A drop-in behavioural twin of `net/unix_socket.mojo`'s public surface, implemented with
`external_call` instead of CPython's `socket` module. The frozen module is untouched and every
existing caller keeps using it; this one exists so the LLM worker binary can link without
`libpython`. See `hostio/__init__.mojo` for why that matters.

Wire protocol, byte-identical to the frozen module:
    [4 bytes big-endian uint32: payload length] [N bytes: UTF-8 JSON]

Public API:
  Frame encoding:
    sn_encode_u32_be(value: Int) -> List[UInt8]
    sn_decode_u32_be(data: List[UInt8]) -> Int
    sn_encode_frame(payload: String) -> List[UInt8]
    sn_decode_frame_length(header: List[UInt8]) -> Int

  Socket primitives (return -1 / False on failure; never raise, never abort):
    sn_socket_unix() -> Int
    sn_bind_unix(fd: Int, path: String) -> Int
    sn_listen(fd: Int, backlog: Int) -> Int
    sn_accept(fd: Int) -> Int
    sn_close(fd: Int) -> Int
    sn_unlink(path: String) -> Int
    sn_path_exists(path: String) -> Bool
    sn_recv(fd: Int, buf: List[UInt8], count: Int) -> Int
    sn_send(fd: Int, buf: List[UInt8], count: Int) -> Int

  Framed I/O:
    sn_recv_exact(fd: Int, n: Int) -> List[UInt8]
    sn_recv_frame(fd: Int) -> String
    sn_send_frame(fd: Int, payload: String) -> Int

The frame helpers are re-declared here rather than imported
-----------------------------------------------------------
Rule 3 says never reimplement a frozen kernel — call it. This is the one place that cannot comply,
and the reason is structural rather than convenient: importing `net/unix_socket.mojo` to reuse
`encode_u32_be` would pull `from std.python import Python` into the module graph and reintroduce
exactly the `libpython` dependency this package exists to remove. Importing it defeats the purpose.

The obligation that replaces the reuse: `test_hostio_socket_native.mojo` imports **both** modules and
asserts byte-equality of the encoders across a value sweep, so the duplication is proven equivalent
rather than assumed. If the frozen encoding ever changed, the test would fail rather than the two
silently diverging.

sockaddr_un is laid out per-platform
------------------------------------
Darwin is BSD-shaped and carries a length byte; Linux does not:

    Darwin:  { uint8_t sun_len; uint8_t sun_family; char sun_path[104]; }   106 bytes
    Linux:   { uint16_t sun_family;                 char sun_path[108]; }   110 bytes

Both put the path at byte offset 2, which is why one offset constant serves both, but the first two
bytes differ and the total length differs. Getting this wrong does not fail loudly — `bind` returns
-1 with no indication that the family field was misread — so the layout is written out explicitly
above each branch rather than derived.

Paths are bounded, not trusted
------------------------------
`sun_path` is a fixed 104/108-byte field with no terminator guarantee from the caller. A path at or
over the limit is rejected with `SN_ERR_PATH_TOO_LONG` before any copy, because the alternative is a
silently truncated path that binds a *different* socket than the caller asked for — which presents as
a connection that never arrives rather than an error.
"""

from std.ffi import external_call
from std.sys.info import CompilationTarget

# ── status codes ──────────────────────────────────────────────────────────────
# hostio owns 050-099 (see docs/mojo/new-kernel-package-rules.md rule 4e).
# Distinct per defect: a caller that gets a rejection needs to know which input is wrong.

comptime SN_OK: Int = 50
comptime SN_ERR_PATH_EMPTY: Int = 51
comptime SN_ERR_PATH_TOO_LONG: Int = 52
comptime SN_ERR_BAD_FD: Int = 53
comptime SN_ERR_BAD_COUNT: Int = 54
comptime SN_ERR_SYSCALL: Int = 55

# ── platform constants ────────────────────────────────────────────────────────
# AF_UNIX and SOCK_STREAM are both 1 on Darwin and Linux, so they need no branch.

comptime AF_UNIX: Int = 1
comptime SOCK_STREAM: Int = 1
comptime F_OK: Int = 0

comptime SUN_PATH_OFFSET: Int = 2
comptime SUN_LEN_DARWIN: Int = 106
comptime SUN_LEN_LINUX: Int = 110
comptime SUN_PATH_MAX_DARWIN: Int = 104
comptime SUN_PATH_MAX_LINUX: Int = 108

comptime SN_MAX_FRAME_BYTES: Int = 64 * 1024 * 1024
"""64 MiB, matching the Python worker's `_MAX_FRAME_BYTES` and the TypeScript client's
`MAX_MESSAGE_BYTES`. A length header is attacker-controlled in the sense that a malformed writer can
send any 32-bit value, and `recv_exact` would otherwise pre-size a 4 GiB list from four bytes."""


def _is_darwin() -> Bool:
    """True when compiling for macOS.

    Read once here rather than at each use so the two sockaddr layouts sit side by side in
    `_sockaddr_un` and cannot drift apart.
    """
    return CompilationTarget.is_macos()


def _sun_path_max() -> Int:
    return SUN_PATH_MAX_DARWIN if _is_darwin() else SUN_PATH_MAX_LINUX


def _sun_size() -> Int:
    return SUN_LEN_DARWIN if _is_darwin() else SUN_LEN_LINUX


def _cstr(s: String) -> List[UInt8]:
    """Copy a String into an owned NUL-terminated byte buffer.

    Stops at the first embedded NUL: a caller-supplied path containing one would otherwise be passed
    to libc as a shorter path than the caller believes, which is the classic truncation trap.
    """
    var raw = s.as_bytes()
    var out = List[UInt8](capacity=len(raw) + 1)
    for i in range(len(raw)):
        if raw[i] == 0:
            break
        out.append(raw[i])
    out.append(0)
    return out^


def _cstr_len(c: List[UInt8]) -> Int:
    """Length of a `_cstr` buffer excluding its terminator."""
    var n = len(c)
    return n - 1 if n > 0 else 0


def _sockaddr_un(path: String) -> List[UInt8]:
    """Build a platform-correct `sockaddr_un` for `path`.

    Returns an empty list when the path is empty or does not fit `sun_path`; every caller checks for
    that rather than binding a truncated address.
    """
    var c = _cstr(path)
    var plen = _cstr_len(c)
    if plen == 0 or plen >= _sun_path_max():
        return List[UInt8]()

    var size = _sun_size()
    var buf = List[UInt8](capacity=size)
    for _ in range(size):
        buf.append(0)

    if _is_darwin():
        # { uint8_t sun_len; uint8_t sun_family; char sun_path[104]; }
        buf[0] = UInt8(size)
        buf[1] = UInt8(AF_UNIX)
    else:
        # { uint16_t sun_family; char sun_path[108]; } — little-endian AF_UNIX == 1
        buf[0] = UInt8(AF_UNIX)
        buf[1] = 0

    for i in range(plen):
        buf[SUN_PATH_OFFSET + i] = c[i]
    return buf^


# ── frame encoding (pure byte manipulation) ───────────────────────────────────


def sn_encode_u32_be(value: Int) -> List[UInt8]:
    """Encode an Int as 4 big-endian bytes. Byte-identical to `net.unix_socket.encode_u32_be`."""
    var result = List[UInt8](capacity=4)
    result.append(UInt8((value >> 24) & 0xFF))
    result.append(UInt8((value >> 16) & 0xFF))
    result.append(UInt8((value >> 8) & 0xFF))
    result.append(UInt8(value & 0xFF))
    return result^


def sn_decode_u32_be(data: List[UInt8]) -> Int:
    """Decode 4 big-endian bytes to Int. Returns -1 on a short buffer rather than indexing past it.

    The frozen twin indexes `data[0..3]` unguarded, which is correct for its own call sites but is an
    uncatchable abort if a caller ever passes fewer than four bytes. Rule 1: a new surface bounds its
    own inputs.
    """
    if len(data) < 4:
        return -1
    return (
        (Int(data[0]) << 24)
        | (Int(data[1]) << 16)
        | (Int(data[2]) << 8)
        | Int(data[3])
    )


def sn_encode_frame(payload: String) -> List[UInt8]:
    """Encode a string into a length-prefixed frame: [4-byte BE length][UTF-8 payload]."""
    var payload_bytes = payload.as_bytes()
    var payload_len = len(payload_bytes)
    # Mojo's as_bytes() appends a trailing NUL; the frozen module strips it the same way.
    if payload_len > 0 and payload_bytes[payload_len - 1] == 0:
        payload_len -= 1

    var header = sn_encode_u32_be(payload_len)
    var frame = List[UInt8](capacity=4 + payload_len)
    for i in range(4):
        frame.append(header[i])
    for i in range(payload_len):
        frame.append(payload_bytes[i])
    return frame^


def sn_decode_frame_length(header: List[UInt8]) -> Int:
    """Decode a 4-byte header into a payload length. -1 on a short header."""
    return sn_decode_u32_be(header)


# ── socket primitives ─────────────────────────────────────────────────────────


def sn_socket_unix() -> Int:
    """Create an AF_UNIX SOCK_STREAM socket. Returns the fd, or -1."""
    var fd = external_call["socket", Int32](
        Int32(AF_UNIX), Int32(SOCK_STREAM), Int32(0)
    )
    return Int(fd)


def sn_bind_unix(fd: Int, path: String) -> Int:
    """Bind `fd` to a Unix socket path. Returns 0 on success, a negative status otherwise."""
    if fd < 0:
        return -SN_ERR_BAD_FD
    var addr = _sockaddr_un(path)
    if len(addr) == 0:
        # Distinguishes "you gave me nothing" from "your path will not fit" — the caller can only
        # act on the second, and it is the one that looks like a working config in a YAML file.
        var c = _cstr(path)
        return -SN_ERR_PATH_EMPTY if _cstr_len(c) == 0 else -SN_ERR_PATH_TOO_LONG
    var rc = external_call["bind", Int32](
        Int32(fd), addr.unsafe_ptr(), UInt32(len(addr))
    )
    return Int(rc) if Int(rc) == 0 else -SN_ERR_SYSCALL


def sn_listen(fd: Int, backlog: Int) -> Int:
    """Mark `fd` as accepting connections. Returns 0 on success."""
    if fd < 0:
        return -SN_ERR_BAD_FD
    var b = backlog if backlog > 0 else 1
    var rc = external_call["listen", Int32](Int32(fd), Int32(b))
    return Int(rc) if Int(rc) == 0 else -SN_ERR_SYSCALL


def sn_accept(fd: Int) -> Int:
    """Accept one connection. Returns the new fd, or -1.

    The peer address is discarded (NULL, NULL): an AF_UNIX server socket bound to a path Algenta
    chose learns nothing useful from the client's address, and asking for it would mean carrying a
    second sockaddr buffer whose length semantics differ across the two platforms again.
    """
    if fd < 0:
        return -1
    var nullptr = UnsafePointer[UInt8](unsafe_from_address=0)
    var conn = external_call["accept", Int32](Int32(fd), nullptr, nullptr)
    return Int(conn)


def sn_close(fd: Int) -> Int:
    """Close a file descriptor. Returns 0 on success. Closing an invalid fd is not an error here."""
    if fd < 0:
        return 0
    var rc = external_call["close", Int32](Int32(fd))
    return Int(rc) if Int(rc) == 0 else -SN_ERR_SYSCALL


def sn_unlink(path: String) -> Int:
    """Remove a filesystem entry. Returns 0 on success; a missing path is not an error."""
    var c = _cstr(path)
    if _cstr_len(c) == 0:
        return -SN_ERR_PATH_EMPTY
    var rc = external_call["unlink", Int32](c.unsafe_ptr())
    return 0 if Int(rc) == 0 else 0


def sn_path_exists(path: String) -> Bool:
    """True when `path` exists, via access(F_OK)."""
    var c = _cstr(path)
    if _cstr_len(c) == 0:
        return False
    var rc = external_call["access", Int32](c.unsafe_ptr(), Int32(F_OK))
    return Int(rc) == 0


def sn_recv(fd: Int, mut buf: List[UInt8], count: Int) -> Int:
    """Read up to `count` bytes into `buf`. Returns bytes read, 0 at EOF, negative on error.

    `count` is validated against the real length of `buf` before the call. The frozen twin writes
    through a raw pointer and trusts the count; here a mismatch is rule 1's uncatchable abort, so it
    is rejected instead.
    """
    if fd < 0:
        return -SN_ERR_BAD_FD
    if count <= 0 or count > len(buf):
        return -SN_ERR_BAD_COUNT
    var n = external_call["recv", Int](
        Int32(fd), buf.unsafe_ptr(), UInt(count), Int32(0)
    )
    return Int(n)


def sn_send(fd: Int, buf: List[UInt8], count: Int) -> Int:
    """Write `count` bytes from `buf`. Returns bytes sent, negative on error."""
    if fd < 0:
        return -SN_ERR_BAD_FD
    if count <= 0 or count > len(buf):
        return -SN_ERR_BAD_COUNT
    var n = external_call["send", Int](
        Int32(fd), buf.unsafe_ptr(), UInt(count), Int32(0)
    )
    return Int(n)


# ── framed I/O ────────────────────────────────────────────────────────────────


def sn_recv_exact(fd: Int, n: Int) -> List[UInt8]:
    """Read exactly `n` bytes. Returns an empty list on EOF, error, or an out-of-range `n`.

    Loops because a stream socket may return a short read at any point; a single `recv` that happens
    to fill the buffer in testing is the bug that shows up under load.
    """
    var out = List[UInt8]()
    if fd < 0 or n <= 0 or n > SN_MAX_FRAME_BYTES:
        return out^

    var chunk = List[UInt8](capacity=n)
    for _ in range(n):
        chunk.append(0)

    var total = 0
    while total < n:
        var want = n - total
        var got = external_call["recv", Int](
            Int32(fd), chunk.unsafe_ptr(), UInt(want), Int32(0)
        )
        var g = Int(got)
        if g <= 0:
            return List[UInt8]()
        for i in range(g):
            out.append(chunk[i])
        total += g
    return out^


def sn_recv_frame(fd: Int) -> String:
    """Read one length-prefixed frame. Returns "" on close, malformed header, or oversize length."""
    var header = sn_recv_exact(fd, 4)
    if len(header) < 4:
        return String("")

    var payload_len = sn_decode_u32_be(header)
    if payload_len <= 0:
        return String("")
    if payload_len > SN_MAX_FRAME_BYTES:
        # Refuse rather than allocate: four bytes should not be able to ask for gigabytes.
        return String("")

    var body = sn_recv_exact(fd, payload_len)
    if len(body) < payload_len:
        return String("")

    var out = String("")
    for i in range(len(body)):
        out += chr(Int(body[i]))
    return out^


def sn_send_frame(fd: Int, payload: String) -> Int:
    """Write one length-prefixed frame. Returns bytes sent, negative on error.

    Loops on partial writes for the same reason `sn_recv_exact` loops on partial reads.
    """
    if fd < 0:
        return -SN_ERR_BAD_FD
    var frame = sn_encode_frame(payload)
    var total = len(frame)
    if total > SN_MAX_FRAME_BYTES:
        return -SN_ERR_BAD_COUNT

    var sent = 0
    while sent < total:
        var rest = List[UInt8](capacity=total - sent)
        for i in range(sent, total):
            rest.append(frame[i])
        var n = external_call["send", Int](
            Int32(fd), rest.unsafe_ptr(), UInt(total - sent), Int32(0)
        )
        var wrote = Int(n)
        if wrote <= 0:
            return -SN_ERR_SYSCALL
        sent += wrote
    return sent
