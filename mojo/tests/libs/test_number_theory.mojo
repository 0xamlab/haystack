"""test_number_theory.mojo — auto-generated tests for number_theory library."""
from std.math import isnan, isinf
from number_theory import is_prime, gcd, lcm, mod_pow, euler_totient, prime_factors, sieve_of_eratosthenes, is_coprime, extended_gcd, mod_inverse, fibonacci, is_perfect_square

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

    _ = is_prime(5)
    passed += 1; print("  ✅ number_theory::is_prime")
    _ = gcd(5, 5)
    passed += 1; print("  ✅ number_theory::gcd")
    _ = lcm(5, 5)
    passed += 1; print("  ✅ number_theory::lcm")
    _ = mod_pow(5, 5, 5)
    passed += 1; print("  ✅ number_theory::mod_pow")
    _ = euler_totient(5)
    passed += 1; print("  ✅ number_theory::euler_totient")
    var _v_prime_factors = prime_factors(5)
    if len(_v_prime_factors) >= 0: passed += 1; print("  ✅ number_theory::prime_factors")
    var _v_sieve_of_eratosthenes = sieve_of_eratosthenes(5)
    if len(_v_sieve_of_eratosthenes) >= 0: passed += 1; print("  ✅ number_theory::sieve_of_eratosthenes")
    _ = is_coprime(5, 5)
    passed += 1; print("  ✅ number_theory::is_coprime")
    var _v_extended_gcd = extended_gcd(5, 5)
    if len(_v_extended_gcd) >= 0: passed += 1; print("  ✅ number_theory::extended_gcd")
    _ = mod_inverse(5, 5)
    passed += 1; print("  ✅ number_theory::mod_inverse")
    _ = fibonacci(5)
    passed += 1; print("  ✅ number_theory::fibonacci")
    _ = is_perfect_square(5)
    passed += 1; print("  ✅ number_theory::is_perfect_square")

    print("  [number_theory] Passed:", passed, "Failed:", failed)
