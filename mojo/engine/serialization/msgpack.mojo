"""
msgpack.mojo — MessagePack binary serialization. Zero Python imports.

Implements the MessagePack specification (msgpack.org) for encoding/decoding
integers, floats, strings, booleans, nil, arrays, and maps.

Public API:
  msgpack_encode_int()           msgpack_decode_int()
  msgpack_encode_float()         msgpack_decode_float()
  msgpack_encode_string()        msgpack_decode_string()
  msgpack_encode_bool()
  msgpack_encode_nil()
  msgpack_encode_array_header()
  msgpack_encode_map_header()
"""

from std.memory import bitcast


# ── Result structs for decode functions ──────────────────────────────────────


struct MsgPackIntResult(Copyable, Movable):
    """Result of decoding an integer: value and bytes consumed."""
    var value: Int
    var consumed: Int

    def __init__(out self, value: Int = 0, consumed: Int = 0):
        self.value = value
        self.consumed = consumed

    def __copyinit__(out self, copy: Self):
        self.value = copy.value
        self.consumed = copy.consumed


struct MsgPackFloatResult(Copyable, Movable):
    """Result of decoding a float: value and bytes consumed."""
    var value: Float64
    var consumed: Int

    def __init__(out self, value: Float64 = 0.0, consumed: Int = 0):
        self.value = value
        self.consumed = consumed

    def __copyinit__(out self, copy: Self):
        self.value = copy.value
        self.consumed = copy.consumed


struct MsgPackStringResult(Copyable, Movable):
    """Result of decoding a string: value and bytes consumed."""
    var value: String
    var consumed: Int

    def __init__(out self, value: String = String(""), consumed: Int = 0):
        self.value = value
        self.consumed = consumed

    def __copyinit__(out self, copy: Self):
        self.value = copy.value
        self.consumed = copy.consumed


# ── Encoding: Integer ────────────────────────────────────────────────────────


def msgpack_encode_int(v: Int) -> List[UInt8]:
    """Encode an integer using the most compact MessagePack format."""
    var buf = List[UInt8]()

    # Positive fixint: 0 to 127
    if v >= 0 and v <= 127:
        buf.append(UInt8(v))
        return buf^

    # Negative fixint: -32 to -1
    if v >= -32 and v < 0:
        buf.append(UInt8(v + 256))
        return buf^

    # uint8: 128-255
    if v >= 0 and v <= 255:
        buf.append(UInt8(0xcc))
        buf.append(UInt8(v))
        return buf^

    # uint16: 256-65535
    if v >= 0 and v <= 65535:
        buf.append(UInt8(0xcd))
        buf.append(UInt8((v >> 8) & 0xff))
        buf.append(UInt8(v & 0xff))
        return buf^

    # uint32: 65536-4294967295
    if v >= 0 and v <= 4294967295:
        buf.append(UInt8(0xce))
        buf.append(UInt8((v >> 24) & 0xff))
        buf.append(UInt8((v >> 16) & 0xff))
        buf.append(UInt8((v >> 8) & 0xff))
        buf.append(UInt8(v & 0xff))
        return buf^

    # uint64 for large positive
    if v >= 0:
        buf.append(UInt8(0xcf))
        buf.append(UInt8((v >> 56) & 0xff))
        buf.append(UInt8((v >> 48) & 0xff))
        buf.append(UInt8((v >> 40) & 0xff))
        buf.append(UInt8((v >> 32) & 0xff))
        buf.append(UInt8((v >> 24) & 0xff))
        buf.append(UInt8((v >> 16) & 0xff))
        buf.append(UInt8((v >> 8) & 0xff))
        buf.append(UInt8(v & 0xff))
        return buf^

    # int8: -128 to -33
    if v >= -128:
        buf.append(UInt8(0xd0))
        buf.append(UInt8(v + 256))
        return buf^

    # int16: -32768 to -129
    if v >= -32768:
        buf.append(UInt8(0xd1))
        var u = v + 65536
        buf.append(UInt8((u >> 8) & 0xff))
        buf.append(UInt8(u & 0xff))
        return buf^

    # int32: -2147483648 to -32769
    if v >= -2147483648:
        buf.append(UInt8(0xd2))
        var u = v + 4294967296
        buf.append(UInt8((u >> 24) & 0xff))
        buf.append(UInt8((u >> 16) & 0xff))
        buf.append(UInt8((u >> 8) & 0xff))
        buf.append(UInt8(u & 0xff))
        return buf^

    # int64
    buf.append(UInt8(0xd3))
    var u = v
    buf.append(UInt8((u >> 56) & 0xff))
    buf.append(UInt8((u >> 48) & 0xff))
    buf.append(UInt8((u >> 40) & 0xff))
    buf.append(UInt8((u >> 32) & 0xff))
    buf.append(UInt8((u >> 24) & 0xff))
    buf.append(UInt8((u >> 16) & 0xff))
    buf.append(UInt8((u >> 8) & 0xff))
    buf.append(UInt8(u & 0xff))
    return buf^


# ── Encoding: Float64 ───────────────────────────────────────────────────────


def msgpack_encode_float(v: Float64) -> List[UInt8]:
    """Encode a float64 as MessagePack float64 (0xcb + 8 bytes big-endian IEEE 754)."""
    var buf = List[UInt8]()
    buf.append(UInt8(0xcb))

    var bits = bitcast[DType.uint64](v)
    var u = Int(bits)
    buf.append(UInt8((u >> 56) & 0xff))
    buf.append(UInt8((u >> 48) & 0xff))
    buf.append(UInt8((u >> 40) & 0xff))
    buf.append(UInt8((u >> 32) & 0xff))
    buf.append(UInt8((u >> 24) & 0xff))
    buf.append(UInt8((u >> 16) & 0xff))
    buf.append(UInt8((u >> 8) & 0xff))
    buf.append(UInt8(u & 0xff))
    return buf^


# ── Encoding: String ─────────────────────────────────────────────────────────


def msgpack_encode_string(v: String) -> List[UInt8]:
    """Encode a string using the most compact MessagePack string format."""
    var buf = List[UInt8]()
    var bs = v.as_bytes()
    var n = len(v)

    if n <= 31:
        buf.append(UInt8(0xa0 | n))
    elif n <= 255:
        buf.append(UInt8(0xd9))
        buf.append(UInt8(n))
    elif n <= 65535:
        buf.append(UInt8(0xda))
        buf.append(UInt8((n >> 8) & 0xff))
        buf.append(UInt8(n & 0xff))
    else:
        buf.append(UInt8(0xdb))
        buf.append(UInt8((n >> 24) & 0xff))
        buf.append(UInt8((n >> 16) & 0xff))
        buf.append(UInt8((n >> 8) & 0xff))
        buf.append(UInt8(n & 0xff))

    for i in range(n):
        buf.append(bs[i])

    return buf^


# ── Encoding: Bool ───────────────────────────────────────────────────────────


def msgpack_encode_bool(v: Bool) -> List[UInt8]:
    """Encode a boolean: true=0xc3, false=0xc2."""
    var buf = List[UInt8]()
    if v:
        buf.append(UInt8(0xc3))
    else:
        buf.append(UInt8(0xc2))
    return buf^


# ── Encoding: Nil ────────────────────────────────────────────────────────────


def msgpack_encode_nil() -> List[UInt8]:
    """Encode nil: 0xc0."""
    var buf = List[UInt8]()
    buf.append(UInt8(0xc0))
    return buf^


# ── Encoding: Array header ───────────────────────────────────────────────────


def msgpack_encode_array_header(n: Int) -> List[UInt8]:
    """Encode an array header (element count)."""
    var buf = List[UInt8]()
    if n <= 15:
        buf.append(UInt8(0x90 | n))
    elif n <= 65535:
        buf.append(UInt8(0xdc))
        buf.append(UInt8((n >> 8) & 0xff))
        buf.append(UInt8(n & 0xff))
    else:
        buf.append(UInt8(0xdd))
        buf.append(UInt8((n >> 24) & 0xff))
        buf.append(UInt8((n >> 16) & 0xff))
        buf.append(UInt8((n >> 8) & 0xff))
        buf.append(UInt8(n & 0xff))
    return buf^


# ── Encoding: Map header ────────────────────────────────────────────────────


def msgpack_encode_map_header(n: Int) -> List[UInt8]:
    """Encode a map header (pair count)."""
    var buf = List[UInt8]()
    if n <= 15:
        buf.append(UInt8(0x80 | n))
    elif n <= 65535:
        buf.append(UInt8(0xde))
        buf.append(UInt8((n >> 8) & 0xff))
        buf.append(UInt8(n & 0xff))
    else:
        buf.append(UInt8(0xdf))
        buf.append(UInt8((n >> 24) & 0xff))
        buf.append(UInt8((n >> 16) & 0xff))
        buf.append(UInt8((n >> 8) & 0xff))
        buf.append(UInt8(n & 0xff))
    return buf^


# ── Decoding: Integer ────────────────────────────────────────────────────────


def msgpack_decode_int(data: List[UInt8], pos: Int) -> MsgPackIntResult:
    """Decode an integer from data at pos. Returns MsgPackIntResult(value, consumed)."""
    # A negative pos would read data out of bounds — an uncatchable abort.
    if pos < 0 or pos >= len(data):
        return MsgPackIntResult(0, 0)

    var tag = Int(data[pos])

    # Positive fixint: 0x00-0x7f
    if tag <= 0x7f:
        return MsgPackIntResult(tag, 1)

    # Negative fixint: 0xe0-0xff
    if tag >= 0xe0:
        return MsgPackIntResult(tag - 256, 1)

    # uint8
    if tag == 0xcc:
        if pos + 1 >= len(data):
            return MsgPackIntResult(0, 0)
        return MsgPackIntResult(Int(data[pos + 1]), 2)

    # uint16
    if tag == 0xcd:
        if pos + 2 >= len(data):
            return MsgPackIntResult(0, 0)
        var v = (Int(data[pos + 1]) << 8) | Int(data[pos + 2])
        return MsgPackIntResult(v, 3)

    # uint32
    if tag == 0xce:
        if pos + 4 >= len(data):
            return MsgPackIntResult(0, 0)
        var v = (Int(data[pos + 1]) << 24) | (Int(data[pos + 2]) << 16) | (Int(data[pos + 3]) << 8) | Int(data[pos + 4])
        return MsgPackIntResult(v, 5)

    # uint64
    if tag == 0xcf:
        if pos + 8 >= len(data):
            return MsgPackIntResult(0, 0)
        var v = 0
        for i in range(8):
            v = (v << 8) | Int(data[pos + 1 + i])
        return MsgPackIntResult(v, 9)

    # int8
    if tag == 0xd0:
        if pos + 1 >= len(data):
            return MsgPackIntResult(0, 0)
        var v = Int(data[pos + 1])
        if v >= 128:
            v = v - 256
        return MsgPackIntResult(v, 2)

    # int16
    if tag == 0xd1:
        if pos + 2 >= len(data):
            return MsgPackIntResult(0, 0)
        var v = (Int(data[pos + 1]) << 8) | Int(data[pos + 2])
        if v >= 32768:
            v = v - 65536
        return MsgPackIntResult(v, 3)

    # int32
    if tag == 0xd2:
        if pos + 4 >= len(data):
            return MsgPackIntResult(0, 0)
        var v = (Int(data[pos + 1]) << 24) | (Int(data[pos + 2]) << 16) | (Int(data[pos + 3]) << 8) | Int(data[pos + 4])
        if v >= 2147483648:
            v = v - 4294967296
        return MsgPackIntResult(v, 5)

    # int64
    if tag == 0xd3:
        if pos + 8 >= len(data):
            return MsgPackIntResult(0, 0)
        var v = 0
        for i in range(8):
            v = (v << 8) | Int(data[pos + 1 + i])
        if v >= (1 << 63):
            v = v - (1 << 64)
        return MsgPackIntResult(v, 9)

    return MsgPackIntResult(0, 0)


# ── Decoding: Float64 ───────────────────────────────────────────────────────


def msgpack_decode_float(data: List[UInt8], pos: Int) -> MsgPackFloatResult:
    """Decode a float64 from data at pos. Returns MsgPackFloatResult(value, consumed)."""
    # A negative pos would read data out of bounds — an uncatchable abort.
    if pos < 0 or pos >= len(data):
        return MsgPackFloatResult(0.0, 0)

    var tag = Int(data[pos])

    # float64: 0xcb
    if tag == 0xcb:
        if pos + 8 >= len(data):
            return MsgPackFloatResult(0.0, 0)
        var bits: UInt64 = 0
        for i in range(8):
            bits = (bits << 8) | UInt64(data[pos + 1 + i])
        var v = bitcast[DType.float64](bits)
        return MsgPackFloatResult(Float64(v), 9)

    # float32: 0xca
    if tag == 0xca:
        if pos + 4 >= len(data):
            return MsgPackFloatResult(0.0, 0)
        var bits: UInt32 = 0
        for i in range(4):
            bits = (bits << 8) | UInt32(data[pos + 1 + i])
        var v = bitcast[DType.float32](bits)
        return MsgPackFloatResult(Float64(v), 5)

    return MsgPackFloatResult(0.0, 0)


# ── Decoding: String ─────────────────────────────────────────────────────────


def msgpack_decode_string(data: List[UInt8], pos: Int) -> MsgPackStringResult:
    """Decode a string from data at pos. Returns MsgPackStringResult(value, consumed)."""
    # A negative pos would read data out of bounds — an uncatchable abort.
    if pos < 0 or pos >= len(data):
        return MsgPackStringResult(String(""), 0)

    var tag = Int(data[pos])
    var str_len = 0
    var header_size = 0

    # fixstr: 0xa0-0xbf
    if tag >= 0xa0 and tag <= 0xbf:
        str_len = tag & 0x1f
        header_size = 1
    elif tag == 0xd9:
        if pos + 1 >= len(data):
            return MsgPackStringResult(String(""), 0)
        str_len = Int(data[pos + 1])
        header_size = 2
    elif tag == 0xda:
        if pos + 2 >= len(data):
            return MsgPackStringResult(String(""), 0)
        str_len = (Int(data[pos + 1]) << 8) | Int(data[pos + 2])
        header_size = 3
    elif tag == 0xdb:
        if pos + 4 >= len(data):
            return MsgPackStringResult(String(""), 0)
        str_len = (Int(data[pos + 1]) << 24) | (Int(data[pos + 2]) << 16) | (Int(data[pos + 3]) << 8) | Int(data[pos + 4])
        header_size = 5
    else:
        return MsgPackStringResult(String(""), 0)

    var result = String("")
    var start = pos + header_size
    for i in range(str_len):
        if start + i < len(data):
            result += chr(Int(data[start + i]))

    return MsgPackStringResult(result, header_size + str_len)
