"""bench_checksum.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from checksum import adler32, fletcher16, luhn_check, luhn_checksum, isbn10_check, isbn13_check, xor_checksum, modular_sum, parity_bit, internet_checksum, verhoeff_check
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

    var _acc_adler32: Float64 = 0.0
    var _t0_adler32 = perf_counter_ns()
    for _ in range(N):
        _acc_adler32 += Float64(adler32(_li5))
    var _t1_adler32 = perf_counter_ns()
    var _ns_adler32 = Float64(_t1_adler32 - _t0_adler32) / Float64(N)
    print("MOJO_TIMING checksum::adler32", _ns_adler32, _acc_adler32)
    var _acc_fletcher16: Float64 = 0.0
    var _t0_fletcher16 = perf_counter_ns()
    for _ in range(N):
        _acc_fletcher16 += Float64(fletcher16(_li5))
    var _t1_fletcher16 = perf_counter_ns()
    var _ns_fletcher16 = Float64(_t1_fletcher16 - _t0_fletcher16) / Float64(N)
    print("MOJO_TIMING checksum::fletcher16", _ns_fletcher16, _acc_fletcher16)
    var _acc_luhn_check: Float64 = 0.0
    var _t0_luhn_check = perf_counter_ns()
    for _ in range(N):
        _acc_luhn_check += Float64(luhn_check(_li5))
    var _t1_luhn_check = perf_counter_ns()
    var _ns_luhn_check = Float64(_t1_luhn_check - _t0_luhn_check) / Float64(N)
    print("MOJO_TIMING checksum::luhn_check", _ns_luhn_check, _acc_luhn_check)
    var _acc_luhn_checksum: Float64 = 0.0
    var _t0_luhn_checksum = perf_counter_ns()
    for _ in range(N):
        _acc_luhn_checksum += Float64(luhn_checksum(_li5))
    var _t1_luhn_checksum = perf_counter_ns()
    var _ns_luhn_checksum = Float64(_t1_luhn_checksum - _t0_luhn_checksum) / Float64(N)
    print("MOJO_TIMING checksum::luhn_checksum", _ns_luhn_checksum, _acc_luhn_checksum)
    var _acc_isbn10_check: Float64 = 0.0
    var _t0_isbn10_check = perf_counter_ns()
    for _ in range(N):
        _acc_isbn10_check += Float64(isbn10_check(_li5))
    var _t1_isbn10_check = perf_counter_ns()
    var _ns_isbn10_check = Float64(_t1_isbn10_check - _t0_isbn10_check) / Float64(N)
    print("MOJO_TIMING checksum::isbn10_check", _ns_isbn10_check, _acc_isbn10_check)
    var _acc_isbn13_check: Float64 = 0.0
    var _t0_isbn13_check = perf_counter_ns()
    for _ in range(N):
        _acc_isbn13_check += Float64(isbn13_check(_li5))
    var _t1_isbn13_check = perf_counter_ns()
    var _ns_isbn13_check = Float64(_t1_isbn13_check - _t0_isbn13_check) / Float64(N)
    print("MOJO_TIMING checksum::isbn13_check", _ns_isbn13_check, _acc_isbn13_check)
    var _acc_xor_checksum: Float64 = 0.0
    var _t0_xor_checksum = perf_counter_ns()
    for _ in range(N):
        _acc_xor_checksum += Float64(xor_checksum(_li5))
    var _t1_xor_checksum = perf_counter_ns()
    var _ns_xor_checksum = Float64(_t1_xor_checksum - _t0_xor_checksum) / Float64(N)
    print("MOJO_TIMING checksum::xor_checksum", _ns_xor_checksum, _acc_xor_checksum)
    var _acc_modular_sum: Float64 = 0.0
    var _t0_modular_sum = perf_counter_ns()
    for _ in range(N):
        _acc_modular_sum += Float64(modular_sum(_li5, 5))
    var _t1_modular_sum = perf_counter_ns()
    var _ns_modular_sum = Float64(_t1_modular_sum - _t0_modular_sum) / Float64(N)
    print("MOJO_TIMING checksum::modular_sum", _ns_modular_sum, _acc_modular_sum)
    var _acc_parity_bit: Float64 = 0.0
    var _t0_parity_bit = perf_counter_ns()
    for _ in range(N):
        _acc_parity_bit += Float64(parity_bit(_li5))
    var _t1_parity_bit = perf_counter_ns()
    var _ns_parity_bit = Float64(_t1_parity_bit - _t0_parity_bit) / Float64(N)
    print("MOJO_TIMING checksum::parity_bit", _ns_parity_bit, _acc_parity_bit)
    var _acc_internet_checksum: Float64 = 0.0
    var _t0_internet_checksum = perf_counter_ns()
    for _ in range(N):
        _acc_internet_checksum += Float64(internet_checksum(_li5))
    var _t1_internet_checksum = perf_counter_ns()
    var _ns_internet_checksum = Float64(_t1_internet_checksum - _t0_internet_checksum) / Float64(N)
    print("MOJO_TIMING checksum::internet_checksum", _ns_internet_checksum, _acc_internet_checksum)
    var _acc_verhoeff_check: Float64 = 0.0
    var _t0_verhoeff_check = perf_counter_ns()
    for _ in range(N):
        _acc_verhoeff_check += Float64(verhoeff_check(_li5))
    var _t1_verhoeff_check = perf_counter_ns()
    var _ns_verhoeff_check = Float64(_t1_verhoeff_check - _t0_verhoeff_check) / Float64(N)
    print("MOJO_TIMING checksum::verhoeff_check", _ns_verhoeff_check, _acc_verhoeff_check)
