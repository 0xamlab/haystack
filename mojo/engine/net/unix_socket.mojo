"""
Pure Mojo Unix domain socket server — frame encoding + Python-backed socket I/O.

Wire protocol (both directions):
    [4 bytes big-endian uint32: payload length] [N bytes: UTF-8 JSON]

Public API:
  Frame encoding (pure Mojo byte manipulation — performance-critical):
    encode_u32_be(value: Int) -> List[UInt8]
    decode_u32_be(data: List[UInt8]) -> Int
    encode_frame(payload: String) -> List[UInt8]
    decode_frame_length(header: List[UInt8]) -> Int

  Socket wrappers (Python-backed fallback for libc FFI compat):
    libc_socket_unix() -> Int
    libc_bind_unix(fd: Int, path: String) raises
    libc_listen(fd: Int, backlog: Int) raises
    libc_accept(fd: Int) -> Int
    libc_close(fd: Int)
    libc_unlink(path: String)
    libc_path_exists(path: String) -> Bool
    libc_recv(fd: Int, buf: UnsafePointer[UInt8], count: Int) -> Int
    libc_send(fd: Int, buf: UnsafePointer[UInt8], count: Int) -> Int

  High-level framed I/O:
    send_frame(fd: Int, payload: String) raises
    recv_frame(fd: Int) -> String
    recv_exact(fd: Int, n: Int) -> List[UInt8]
"""

from std.memory import UnsafePointer, memset
from std.python import Python, PythonObject
from python_bridge import py_str


# ── Constants ─────────────────────────────────────────────────────────────────

comptime AF_UNIX: Int = 1
comptime SOCK_STREAM: Int = 1


# ── Length-prefixed frame helpers (pure byte manipulation) ─────────────────────


def encode_u32_be(value: Int) -> List[UInt8]:
    """Encode an Int as 4 big-endian bytes. Used for frame headers.

    Compatible with Python's struct.pack('>I', value).
    """
    var result = List[UInt8](capacity=4)
    result.append(UInt8((value >> 24) & 0xFF))
    result.append(UInt8((value >> 16) & 0xFF))
    result.append(UInt8((value >> 8) & 0xFF))
    result.append(UInt8(value & 0xFF))
    return result^


def decode_u32_be(data: List[UInt8]) -> Int:
    """Decode 4 big-endian bytes to Int.

    Compatible with Python's struct.unpack('>I', data)[0].
    """
    return (
        (Int(data[0]) << 24)
        | (Int(data[1]) << 16)
        | (Int(data[2]) << 8)
        | Int(data[3])
    )


def encode_frame(payload: String) -> List[UInt8]:
    """Encode a string into a length-prefixed frame.

    Returns: [4-byte big-endian length] + [UTF-8 payload bytes].
    """
    var payload_bytes = payload.as_bytes()
    var payload_len = len(payload_bytes)
    # Strip the trailing null byte that Mojo's as_bytes() appends
    if payload_len > 0 and payload_bytes[payload_len - 1] == 0:
        payload_len -= 1

    var header = encode_u32_be(payload_len)
    var frame = List[UInt8](capacity=4 + payload_len)
    for i in range(4):
        frame.append(header[i])
    for i in range(payload_len):
        frame.append(payload_bytes[i])
    return frame^


def decode_frame_length(header: List[UInt8]) -> Int:
    """Decode 4 big-endian bytes into a payload length integer."""
    return decode_u32_be(header)


# ── Python-backed socket wrappers ─────────────────────────────────────────────
# These use Python's socket module for actual I/O. The frame encoding above
# remains pure Mojo. Socket creation/bind/listen happens once at startup so
# Python overhead is negligible. This avoids libc FFI compatibility issues
# across Mojo nightly versions.
#
# Socket objects are stored in a Python-side global dict (keyed by fd)
# since Mojo does not support module-level global vars.


def _get_registry() raises -> PythonObject:
    """Get or create the Python-side socket registry dict."""
    var builtins = Python.import_module("builtins")
    if not Bool(builtins.hasattr(builtins, "_mojo_sock_registry")):
        builtins._mojo_sock_registry = Python.evaluate("dict()")
    return builtins._mojo_sock_registry


def _store_py_socket(fd: Int, sock: PythonObject) raises:
    """Associate a Python socket object with its fd."""
    var reg = _get_registry()
    reg[fd] = sock


def _get_py_socket(fd: Int) raises -> PythonObject:
    """Look up a Python socket by fd."""
    var reg = _get_registry()
    return reg[fd]


def _py_int(obj: PythonObject) raises -> Int:
    """Convert PythonObject to Mojo Int."""
    return Int(py=obj)


def _py_len(obj: PythonObject) raises -> Int:
    """Get Python len() as Mojo Int."""
    var b = Python.import_module("builtins")
    return Int(py=b.len(obj))


def libc_socket_unix() raises -> Int:
    """Create a Unix domain socket (AF_UNIX, SOCK_STREAM). Returns fd or -1."""
    try:
        var sock_m = Python.import_module("socket")
        var sock = sock_m.socket(sock_m.AF_UNIX, sock_m.SOCK_STREAM)
        var fd = _py_int(sock.fileno())
        _store_py_socket(fd, sock)
        return fd
    except:
        return -1


def libc_bind_unix(fd: Int, path: String) raises:
    """Bind the socket to a Unix domain socket path."""
    var sock = _get_py_socket(fd)
    sock.bind(path)


def libc_listen(fd: Int, backlog: Int) raises:
    """Listen for connections on the socket."""
    var sock = _get_py_socket(fd)
    sock.listen(backlog)


def libc_accept(fd: Int) raises -> Int:
    """Accept a connection. Returns the new connection fd or -1."""
    try:
        var sock = _get_py_socket(fd)
        var result = sock.accept()
        var conn = result[0]
        var new_fd = _py_int(conn.fileno())
        _store_py_socket(new_fd, conn)
        return new_fd
    except:
        return -1


def libc_close(fd: Int) raises:
    """Close a file descriptor."""
    try:
        var sock = _get_py_socket(fd)
        sock.close()
    except:
        pass


def libc_unlink(path: String) raises:
    """Delete a file (socket file cleanup)."""
    try:
        var os_m = Python.import_module("os")
        os_m.unlink(path)
    except:
        pass


def libc_path_exists(path: String) raises -> Bool:
    """Check if a path exists."""
    try:
        var os_path = Python.import_module("os.path")
        return Bool(os_path.exists(path))
    except:
        return False


def libc_recv(fd: Int, buf: UnsafePointer[UInt8], count: Int) raises -> Int:
    """Receive bytes from a socket. Returns bytes read, 0 on close, -1 on error."""
    try:
        var sock = _get_py_socket(fd)
        var data = sock.recv(count)
        var n = _py_len(data)
        if n == 0:
            return 0
        for i in range(n):
            buf[i] = UInt8(_py_int(data[i]))
        return n
    except:
        return -1


def libc_send(fd: Int, buf: UnsafePointer[UInt8], count: Int) raises -> Int:
    """Send bytes to a socket. Returns bytes sent or -1 on error."""
    try:
        var sock = _get_py_socket(fd)
        var ba = Python.import_module("builtins").bytearray(count)
        for i in range(count):
            ba[i] = Int(buf[i])
        var sent = _py_int(sock.send(Python.import_module("builtins").bytes(ba)))
        return sent
    except:
        return -1


# ── High-level framed I/O ────────────────────────────────────────────────────


def recv_exact(fd: Int, n: Int) raises -> List[UInt8]:
    """Receive exactly n bytes from fd using Python socket. Returns empty list on close."""
    var result = List[UInt8](capacity=n)
    try:
        var sock = _get_py_socket(fd)
        var total_read = 0
        while total_read < n:
            var data = sock.recv(n - total_read)
            var chunk_len = _py_len(data)
            if chunk_len <= 0:
                return List[UInt8]()
            for i in range(chunk_len):
                result.append(UInt8(_py_int(data[i])))
            total_read += chunk_len
    except:
        return List[UInt8]()
    return result^


def recv_frame(fd: Int) raises -> String:
    """Receive a length-prefixed frame from fd. Returns empty string on connection close."""
    # Read 4-byte header
    var header = recv_exact(fd, 4)
    if len(header) < 4:
        return String("")

    var payload_len = decode_u32_be(header)
    if payload_len == 0:
        return String("")

    # Read payload
    var payload_bytes = recv_exact(fd, payload_len)
    if len(payload_bytes) < payload_len:
        return String("")

    # Decode through Python's bytes->str path to avoid Mojo string-construction
    # edge cases on framed JSON payloads.
    var builtins = Python.import_module("builtins")
    var ba = builtins.bytearray(payload_len)
    for i in range(payload_len):
        ba[i] = Int(payload_bytes[i])
    return py_str(builtins.bytes(ba).decode("utf-8"))


def send_frame(fd: Int, payload: String) raises:
    """Send a length-prefixed frame on fd using Python socket."""
    var frame = encode_frame(payload)
    var frame_len = len(frame)
    var sock = _get_py_socket(fd)

    # Build bytearray from frame bytes
    var ba = Python.import_module("builtins").bytearray(frame_len)
    for i in range(frame_len):
        ba[i] = Int(frame[i])

    var total_sent = 0
    var frame_bytes = Python.import_module("builtins").bytes(ba)
    while total_sent < frame_len:
        var sent = _py_int(sock.send(frame_bytes[total_sent:]))
        if sent <= 0:
            raise Error("send_frame: send() failed")
        total_sent += sent
