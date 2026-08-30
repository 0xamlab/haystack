---
icon: square-root-variable
description: Dense-coefficient polynomial arithmetic and calculus, five classical root-finding algorithms run against a fixed menu of test functions, and integer number theory -- primality, GCD, modular exponentiation, and small combinatorial sequences.
---

# Polynomial, root-finding, and number-theory kernels

Three small, self-contained modules that replace pieces of `numpy.polynomial`, `scipy.optimize`,
and `sympy.ntheory` with pure Mojo. `polynomial` stores a polynomial as a flat `List[Float64]` of
coefficients (`coeffs[i]` is the coefficient of `xⁱ`, constant term first) and does evaluation,
arithmetic, calculus, and composition on that representation. `root_finding` implements five
classical scalar root-finders -- bisection, Newton-Raphson, secant, regula falsi, and a
Newton-flavored fixed-point variant -- run not against an arbitrary user-supplied function but
against a closed menu of four hardcoded test functions selected by integer `func_id`, plus a
bracket-search helper and a convergence-order estimator for comparing them. `number_theory` is
integer-only: primality testing, GCD/LCM, modular exponentiation and inverse, Euler's totient,
prime factorization, a sieve, Fibonacci, and integer perfect-square testing. None of the three
share code with each other; they are grouped on this page because they are the engine's classical
numerical-methods primitives, not because one calls another.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# roots of x^2 - 5x + 6 = (x-2)(x-3)
runtime.execute("polynomial", "quadratic_roots", [1.0, -5.0, 6.0])["result"]
# [2.0, 3.0]

# Newton-Raphson on func_id 0 (x^2 - 2), starting from x0 = 1.0
runtime.execute("root_finding", "newton_raphson", [1.0, 0])["result"]
# 1.4142135623746899 -- sqrt(2) to ~11 digits; see below for why not more

runtime.execute("number_theory", "is_prime", [561])["result"]
# False -- 561 = 3 x 11 x 17, a Carmichael number that fools a naive Fermat test
```

## The modules

| Module | What it does |
| --- | --- |
| `polynomial` | Dense-coefficient polynomial arithmetic: Horner evaluation, add, multiply, derivative, integral, degree, scaling, composition, building a polynomial from its roots, and the closed-form quadratic formula. |
| `root_finding` | Bisection, Newton-Raphson, secant, regula falsi, and a Newton-form fixed-point iteration, all run against four hardcoded test functions selected by `func_id`; plus a bracket-search helper and an empirical convergence-order estimator. |
| `number_theory` | Primality (deterministic Miller-Rabin), GCD/LCM, modular exponentiation and inverse, extended GCD, Euler's totient, prime factorization, a sieve of Eratosthenes, coprimality, Fibonacci, and integer perfect-square testing. |

## `polynomial`: dense-coefficient arithmetic and calculus

| Function | What it does |
| --- | --- |
| `poly_eval(coeffs, x)` | Evaluates `p(x)` by Horner's method, working from the highest-degree term down. `poly_eval([], x)` returns `0.0`. |
| `poly_add(a, b)` | Coefficient-wise sum; the shorter input is treated as zero-padded rather than requiring equal lengths. |
| `poly_multiply(a, b)` | Convolution: `result[i+j] += a[i]*b[j]`. Output has `len(a)+len(b)-1` terms; either empty input yields an empty result. |
| `poly_derivative(coeffs)` | `d/dx`: term `i` of the input (`i >= 1`) becomes term `i-1` of the output, scaled by `i`. A constant or empty input returns `[0.0]`. |
| `poly_integral(coeffs, C=0.0)` | Indefinite integral: prepends the constant `C`, then divides term `i` of the input by `i+1`. |
| `poly_degree(coeffs)` | Index of the highest coefficient whose magnitude exceeds `1e-15`. Returns `-1` only for a genuinely empty list -- see the edge case below. |
| `quadratic_roots(a, b, c)` | Roots of `a*x^2 + b*x + c` by the closed-form formula. Degrades to the single linear root when `a` is ~0, and returns an empty list both for a fully degenerate `a=b=0` input and for a negative discriminant (complex roots). |
| `poly_scale(coeffs, s)` | Multiplies every coefficient by scalar `s`. |
| `poly_compose(f, g)` | Substitutes `g(x)` into `f`, producing `f(g(x))`, via repeated Horner-style multiplication by `g`. |
| `poly_from_roots(roots)` | Builds `∏(x - rᵢ)` from a list of real roots. An empty root list returns the constant polynomial `[1.0]` -- the empty product. |

**Worked arithmetic and calculus, hand-verified.** Evaluating `p(x) = 1 - 2x + 3x^2` at `x = 2` by
Horner's method gives `1 - 4 + 12 = 9.0`, matching `poly_eval([1.0, -2.0, 3.0], 2.0)`. Its
derivative is `-2 + 6x`, i.e. `poly_derivative([1.0, -2.0, 3.0]) == [-2.0, 6.0]`, and integrating
`[1.0, -2.0, 3.0]` with `C=0.0` gives `[0.0, 1.0, -1.0, 1.0]` -- the polynomial `x - x^2 + x^3`.
Differentiating that result recovers the original `[1.0, -2.0, 3.0]` exactly, since
`poly_derivative` multiplies term `i` of `[C, 1, -1, 1]` by `i` for `i = 1, 2, 3`, giving
`[1*1, 2*-1, 3*1] = [1.0, -2.0, 3.0]` -- integral and derivative are exact inverses of each other
up to the constant term, on this representation.

`poly_from_roots([2.0, 3.0])` builds `(x-2)(x-3) = x^2 - 5x + 6`, returning `[6.0, -5.0, 1.0]`,
and `poly_compose` substitutes one polynomial into another: composing `f = 1 + x^2` (`[1.0, 0.0,
1.0]`) with `g = x + 1` (`[1.0, 1.0]`) gives `f(g(x)) = 1 + (x+1)^2 = x^2 + 2x + 2`, i.e.
`poly_compose([1.0, 0.0, 1.0], [1.0, 1.0]) == [2.0, 2.0, 1.0]`.

**`quadratic_roots` cannot represent a complex pair -- it returns nothing instead.** For
`x^2 + 1 = 0` (`a=1, b=0, c=1`), the discriminant `b^2 - 4ac = -4` is negative, and the function
returns an empty list rather than a complex pair, because the return type is `List[Float64]`. A
caller cannot distinguish "no real roots" from certain other empty-list cases (see below) without
also knowing which branch produced it. The degenerate `a ≈ 0` branch is a real fallback, not an
error: `quadratic_roots(0.0, 2.0, -4.0)` returns `[2.0]`, the single linear root `-c/b`, and
`quadratic_roots(0.0, 0.0, 5.0)` -- both leading coefficients zero, an inconsistent equation --
returns an empty list, the same empty result a genuine complex-root case produces.

**`poly_degree` of an all-zero, non-empty list is `0`, not `-1`.** The loop that walks down from
the top looking for a non-negligible coefficient is guarded by `deg > 0`, so it stops at index `0`
even if `coeffs[0]` is also below `1e-15` in magnitude: `poly_degree([0.0, 0.0, 0.0])` returns `0`.
Only a literally empty `List[Float64]` (`poly_degree([])`) produces the `-1` sentinel that means
"no coefficients at all." The identically-zero polynomial and a nonzero constant polynomial both
report degree `0`.

## `root_finding`: five algorithms sharing one closed menu of test functions

| Function | What it does |
| --- | --- |
| `eval_func(x, func_id)` | Evaluates test function `func_id` at `x`. Unrecognized `func_id` values silently return `0.0` rather than raising. |
| `eval_deriv(x, func_id)` | The matching hand-derived derivative for the same four functions; same silent-`0.0` fallback. |
| `bisection(a, b, func_id, tol=1e-10, max_iter=100)` | Standard bracketing bisection. If `f(a)` and `f(b)` don't have opposite signs, returns the midpoint immediately rather than searching. |
| `newton_raphson(x0, func_id, tol=1e-10, max_iter=100)` | `x_{n+1} = x_n - f(x_n)/f'(x_n)`, stopping when `\|f(x)\| < tol` or the derivative underflows below `1e-15`. |
| `secant_method(x0, x1, func_id, tol=1e-10, max_iter=100)` | Newton's method with a finite-difference secant in place of the analytic derivative. |
| `fixed_point(x0, func_id, tol=1e-10, max_iter=100)` | See the callout below -- this is Newton's method again, not generic fixed-point iteration. |
| `regula_falsi(a, b, func_id, tol=1e-10, max_iter=100)` | False position: like bisection, but the next probe point is a secant intersection instead of the midpoint. Refuses a degenerate or non-finite bracket by returning the plain midpoint. |
| `bracket_root(func_id, start=0.0, step=0.5, max_steps=100)` | Walks outward from `start` in both directions looking for a sign change. See the caveats below. |
| `convergence_order(errors)` | Estimates the convergence order from the last usable triple of consecutive errors via `log(e_{n+1}/e_n) / log(e_n/e_{n-1})`. Returns `0.0` if fewer than 3 usable (positive, non-degenerate) errors are available. |

All five solvers and `eval_func`/`eval_deriv` take an `Int func_id` rather than a callback, because
the four test functions are hardcoded in `eval_func` and `eval_deriv` themselves:

| `func_id` | Function | Derivative | Real root(s) |
| --- | --- | --- | --- |
| `0` | `x^2 - 2` | `2x` | `√2 ≈ 1.41421356` |
| `1` | `x^3 - x - 2` | `3x^2 - 1` | `≈ 1.52137970` |
| `2` | `cos(x) - x` | `-sin(x) - 1` | `≈ 0.73908513` |
| `3` | `exp(x) - 3x` | `exp(x) - 3` | `≈ 0.61906129` and `≈ 1.51213455` |

This is a real, narrower scope than a general-purpose numerical solver library: there is no way to
hand these functions an arbitrary user-defined `f`; every solver here is exercised against this
fixed menu of four textbook test cases, which is what "test functions identified by `func_id`" in
the module's own docstring means literally.

**`fixed_point` is not generic fixed-point iteration -- it is Newton's method under another
name.** Classical fixed-point iteration repeatedly applies an arbitrary map `g` and converges when
`x_{n+1} = g(x_n) ≈ x_n`, for any `g` the caller chooses. Reading the body of `fixed_point`, its
update rule is hardcoded to `x - f(x)/f'(x)` -- calling `eval_deriv` exactly as `newton_raphson`
does -- with the only difference being an added `|x_{n+1} - x_n| < tol` stopping check alongside
the `|f(x)| < tol` one. For every `func_id` in the table above, `fixed_point(x0, func_id)` and
`newton_raphson(x0, func_id)` converge to the same value by the same iteration; there is no
generic `g(x) = x` map here to substitute a different one in.

**Newton, bisection, secant, and regula falsi all land on the same root, to comparable
precision.** Solving `func_id = 0` (root `√2`) from reasonable starting brackets/points:
`newton_raphson(1.0, 0)` returns `1.4142135623746899`, `bisection(0.0, 2.0, 0)` returns
`1.4142135623842478`, `secant_method(1.0, 2.0, 0)` returns `1.4142135623730954`, and
`regula_falsi(0.0, 2.0, 0)` returns `1.4142135623637997` -- all four agree with `√2 =
1.4142135623730951` to at least 9 significant digits, and all four were hand-traced against the
real formulas in `mojo/engine/root_finding.mojo` and independently reproduced in Python. Note that
the default `tol=1e-10` bounds `|f(x)|`, not `|x - root|`; near `√2` the derivative is
`2x ≈ 2.83`, so an `f(x)` just under `1e-10` corresponds to an `x` error on the order of `1e-10 /
2.83`, which is why Newton's actual returned value differs from the true `√2` by only
`1.6e-12` rather than landing exactly on `tol`.

**`convergence_order`, measured on Newton's own iterates, reports ≈2.0 -- textbook quadratic
convergence.** Tracing `newton_raphson`'s five iterates starting from `x0 = 1.0` on `func_id = 0`
and computing the true error `|x_i - √2|` at each step gives the sequence `[0.41421356,
0.08578644, 0.00245310, 2.1239e-06, 1.5947e-12]` -- each error is roughly the square of the
previous one, the signature of quadratic convergence. Feeding that sequence into
`convergence_order` returns `1.9997666710861988`, matching the theoretical order-2 convergence of
Newton's method on a simple root to three decimal places; this number was computed by re-running
the exact recurrence in `convergence_order`'s docstring formula in Python, not invented.

**`bracket_root`'s fallback is not validated, and a coarse step size can straddle a pair of roots
without detecting either.** When the search loop exhausts `max_steps` without finding a sign
change, the function falls back to returning `[start, start + step]` unconditionally -- it does
not check `eval_func(start, func_id) * eval_func(start + step, func_id) < 0.0` before returning,
so a caller must verify that product itself before trusting the result as an actual bracket. This
is not a hypothetical: `func_id = 3` (`exp(x) - 3x`) has two real roots, `≈0.619` and `≈1.512`,
both strictly between `x = 0.6` and `x = 1.6`. Calling `bracket_root(3, 0.6, 1.0, 60)` samples only
`f(0.6) ≈ 0.0221` and `f(1.6) ≈ 0.153` -- both positive, because the step of `1.0` jumps clean over
both roots without sampling the negative dip between them -- so no sign change is ever seen, and
the function falls through every iteration to the unvalidated `[0.6, 1.6]` fallback, which is not
a valid bracket for either root.

## `number_theory`: primality, modular arithmetic, and small integer sequences

| Function | What it does |
| --- | --- |
| `is_prime(n)` | Deterministic Miller-Rabin using witnesses `{2, 3, 5, 7}`, valid for `n < 2^31` (the module docstring's claimed range fits inside the proven deterministic bound of `n < 3,215,031,751` for this witness set). |
| `gcd(a, b)` | Euclidean algorithm; negative inputs are converted to their absolute value first. |
| `lcm(a, b)` | `\|a*b\| / gcd(a, b)`; `0` if either input is `0`. |
| `mod_pow(base, exp, modulus)` | Modular exponentiation by repeated squaring. See the negative-exponent caveat below. |
| `euler_totient(n)` | Euler's φ(n) by trial division up to `√n`. `0` for `n <= 0`, `1` for `n == 1`. |
| `prime_factors(n)` | Prime factorization with repetition, smallest factor first, via trial division. Empty for `n <= 1`. |
| `sieve_of_eratosthenes(limit)` | All primes up to and including `limit`. Empty for `limit < 2`. |
| `is_coprime(a, b)` | `gcd(a, b) == 1`. |
| `extended_gcd(a, b)` | Returns `[gcd, x, y]` satisfying Bezout's identity `a*x + b*y = gcd(a, b)`. Unlike `gcd`, does not normalize the sign of its inputs first. |
| `mod_inverse(a, m)` | Modular multiplicative inverse of `a` mod `m`, built on `extended_gcd(a, m)`; returns `-1` if `gcd(a, m) != 1`. |
| `fibonacci(n)` | Nth Fibonacci number, iterative, `fibonacci(0) = 0`, `fibonacci(1) = 1`. |
| `is_perfect_square(n)` | Integer square root via Newton's method, then checks `x*x == n`. `False` for negative `n`. |

**`is_prime` correctly rejects a Carmichael number, which a naive Fermat test would not.** `561 =
3 * 11 * 17` is the smallest Carmichael number -- it passes a plain Fermat primality test for every
base coprime to it, which is exactly the failure mode Miller-Rabin's extra squaring step exists to
catch. Tracing the real algorithm: `n - 1 = 560 = 2^4 * 35`, so `d = 35`, `r = 4`. The first
witness, `a = 2`, gives `x = 2^35 mod 561 = 263`, which is neither `1` nor `560`; squaring
`r - 1 = 3` more times never lands on `560` either, so the witness proves `561` composite and
`is_prime(561)` correctly returns `False` -- confirmed independently in Python against the same
witness set and against brute-force trial division.

**`mod_pow` silently returns `1` for a negative exponent -- it does not compute an inverse.** The
squaring loop is `while e > 0`, so a negative `exp` never enters it and `result` is returned
unchanged at its initial value of `1`, identical to what `exp = 0` produces:
`mod_pow(3, -1, 7)` returns `1`, not the true inverse `5` (since `3 * 5 = 15 ≡ 1 mod 7`). A caller
wanting a modular inverse needs the dedicated `mod_inverse` function, not a negative exponent
passed to `mod_pow`.

**`gcd`/`lcm` normalize sign; `extended_gcd`/`mod_inverse` do not, except at the very end.**
`gcd` and `lcm` explicitly take the absolute value of both inputs before running the Euclidean
algorithm, so `gcd(-48, 18) == gcd(48, 18) == 6`. `extended_gcd` runs the extended Euclidean
algorithm directly on the signed inputs it is given with no such normalization step, so its
Bezout coefficients (and occasionally the sign of the reported gcd itself) depend on the actual
signs of `a` and `b`, not their magnitudes. `mod_inverse` builds on `extended_gcd(a, m)` and only
normalizes at the very end, folding a negative Bezout coefficient into `[0, m)` with a single
`+= m` if needed -- e.g. `mod_inverse(3, 11)` returns `4` (since `3*4 = 12 ≡ 1 mod 11`), and
`mod_inverse(4, 8)` returns `-1` (since `gcd(4, 8) = 4 != 1`, no inverse exists), both confirmed by
re-running the same recurrence independently.

**Worked chain: `euler_totient`, `prime_factors`, and `sieve_of_eratosthenes` on the same
numbers.** `36 = 2^2 * 3^2`, so `prime_factors(36)` gives `[2, 2, 3, 3]` and `euler_totient(36) =
36 * (1 - 1/2) * (1 - 1/3) = 12` -- both independently re-derived and matching the trial-division
formula in the source. `sieve_of_eratosthenes(30)` returns `[2, 3, 5, 7, 11, 13, 17, 19, 23, 29]`,
the ten primes up to 30. `fibonacci(10) = 55` and `is_perfect_square(144)` is `True` (`12^2 = 144`)
while `is_perfect_square(145)` is `False`, both traced through the integer-Newton loop by hand.

## Verification

All three `mojo/tests/libs/test_*.mojo` files behind this page (`test_polynomial.mojo`,
`test_root_finding.mojo`, `test_number_theory.mojo`) are auto-generated coverage smoke tests: each
calls every function once with a literal fixture (mostly `0.5`-valued floats or the integer `5`)
and checks only that a numeric result is finite or a list result has non-negative length -- none
of the three pin any specific expected output. Every numeric claim on this page -- the Horner
evaluation, the derivative/integral round trip, the quadratic and composed-polynomial coefficients,
the four solvers' agreement on `√2`, the Newton convergence-order measurement, the Carmichael-number
primality trace, the negative-exponent `mod_pow` behavior, and the totient/factorization/sieve
chain -- was instead hand-traced against the real formulas in `mojo/engine/polynomial.mojo`,
`root_finding.mojo`, and `number_theory.mojo`, and independently re-run in Python to confirm the
value before being presented here.

## Relationship to other pages

Grepping `gitbook/` for `polynomial`, `root_finding`, and `number_theory` as module names turns up
nothing besides this page and the auto-generated
[Runtime library catalog](runtime-library-catalog.md), which lists them with 10, 9, and 12
functions respectively -- matching the counts above exactly. Two near-miss names are worth ruling
out explicitly: [`ml-classical-algorithms.md`](ml-classical-algorithms.md)'s
`ml.preprocessing.polynomial_features` shares the word "polynomial" but is a feature-engineering
transform that expands a numeric vector into monomial cross-terms for a downstream model -- it
does not touch this page's `List[Float64]` coefficient representation or arithmetic at all. And
[`optimization.md`](optimization.md)'s six modules (`optimization.model`, `.linear`, `.integer`,
`.assignment`, `.flow`, `.explain`) solve linear and integer programs, assignment, and network
flow -- none of them do scalar root-finding or expose anything resembling `newton_raphson` or
`bisection`; the two families do not share code or call each other.

**Next:** see the [Runtime library catalog](runtime-library-catalog.md) for every module and
function, or [Optimization & decision programs](optimization.md) for the engine's other family of
classical numerical methods.
