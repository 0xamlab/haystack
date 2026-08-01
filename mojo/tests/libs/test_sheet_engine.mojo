"""test_sheet_engine.mojo — recalc semantics on hand-computed workbooks
(hand-written; registered in HANDWRITTEN_TESTS).

The LAW cases live here:
  * a five-cell workbook computed by hand, matched cell for cell;
  * #DIV/0! PROPAGATING through a dependent chain as a typed value;
  * a deliberately-cyclic workbook that NAMES its cycle's cells;
  * the comparator refusing to hide a genuinely wrong recalc behind the
    tolerance (the anti-vacuity of the tolerance itself);
  * shared-formula followers shifting only RELATIVE refs;
  * budget exhaustion as an honest partial status, never a hang.
"""

from sheet.api import SheetRecalcReport, sheet_eval_cell, sheet_recalc_report
from sheet.grid import (
    SHEET_ERR_BAD_MAGIC,
    SHEET_ERR_BAD_REF,
    SHEET_ERR_DATE1904,
    SHEET_ERR_DUP_CELL,
)
from sheet.values import VK_BOOL, VK_ERR, VK_NUM, VK_TEXT


fn _hand_workbook() -> String:
    """Five formula cells, every expectation computed by hand:
    C1 = A1+A2 = 30; C2 = C1*2 = 60; C3 = A1/A2 = 0.5;
    C4 = "x" & B1 = "xhello"; C5 = (A1>A2) = FALSE."""
    var t = String("SHEETWB\t1\nD\t0\nS\tSheet1\n")
    t += "C\t0\tA1\tn\t10\n"
    t += "C\t0\tA2\tn\t20\n"
    t += "C\t0\tB1\ts\thello\n"
    t += "F\t0\tC1\tn\tA1+A2\tn\t30\n"
    t += "F\t0\tC2\tn\tC1*2\tn\t60\n"
    t += "F\t0\tC3\tn\tA1/A2\tn\t0.5\n"
    t += 'F\t0\tC4\tn\t"x"&B1\ts\txhello\n'
    t += "F\t0\tC5\tn\tA1>A2\tb\t0\n"
    return t^


fn main() raises:
    var passed = 0
    var failed = 0

    # ── the hand workbook matches exactly, all five cells ────────────────────
    var rep = sheet_recalc_report(_hand_workbook(), 0)
    if rep.status == 1320 and rep.formula_cells == 5 and rep.matched_exact == 5 and rep.mismatched == 0:
        passed += 1
        print("  ✅ five hand-computed cells all match exactly")
    else:
        failed += 1
        print("  ❌ hand workbook:", rep.matched_exact, "exact,", rep.mismatched, "mm")

    # ── anti-vacuity: a WRONG cached value must be a mismatch ───────────────
    # same workbook, but C1's cached value is corrupted to 31 — if the
    # comparator "passes" this, the whole validation number is vacuous
    var bad = String("SHEETWB\t1\nD\t0\nS\tSheet1\n")
    bad += "C\t0\tA1\tn\t10\n"
    bad += "C\t0\tA2\tn\t20\n"
    bad += "F\t0\tC1\tn\tA1+A2\tn\t31\n"
    var brep = sheet_recalc_report(bad, 0)
    if brep.mismatched == 1 and brep.matched_exact == 0 and brep.matched_tol == 0 and brep.matched_snap == 0:
        passed += 1
        print("  ✅ a wrong cached value (31 vs 30) FAILS: no bucket hides it")
    else:
        failed += 1
        print("  ❌ tolerance swallowed a wrong answer")

    # ...and a near-zero wrong answer must not hide in the snap bucket:
    # cached 0 with a computed 0.5 is a mismatch, not a snap
    var bad2 = String("SHEETWB\t1\nD\t0\nS\tS\n")
    bad2 += "C\t0\tA1\tn\t10\n"
    bad2 += "F\t0\tB1\tn\tA1/20\tn\t0\n"
    var brep2 = sheet_recalc_report(bad2, 0)
    if brep2.mismatched == 1 and brep2.matched_snap == 0:
        passed += 1
        print("  ✅ snap bucket only takes sub-1e-6 residue, not real values")
    else:
        failed += 1
        print("  ❌ snap bucket over-matched")

    # ── #DIV/0! propagates as a typed value through a chain ─────────────────
    var t = String("SHEETWB\t1\nD\t0\nS\tS\n")
    t += "C\t0\tA1\tn\t1\n"
    t += "F\t0\tB1\tn\tA1/0\te\t#DIV/0!\n"
    t += "F\t0\tB2\tn\tB1+1\te\t#DIV/0!\n"
    t += "F\t0\tB3\tn\tSUM(B1:B2)\te\t#DIV/0!\n"
    t += "F\t0\tB4\tn\tIFERROR(B3,\"caught\")\ts\tcaught\n"
    var erep = sheet_recalc_report(t, 0)
    if erep.error_matched == 3 and erep.matched_exact == 1 and erep.mismatched == 0:
        passed += 1
        print("  ✅ #DIV/0! propagates B1->B2->SUM and IFERROR catches it")
    else:
        failed += 1
        print("  ❌ error propagation:", erep.error_matched, erep.matched_exact)

    # ── a deliberate cycle NAMES its cells ───────────────────────────────────
    var c = String("SHEETWB\t1\nD\t0\nS\tModel\n")
    c += "F\t0\tA1\tn\tB1+1\tn\t0\n"
    c += "F\t0\tB1\tn\tA1*2\tn\t0\n"
    c += "F\t0\tK3\tn\tK4-$K$3\tn\t5\n"
    c += "C\t0\tK4\tn\t7\n"
    var crep = sheet_recalc_report(c, 0)
    var names_ok = False
    # both the mutual A1<->B1 cycle and the K3 self-cycle must be spelled out
    if crep.cycle_count == 2 and crep.cycle_cells == 3:
        var n = crep.cycle_names
        # cheap containment checks without a substring helper: exact spellings
        names_ok = n == "Model!A1 -> Model!B1 -> Model!A1 | Model!K3 -> Model!K3" or n == "Model!K3 -> Model!K3 | Model!A1 -> Model!B1 -> Model!A1"
    if names_ok:
        passed += 1
        print("  ✅ cycles NAME their cells:", crep.cycle_names)
    else:
        failed += 1
        print("  ❌ cycle naming wrong:", crep.cycle_names, crep.cycle_count, crep.cycle_cells)

    # ── shared followers shift RELATIVE parts only ───────────────────────────
    var s = String("SHEETWB\t1\nD\t0\nS\tS\n")
    s += "C\t0\tA1\tn\t1\n"
    s += "C\t0\tA2\tn\t2\n"
    s += "C\t0\tA3\tn\t3\n"
    s += "C\t0\tB1\tn\t100\n"
    # master at C1: =A1+$B$1 -> followers C2, C3 shift only the A part
    s += "F\t0\tC1\tm:0\tA1+$B$1\tn\t101\n"
    s += "G\t0\tC2\t0\tn\t102\n"
    s += "G\t0\tC3\t0\tn\t103\n"
    var srep = sheet_recalc_report(s, 0)
    if srep.matched_exact == 3 and srep.mismatched == 0:
        passed += 1
        print("  ✅ follower C3 computes A3+$B$1 = 103 (relative shifts, absolute stays)")
    else:
        failed += 1
        print("  ❌ shared-formula shift wrong:", srep.matched_exact, srep.mismatched)

    # ── cross-sheet references ───────────────────────────────────────────────
    var x = String("SHEETWB\t1\nD\t0\nS\tData\nS\tCalc\n")
    x += "C\t0\tA1\tn\t42\n"
    x += "F\t1\tA1\tn\tData!A1*2\tn\t84\n"
    var xrep = sheet_recalc_report(x, 0)
    if xrep.matched_exact == 1:
        passed += 1
        print("  ✅ cross-sheet Data!A1 from sheet Calc")
    else:
        failed += 1
        print("  ❌ cross-sheet broken")

    # ── loader refusals are typed, never crashes ─────────────────────────────
    var r1 = sheet_recalc_report(String("not a workbook"), 0)
    var r2 = sheet_recalc_report(String("SHEETWB\t1\nD\t1\nS\tS\n"), 0)
    var r3 = sheet_recalc_report(String("SHEETWB\t1\nD\t0\nS\tS\nC\t0\tA0\tn\t1\n"), 0)
    var dup = String("SHEETWB\t1\nD\t0\nS\tS\nC\t0\tA1\tn\t1\nC\t0\tA1\tn\t2\n")
    var r4 = sheet_recalc_report(dup, 0)
    if (
        r1.status == SHEET_ERR_BAD_MAGIC
        and r2.status == SHEET_ERR_DATE1904
        and r3.status == SHEET_ERR_BAD_REF
        and r4.status == SHEET_ERR_DUP_CELL
    ):
        passed += 1
        print("  ✅ bad magic / date1904 / A0 / duplicate cell all refused by name")
    else:
        failed += 1
        print("  ❌ loader refusal statuses:", r1.status, r2.status, r3.status, r4.status)

    # ── the budget is a real budget: tiny budget -> honest partial ──────────
    var big = String("SHEETWB\t1\nD\t0\nS\tS\n")
    big += "C\t0\tA1\tn\t1\n"
    # DEEPEST CELL FIRST: evaluating A399 must demand A398 .. A2 down the
    # explicit stack, so the 398-deep chain is what the traversal actually
    # walks (in file order the stack would never grow past 1)
    var i = 399
    while i >= 2:
        big += "F\t0\tA"
        big += String(i)
        big += "\tn\tA"
        big += String(i - 1)
        big += "+1\tn\t"
        big += String(i)
        big += "\n"
        i -= 1
    var prep = sheet_recalc_report(big, 50)  # 50 charged ops cannot finish 398 cells
    var frep = sheet_recalc_report(big, 0)  # default budget finishes them
    if prep.status == 1321 and prep.not_evaluated > 0 and frep.status == 1320 and frep.matched_exact == 398:
        passed += 1
        print("  ✅ budget 50 stops honestly (RECALC_BUDGET); full budget matches all 398")
    else:
        failed += 1
        print("  ❌ budget handling:", prep.status, prep.not_evaluated, frep.matched_exact)

    # ── a 398-deep chain reports its depth (the DAG is charged) ─────────────
    if frep.max_chain >= 398:
        passed += 1
        print("  ✅ dependency chain depth is measured:", frep.max_chain)
    else:
        failed += 1
        print("  ❌ chain depth wrong:", frep.max_chain)

    # ── sheet_eval_cell agrees with the report ───────────────────────────────
    var cell = sheet_eval_cell(_hand_workbook(), String("sheet1"), String("C4"), 0)
    if cell.found and cell.kind == VK_TEXT and cell.text == "xhello":
        passed += 1
        print('  ✅ sheet_eval_cell("C4") = "xhello"')
    else:
        failed += 1
        print("  ❌ sheet_eval_cell broken")

    print("  [sheet.engine] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_sheet_engine failed")
