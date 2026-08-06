"""test_document_layout.mojo — auto-generated tests for document_layout."""
from std.math import isnan, isinf
from document_layout import text_line_boxes_flat, line_count_flat, column_boxes_flat, column_count_flat, text_density_grid_flat, multi_column_score_flat, table_like_score_flat

def is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _li3 = List[Int]()
    _li3.append(1); _li3.append(2); _li3.append(3)
    var _li2_zero = List[Int]()
    _li2_zero.append(0); _li2_zero.append(1)
    var _li3_tail = List[Int]()
    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)
    var _li8 = List[Int]()
    for i in range(8):
        _li8.append(i + 1)
    var _li6_grid2x3 = List[Int]()
    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    var _li10_borda = List[Int]()
    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)
    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)
    var _li16 = List[Int]()
    for i in range(16):
        _li16.append(i)
    var _lf6_matrix = List[Float64]()
    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)
    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)
    var _lf8_coalitions = List[Float64]()
    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)
    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _lf64_docmask8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):
                _lf64_docmask8x8.append(255.0)
            else:
                _lf64_docmask8x8.append(0.0)
    var _lf64_doccolumns8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if y >= 1 and y <= 6 and ((x >= 1 and x <= 2) or (x >= 5 and x <= 6)):
                _lf64_doccolumns8x8.append(255.0)
            else:
                _lf64_doccolumns8x8.append(0.0)
    var _lf81_doctable9x9 = List[Float64]()
    for y in range(9):
        for x in range(9):
            if ((y >= 1 and y <= 2) or (y >= 4 and y <= 5) or (y >= 7 and y <= 8)) and ((x >= 1 and x <= 2) or (x >= 4 and x <= 5) or (x >= 7 and x <= 8)):
                _lf81_doctable9x9.append(255.0)
            else:
                _lf81_doctable9x9.append(0.0)
    var _v_text_line_boxes_flat = text_line_boxes_flat(_lf64_docmask8x8, 8, 8, 128.0, 1)
    if len(_v_text_line_boxes_flat) >= 0: passed += 1; print("  ✅ document_layout::text_line_boxes_flat")
    _ = line_count_flat(_lf64_docmask8x8, 8, 8, 128.0, 1)
    passed += 1; print("  ✅ document_layout::line_count_flat")
    var _v_column_boxes_flat = column_boxes_flat(_lf64_doccolumns8x8, 8, 8, 128.0, 2)
    if len(_v_column_boxes_flat) >= 0: passed += 1; print("  ✅ document_layout::column_boxes_flat")
    _ = column_count_flat(_lf64_doccolumns8x8, 8, 8, 128.0, 2)
    passed += 1; print("  ✅ document_layout::column_count_flat")
    var _v_text_density_grid_flat = text_density_grid_flat(_lf64_docmask8x8, 8, 8, 128.0, 2, 2)
    if len(_v_text_density_grid_flat) >= 0: passed += 1; print("  ✅ document_layout::text_density_grid_flat")
    var _v_multi_column_score_flat = multi_column_score_flat(_lf64_doccolumns8x8, 8, 8, 128.0)
    if is_finite(_v_multi_column_score_flat): passed += 1; print("  ✅ document_layout::multi_column_score_flat =", _v_multi_column_score_flat)
    else: failed += 1; print("  ❌ document_layout::multi_column_score_flat → non-finite:", _v_multi_column_score_flat)
    var _v_table_like_score_flat = table_like_score_flat(_lf81_doctable9x9, 9, 9, 128.0)
    if is_finite(_v_table_like_score_flat): passed += 1; print("  ✅ document_layout::table_like_score_flat =", _v_table_like_score_flat)
    else: failed += 1; print("  ❌ document_layout::table_like_score_flat → non-finite:", _v_table_like_score_flat)

    print("  [document_layout] Passed:", passed, "Failed:", failed)
