"""
test_document_layout.mojo — Tests for the pure-Mojo document_layout library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_document_layout.mojo
"""
from document_layout import (
    text_line_boxes_flat,
    line_count_flat,
    column_boxes_flat,
    column_count_flat,
    text_density_grid_flat,
    multi_column_score_flat,
    table_like_score_flat,
)


def _assert_true(cond: Bool, label: String) raises:
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)


def _assert_close(got: Float64, expected: Float64, tol: Float64, label: String) raises:
    var diff = got - expected
    if diff < 0.0:
        diff = -diff
    if diff > tol:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected) + " ± " + String(tol))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)


def _assert_eq_int(got: Int, expected: Int, label: String) raises:
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)


fn _docmask8() -> List[Float64]:
    var flat = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):
                flat.append(255.0)
            else:
                flat.append(0.0)
    return flat^


fn _twocol_mask8() -> List[Float64]:
    var flat = List[Float64]()
    for y in range(8):
        for x in range(8):
            if y >= 1 and y <= 6 and ((x >= 1 and x <= 2) or (x >= 5 and x <= 6)):
                flat.append(255.0)
            else:
                flat.append(0.0)
    return flat^


fn _table_mask9() -> List[Float64]:
    var flat = List[Float64]()
    for y in range(9):
        for x in range(9):
            var in_row_band = (y >= 1 and y <= 2) or (y >= 4 and y <= 5) or (y >= 7 and y <= 8)
            var in_col_band = (x >= 1 and x <= 2) or (x >= 4 and x <= 5) or (x >= 7 and x <= 8)
            flat.append(255.0 if in_row_band and in_col_band else 0.0)
    return flat^


def test_line_boxes_and_counts() raises:
    var lines = text_line_boxes_flat(_docmask8(), 8, 8, 128.0, 1)
    _assert_eq_int(len(lines), 10, "two text line boxes")
    _assert_eq_int(lines[0], 1, "line 1 x0")
    _assert_eq_int(lines[1], 2, "line 1 y0")
    _assert_eq_int(lines[2], 6, "line 1 x1")
    _assert_eq_int(lines[3], 2, "line 1 y1")
    _assert_eq_int(lines[4], 6, "line 1 area")
    _assert_eq_int(lines[5], 2, "line 2 x0")
    _assert_eq_int(lines[6], 5, "line 2 y0")
    _assert_eq_int(lines[7], 5, "line 2 x1")
    _assert_eq_int(lines[8], 5, "line 2 y1")
    _assert_eq_int(lines[9], 4, "line 2 area")
    _assert_eq_int(line_count_flat(_docmask8(), 8, 8, 128.0, 1), 2, "line_count_flat")
    print("✅ line segmentation")


def test_columns_and_multicolumn_score() raises:
    var cols = column_boxes_flat(_twocol_mask8(), 8, 8, 128.0, 2)
    _assert_eq_int(len(cols), 10, "two column boxes")
    _assert_eq_int(cols[0], 1, "column 1 x0")
    _assert_eq_int(cols[1], 1, "column 1 y0")
    _assert_eq_int(cols[2], 2, "column 1 x1")
    _assert_eq_int(cols[3], 6, "column 1 y1")
    _assert_eq_int(cols[4], 12, "column 1 area")
    _assert_eq_int(cols[5], 5, "column 2 x0")
    _assert_eq_int(cols[6], 1, "column 2 y0")
    _assert_eq_int(cols[7], 6, "column 2 x1")
    _assert_eq_int(cols[8], 6, "column 2 y1")
    _assert_eq_int(cols[9], 12, "column 2 area")
    _assert_eq_int(column_count_flat(_twocol_mask8(), 8, 8, 128.0, 2), 2, "column_count_flat")
    _assert_true(
        multi_column_score_flat(_twocol_mask8(), 8, 8, 128.0) > 0.65,
        "two separated columns score as multi-column",
    )
    print("✅ column segmentation / multicolumn score")


def test_density_grid_and_table_score() raises:
    var density = text_density_grid_flat(_docmask8(), 8, 8, 128.0, 2, 2)
    _assert_eq_int(len(density), 4, "2x2 density grid")
    _assert_close(density[0], 3.0 / 16.0, 1e-9, "density cell 0")
    _assert_close(density[1], 3.0 / 16.0, 1e-9, "density cell 1")
    _assert_close(density[2], 2.0 / 16.0, 1e-9, "density cell 2")
    _assert_close(density[3], 2.0 / 16.0, 1e-9, "density cell 3")

    var table_score = table_like_score_flat(_table_mask9(), 9, 9, 128.0)
    var doc_score = table_like_score_flat(_docmask8(), 8, 8, 128.0)
    _assert_true(table_score > 0.8, "table-like mask scores strongly")
    _assert_true(table_score > doc_score, "table-like mask outranks simple text lines")
    print("✅ density grid / table-like score")


def main() raises:
    print("━━━ document_layout test suite ━━━")
    test_line_boxes_and_counts()
    test_columns_and_multicolumn_score()
    test_density_grid_and_table_score()
    print("━━━ All document_layout tests passed ━━━")

