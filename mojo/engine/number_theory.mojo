"""
number_theory.mojo — Number theory utilities. Zero Python imports.

Replaces sympy.ntheory with pure Mojo implementations for primality,
GCD/LCM, modular arithmetic, Euler totient, sieve, and Fibonacci.

Public API:
  is_prime, gcd, lcm, mod_pow, euler_totient, prime_factors,
  sieve_of_eratosthenes, is_coprime, extended_gcd, mod_inverse,
  fibonacci, is_perfect_square
"""


# ── Primality ────────────────────────────────────────────────────────────────


fn is_prime(n: Int) -> Bool:
    """Deterministic Miller-Rabin-like primality test for n < 2^31."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    # Write n-1 as 2^r * d
    var d = n - 1
    var r = 0
    while d % 2 == 0:
        d //= 2
        r += 1
    # Witnesses sufficient for n < 3,215,031,751 (covers < 2^31)
    var witnesses = List[Int]()
    witnesses.append(2)
    witnesses.append(3)
    witnesses.append(5)
    witnesses.append(7)
    for wi in range(len(witnesses)):
        var a = witnesses[wi]
        if a >= n:
            continue
        var x = mod_pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        var composite = True
        for _ in range(r - 1):
            x = mod_pow(x, 2, n)
            if x == n - 1:
                composite = False
                break
        if composite:
            return False
    return True


# ── GCD / LCM ───────────────────────────────────────────────────────────────


fn gcd(a: Int, b: Int) -> Int:
    """Greatest common divisor via Euclidean algorithm."""
    var x = a
    var y = b
    if x < 0:
        x = -x
    if y < 0:
        y = -y
    while y != 0:
        var t = y
        y = x % y
        x = t
    return x


fn lcm(a: Int, b: Int) -> Int:
    """Least common multiple: a*b / gcd(a,b)."""
    if a == 0 or b == 0:
        return 0
    var g = gcd(a, b)
    var aa = a
    var bb = b
    if aa < 0:
        aa = -aa
    if bb < 0:
        bb = -bb
    return (aa // g) * bb


# ── Modular Exponentiation ───────────────────────────────────────────────────


fn mod_pow(base: Int, exp: Int, modulus: Int) -> Int:
    """Modular exponentiation by squaring: base^exp mod modulus."""
    if modulus == 1:
        return 0
    var result = 1
    var b = base % modulus
    if b < 0:
        b += modulus
    var e = exp
    while e > 0:
        if e % 2 == 1:
            result = (result * b) % modulus
        e //= 2
        b = (b * b) % modulus
    return result


# ── Euler Totient ────────────────────────────────────────────────────────────


fn euler_totient(n: Int) -> Int:
    """Euler's totient φ(n) by trial division."""
    if n <= 0:
        return 0
    if n == 1:
        return 1
    var result = n
    var m = n
    var p = 2
    while p * p <= m:
        if m % p == 0:
            while m % p == 0:
                m //= p
            result -= result // p
        p += 1
    if m > 1:
        result -= result // m
    return result


# ── Prime Factors ────────────────────────────────────────────────────────────


fn prime_factors(n: Int) -> List[Int]:
    """List of prime factors with repetition."""
    var factors = List[Int]()
    if n <= 1:
        return factors^
    var m = n
    while m % 2 == 0:
        factors.append(2)
        m //= 2
    var f = 3
    while f * f <= m:
        while m % f == 0:
            factors.append(f)
            m //= f
        f += 2
    if m > 1:
        factors.append(m)
    return factors^


# ── Sieve of Eratosthenes ───────────────────────────────────────────────────


fn sieve_of_eratosthenes(limit: Int) -> List[Int]:
    """All primes up to limit (inclusive)."""
    var primes = List[Int]()
    if limit < 2:
        return primes^
    # is_composite flags
    var is_comp = List[Bool]()
    for _ in range(limit + 1):
        is_comp.append(False)
    var p = 2
    while p * p <= limit:
        if not is_comp[p]:
            var j = p * p
            while j <= limit:
                is_comp[j] = True
                j += p
        p += 1
    for i in range(2, limit + 1):
        if not is_comp[i]:
            primes.append(i)
    return primes^


# ── Coprimality ──────────────────────────────────────────────────────────────


fn is_coprime(a: Int, b: Int) -> Bool:
    """True if gcd(a, b) == 1."""
    return gcd(a, b) == 1


# ── Extended GCD ─────────────────────────────────────────────────────────────


fn extended_gcd(a: Int, b: Int) -> List[Int]:
    """Returns [gcd, x, y] where a*x + b*y = gcd(a, b)."""
    var old_r = a
    var r = b
    var old_s = 1
    var s = 0
    var old_t = 0
    var t = 1
    while r != 0:
        var q = old_r // r
        var tmp_r = r
        r = old_r - q * r
        old_r = tmp_r
        var tmp_s = s
        s = old_s - q * s
        old_s = tmp_s
        var tmp_t = t
        t = old_t - q * t
        old_t = tmp_t
    var result = List[Int]()
    result.append(old_r)
    result.append(old_s)
    result.append(old_t)
    return result^


# ── Modular Inverse ──────────────────────────────────────────────────────────


fn mod_inverse(a: Int, m: Int) -> Int:
    """Modular multiplicative inverse of a mod m. Returns -1 if none."""
    var res = extended_gcd(a, m)
    if res[0] != 1:
        return -1
    var inv = res[1] % m
    if inv < 0:
        inv += m
    return inv


# ── Fibonacci ────────────────────────────────────────────────────────────────


fn fibonacci(n: Int) -> Int:
    """Nth Fibonacci number (iterative). fib(0)=0, fib(1)=1."""
    if n <= 0:
        return 0
    if n == 1:
        return 1
    var a = 0
    var b = 1
    for _ in range(2, n + 1):
        var c = a + b
        a = b
        b = c
    return b


# ── Perfect Square ───────────────────────────────────────────────────────────


fn is_perfect_square(n: Int) -> Bool:
    """Check if n is a perfect square."""
    if n < 0:
        return False
    if n == 0:
        return True
    # Integer square root via Newton's method
    var x = n
    var y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x * x == n
