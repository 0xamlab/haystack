"""Tests for Wave 52 — Number Theory, Metaheuristic Optimization, Accounting."""

from number_theory import (
    is_prime,
    gcd,
    lcm,
    mod_pow,
    euler_totient,
    prime_factors,
    sieve_of_eratosthenes,
    is_coprime,
    extended_gcd,
    mod_inverse,
    fibonacci,
    is_perfect_square,
)
from optimization_meta import (
    eval_objective,
    simulated_annealing,
    particle_swarm,
    random_search,
    hill_climbing,
    acceptance_probability,
    neighbor,
)
from accounting import (
    straight_line_depreciation,
    declining_balance,
    sum_of_years_digits,
    future_value,
    present_value_single,
    gross_profit_margin,
    net_profit_margin,
    current_ratio,
    debt_to_equity,
    return_on_equity,
    break_even_units,
    compound_annual_growth,
)
from std.math import abs as fabs


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


# ── Number Theory Tests ─────────────────────────────────────────────────────


def test_is_prime() raises:
    print("  is_prime...")
    _assert(is_prime(2), "2 is prime")                          # 1
    _assert(is_prime(3), "3 is prime")                          # 2
    _assert(not is_prime(4), "4 is not prime")                  # 3
    _assert(not is_prime(1), "1 is not prime")                  # 4
    _assert(not is_prime(0), "0 is not prime")                  # 5
    _assert(is_prime(97), "97 is prime")                        # 6
    _assert(is_prime(7919), "7919 is prime")                    # 7
    _assert(not is_prime(100), "100 is not prime")              # 8
    _assert(is_prime(104729), "104729 is prime")                # 9


def test_gcd_lcm() raises:
    print("  gcd / lcm...")
    _assert(gcd(12, 8) == 4, "gcd(12,8)==4")                   # 10
    _assert(gcd(100, 75) == 25, "gcd(100,75)==25")              # 11
    _assert(gcd(17, 13) == 1, "gcd(17,13)==1")                  # 12
    _assert(lcm(4, 6) == 12, "lcm(4,6)==12")                   # 13
    _assert(lcm(3, 7) == 21, "lcm(3,7)==21")                   # 14
    _assert(lcm(0, 5) == 0, "lcm(0,5)==0")                     # 15


def test_mod_pow() raises:
    print("  mod_pow...")
    _assert(mod_pow(2, 10, 1000) == 24, "2^10 mod 1000 == 24")     # 16
    _assert(mod_pow(3, 13, 100) == 23, "3^13 mod 100 == 23")   # 17
    _assert(mod_pow(2, 10, 1024) == 0, "2^10 mod 1024==0")     # 18
    _assert(mod_pow(5, 0, 7) == 1, "5^0 mod 7==1")             # 19


def test_euler_totient() raises:
    print("  euler_totient...")
    _assert(euler_totient(12) == 4, "φ(12)==4")                 # 20
    _assert(euler_totient(1) == 1, "φ(1)==1")                   # 21
    _assert(euler_totient(7) == 6, "φ(7)==6 (prime)")           # 22
    _assert(euler_totient(10) == 4, "φ(10)==4")                 # 23


def test_prime_factors() raises:
    print("  prime_factors...")
    var pf12 = prime_factors(12)
    _assert(len(pf12) == 3, "12 has 3 prime factors")          # 24
    _assert(pf12[0] == 2, "12 factor[0]==2")                   # 25
    _assert(pf12[1] == 2, "12 factor[1]==2")                   # 26
    _assert(pf12[2] == 3, "12 factor[2]==3")                   # 27
    var pf30 = prime_factors(30)
    _assert(len(pf30) == 3, "30 has 3 prime factors")          # 28
    _assert(pf30[0] == 2, "30 factor[0]==2")                   # 29
    _assert(pf30[1] == 3, "30 factor[1]==3")                   # 30
    _assert(pf30[2] == 5, "30 factor[2]==5")                   # 31


def test_sieve() raises:
    print("  sieve_of_eratosthenes...")
    var primes = sieve_of_eratosthenes(20)
    _assert(len(primes) == 8, "8 primes <= 20")                # 32
    _assert(primes[0] == 2, "sieve[0]==2")                     # 33
    _assert(primes[1] == 3, "sieve[1]==3")                     # 34
    _assert(primes[2] == 5, "sieve[2]==5")                     # 35
    _assert(primes[7] == 19, "sieve[7]==19")                   # 36


def test_extended_gcd() raises:
    print("  extended_gcd...")
    var r = extended_gcd(35, 15)
    _assert(r[0] == 5, "gcd(35,15)==5")                        # 37
    # Verify 35*x + 15*y == 5
    var check = 35 * r[1] + 15 * r[2]
    _assert(check == 5, "35*x + 15*y == 5")                    # 38


def test_mod_inverse() raises:
    print("  mod_inverse...")
    var inv = mod_inverse(3, 7)
    _assert(inv == 5, "3^-1 mod 7 == 5")                       # 39
    _assert(mod_inverse(2, 4) == -1, "no inverse 2 mod 4")     # 40


def test_fibonacci() raises:
    print("  fibonacci...")
    _assert(fibonacci(0) == 0, "fib(0)==0")                     # 41
    _assert(fibonacci(1) == 1, "fib(1)==1")                     # 42
    _assert(fibonacci(10) == 55, "fib(10)==55")                 # 43
    _assert(fibonacci(20) == 6765, "fib(20)==6765")             # 44


def test_perfect_square() raises:
    print("  is_perfect_square...")
    _assert(is_perfect_square(49), "49 is perfect square")      # 45
    _assert(is_perfect_square(0), "0 is perfect square")        # 46
    _assert(not is_perfect_square(50), "50 not perfect square") # 47
    _assert(is_perfect_square(144), "144 is perfect square")    # 48


def test_coprime() raises:
    print("  is_coprime...")
    _assert(is_coprime(15, 28), "15,28 coprime")               # 49
    _assert(not is_coprime(12, 8), "12,8 not coprime")         # 50


# ── Optimization Tests ───────────────────────────────────────────────────────


def test_eval_objective() raises:
    print("  eval_objective...")
    var origin = List[Float64]()
    origin.append(0.0)
    origin.append(0.0)
    _assert_close(
        eval_objective(origin, 0), 0.0, 1e-12, "sphere(0,0)==0"
    )                                                           # 51
    _assert_close(
        eval_objective(origin, 1), 0.0, 1e-12, "rastrigin(0,0)==0"
    )                                                           # 52
    _assert_close(
        eval_objective(origin, 2), 0.0, 1e-6, "ackley(0,0)≈0"
    )                                                           # 53

    var v1 = List[Float64]()
    v1.append(1.0)
    v1.append(2.0)
    _assert_close(
        eval_objective(v1, 0), 5.0, 1e-12, "sphere(1,2)==5"
    )                                                           # 54


def test_acceptance_probability() raises:
    print("  acceptance_probability...")
    # Lower cost → accept with probability 1.0
    _assert_close(
        acceptance_probability(10.0, 5.0, 1.0),
        1.0, 1e-12, "accept lower cost"
    )                                                           # 55
    # Same cost → exp(0) = 1.0
    _assert_close(
        acceptance_probability(10.0, 10.0, 1.0),
        1.0, 1e-12, "same cost → 1.0"
    )                                                           # 56
    # Higher cost, very low temperature → near 0
    var p = acceptance_probability(10.0, 20.0, 0.001)
    _assert(p < 0.01, "high cost low temp → low prob")         # 57


def test_neighbor_fn() raises:
    print("  neighbor...")
    var x = List[Float64]()
    x.append(5.0)
    x.append(5.0)
    var n = neighbor(x, 0.1)
    _assert(len(n) == 2, "neighbor same dimension")             # 58
    _assert(fabs(n[0] - 5.0) <= 0.1, "neighbor within step")   # 59


def test_simulated_annealing() raises:
    print("  simulated_annealing...")
    var x0 = List[Float64]()
    x0.append(5.0)
    x0.append(5.0)
    var best = simulated_annealing(x0, 0, 100.0, 0.995, 5000)
    var cost = eval_objective(best, 0)
    _assert(cost < 1.0, "SA sphere converges near 0")          # 60


def test_particle_swarm() raises:
    print("  particle_swarm...")
    var best = particle_swarm(20, 2, 0, 200, -5.0, 5.0)
    var cost = eval_objective(best, 0)
    _assert(cost < 1.0, "PSO sphere near-optimal")             # 61


def test_random_search() raises:
    print("  random_search...")
    var best = random_search(2, 0, 500, -5.0, 5.0)
    _assert(len(best) == 2, "random_search returns dim=2")      # 62
    _assert(best[0] >= -5.0, "within lower bound")             # 63
    _assert(best[0] <= 5.0, "within upper bound")              # 64


def test_hill_climbing() raises:
    print("  hill_climbing...")
    var x0 = List[Float64]()
    x0.append(3.0)
    x0.append(3.0)
    var initial_cost = eval_objective(x0, 0)
    var best = hill_climbing(x0, 0, 0.5, 1000)
    var best_cost = eval_objective(best, 0)
    _assert(best_cost < initial_cost, "hill climbing improves") # 65


# ── Accounting Tests ─────────────────────────────────────────────────────────


def test_straight_line() raises:
    print("  straight_line_depreciation...")
    _assert_close(
        straight_line_depreciation(10000.0, 2000.0, 5),
        1600.0, 1e-6, "SLD(10000,2000,5)==1600"
    )                                                           # 66
    _assert_close(
        straight_line_depreciation(5000.0, 500.0, 10),
        450.0, 1e-6, "SLD(5000,500,10)==450"
    )                                                           # 67


def test_declining_balance() raises:
    print("  declining_balance...")
    _assert_close(
        declining_balance(10000.0, 0.2, 1),
        8000.0, 1e-6, "DB(10000,0.2,1)==8000"
    )                                                           # 68
    _assert_close(
        declining_balance(10000.0, 0.2, 0),
        10000.0, 1e-6, "DB year 0 == cost"
    )                                                           # 69


def test_sum_of_years_digits() raises:
    print("  sum_of_years_digits...")
    # 5-year life, year 1: (10000-2000) * 5/15 = 2666.67
    _assert_close(
        sum_of_years_digits(10000.0, 2000.0, 5, 1),
        2666.6666666666665, 1e-4, "SYD year 1"
    )                                                           # 70
    # year 5: (10000-2000) * 1/15 = 533.33
    _assert_close(
        sum_of_years_digits(10000.0, 2000.0, 5, 5),
        533.3333333333333, 1e-4, "SYD year 5"
    )                                                           # 71


def test_future_present_value() raises:
    print("  future_value / present_value...")
    _assert_close(
        future_value(1000.0, 0.05, 10),
        1628.894626777442, 0.01, "FV(1000,0.05,10)≈1628.89"
    )                                                           # 72
    _assert_close(
        present_value_single(1628.89, 0.05, 10),
        1000.0, 0.1, "PV≈1000"
    )                                                           # 73


def test_profit_margins() raises:
    print("  profit margins...")
    _assert_close(
        gross_profit_margin(100.0, 60.0),
        0.4, 1e-12, "GPM(100,60)==0.4"
    )                                                           # 74
    _assert_close(
        net_profit_margin(20.0, 100.0),
        0.2, 1e-12, "NPM(20,100)==0.2"
    )                                                           # 75


def test_ratios() raises:
    print("  ratios...")
    _assert_close(
        current_ratio(150.0, 100.0),
        1.5, 1e-12, "CR(150,100)==1.5"
    )                                                           # 76
    _assert_close(
        debt_to_equity(200.0, 400.0),
        0.5, 1e-12, "D/E(200,400)==0.5"
    )                                                           # 77
    _assert_close(
        return_on_equity(50.0, 200.0),
        0.25, 1e-12, "ROE(50,200)==0.25"
    )                                                           # 78


def test_break_even() raises:
    print("  break_even_units...")
    _assert_close(
        break_even_units(10000.0, 50.0, 30.0),
        500.0, 1e-6, "BE(10000,50,30)==500"
    )                                                           # 79


def test_cagr() raises:
    print("  compound_annual_growth...")
    _assert_close(
        compound_annual_growth(100.0, 200.0, 5),
        0.148698, 0.001, "CAGR(100,200,5)≈0.1487"
    )                                                           # 80
    _assert_close(
        compound_annual_growth(100.0, 100.0, 3),
        0.0, 1e-12, "CAGR no growth"
    )                                                           # 81


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 52 Tests ===")

    # Number Theory
    print("Number Theory:")
    test_is_prime()
    test_gcd_lcm()
    test_mod_pow()
    test_euler_totient()
    test_prime_factors()
    test_sieve()
    test_extended_gcd()
    test_mod_inverse()
    test_fibonacci()
    test_perfect_square()
    test_coprime()

    # Optimization
    print("Metaheuristic Optimization:")
    test_eval_objective()
    test_acceptance_probability()
    test_neighbor_fn()
    test_simulated_annealing()
    test_particle_swarm()
    test_random_search()
    test_hill_climbing()

    # Accounting
    print("Accounting:")
    test_straight_line()
    test_declining_balance()
    test_sum_of_years_digits()
    test_future_present_value()
    test_profit_margins()
    test_ratios()
    test_break_even()
    test_cagr()

    print("All 81 assertions passed! ✓")
