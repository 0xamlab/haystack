"""test_progexec_roundexact.mojo — known-value tests for `progexec.roundexact`.

Hand-written. Registered in `tests/generate_mojo_tests.py` HANDWRITTEN_TESTS; the generator
destroys any unregistered `test_<module>.mojo` in this directory.

Anti-vacuity, the same discipline `test_exactnum_eft.mojo` uses: a rounder that has silently
degraded to "multiply by scale, round, divide back" (Mojo's own builtin `round(x, ndigits)`,
measured to do exactly this) still passes any test whose expected value that naive shape
already gets right. Every non-tie assertion below is chosen so THE NAIVE SHAPE PROVABLY
FAILS IT — these are six real FinQA gold programs (github.com/czyssrs/FinQA, MIT licensed),
not constructed examples, where `round(raw, 5)` (Mojo builtin, measured live) disagrees with
CPython's `round(raw, 5)` (the value `exe_ans` in the dataset actually is):

    program                                                          raw            gold
    HII/2011/page_100.pdf-3   multiply(83.7,7.81%),divide(#0,2)       3.268485       3.26849
    RE/2010/page_42.pdf-4     subtract(364.3,160.0),divide(#0,160.0) 1.276875       1.27687
    CAT/2017/page_69.pdf-2    ...,divide(#1,#0)                     -0.771875      -0.77187
    IP/2012/page_84.pdf-2     divide(3.7,32)                         0.115625       0.11563
    ETR/2017/page_143.pdf-2   subtract(857679,760000),divide(#0,..)  0.128525       0.12853
    HIG/2011/page_53.pdf-1    divide(57,320)                         0.178125       0.17813

The genuine-tie cases (0.125, -0.125, 1.5, 2.5) are the OTHER half of the anti-vacuity
argument: a rounder that always rounds half away from zero (this tree's own
`currency.round_currency`, independently measured) passes the six above on five of six by
getting the corrupted tie's direction right for the wrong reason, but fails a REAL tie in
the opposite, checkable way (`round_currency(2.5, 0) == 3.0`; true round-half-to-even is
`2.0`). See `roundexact.mojo`'s own module docstring for that count.
"""
from progexec.roundexact import round_half_even_scaled

comptime SCALE5: Float64 = 100000.0
comptime SCALE2: Float64 = 100.0
comptime SCALE0: Float64 = 1.0


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── six real FinQA gold programs where the naive scale-multiply-round trips ──
    var raw_hii = (83.7 * (7.81 / 100.0)) / 2.0
    if round_half_even_scaled(raw_hii, SCALE5) == 3.26849:
        passed += 1
        print("  ✅ HII/2011/page_100.pdf-3: 3.268485 -> 3.26849, not the corrupted 3.26848")
    else:
        failed += 1
        print("  ❌ HII/2011/page_100.pdf-3 diverged from exe_ans")

    var raw_re = (364.3 - 160.0) / 160.0
    if round_half_even_scaled(raw_re, SCALE5) == 1.27687:
        passed += 1
        print("  ✅ RE/2010/page_42.pdf-4: 1.276875 -> 1.27687, not the corrupted 1.27688")
    else:
        failed += 1
        print("  ❌ RE/2010/page_42.pdf-4 diverged from exe_ans")

    var denom_cat = 1000.0 * 1.6
    var raw_cat = (365.0 - denom_cat) / denom_cat
    if round_half_even_scaled(raw_cat, SCALE5) == -0.77187:
        passed += 1
        print("  ✅ CAT/2017/page_69.pdf-2: -0.771875 -> -0.77187, not the corrupted -0.77188")
    else:
        failed += 1
        print("  ❌ CAT/2017/page_69.pdf-2 diverged from exe_ans")

    var raw_ip = 3.7 / 32.0
    if round_half_even_scaled(raw_ip, SCALE5) == 0.11563:
        passed += 1
        print("  ✅ IP/2012/page_84.pdf-2: 0.115625 -> 0.11563, not the corrupted 0.11562")
    else:
        failed += 1
        print("  ❌ IP/2012/page_84.pdf-2 diverged from exe_ans")

    var raw_etr = (857679.0 - 760000.0) / 760000.0
    if round_half_even_scaled(raw_etr, SCALE5) == 0.12853:
        passed += 1
        print("  ✅ ETR/2017/page_143.pdf-2: 0.128525 -> 0.12853, not the corrupted 0.12852")
    else:
        failed += 1
        print("  ❌ ETR/2017/page_143.pdf-2 diverged from exe_ans")

    var raw_hig = 57.0 / 320.0
    if round_half_even_scaled(raw_hig, SCALE5) == 0.17813:
        passed += 1
        print("  ✅ HIG/2011/page_53.pdf-1: 0.178125 -> 0.17813, not the corrupted 0.17812")
    else:
        failed += 1
        print("  ❌ HIG/2011/page_53.pdf-1 diverged from exe_ans")

    # ── genuine exact ties: round-half-to-even, not round-half-away ──────────────
    if round_half_even_scaled(0.125, SCALE2) == 0.12:
        passed += 1
        print("  ✅ 0.125 at 2dp is an exact tie -> 0.12 (2 is even), not round_currency's 0.13")
    else:
        failed += 1
        print("  ❌ genuine tie 0.125 did not round to even")

    if round_half_even_scaled(-0.125, SCALE2) == -0.12:
        passed += 1
        print("  ✅ -0.125 at 2dp -> -0.12, ties-to-even is sign-symmetric")
    else:
        failed += 1
        print("  ❌ genuine tie -0.125 did not round to even")

    if round_half_even_scaled(1.5, SCALE0) == 2.0 and round_half_even_scaled(2.5, SCALE0) == 2.0:
        passed += 1
        print("  ✅ 1.5 -> 2.0 and 2.5 -> 2.0: both ties resolve to the EVEN neighbour")
    else:
        failed += 1
        print("  ❌ integer ties did not resolve to even")

    # ── a non-tie the naive multiply corrupts INTO an apparent tie (2.675, 2dp) ──
    if round_half_even_scaled(2.675, SCALE2) == 2.67:
        passed += 1
        print("  ✅ 2.675 at 2dp is NOT a real tie (true value is 2.67499999999999982...) -> 2.67")
    else:
        failed += 1
        print("  ❌ 2.675 rounded to the naive-multiply-corrupted 2.68")

    # ── zero and sign round-trip ──────────────────────────────────────────────────
    if round_half_even_scaled(0.0, SCALE5) == 0.0:
        passed += 1
        print("  ✅ zero round-trips")
    else:
        failed += 1
        print("  ❌ zero did not round-trip")

    if round_half_even_scaled(-3.14159265, SCALE5) == -3.14159:
        passed += 1
        print("  ✅ an ordinary negative value rounds like its positive mirror")
    else:
        failed += 1
        print("  ❌ sign handling diverged from the unsigned case")

    print("  [progexec.roundexact] Passed:", passed, "Failed:", failed)
