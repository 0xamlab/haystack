"""
canonical.encode — canonical binary TLV encoding. Zero Python.

Every value gets exactly one byte sequence, so two inputs that are semantically
equal encode identically no matter which language or process produced them.

Wire grammar
------------
Each value is `tag || payload`:

    0x00  null      (no payload)
    0x01  false     (no payload)
    0x02  true      (no payload)
    0x03  int       zigzag varint          — one encoding per integer, sign included
    0x04  float     8 bytes, IEEE-754 big-endian
    0x05  string    varint byte length || UTF-8 bytes
    0x06  array     varint count || values
    0x07  object    varint count || (key, value) pairs, keys sorted by byte order

Frozen decisions, and why each one has to be a decision
-------------------------------------------------------
* **Big-endian floats.** Byte order would otherwise differ by architecture; decimal
  text would differ by language (`1.0` vs `1`).
* **-0.0 becomes +0.0.** `-0.0 == 0.0` is true in every language here, so treating
  the sign bit as significant would make equal values hash differently.
* **One NaN pattern.** IEEE-754 admits ~2^52 NaN bit patterns. Without collapsing
  them, two NaNs that compare and behave identically would hash differently.
* **Zigzag varints.** A fixed-width integer would leave leading zeros free to vary;
  zigzag gives small negatives short encodings and exactly one form each.
* **Keys sorted by UTF-8 bytes.** Insertion order is not semantic, and any
  locale-aware ordering differs between runtimes.

Changing any of these changes every hash ever produced, which is the point: the
encoding is an identity, so it is versioned rather than tuned. See `ENCODING_VERSION`.
"""
from std.math import isnan
from std.memory import bitcast

comptime ENCODING_VERSION: String = "algenta-canonical/v1"

comptime TAG_NULL: UInt8 = 0x00
comptime TAG_FALSE: UInt8 = 0x01
comptime TAG_TRUE: UInt8 = 0x02
comptime TAG_INT: UInt8 = 0x03
comptime TAG_FLOAT: UInt8 = 0x04
comptime TAG_STRING: UInt8 = 0x05
comptime TAG_ARRAY: UInt8 = 0x06
comptime TAG_OBJECT: UInt8 = 0x07

# The single quiet-NaN pattern every NaN collapses to.
comptime CANONICAL_NAN_BITS: UInt64 = 0x7FF8000000000000


def encoding_version() -> String:
    """Identity of this encoding. Bump only alongside a deliberate hash break."""
    return ENCODING_VERSION


def write_varint(mut out: List[UInt8], value: UInt64):
    """LEB128: 7 bits per byte, high bit continues. One encoding per value."""
    var remaining = value
    while True:
        var byte = UInt8(remaining & 0x7F)
        remaining = remaining >> 7
        if remaining != 0:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return


def zigzag(value: Int) -> UInt64:
    """Map signed to unsigned so small magnitudes stay short: 0,-1,1,-2 -> 0,1,2,3."""
    if value < 0:
        return UInt64(-(value + 1)) * 2 + 1
    return UInt64(value) * 2


def write_null(mut out: List[UInt8]):
    out.append(TAG_NULL)


def write_bool(mut out: List[UInt8], value: Bool):
    out.append(TAG_TRUE if value else TAG_FALSE)


def write_int(mut out: List[UInt8], value: Int):
    out.append(TAG_INT)
    write_varint(out, zigzag(value))


def write_float(mut out: List[UInt8], value: Float64):
    """IEEE-754 big-endian, with NaN collapsed and -0.0 normalised to +0.0."""
    out.append(TAG_FLOAT)
    var bits: UInt64
    if isnan(value):
        bits = CANONICAL_NAN_BITS
    elif value == 0.0:
        # Catches -0.0: it compares equal to 0.0, so it must not encode differently.
        bits = 0
    else:
        bits = bitcast[DType.uint64](value)
    for shift in range(7, -1, -1):
        out.append(UInt8((bits >> UInt64(shift * 8)) & 0xFF))


def write_string(mut out: List[UInt8], value: String):
    out.append(TAG_STRING)
    var bytes = value.as_bytes()
    write_varint(out, UInt64(value.byte_length()))
    for i in range(value.byte_length()):
        out.append(bytes[i])


def write_array_header(mut out: List[UInt8], count: Int):
    """Open an array of `count` values; append each value after this."""
    out.append(TAG_ARRAY)
    write_varint(out, UInt64(count))


def write_object_header(mut out: List[UInt8], count: Int):
    """Open an object of `count` pairs; append sorted (key, value) pairs after this."""
    out.append(TAG_OBJECT)
    write_varint(out, UInt64(count))


def byte_order_less(a: String, b: String) -> Bool:
    """Strict UTF-8 byte-order comparison — the object key ordering.

    Byte order rather than any collation: it is the only ordering that is identical
    in every language and locale.
    """
    var ab = a.as_bytes()
    var bb = b.as_bytes()
    var n = a.byte_length() if a.byte_length() < b.byte_length() else b.byte_length()
    for i in range(n):
        if ab[i] != bb[i]:
            return ab[i] < bb[i]
    return a.byte_length() < b.byte_length()


def sort_keys(keys: List[String]) -> List[String]:
    """Keys in canonical order. Insertion sort: key counts here are small."""
    var sorted = List[String]()
    for i in range(len(keys)):
        sorted.append(keys[i])
    for i in range(1, len(sorted)):
        var j = i
        while j > 0 and byte_order_less(sorted[j], sorted[j - 1]):
            var swap = sorted[j]
            sorted[j] = sorted[j - 1]
            sorted[j - 1] = swap
            j -= 1
    return sorted^


def write_float_list(mut out: List[UInt8], values: List[Float64]):
    """An array of floats — the common shape for kernel arguments and results."""
    write_array_header(out, len(values))
    for i in range(len(values)):
        write_float(out, values[i])


def write_int_list(mut out: List[UInt8], values: List[Int]):
    write_array_header(out, len(values))
    for i in range(len(values)):
        write_int(out, values[i])


def write_string_list(mut out: List[UInt8], values: List[String]):
    write_array_header(out, len(values))
    for i in range(len(values)):
        write_string(out, values[i])


def to_hex(bytes: List[UInt8]) -> String:
    """Lowercase hex, for tests and for logging an encoding without a hash."""
    comptime digits = String("0123456789abcdef")
    var out = String("")
    var table = digits.as_bytes()
    for i in range(len(bytes)):
        out += chr(Int(table[Int(bytes[i] >> 4)]))
        out += chr(Int(table[Int(bytes[i] & 0x0F)]))
    return out
