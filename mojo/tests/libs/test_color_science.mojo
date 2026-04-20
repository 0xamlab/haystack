"""test_color_science.mojo — auto-generated tests for color_science library."""
from std.math import isnan, isinf
from color_science import delta_e_76, lab_to_lch_l, lab_to_lch_c, lab_to_lch_h, rgb_to_luminance, contrast_ratio, wcag_aa_pass, color_temperature_approx, metamerism_index, chromatic_adaptation_von_kries, cri_from_delta_e, whiteness_index_cie

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

    var _v_delta_e_76 = delta_e_76(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_delta_e_76): passed += 1; print("  ✅ color_science::delta_e_76 =", _v_delta_e_76)
    else: failed += 1; print("  ❌ color_science::delta_e_76 → non-finite:", _v_delta_e_76)
    var _v_lab_to_lch_l = lab_to_lch_l(0.5)
    if is_finite(_v_lab_to_lch_l): passed += 1; print("  ✅ color_science::lab_to_lch_l =", _v_lab_to_lch_l)
    else: failed += 1; print("  ❌ color_science::lab_to_lch_l → non-finite:", _v_lab_to_lch_l)
    var _v_lab_to_lch_c = lab_to_lch_c(0.5, 0.5)
    if is_finite(_v_lab_to_lch_c): passed += 1; print("  ✅ color_science::lab_to_lch_c =", _v_lab_to_lch_c)
    else: failed += 1; print("  ❌ color_science::lab_to_lch_c → non-finite:", _v_lab_to_lch_c)
    var _v_lab_to_lch_h = lab_to_lch_h(0.5, 0.5)
    if is_finite(_v_lab_to_lch_h): passed += 1; print("  ✅ color_science::lab_to_lch_h =", _v_lab_to_lch_h)
    else: failed += 1; print("  ❌ color_science::lab_to_lch_h → non-finite:", _v_lab_to_lch_h)
    var _v_rgb_to_luminance = rgb_to_luminance(0.5, 0.5, 0.5)
    if is_finite(_v_rgb_to_luminance): passed += 1; print("  ✅ color_science::rgb_to_luminance =", _v_rgb_to_luminance)
    else: failed += 1; print("  ❌ color_science::rgb_to_luminance → non-finite:", _v_rgb_to_luminance)
    var _v_contrast_ratio = contrast_ratio(0.5, 0.5)
    if is_finite(_v_contrast_ratio): passed += 1; print("  ✅ color_science::contrast_ratio =", _v_contrast_ratio)
    else: failed += 1; print("  ❌ color_science::contrast_ratio → non-finite:", _v_contrast_ratio)
    var _v_wcag_aa_pass = wcag_aa_pass(0.5, 0.5)
    if is_finite(_v_wcag_aa_pass): passed += 1; print("  ✅ color_science::wcag_aa_pass =", _v_wcag_aa_pass)
    else: failed += 1; print("  ❌ color_science::wcag_aa_pass → non-finite:", _v_wcag_aa_pass)
    var _v_color_temperature_approx = color_temperature_approx(0.5, 0.5)
    if is_finite(_v_color_temperature_approx): passed += 1; print("  ✅ color_science::color_temperature_approx =", _v_color_temperature_approx)
    else: failed += 1; print("  ❌ color_science::color_temperature_approx → non-finite:", _v_color_temperature_approx)
    var _v_metamerism_index = metamerism_index(0.5, 0.5)
    if is_finite(_v_metamerism_index): passed += 1; print("  ✅ color_science::metamerism_index =", _v_metamerism_index)
    else: failed += 1; print("  ❌ color_science::metamerism_index → non-finite:", _v_metamerism_index)
    var _v_chromatic_adaptation_von_kries = chromatic_adaptation_von_kries(0.5, 0.5)
    if is_finite(_v_chromatic_adaptation_von_kries): passed += 1; print("  ✅ color_science::chromatic_adaptation_von_kries =", _v_chromatic_adaptation_von_kries)
    else: failed += 1; print("  ❌ color_science::chromatic_adaptation_von_kries → non-finite:", _v_chromatic_adaptation_von_kries)
    var _v_cri_from_delta_e = cri_from_delta_e(0.5)
    if is_finite(_v_cri_from_delta_e): passed += 1; print("  ✅ color_science::cri_from_delta_e =", _v_cri_from_delta_e)
    else: failed += 1; print("  ❌ color_science::cri_from_delta_e → non-finite:", _v_cri_from_delta_e)
    var _v_whiteness_index_cie = whiteness_index_cie(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_whiteness_index_cie): passed += 1; print("  ✅ color_science::whiteness_index_cie =", _v_whiteness_index_cie)
    else: failed += 1; print("  ❌ color_science::whiteness_index_cie → non-finite:", _v_whiteness_index_cie)

    print("  [color_science] Passed:", passed, "Failed:", failed)
