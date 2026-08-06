"""bench_checksum.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from checksum import adler32, fletcher16, luhn_check, luhn_checksum, isbn10_check, isbn13_check, xor_checksum, modular_sum, parity_bit, internet_checksum, verhoeff_check
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_adler32: Float64 = 0.0
    var _t0_adler32 = perf_counter_ns()
    for _ in range(N):
        _acc_adler32 += Float64(adler32(_li5))
    var _t1_adler32 = perf_counter_ns()
    var _ns_adler32 = Float64(_t1_adler32 - _t0_adler32) / Float64(N)
    print("MOJO_TIMING checksum::adler32", _ns_adler32, _acc_adler32)
    var _result_adler32 = adler32(_li5)
    var _summary_adler32 = _summary_int(_result_adler32)
    print("MOJO_RESULT checksum::adler32", _summary_adler32)
    var _acc_fletcher16: Float64 = 0.0
    var _t0_fletcher16 = perf_counter_ns()
    for _ in range(N):
        _acc_fletcher16 += Float64(fletcher16(_li5))
    var _t1_fletcher16 = perf_counter_ns()
    var _ns_fletcher16 = Float64(_t1_fletcher16 - _t0_fletcher16) / Float64(N)
    print("MOJO_TIMING checksum::fletcher16", _ns_fletcher16, _acc_fletcher16)
    var _result_fletcher16 = fletcher16(_li5)
    var _summary_fletcher16 = _summary_int(_result_fletcher16)
    print("MOJO_RESULT checksum::fletcher16", _summary_fletcher16)
    var _acc_luhn_check: Float64 = 0.0
    var _t0_luhn_check = perf_counter_ns()
    for _ in range(N):
        _acc_luhn_check += Float64(luhn_check(_li5))
    var _t1_luhn_check = perf_counter_ns()
    var _ns_luhn_check = Float64(_t1_luhn_check - _t0_luhn_check) / Float64(N)
    print("MOJO_TIMING checksum::luhn_check", _ns_luhn_check, _acc_luhn_check)
    var _result_luhn_check = luhn_check(_li5)
    var _summary_luhn_check = _summary_bool(_result_luhn_check)
    print("MOJO_RESULT checksum::luhn_check", _summary_luhn_check)
    var _acc_luhn_checksum: Float64 = 0.0
    var _t0_luhn_checksum = perf_counter_ns()
    for _ in range(N):
        _acc_luhn_checksum += Float64(luhn_checksum(_li5))
    var _t1_luhn_checksum = perf_counter_ns()
    var _ns_luhn_checksum = Float64(_t1_luhn_checksum - _t0_luhn_checksum) / Float64(N)
    print("MOJO_TIMING checksum::luhn_checksum", _ns_luhn_checksum, _acc_luhn_checksum)
    var _result_luhn_checksum = luhn_checksum(_li5)
    var _summary_luhn_checksum = _summary_int(_result_luhn_checksum)
    print("MOJO_RESULT checksum::luhn_checksum", _summary_luhn_checksum)
    var _acc_isbn10_check: Float64 = 0.0
    var _t0_isbn10_check = perf_counter_ns()
    for _ in range(N):
        _acc_isbn10_check += Float64(isbn10_check(_li5))
    var _t1_isbn10_check = perf_counter_ns()
    var _ns_isbn10_check = Float64(_t1_isbn10_check - _t0_isbn10_check) / Float64(N)
    print("MOJO_TIMING checksum::isbn10_check", _ns_isbn10_check, _acc_isbn10_check)
    var _result_isbn10_check = isbn10_check(_li5)
    var _summary_isbn10_check = _summary_bool(_result_isbn10_check)
    print("MOJO_RESULT checksum::isbn10_check", _summary_isbn10_check)
    var _acc_isbn13_check: Float64 = 0.0
    var _t0_isbn13_check = perf_counter_ns()
    for _ in range(N):
        _acc_isbn13_check += Float64(isbn13_check(_li5))
    var _t1_isbn13_check = perf_counter_ns()
    var _ns_isbn13_check = Float64(_t1_isbn13_check - _t0_isbn13_check) / Float64(N)
    print("MOJO_TIMING checksum::isbn13_check", _ns_isbn13_check, _acc_isbn13_check)
    var _result_isbn13_check = isbn13_check(_li5)
    var _summary_isbn13_check = _summary_bool(_result_isbn13_check)
    print("MOJO_RESULT checksum::isbn13_check", _summary_isbn13_check)
    var _acc_xor_checksum: Float64 = 0.0
    var _t0_xor_checksum = perf_counter_ns()
    for _ in range(N):
        _acc_xor_checksum += Float64(xor_checksum(_li5))
    var _t1_xor_checksum = perf_counter_ns()
    var _ns_xor_checksum = Float64(_t1_xor_checksum - _t0_xor_checksum) / Float64(N)
    print("MOJO_TIMING checksum::xor_checksum", _ns_xor_checksum, _acc_xor_checksum)
    var _result_xor_checksum = xor_checksum(_li5)
    var _summary_xor_checksum = _summary_int(_result_xor_checksum)
    print("MOJO_RESULT checksum::xor_checksum", _summary_xor_checksum)
    var _acc_modular_sum: Float64 = 0.0
    var _t0_modular_sum = perf_counter_ns()
    for _ in range(N):
        _acc_modular_sum += Float64(modular_sum(_li5, 5))
    var _t1_modular_sum = perf_counter_ns()
    var _ns_modular_sum = Float64(_t1_modular_sum - _t0_modular_sum) / Float64(N)
    print("MOJO_TIMING checksum::modular_sum", _ns_modular_sum, _acc_modular_sum)
    var _result_modular_sum = modular_sum(_li5, 5)
    var _summary_modular_sum = _summary_int(_result_modular_sum)
    print("MOJO_RESULT checksum::modular_sum", _summary_modular_sum)
    var _acc_parity_bit: Float64 = 0.0
    var _t0_parity_bit = perf_counter_ns()
    for _ in range(N):
        _acc_parity_bit += Float64(parity_bit(_li5))
    var _t1_parity_bit = perf_counter_ns()
    var _ns_parity_bit = Float64(_t1_parity_bit - _t0_parity_bit) / Float64(N)
    print("MOJO_TIMING checksum::parity_bit", _ns_parity_bit, _acc_parity_bit)
    var _result_parity_bit = parity_bit(_li5)
    var _summary_parity_bit = _summary_int(_result_parity_bit)
    print("MOJO_RESULT checksum::parity_bit", _summary_parity_bit)
    var _acc_internet_checksum: Float64 = 0.0
    var _t0_internet_checksum = perf_counter_ns()
    for _ in range(N):
        _acc_internet_checksum += Float64(internet_checksum(_li5))
    var _t1_internet_checksum = perf_counter_ns()
    var _ns_internet_checksum = Float64(_t1_internet_checksum - _t0_internet_checksum) / Float64(N)
    print("MOJO_TIMING checksum::internet_checksum", _ns_internet_checksum, _acc_internet_checksum)
    var _result_internet_checksum = internet_checksum(_li5)
    var _summary_internet_checksum = _summary_int(_result_internet_checksum)
    print("MOJO_RESULT checksum::internet_checksum", _summary_internet_checksum)
    var _acc_verhoeff_check: Float64 = 0.0
    var _t0_verhoeff_check = perf_counter_ns()
    for _ in range(N):
        _acc_verhoeff_check += Float64(verhoeff_check(_li5))
    var _t1_verhoeff_check = perf_counter_ns()
    var _ns_verhoeff_check = Float64(_t1_verhoeff_check - _t0_verhoeff_check) / Float64(N)
    print("MOJO_TIMING checksum::verhoeff_check", _ns_verhoeff_check, _acc_verhoeff_check)
    var _result_verhoeff_check = verhoeff_check(_li5)
    var _summary_verhoeff_check = _summary_bool(_result_verhoeff_check)
    print("MOJO_RESULT checksum::verhoeff_check", _summary_verhoeff_check)
