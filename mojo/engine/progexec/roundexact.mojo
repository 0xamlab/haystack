"""
progexec.roundexact — round-half-to-even at a caller-supplied decimal scale, decided from
the EXACT value of `x * scale`, matching CPython's `round(x, n)` bit-for-bit.

MEASURED, not assumed: Mojo's own builtin `round(x, ndigits)` computes `x * 10^n` as a
single float64 multiply and rounds THAT — which is a DOUBLE rounding whenever the true
value of `x * 10^n` sits within about half an ULP of an integer-plus-one-half. Six real
FinQA gold programs land exactly there:

    fn (Mojo builtin round(_, 5))          correct (CPython round(_, 5))
    HII/2011/page_100.pdf-3   3.26848      3.26849
    RE/2010/page_42.pdf-4     1.27688      1.27687
    CAT/2017/page_69.pdf-2   -0.77188     -0.77187
    IP/2012/page_84.pdf-2     0.11562      0.11563
    ETR/2017/page_143.pdf-2   0.12852      0.12853
    HIG/2011/page_53.pdf-1    0.17812      0.17813

(reproduced live: `mojo run` on the raw arithmetic chain for each of the six, both with the
builtin `round` and with `round_half_even_scaled` below — see
`benchmarks/external_baselines/finqa_exec/`.)

`currency.round_currency` is a second, independently wrong candidate, for two SEPARATE
reasons, each measured rather than assumed: it also forms `amount * mult` as a single
float64 multiply (`floor(shifted + 0.5) / mult`), and separately its tie-break is
round-HALF-UP, not the "banker's rounding" its own docstring claims (`round_currency(2.5,
0)` returns `3.0`; true round-half-to-even returns `2.0`). The two defects do not always
fail on the same inputs as the builtin `round` above — round-half-up happens to recover
the right answer on five of the six cases above by getting the DIRECTION of the corrupted
tie right for the wrong reason — but produces its OWN five real divergences from
`exe_ans`, confirmed by running it: `INTC/2016/page_33.pdf-3` (`divide(31.5, 19.2)`,
correct `1.64062`, `round_currency` returns `1.64063`), `RE/2010/page_42.pdf-4` (shared
with the list above), `ZBH/2008/page_70.pdf-2` (`divide(5.1, 19.2)`, correct `0.26562`,
returns `0.26563`), `CMCSA/2008/page_59.pdf-4` (`divide(1.05, 3.2)`, correct `0.32812`,
returns `0.32813`), `AMT/2012/page_118.pdf-2` (`divide(151.7, 800)`, correct `0.18962`,
returns `0.18963`) — all five are ties that round-half-up rounds up on principle,
regardless of which side of the tie the true value actually falls on. Not modified
because it is a frozen kernel serving other callers under its documented (if mislabelled)
contract; named here as evidence that reaching for the obvious tool in THIS tree also
gets this wrong, not only a hypothetical naive port.

How this avoids the same trap
------------------------------
`exactnum.eft.eft_two_product(x, scale)` forms `x * scale` EXACTLY as a double-double
`(hi, lo)` — no rounding at all, per that module's own measured FMA guarantee. Rounding
`hi` alone to the nearest integer (`round(hi, 0)`, which has no scaling step and therefore
no double-rounding exposure) is correct unless the true value `hi + lo` sits on the far
side of a tie from `hi` alone — which is exactly the boundary case above. The residual
`(hi - round(hi)) + lo` is then combined with `exactnum.eft.eft_two_sum` into a clean
(frac_hi, frac_lo) pair, and THAT pair, not a re-multiplied approximation, decides whether
the true value crossed the boundary and which way a genuine exact tie breaks.

@capability-module
deterministic: true
stateful: false
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute
golden_vectors: mojo/tests/libs/test_progexec_roundexact.mojo
benchmark: benchmarks/external_baselines/finqa_exec/
docs: docs/mojo/new-kernel-package-rules.md
version_introduced: 2026-08
deprecation_state: active
@endcapability
"""

from exactnum.eft import eft_two_product, eft_two_sum


fn _is_even_integer_valued(x: Float64) -> Bool:
    """`x` is already integer-valued (caller's job); True when that integer is even."""
    return (Int(x) % 2) == 0


fn round_half_even_scaled(x: Float64, scale: Float64) -> Float64:
    """Round `x` to the decimal place implied by `scale` (e.g. `scale=100000.0` for five
    decimal places), round-half-to-even, decided from the exact value of `x * scale`.

    `scale` must be a positive, exactly-representable power of ten supplied by the caller
    as a literal (`progexec.contract.PROGEXEC_ROUND_SCALE`) — never computed here via
    `pow`, which is a transcendental and not guaranteed exact even for integer exponents.

    Matches CPython's `round(x, n)` for every finite, non-zero `x` at a magnitude where
    `x * scale` does not overflow float64 range, which covers every value this driver's
    caller (`progexec.exec`) can produce from real FinQA-shaped arithmetic.

    @capability round_half_even_scaled
    complexity: O(1)
    @endcapability
    """
    if x == 0.0:
        return x
    var neg = x < 0.0
    var ax = -x if neg else x
    var p = eft_two_product(ax, scale)  # p.hi + p.lo == ax * scale, exactly
    var r = round(p.hi, 0)  # nearest integer to hi alone; ndigits=0 has no scaling step
    var d1 = eft_two_sum(p.hi, -r)  # d1.hi + d1.lo == p.hi - r, exactly
    var resid = d1.lo + p.lo  # both terms are at most ulp(p.hi)/2-ish; a plain add is safe
    var d2 = eft_two_sum(d1.hi, resid)  # clean (frac_hi, frac_lo) pair
    var frac_hi = d2.hi
    var frac_lo = d2.lo

    var result_int: Float64
    if frac_hi > 0.5:
        result_int = r + 1.0
    elif frac_hi < -0.5:
        result_int = r - 1.0
    elif frac_hi == 0.5:
        if frac_lo > 0.0:
            result_int = r + 1.0
        elif frac_lo < 0.0:
            result_int = r
        else:
            result_int = r if _is_even_integer_valued(r) else r + 1.0
    elif frac_hi == -0.5:
        if frac_lo < 0.0:
            result_int = r - 1.0
        elif frac_lo > 0.0:
            result_int = r
        else:
            result_int = r if _is_even_integer_valued(r) else r - 1.0
    else:
        result_int = r

    var out = result_int / scale
    return -out if neg else out
