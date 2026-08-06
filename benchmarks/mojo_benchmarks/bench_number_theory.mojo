"""bench_number_theory.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from number_theory import is_prime, gcd, lcm, mod_pow, euler_totient, prime_factors, sieve_of_eratosthenes, is_coprime, extended_gcd, mod_inverse, fibonacci, is_perfect_square
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

    var _acc_is_prime: Float64 = 0.0
    var _t0_is_prime = perf_counter_ns()
    for _ in range(N):
        _acc_is_prime += Float64(is_prime(5))
    var _t1_is_prime = perf_counter_ns()
    var _ns_is_prime = Float64(_t1_is_prime - _t0_is_prime) / Float64(N)
    print("MOJO_TIMING number_theory::is_prime", _ns_is_prime, _acc_is_prime)
    var _result_is_prime = is_prime(5)
    var _summary_is_prime = _summary_bool(_result_is_prime)
    print("MOJO_RESULT number_theory::is_prime", _summary_is_prime)
    var _acc_gcd: Float64 = 0.0
    var _t0_gcd = perf_counter_ns()
    for _ in range(N):
        _acc_gcd += Float64(gcd(5, 5))
    var _t1_gcd = perf_counter_ns()
    var _ns_gcd = Float64(_t1_gcd - _t0_gcd) / Float64(N)
    print("MOJO_TIMING number_theory::gcd", _ns_gcd, _acc_gcd)
    var _result_gcd = gcd(5, 5)
    var _summary_gcd = _summary_int(_result_gcd)
    print("MOJO_RESULT number_theory::gcd", _summary_gcd)
    var _acc_lcm: Float64 = 0.0
    var _t0_lcm = perf_counter_ns()
    for _ in range(N):
        _acc_lcm += Float64(lcm(5, 5))
    var _t1_lcm = perf_counter_ns()
    var _ns_lcm = Float64(_t1_lcm - _t0_lcm) / Float64(N)
    print("MOJO_TIMING number_theory::lcm", _ns_lcm, _acc_lcm)
    var _result_lcm = lcm(5, 5)
    var _summary_lcm = _summary_int(_result_lcm)
    print("MOJO_RESULT number_theory::lcm", _summary_lcm)
    var _acc_mod_pow: Float64 = 0.0
    var _t0_mod_pow = perf_counter_ns()
    for _ in range(N):
        _acc_mod_pow += Float64(mod_pow(5, 5, 5))
    var _t1_mod_pow = perf_counter_ns()
    var _ns_mod_pow = Float64(_t1_mod_pow - _t0_mod_pow) / Float64(N)
    print("MOJO_TIMING number_theory::mod_pow", _ns_mod_pow, _acc_mod_pow)
    var _result_mod_pow = mod_pow(5, 5, 5)
    var _summary_mod_pow = _summary_int(_result_mod_pow)
    print("MOJO_RESULT number_theory::mod_pow", _summary_mod_pow)
    var _acc_euler_totient: Float64 = 0.0
    var _t0_euler_totient = perf_counter_ns()
    for _ in range(N):
        _acc_euler_totient += Float64(euler_totient(5))
    var _t1_euler_totient = perf_counter_ns()
    var _ns_euler_totient = Float64(_t1_euler_totient - _t0_euler_totient) / Float64(N)
    print("MOJO_TIMING number_theory::euler_totient", _ns_euler_totient, _acc_euler_totient)
    var _result_euler_totient = euler_totient(5)
    var _summary_euler_totient = _summary_int(_result_euler_totient)
    print("MOJO_RESULT number_theory::euler_totient", _summary_euler_totient)
    var _acc_prime_factors: Float64 = 0.0
    var _t0_prime_factors = perf_counter_ns()
    for _ in range(N):
        var _r_prime_factors = prime_factors(5)
        _acc_prime_factors += Float64(len(_r_prime_factors))
    var _t1_prime_factors = perf_counter_ns()
    var _ns_prime_factors = Float64(_t1_prime_factors - _t0_prime_factors) / Float64(N)
    print("MOJO_TIMING number_theory::prime_factors", _ns_prime_factors, _acc_prime_factors)
    var _result_prime_factors = prime_factors(5)
    var _summary_prime_factors = _summary_list_int(_result_prime_factors)
    print("MOJO_RESULT number_theory::prime_factors", _summary_prime_factors)
    var _acc_sieve_of_eratosthenes: Float64 = 0.0
    var _t0_sieve_of_eratosthenes = perf_counter_ns()
    for _ in range(N):
        var _r_sieve_of_eratosthenes = sieve_of_eratosthenes(5)
        _acc_sieve_of_eratosthenes += Float64(len(_r_sieve_of_eratosthenes))
    var _t1_sieve_of_eratosthenes = perf_counter_ns()
    var _ns_sieve_of_eratosthenes = Float64(_t1_sieve_of_eratosthenes - _t0_sieve_of_eratosthenes) / Float64(N)
    print("MOJO_TIMING number_theory::sieve_of_eratosthenes", _ns_sieve_of_eratosthenes, _acc_sieve_of_eratosthenes)
    var _result_sieve_of_eratosthenes = sieve_of_eratosthenes(5)
    var _summary_sieve_of_eratosthenes = _summary_list_int(_result_sieve_of_eratosthenes)
    print("MOJO_RESULT number_theory::sieve_of_eratosthenes", _summary_sieve_of_eratosthenes)
    var _acc_is_coprime: Float64 = 0.0
    var _t0_is_coprime = perf_counter_ns()
    for _ in range(N):
        _acc_is_coprime += Float64(is_coprime(5, 5))
    var _t1_is_coprime = perf_counter_ns()
    var _ns_is_coprime = Float64(_t1_is_coprime - _t0_is_coprime) / Float64(N)
    print("MOJO_TIMING number_theory::is_coprime", _ns_is_coprime, _acc_is_coprime)
    var _result_is_coprime = is_coprime(5, 5)
    var _summary_is_coprime = _summary_bool(_result_is_coprime)
    print("MOJO_RESULT number_theory::is_coprime", _summary_is_coprime)
    var _acc_extended_gcd: Float64 = 0.0
    var _t0_extended_gcd = perf_counter_ns()
    for _ in range(N):
        var _r_extended_gcd = extended_gcd(5, 5)
        _acc_extended_gcd += Float64(len(_r_extended_gcd))
    var _t1_extended_gcd = perf_counter_ns()
    var _ns_extended_gcd = Float64(_t1_extended_gcd - _t0_extended_gcd) / Float64(N)
    print("MOJO_TIMING number_theory::extended_gcd", _ns_extended_gcd, _acc_extended_gcd)
    var _result_extended_gcd = extended_gcd(5, 5)
    var _summary_extended_gcd = _summary_list_int(_result_extended_gcd)
    print("MOJO_RESULT number_theory::extended_gcd", _summary_extended_gcd)
    var _acc_mod_inverse: Float64 = 0.0
    var _t0_mod_inverse = perf_counter_ns()
    for _ in range(N):
        _acc_mod_inverse += Float64(mod_inverse(5, 5))
    var _t1_mod_inverse = perf_counter_ns()
    var _ns_mod_inverse = Float64(_t1_mod_inverse - _t0_mod_inverse) / Float64(N)
    print("MOJO_TIMING number_theory::mod_inverse", _ns_mod_inverse, _acc_mod_inverse)
    var _result_mod_inverse = mod_inverse(5, 5)
    var _summary_mod_inverse = _summary_int(_result_mod_inverse)
    print("MOJO_RESULT number_theory::mod_inverse", _summary_mod_inverse)
    var _acc_fibonacci: Float64 = 0.0
    var _t0_fibonacci = perf_counter_ns()
    for _ in range(N):
        _acc_fibonacci += Float64(fibonacci(5))
    var _t1_fibonacci = perf_counter_ns()
    var _ns_fibonacci = Float64(_t1_fibonacci - _t0_fibonacci) / Float64(N)
    print("MOJO_TIMING number_theory::fibonacci", _ns_fibonacci, _acc_fibonacci)
    var _result_fibonacci = fibonacci(5)
    var _summary_fibonacci = _summary_int(_result_fibonacci)
    print("MOJO_RESULT number_theory::fibonacci", _summary_fibonacci)
    var _acc_is_perfect_square: Float64 = 0.0
    var _t0_is_perfect_square = perf_counter_ns()
    for _ in range(N):
        _acc_is_perfect_square += Float64(is_perfect_square(5))
    var _t1_is_perfect_square = perf_counter_ns()
    var _ns_is_perfect_square = Float64(_t1_is_perfect_square - _t0_is_perfect_square) / Float64(N)
    print("MOJO_TIMING number_theory::is_perfect_square", _ns_is_perfect_square, _acc_is_perfect_square)
    var _result_is_perfect_square = is_perfect_square(5)
    var _summary_is_perfect_square = _summary_bool(_result_is_perfect_square)
    print("MOJO_RESULT number_theory::is_perfect_square", _summary_is_perfect_square)
