"""test_sheet_functions.mojo — hand-checkable known values for every
implemented function, in census order (hand-written; registered in
HANDWRITTEN_TESTS).

Each cached value below was computed BY HAND (or by independent arithmetic:
sqrt(32/7), 3600/86400, calendar day counts vs 1899-12-30) and the workbook
must match it EXACTLY — one wrong function means matched_exact drops and the
suite prints which cell diverged. Laziness is semantics and is asserted:
IF(TRUE,1,1/0) is 1 and CHOOSE(1,5,1/0) is 5, never #DIV/0!.
"""

from sheet.api import sheet_eval_cell, sheet_recalc_report
from sheet.values import VK_ERR, VK_NUM, VK_TEXT


def _wb_head() -> String:
    var t = String("SHEETWB\t1\nD\t0\nS\tS\nS\tS2\n")
    # data block: A1:A8 = 2,4,4,4,5,5,7,9 ; B1:B4 = text/mixed ; D1:E3 lookup
    t += "C\t0\tA1\tn\t2\nC\t0\tA2\tn\t4\nC\t0\tA3\tn\t4\nC\t0\tA4\tn\t4\n"
    t += "C\t0\tA5\tn\t5\nC\t0\tA6\tn\t5\nC\t0\tA7\tn\t7\nC\t0\tA8\tn\t9\n"
    t += "C\t0\tB1\ts\tapple\nC\t0\tB2\tn\t10\nC\t0\tB3\ts\tbanana\nC\t0\tB4\tb\t1\n"
    t += "C\t0\tB5\ts\tMAGAÑA\n"  # non-ASCII bytes for the criteria regression
    t += "C\t0\tC2\tn\t20\nC\t0\tC6\tn\t60\n"  # sparse column for the LOOKUP idiom
    t += "C\t0\tD1\tn\t1\nC\t0\tE1\ts\tone\n"
    t += "C\t0\tD2\tn\t3\nC\t0\tE2\ts\tthree\n"
    t += "C\t0\tD3\tn\t5\nC\t0\tE3\ts\tfive\n"
    t += "C\t1\tB1\tn\t777\n"  # S2!B1 for INDIRECT/cross-sheet
    return t^


def _f(cell: String, formula: String, ct: String, cv: String) -> String:
    var t = String("F\t0\t")
    t += cell
    t += "\tn\t"
    t += formula
    t += "\t"
    t += ct
    t += "\t"
    t += cv
    t += "\n"
    return t^


def main() raises:
    var passed = 0
    var failed = 0

    var t = _wb_head()
    var n_formulas = 0
    # ── census order: OFFSET(1) .. DATE(47), every cached value hand-checked ─
    # OFFSET: A2:A3 summed = 4+4 = 8
    t += _f(String("G1"), String("SUM(OFFSET(A1,1,0,2,1))"), String("n"), String("8"))
    # ROW / COLUMN
    t += _f(String("G2"), String("ROW()"), String("n"), String("2"))
    t += _f(String("G3"), String("ROW(A5:A9)"), String("n"), String("5"))
    t += _f(String("G4"), String("COLUMN()"), String("n"), String("7"))
    # MIN ignores text and bools in ranges: min(A)=2 even with B4=TRUE nearby
    t += _f(String("G5"), String("MIN(A1:B8)"), String("n"), String("2"))
    # IF is LAZY: the untaken 1/0 must not fire
    t += _f(String("G6"), String("IF(TRUE,1,1/0)"), String("n"), String("1"))
    # SUM coerces direct text args but ignores range text: "3"+A1 = 5
    t += _f(String("G7"), String("SUM(\"3\",A1)"), String("n"), String("5"))
    t += _f(String("G8"), String("SUM(B1:B3)"), String("n"), String("10"))
    # VLOOKUP exact (4th arg FALSE), approximate, and the ,) empty-arg trap
    t += _f(String("G9"), String("VLOOKUP(3,D1:E3,2,FALSE)"), String("s"), String("three"))
    t += _f(String("G10"), String("VLOOKUP(4,D1:E3,2)"), String("s"), String("three"))
    t += _f(String("G11"), String("VLOOKUP(2,D1:E3,2,)"), String("e"), String("#N/A"))
    # IFERROR
    t += _f(String("G12"), String("IFERROR(1/0,42)"), String("n"), String("42"))
    # COUNTIFS: rows where A>=4 AND A<=5 -> {4,4,4,5,5} = 5
    t += _f(String("G13"), String("COUNTIFS(A1:A8,\">=4\",A1:A8,\"<=5\")"), String("n"), String("5"))
    # TIME wraps: 25h == 1h
    t += _f(String("G14"), String("TIME(25,0,0)"), String("n"), String("0.041666666666666664"))
    # INDIRECT crosses sheets dynamically
    t += _f(String("G15"), String("INDIRECT(\"S2!B\"&1)"), String("n"), String("777"))
    # AND / OR over a range of comparisons
    t += _f(String("G16"), String("AND(A1>1,A8=9)"), String("b"), String("1"))
    t += _f(String("G17"), String("OR(A1>5,A8=9)"), String("b"), String("1"))
    # MAX / AVERAGE / STDEV on the hand column: mean 5, sqrt(32/7)
    t += _f(String("G18"), String("MAX(A1:A8)"), String("n"), String("9"))
    t += _f(String("G19"), String("AVERAGE(A1:A8)"), String("n"), String("5"))
    t += _f(String("G20"), String("STDEV(A1:A8)"), String("n"), String("2.138089935299395"))
    # TEXTAFTER: positive, nth, from-end, not-found default and override
    t += _f(String("G21"), String("TEXTAFTER(\"a-b-c\",\"-\")"), String("s"), String("b-c"))
    t += _f(String("G22"), String("TEXTAFTER(\"a-b-c\",\"-\",2)"), String("s"), String("c"))
    t += _f(String("G23"), String("TEXTAFTER(\"a-b-c\",\"x\")"), String("e"), String("#N/A"))
    t += _f(String("G24"), String("TEXTAFTER(\"a-b-c\",\"x\",1,0,0,\"none\")"), String("s"), String("none"))
    # ABS
    t += _f(String("G25"), String("ABS(-3.5)"), String("n"), String("3.5"))
    # YEAR / MONTH with the 1900 leap bug: serial 60 IS 1900-02-29
    t += _f(String("G26"), String("YEAR(45000)"), String("n"), String("2023"))
    t += _f(String("G27"), String("MONTH(45000)"), String("n"), String("3"))
    t += _f(String("G28"), String("MONTH(60)"), String("n"), String("2"))
    t += _f(String("G29"), String("MONTH(61)"), String("n"), String("3"))
    # COUNTIF with wildcard and inequality
    t += _f(String("G30"), String("COUNTIF(B1:B3,\"*an*\")"), String("n"), String("1"))
    t += _f(String("G31"), String("COUNTIF(A1:A8,\">4\")"), String("n"), String("4"))
    # INDEX / MATCH
    t += _f(String("G32"), String("INDEX(E1:E3,MATCH(5,D1:D3,0))"), String("s"), String("five"))
    t += _f(String("G33"), String("MATCH(4,D1:D3)"), String("n"), String("2"))
    # SUMIF with a shifted sum range: A-values where D>=3 -> rows 2,3 of E?
    # SUMIF(D1:D3,">=3",A1:A3) sums A2+A3 = 8
    t += _f(String("G34"), String("SUMIF(D1:D3,\">=3\",A1:A3)"), String("n"), String("8"))
    # RANK: 7 is 2nd highest; absent 6 is #N/A
    t += _f(String("G35"), String("RANK(7,A1:A8)"), String("n"), String("2"))
    t += _f(String("G36"), String("RANK(6,A1:A8)"), String("e"), String("#N/A"))
    t += _f(String("G37"), String("RANK(4,A1:A8,1)"), String("n"), String("2"))
    # WEEKDAY: Excel calls serial 1 (1900-01-01) Sunday; 45000 is Wednesday
    t += _f(String("G38"), String("WEEKDAY(1)"), String("n"), String("1"))
    t += _f(String("G39"), String("WEEKDAY(45000)"), String("n"), String("4"))
    t += _f(String("G40"), String("WEEKDAY(45000,2)"), String("n"), String("3"))
    # INT floors toward minus infinity
    t += _f(String("G41"), String("INT(-1.5)"), String("n"), String("-2"))
    # LEFT / RIGHT / LEN count CHARACTERS (UTF-8 codepoints)
    t += _f(String("G42"), String("LEFT(\"héllo\",2)"), String("s"), String("hé"))
    t += _f(String("G43"), String("RIGHT(\"héllo\",3)"), String("s"), String("llo"))
    t += _f(String("G44"), String("LEN(\"héllo\")"), String("n"), String("5"))
    # EDATE clamps into short months; EOMONTH finds the month end
    t += _f(String("G45"), String("EDATE(DATE(2024,1,31),1)"), String("n"), String("45351"))
    t += _f(String("G46"), String("EOMONTH(DATE(2023,1,15),0)"), String("n"), String("44957"))
    # SUBSTITUTE, all and nth
    t += _f(String("G47"), String("SUBSTITUTE(\"aaa\",\"a\",\"b\")"), String("s"), String("bbb"))
    t += _f(String("G48"), String("SUBSTITUTE(\"aaa\",\"a\",\"b\",2)"), String("s"), String("aba"))
    # SLN straight-line depreciation
    t += _f(String("G49"), String("SLN(1000,100,9)"), String("n"), String("100"))
    # ROUNDUP / ROUNDDOWN are directed, away from / toward zero
    t += _f(String("G50"), String("ROUNDUP(2.13,1)"), String("n"), String("2.2"))
    t += _f(String("G51"), String("ROUNDDOWN(-2.19,1)"), String("n"), String("-2.1"))
    t += _f(String("G52"), String("ROUNDUP(-2.13,1)"), String("n"), String("-2.2"))
    # VALUE
    t += _f(String("G53"), String("VALUE(\" 12.5 \")"), String("n"), String("12.5"))
    t += _f(String("G54"), String("VALUE(\"x\")"), String("e"), String("#VALUE!"))
    # SUMPRODUCT: D1:D3 x A1:A3 = 1*2 + 3*4 + 5*4 = 34
    t += _f(String("G55"), String("SUMPRODUCT(D1:D3,A1:A3)"), String("n"), String("34"))
    # SUMIFS: sum A where D >= 3 = 8 (same rows as G34, sum range first)
    t += _f(String("G56"), String("SUMIFS(A1:A3,D1:D3,\">=3\")"), String("n"), String("8"))
    # DAYS
    t += _f(String("G57"), String("DAYS(45000,44990)"), String("n"), String("10"))
    # LOOKUP vector form: last D <= 4 is 3 -> "three"
    t += _f(String("G58"), String("LOOKUP(4,D1:D3,E1:E3)"), String("s"), String("three"))
    # LARGE
    t += _f(String("G59"), String("LARGE(A1:A8,2)"), String("n"), String("7"))
    # ROWS
    t += _f(String("G60"), String("ROWS(A1:A5)"), String("n"), String("5"))
    # ISNUMBER / ISBLANK
    t += _f(String("G61"), String("ISNUMBER(A1)"), String("b"), String("1"))
    t += _f(String("G62"), String("ISBLANK(Z99)"), String("b"), String("1"))
    t += _f(String("G63"), String("ISBLANK(A1)"), String("b"), String("0"))
    # CHOOSE is lazy like IF
    t += _f(String("G64"), String("CHOOSE(2,10,20,30)"), String("n"), String("20"))
    t += _f(String("G65"), String("CHOOSE(1,5,1/0)"), String("n"), String("5"))
    # DATE with the leap legend: 1900-01-01 is 1, 1900-03-01 is 61 (fake
    # Feb 29 absorbs 60), 2024-02-29 is 45351
    t += _f(String("G66"), String("DATE(1900,1,1)"), String("n"), String("1"))
    t += _f(String("G67"), String("DATE(1900,3,1)"), String("n"), String("61"))
    t += _f(String("G68"), String("DATE(2024,2,29)"), String("n"), String("45351"))
    # ── corpus-found regressions (fixed after the first validation pass) ─────
    # criteria with non-ASCII bytes must match byte-identically: the operator
    # strip re-encoded Ñ via chr() and "MAGAÑA" never matched (sb 31202)
    t += _f(String("G69"), String('SUMIF(B5:B5,B5,A1:A1)'), String("n"), String("2"))
    t += _f(String("G70"), String('COUNTIF(B5:B5,"MAGAÑA")'), String("n"), String("1"))
    # INDEX(computed_array, 0) is the whole-column form (sb 3413): A1:A8 is
    # {2,4,4,4,5,5,7,9} so (=4)*(>3) is {0,1,1,1,0,0,0,0} and MATCH finds 2
    t += _f(
        String("G71"),
        String("MATCH(1,INDEX((A1:A8=4)*(A1:A8>3),0),0)"),
        String("n"),
        String("2"),
    )
    # INDEX(computed_array, n) picks the n-th element: (>4)*1 = {0,0,0,0,1,...}
    t += _f(String("G72"), String("INDEX((A1:A8>4)*1,5)"), String("n"), String("1"))
    # INDEX propagates an ERROR first argument as itself, not as #VALUE!
    # (sb 54590: INDEX(#REF!,MATCH(..)) caches #REF!)
    t += _f(String("G73"), String("INDEX(#REF!,1)"), String("e"), String("#REF!"))
    # the last-non-blank idiom: LOOKUP over a computed {1|#DIV/0!} vector must
    # SKIP the errors and answer the LAST hit. C1:C8 is blank except C2/C6, so
    # the last non-blank is C6 = 60 (sb 54490). Critically, the answer must NOT
    # depend on the formula's own row: G74 and G75 are identical formulas in
    # different rows and both must be 60 — the implicit-intersection bug made
    # the row-3 copy answer 20.
    t += _f(
        String("G74"),
        String('LOOKUP(2,1/($C$1:$C$8<>""),$C$1:$C$8)'),
        String("n"),
        String("60"),
    )
    t += _f(
        String("G75"),
        String('LOOKUP(2,1/($C$1:$C$8<>""),$C$1:$C$8)'),
        String("n"),
        String("60"),
    )
    # a WHOLE-COLUMN operand in a vector slot clamps to the sheet's used range
    # (F:F is nominally 2^20 rows); the answer is still the last non-blank, and
    # an EXPLICIT range keeps its blank tail (G77 counts all 8 rows of C1:C8)
    t += _f(String("G76"), String('LOOKUP(2,1/($C:$C<>""),$C:$C)'), String("n"), String("60"))
    t += _f(String("G77"), String("ROWS($C$1:$C$8)"), String("n"), String("8"))
    n_formulas = 77

    var rep = sheet_recalc_report(t, 0)
    var err_expected = 5  # G11, G23, G36, G54, G73 match as typed errors
    if (
        rep.status == 1320
        and rep.formula_cells == n_formulas
        and rep.matched_exact == n_formulas - err_expected
        and rep.error_matched == err_expected
        and rep.mismatched == 0
        and rep.error_mismatched == 0
        and rep.unsupported == 0
    ):
        passed += 1
        print("  ✅ all 77 census-order function cells match their hand values exactly")
    else:
        failed += 1
        print(
            "  ❌ function cells:",
            rep.matched_exact,
            "exact /",
            rep.error_matched,
            "err /",
            rep.mismatched + rep.error_mismatched,
            "MISMATCHED:",
            rep.mismatch_samples,
        )

    # ── unknown functions land in the NAMED uncovered table ─────────────────
    var u = String("SHEETWB\t1\nD\t0\nS\tS\n")
    u += "C\t0\tA1\tn\t1\n"
    u += "F\t0\tB1\tn\tNPV(0.1,A1)\tn\t0.909090909090909\n"
    u += "F\t0\tB2\tn\tB1+1\tn\t1.9090909\n"
    var urep = sheet_recalc_report(u, 0)
    if urep.unsupported == 2 and urep.unsupported_names == "NPV:2" and urep.mismatched == 0:
        passed += 1
        print("  ✅ NPV and its dependent taint into the tail as NPV:2, no fake numbers")
    else:
        failed += 1
        print("  ❌ uncovered accounting:", urep.unsupported, urep.unsupported_names)

    # ── volatile functions are a separate honesty bucket ─────────────────────
    var v = String("SHEETWB\t1\nD\t0\nS\tS\n")
    v += "F\t0\tA1\tn\tTODAY()\tn\t45000\n"
    var vrep = sheet_recalc_report(v, 0)
    if vrep.volatile_cells == 1 and vrep.unsupported == 0 and vrep.mismatched == 0:
        passed += 1
        print("  ✅ TODAY() is volatile, never a mismatch, never 'supported'")
    else:
        failed += 1
        print("  ❌ volatile bucket:", vrep.volatile_cells, vrep.unsupported)

    # ── spot values through sheet_eval_cell (typed, not just counted) ────────
    var c = sheet_eval_cell(t, String("S"), String("G21"), 0)
    if c.found and c.kind == VK_TEXT and c.text == "b-c":
        passed += 1
        print('  ✅ TEXTAFTER("a-b-c","-") = "b-c" as a typed TEXT value')
    else:
        failed += 1
        print("  ❌ typed TEXTAFTER wrong")
    var c2 = sheet_eval_cell(t, String("S"), String("G14"), 0)
    if c2.found and c2.kind == VK_NUM and c2.num == 3600.0 / 86400.0:
        passed += 1
        print("  ✅ TIME(25,0,0) is bit-identical to 3600/86400")
    else:
        failed += 1
        print("  ❌ TIME bits wrong")

    print("  [sheet.functions] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_sheet_functions failed")
