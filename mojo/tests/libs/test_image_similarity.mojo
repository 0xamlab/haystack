"""test_image_similarity.mojo — auto-generated tests for image_similarity."""
from std.math import isnan, isinf
from image_similarity import mean_squared_error_flat, mean_abs_error_flat, psnr_flat, normalized_cross_correlation_flat, ssim_global_flat, diff_fraction_flat, crop_region_similarity_flat, duplicate_score_flat

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
    var _lf64_doc8x8_alt = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):
                _lf64_doc8x8_alt.append(60.0)
            else:
                _lf64_doc8x8_alt.append(235.0)
    var _v_mean_squared_error_flat = mean_squared_error_flat(_lf64_doc8x8, _lf64_doc8x8_alt, 8, 8)
    if is_finite(_v_mean_squared_error_flat): passed += 1; print("  ✅ image_similarity::mean_squared_error_flat =", _v_mean_squared_error_flat)
    else: failed += 1; print("  ❌ image_similarity::mean_squared_error_flat → non-finite:", _v_mean_squared_error_flat)
    var _v_mean_abs_error_flat = mean_abs_error_flat(_lf64_doc8x8, _lf64_doc8x8_alt, 8, 8)
    if is_finite(_v_mean_abs_error_flat): passed += 1; print("  ✅ image_similarity::mean_abs_error_flat =", _v_mean_abs_error_flat)
    else: failed += 1; print("  ❌ image_similarity::mean_abs_error_flat → non-finite:", _v_mean_abs_error_flat)
    var _v_psnr_flat = psnr_flat(_lf64_doc8x8, _lf64_doc8x8_alt, 8, 8, 255.0)
    if is_finite(_v_psnr_flat): passed += 1; print("  ✅ image_similarity::psnr_flat =", _v_psnr_flat)
    else: failed += 1; print("  ❌ image_similarity::psnr_flat → non-finite:", _v_psnr_flat)
    var _v_normalized_cross_correlation_flat = normalized_cross_correlation_flat(_lf64_doc8x8, _lf64_doc8x8_alt, 8, 8)
    if is_finite(_v_normalized_cross_correlation_flat): passed += 1; print("  ✅ image_similarity::normalized_cross_correlation_flat =", _v_normalized_cross_correlation_flat)
    else: failed += 1; print("  ❌ image_similarity::normalized_cross_correlation_flat → non-finite:", _v_normalized_cross_correlation_flat)
    var _v_ssim_global_flat = ssim_global_flat(_lf64_doc8x8, _lf64_doc8x8_alt, 8, 8)
    if is_finite(_v_ssim_global_flat): passed += 1; print("  ✅ image_similarity::ssim_global_flat =", _v_ssim_global_flat)
    else: failed += 1; print("  ❌ image_similarity::ssim_global_flat → non-finite:", _v_ssim_global_flat)
    var _v_diff_fraction_flat = diff_fraction_flat(_lf64_doc8x8, _lf64_doc8x8_alt, 8, 8, 5.0)
    if is_finite(_v_diff_fraction_flat): passed += 1; print("  ✅ image_similarity::diff_fraction_flat =", _v_diff_fraction_flat)
    else: failed += 1; print("  ❌ image_similarity::diff_fraction_flat → non-finite:", _v_diff_fraction_flat)
    var _v_crop_region_similarity_flat = crop_region_similarity_flat(_lf64_doc8x8, _lf64_doc8x8_alt, 8, 8, 2, 2, 5, 5)
    if is_finite(_v_crop_region_similarity_flat): passed += 1; print("  ✅ image_similarity::crop_region_similarity_flat =", _v_crop_region_similarity_flat)
    else: failed += 1; print("  ❌ image_similarity::crop_region_similarity_flat → non-finite:", _v_crop_region_similarity_flat)
    var _v_duplicate_score_flat = duplicate_score_flat(_lf64_doc8x8, _lf64_doc8x8_alt, 8, 8)
    if is_finite(_v_duplicate_score_flat): passed += 1; print("  ✅ image_similarity::duplicate_score_flat =", _v_duplicate_score_flat)
    else: failed += 1; print("  ❌ image_similarity::duplicate_score_flat → non-finite:", _v_duplicate_score_flat)

    print("  [image_similarity] Passed:", passed, "Failed:", failed)
