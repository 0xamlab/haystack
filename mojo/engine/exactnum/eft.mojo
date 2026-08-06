"""
exactnum.eft — error-free transformations and double-double arithmetic. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_exactnum_eft.mojo
benchmark: benchmarks/mojo_benchmarks/measure_exactnum_strd.mojo
docs: gitbook/benchmarks/least-squares-accuracy.md
version_introduced: 0.1.0
deprecation_state: active
@endcapability

An *error-free transformation* returns the rounded result of an operation together with the
exact rounding error, so that `hi + lo` reproduces the infinitely-precise answer with no
loss. Two of them (Knuth's `two_sum`, Dekker's `two_product`) are enough to build a number
format with roughly twice float64's significand at a few flops of cost, which is the whole
mechanism this package rests on.

Status range
------------
`eft` owns **800-809** of `exactnum`'s 800-819 (rule 4e).

What this depends on, and how it is checked rather than assumed
--------------------------------------------------------------
`two_product` is exact only with a genuine single-rounding FMA. `two_sum` is exact only if
`s - a` is recomputed rather than algebraically folded back to `b`, and only if the
compiler does not reassociate. If a future toolchain breaks any of those, every routine
here silently degrades to plain float64 and still passes a naive test, because a naive test
compares against a value plain float64 already gets right.

So the three decisive cases are checked at runtime by `eft_selfcheck_code`:

1. `a = b = 1 + 2^-52`. The exact product is `1 + 2^-51 + 2^-104`; the float64 product
   drops the `2^-104`. `two_product` must return exactly `2^-104` as its error term, and
   `(a*b) - (a*b)` — the same expression without an FMA — must return zero.
2. `p = a*b; p - a*b` must be exactly zero. If the compiler contracted the second `a*b`
   into an FMA against `p`, `p` is not the rounded product and every EFT here is wrong.
3. `u = 2^53, v = w = 1`. `(u+v)+w != u+(v+w)` in float64. If those compare equal the
   compiler reassociated, and `two_sum` cannot be trusted.

A caller that cares should assert `eft_selfcheck_code() == EFT_OK` before believing any
double-double result. `exactnum.lstsq` does this on every solve and refuses rather than
returning a number it cannot stand behind (rule 4).

Frozen kernels called rather than reimplemented (rule 3)
--------------------------------------------------------
`eft_kahan_sum_f64` forwards to the frozen `numerical_stability.kahan_sum`. It is here so
that the plain-float64 compensated sum has exactly one definition in the tree and a caller
comparing `Sum2` against "compensated float64" is comparing against the shipped one.
`eft_sum2` is not a rewrite of it: `kahan_sum` returns a Float64 and discards the running
compensation at the end, while `Sum2` returns the (sum, error) pair, which is a different
result type and the one a double-double accumulation needs.

Public API:
  eft_selfcheck_code()                        — EFT_OK, or which assumption broke
  eft_two_sum(a, b)                           — Knuth two_sum, branch-free
  eft_fast_two_sum(a, b)                      — Dekker, valid only when |a| >= |b|
  eft_two_product(a, b)                       — Dekker two_product via one FMA
  eft_two_product_dekker(a, b)                — the 17-flop splitting fallback, no FMA
  eft_dd_add / sub / mul / div(a_hi, a_lo, b_hi, b_lo)
  eft_dd_sqrt(a_hi, a_lo)                     — one Newton step, absent for a_hi < 0
  eft_dot2(x, y, n)                           — Ogita-Rump-Oishi Dot2
  eft_sum2(x, n)                              — Ogita-Rump-Oishi Sum2
  eft_kahan_sum_f64(x)                        — the frozen compensated sum, forwarded
"""

from std.math import abs as fabs, isinf, isnan, sqrt

from numerical_stability import kahan_sum

# ── status codes: eft owns 800-809 ────────────────────────────────────────────

comptime EFT_OK: Int = 800
comptime EFT_ERR_NO_FUSED_MULTIPLY_ADD: Int = 801
comptime EFT_ERR_COMPILER_CONTRACTS_FMA: Int = 802
comptime EFT_ERR_COMPILER_REASSOCIATES: Int = 803
comptime EFT_ERR_INVALID_LENGTH: Int = 804
comptime EFT_ERR_NON_FINITE_INPUT: Int = 805
comptime EFT_ERR_NEGATIVE_RADICAND: Int = 806

comptime EFT_MAX_TERMS: Int = 1 << 26
"""Element bound on a `Dot2` / `Sum2` input.

`1 << 26` is `sparse_numerics.csr.MAX_CSR_DIM`, the tree's one shared dimension ceiling, and
it is the right number here for the same reason: a single 2^26 `Float64` buffer is ~512 MB,
which is the per-object resident budget. `Dot2` allocates nothing per element, so rule 1c's
"k arrays of a bounded length" multiplier is 1 and the ceiling does not need scaling down."""

comptime _DEKKER_SPLITTER: Float64 = 134217729.0
"""2^27 + 1, Dekker's splitter. Only used by the no-FMA fallback."""


def eft_status_name(code: Int) -> String:
    """The `exactnum.eft` status vocabulary. One integer, one meaning (rule 4e)."""
    if code == EFT_OK:
        return String("ok")
    if code == EFT_ERR_NO_FUSED_MULTIPLY_ADD:
        return String("no_fused_multiply_add")
    if code == EFT_ERR_COMPILER_CONTRACTS_FMA:
        return String("compiler_contracts_fma")
    if code == EFT_ERR_COMPILER_REASSOCIATES:
        return String("compiler_reassociates")
    if code == EFT_ERR_INVALID_LENGTH:
        return String("invalid_length")
    if code == EFT_ERR_NON_FINITE_INPUT:
        return String("non_finite_input")
    if code == EFT_ERR_NEGATIVE_RADICAND:
        return String("negative_radicand")
    return String("unknown_status")


@fieldwise_init
struct DD(ImplicitlyCopyable, Movable):
    """An unevaluated sum `hi + lo` with `|lo| <= ulp(hi) / 2` after normalisation.

    `hi` is then the float64 nearest to the represented value, so rounding a double-double
    result down to a float64 return is `.hi` and costs nothing.

    `exact` is not a field. A DD is exact when it came straight out of an error-free
    transformation and inexact after the first `dd_add` that had to renormalise; tracking
    that would be a lie the moment two of them were combined, so callers that need an exact
    residual must arrange it structurally instead (see `lstsq`'s refinement note)."""

    var hi: Float64
    var lo: Float64


# ── the two error-free transformations everything else is built from ──────────


@always_inline
def eft_two_sum(a: Float64, b: Float64) -> DD:
    """Knuth two_sum: `hi + lo == a + b` exactly, for any finite a, b. 6 flops.

    Branch-free and order-independent, unlike `eft_fast_two_sum`. The `s - bb` term must be
    recomputed by the hardware; if a compiler folds it algebraically the error term
    collapses to zero and this becomes plain addition. `eft_selfcheck_code` checks that.

    @capability eft_two_sum
    complexity: O(1)
    @endcapability
    """
    var s = a + b
    var bb = s - a
    var err = (a - (s - bb)) + (b - bb)
    return DD(s, err)


@always_inline
def eft_fast_two_sum(a: Float64, b: Float64) -> DD:
    """Dekker fast_two_sum: `hi + lo == a + b` exactly, **only when `|a| >= |b|`**. 3 flops.

    The precondition is not checked. It is not checkable for free — a branch here costs more
    than the three flops it guards — so every internal use below is a renormalisation where
    `|b|` is already known to be at ulp scale. Public callers who cannot prove the ordering
    must use `eft_two_sum`.

    @capability eft_fast_two_sum
    complexity: O(1)
    @endcapability
    """
    var s = a + b
    var err = b - (s - a)
    return DD(s, err)


@always_inline
def eft_two_product(a: Float64, b: Float64) -> DD:
    """Dekker two_product via one FMA: `hi + lo == a * b` exactly. 2 flops.

    Exact for every finite product that does not overflow or fall into the subnormal range,
    because `a*b` needs at most 106 significand bits and the FMA delivers the residual
    `a*b - fl(a*b)` with a single rounding.

    @capability eft_two_product
    complexity: O(1)
    @endcapability
    """
    var p = a * b
    var e = a.fma(b, -p)
    return DD(p, e)


@always_inline
def _dekker_split(a: Float64) -> DD:
    var c = _DEKKER_SPLITTER * a
    var hi = c - (c - a)
    var lo = a - hi
    return DD(hi, lo)


@always_inline
def eft_two_product_dekker(a: Float64, b: Float64) -> DD:
    """`eft_two_product` without any FMA — 17 flops of splitting instead of 2.

    Kept as a portability fallback and as an independent second opinion: it agrees with the
    FMA form bit-for-bit on this toolchain, which is one of the checks in the suite. Not the
    default, because it is 8x the flops and this hardware has a real FMA.

    @capability eft_two_product_dekker
    complexity: O(1)
    @endcapability
    """
    var p = a * b
    var sa = _dekker_split(a)
    var sb = _dekker_split(b)
    var err = ((sa.hi * sb.hi - p) + sa.hi * sb.lo + sa.lo * sb.hi) + sa.lo * sb.lo
    return DD(p, err)


# ── double-double arithmetic (Dekker / Bailey QD algorithms) ──────────────────


@always_inline
def dd_from(a: Float64) -> DD:
    """A float64 lifted exactly into double-double."""
    return DD(a, 0.0)


@always_inline
def dd_neg(a: DD) -> DD:
    return DD(-a.hi, -a.lo)


@always_inline
def dd_add(a: DD, b: DD) -> DD:
    """Accurate double-double addition (Bailey's `ieee_add`), ~2^-106 relative. 20 flops.

    The cheaper `sloppy_add` loses its error bound when the operands nearly cancel, which is
    the case a Householder reflector generates on an ill-conditioned column. Measured rather
    than assumed: substituting the sloppy form and re-running the whole NIST StRD suite changed
    no returned float64 coefficient on any of the 11 datasets. So the accurate form is kept
    because it is the one with a proof behind it and the 11 extra flops are not the bottleneck,
    NOT because this suite can see the difference. Do not cite these datasets as evidence that
    it matters; cite the bound."""
    var s = eft_two_sum(a.hi, b.hi)
    var t = eft_two_sum(a.lo, b.lo)
    var lo1 = s.lo + t.hi
    var r1 = eft_fast_two_sum(s.hi, lo1)
    var lo2 = r1.lo + t.lo
    return eft_fast_two_sum(r1.hi, lo2)


@always_inline
def dd_sub(a: DD, b: DD) -> DD:
    return dd_add(a, dd_neg(b))


@always_inline
def dd_add_d(a: DD, b: Float64) -> DD:
    """`a + b` where `b` is a float64. 10 flops."""
    var s = eft_two_sum(a.hi, b)
    var lo = s.lo + a.lo
    return eft_fast_two_sum(s.hi, lo)


@always_inline
def dd_mul(a: DD, b: DD) -> DD:
    """`a * b`, ~2^-106 relative. 9 flops.

    The `a.lo * b.lo` cross term is dropped: it is O(2^-106) *relative to the product*, i.e.
    below what the result format can hold, so keeping it would cost a flop and change
    nothing. Bailey's QD makes the same choice."""
    var p = eft_two_product(a.hi, b.hi)
    var lo = p.lo + (a.hi * b.lo + a.lo * b.hi)
    return eft_fast_two_sum(p.hi, lo)


@always_inline
def dd_mul_d(a: DD, b: Float64) -> DD:
    """`a * b` where `b` is a float64. 6 flops, and exact in `b`."""
    var p = eft_two_product(a.hi, b)
    var lo = p.lo + a.lo * b
    return eft_fast_two_sum(p.hi, lo)


def dd_div(a: DD, b: DD) -> DD:
    """`a / b` by three float64 Newton corrections (Bailey's `accurate_div`).

    Returns a NaN pair when `b` is zero rather than raising: this is an inner arithmetic
    primitive on a hot path, and the drivers that call it check the divisor first and report
    a status (rule 4). A caller using `dd_div` directly must do the same."""
    if b.hi == 0.0 and b.lo == 0.0:
        var nan = 0.0 / 0.0
        return DD(nan, nan)
    var q1 = a.hi / b.hi
    var r = dd_sub(a, dd_mul_d(b, q1))
    var q2 = r.hi / b.hi
    r = dd_sub(r, dd_mul_d(b, q2))
    var q3 = r.hi / b.hi
    var q = eft_fast_two_sum(q1, q2)
    return dd_add_d(q, q3)


def dd_sqrt(a: DD) -> DD:
    """`sqrt(a)` by one Newton step from the float64 square root. ~2^-106 relative.

    `sqrt(0)` is `0`. A negative radicand has no real square root, so it returns a NaN pair
    — the drivers check the sign first and return `EFT_ERR_NEGATIVE_RADICAND` rather than
    letting a NaN travel (rule 4)."""
    if a.hi == 0.0 and a.lo == 0.0:
        return DD(0.0, 0.0)
    if a.hi < 0.0:
        var nan = 0.0 / 0.0
        return DD(nan, nan)
    var x = 1.0 / sqrt(a.hi)
    var ax = a.hi * x
    var t = dd_sub(a, eft_two_product(ax, ax))
    var corr = t.hi * (x * 0.5)
    return eft_two_sum(ax, corr)


# ── compensated reductions ───────────────────────────────────────────────────


def _dot2(x: List[Float64], y: List[Float64], n: Int) -> DD:
    """Ogita-Rump-Oishi Dot2 over `x[0..n)` and `y[0..n)`. Caller has bounds-checked `n`.

    Internal: takes an unchecked `n` because it sits inside the QR inner loop. The public
    entry point is `eft_dot2`, which validates. Rule 1's guard belongs at the boundary, not
    once per iteration."""
    if n <= 0:
        return DD(0.0, 0.0)
    var p = eft_two_product(x[0], y[0])
    var s = p.lo
    var hi = p.hi
    for i in range(1, n):
        var h = eft_two_product(x[i], y[i])
        var t = eft_two_sum(hi, h.hi)
        hi = t.hi
        s = s + (h.lo + t.lo)
    return eft_fast_two_sum(hi, s)


def _sum2(x: List[Float64], n: Int) -> DD:
    """Ogita-Rump-Oishi Sum2 over `x[0..n)`. Caller has bounds-checked `n`.

    Unlike `kahan_sum` this keeps the accumulated error term in the result, which is what
    makes it composable into double-double arithmetic. It is still not associative and still
    not chunk-invariant — `determinism.reduce_det`'s note applies here unchanged."""
    if n <= 0:
        return DD(0.0, 0.0)
    var hi = x[0]
    var s: Float64 = 0.0
    for i in range(1, n):
        var t = eft_two_sum(hi, x[i])
        hi = t.hi
        s = s + t.lo
    return eft_fast_two_sum(hi, s)


# ── the runtime self-check: three cases plain float64 provably gets wrong ─────


def eft_selfcheck_code() -> Int:
    """`EFT_OK` iff the FMA is fused, the compiler does not contract, and `+` is not reassociated.

    Every case here is one where plain float64 gives a *different* answer, so passing cannot
    happen by accident. The inputs are built by arithmetic on `1.0` and `2.0` rather than
    written as literals so that a constant-folding compiler evaluating this at compile time
    still has to model the same rounding the hardware would.

    @capability eft_selfcheck_code
    complexity: O(1)
    @endcapability
    """
    # 1 + 2^-52: the smallest float64 above 1 with a nonzero product tail.
    var eps: Float64 = 1.0
    for _ in range(52):
        eps = eps * 0.5
    var a = 1.0 + eps
    var p = a * a
    var e = a.fma(a, -p)
    # exact tail is 2^-104
    var tail: Float64 = 1.0
    for _ in range(104):
        tail = tail * 0.5
    if e != tail:
        return EFT_ERR_NO_FUSED_MULTIPLY_ADD
    # the same expression without an FMA must lose the tail entirely
    if (a * a) - p != 0.0:
        return EFT_ERR_NO_FUSED_MULTIPLY_ADD

    # contraction check: p must BE the rounded product, or two_product is meaningless
    var q = a * a
    if q - a * a != 0.0:
        return EFT_ERR_COMPILER_CONTRACTS_FMA

    # reassociation check: (2^53 + 1) + 1 != 2^53 + (1 + 1) in float64
    var u: Float64 = 1.0
    for _ in range(53):
        u = u * 2.0
    var v: Float64 = 1.0
    if (u + v) + v == u + (v + v):
        return EFT_ERR_COMPILER_REASSOCIATES
    # and (u + v) - u must be recomputed, not folded to v
    var s = u + v
    if s - u == v:
        return EFT_ERR_COMPILER_REASSOCIATES
    return EFT_OK


# ── public, contract-shaped entry points ─────────────────────────────────────


def eft_two_sum_pair(a: Float64, b: Float64) -> DD:
    """Knuth two_sum as a returned pair. See `eft_two_sum`.

    @capability eft_two_sum_pair
    complexity: O(1)
    @endcapability
    """
    return eft_two_sum(a, b)


def eft_two_product_pair(a: Float64, b: Float64) -> DD:
    """Dekker two_product as a returned pair. See `eft_two_product`.

    @capability eft_two_product_pair
    complexity: O(1)
    @endcapability
    """
    return eft_two_product(a, b)


def eft_dd_add(a_hi: Float64, a_lo: Float64, b_hi: Float64, b_lo: Float64) -> DD:
    """Double-double sum of `(a_hi, a_lo)` and `(b_hi, b_lo)`.

    @capability eft_dd_add
    complexity: O(1)
    @endcapability
    """
    return dd_add(DD(a_hi, a_lo), DD(b_hi, b_lo))


def eft_dd_mul(a_hi: Float64, a_lo: Float64, b_hi: Float64, b_lo: Float64) -> DD:
    """Double-double product of `(a_hi, a_lo)` and `(b_hi, b_lo)`.

    @capability eft_dd_mul
    complexity: O(1)
    @endcapability
    """
    return dd_mul(DD(a_hi, a_lo), DD(b_hi, b_lo))


def eft_dd_div(a_hi: Float64, a_lo: Float64, b_hi: Float64, b_lo: Float64) -> DD:
    """Double-double quotient. A zero divisor returns a NaN pair; check first.

    @capability eft_dd_div
    complexity: O(1)
    @endcapability
    """
    return dd_div(DD(a_hi, a_lo), DD(b_hi, b_lo))


def eft_dd_sqrt(a_hi: Float64, a_lo: Float64) -> DD:
    """Double-double square root. A negative radicand returns a NaN pair; check first.

    @capability eft_dd_sqrt
    complexity: O(1)
    @endcapability
    """
    return dd_sqrt(DD(a_hi, a_lo))


@fieldwise_init
struct EftReduction(Copyable, Movable):
    """A compensated reduction: `hi + lo` is the value, `status` says whether it exists.

    Absent, not zero, when the input is unusable (rule 4): a length that does not match the
    buffer or a non-finite element gives `status != EFT_OK` and `hi = lo = 0`, and the
    caller must branch on `status` — `0.0` is also a perfectly good sum of nothing, so the
    number alone cannot carry the distinction."""

    var hi: Float64
    var lo: Float64
    var status: Int
    var terms: Int


def eft_dot2(x: List[Float64], y: List[Float64], n: Int) -> EftReduction:
    """Compensated dot product of the first `n` elements, ~2^-106 relative.

    `n` is an element count over BOTH buffers and is validated against both real lengths
    before any element is read: an unchecked count past the end is an uncatchable abort that
    takes the worker down, not an exception (rule 1).

    @capability eft_dot2
    complexity: O(n)
    counts:
    - n == len(x, y) [kernel_validated]
    - dim n <= EFT_MAX_TERMS [kernel_validated]
    @endcapability
    """
    if n < 0 or n > EFT_MAX_TERMS or n > len(x) or n > len(y):
        return EftReduction(0.0, 0.0, EFT_ERR_INVALID_LENGTH, 0)
    for i in range(n):
        if isnan(x[i]) or isinf(x[i]) or isnan(y[i]) or isinf(y[i]):
            return EftReduction(0.0, 0.0, EFT_ERR_NON_FINITE_INPUT, 0)
    var r = _dot2(x, y, n)
    return EftReduction(r.hi, r.lo, EFT_OK, n)


def eft_sum2(x: List[Float64], n: Int) -> EftReduction:
    """Compensated sum of the first `n` elements, keeping the error term.

    @capability eft_sum2
    complexity: O(n)
    counts:
    - n == len(x) [kernel_validated]
    - dim n <= EFT_MAX_TERMS [kernel_validated]
    @endcapability
    """
    if n < 0 or n > EFT_MAX_TERMS or n > len(x):
        return EftReduction(0.0, 0.0, EFT_ERR_INVALID_LENGTH, 0)
    for i in range(n):
        if isnan(x[i]) or isinf(x[i]):
            return EftReduction(0.0, 0.0, EFT_ERR_NON_FINITE_INPUT, 0)
    var r = _sum2(x, n)
    return EftReduction(r.hi, r.lo, EFT_OK, n)


def eft_kahan_sum_f64(x: List[Float64]) -> Float64:
    """The frozen `numerical_stability.kahan_sum`, forwarded unchanged (rule 3).

    Present so that "compensated float64 sum" has one definition in the tree and a
    comparison against `eft_sum2` is a comparison against the shipped kernel rather than a
    private copy of it.

    @capability eft_kahan_sum_f64
    complexity: O(n)
    @endcapability
    """
    return kahan_sum(x)
