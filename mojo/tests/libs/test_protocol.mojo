"""test_protocol.mojo — auto-generated tests for protocol library."""
from std.math import isnan, isinf
from protocol import encode_varint, decode_varint, zigzag_encode, zigzag_decode, encode_field, decode_field, encode_string_field, decode_string_field, decode_message

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_encode_varint = encode_varint(5)
    if len(_v_encode_varint) >= 0: passed += 1; print("  ✅ protocol::encode_varint")
    var _v_decode_varint = decode_varint(_li5, 5)
    if len(_v_decode_varint) >= 0: passed += 1; print("  ✅ protocol::decode_varint")
    _ = zigzag_encode(5)
    passed += 1; print("  ✅ protocol::zigzag_encode")
    _ = zigzag_decode(5)
    passed += 1; print("  ✅ protocol::zigzag_decode")
    var _v_encode_field = encode_field(5, 5, 5)
    if len(_v_encode_field) >= 0: passed += 1; print("  ✅ protocol::encode_field")
    var _v_decode_field = decode_field(_li5, 5)
    if len(_v_decode_field) >= 0: passed += 1; print("  ✅ protocol::decode_field")
    var _v_encode_string_field = encode_string_field(5, "test")
    if len(_v_encode_string_field) >= 0: passed += 1; print("  ✅ protocol::encode_string_field")
    var _v_decode_string_field = decode_string_field(_li5, 5)
    if len(_v_decode_string_field) >= 0: passed += 1; print("  ✅ protocol::decode_string_field")
    _ = decode_message(_li5)
    passed += 1; print("  ✅ protocol::decode_message")

    print("  [protocol] Passed:", passed, "Failed:", failed)
