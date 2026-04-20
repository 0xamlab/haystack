"""bench_bitops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from bitops import popcount, leading_zeros, trailing_zeros, next_power_of_2, is_power_of_2, reverse_bits, rotate_left, rotate_right, bit_set, bit_clear, bit_test, bit_toggle, fnv1a_hash
from std.time import perf_counter_ns

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
    var _acc_leading_zeros: Float64 = 0.0
    var _t0_leading_zeros = perf_counter_ns()
    for _ in range(N):
        _acc_leading_zeros += Float64(leading_zeros(5))
    var _t1_leading_zeros = perf_counter_ns()
    var _ns_leading_zeros = Float64(_t1_leading_zeros - _t0_leading_zeros) / Float64(N)
    print("MOJO_TIMING bitops::leading_zeros", _ns_leading_zeros, _acc_leading_zeros)
    var _acc_trailing_zeros: Float64 = 0.0
    var _t0_trailing_zeros = perf_counter_ns()
    for _ in range(N):
        _acc_trailing_zeros += Float64(trailing_zeros(5))
    var _t1_trailing_zeros = perf_counter_ns()
    var _ns_trailing_zeros = Float64(_t1_trailing_zeros - _t0_trailing_zeros) / Float64(N)
    print("MOJO_TIMING bitops::trailing_zeros", _ns_trailing_zeros, _acc_trailing_zeros)
    var _acc_next_power_of_2: Float64 = 0.0
    var _t0_next_power_of_2 = perf_counter_ns()
    for _ in range(N):
        _acc_next_power_of_2 += Float64(next_power_of_2(5))
    var _t1_next_power_of_2 = perf_counter_ns()
    var _ns_next_power_of_2 = Float64(_t1_next_power_of_2 - _t0_next_power_of_2) / Float64(N)
    print("MOJO_TIMING bitops::next_power_of_2", _ns_next_power_of_2, _acc_next_power_of_2)
    var _acc_is_power_of_2: Float64 = 0.0
    var _t0_is_power_of_2 = perf_counter_ns()
    for _ in range(N):
        _acc_is_power_of_2 += Float64(is_power_of_2(5))
    var _t1_is_power_of_2 = perf_counter_ns()
    var _ns_is_power_of_2 = Float64(_t1_is_power_of_2 - _t0_is_power_of_2) / Float64(N)
    print("MOJO_TIMING bitops::is_power_of_2", _ns_is_power_of_2, _acc_is_power_of_2)
    var _acc_reverse_bits: Float64 = 0.0
    var _t0_reverse_bits = perf_counter_ns()
    for _ in range(N):
        _acc_reverse_bits += Float64(reverse_bits(1))
    var _t1_reverse_bits = perf_counter_ns()
    var _ns_reverse_bits = Float64(_t1_reverse_bits - _t0_reverse_bits) / Float64(N)
    print("MOJO_TIMING bitops::reverse_bits", _ns_reverse_bits, _acc_reverse_bits)
    var _acc_rotate_left: Float64 = 0.0
    var _t0_rotate_left = perf_counter_ns()
    for _ in range(N):
        _acc_rotate_left += Float64(rotate_left(1, 5))
    var _t1_rotate_left = perf_counter_ns()
    var _ns_rotate_left = Float64(_t1_rotate_left - _t0_rotate_left) / Float64(N)
    print("MOJO_TIMING bitops::rotate_left", _ns_rotate_left, _acc_rotate_left)
    var _acc_rotate_right: Float64 = 0.0
    var _t0_rotate_right = perf_counter_ns()
    for _ in range(N):
        _acc_rotate_right += Float64(rotate_right(1, 5))
    var _t1_rotate_right = perf_counter_ns()
    var _ns_rotate_right = Float64(_t1_rotate_right - _t0_rotate_right) / Float64(N)
    print("MOJO_TIMING bitops::rotate_right", _ns_rotate_right, _acc_rotate_right)
    var _acc_bit_set: Float64 = 0.0
    var _t0_bit_set = perf_counter_ns()
    for _ in range(N):
        _acc_bit_set += Float64(bit_set(5, 5))
    var _t1_bit_set = perf_counter_ns()
    var _ns_bit_set = Float64(_t1_bit_set - _t0_bit_set) / Float64(N)
    print("MOJO_TIMING bitops::bit_set", _ns_bit_set, _acc_bit_set)
    var _acc_bit_clear: Float64 = 0.0
    var _t0_bit_clear = perf_counter_ns()
    for _ in range(N):
        _acc_bit_clear += Float64(bit_clear(5, 5))
    var _t1_bit_clear = perf_counter_ns()
    var _ns_bit_clear = Float64(_t1_bit_clear - _t0_bit_clear) / Float64(N)
    print("MOJO_TIMING bitops::bit_clear", _ns_bit_clear, _acc_bit_clear)
    var _acc_bit_test: Float64 = 0.0
    var _t0_bit_test = perf_counter_ns()
    for _ in range(N):
        _acc_bit_test += Float64(bit_test(5, 5))
    var _t1_bit_test = perf_counter_ns()
    var _ns_bit_test = Float64(_t1_bit_test - _t0_bit_test) / Float64(N)
    print("MOJO_TIMING bitops::bit_test", _ns_bit_test, _acc_bit_test)
    var _acc_bit_toggle: Float64 = 0.0
    var _t0_bit_toggle = perf_counter_ns()
    for _ in range(N):
        _acc_bit_toggle += Float64(bit_toggle(5, 5))
    var _t1_bit_toggle = perf_counter_ns()
    var _ns_bit_toggle = Float64(_t1_bit_toggle - _t0_bit_toggle) / Float64(N)
    print("MOJO_TIMING bitops::bit_toggle", _ns_bit_toggle, _acc_bit_toggle)
    var _acc_fnv1a_hash: Float64 = 0.0
    var _t0_fnv1a_hash = perf_counter_ns()
    for _ in range(N):
        _acc_fnv1a_hash += Float64(fnv1a_hash("test"))
    var _t1_fnv1a_hash = perf_counter_ns()
    var _ns_fnv1a_hash = Float64(_t1_fnv1a_hash - _t0_fnv1a_hash) / Float64(N)
    print("MOJO_TIMING bitops::fnv1a_hash", _ns_fnv1a_hash, _acc_fnv1a_hash)
