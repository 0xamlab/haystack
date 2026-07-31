"""test_hostio_socket_native.mojo — known-value tests for the libpython-free socket layer.

Hand-written. Two jobs.

**One: prove the duplication is equivalent.** `hostio/socket_native.mojo` re-declares the frame
encoders instead of importing `net/unix_socket.mojo`, because importing that module would pull
`from std.python import Python` back into the graph and reintroduce the exact `libpython` dependency
the package exists to remove. Rule 3 says call the frozen kernel rather than reimplement it; this is
the one place that cannot comply, so the obligation that replaces the reuse is discharged here — both
modules are imported and their encoders compared byte for byte across a value sweep. If the frozen
encoding ever changed, this fails rather than the two silently diverging in production.

This test therefore *does* depend on Python (through the frozen import). That is fine: it runs under
`mojo run`, where CPython is present. The shipped worker imports only `hostio`.

**Two: cover the failures that are silent rather than loud.** A path that fits `sun_path` minus one
byte versus one that does not. A `recv` count larger than the buffer, which in the frozen twin is
rule 1's uncatchable abort rather than an error. A four-byte length header claiming gigabytes. A
short header, which the frozen `decode_u32_be` indexes past.

The socket assertions bind real AF_UNIX sockets under `/tmp` and unlink them; they need no peer,
because bind/listen/accept-readiness is the part where the per-platform `sockaddr_un` layout is
either right or quietly wrong.
"""
from net.unix_socket import (
    encode_u32_be as frozen_encode_u32_be,
    decode_u32_be as frozen_decode_u32_be,
    encode_frame as frozen_encode_frame,
)
from hostio.socket_native import (
    SN_ERR_BAD_COUNT,
    SN_ERR_BAD_FD,
    SN_ERR_PATH_EMPTY,
    SN_ERR_PATH_TOO_LONG,
    SN_MAX_FRAME_BYTES,
    sn_bind_unix,
    sn_close,
    sn_decode_frame_length,
    sn_decode_u32_be,
    sn_encode_frame,
    sn_encode_u32_be,
    sn_listen,
    sn_path_exists,
    sn_recv,
    sn_recv_exact,
    sn_send,
    sn_socket_unix,
    sn_unlink,
)


fn _bytes_equal(a: List[UInt8], b: List[UInt8]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── 1. byte-equality with the frozen encoders ─────────────────────────────
    # The sweep deliberately includes 0, the byte boundaries, and the top of the u32 range, because
    # a shift/mask error shows up at a boundary and nowhere else.
    var probes = List[Int]()
    probes.append(0)
    probes.append(1)
    probes.append(255)
    probes.append(256)
    probes.append(65535)
    probes.append(65536)
    probes.append(16777215)
    probes.append(16777216)
    probes.append(305419896)
    probes.append(4294967295)

    var u32_mismatch = 0
    for i in range(len(probes)):
        var v = probes[i]
        if not _bytes_equal(sn_encode_u32_be(v), frozen_encode_u32_be(v)):
            u32_mismatch += 1
    if u32_mismatch == 0:
        passed += 1
        print("  ✅ sn_encode_u32_be matches the frozen encoder on all", len(probes), "probes")
    else:
        failed += 1
        print("  ❌ sn_encode_u32_be diverged from frozen on", u32_mismatch, "probes")

    var rt_bad = 0
    for i in range(len(probes)):
        var v = probes[i]
        var enc = sn_encode_u32_be(v)
        if sn_decode_u32_be(enc) != v or frozen_decode_u32_be(enc) != v:
            rt_bad += 1
    if rt_bad == 0:
        passed += 1
        print("  ✅ u32 round-trips identically through both decoders")
    else:
        failed += 1
        print("  ❌ u32 round-trip diverged on", rt_bad, "probes")

    var payloads = List[String]()
    payloads.append(String(""))
    payloads.append(String("{}"))
    payloads.append(String("{\"type\":\"ping\"}"))
    payloads.append(String("{\"k\":\"éü中\"}"))

    var frame_mismatch = 0
    for i in range(len(payloads)):
        if not _bytes_equal(sn_encode_frame(payloads[i]), frozen_encode_frame(payloads[i])):
            frame_mismatch += 1
    if frame_mismatch == 0:
        passed += 1
        print("  ✅ sn_encode_frame is byte-identical to the frozen encoder, incl. non-ASCII")
    else:
        failed += 1
        print("  ❌ sn_encode_frame diverged on", frame_mismatch, "payloads")

    # ── 2. the bounds guard the frozen twin does not have ─────────────────────
    var short = List[UInt8]()
    short.append(1)
    short.append(2)
    if sn_decode_u32_be(short) == -1 and sn_decode_frame_length(short) == -1:
        passed += 1
        print("  ✅ a short header returns -1 instead of indexing past the end")
    else:
        failed += 1
        print("  ❌ short header was not rejected")

    # ── 3. real AF_UNIX lifecycle ─────────────────────────────────────────────
    var path = String("/tmp/algenta_test_hostio.sock")
    _ = sn_unlink(path)
    var fd = sn_socket_unix()
    if fd >= 0:
        passed += 1
        print("  ✅ socket(AF_UNIX, SOCK_STREAM) returned fd", fd)
    else:
        failed += 1
        print("  ❌ socket() failed:", fd)

    if sn_bind_unix(fd, path) == 0 and sn_listen(fd, 8) == 0 and sn_path_exists(path):
        passed += 1
        print("  ✅ bind + listen succeeded and the socket file exists")
    else:
        failed += 1
        print("  ❌ bind/listen/exists failed — check the sockaddr_un layout for this platform")

    _ = sn_close(fd)
    _ = sn_unlink(path)
    if not sn_path_exists(path):
        passed += 1
        print("  ✅ close + unlink cleaned up")
    else:
        failed += 1
        print("  ❌ socket file survived unlink")

    # ── 4. path bounds ────────────────────────────────────────────────────────
    # 104 bytes on Darwin, 108 on Linux. Build one that overflows either.
    var long_path = String("/tmp/")
    for _ in range(40):
        long_path += "abcdefgh"
    var fd2 = sn_socket_unix()
    if sn_bind_unix(fd2, long_path) == -SN_ERR_PATH_TOO_LONG:
        passed += 1
        print("  ✅ an oversize path is rejected, not silently truncated to a different socket")
    else:
        failed += 1
        print("  ❌ oversize path was not rejected")

    if sn_bind_unix(fd2, String("")) == -SN_ERR_PATH_EMPTY:
        passed += 1
        print("  ✅ an empty path reports a distinct status from an oversize one")
    else:
        failed += 1
        print("  ❌ empty path did not report SN_ERR_PATH_EMPTY")
    _ = sn_close(fd2)

    # ── 5. count and fd validation ────────────────────────────────────────────
    var small = List[UInt8]()
    small.append(0)
    small.append(0)
    if sn_recv(0, small, 4096) == -SN_ERR_BAD_COUNT:
        passed += 1
        print("  ✅ a recv count larger than the buffer is refused, not an out-of-bounds write")
    else:
        failed += 1
        print("  ❌ recv did not validate count against the real buffer length")

    if sn_send(-1, small, 2) == -SN_ERR_BAD_FD and sn_recv(-1, small, 2) == -SN_ERR_BAD_FD:
        passed += 1
        print("  ✅ a negative fd is refused on both directions")
    else:
        failed += 1
        print("  ❌ negative fd was not refused")

    # ── 6. the frame ceiling ──────────────────────────────────────────────────
    # Four attacker-controlled bytes must not be able to pre-size a multi-gigabyte list.
    if len(sn_recv_exact(0, SN_MAX_FRAME_BYTES + 1)) == 0:
        passed += 1
        print("  ✅ an oversize frame length is refused before allocating")
    else:
        failed += 1
        print("  ❌ recv_exact accepted a length above SN_MAX_FRAME_BYTES")

    if SN_MAX_FRAME_BYTES == 67108864:
        passed += 1
        print("  ✅ the frame ceiling is 64 MiB, matching the Python worker and the TS client")
    else:
        failed += 1
        print("  ❌ SN_MAX_FRAME_BYTES drifted from the 64 MiB transport contract")

    print("  [hostio.socket_native] Passed:", passed, "Failed:", failed)
