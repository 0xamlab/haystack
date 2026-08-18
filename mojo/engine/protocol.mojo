"""
protocol.mojo — Protocol Buffer-like serialization primitives.

Replaces Python's protobuf basics with a pure Mojo implementation
supporting varint encoding, ZigZag signed integers, field encoding,
and simple message encode/decode.

Public API:
  encode_varint         — Encode unsigned int as varint bytes (base-128)
  decode_varint         — Decode varint, returns [value, bytes_consumed]
  zigzag_encode         — ZigZag encoding for signed integers
  zigzag_decode         — ZigZag decoding
  encode_field          — Encode a protobuf field (tag + varint value)
  decode_field          — Decode one field
  encode_string_field   — Encode string field (tag + length + bytes)
  decode_string_field   — Decode string field
  encode_message        — Encode multiple [field_number, value] pairs
  decode_message        — Decode all fields from message bytes
"""


# ── Varint encoding ──────────────────────────────────────────────────────────


def encode_varint(value: Int) -> List[Int]:
    """Encode unsigned int as varint bytes (base-128 encoding).

    Each byte uses 7 bits for data and 1 bit (MSB) as continuation flag.
    """
    var result = List[Int]()
    var v = value
    if v == 0:
        result.append(0)
        return result^
    while v > 0:
        var byte = v & 0x7F  # low 7 bits
        v >>= 7
        if v > 0:
            byte |= 0x80  # set continuation bit
        result.append(byte)
    return result^


def decode_varint(data: List[Int], offset: Int) -> List[Int]:
    """Decode varint from data starting at offset.

    Returns [decoded_value, bytes_consumed].
    """
    var result = List[Int]()
    # Out-of-range offset: data[pos] would abort; return [value=0, consumed=0].
    if offset < 0 or offset >= len(data):
        result.append(0)
        result.append(0)
        return result^
    var value: Int = 0
    var shift: Int = 0
    var pos = offset
    while pos < len(data):
        var byte = data[pos]
        value |= (byte & 0x7F) << shift
        pos += 1
        if (byte & 0x80) == 0:
            break
        shift += 7
    result.append(value)
    result.append(pos - offset)
    return result^


# ── ZigZag encoding ──────────────────────────────────────────────────────────


def zigzag_encode(value: Int) -> Int:
    """ZigZag encoding for signed integers: (n << 1) ^ (n >> 63).

    Maps signed integers to unsigned: 0->0, -1->1, 1->2, -2->3, ...
    """
    return (value << 1) ^ (value >> 63)


def zigzag_decode(value: Int) -> Int:
    """ZigZag decoding: (n >>> 1) ^ -(n & 1).

    Reverses the ZigZag mapping back to signed integers.
    """
    var unsigned_shift = value >> 1
    if (value & 1) == 0:
        return unsigned_shift
    else:
        return unsigned_shift ^ -1


# ── Field encoding ───────────────────────────────────────────────────────────


def encode_field(field_number: Int, wire_type: Int, value: Int) -> List[Int]:
    """Encode a protobuf field: tag (field_number << 3 | wire_type) + varint value.

    Wire types: 0=varint, 2=length-delimited.
    """
    var tag = (field_number << 3) | wire_type
    var result = encode_varint(tag)
    var val_bytes = encode_varint(value)
    for i in range(len(val_bytes)):
        result.append(val_bytes[i])
    return result^


def decode_field(data: List[Int], offset: Int) -> List[Int]:
    """Decode one field from data at offset.

    Returns [field_number, wire_type, value, bytes_consumed].
    """
    var result = List[Int]()
    # Out-of-range offset: return the all-zero field sentinel.
    if offset < 0 or offset >= len(data):
        result.append(0)
        result.append(0)
        result.append(0)
        result.append(0)
        return result^
    # Decode tag
    var tag_result = decode_varint(data, offset)
    var tag = tag_result[0]
    var tag_bytes = tag_result[1]
    var field_number = tag >> 3
    var wire_type = tag & 0x07

    # Decode value (assuming varint wire type 0)
    var val_result = decode_varint(data, offset + tag_bytes)
    var value = val_result[0]
    var val_bytes = val_result[1]

    result.append(field_number)
    result.append(wire_type)
    result.append(value)
    result.append(tag_bytes + val_bytes)
    return result^


# ── String field encoding ────────────────────────────────────────────────────


def encode_string_field(field_number: Int, text: String) -> List[Int]:
    """Encode string field: tag (wire_type=2) + length + bytes."""
    var tag = (field_number << 3) | 2  # wire_type 2 = length-delimited
    var result = encode_varint(tag)
    var text_bytes = text.as_bytes()
    var length = text.byte_length()
    var len_enc = encode_varint(length)
    for i in range(len(len_enc)):
        result.append(len_enc[i])
    for i in range(length):
        result.append(Int(text_bytes[i]))
    return result^


def decode_string_field(data: List[Int], offset: Int) -> List[Int]:
    """Decode string field from data at offset.

    Returns [field_number, string_start_offset, string_length, total_consumed].
    """
    var result = List[Int]()
    # Out-of-range offset: return the all-zero field sentinel.
    if offset < 0 or offset >= len(data):
        result.append(0)
        result.append(0)
        result.append(0)
        result.append(0)
        return result^
    # Decode tag
    var tag_result = decode_varint(data, offset)
    var tag = tag_result[0]
    var tag_bytes = tag_result[1]
    var field_number = tag >> 3

    # Decode length
    var len_result = decode_varint(data, offset + tag_bytes)
    var str_len = len_result[0]
    var len_bytes = len_result[1]

    var str_start = offset + tag_bytes + len_bytes
    var total = tag_bytes + len_bytes + str_len

    result.append(field_number)
    result.append(str_start)
    result.append(str_len)
    result.append(total)
    return result^


# ── Message encoding ─────────────────────────────────────────────────────────


def encode_message(fields: List[List[Int]]) -> List[Int]:
    """Encode multiple [field_number, value] pairs as varint fields.

    Each entry in fields is [field_number, value]. Wire type is always 0 (varint).
    """
    var result = List[Int]()
    for i in range(len(fields)):
        if len(fields[i]) >= 2:
            var encoded = encode_field(fields[i][0], 0, fields[i][1])
            for j in range(len(encoded)):
                result.append(encoded[j])
    return result^


def decode_message(data: List[Int]) -> List[List[Int]]:
    """Decode all fields from message bytes.

    Returns list of [field_number, wire_type, value] triples.
    """
    var result = List[List[Int]]()
    var pos: Int = 0
    while pos < len(data):
        var field_result = decode_field(data, pos)
        var entry = List[Int]()
        entry.append(field_result[0])  # field_number
        entry.append(field_result[1])  # wire_type
        entry.append(field_result[2])  # value
        result.append(entry^)
        pos += field_result[3]  # advance by bytes consumed
    return result^
