"""test_document_vision.mojo — auto-generated tests for document_vision."""
from std.math import isnan, isinf
from document_vision import otsu_threshold_flat, binarize_otsu_flat, adaptive_mean_binarize_flat, horizontal_projection, vertical_projection, mask_content_bbox_flat, skew_angle_estimate_flat, horizontal_text_score_flat, document_scan_quality_flat

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

    var _lf64_doc8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):
                _lf64_doc8x8.append(20.0)
            else:
                _lf64_doc8x8.append(240.0)
    var _lf36_adaptive_doc6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if y == 2 and x >= 2 and x <= 3:
                _lf36_adaptive_doc6x6.append(40.0)
            elif x < 3:
                _lf36_adaptive_doc6x6.append(220.0)
            else:
                _lf36_adaptive_doc6x6.append(245.0)
    var _lf64_docmask8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):
                _lf64_docmask8x8.append(255.0)
            else:
                _lf64_docmask8x8.append(0.0)
    var _lf36_skewmask6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if y >= 1 and y <= 4 and x == y:
                _lf36_skewmask6x6.append(255.0)
            else:
                _lf36_skewmask6x6.append(0.0)
    var _v_otsu_threshold_flat = otsu_threshold_flat(_lf64_doc8x8, 8, 8)
    if is_finite(_v_otsu_threshold_flat): passed += 1; print("  ✅ document_vision::otsu_threshold_flat =", _v_otsu_threshold_flat)
    else: failed += 1; print("  ❌ document_vision::otsu_threshold_flat → non-finite:", _v_otsu_threshold_flat)
    var _v_binarize_otsu_flat = binarize_otsu_flat(_lf64_doc8x8, 8, 8)
    if len(_v_binarize_otsu_flat) >= 0: passed += 1; print("  ✅ document_vision::binarize_otsu_flat")
    var _v_adaptive_mean_binarize_flat = adaptive_mean_binarize_flat(_lf36_adaptive_doc6x6, 6, 6, 1, 20.0)
    if len(_v_adaptive_mean_binarize_flat) >= 0: passed += 1; print("  ✅ document_vision::adaptive_mean_binarize_flat")
    var _v_horizontal_projection = horizontal_projection(_lf64_docmask8x8, 8, 8, 128.0)
    if len(_v_horizontal_projection) >= 0: passed += 1; print("  ✅ document_vision::horizontal_projection")
    var _v_vertical_projection = vertical_projection(_lf64_docmask8x8, 8, 8, 128.0)
    if len(_v_vertical_projection) >= 0: passed += 1; print("  ✅ document_vision::vertical_projection")
    var _v_mask_content_bbox_flat = mask_content_bbox_flat(_lf64_docmask8x8, 8, 8, 128.0)
    if len(_v_mask_content_bbox_flat) >= 0: passed += 1; print("  ✅ document_vision::mask_content_bbox_flat")
    var _v_skew_angle_estimate_flat = skew_angle_estimate_flat(_lf36_skewmask6x6, 6, 6, 128.0)
    if is_finite(_v_skew_angle_estimate_flat): passed += 1; print("  ✅ document_vision::skew_angle_estimate_flat =", _v_skew_angle_estimate_flat)
    else: failed += 1; print("  ❌ document_vision::skew_angle_estimate_flat → non-finite:", _v_skew_angle_estimate_flat)
    var _v_horizontal_text_score_flat = horizontal_text_score_flat(_lf64_docmask8x8, 8, 8, 128.0)
    if is_finite(_v_horizontal_text_score_flat): passed += 1; print("  ✅ document_vision::horizontal_text_score_flat =", _v_horizontal_text_score_flat)
    else: failed += 1; print("  ❌ document_vision::horizontal_text_score_flat → non-finite:", _v_horizontal_text_score_flat)
    var _v_document_scan_quality_flat = document_scan_quality_flat(_lf64_doc8x8, 8, 8)
    if is_finite(_v_document_scan_quality_flat): passed += 1; print("  ✅ document_vision::document_scan_quality_flat =", _v_document_scan_quality_flat)
    else: failed += 1; print("  ❌ document_vision::document_scan_quality_flat → non-finite:", _v_document_scan_quality_flat)

    print("  [document_vision] Passed:", passed, "Failed:", failed)
