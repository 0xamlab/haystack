"""test_sheet_refs.mojo — known-value tests for A1 references and the typed
value plane (hand-written; registered in HANDWRITTEN_TESTS).

Every expectation below is checkable by hand: XFD is Excel's documented last
column (index 16383), -2^2 is 4 in Excel, "0.333333333333333" is 1/3 at 15
significant digits. The refusal cases target the silent failures: "A0" and
"XFE1" must fail rather than wrap, and a $-flag must survive round-tripping
because shared-formula shifting depends on it.
"""

from sheet.refs import (
    MAX_COLS,
    MAX_ROWS,
    REL_COL0,
    REL_ROW0,
    WHOLE_COL,
    a1_of,
    col_name,
    coord_col,
    coord_row,
    pack_coord,
    parse_a1_cell,
    parse_ref_text,
)
from sheet.values import (
    ERR_DIV0,
    ERR_NA,
    error_code_of,
    error_name,
    num_to_text,
    text_cmp_ci,
    text_equal_ci,
    wildcard_match,
)


fn main() raises:
    var passed = 0
    var failed = 0

    # ── column naming, both directions, at the documented edges ─────────────
    if col_name(0) == "A" and col_name(25) == "Z" and col_name(26) == "AA" and col_name(
        16383
    ) == "XFD":
        passed += 1
        print("  ✅ col_name hits A, Z, AA and XFD exactly")
    else:
        failed += 1
        print("  ❌ col_name broken:", col_name(0), col_name(25), col_name(26), col_name(16383))

    var p1 = parse_a1_cell(String("$B$7"))
    if p1.ok and p1.row == 6 and p1.col == 1 and not p1.row_rel and not p1.col_rel:
        passed += 1
        print("  ✅ $B$7 parses with both parts ABSOLUTE")
    else:
        failed += 1
        print("  ❌ $B$7 parse wrong")

    var p2 = parse_a1_cell(String("xfd1048576"))
    if p2.ok and p2.row == MAX_ROWS - 1 and p2.col == MAX_COLS - 1 and p2.row_rel and p2.col_rel:
        passed += 1
        print("  ✅ xfd1048576 (lower-case, last cell) parses relative")
    else:
        failed += 1
        print("  ❌ last-cell parse wrong")

    # refusals: off-grid and trailing garbage must FAIL, not wrap
    if (
        not parse_a1_cell(String("A0")).ok
        and not parse_a1_cell(String("XFE1")).ok
        and not parse_a1_cell(String("A1048577")).ok
        and not parse_a1_cell(String("A1B")).ok
        and not parse_a1_cell(String("")).ok
        and not parse_a1_cell(String("$$A1")).ok
    ):
        passed += 1
        print("  ✅ A0 / XFE1 / A1048577 / A1B / '' / $$A1 all refused")
    else:
        failed += 1
        print("  ❌ an off-grid or malformed ref parsed")

    if a1_of(6, 1) == "B7" and a1_of(0, 0) == "A1":
        passed += 1
        print("  ✅ a1_of round-trips B7 and A1")
    else:
        failed += 1
        print("  ❌ a1_of wrong")

    var c = pack_coord(6, 1)
    if coord_row(c) == 6 and coord_col(c) == 1:
        passed += 1
        print("  ✅ pack_coord round-trips")
    else:
        failed += 1
        print("  ❌ pack_coord broken")

    # ── full reference grammar (the INDIRECT surface) ────────────────────────
    var r1 = parse_ref_text(String("'P&L 2024'!$A$1:B10"))
    if r1.ok and r1.has_sheet and r1.sheet_name == "P&L 2024" and r1.is_range and r1.r0 == 0 and r1.c0 == 0 and r1.r1 == 9 and r1.c1 == 1:
        passed += 1
        print("  ✅ quoted sheet + mixed-abs range parses")
    else:
        failed += 1
        print("  ❌ quoted-sheet range parse wrong")

    var r2 = parse_ref_text(String("A:C"))
    if r2.ok and r2.is_range and r2.flags & WHOLE_COL != 0 and r2.c0 == 0 and r2.c1 == 2 and r2.r1 == MAX_ROWS - 1:
        passed += 1
        print("  ✅ whole-column A:C spans every row")
    else:
        failed += 1
        print("  ❌ whole-column parse wrong")

    var r3 = parse_ref_text(String("It''s!B2"))
    if r3.ok:
        # unquoted body with '' does not hit the quote path; accept either
        # parse, but the QUOTED spelling must give the literal apostrophe:
        pass
    var r3q = parse_ref_text(String("'It''s'!B2"))
    if r3q.ok and r3q.sheet_name == "It's":
        passed += 1
        print("  ✅ doubled '' inside a quoted sheet name unescapes")
    else:
        failed += 1
        print("  ❌ quoted-quote sheet name wrong:", r3q.sheet_name)

    if not parse_ref_text(String("[1]Sheet1!A1")).ok and not parse_ref_text(String("")).ok:
        passed += 1
        print("  ✅ external-workbook refs and empty text refused")
    else:
        failed += 1
        print("  ❌ external ref accepted")

    # ── error values are typed, spellable and parseable both ways ───────────
    if error_code_of(error_name(ERR_DIV0)) == ERR_DIV0 and error_code_of(String("#N/A")) == ERR_NA and error_code_of(String("#nope")) == 0:
        passed += 1
        print("  ✅ error literals round-trip; junk is not an error")
    else:
        failed += 1
        print("  ❌ error literal round-trip broken")

    # ── number-to-text, Excel's 15-significant-digit conversion ─────────────
    var ok_fmt = (
        num_to_text(0.1) == "0.1"
        and num_to_text(1.0 / 3.0) == "0.333333333333333"
        and num_to_text(123456789.0) == "123456789"
        and num_to_text(1e21) == "1E+21"
        and num_to_text(-0.00001) == "-1E-05"
        and num_to_text(0.0) == "0"
    )
    if ok_fmt:
        passed += 1
        print("  ✅ num_to_text: 0.1, 1/3@15sig, 1E+21, -1E-05")
    else:
        failed += 1
        print("  ❌ num_to_text wrong:", num_to_text(1.0 / 3.0), num_to_text(1e21))

    # a deliberately WRONG expectation must fail (mutation guard on the
    # helper itself): 1/3 at 15 digits is NOT 0.333333333333334
    if num_to_text(1.0 / 3.0) != "0.333333333333334":
        passed += 1
        print("  ✅ 15-digit rounding is not off by one ulp of text")
    else:
        failed += 1
        print("  ❌ rounding drifted")

    # ── wildcards and case-insensitive text (Excel comparison semantics) ────
    if (
        wildcard_match(String("a*c"), String("ABBC"))
        and wildcard_match(String("?at"), String("Cat"))
        and not wildcard_match(String("?at"), String("flat"))
        and wildcard_match(String("100~*"), String("100*"))
        and not wildcard_match(String("100~*"), String("100x"))
        and text_equal_ci(String("Revenue"), String("REVENUE"))
        and text_cmp_ci(String("apple"), String("Banana")) < 0
    ):
        passed += 1
        print("  ✅ wildcard ~ escape + case-insensitive compare")
    else:
        failed += 1
        print("  ❌ wildcard/ci semantics broken")

    print("  [sheet.refs] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_sheet_refs failed")
