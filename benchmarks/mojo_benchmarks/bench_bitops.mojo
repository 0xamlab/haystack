"""bench_bitops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from bitops import popcount, leading_zeros, trailing_zeros, next_power_of_2, is_power_of_2, reverse_bits, rotate_left, rotate_right, bit_set, bit_clear, bit_test, bit_toggle, fnv1a_hash
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_popcount: Float64 = 0.0
    var _t0_popcount = perf_counter_ns()
    for _ in range(N):
        _acc_popcount += Float64(popcount(5))
    var _t1_popcount = perf_counter_ns()
    var _ns_popcount = Float64(_t1_popcount - _t0_popcount) / Float64(N)
    print("MOJO_TIMING bitops::popcount", _ns_popcount, _acc_popcount)
    var _result_popcount = popcount(5)
    var _summary_popcount = _summary_int(_result_popcount)
    print("MOJO_RESULT bitops::popcount", _summary_popcount)
    var _acc_leading_zeros: Float64 = 0.0
    var _t0_leading_zeros = perf_counter_ns()
    for _ in range(N):
        _acc_leading_zeros += Float64(leading_zeros(5))
    var _t1_leading_zeros = perf_counter_ns()
    var _ns_leading_zeros = Float64(_t1_leading_zeros - _t0_leading_zeros) / Float64(N)
    print("MOJO_TIMING bitops::leading_zeros", _ns_leading_zeros, _acc_leading_zeros)
    var _result_leading_zeros = leading_zeros(5)
    var _summary_leading_zeros = _summary_int(_result_leading_zeros)
    print("MOJO_RESULT bitops::leading_zeros", _summary_leading_zeros)
    var _acc_trailing_zeros: Float64 = 0.0
    var _t0_trailing_zeros = perf_counter_ns()
    for _ in range(N):
        _acc_trailing_zeros += Float64(trailing_zeros(5))
    var _t1_trailing_zeros = perf_counter_ns()
    var _ns_trailing_zeros = Float64(_t1_trailing_zeros - _t0_trailing_zeros) / Float64(N)
    print("MOJO_TIMING bitops::trailing_zeros", _ns_trailing_zeros, _acc_trailing_zeros)
    var _result_trailing_zeros = trailing_zeros(5)
    var _summary_trailing_zeros = _summary_int(_result_trailing_zeros)
    print("MOJO_RESULT bitops::trailing_zeros", _summary_trailing_zeros)
    var _acc_next_power_of_2: Float64 = 0.0
    var _t0_next_power_of_2 = perf_counter_ns()
    for _ in range(N):
        _acc_next_power_of_2 += Float64(next_power_of_2(5))
    var _t1_next_power_of_2 = perf_counter_ns()
    var _ns_next_power_of_2 = Float64(_t1_next_power_of_2 - _t0_next_power_of_2) / Float64(N)
    print("MOJO_TIMING bitops::next_power_of_2", _ns_next_power_of_2, _acc_next_power_of_2)
    var _result_next_power_of_2 = next_power_of_2(5)
    var _summary_next_power_of_2 = _summary_int(_result_next_power_of_2)
    print("MOJO_RESULT bitops::next_power_of_2", _summary_next_power_of_2)
    var _acc_is_power_of_2: Float64 = 0.0
    var _t0_is_power_of_2 = perf_counter_ns()
    for _ in range(N):
        _acc_is_power_of_2 += Float64(is_power_of_2(5))
    var _t1_is_power_of_2 = perf_counter_ns()
    var _ns_is_power_of_2 = Float64(_t1_is_power_of_2 - _t0_is_power_of_2) / Float64(N)
    print("MOJO_TIMING bitops::is_power_of_2", _ns_is_power_of_2, _acc_is_power_of_2)
    var _result_is_power_of_2 = is_power_of_2(5)
    var _summary_is_power_of_2 = _summary_bool(_result_is_power_of_2)
    print("MOJO_RESULT bitops::is_power_of_2", _summary_is_power_of_2)
    var _acc_reverse_bits: Float64 = 0.0
    var _t0_reverse_bits = perf_counter_ns()
    for _ in range(N):
        _acc_reverse_bits += Float64(reverse_bits(1))
    var _t1_reverse_bits = perf_counter_ns()
    var _ns_reverse_bits = Float64(_t1_reverse_bits - _t0_reverse_bits) / Float64(N)
    print("MOJO_TIMING bitops::reverse_bits", _ns_reverse_bits, _acc_reverse_bits)
    var _result_reverse_bits = reverse_bits(1)
    var _summary_reverse_bits = _summary_uint32(_result_reverse_bits)
    print("MOJO_RESULT bitops::reverse_bits", _summary_reverse_bits)
    var _acc_rotate_left: Float64 = 0.0
    var _t0_rotate_left = perf_counter_ns()
    for _ in range(N):
        _acc_rotate_left += Float64(rotate_left(1, 5))
    var _t1_rotate_left = perf_counter_ns()
    var _ns_rotate_left = Float64(_t1_rotate_left - _t0_rotate_left) / Float64(N)
    print("MOJO_TIMING bitops::rotate_left", _ns_rotate_left, _acc_rotate_left)
    var _result_rotate_left = rotate_left(1, 5)
    var _summary_rotate_left = _summary_uint32(_result_rotate_left)
    print("MOJO_RESULT bitops::rotate_left", _summary_rotate_left)
    var _acc_rotate_right: Float64 = 0.0
    var _t0_rotate_right = perf_counter_ns()
    for _ in range(N):
        _acc_rotate_right += Float64(rotate_right(1, 5))
    var _t1_rotate_right = perf_counter_ns()
    var _ns_rotate_right = Float64(_t1_rotate_right - _t0_rotate_right) / Float64(N)
    print("MOJO_TIMING bitops::rotate_right", _ns_rotate_right, _acc_rotate_right)
    var _result_rotate_right = rotate_right(1, 5)
    var _summary_rotate_right = _summary_uint32(_result_rotate_right)
    print("MOJO_RESULT bitops::rotate_right", _summary_rotate_right)
    var _acc_bit_set: Float64 = 0.0
    var _t0_bit_set = perf_counter_ns()
    for _ in range(N):
        _acc_bit_set += Float64(bit_set(5, 5))
    var _t1_bit_set = perf_counter_ns()
    var _ns_bit_set = Float64(_t1_bit_set - _t0_bit_set) / Float64(N)
    print("MOJO_TIMING bitops::bit_set", _ns_bit_set, _acc_bit_set)
    var _result_bit_set = bit_set(5, 5)
    var _summary_bit_set = _summary_int(_result_bit_set)
    print("MOJO_RESULT bitops::bit_set", _summary_bit_set)
    var _acc_bit_clear: Float64 = 0.0
    var _t0_bit_clear = perf_counter_ns()
    for _ in range(N):
        _acc_bit_clear += Float64(bit_clear(5, 5))
    var _t1_bit_clear = perf_counter_ns()
    var _ns_bit_clear = Float64(_t1_bit_clear - _t0_bit_clear) / Float64(N)
    print("MOJO_TIMING bitops::bit_clear", _ns_bit_clear, _acc_bit_clear)
    var _result_bit_clear = bit_clear(5, 5)
    var _summary_bit_clear = _summary_int(_result_bit_clear)
    print("MOJO_RESULT bitops::bit_clear", _summary_bit_clear)
    var _acc_bit_test: Float64 = 0.0
    var _t0_bit_test = perf_counter_ns()
    for _ in range(N):
        _acc_bit_test += Float64(bit_test(5, 5))
    var _t1_bit_test = perf_counter_ns()
    var _ns_bit_test = Float64(_t1_bit_test - _t0_bit_test) / Float64(N)
    print("MOJO_TIMING bitops::bit_test", _ns_bit_test, _acc_bit_test)
    var _result_bit_test = bit_test(5, 5)
    var _summary_bit_test = _summary_bool(_result_bit_test)
    print("MOJO_RESULT bitops::bit_test", _summary_bit_test)
    var _acc_bit_toggle: Float64 = 0.0
    var _t0_bit_toggle = perf_counter_ns()
    for _ in range(N):
        _acc_bit_toggle += Float64(bit_toggle(5, 5))
    var _t1_bit_toggle = perf_counter_ns()
    var _ns_bit_toggle = Float64(_t1_bit_toggle - _t0_bit_toggle) / Float64(N)
    print("MOJO_TIMING bitops::bit_toggle", _ns_bit_toggle, _acc_bit_toggle)
    var _result_bit_toggle = bit_toggle(5, 5)
    var _summary_bit_toggle = _summary_int(_result_bit_toggle)
    print("MOJO_RESULT bitops::bit_toggle", _summary_bit_toggle)
    var _acc_fnv1a_hash: Float64 = 0.0
    var _t0_fnv1a_hash = perf_counter_ns()
    for _ in range(N):
        _acc_fnv1a_hash += Float64(fnv1a_hash("test"))
    var _t1_fnv1a_hash = perf_counter_ns()
    var _ns_fnv1a_hash = Float64(_t1_fnv1a_hash - _t0_fnv1a_hash) / Float64(N)
    print("MOJO_TIMING bitops::fnv1a_hash", _ns_fnv1a_hash, _acc_fnv1a_hash)
    var _result_fnv1a_hash = fnv1a_hash("test")
    var _summary_fnv1a_hash = _summary_int(_result_fnv1a_hash)
    print("MOJO_RESULT bitops::fnv1a_hash", _summary_fnv1a_hash)
