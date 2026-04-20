"""test_printing.mojo — auto-generated tests for printing library."""
from std.math import isnan, isinf
from printing import dpi_to_lpi, pixel_count, file_size_uncompressed, bleed_area, spine_width, ink_coverage, paper_weight_gsm_to_lb, sheets_per_ream, cost_per_page, imposition_pages, color_delta_e, dot_gain_apparent

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_dpi_to_lpi = dpi_to_lpi(0.5, 0.5)
    if is_finite(_v_dpi_to_lpi): passed += 1; print("  ✅ printing::dpi_to_lpi =", _v_dpi_to_lpi)
    else: failed += 1; print("  ❌ printing::dpi_to_lpi → non-finite:", _v_dpi_to_lpi)
    var _v_pixel_count = pixel_count(0.5, 0.5, 0.5)
    if is_finite(_v_pixel_count): passed += 1; print("  ✅ printing::pixel_count =", _v_pixel_count)
    else: failed += 1; print("  ❌ printing::pixel_count → non-finite:", _v_pixel_count)
    var _v_file_size_uncompressed = file_size_uncompressed(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_file_size_uncompressed): passed += 1; print("  ✅ printing::file_size_uncompressed =", _v_file_size_uncompressed)
    else: failed += 1; print("  ❌ printing::file_size_uncompressed → non-finite:", _v_file_size_uncompressed)
    var _v_bleed_area = bleed_area(0.5, 0.5, 0.5)
    if is_finite(_v_bleed_area): passed += 1; print("  ✅ printing::bleed_area =", _v_bleed_area)
    else: failed += 1; print("  ❌ printing::bleed_area → non-finite:", _v_bleed_area)
    var _v_spine_width = spine_width(0.5, 0.5)
    if is_finite(_v_spine_width): passed += 1; print("  ✅ printing::spine_width =", _v_spine_width)
    else: failed += 1; print("  ❌ printing::spine_width → non-finite:", _v_spine_width)
    var _v_ink_coverage = ink_coverage(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_ink_coverage): passed += 1; print("  ✅ printing::ink_coverage =", _v_ink_coverage)
    else: failed += 1; print("  ❌ printing::ink_coverage → non-finite:", _v_ink_coverage)
    var _v_paper_weight_gsm_to_lb = paper_weight_gsm_to_lb(0.5)
    if is_finite(_v_paper_weight_gsm_to_lb): passed += 1; print("  ✅ printing::paper_weight_gsm_to_lb =", _v_paper_weight_gsm_to_lb)
    else: failed += 1; print("  ❌ printing::paper_weight_gsm_to_lb → non-finite:", _v_paper_weight_gsm_to_lb)
    _ = sheets_per_ream()
    passed += 1; print("  ✅ printing::sheets_per_ream")
    var _v_cost_per_page = cost_per_page(0.5, 0.5)
    if is_finite(_v_cost_per_page): passed += 1; print("  ✅ printing::cost_per_page =", _v_cost_per_page)
    else: failed += 1; print("  ❌ printing::cost_per_page → non-finite:", _v_cost_per_page)
    var _v_imposition_pages = imposition_pages(0.5, 0.5)
    if is_finite(_v_imposition_pages): passed += 1; print("  ✅ printing::imposition_pages =", _v_imposition_pages)
    else: failed += 1; print("  ❌ printing::imposition_pages → non-finite:", _v_imposition_pages)
    var _v_color_delta_e = color_delta_e(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_color_delta_e): passed += 1; print("  ✅ printing::color_delta_e =", _v_color_delta_e)
    else: failed += 1; print("  ❌ printing::color_delta_e → non-finite:", _v_color_delta_e)
    var _v_dot_gain_apparent = dot_gain_apparent(0.5, 0.5)
    if is_finite(_v_dot_gain_apparent): passed += 1; print("  ✅ printing::dot_gain_apparent =", _v_dot_gain_apparent)
    else: failed += 1; print("  ❌ printing::dot_gain_apparent → non-finite:", _v_dot_gain_apparent)

    print("  [printing] Passed:", passed, "Failed:", failed)
