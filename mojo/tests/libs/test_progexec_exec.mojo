"""test_progexec_exec.mojo — known-value tests for `progexec.exec`, over REAL FinQA gold
programs (github.com/czyssrs/FinQA, MIT licensed) plus the adversarial guard cases rule 1
requires for every dimension argument.

Hand-written. Registered in `tests/generate_mojo_tests.py` HANDWRITTEN_TESTS; the generator
destroys any unregistered `test_<module>.mojo` in this directory.

Every numeric golden below is the dataset's own `exe_ans` for the named question id — not
computed by this test, not computed by `progexec` and checked against itself. The full
8281-program cross-check against the real dataset lives in
`benchmarks/external_baselines/finqa_exec/score.py`; this suite is the fast, CI-integrated
sample plus the guard paths that suite does not exercise (a benchmark run never sends a
malformed program on purpose).
"""
from progexec.contract import ARG_LITERAL, ARG_REF, ARG_TABLE_ROW
from progexec.exec import progexec_run_flat


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── ADI/2009/page_49.pdf-1: divide(100, 100), divide(3.8, #0) -> exe_ans 3.8 ──
    var ops1 = List[Int]()
    ops1.append(3)
    ops1.append(3)
    var a1k1 = List[Int]()
    a1k1.append(ARG_LITERAL)
    a1k1.append(ARG_LITERAL)
    var a1n1 = List[Float64]()
    a1n1.append(100.0)
    a1n1.append(3.8)
    var a2k1 = List[Int]()
    a2k1.append(ARG_LITERAL)
    a2k1.append(ARG_REF)
    var a2n1 = List[Float64]()
    a2n1.append(100.0)
    a2n1.append(0.0)
    var empty_tv = List[Float64]()
    var toff1 = List[Int]()
    toff1.append(0)
    toff1.append(0)
    var tlen1 = List[Int]()
    tlen1.append(0)
    tlen1.append(0)
    var r1 = progexec_run_flat(ops1, a1k1, a1n1, a2k1, a2n1, empty_tv, toff1, tlen1, 2)
    if r1.present and not r1.is_bool and r1.value == 3.8:
        passed += 1
        print("  ✅ ADI/2009/page_49.pdf-1 -> 3.8")
    else:
        failed += 1
        print("  ❌ ADI/2009/page_49.pdf-1 diverged:", r1.value, r1.present, r1.status)

    # ── IPG/2009/page_89.pdf-3: subtract(34.8,1.2), divide(#0,34.8), multiply(#1,const_100)
    #    -> exe_ans 96.55172. Chained 3-step with a percentage scale, and one of the 130
    #    real programs a round-every-step naive re-implementation gets wrong (96.552). ──
    var ops2 = List[Int]()
    ops2.append(1)  # subtract
    ops2.append(3)  # divide
    ops2.append(2)  # multiply
    var a1k2 = List[Int]()
    a1k2.append(ARG_LITERAL)
    a1k2.append(ARG_REF)
    a1k2.append(ARG_REF)
    var a1n2 = List[Float64]()
    a1n2.append(34.8)
    a1n2.append(0.0)
    a1n2.append(1.0)
    var a2k2 = List[Int]()
    a2k2.append(ARG_LITERAL)
    a2k2.append(ARG_LITERAL)
    a2k2.append(ARG_LITERAL)
    var a2n2 = List[Float64]()
    a2n2.append(1.2)
    a2n2.append(34.8)
    a2n2.append(100.0)
    var toff2 = List[Int]()
    toff2.append(0)
    toff2.append(0)
    toff2.append(0)
    var tlen2 = List[Int]()
    tlen2.append(0)
    tlen2.append(0)
    tlen2.append(0)
    var r2 = progexec_run_flat(ops2, a1k2, a1n2, a2k2, a2n2, empty_tv, toff2, tlen2, 3)
    if r2.present and not r2.is_bool and r2.value == 96.55172:
        passed += 1
        print("  ✅ IPG/2009/page_89.pdf-3 -> 96.55172")
    else:
        failed += 1
        print("  ❌ IPG/2009/page_89.pdf-3 diverged:", r2.value, r2.present, r2.status)

    # ── ABMD/2012/page_75.pdf-1: multiply(607,18.13), multiply(#0,const_1000),
    #    multiply(3.3,const_1000000), greater(#1,#2) -> exe_ans "yes" ──
    var ops3 = List[Int]()
    ops3.append(2)
    ops3.append(2)
    ops3.append(2)
    ops3.append(5)  # greater
    var a1k3 = List[Int]()
    a1k3.append(ARG_LITERAL)
    a1k3.append(ARG_REF)
    a1k3.append(ARG_LITERAL)
    a1k3.append(ARG_REF)
    var a1n3 = List[Float64]()
    a1n3.append(607.0)
    a1n3.append(0.0)
    a1n3.append(3.3)
    a1n3.append(1.0)
    var a2k3 = List[Int]()
    a2k3.append(ARG_LITERAL)
    a2k3.append(ARG_LITERAL)
    a2k3.append(ARG_LITERAL)
    a2k3.append(ARG_REF)
    var a2n3 = List[Float64]()
    a2n3.append(18.13)
    a2n3.append(1000.0)
    a2n3.append(1000000.0)
    a2n3.append(2.0)
    var toff3 = List[Int]()
    for _ in range(4):
        toff3.append(0)
    var tlen3 = List[Int]()
    for _ in range(4):
        tlen3.append(0)
    var r3 = progexec_run_flat(ops3, a1k3, a1n3, a2k3, a2n3, empty_tv, toff3, tlen3, 4)
    if r3.present and r3.is_bool and r3.bool_value:
        passed += 1
        print("  ✅ ABMD/2012/page_75.pdf-1 -> yes")
    else:
        failed += 1
        print("  ❌ ABMD/2012/page_75.pdf-1 diverged:", r3.bool_value, r3.present, r3.status)

    # ── ORLY/2009/page_77.pdf-3: table_average(interest rate swaps, none), row [13053,
    #    18874] -> exe_ans 15963.5. table_average is plain sum/n, not reduce_mean's
    #    Welford mean (see contract.mojo) — this is the assertion that matters here. ──
    var ops4 = List[Int]()
    ops4.append(9)  # table_average
    var a1k4 = List[Int]()
    a1k4.append(ARG_TABLE_ROW)
    var a1n4 = List[Float64]()
    a1n4.append(0.0)
    var a2k4 = List[Int]()
    a2k4.append(ARG_LITERAL)
    var a2n4 = List[Float64]()
    a2n4.append(0.0)
    var tv4 = List[Float64]()
    tv4.append(13053.0)
    tv4.append(18874.0)
    var toff4 = List[Int]()
    toff4.append(0)
    var tlen4 = List[Int]()
    tlen4.append(2)
    var r4 = progexec_run_flat(ops4, a1k4, a1n4, a2k4, a2n4, tv4, toff4, tlen4, 1)
    if r4.present and not r4.is_bool and r4.value == 15963.5:
        passed += 1
        print("  ✅ ORLY/2009/page_77.pdf-3 (table_average) -> 15963.5")
    else:
        failed += 1
        print("  ❌ ORLY/2009/page_77.pdf-3 diverged:", r4.value, r4.present, r4.status)

    # ── MKTX/2005/page_40.pdf-2: table_max(..), row [13.14, 10.64] -> exe_ans 13.14 ──
    var ops5 = List[Int]()
    ops5.append(6)  # table_max
    var a1k5 = List[Int]()
    a1k5.append(ARG_TABLE_ROW)
    var a1n5 = List[Float64]()
    a1n5.append(0.0)
    var a2k5 = List[Int]()
    a2k5.append(ARG_LITERAL)
    var a2n5 = List[Float64]()
    a2n5.append(0.0)
    var tv5 = List[Float64]()
    tv5.append(13.14)
    tv5.append(10.64)
    var toff5 = List[Int]()
    toff5.append(0)
    var tlen5 = List[Int]()
    tlen5.append(2)
    var r5 = progexec_run_flat(ops5, a1k5, a1n5, a2k5, a2n5, tv5, toff5, tlen5, 1)
    if r5.present and r5.value == 13.14:
        passed += 1
        print("  ✅ MKTX/2005/page_40.pdf-2 (table_max) -> 13.14")
    else:
        failed += 1
        print("  ❌ MKTX/2005/page_40.pdf-2 diverged:", r5.value, r5.present, r5.status)

    # ── GS/2012/page_95.pdf-2: table_min(icbc, none), row [208, 212] -> exe_ans 208 ──
    var ops6 = List[Int]()
    ops6.append(7)  # table_min
    var a1k6 = List[Int]()
    a1k6.append(ARG_TABLE_ROW)
    var a1n6 = List[Float64]()
    a1n6.append(0.0)
    var a2k6 = List[Int]()
    a2k6.append(ARG_LITERAL)
    var a2n6 = List[Float64]()
    a2n6.append(0.0)
    var tv6 = List[Float64]()
    tv6.append(208.0)
    tv6.append(212.0)
    var toff6 = List[Int]()
    toff6.append(0)
    var tlen6 = List[Int]()
    tlen6.append(2)
    var r6 = progexec_run_flat(ops6, a1k6, a1n6, a2k6, a2n6, tv6, toff6, tlen6, 1)
    if r6.present and r6.value == 208.0:
        passed += 1
        print("  ✅ GS/2012/page_95.pdf-2 (table_min) -> 208.0")
    else:
        failed += 1
        print("  ❌ GS/2012/page_95.pdf-2 diverged:", r6.value, r6.present, r6.status)

    # ── ORLY/2009/page_77.pdf-2: table_sum(interest rate swaps, none) -> exe_ans 31927 ──
    var ops7 = List[Int]()
    ops7.append(8)  # table_sum
    var a1k7 = List[Int]()
    a1k7.append(ARG_TABLE_ROW)
    var a1n7 = List[Float64]()
    a1n7.append(0.0)
    var a2k7 = List[Int]()
    a2k7.append(ARG_LITERAL)
    var a2n7 = List[Float64]()
    a2n7.append(0.0)
    var tv7 = List[Float64]()
    tv7.append(13053.0)
    tv7.append(18874.0)
    var toff7 = List[Int]()
    toff7.append(0)
    var tlen7 = List[Int]()
    tlen7.append(2)
    var r7 = progexec_run_flat(ops7, a1k7, a1n7, a2k7, a2n7, tv7, toff7, tlen7, 1)
    if r7.present and r7.value == 31927.0:
        passed += 1
        print("  ✅ ORLY/2009/page_77.pdf-2 (table_sum) -> 31927.0")
    else:
        failed += 1
        print("  ❌ ORLY/2009/page_77.pdf-2 diverged:", r7.value, r7.present, r7.status)

    # ── guard: n_steps <= 0 is refused, not indexed ──────────────────────────────
    var r8 = progexec_run_flat(ops1, a1k1, a1n1, a2k1, a2n1, empty_tv, toff1, tlen1, 0)
    if not r8.present:
        passed += 1
        print("  ✅ n_steps == 0 is refused (absent, not a fabricated zero)")
    else:
        failed += 1
        print("  ❌ n_steps == 0 produced a plausible-looking answer")

    # ── guard: n_steps claims more than the lists actually hold (rule 1) ─────────
    var short_ops = List[Int]()
    short_ops.append(0)
    var r9 = progexec_run_flat(short_ops, short_ops, empty_tv, short_ops, empty_tv, empty_tv, short_ops, short_ops, 5)
    if not r9.present:
        passed += 1
        print("  ✅ n_steps=5 against 1-element lists is refused, not read past the end")
    else:
        failed += 1
        print("  ❌ a short list was indexed past its own length")

    # ── guard: a forward/self reference is refused ───────────────────────────────
    var ops10 = List[Int]()
    ops10.append(0)  # add
    var a1k10 = List[Int]()
    a1k10.append(ARG_REF)
    var a1n10 = List[Float64]()
    a1n10.append(0.0)  # step 0 referencing itself
    var a2k10 = List[Int]()
    a2k10.append(ARG_LITERAL)
    var a2n10 = List[Float64]()
    a2n10.append(1.0)
    var toff10 = List[Int]()
    toff10.append(0)
    var tlen10 = List[Int]()
    tlen10.append(0)
    var r10 = progexec_run_flat(ops10, a1k10, a1n10, a2k10, a2n10, empty_tv, toff10, tlen10, 1)
    if not r10.present:
        passed += 1
        print("  ✅ a self-reference (#0 at step 0) is refused")
    else:
        failed += 1
        print("  ❌ a self-reference was silently resolved")

    # ── guard: table_offset/table_len past the real table_values length ─────────
    var ops11 = List[Int]()
    ops11.append(9)  # table_average
    var a1k11 = List[Int]()
    a1k11.append(ARG_TABLE_ROW)
    var a1n11 = List[Float64]()
    a1n11.append(0.0)
    var a2k11 = List[Int]()
    a2k11.append(ARG_LITERAL)
    var a2n11 = List[Float64]()
    a2n11.append(0.0)
    var tv11 = List[Float64]()
    tv11.append(1.0)
    var toff11 = List[Int]()
    toff11.append(0)
    var tlen11 = List[Int]()
    tlen11.append(5)  # claims 5 elements from a 1-element table
    var r11 = progexec_run_flat(ops11, a1k11, a1n11, a2k11, a2n11, tv11, toff11, tlen11, 1)
    if not r11.present:
        passed += 1
        print("  ✅ a table row past the real table_values length is refused, not read past it")
    else:
        failed += 1
        print("  ❌ a table row length was trusted past the buffer it names")

    # ── guard: divide by zero is an absence, not inf ─────────────────────────────
    var ops12 = List[Int]()
    ops12.append(3)  # divide
    var a1k12 = List[Int]()
    a1k12.append(ARG_LITERAL)
    var a1n12 = List[Float64]()
    a1n12.append(1.0)
    var a2k12 = List[Int]()
    a2k12.append(ARG_LITERAL)
    var a2n12 = List[Float64]()
    a2n12.append(0.0)
    var toff12 = List[Int]()
    toff12.append(0)
    var tlen12 = List[Int]()
    tlen12.append(0)
    var r12 = progexec_run_flat(ops12, a1k12, a1n12, a2k12, a2n12, empty_tv, toff12, tlen12, 1)
    if not r12.present:
        passed += 1
        print("  ✅ divide(1, 0) is refused, not returned as inf")
    else:
        failed += 1
        print("  ❌ divide(1, 0) returned a plausible-looking number")

    # ── guard: an unknown op code is refused ─────────────────────────────────────
    var ops13 = List[Int]()
    ops13.append(99)
    var r13 = progexec_run_flat(ops13, a1k12, a1n12, a2k12, a2n12, empty_tv, toff12, tlen12, 1)
    if not r13.present:
        passed += 1
        print("  ✅ an unknown op code is refused")
    else:
        failed += 1
        print("  ❌ an unknown op code produced a plausible-looking number")

    print("  [progexec.exec] Passed:", passed, "Failed:", failed)
