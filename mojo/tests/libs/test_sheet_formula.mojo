"""test_sheet_formula.mojo — parser known-values (hand-written; registered in
HANDWRITTEN_TESTS).

Targets Excel's two precedence traps directly (-2^2 = 4, 2^3^2 = 64 — both
verified in Excel itself), the storage prefixes real files carry
(_xlfn.TEXTAFTER), and the refusal paths that must produce a NAMED reason
node rather than a wrong tree: structured references, external links, range
unions.
"""

from sheet.formula import (
    FID_TEXTAFTER,
    FID_UNKNOWN,
    FID_VOLATILE,
    FNode,
    NK_ARRAYLIT,
    NK_BIN,
    NK_BOOL,
    NK_ERR,
    NK_FUNC,
    NK_NAME,
    NK_NUM,
    NK_RANGE,
    NK_REF,
    NK_UN,
    NK_UNSUP,
    OP_CAT,
    OP_NEG,
    OP_PCT,
    OP_POW,
    parse_formula,
)
from sheet.values import ERR_NA


def _sheets() -> List[String]:
    var s = List[String]()
    s.append(String("Sheet1"))
    s.append(String("My Data"))
    return s^


def main() raises:
    var passed = 0
    var failed = 0
    var nodes = List[FNode]()
    var pool = List[Int]()
    var sheets = _sheets()

    # ── the two documented precedence traps ──────────────────────────────────
    # -2^2: root must be POW (unary minus binds tighter), so the value is 4
    var r = parse_formula(String("-2^2"), sheets, nodes, pool)
    var trap1 = nodes[r].k == NK_BIN and nodes[r].a == OP_POW and nodes[
        pool[nodes[r].arg_start]
    ].k == NK_UN and nodes[pool[nodes[r].arg_start]].a == OP_NEG
    if trap1:
        passed += 1
        print("  ✅ -2^2 parses as (-2)^2, Excel's answer 4")
    else:
        failed += 1
        print("  ❌ -2^2 mis-parsed")

    # 2^3^2 left-associative: root's LEFT child is itself a POW
    r = parse_formula(String("2^3^2"), sheets, nodes, pool)
    var lchild = pool[nodes[r].arg_start]
    if nodes[r].a == OP_POW and nodes[lchild].k == NK_BIN and nodes[lchild].a == OP_POW:
        passed += 1
        print("  ✅ 2^3^2 parses as (2^3)^2 = 64, never 512")
    else:
        failed += 1
        print("  ❌ ^ associativity wrong")

    # percent is a postfix unary
    r = parse_formula(String("50%"), sheets, nodes, pool)
    if nodes[r].k == NK_UN and nodes[r].a == OP_PCT:
        passed += 1
        print("  ✅ 50% is postfix percent")
    else:
        failed += 1
        print("  ❌ percent broken")

    # ── references, cross-sheet, whole-column, storage prefixes ──────────────
    r = parse_formula(String("SUM('My Data'!$A$1:B10,A:A,3:7)"), sheets, nodes, pool)
    var a0 = pool[nodes[r].arg_start]
    var a1 = pool[nodes[r].arg_start + 1]
    var a2 = pool[nodes[r].arg_start + 2]
    if (
        nodes[r].k == NK_FUNC
        and nodes[a0].k == NK_RANGE
        and nodes[a0].a == 1  # 'My Data' resolved to sheet index 1
        and nodes[a1].k == NK_RANGE
        and nodes[a1].b == 0
        and nodes[a1].d == 1048575  # A:A spans every row
        and nodes[a2].k == NK_RANGE
        and nodes[a2].b == 2
        and nodes[a2].d == 6  # 3:7 rows
    ):
        passed += 1
        print("  ✅ cross-sheet + whole-column + whole-row ranges")
    else:
        failed += 1
        print("  ❌ range forms mis-parsed")

    r = parse_formula(String("_xlfn.TEXTAFTER(A1,\"-\")"), sheets, nodes, pool)
    if nodes[r].k == NK_FUNC and nodes[r].text == "TEXTAFTER" and nodes[r].b == FID_TEXTAFTER:
        passed += 1
        print("  ✅ _xlfn. storage prefix stripped, id resolved")
    else:
        failed += 1
        print("  ❌ prefix handling broken")

    # LOG10 with no '(' is a CELL (column LOG exists), with '(' a function
    r = parse_formula(String("LOG10"), sheets, nodes, pool)
    var r2 = parse_formula(String("LOG10(A1)"), sheets, nodes, pool)
    if nodes[r].k == NK_REF and nodes[r2].k == NK_FUNC and nodes[r2].b == FID_UNKNOWN:
        passed += 1
        print("  ✅ LOG10 is a cell; LOG10( is an (unimplemented) function")
    else:
        failed += 1
        print("  ❌ ident/ref disambiguation broken")

    # TODAY() resolves to the volatile id — its cached value is irreproducible
    r = parse_formula(String("TODAY()"), sheets, nodes, pool)
    if nodes[r].k == NK_FUNC and nodes[r].b == FID_VOLATILE:
        passed += 1
        print("  ✅ TODAY() marked volatile")
    else:
        failed += 1
        print("  ❌ volatile marking broken")

    # ── literals ─────────────────────────────────────────────────────────────
    r = parse_formula(String("IF(TRUE,#N/A,\"a\"\"b\")"), sheets, nodes, pool)
    var c1 = pool[nodes[r].arg_start]
    var c2 = pool[nodes[r].arg_start + 1]
    var c3 = pool[nodes[r].arg_start + 2]
    if (
        nodes[c1].k == NK_BOOL
        and nodes[c2].k == NK_ERR
        and nodes[c2].a == ERR_NA
        and nodes[c3].text == 'a"b'
    ):
        passed += 1
        print("  ✅ TRUE, #N/A and doubled-quote string literals")
    else:
        failed += 1
        print("  ❌ literal parsing broken")

    r = parse_formula(String("{1,2;3,4}"), sheets, nodes, pool)
    if nodes[r].k == NK_ARRAYLIT and nodes[r].a == 2 and nodes[r].b == 2:
        passed += 1
        print("  ✅ {1,2;3,4} is a 2x2 array literal")
    else:
        failed += 1
        print("  ❌ array literal broken")

    r = parse_formula(String("MyRate*2"), sheets, nodes, pool)
    var l = pool[nodes[r].arg_start]
    if nodes[l].k == NK_NAME and nodes[l].text == "myrate":
        passed += 1
        print("  ✅ defined-name reference folds for lookup")
    else:
        failed += 1
        print("  ❌ defined-name parse broken")

    # ── refusals carry their NAME (the uncovered table depends on it) ────────
    var u1 = parse_formula(String("Table1[Col]"), sheets, nodes, pool)
    var u2 = parse_formula(String("[1]Sheet1!A1"), sheets, nodes, pool)
    var u3 = parse_formula(String("SUM((A1:A5,B1:B5))"), sheets, nodes, pool)
    var u4 = parse_formula(String("'[3]Detail Expenses'!P3"), sheets, nodes, pool)
    if (
        nodes[u1].k == NK_UNSUP
        and nodes[u1].text == "STRUCTURED_REF"
        and nodes[u2].k == NK_UNSUP
        and nodes[u2].text == "EXTERNAL_REF"
        and nodes[u3].k == NK_UNSUP
        and nodes[u3].text == "RANGE_UNION"
        and nodes[u4].k == NK_UNSUP
        and nodes[u4].text == "EXTERNAL_REF"
    ):
        passed += 1
        print("  ✅ structured/external/union refusals are NAMED, incl. quoted '[3]...'")
    else:
        failed += 1
        print("  ❌ refusal reasons wrong:", nodes[u1].text, nodes[u2].text, nodes[u3].text, nodes[u4].text)

    # unbalanced input never yields a usable tree, and never crashes
    var junk = parse_formula(String("SUM(A1"), sheets, nodes, pool)
    var junk2 = parse_formula(String(")(*&"), sheets, nodes, pool)
    if nodes[junk].k == NK_UNSUP and nodes[junk2].k == NK_UNSUP:
        passed += 1
        print("  ✅ malformed input refuses instead of guessing")
    else:
        failed += 1
        print("  ❌ malformed input accepted")

    print("  [sheet.formula] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_sheet_formula failed")
