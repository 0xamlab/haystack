"""bench_color_science.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from color_science import delta_e_76, lab_to_lch_l, lab_to_lch_c, lab_to_lch_h, rgb_to_luminance, contrast_ratio, wcag_aa_pass, color_temperature_approx, metamerism_index, chromatic_adaptation_von_kries, cri_from_delta_e, whiteness_index_cie
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_delta_e_76: Float64 = 0.0
    var _t0_delta_e_76 = perf_counter_ns()
    for _ in range(N):
        _acc_delta_e_76 += delta_e_76(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_delta_e_76 = perf_counter_ns()
    var _ns_delta_e_76 = Float64(_t1_delta_e_76 - _t0_delta_e_76) / Float64(N)
    print("MOJO_TIMING color_science::delta_e_76", _ns_delta_e_76, _acc_delta_e_76)
    var _acc_lab_to_lch_l: Float64 = 0.0
    var _t0_lab_to_lch_l = perf_counter_ns()
    for _ in range(N):
        _acc_lab_to_lch_l += lab_to_lch_l(0.5)
    var _t1_lab_to_lch_l = perf_counter_ns()
    var _ns_lab_to_lch_l = Float64(_t1_lab_to_lch_l - _t0_lab_to_lch_l) / Float64(N)
    print("MOJO_TIMING color_science::lab_to_lch_l", _ns_lab_to_lch_l, _acc_lab_to_lch_l)
    var _acc_lab_to_lch_c: Float64 = 0.0
    var _t0_lab_to_lch_c = perf_counter_ns()
    for _ in range(N):
        _acc_lab_to_lch_c += lab_to_lch_c(0.5, 0.5)
    var _t1_lab_to_lch_c = perf_counter_ns()
    var _ns_lab_to_lch_c = Float64(_t1_lab_to_lch_c - _t0_lab_to_lch_c) / Float64(N)
    print("MOJO_TIMING color_science::lab_to_lch_c", _ns_lab_to_lch_c, _acc_lab_to_lch_c)
    var _acc_lab_to_lch_h: Float64 = 0.0
    var _t0_lab_to_lch_h = perf_counter_ns()
    for _ in range(N):
        _acc_lab_to_lch_h += lab_to_lch_h(0.5, 0.5)
    var _t1_lab_to_lch_h = perf_counter_ns()
    var _ns_lab_to_lch_h = Float64(_t1_lab_to_lch_h - _t0_lab_to_lch_h) / Float64(N)
    print("MOJO_TIMING color_science::lab_to_lch_h", _ns_lab_to_lch_h, _acc_lab_to_lch_h)
    var _acc_rgb_to_luminance: Float64 = 0.0
    var _t0_rgb_to_luminance = perf_counter_ns()
    for _ in range(N):
        _acc_rgb_to_luminance += rgb_to_luminance(0.5, 0.5, 0.5)
    var _t1_rgb_to_luminance = perf_counter_ns()
    var _ns_rgb_to_luminance = Float64(_t1_rgb_to_luminance - _t0_rgb_to_luminance) / Float64(N)
    print("MOJO_TIMING color_science::rgb_to_luminance", _ns_rgb_to_luminance, _acc_rgb_to_luminance)
    var _acc_contrast_ratio: Float64 = 0.0
    var _t0_contrast_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_contrast_ratio += contrast_ratio(0.5, 0.5)
    var _t1_contrast_ratio = perf_counter_ns()
    var _ns_contrast_ratio = Float64(_t1_contrast_ratio - _t0_contrast_ratio) / Float64(N)
    print("MOJO_TIMING color_science::contrast_ratio", _ns_contrast_ratio, _acc_contrast_ratio)
    var _acc_wcag_aa_pass: Float64 = 0.0
    var _t0_wcag_aa_pass = perf_counter_ns()
    for _ in range(N):
        _acc_wcag_aa_pass += wcag_aa_pass(0.5, 0.5)
    var _t1_wcag_aa_pass = perf_counter_ns()
    var _ns_wcag_aa_pass = Float64(_t1_wcag_aa_pass - _t0_wcag_aa_pass) / Float64(N)
    print("MOJO_TIMING color_science::wcag_aa_pass", _ns_wcag_aa_pass, _acc_wcag_aa_pass)
    var _acc_color_temperature_approx: Float64 = 0.0
    var _t0_color_temperature_approx = perf_counter_ns()
    for _ in range(N):
        _acc_color_temperature_approx += color_temperature_approx(0.5, 0.5)
    var _t1_color_temperature_approx = perf_counter_ns()
    var _ns_color_temperature_approx = Float64(_t1_color_temperature_approx - _t0_color_temperature_approx) / Float64(N)
    print("MOJO_TIMING color_science::color_temperature_approx", _ns_color_temperature_approx, _acc_color_temperature_approx)
    var _acc_metamerism_index: Float64 = 0.0
    var _t0_metamerism_index = perf_counter_ns()
    for _ in range(N):
        _acc_metamerism_index += metamerism_index(0.5, 0.5)
    var _t1_metamerism_index = perf_counter_ns()
    var _ns_metamerism_index = Float64(_t1_metamerism_index - _t0_metamerism_index) / Float64(N)
    print("MOJO_TIMING color_science::metamerism_index", _ns_metamerism_index, _acc_metamerism_index)
    var _acc_chromatic_adaptation_von_kries: Float64 = 0.0
    var _t0_chromatic_adaptation_von_kries = perf_counter_ns()
    for _ in range(N):
        _acc_chromatic_adaptation_von_kries += chromatic_adaptation_von_kries(0.5, 0.5)
    var _t1_chromatic_adaptation_von_kries = perf_counter_ns()
    var _ns_chromatic_adaptation_von_kries = Float64(_t1_chromatic_adaptation_von_kries - _t0_chromatic_adaptation_von_kries) / Float64(N)
    print("MOJO_TIMING color_science::chromatic_adaptation_von_kries", _ns_chromatic_adaptation_von_kries, _acc_chromatic_adaptation_von_kries)
    var _acc_cri_from_delta_e: Float64 = 0.0
    var _t0_cri_from_delta_e = perf_counter_ns()
    for _ in range(N):
        _acc_cri_from_delta_e += cri_from_delta_e(0.5)
    var _t1_cri_from_delta_e = perf_counter_ns()
    var _ns_cri_from_delta_e = Float64(_t1_cri_from_delta_e - _t0_cri_from_delta_e) / Float64(N)
    print("MOJO_TIMING color_science::cri_from_delta_e", _ns_cri_from_delta_e, _acc_cri_from_delta_e)
    var _acc_whiteness_index_cie: Float64 = 0.0
    var _t0_whiteness_index_cie = perf_counter_ns()
    for _ in range(N):
        _acc_whiteness_index_cie += whiteness_index_cie(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_whiteness_index_cie = perf_counter_ns()
    var _ns_whiteness_index_cie = Float64(_t1_whiteness_index_cie - _t0_whiteness_index_cie) / Float64(N)
    print("MOJO_TIMING color_science::whiteness_index_cie", _ns_whiteness_index_cie, _acc_whiteness_index_cie)
